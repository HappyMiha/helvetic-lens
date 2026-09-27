"""Team source choices retain history and govern only new research in the same dossier."""
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from conftest import LAW_URL
from sqlalchemy import select
from test_auth import _register
from test_product_dossiers import ROOT, active, create, post
from test_product_dossiers import signed as signed
from test_product_research import question

from helvetic_lens import product_research, product_source_reviews
from helvetic_lens.db import utcnow
from helvetic_lens.models import OrganizationMembership, UserSession
from helvetic_lens.product_api import dossier
from helvetic_lens.product_models import DossierEntry


def reference(client, path, *, url=LAW_URL):
    result = post(client, path + "/entries", {"request_key": str(uuid4()), "kind": "reference", "title": "Original source",
        "url": url, "body": "The catalogue reports an observed change requiring professional review."})
    assert result.status_code == 201, result.text
    return result.json()


def request(**changes):
    return {"request_key": str(uuid4()), "expected_review_id": None, "decision": "exclude", "reason": "Outside the current question's scope.", **changes}


def setup(client):
    doc, _ = create(client)
    path = ROOT + "/" + doc["id"]
    ref = reference(client, path)
    return doc, path, ref, path + "/sources/" + ref["id"] + "/reviews"


def test_reviews_share_exact_url_keep_history_retry_and_escape_brief_export(signed):
    client, service, _, model = signed
    doc, path, ref, route = setup(client)
    duplicate = reference(client, path)
    other = reference(client, path, url=LAW_URL + "?another=1")
    other_doc, _ = create(client)
    separate = reference(client, ROOT + "/" + other_doc["id"])
    values = request(reason='Unrelated <script>source</script> & still retained.')
    response = post(client, route, values)
    assert response.status_code == 201, response.text
    first = response.json()
    assert first["author"] == "Ada Example" and first["data"]["revision"] == 1
    assert post(client, route, values).json()["id"] == first["id"]
    rows = {e["id"]: e for e in client.get(path).json()["entries"]}
    assert rows[ref["id"]]["source_review"] == rows[duplicate["id"]]["source_review"] == first
    assert rows[other["id"]]["source_review"] is None
    assert client.get(ROOT + "/" + other_doc["id"]).json()["entries"][0]["source_review"] is None
    assert separate["data"] == ref["data"]
    restored = post(client, route, request(expected_review_id=first["id"], decision="include", reason="Now relevant to the revised question.")).json()
    assert restored["data"]["revision"] == 2
    assert post(client, route, values).json()["id"] == first["id"]
    history = client.get(route).json()
    assert history["current"]["id"] == restored["id"] and history["total"] == 2
    assert [x["id"] for x in history["items"]] == [restored["id"], first["id"]]
    exported = client.get(path + "/export").json()["entries"]
    assert next(e for e in exported if e["id"] == ref["id"])["source_review"]["id"] == restored["id"]
    assert {e["id"] for e in exported if e["kind"] == "source_review"} == {first["id"], restored["id"]}
    brief = client.get(path + "/brief").text
    assert 'Include in AI research' in brief and 'Latest 2 of 2 reviews' in brief
    assert '&lt;script&gt;source&lt;/script&gt;' in brief and '<script>' not in brief and 'Ada Example' in brief
    assert not service.fetcher.calls and not model.calls


def test_stale_duplicate_reference_reviews_and_request_key_collisions_fail(signed):
    client, _, _, _ = signed
    _, path, _, route = setup(client)
    duplicate = reference(client, path)
    other_route = path + "/sources/" + duplicate["id"] + "/reviews"
    values = request()
    saved = post(client, route, values).json()
    assert post(client, other_route, request()).status_code == 409
    for change in ({"decision": "include"}, {"reason": "Changed rationale"}, {"expected_review_id": saved["id"]}):
        assert post(client, route, {**values, **change}).status_code == 409
    assert post(client, other_route, values).status_code == 409
    reset = post(client, other_route, request(expected_review_id=saved["id"], decision="unreviewed")).json()
    assert reset["data"]["revision"] == 2 and client.get(route).json()["current"]["id"] == reset["id"]
    existing = {"request_key": str(uuid4()), "kind": "note", "body": "Keep the original entry"}
    assert post(client, path + "/entries", existing).status_code == 201
    assert post(client, route, request(request_key=existing["request_key"], expected_review_id=reset["id"])).status_code == 409
    for bad in ({"decision": "verified"}, {"reason": "  "}, {"reason": "x" * 2001}, {"expected_review_id": "fake"}, {"url": "https://evil.example"}):
        assert post(client, route, request(**bad)).status_code == 422
    missing = request()
    del missing["expected_review_id"]
    assert post(client, route, missing).status_code == 422


def test_history_pagination_and_latest_revision_survive_clock_order_changes(signed):
    client, service, _, _ = signed
    doc, _, ref, route = setup(client)
    with service.db.session() as session:
        for i in range(1, 56):
            session.add(DossierEntry(dossier_id=doc["id"], request_key=str(uuid4()), kind="source_review", url=ref["url"],
                body=f"Review number {i}", created_at=utcnow() - timedelta(minutes=i),
                data_json={"reference_id": ref["id"], "decision": "exclude", "revision": i, "expected_review_id": None}))
        session.commit()
    first, second = client.get(route).json(), client.get(route + "?offset=50").json()
    assert first["total"] == second["total"] == 55
    assert [x["data"]["revision"] for x in first["items"]] == list(range(55, 5, -1))
    assert [x["data"]["revision"] for x in second["items"]] == [5, 4, 3, 2, 1]
    assert first["current"]["id"] == second["current"]["id"] == first["items"][0]["id"]
    assert all(x["author"] == "Former member" for x in first["items"])
    assert client.get(route + "?offset=55").json()["items"] == []


def test_source_review_access_roles_drafts_csrf_products_and_tenants(signed):
    client, service, identity, _ = signed
    private, hidden_path, _, hidden = setup(client)
    shared, path, ref, route = setup(client)
    active(client, shared)
    assert post(client, route, request()).status_code == 201
    assert client.post(route, json=request()).status_code == 403
    assert client.get(route.replace("pharma", "loyer")).status_code == 404
    assert post(client, route.replace("pharma", "loyer"), request()).status_code == 404
    assert client.get(hidden_path + "/sources/" + ref["id"] + "/reviews").status_code == 404
    note = post(client, path + "/entries", {"request_key": str(uuid4()), "kind": "note", "body": "Not a source reference"}).json()
    assert post(client, path + "/sources/" + note["id"] + "/reviews", request()).status_code == 404
    reader = _register(client, "source-review-reader@example.ch").json()
    assert client.get(route).status_code == 404 and post(client, route, request()).status_code == 404
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=reader["user"]["id"], organization_id=identity["organization"]["id"], role="viewer"))
        session.commit()
    assert post(client, "/api/auth/session/organization", {"organization_id": identity["organization"]["id"]}).status_code == 200
    assert client.get(route).json()["total"] == 1 and client.get(hidden).status_code == 404
    assert post(client, route, request()).status_code == 403
    client.cookies.clear()
    assert client.get(route).status_code == 401


@pytest.mark.parametrize("change", ["role", "session"])
def test_review_checks_current_write_authorization_after_middleware(signed, monkeypatch, change):
    client, service, identity, _ = signed
    _, _, _, route = setup(client)
    original = product_source_reviews.principal
    def changed(session, actor, now, *, write=False):
        if write:
            with service.db.session() as other:
                if change == "role":
                    other.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"])).role = "viewer"
                else:
                    other.scalar(select(UserSession).where(UserSession.user_id == identity["user"]["id"])).revoked_at = utcnow()
                other.commit()
        return original(session, actor, now, write=write)
    monkeypatch.setattr(product_source_reviews, "principal", changed)
    assert post(client, route, request()).status_code in (401, 403)
    with service.db.session() as session:
        assert session.scalar(select(DossierEntry).where(DossierEntry.kind == "source_review")) is None


def test_exclusion_filters_references_page_extracts_events_and_restores_without_stopping_watch(signed, monkeypatch):
    client, service, identity, model = signed
    doc, path, ref, route = setup(client)
    active(client, doc)
    watch = post(client, path + "/sources/" + ref["id"] + "/monitor", {})
    assert watch.status_code == 200, watch.text
    calls_before = len(service.fetcher.calls)
    post(client, path + "/entries", {"request_key": str(uuid4()), "kind": "note", "body": "Keep unrelated source text", "url": LAW_URL + "?other=1"})
    monkeypatch.setattr(product_research.topic_matching, "list_matches", lambda *a, **k: [{"id": "saved-event", "is_current": True,
        "matched_at": utcnow().isoformat(), "evidence": {"source_url": LAW_URL, "work_title": "Saved official event"}}])
    def sources():
        with service.db.session() as session:
            parent, _ = dossier(session, "pharma", doc["id"], identity["user"]["id"])
            return product_research.research_sources(session, parent, "What changed?", identity["organization"]["id"])
    before = sources()
    assert {x["kind"] for x in before} >= {"team_contribution", "saved_page_extract", "official_event_metadata"}
    excluded = post(client, route, request()).json()
    after = sources()
    assert after and all(x["url"] != LAW_URL for x in after)
    assert all(x["key"] != excluded["id"] for x in after)
    restored = post(client, route, request(expected_review_id=excluded["id"], decision="unreviewed")).json()
    assert restored["data"]["revision"] == 2
    assert {x["kind"] for x in sources()} >= {"team_contribution", "saved_page_extract", "official_event_metadata"}
    assert len(service.fetcher.calls) == calls_before and not model.calls
    assert client.get(path).json()["documents"][0]["active"]


def test_new_research_respects_exclusion_and_retains_previous_accepted_snapshot(signed):
    client, _, _, model = signed
    _, path, ref, route = setup(client)
    thread, _ = question(client, path)
    question_route = path + "/discussion/" + thread["id"]
    model.responses = [json.dumps({"findings": [{"claim": "A recorded change needs review.", "citations": [{"source_id": "S1", "quote": "an observed change requiring professional review"}]}], "unknowns": ["Verify the original"], "search_queries": ["official changes"]})]
    research = post(client, question_route + "/research", {"request_key": str(uuid4()), "expected_revision": 1}).json()
    assert research["data"]["sources"][0]["key"] == ref["id"]
    assert post(client, question_route + "/accept", {"expected_revision": 2, "entry_id": research["id"]}).status_code == 200
    assert not client.get(question_route).json()["answer_needs_review"]
    review = post(client, route, request()).json()
    detail = client.get(question_route).json()
    assert detail["answer_needs_review"] and detail["accepted"]["data"] == research["data"]
    model.responses = [json.dumps({"findings": [], "unknowns": ["Need other evidence"], "search_queries": ["other official sources"]})]
    result = post(client, question_route + "/research", {"request_key": str(uuid4()), "expected_revision": 3})
    assert result.status_code == 200, result.text
    assert all(x["url"] != ref["url"] for x in json.loads(model.calls[-1][1])["sources"])
    assert result.json()["data"]["source_review_ids"] == {ref["url"]: review["id"]}
    assert client.get(question_route).json()["accepted"]["data"] == research["data"]


def test_review_during_inference_rejects_stale_note_even_when_selected_text_is_unchanged(signed):
    client, service, _, model = signed
    doc, path, ref, _ = setup(client)
    thread, _ = question(client, path)
    async def changing_model(*args, **kwargs):
        with service.db.session() as session:
            session.add(DossierEntry(dossier_id=doc["id"], request_key=str(uuid4()), kind="source_review", url=ref["url"],
                body="Explicitly include this source", data_json={"reference_id": ref["id"], "revision": 1, "decision": "include", "expected_review_id": None}))
            session.commit()
        return json.dumps({"findings": [], "unknowns": ["Check evidence"], "search_queries": ["official evidence"]})
    model.complete = changing_model
    question_route = path + "/discussion/" + thread["id"]
    response = post(client, question_route + "/research", {"request_key": str(uuid4()), "expected_revision": 1})
    assert response.status_code == 409, response.text
    assert client.get(question_route).json()["reply_count"] == 0


def test_loyer_review_is_independent_from_pharma_at_the_same_url(signed):
    client, _, _, _ = signed
    _, initial = create(client)
    legal = post(client, ROOT.replace("pharma", "loyer"), {**initial, "creation_key": str(uuid4())}).json()
    _, pharma_path, _, pharma_route = setup(client)
    legal_path = ROOT.replace("pharma", "loyer") + "/" + legal["id"]
    source = reference(client, legal_path)
    legal_route = legal_path + "/sources/" + source["id"] + "/reviews"
    review = post(client, legal_route, request(decision="include"))
    assert review.status_code == 201, review.text
    assert client.get(legal_path).json()["entries"][1]["source_review"]["id"] == review.json()["id"]
    assert client.get(pharma_route).json()["total"] == 0
    assert all(e.get("source_review") is None for e in client.get(pharma_path).json()["entries"])
