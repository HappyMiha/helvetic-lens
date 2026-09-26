"""A follow-up keeps its verified research origin without accepting an AI answer."""
import json
from uuid import uuid4

from test_auth import _register
from test_product_dossiers import ROOT, active, create, post
from test_product_dossiers import signed as signed
from test_product_operations import action, put
from test_product_research import contribution, question

from helvetic_lens.models import OrganizationMembership
from helvetic_lens.product_models import DossierAction
from helvetic_lens.product_operations import fingerprint


def research_note(client, model, route, thread):
    model.responses = [json.dumps({"findings": [], "unknowns": ["Verify <script>scope</script> with the original authority."],
                                   "search_queries": ["official scope"]})]
    response = post(client, route + "/discussion/" + thread["id"] + "/research", {
        "expected_revision": thread["revision"], "request_key": str(uuid4())})
    assert response.status_code == 200, response.text
    return response.json()


def test_gap_followup_captures_source_keeps_outcome_and_never_accepts_an_answer(signed):
    client, _, identity, model = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    thread, _ = question(client, route, "Which safety scope requires verification?")
    note = research_note(client, model, route, thread)
    origin = {"thread_id": thread["id"], "entry_id": note["id"], "gap_index": 0}
    saved, request = action(client, route, research_origin=origin, assignee_user_id=identity["user"]["id"])
    snapshot = saved["evidence"]["research"]
    assert snapshot["question"] == thread["title"] and snapshot["gap"] == note["data"]["unknowns"][0]
    assert snapshot["entry_id"] == note["id"] and snapshot["captured_at"]
    assert post(client, route + "/actions", request).json()["id"] == saved["id"]
    assert post(client, route + "/actions", {**request, "research_origin": {**origin, "gap_index": 1}}).status_code == 409
    update = {"expected_revision": 1, "title": "Verify the official safety scope", "status": "done", "outcome": "Reviewed the source. More evidence is needed."}
    result = put(client, route + "/actions/" + saved["id"], update)
    assert result.status_code == 200 and result.json()["evidence"]["research"] == snapshot
    assert client.get(route + "/discussion/" + thread["id"]).json()["accepted_entry_id"] is None
    listed = client.get(route + "/actions", params={"thread_id": thread["id"]}).json()
    assert listed["total"] == 1 and listed["items"][0]["outcome"] == update["outcome"]
    assert client.get(route + "/export").json()["actions"][0]["evidence"]["research"] == snapshot
    brief = client.get(route + "/brief")
    assert "Gap to establish" in brief.text and "&lt;script&gt;scope&lt;/script&gt;" in brief.text
    assert "<script>scope</script>" not in brief.text and "question=" + thread["id"] in brief.text
    assert "no-store" in brief.headers["cache-control"]
    assert put(client, route + "/actions/" + saved["id"], {**update, "expected_revision": 2, "research_origin": origin}).status_code == 422


def test_invalid_or_foreign_research_origins_are_not_accepted(signed):
    client, _, _, model = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    one, _ = question(client, route)
    two, _ = question(client, route, "A separate evidence question")
    note = research_note(client, model, route, one)
    reply, _ = contribution(client, route + "/discussion/" + two["id"])
    base = {"thread_id": one["id"], "entry_id": note["id"], "gap_index": 0}
    for origin, expected in [
        ({**base, "thread_id": two["id"]}, 404),
        ({**base, "entry_id": reply["id"], "thread_id": two["id"]}, 404),
        ({**base, "gap_index": 7}, 409),
        ({**base, "gap_index": -1}, 422),
        ({**base, "gap_index": False}, 422),
        ({"thread_id": one["id"], "entry_id": note["id"]}, 422),
        ({"thread_id": one["id"], "gap_index": 0}, 422),
        ({**base, "gap": "A browser-invented gap"}, 422),
    ]:
        result = post(client, route + "/actions", {"creation_key": str(uuid4()), "title": "Verify this source", "research_origin": origin})
        assert result.status_code == expected, result.text
    mixed = post(client, route + "/actions", {"creation_key": str(uuid4()), "title": "Mixed origin", "research_origin": base, "match_id": str(uuid4())})
    assert mixed.status_code == 422
    other, _ = create(client)
    other_route = ROOT + "/" + other["id"]
    assert post(client, other_route + "/actions", {"creation_key": str(uuid4()), "title": "Foreign question", "research_origin": base}).status_code == 404
    assert client.get(other_route + "/actions", params={"thread_id": one["id"]}).status_code == 404
    assert client.get(route + "/actions").json()["total"] == 0


def test_research_followups_obey_roles_draft_product_and_organization_privacy(signed):
    client, service, identity, _ = signed
    private, _ = create(client)
    shared, _ = create(client)
    active(client, shared)
    route = ROOT + "/" + shared["id"]
    thread, _ = question(client, route)
    origin = {"thread_id": thread["id"]}
    action(client, route, research_origin=origin)
    data = {"creation_key": str(uuid4()), "title": "Follow up this question", "research_origin": origin}
    assert client.post(route + "/actions", json=data).status_code == 403
    assert client.get(route.replace("pharma", "loyer") + "/actions", params={"thread_id": thread["id"]}).status_code == 404
    reader = _register(client, "research-reader@example.ch").json()
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=reader["user"]["id"], organization_id=identity["organization"]["id"], role="viewer"))
        session.commit()
    assert post(client, "/api/auth/session/organization", {"organization_id": identity["organization"]["id"]}).status_code == 200
    assert client.get(route + "/actions", params={"thread_id": thread["id"]}).json()["total"] == 1
    assert post(client, route + "/actions", data).status_code == 403
    assert client.get(ROOT + "/" + private["id"] + "/actions", params={"thread_id": thread["id"]}).status_code == 404
    client.cookies.clear()
    assert client.get(route + "/actions", params={"thread_id": thread["id"]}).status_code == 401
    assert _register(client, "another-researcher@example.ch").status_code == 201
    assert client.get(route + "/actions", params={"thread_id": thread["id"]}).status_code == 404
    assert post(client, route + "/actions", data).status_code == 404


def test_question_action_filter_counts_and_paginates_only_its_own_work(signed):
    client, service, _, _ = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    one, _ = question(client, route)
    two, _ = question(client, route, "Another question to follow up")
    with service.db.session() as session:
        for index in range(55):
            session.add(DossierAction(dossier_id=doc["id"], creation_key=str(uuid4()), creation_fingerprint="fixture",
                title=f"Research follow-up {index}", evidence_json={"research": {"thread_id": one["id"], "question": one["title"]}}))
        session.commit()
    action(client, route)
    action(client, route, research_origin={"thread_id": two["id"]})
    first = client.get(route + "/actions", params={"thread_id": one["id"]}).json()
    last = client.get(route + "/actions", params={"thread_id": one["id"], "offset": 50}).json()
    assert first["total"] == last["total"] == 55 and len(first["items"]) == 50 and len(last["items"]) == 5
    assert not {x["id"] for x in first["items"]} & {x["id"] for x in last["items"]}
    assert client.get(route + "/actions").json()["total"] == 57
    assert client.get(route + "/actions", params={"thread_id": two["id"]}).json()["total"] == 1


def test_action_retries_from_pre_research_clients_keep_their_original_fingerprint(signed):
    client, service, _, _ = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    key = str(uuid4())
    legacy = {"title": "Existing published client action", "detail": "", "priority": "normal", "assignee_user_id": None,
              "due_on": None, "source_url": "", "match_id": None, "evaluation_fingerprint": ""}
    with service.db.session() as session:
        saved = DossierAction(dossier_id=doc["id"], creation_key=key, creation_fingerprint=fingerprint(legacy), title=legacy["title"])
        session.add(saved)
        session.flush()
        identifier = saved.id
        session.commit()
    result = post(client, route + "/actions", {"creation_key": key, "title": legacy["title"]})
    assert result.status_code == 201 and result.json()["id"] == identifier
    again = post(client, route + "/actions", {"creation_key": key, "title": legacy["title"], "research_origin": None})
    assert again.json()["id"] == identifier and client.get(route + "/actions").json()["total"] == 1
