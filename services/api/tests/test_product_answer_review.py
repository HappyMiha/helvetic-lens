"""Accepted answers retain human review state without rewriting historical evidence."""
import json
from uuid import uuid4

import pytest
from conftest import LAW_URL, policy
from sqlalchemy import select
from test_auth import _register
from test_law_history_metadata import recording
from test_product_dossiers import ROOT, create, post
from test_product_dossiers import signed as signed
from test_product_research_documents import captured
from test_product_source_health import connect

from helvetic_lens.legal_profile_models import LegalMonitoringProfile
from helvetic_lens.models import DocumentWatch, Law, Organization, OrganizationMembership, Version
from helvetic_lens.product_models import DossierEntry, ResearchThread


def accept(client, path, note):
    current = client.get(path).json()
    response = post(client, path + "/accept", {"expected_revision": current["revision"], "entry_id": note["id"]})
    assert response.status_code == 200, response.text
    return client.get(path).json()


def confirmation(state):
    return {"expected_revision": state["revision"], "entry_id": state["accepted_entry_id"],
            "expected_review": state["answer_review"]["fingerprint"]}


def codes(state):
    return {reason["code"] for reason in state["answer_review"]["reasons"]}


@pytest.mark.parametrize("product", ["pharma", "loyer"])
def test_corrected_source_review_reconfirmation_and_next_change(signed, product):
    client, service, _, model = signed
    _, parent, path, _, version_id, _, source, note, _ = captured(signed, product)
    first = accept(client, path, note)
    assert not first["answer_needs_review"] and not codes(first)
    before_reads = client.get(parent).json()["entry_count"], len(service.fetcher.calls), len(model.calls)
    with service.db.session() as session:
        version = session.get(Version, version_id)
        saved_at = version.created_at
        version.text = "Corrected source text."
        session.commit()
    with recording(service) as (_, loaded):
        changed = client.get(path).json()
        assert not loaded
    assert codes(changed) == {"source_changed"} and changed["answer_needs_review"]
    assert changed["answer_review"]["reasons"][0]["source_ids"] == [source["id"]]
    assert changed["accepted_entry_id"] == note["id"] and changed["accepted"]["data"] == note["data"]
    assert before_reads == (client.get(parent).json()["entry_count"], len(service.fetcher.calls), len(model.calls))
    brief = client.get(parent + "/brief")
    assert "Review needed:" in brief.text and "Saved evidence behind this AI answer changed" in brief.text
    assert post(client, path + "/accept", confirmation(changed)).status_code == 200
    reviewed = client.get(path).json()
    assert not reviewed["answer_needs_review"] and reviewed["accepted_at"] != first["accepted_at"]
    assert reviewed["accepted"]["data"] == note["data"]
    exported = client.get(parent + "/export").json()
    audits = [entry for entry in exported["entries"] if entry["kind"] == "review" and entry["data"].get("accepted_entry_id") == note["id"]]
    assert len(audits) == 2 and all(entry["data"]["answer_evidence"]["schema_version"] == 1 for entry in audits)
    assert all(entry["author"] == "Ada Example" for entry in audits)
    states = [entry["data"]["answer_evidence"]["sources"][0]["revision"] for entry in audits]
    assert len(set(states)) == 2
    with service.db.session() as session:
        version = session.get(Version, version_id)
        assert version.created_at == saved_at
        version.passages = [{"id": "changed-extraction", "text": version.text}]
        session.commit()
    assert codes(client.get(path).json()) == {"source_changed"}


@pytest.mark.parametrize("change", ["law", "version", "watch", "monitor"])
def test_unavailable_source_acknowledgement_and_restoration_are_distinct(signed, change):
    client, service, identity, _ = signed
    _, parent, path, law_id, version_id, _, _, note, _ = captured(signed)
    accept(client, path, note)
    with service.db.session(include_all_organizations=True) as session:
        foreign = Organization(name="Unrelated private owner", slug="unrelated-private-owner")
        session.add(foreign)
        session.flush()
        if change == "law":
            session.get(Law, law_id).owner_organization_id = foreign.id
        elif change == "version":
            session.get(Version, version_id).owner_organization_id = foreign.id
        elif change == "watch":
            watch = session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law_id,
                DocumentWatch.organization_id == identity["organization"]["id"]))
            watch_id = watch.id
            watch.organization_id = foreign.id
        else:
            entry = session.scalar(select(DossierEntry).where(DossierEntry.dossier_id == parent.rsplit("/", 1)[-1], DossierEntry.kind == "monitor"))
            entry_id = entry.id
            entry.kind = "note"
        session.commit()
    changed = client.get(path).json()
    assert codes(changed) == {"source_unavailable"}
    assert "Unrelated private owner" not in json.dumps(changed["answer_review"])
    assert post(client, path + "/accept", confirmation(changed)).status_code == 200
    assert not client.get(path).json()["answer_needs_review"]
    with service.db.session(include_all_organizations=True) as session:
        if change == "law":
            session.get(Law, law_id).owner_organization_id = None
        elif change == "version":
            session.get(Version, version_id).owner_organization_id = None
        elif change == "watch":
            session.get(DocumentWatch, watch_id).organization_id = identity["organization"]["id"]
        else:
            session.get(DossierEntry, entry_id).kind = "monitor"
        session.commit()
    restored = client.get(path).json()
    assert codes(restored) == {"source_changed"} and restored["accepted_entry_id"] == note["id"]


def test_stale_reconfirmation_refuses_further_source_or_new_material_changes(signed):
    client, service, _, _ = signed
    _, parent, path, _, version_id, _, _, note, _ = captured(signed)
    original = accept(client, path, note)
    token = confirmation(original)
    with service.db.session() as session:
        session.get(Version, version_id).text = "Changed before acknowledgement."
        session.commit()
    assert post(client, path + "/accept", token).status_code == 409
    changed = client.get(path).json()
    assert changed["accepted_at"] == original["accepted_at"] and changed["revision"] == original["revision"]
    fresh = confirmation(changed)
    added = post(client, parent + "/entries", {"request_key": str(uuid4()), "kind": "note", "body": "A further observation for review."})
    assert added.status_code == 201
    assert post(client, path + "/accept", fresh).status_code == 409
    current = client.get(path).json()
    assert codes(current) == {"source_changed", "new_contributions"}
    assert post(client, path + "/accept", confirmation(current)).status_code == 200
    assert not client.get(path).json()["answer_needs_review"]
    assert post(client, path + "/accept", confirmation(current)).status_code == 409


@pytest.mark.parametrize("legacy_source", [False, True])
def test_old_acceptance_without_baseline_requires_review_only_when_needed(signed, legacy_source):
    client, service, _, _ = signed
    _, _, path, _, version_id, _, _, note, _ = captured(signed)
    initial = accept(client, path, note)
    with service.db.session() as session:
        audit = session.scalar(select(DossierEntry).where(DossierEntry.kind == "review"))
        audit.data_json = {key: value for key, value in audit.data_json.items() if key != "answer_evidence"}
        if legacy_source:
            saved = session.get(DossierEntry, note["id"])
            data = json.loads(json.dumps(saved.data_json))
            for source in data["sources"]:
                source.pop("document_id", None)
                source.pop("evidence_revision", None)
            saved.data_json = data
        session.commit()
    state = client.get(path).json()
    assert codes(state) == ({"source_revision_unknown"} if legacy_source else set())
    if not legacy_source:
        with service.db.session() as session:
            session.get(Version, version_id).text = "Legacy accepted evidence corrected."
            session.commit()
        state = client.get(path).json()
        assert codes(state) == {"source_changed"}
    # Older clients can still explicitly reconfirm without the new optional fingerprint.
    assert post(client, path + "/accept", {"expected_revision": initial["revision"], "entry_id": note["id"]}).status_code == 200
    assert not client.get(path).json()["answer_needs_review"]


def test_review_fingerprint_does_not_grant_access_or_change_acceptance_target(signed):
    client, service, identity, _ = signed
    doc, _, path, _, version_id, _, _, note, _ = captured(signed)
    initial = accept(client, path, note)
    data = confirmation(initial)
    assert client.post(path + "/accept", json=data).status_code == 403
    assert post(client, path + "/accept", {**data, "expected_review": "bad"}).status_code == 422
    assert post(client, path + "/accept", {**data, "entry_id": None}).status_code == 409
    assert post(client, path.replace("pharma", "loyer") + "/accept", data).status_code == 404
    private, _ = create(client)
    private_path = ROOT + "/" + private["id"] + "/discussion/" + path.rsplit("/", 1)[-1]
    assert client.get(private_path).status_code == 404
    with service.db.session() as session:
        session.get(Version, version_id).text = "A revised page."
        session.commit()
    reader = _register(client, "answer-review-reader@example.ch").json()
    assert client.get(path).status_code == 404
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=reader["user"]["id"], organization_id=identity["organization"]["id"], role="viewer"))
        session.commit()
    assert post(client, "/api/auth/session/organization", {"organization_id": identity["organization"]["id"]}).status_code == 200
    visible = client.get(path).json()
    assert codes(visible) == {"source_changed"}
    assert post(client, path + "/accept", confirmation(visible)).status_code == 403
    with service.db.session() as session:
        assert session.get(ResearchThread, path.rsplit("/", 1)[-1]).accepted_at is not None
        session.get(LegalMonitoringProfile, doc["profile"]["id"]).status = "draft"
        session.commit()
    assert client.get(path).status_code == 404
    client.cookies.clear()
    assert client.get(path).status_code == 401


def test_reassigned_source_and_reopening_never_rewrite_the_accepted_note(signed):
    client, service, _, _ = signed
    _, parent, path, _, version_id, _, _, note, _ = captured(signed)
    accept(client, path, note)
    url = LAW_URL + "?reassigned-answer-source=1"
    service.fetcher.values[url] = policy("Another watched source.")
    other_law = connect(client, parent, url)
    # Explicitly acknowledge the additional watched page before changing the old identity.
    state = client.get(path).json()
    assert post(client, path + "/accept", confirmation(state)).status_code == 200
    with service.db.session() as session:
        session.get(Version, version_id).law_id = other_law
        session.commit()
    changed = client.get(path).json()
    assert codes(changed) == {"source_unavailable"}
    assert changed["accepted"]["data"] == note["data"]
    assert post(client, path + "/accept", {"expected_revision": changed["revision"], "entry_id": None}).status_code == 200
    reopened = client.get(path).json()
    assert reopened["accepted"] is None and reopened["accepted_at"] is None and not reopened["answer_needs_review"]
    assert reopened["answer_review"]["reasons"] == []
    with service.db.session() as session:
        assert session.get(DossierEntry, note["id"]).data_json == note["data"]
