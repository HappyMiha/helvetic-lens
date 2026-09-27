"""Product readers reuse native bounded history while enforcing the dossier link."""
import hashlib
from datetime import timedelta
from uuid import uuid4

import pytest
from conftest import LAW_URL, policy
from sqlalchemy import select
from test_auth import _register
from test_law_history_metadata import recording
from test_product_dossiers import ROOT, active, create, post
from test_product_dossiers import signed as signed
from test_product_source_health import connect

from helvetic_lens import evidence_pages
from helvetic_lens.db import utcnow
from helvetic_lens.models import DocumentWatch, Law, Organization, OrganizationMembership, Version
from helvetic_lens.product_models import DossierEntry


def setup(client, product="pharma"):
    _, initial = create(client)
    doc = post(client, ROOT.replace("pharma", product), {**initial, "creation_key": str(uuid4())}).json()
    active(client, doc)
    parent = ROOT.replace("pharma", product) + "/" + doc["id"]
    law_id = connect(client, parent)
    version_id = client.get("/api/laws/" + law_id).json()["current_version"]["id"]
    return doc, parent, law_id, version_id, parent + "/documents/" + law_id + "/versions"


def saved_version(session, law_id, index, **extra):
    text = f"Stored evidence {index}."
    version = Version(law_id=law_id, title=f"Saved source {index}", text=text, passages=[],
        content_hash=hashlib.sha256(text.encode()).hexdigest(), extractor="native-html-v1", content_type="text/html",
        artifact_key="unavailable", filename="snapshot.html", source_url=LAW_URL, origin="live", synthetic=False,
        created_at=utcnow() - timedelta(days=2), **extra)
    session.add(version)
    session.flush()
    return version.id


@pytest.mark.parametrize("product", ["pharma", "loyer"])
def test_complete_history_uses_native_cursors_without_bodies_or_side_effects(signed, product):
    client, service, _, model = signed
    _, parent, law_id, original, route = setup(client, product)
    with service.db.session() as session:
        for i in range(46):
            saved_version(session, law_id, i)
        session.commit()
        expected = list(session.scalars(select(Version.id).where(Version.law_id == law_id)
            .order_by(Version.created_at.desc(), Version.id.desc())))
    before_fetches = len(service.fetcher.calls)
    before_entries = client.get(parent).json()["entry_count"]
    with recording(service) as (_, loaded):
        first = client.get(route)
        assert first.status_code == 200 and "no-store" in first.headers["cache-control"]
        data = first.json()
        assert data["total"] == 47 and len(data["items"]) == 20 and data["document"]["id"] == law_id
        ids = [row["id"] for row in data["items"]]
        cursor = data["next_cursor"]
        while cursor:
            page = client.get(route, params={"cursor": cursor}).json()
            ids.extend(row["id"] for row in page["items"])
            cursor = page["next_cursor"]
        assert loaded == []
    assert ids == expected and original in ids
    for item in data["items"]:
        assert not {"text", "passages", "artifact_key", "artifact_url", "evidence_url", "owner_organization_id"} & item.keys()
    with service.db.session() as session:
        new_id = saved_version(session, law_id, 999)
        session.get(Version, new_id).created_at = utcnow()
        session.commit()
    again = client.get(route, params={"cursor": data["first_cursor"]}).json()
    assert [row["id"] for row in again["items"]] == ids[:20] and again["total"] == 47
    assert client.get(route).json()["total"] == 48
    assert client.get(parent).json()["entry_count"] == before_entries
    assert len(service.fetcher.calls) == before_fetches and not model.calls


def test_exact_passage_and_unicode_text_pages_preserve_provenance_without_orm_loads(signed):
    client, service, _, model = signed
    _, _, _, version_id, route = setup(client)
    url = route + "/" + version_id
    with service.db.session() as session:
        version = session.get(Version, version_id)
        version.passages = [{"id": f"p{i}", "text": f"Saved passage {i} — Ä👁", "page": i // 10 + 1} for i in range(111)]
        version.synthetic = True
        version.origin = "import"
        version.declared_date = "2026-09-01"
        version.date_provenance = "user"
        version.selection_provenance = {"scope": "Articles 1–3", "official_version_date": "2026-09-01",
            "articles": [{"number": "1", "heading": "Saved selected article", "anchor": "art_1"}],
            "artifact_url": "/api/private-artifact", "official_url": "https://example.ch/act"}
        session.commit()
    before = len(service.fetcher.calls)
    with recording(service) as (_, loaded):
        first = client.get(url).json()
        assert len(first["passages"]) == 50 and first["pagination"]["total"] == 111
        assert first["synthetic"] and first["origin"] == "import"
        assert first["declared_date"] == "2026-09-01" and first["date_provenance"] == "user"
        assert first["selection_provenance"]["scope"] == "Articles 1–3"
        assert "artifact_url" not in first and "artifact_url" not in first["selection_provenance"]
        second = client.get(url, params={"offset": 50, "expected_revision": first["evidence_revision"]}).json()
        tail = client.get(url, params={"offset": 100, "expected_revision": first["evidence_revision"]}).json()
        assert [part["id"] for part in first["passages"] + second["passages"] + tail["passages"]] == [f"p{i}" for i in range(111)]
        assert tail["pagination"]["next_offset"] is None and not loaded
    original = "Art. 1 — ÄÖÜ français italiano 👀\n" * 1500
    with service.db.session() as session:
        version = session.get(Version, version_id)
        version.passages = []
        version.text = original
        session.commit()
    offset, parts, revision = 0, [], None
    while True:
        params = {"offset": offset, **({"expected_revision": revision} if revision else {})}
        read = client.get(url, params=params)
        assert read.status_code == 200, read.text
        data = read.json()
        assert data["pagination"]["mode"] == "text" and len(data["plain_text"]) <= 16000
        revision = data["evidence_revision"]
        parts.append(data["plain_text"])
        offset = data["pagination"]["next_offset"]
        if offset is None:
            break
    assert "".join(parts) == original
    assert len(service.fetcher.calls) == before and not model.calls


def test_changed_revision_is_not_combined_with_earlier_pages(signed, monkeypatch):
    client, service, _, _ = signed
    _, _, _, version_id, route = setup(client)
    url = route + "/" + version_id
    before = client.get(url).json()
    with service.db.session() as session:
        session.get(Version, version_id).text = "A corrected saved text."
        session.commit()
    assert client.get(url, params={"expected_revision": before["evidence_revision"]}).status_code == 409
    current = client.get(url).json()
    assert current["evidence_revision"] != before["evidence_revision"]
    native = evidence_pages.detail
    def changed(*args, **kwargs):
        result = native(*args, **kwargs)
        with service.db.session() as session:
            session.get(Version, version_id).text = "Corrected again while loading."
            session.commit()
        return result
    monkeypatch.setattr(evidence_pages, "detail", changed)
    response = client.get(url)
    assert response.status_code == 409 and "passages" not in response.json()


def test_parent_document_version_product_and_viewer_boundaries(signed):
    client, service, identity, _ = signed
    _, parent, law_id, version_id, route = setup(client)
    other, _ = create(client)
    active(client, other)
    other_parent = ROOT + "/" + other["id"]
    other_url = LAW_URL + "?other=1"
    service.fetcher.values[other_url] = policy("Different saved source body.")
    other_law = connect(client, other_parent, other_url)
    with service.db.session() as session:
        other_version = session.get(Law, other_law).current_version_id
    wrong_parent = other_parent + "/documents/" + law_id + "/versions"
    for wrong in (wrong_parent, route.replace("pharma", "loyer"), route + "/" + other_version, route + "/" + str(uuid4())):
        assert client.get(wrong).status_code == 404
    cursor = client.get(route).json()["first_cursor"]
    assert client.get(other_parent + "/documents/" + other_law + "/versions", params={"cursor": cursor}).status_code == 422
    private, _ = create(client)
    private_route = ROOT + "/" + private["id"] + "/documents/" + law_id + "/versions"
    with service.db.session() as session:
        session.add(DossierEntry(organization_id=identity["organization"]["id"], dossier_id=private["id"],
            request_key=str(uuid4()), kind="monitor", data_json={"law_id": law_id}, actor_user_id=identity["user"]["id"]))
        session.commit()
    assert client.get(private_route).status_code == client.get(private_route + "/" + version_id).status_code == 200
    viewer = _register(client, "page-history-reader@example.ch").json()
    assert client.get(route).status_code == 404
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=viewer["user"]["id"], organization_id=identity["organization"]["id"], role="viewer"))
        session.commit()
    assert post(client, "/api/auth/session/organization", {"organization_id": identity["organization"]["id"]}).status_code == 200
    assert client.get(route).status_code == client.get(route + "/" + version_id).status_code == 200
    assert client.get(private_route).status_code == client.get(private_route + "/" + version_id).status_code == 404
    assert post(client, route, {}).status_code == 403
    with service.db.session() as session:
        entry = session.scalar(select(DossierEntry).where(DossierEntry.dossier_id == parent.rsplit("/", 1)[-1], DossierEntry.kind == "monitor"))
        session.delete(entry)
        session.commit()
    assert client.get(route).status_code == client.get(route + "/" + version_id).status_code == 404
    client.cookies.clear()
    assert client.get(route).status_code == 401


def test_foreign_owned_version_bounds_and_unreadable_saved_text(signed):
    client, service, _, _ = signed
    _, _, law_id, version_id, route = setup(client)
    url = route + "/" + version_id
    for params in ({"offset": -1}, {"offset": 2147483648}, {"offset": 999999}, {"expected_revision": 0}):
        assert client.get(url, params=params).status_code == 422
    assert client.get(route, params={"cursor": "bad-cursor"}).status_code == 422
    with service.db.session() as session:
        version = session.get(Version, version_id)
        version.passages = [{"id": "good", "text": "Readable saved text"}, None, {"id": "invalid", "text": {"bad": True}}]
        session.commit()
    page = client.get(url).json()
    assert len(page["passages"]) == 1 and page["omitted_passages"] == 2 and page["pagination"]["total"] == 3
    with service.db.session() as session:
        version = session.get(Version, version_id)
        version.passages = []
        version.text = ""
        session.commit()
    empty = client.get(url).json()
    assert empty["plain_text"] == "" and empty["pagination"]["total"] == 0
    with service.db.session(include_all_organizations=True) as session:
        foreign = Organization(name="Private source owner", slug="private-source-owner")
        session.add(foreign)
        session.flush()
        session.get(Version, version_id).owner_organization_id = foreign.id
        session.commit()
    assert client.get(url).status_code == 404
    assert client.get(route).json()["items"] == []


def test_document_watch_and_source_ownership_are_required_on_every_read(signed):
    client, service, identity, _ = signed
    _, _, law_id, version_id, route = setup(client)
    with service.db.session(include_all_organizations=True) as session:
        foreign = Organization(name="Other source workspace", slug="other-source-workspace")
        session.add(foreign)
        session.flush()
        foreign_id = foreign.id
        session.get(Law, law_id).owner_organization_id = foreign_id
        session.commit()
    for url in (route, route + "/" + version_id):
        assert client.get(url).status_code == 404
    with service.db.session(include_all_organizations=True) as session:
        session.get(Law, law_id).owner_organization_id = None
        watch = session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law_id,
            DocumentWatch.organization_id == identity["organization"]["id"]))
        watch.organization_id = foreign_id
        session.commit()
    for url in (route, route + "/" + version_id):
        assert client.get(url).status_code == 404


def test_version_reassignment_while_reading_is_rejected(signed, monkeypatch):
    client, service, _, _ = signed
    _, _, _, version_id, route = setup(client)
    other, _ = create(client)
    active(client, other)
    other_url = LAW_URL + "?different=1"
    service.fetcher.values[other_url] = policy("Another document.")
    other_law = connect(client, ROOT + "/" + other["id"], other_url)
    native = evidence_pages.detail
    def reassigned(*args, **kwargs):
        result = native(*args, **kwargs)
        with service.db.session() as session:
            session.get(Version, version_id).law_id = other_law
            session.commit()
        return result
    monkeypatch.setattr(evidence_pages, "detail", reassigned)
    response = client.get(route + "/" + version_id)
    assert response.status_code == 409 and "passages" not in response.json()
