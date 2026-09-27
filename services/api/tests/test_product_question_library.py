"""Teams can retrieve old questions without broadening private read access."""
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_auth import _register
from test_product_dossiers import ROOT, active, create, post
from test_product_dossiers import signed as signed
from test_product_research import contribution, question

from helvetic_lens.db import utcnow
from helvetic_lens.models import OrganizationMembership
from helvetic_lens.product_models import DossierEntry, ResearchThread


def seed(session, dossier_id, title, body="", updated_at=None):
    row = ResearchThread(dossier_id=dossier_id, creation_key=str(uuid4()), creation_fingerprint="0" * 64,
        title=title, body=body, updated_at=updated_at or utcnow())
    session.add(row)
    session.flush()
    return row.id


def test_old_questions_and_all_tied_pages_remain_retrievable_without_side_effects(signed):
    client, service, _, model = signed
    doc, _ = create(client)
    path = ROOT + "/" + doc["id"] + "/discussion"
    stamp = utcnow() - timedelta(days=2)
    with service.db.session() as session:
        old = [seed(session, doc["id"], f"Archived renal question {i}", updated_at=stamp) for i in range(65)]
        for i in range(70):
            seed(session, doc["id"], f"New discussion {i}")
        session.commit()
        before = session.scalar(select(func.count()).select_from(DossierEntry))
    assert set(old).isdisjoint(e["id"] for e in client.get(path).json()["items"])
    seen = []
    for offset in [0, 30, 60]:
        response = client.get(path, params={"q": "archived renal", "offset": offset})
        assert response.status_code == 200, response.text
        page = response.json()
        assert page["total"] == page["counts"]["all"] == page["counts"]["open"] == 65
        assert page["dossier_total"] == 135 and page["page_size"] == 30 and page["offset"] == offset
        assert len(page["items"]) == (5 if offset == 60 else 30)
        seen.extend(e["id"] for e in page["items"])
    assert seen == sorted(old) and len(set(seen)) == 65
    assert client.get(path, params={"q": "renal", "offset": 65}).json()["items"] == []
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(DossierEntry)) == before
    assert not model.calls and not service.fetcher.calls


def test_literal_cross_field_terms_title_ranking_and_reply_scope(signed):
    client, service, _, _ = signed
    doc, _ = create(client)
    path = ROOT + "/" + doc["id"]
    with service.db.session() as session:
        title = seed(session, doc["id"], 'Renal 50% A_B "quoted"', "safety signal", utcnow() - timedelta(days=2))
        body = seed(session, doc["id"], "Another question", 'renal safety 50% A_B "quoted"')
        seed(session, doc["id"], "Renal 500 AXB quoted", "safety")
        session.commit()
    for query in ["50% A_B", '"quoted" SAFETY', " renal 50% renal "]:
        page = client.get(path + "/discussion", params={"q": query}).json()
        assert [e["id"] for e in page["items"]] == [title, body]
        assert page["query"] == query.strip()
    thread, _ = question(client, path, "A separate clinical question")
    contribution(client, path + "/discussion/" + thread["id"], "Reply-only uniquephrase must not match question search.")
    page = client.get(path + "/discussion", params={"q": "uniquephrase"}).json()
    assert page["total"] == 0 and page["dossier_total"] == 4
    assert client.get(path + "/discussion", params={"q": "  "}).json()["total"] == 4


@pytest.mark.parametrize("product", ["pharma", "loyer"])
def test_matching_status_facets_and_reopening_in_both_products(signed, product):
    client, _, _, _ = signed
    _, initial = create(client)
    doc = post(client, ROOT.replace("pharma", product), {**initial, "creation_key": str(uuid4())}).json()
    path = ROOT.replace("pharma", product) + "/" + doc["id"]
    empty = client.get(path + "/discussion").json()
    assert empty["counts"] == {"all": 0, "open": 0, "answered": 0}
    answered, _ = question(client, path, "Renal evidence question")
    question(client, path, "Renal safety question")
    question(client, path, "Unrelated question")
    route = path + "/discussion/" + answered["id"]
    reply, _ = contribution(client, route)
    assert post(client, route + "/accept", {"expected_revision": 2, "entry_id": reply["id"]}).status_code == 200
    for status, total in [("all", 2), ("open", 1), ("answered", 1)]:
        page = client.get(path + "/discussion", params={"q": "renal", "status": status}).json()
        assert page["status"] == status and page["total"] == total and page["dossier_total"] == 3
        assert page["counts"] == {"all": 2, "open": 1, "answered": 1}
        if status == "answered":
            assert [e["id"] for e in page["items"]] == [answered["id"]]
    assert post(client, route + "/accept", {"expected_revision": 3, "entry_id": None}).status_code == 200
    page = client.get(path + "/discussion", params={"q": "renal", "status": "answered"}).json()
    assert page["items"] == [] and page["counts"] == {"all": 2, "open": 2, "answered": 0}


def test_question_search_bounds_and_current_private_access(signed):
    client, service, identity, _ = signed
    private, _ = create(client)
    shared, _ = create(client)
    hidden, path = (ROOT + "/" + d["id"] for d in [private, shared])
    question(client, hidden)
    thread, _ = question(client, path)
    active(client, shared)
    route = path + "/discussion"
    for invalid in ({"q": "x" * 301}, {"q": " ".join("word" + str(i) for i in range(13))},
                    {"offset": -1}, {"offset": 100001}, {"status": "approved"}):
        assert client.get(route, params=invalid).status_code == 422
    assert client.get(route, params={"q": "word " * 13}).status_code == 200
    assert client.get(route.replace("pharma", "loyer")).status_code == 404
    reader = _register(client, "question-reader@example.ch").json()
    assert client.get(route).status_code == 404
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=reader["user"]["id"], organization_id=identity["organization"]["id"], role="viewer"))
        session.commit()
    assert post(client, "/api/auth/session/organization", {"organization_id": identity["organization"]["id"]}).status_code == 200
    read = client.get(route, params={"q": "evidence"})
    assert read.status_code == 200 and read.json()["items"][0]["id"] == thread["id"]
    assert "no-store" in read.headers["cache-control"]
    assert client.get(hidden + "/discussion").status_code == 404
    assert post(client, route, {"creation_key": str(uuid4()), "title": "Viewer cannot create"}).status_code == 403
    with service.db.session(include_all_organizations=True) as session:
        member = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == reader["user"]["id"],
            OrganizationMembership.organization_id == identity["organization"]["id"]))
        session.delete(member)
        session.commit()
    assert client.get(route).status_code in (401, 403)
    client.cookies.clear()
    assert client.get(route).status_code == 401
