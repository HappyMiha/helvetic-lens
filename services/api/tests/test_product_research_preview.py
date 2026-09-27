"""Review exact saved research inputs before inference, with current private scope."""
import hashlib
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_auth import _register
from test_product_dossiers import ROOT, active, create, post
from test_product_dossiers import signed as signed
from test_product_reference_library import seed
from test_product_research import question
from test_product_source_reviews import reference, request

from helvetic_lens.db import utcnow
from helvetic_lens.legal_profile_models import LegalMonitoringProfile
from helvetic_lens.models import OrganizationMembership, UserSession
from helvetic_lens.product_models import DossierEntry, ResearchThread

EMPTY_ANSWER = json.dumps({"findings": [], "unknowns": ["Verify the original evidence."], "search_queries": ["official renal evidence"]})


def setup(client, product="pharma"):
    _, initial = create(client)
    doc = post(client, ROOT.replace("pharma", product), {**initial, "creation_key": str(uuid4())}).json()
    parent = ROOT.replace("pharma", product) + "/" + doc["id"]
    thread, _ = question(client, parent, "Renal nephropathy evidence assessment")
    return doc, parent, thread, parent + "/discussion/" + thread["id"]


def values(preview, **changes):
    return {"request_key": str(uuid4()), "expected_revision": preview["expected_revision"],
            "expected_evidence": preview["evidence_fingerprint"], **changes}


@pytest.mark.parametrize("product", ["pharma", "loyer"])
def test_preview_finds_old_relevant_text_before_new_noise_and_is_read_only(signed, product):
    client, service, _, model = signed
    doc, parent, _, path = setup(client, product)
    body = "Unrelated archive preamble. " * 140 + "Renal nephropathy evidence requires a documented review before use. " * 40
    with service.db.session() as session:
        old = seed(session, doc["id"], title="Archived renal nephropathy evidence", body=body,
                   created_at=utcnow() - timedelta(days=3))
        session.flush()
        source_id = old.id
        stamp = utcnow()
        for i in range(60):
            seed(session, doc["id"], title=f"Office filing item {i}", body="An unrelated administrative entry.",
                 created_at=stamp, url=f"https://example.ch/filing/{i}")
        for i in range(35):
            seed(session, doc["id"], title="Renal nephropathy evidence", body="   ", created_at=stamp)
        session.commit()
    before = client.get(parent).json()["entry_count"]
    read = client.get(path + "/research-preview")
    assert read.status_code == 200 and "no-store" in read.headers["cache-control"]
    preview = read.json()
    excerpts = preview["input"]["sources"]
    assert len(excerpts) == 18 and excerpts[0]["key"] == source_id
    exact = excerpts[0]
    assert "requires a documented review before use" in exact["text"]
    assert exact["text"] in body and len(exact["text"]) <= 1800
    assert exact["sha256"] == hashlib.sha256(exact["text"].encode()).hexdigest()
    assert exact["entry_kind"] == "reference"
    for _ in range(7):
        again = client.get(path + "/research-preview").json()
        assert again["input"] == preview["input"] and again["evidence_fingerprint"] == preview["evidence_fingerprint"]
    assert client.get(parent).json()["entry_count"] == before
    assert not model.calls and not service.fetcher.calls
    model.responses = [EMPTY_ANSWER]
    assert post(client, path + "/research", values(preview)).status_code == 200
    assert len(model.calls) == 1  # Preview reads do not consume the AI-specific budget.


def test_generation_uses_exact_preview_and_retries_never_silently_change_inputs(signed):
    client, _, _, model = signed
    _, parent, thread, path = setup(client)
    reference(client, parent)
    preview = client.get(path + "/research-preview").json()
    model.responses = [EMPTY_ANSWER]
    body = values(preview)
    response = post(client, path + "/research", body)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert json.loads(model.calls[0][1]) == preview["input"]
    assert saved["data"]["sources"] == preview["input"]["sources"]
    assert saved["data"]["input_fingerprint"] == saved["data"]["preview_fingerprint"] == preview["evidence_fingerprint"]
    assert saved["thread_id"] == thread["id"]
    assert post(client, path + "/research", body).json()["id"] == saved["id"]
    assert post(client, path + "/research", {**body, "expected_evidence": "0" * 64}).status_code == 409
    assert post(client, path + "/research", {"request_key": body["request_key"], "expected_revision": body["expected_revision"]}).status_code == 409
    assert len(model.calls) == 1 and client.get(path).json()["accepted"] is None


@pytest.mark.parametrize("changed", ["question", "profile", "goal", "evidence", "review"])
def test_stale_preview_is_rejected_before_calling_model(signed, changed):
    client, service, _, model = signed
    doc, parent, thread, path = setup(client)
    ref = reference(client, parent)
    preview = client.get(path + "/research-preview").json()
    with service.db.session() as session:
        if changed == "question":
            session.get(ResearchThread, thread["id"]).revision += 1
        elif changed in ("profile", "goal"):
            profile = session.get(LegalMonitoringProfile, doc["profile"]["id"])
            if changed == "profile":
                profile.revision += 1
            else:
                profile.config_json = {**profile.config_json, "goal": "A changed monitoring goal"}
        elif changed == "evidence":
            seed(session, doc["id"], title="New renal evidence", body="A new source excerpt needs review.")
        else:
            # Including the same URL leaves selected text unchanged, but changes the reviewed input set.
            session.add(DossierEntry(dossier_id=doc["id"], request_key=str(uuid4()), kind="source_review", url=ref["url"],
                body="Explicit inclusion", data_json={"reference_id": ref["id"], "revision": 1, "decision": "include", "expected_review_id": None}))
        session.commit()
    rejected = post(client, path + "/research", values(preview))
    assert rejected.status_code == 409, rejected.text
    assert not model.calls
    with service.db.session() as session:
        assert session.scalar(select(DossierEntry).where(DossierEntry.kind == "research")) is None
    refreshed = client.get(path + "/research-preview").json()
    assert refreshed["evidence_fingerprint"] != preview["evidence_fingerprint"]


def test_preview_exclusions_empty_inputs_and_legacy_generation(signed):
    client, _, _, model = signed
    _, parent, _, path = setup(client)
    ref = reference(client, parent)
    post(client, parent + "/sources/" + ref["id"] + "/reviews", request())
    preview = client.get(path + "/research-preview").json()
    assert preview["input"]["sources"] == [] and preview["selection"]["excluded_urls"] == 1
    model.responses = [EMPTY_ANSWER]
    body = {"expected_revision": preview["expected_revision"], "request_key": str(uuid4())}
    saved = post(client, path + "/research", body).json()
    assert saved["data"]["sources"] == [] and saved["data"]["preview_fingerprint"] is None
    assert post(client, path + "/research", body).json()["id"] == saved["id"]
    assert len(model.calls) == 1


def test_preview_scope_viewers_strict_inputs_and_csrf(signed):
    client, service, identity, model = signed
    private, private_parent, _, private_path = setup(client)
    shared, parent, thread, path = setup(client)
    reference(client, parent)
    active(client, shared)
    preview = client.get(path + "/research-preview").json()
    for wrong in (path.replace("pharma", "loyer"), private_parent + "/discussion/" + thread["id"],
                  parent + "/discussion/" + str(uuid4())):
        assert client.get(wrong + "/research-preview").status_code == 404
    assert post(client, path + "/research", values(preview, expected_evidence="not-a-digest")).status_code == 422
    assert post(client, path + "/research", {**values(preview), "sources": preview["input"]["sources"]}).status_code == 422
    assert client.post(path + "/research", json=values(preview)).status_code == 403
    reader = _register(client, "preview-reader@example.ch").json()
    assert client.get(path + "/research-preview").status_code == 404
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=reader["user"]["id"], organization_id=identity["organization"]["id"], role="viewer"))
        session.commit()
    assert post(client, "/api/auth/session/organization", {"organization_id": identity["organization"]["id"]}).status_code == 200
    assert client.get(path + "/research-preview").json()["input"] == preview["input"]
    assert client.get(private_path + "/research-preview").status_code == 404
    assert post(client, path + "/research", values(preview)).status_code == 403
    assert not model.calls
    client.cookies.clear()
    assert client.get(path + "/research-preview").status_code == 401


@pytest.mark.parametrize("changed", ["role", "session"])
def test_generation_rechecks_current_authorization_after_inference(signed, changed):
    client, service, identity, _ = signed
    _, _, _, path = setup(client)
    preview = client.get(path + "/research-preview").json()
    async def revoke(*args, **kwargs):
        with service.db.session() as session:
            if changed == "role":
                session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"])).role = "viewer"
            else:
                session.scalar(select(UserSession).where(UserSession.user_id == identity["user"]["id"])).revoked_at = utcnow()
            session.commit()
        return EMPTY_ANSWER
    service.model_client.complete = revoke
    response = post(client, path + "/research", values(preview))
    assert response.status_code in (401, 403), response.text
    with service.db.session() as session:
        assert session.scalar(select(DossierEntry).where(DossierEntry.kind == "research")) is None


def test_preview_cannot_be_replayed_on_another_question_or_by_another_author(signed):
    client, service, identity, model = signed
    doc, parent, _, path = setup(client)
    active(client, doc)
    reference(client, parent)
    original = client.get(path + "/research-preview").json()
    other, _ = question(client, parent, original["input"]["title"])
    other_path = parent + "/discussion/" + other["id"]
    assert post(client, other_path + "/research", values(original)).status_code == 409
    assert not model.calls
    model.responses = [EMPTY_ANSWER]
    body = values(original)
    saved = post(client, path + "/research", body)
    assert saved.status_code == 200, saved.text
    another = _register(client, "preview-colleague@example.ch").json()
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=another["user"]["id"], organization_id=identity["organization"]["id"], role="organization_admin"))
        session.commit()
    assert post(client, "/api/auth/session/organization", {"organization_id": identity["organization"]["id"]}).status_code == 200
    assert post(client, path + "/research", body).status_code == 409
    assert len(model.calls) == 1


@pytest.mark.parametrize("changed", ["role", "session"])
def test_generation_checks_fresh_authorization_before_model_call(signed, monkeypatch, changed):
    from helvetic_lens import product_research

    client, service, identity, model = signed
    _, _, _, path = setup(client)
    preview = client.get(path + "/research-preview").json()
    original = product_research.principal
    def revoke(session, actor, now, *, write=False):
        if write:
            with service.db.session() as other:
                if changed == "role":
                    other.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"])).role = "viewer"
                else:
                    other.scalar(select(UserSession).where(UserSession.user_id == identity["user"]["id"])).revoked_at = utcnow()
                other.commit()
        return original(session, actor, now, write=write)
    monkeypatch.setattr(product_research, "principal", revoke)
    assert post(client, path + "/research", values(preview)).status_code in (401, 403)
    assert not model.calls
