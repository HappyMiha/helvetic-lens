"""Shared search recipes retain intent without fabricating collection or evidence."""
from uuid import uuid4

from test_auth import _register
from test_product_dossiers import ROOT, active, create, post
from test_product_dossiers import signed as signed
from test_product_research import contribution, question

from helvetic_lens import product_research
from helvetic_lens.models import OrganizationMembership
from helvetic_lens.product_models import DossierEntry


def recipe(**values):
    return {"request_key": str(uuid4()), "query": "medicine safety", "provider": "workspace",
            "match_mode": "phrase", "purpose": "Compare source evidence for the next team review.", **values}


def test_persisted_searches_replay_export_and_brief_never_fetch_or_claim_results(signed, monkeypatch):
    client, service, _, model = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    async def unexpected_search(*args, **kwargs):
        raise AssertionError("Saving or listing a recipe must not run a source query")
    monkeypatch.setattr(product_research, "public_search", unexpected_search)
    values = recipe(query='<script>alert("query")</script>', purpose="Check <b>original</b> sources & uncertainty")
    saved = post(client, route + "/searches", values)
    assert saved.status_code == 201, saved.text
    item = saved.json()
    assert item["author"] == "Ada Example" and item["created_at"] and item["kind"] == "saved_search"
    assert item["data"] == {"query": values["query"], "provider": "workspace", "match_mode": "phrase"}
    assert post(client, route + "/searches", values).json()["id"] == item["id"]
    for changed in ({"query": "other query"}, {"purpose": "Other purpose"}, {"match_mode": "all"}):
        assert post(client, route + "/searches", {**values, **changed}).status_code == 409
    for provider in ("fedlex", "europepmc"):
        assert post(client, route + "/searches", recipe(provider=provider, match_mode=None)).status_code == 201
    listing = client.get(route + "/searches").json()
    assert listing["total"] == 3 and len(listing["items"]) == 3
    assert next(e for e in client.get(route + "/export").json()["entries"] if e["id"] == item["id"]) == item
    brief = client.get(route + "/brief")
    assert brief.status_code == 200 and "Saved searches" in brief.text
    assert '<script>' not in brief.text and '&lt;script&gt;' in brief.text and '&lt;b&gt;original&lt;/b&gt;' in brief.text
    assert "not scheduled monitors or records of retrieved results" in brief.text
    assert not service.fetcher.calls and not model.calls


def test_invalid_recipes_execution_claims_and_entry_key_collisions_are_rejected(signed):
    client, _, _, _ = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    many = " ".join("word" + str(i) for i in range(13))
    for invalid in ({"query": " a "}, {"query": "x" * 301}, {"provider": "arbitrary-web"},
                    {"provider": "fedlex", "match_mode": "phrase"}, {"match_mode": "semantic"},
                    {"query": many, "match_mode": "all"}, {"purpose": "x" * 2001},
                    {"checked_at": "2026-09-27T00:00:00Z"}, {"results": []}, {"scheduled": True}):
        assert post(client, route + "/searches", recipe(**invalid)).status_code == 422
    assert post(client, route + "/searches", recipe(query=many)).status_code == 201
    default = recipe(match_mode=None)
    assert post(client, route + "/searches", default).json()["data"]["match_mode"] == "all"
    prior = {"request_key": str(uuid4()), "kind": "note", "body": "An existing team note"}
    assert post(client, route + "/entries", prior).status_code == 201
    assert post(client, route + "/searches", recipe(request_key=prior["request_key"])).status_code == 409


def test_saved_search_pagination_is_complete_stable_and_dossier_scoped(signed):
    client, service, _, _ = signed
    doc, _ = create(client)
    other, _ = create(client)
    route = ROOT + "/" + doc["id"]
    with service.db.session() as session:
        for i in range(55):
            session.add(DossierEntry(dossier_id=doc["id"], request_key=str(uuid4()), kind="saved_search",
                title=f"Query {i}", body="Review evidence", data_json={"query": f"Query {i}", "provider": "fedlex", "match_mode": None}))
        session.add(DossierEntry(dossier_id=doc["id"], request_key=str(uuid4()), kind="note", body="Not a search"))
        session.commit()
    post(client, ROOT + "/" + other["id"] + "/searches", recipe())
    first, second = client.get(route + "/searches").json(), client.get(route + "/searches?offset=50").json()
    assert first["total"] == second["total"] == 55 and len(first["items"]) == 50 and len(second["items"]) == 5
    assert len({e["id"] for e in first["items"] + second["items"]}) == 55
    assert first == client.get(route + "/searches").json()
    assert client.get(route + "/searches?offset=55").json() == {"items": [], "total": 55}


def test_saved_search_roles_csrf_private_drafts_tenants_and_products(signed):
    client, service, identity, _ = signed
    private, _ = create(client)
    shared, _ = create(client)
    active(client, shared)
    route, hidden = ROOT + "/" + shared["id"] + "/searches", ROOT + "/" + private["id"] + "/searches"
    assert post(client, route, recipe()).status_code == 201
    assert post(client, hidden, recipe()).status_code == 201
    assert client.post(route, json=recipe()).status_code == 403
    assert client.get(route.replace("pharma", "loyer")).status_code == 404
    assert post(client, route.replace("pharma", "loyer"), recipe()).status_code == 404
    reader = _register(client, "search-reader@example.ch").json()
    assert client.get(route).status_code == 404
    assert post(client, route, recipe()).status_code == 404
    with service.db.session(include_all_organizations=True) as session:
        membership = OrganizationMembership(user_id=reader["user"]["id"], organization_id=identity["organization"]["id"], role="viewer")
        session.add(membership)
        session.commit()
    assert post(client, "/api/auth/session/organization", {"organization_id": identity["organization"]["id"]}).status_code == 200
    assert client.get(route).json()["total"] == 1
    assert post(client, route, recipe()).status_code == 403
    assert client.get(hidden).status_code == 404
    client.cookies.clear()
    assert client.get(route).status_code == 401


def test_search_recipe_is_not_answer_evidence_or_a_review_signal(signed):
    client, service, _, _ = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    thread, _ = question(client, route)
    path = route + "/discussion/" + thread["id"]
    reply, _ = contribution(client, path)
    assert post(client, path + "/accept", {"expected_revision": 2, "entry_id": reply["id"]}).status_code == 200
    saved = post(client, route + "/searches", recipe()).json()
    detail = client.get(path).json()
    assert not detail["answer_needs_review"] and detail["accepted_entry_id"] == reply["id"]
    with service.db.session() as session:
        from helvetic_lens.product_api import dossier
        from helvetic_lens.product_models import ResearchThread
        row = session.get(ResearchThread, thread["id"])
        parent, _ = dossier(session, "pharma", doc["id"], row.created_by_user_id)
        assert all(source["key"] != saved["id"] for source in product_research.research_sources(session, parent, row.title, parent.organization_id))
