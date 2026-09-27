"""The saved source library remains complete as mixed topic activity grows."""
from datetime import timedelta
from uuid import uuid4

import pytest
from test_auth import _register
from test_product_dossiers import ROOT, active, create, post
from test_product_dossiers import signed as signed
from test_product_source_reviews import reference, request

from helvetic_lens.db import utcnow
from helvetic_lens.models import OrganizationMembership
from helvetic_lens.product_models import DossierEntry


def seed(session, identifier, *, title="Saved source", body="", url="https://example.ch/source", data=None, created_at=None, kind="reference"):
    entry = DossierEntry(dossier_id=identifier, request_key=str(uuid4()), kind=kind,
        title=title, body=body, url=url, data_json=data or {}, created_at=created_at or utcnow())
    session.add(entry)
    return entry


def test_all_reference_pages_are_complete_despite_newer_mixed_activity(signed):
    client, service, _, model = signed
    doc, _ = create(client)
    path = ROOT + "/" + doc["id"]
    with service.db.session() as session:
        stamp = utcnow() - timedelta(days=2)
        for i in range(125):
            seed(session, doc["id"], title=f"Archive reference {i}", created_at=stamp, url=f"https://example.ch/source/{i}")
        for i in range(120):
            seed(session, doc["id"], kind="note", body=f"Newer discussion activity {i}")
        session.commit()
    assert all(e["kind"] == "note" for e in client.get(path).json()["entries"])
    seen = []
    for offset in [0, 30, 60, 90, 120]:
        page = client.get(path + "/references", params={"offset": offset})
        assert page.status_code == 200, page.text
        page = page.json()
        assert page["total"] == page["dossier_total"] == page["counts"]["all"] == page["counts"]["unreviewed"] == 125
        assert page["page_size"] == 30 and page["offset"] == offset
        assert len(page["items"]) == (5 if offset == 120 else 30)
        seen.extend(e["id"] for e in page["items"])
    assert seen == sorted(seen) and len(set(seen)) == 125
    assert client.get(path + "/references?offset=125").json()["items"] == []
    assert not model.calls and not service.fetcher.calls


def test_literal_all_words_match_across_reference_and_imported_catalogue_fields(signed):
    client, service, _, _ = signed
    doc, _ = create(client)
    path = ROOT + "/" + doc["id"] + "/references"
    with service.db.session() as session:
        literal = seed(session, doc["id"], title='Marker 50% A_B "quoted"', body="Pharmacovigilance safety signal", url="https://example.ch/report")
        seed(session, doc["id"], title="Marker 500 AXB quoted", body="Safety signal")
        imported = seed(session, doc["id"], title="Short display title", data={"discovery": {"query": "renal safety cohort", "provider": "europepmc",
            "record": {"id": "MED:321", "title": "Full catalogue title that remains searchable", "provider": "Europe PMC"}}})
        session.flush()
        literal_id, imported_id = literal.id, imported.id
        session.commit()
    for query in ["50% A_B", '"quoted" pharmacovigilance', "MARKER safety report", "  50%   50%  "]:
        response = client.get(path, params={"q": query})
        assert response.status_code == 200, response.text
        assert [e["id"] for e in response.json()["items"]] == [literal_id]
        assert response.json()["query"] == query.strip()
    for query in ["renal catalogue", "europepmc MED:321", "Europe PMC renal"]:
        assert [e["id"] for e in client.get(path, params={"q": query}).json()["items"]] == [imported_id]
    assert client.get(path, params={"q": "no match"}).json()["total"] == 0
    assert client.get(path, params={"q": "  "}).json()["total"] == 3


def test_current_review_filters_counts_and_duplicates_ignore_old_decisions(signed):
    client, _, _, _ = signed
    doc, _ = create(client)
    path = ROOT + "/" + doc["id"]
    duplicate_a, duplicate_b = reference(client, path), reference(client, path)
    included = reference(client, path, url="https://example.ch/included")
    pending = reference(client, path, url="https://example.ch/pending")
    review_route = path + "/sources/" + duplicate_a["id"] + "/reviews"
    first = post(client, review_route, request(decision="include")).json()
    excluded = post(client, review_route, request(expected_review_id=first["id"])).json()
    post(client, path + "/sources/" + included["id"] + "/reviews", request(decision="include"))
    all_sources = client.get(path + "/references").json()
    assert all_sources["counts"] == {"all": 4, "include": 1, "exclude": 2, "unreviewed": 1}
    for decision, expected in [("include", {included["id"]}), ("exclude", {duplicate_a["id"], duplicate_b["id"]}), ("unreviewed", {pending["id"]})]:
        page = client.get(path + "/references", params={"decision": decision}).json()
        assert page["total"] == len(expected) and {e["id"] for e in page["items"]} == expected
        assert page["counts"] == all_sources["counts"]
        if decision == "exclude":
            assert all(e["source_review"]["id"] == excluded["id"] for e in page["items"])
    narrowed = client.get(path + "/references", params={"q": "included", "decision": "exclude"}).json()
    assert narrowed["total"] == 0 and narrowed["dossier_total"] == 4
    assert narrowed["counts"] == {"all": 1, "include": 1, "exclude": 0, "unreviewed": 0}
    post(client, review_route, request(expected_review_id=excluded["id"], decision="unreviewed"))
    reset = client.get(path + "/references", params={"decision": "unreviewed"}).json()
    assert reset["total"] == 3 and reset["counts"]["exclude"] == 0


def test_library_bounds_drafts_tenants_products_and_read_only_access(signed):
    client, service, identity, _ = signed
    private, _ = create(client)
    shared, _ = create(client)
    hidden = ROOT + "/" + private["id"]
    path = ROOT + "/" + shared["id"]
    reference(client, hidden)
    ref = reference(client, path)
    active(client, shared)
    route = path + "/references"
    for invalid in ({"q": "x" * 301}, {"q": " ".join("word" + str(i) for i in range(13))}, {"offset": -1},
                    {"offset": 2147483648}, {"decision": "approved"}):
        assert client.get(route, params=invalid).status_code == 422
    assert client.get(route, params={"q": "word " * 13}).status_code == 200
    assert client.get(route.replace("pharma", "loyer")).status_code == 404
    reader = _register(client, "reference-reader@example.ch").json()
    assert client.get(route).status_code == 404
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=reader["user"]["id"], organization_id=identity["organization"]["id"], role="viewer"))
        session.commit()
    assert post(client, "/api/auth/session/organization", {"organization_id": identity["organization"]["id"]}).status_code == 200
    read = client.get(route)
    assert read.status_code == 200 and read.json()["items"][0]["id"] == ref["id"]
    assert "no-store" in read.headers["cache-control"]
    assert client.get(hidden + "/references").status_code == 404
    client.cookies.clear()
    assert client.get(route).status_code == 401


@pytest.mark.parametrize("product", ["pharma", "loyer"])
def test_empty_source_library_and_isolated_product_lists(signed, product):
    client, _, _, _ = signed
    _, initial = create(client)
    doc = post(client, ROOT.replace("pharma", product), {**initial, "creation_key": str(uuid4())}).json()
    path = ROOT.replace("pharma", product) + "/" + doc["id"]
    empty = client.get(path + "/references").json()
    assert empty["items"] == [] and empty["counts"] == {"all": 0, "include": 0, "exclude": 0, "unreviewed": 0}
    ref = reference(client, path)
    read = client.get(path + "/references").json()
    assert read["total"] == read["dossier_total"] == 1 and read["items"][0] == ref
