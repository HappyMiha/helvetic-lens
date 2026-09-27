"""AI citations resolve an exact saved source without changing the historical note."""
import json
from uuid import uuid4

import pytest
from conftest import LAW_URL, policy
from sqlalchemy import select
from test_auth import _register
from test_product_document_history import setup
from test_product_dossiers import ROOT, create, post
from test_product_dossiers import signed as signed
from test_product_research import question
from test_product_research_preview import values
from test_product_source_health import connect

from helvetic_lens.models import DocumentWatch, Law, Organization, OrganizationMembership, Version
from helvetic_lens.product_models import DossierEntry


def captured(signed, product="pharma"):
    client, service, _, model = signed
    doc, parent, law_id, version_id, history = setup(client, product)
    thread, _ = question(client, parent)
    path = parent + "/discussion/" + thread["id"]
    preview = client.get(path + "/research-preview").json()
    source = next(item for item in preview["input"]["sources"] if item["kind"] == "saved_page_extract")
    assert source["document_id"] == law_id and source["key"] == version_id
    model.responses = [json.dumps({"findings": [{"claim": "The saved source contains this passage.",
        "citations": [{"source_id": source["id"], "quote": source["text"][:40]}]}],
        "unknowns": ["Review the source's current status."], "search_queries": ["official document current status"]})]
    response = post(client, path + "/research", values(preview))
    assert response.status_code == 200, response.text
    note = response.json()
    route = path + "/research/" + note["id"] + "/sources/" + source["id"] + "/document"
    return doc, parent, path, law_id, version_id, history, source, note, route


@pytest.mark.parametrize("product", ["pharma", "loyer"])
def test_exact_citation_target_keeps_recorded_revision_and_historical_excerpt(signed, product):
    client, service, _, model = signed
    _, parent, path, law_id, version_id, history, source, note, route = captured(signed, product)
    assert json.loads(model.calls[-1][1])["sources"] == note["data"]["sources"]
    before = client.get(parent).json()["entry_count"], len(service.fetcher.calls), len(model.calls)
    target = client.get(route)
    assert target.status_code == 200 and "no-store" in target.headers["cache-control"]
    assert target.json() == {"document_id": law_id, "version_id": version_id,
        "expected_revision": source["evidence_revision"], "revision_recorded": True}
    page = client.get(history + "/" + version_id, params={"expected_revision": target.json()["expected_revision"]})
    assert page.status_code == 200
    with service.db.session() as session:
        session.get(Version, version_id).text = "Corrected document contents."
        session.commit()
    assert client.get(route).json() == target.json()
    assert client.get(history + "/" + version_id, params={"expected_revision": source["evidence_revision"]}).status_code == 409
    stored = next(row for row in client.get(path).json()["replies"] if row["id"] == note["id"])
    assert stored["data"]["sources"] == note["data"]["sources"]
    exported = client.get(parent + "/export").json()
    assert next(row for row in exported["entries"] if row["id"] == note["id"])["data"]["sources"] == note["data"]["sources"]
    assert before == (client.get(parent).json()["entry_count"], len(service.fetcher.calls), len(model.calls))


def test_legacy_note_has_explicit_unrecorded_revision_without_backfilling(signed):
    client, service, _, _ = signed
    _, _, path, _, version_id, history, _, note, route = captured(signed)
    with service.db.session() as session:
        entry = session.get(DossierEntry, note["id"])
        data = json.loads(json.dumps(entry.data_json))
        for source in data["sources"]:
            source.pop("document_id", None)
            source.pop("evidence_revision", None)
        entry.data_json = data
        session.get(Version, version_id).text = "A later corrected source."
        session.commit()
    target = client.get(route).json()
    assert target["revision_recorded"] is False and target["expected_revision"] is None
    assert client.get(history + "/" + version_id).status_code == 200
    stored = next(row for row in client.get(path).json()["replies"] if row["id"] == note["id"])
    assert stored["data"] == data


def test_note_source_scope_private_draft_product_and_viewer_access(signed):
    client, service, identity, _ = signed
    _, parent, path, _, _, _, source, note, route = captured(signed)
    private, _ = create(client)
    private_parent = ROOT + "/" + private["id"]
    private_thread, _ = question(client, private_parent)
    with service.db.session() as session:
        entry = DossierEntry(dossier_id=private["id"], kind="research", request_key=str(uuid4()),
            thread_id=private_thread["id"], data_json=note["data"], actor_user_id=identity["user"]["id"])
        session.add(entry)
        session.add(DossierEntry(dossier_id=private["id"], kind="monitor", request_key=str(uuid4()),
            data_json={"law_id": source["document_id"]}, actor_user_id=identity["user"]["id"]))
        session.flush()
        private_note_id = entry.id
        session.commit()
    private_route = private_parent + "/discussion/" + private_thread["id"] + "/research/" + private_note_id + "/sources/" + source["id"] + "/document"
    assert client.get(private_route).status_code == 200
    wrong_note = post(client, parent + "/entries", {"request_key": str(uuid4()), "kind": "note", "body": "A normal note."}).json()
    for wrong in (route.replace("pharma", "loyer"), route.replace(note["id"], str(uuid4())),
                  route.replace(note["id"], wrong_note["id"]), route.replace(path.rsplit("/", 1)[-1], str(uuid4())),
                  route.replace("/sources/" + source["id"], "/sources/unknown"), route.replace(parent, private_parent)):
        assert client.get(wrong).status_code == 404
    viewer = _register(client, "citation-reader@example.ch").json()
    assert client.get(route).status_code == 404
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=viewer["user"]["id"], organization_id=identity["organization"]["id"], role="viewer"))
        session.commit()
    assert post(client, "/api/auth/session/organization", {"organization_id": identity["organization"]["id"]}).status_code == 200
    assert client.get(route).status_code == 200
    assert client.get(private_route).status_code == 404
    assert post(client, route, {}).status_code == 403
    client.cookies.clear()
    assert client.get(route).status_code == 401


@pytest.mark.parametrize("change", ["law", "version", "watch", "monitor"])
def test_changed_source_access_removes_preview_candidate_and_denies_locator(signed, change):
    client, service, identity, model = signed
    _, parent, path, law_id, version_id, _, _, _, route = captured(signed)
    preview = client.get(path + "/research-preview").json()
    before = len(model.calls), len(service.fetcher.calls)
    with service.db.session(include_all_organizations=True) as session:
        foreign = Organization(name="Another document owner", slug="another-document-owner")
        session.add(foreign)
        session.flush()
        if change == "law":
            session.get(Law, law_id).owner_organization_id = foreign.id
        elif change == "version":
            session.get(Version, version_id).owner_organization_id = foreign.id
        elif change == "watch":
            session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law_id,
                DocumentWatch.organization_id == identity["organization"]["id"])).organization_id = foreign.id
        else:
            entry = session.scalar(select(DossierEntry).where(DossierEntry.dossier_id == parent.rsplit("/", 1)[-1], DossierEntry.kind == "monitor"))
            session.delete(entry)
        session.commit()
    assert client.get(route).status_code == 404
    assert not any(source["kind"] == "saved_page_extract" for source in client.get(path + "/research-preview").json()["input"]["sources"])
    assert post(client, path + "/research", values(preview)).status_code == 409
    assert (len(model.calls), len(service.fetcher.calls)) == before


def test_recorded_source_identity_never_retargets_a_reassigned_version(signed):
    client, service, _, _ = signed
    _, parent, _, _, version_id, _, _, _, route = captured(signed)
    url = LAW_URL + "?second-document=1"
    service.fetcher.values[url] = policy("Another source.")
    other_law = connect(client, parent, url)
    with service.db.session() as session:
        session.get(Version, version_id).law_id = other_law
        session.commit()
    assert client.get(route).status_code == 404


@pytest.mark.parametrize("phase", ["before", "during"])
def test_same_excerpt_with_changed_evidence_revision_invalidates_preview(signed, phase):
    client, service, _, model = signed
    _, _, path, _, version_id, _, _, note, _ = captured(signed)
    preview = client.get(path + "/research-preview").json()
    def correct():
        with service.db.session() as session:
            version = session.get(Version, version_id)
            version.passages = [{"id": "updated-extraction", "text": version.text}]
            session.commit()
    calls = len(model.calls)
    if phase == "during":
        async def update_during_inference(*args, **kwargs):
            correct()
            return json.dumps({"findings": [], "unknowns": ["Recheck evidence."], "search_queries": ["official current evidence"]})
        service.model_client.complete = update_during_inference
        assert post(client, path + "/research", values(preview)).status_code == 409
    else:
        correct()
        assert post(client, path + "/research", values(preview)).status_code == 409
        assert len(model.calls) == calls
    updated = client.get(path + "/research-preview").json()
    old_source, new_source = preview["input"]["sources"][0], updated["input"]["sources"][0]
    assert old_source["text"] == new_source["text"] and old_source["sha256"] == new_source["sha256"]
    assert old_source["evidence_revision"] != new_source["evidence_revision"]
    assert updated["evidence_fingerprint"] != preview["evidence_fingerprint"]
    with service.db.session() as session:
        assert session.get(DossierEntry, note["id"]).data_json["sources"] == note["data"]["sources"]
        assert len(list(session.scalars(select(DossierEntry.id).where(DossierEntry.kind == "research")))) == 1


def test_malformed_or_non_page_snapshot_never_falls_back_to_another_source(signed):
    client, service, _, _ = signed
    _, _, _, _, _, _, source, note, route = captured(signed)
    for changes in ({"kind": "team_contribution"}, {"key": str(uuid4())}, {"document_id": str(uuid4())},
                    {"evidence_revision": 0}, {"evidence_revision": True}, {"evidence_revision": None},
                    {"evidence_revision": "1"}):
        with service.db.session() as session:
            entry = session.get(DossierEntry, note["id"])
            entry.data_json = {**note["data"], "sources": [{**source, **changes}]}
            session.commit()
        assert client.get(route).status_code == 404
