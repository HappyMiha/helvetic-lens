from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_auth import _register
from test_product_dossiers import ROOT, active, create, post
from test_product_dossiers import signed as signed

from helvetic_lens.db import utcnow
from helvetic_lens.models import OrganizationMembership
from helvetic_lens.product_models import ProductDossier, ProductPublication, PublicationRevision

PUBLIC = "/api/products/pharma/public-dossiers"


def draft(revision=0, **changes):
    return {"expected_revision": revision, "content": {"title": "Public research question",
        "summary": "A deliberately public summary of the research question.",
        "body": "This explicitly authored explanation is the only text intended for publication.",
        "author_label": "Research editors", "sources": [{"title": "Official legislation", "url": "https://www.fedlex.admin.ch/"}],
        **changes}}


def preview_and_publish(client, identifier, data=None):
    path = ROOT + "/" + identifier + "/publication"
    prepared = post(client, path + "/preview", data or draft())
    assert prepared.status_code == 200, prepared.text
    command = {**prepared.json(), "request_key": str(uuid4()), "confirm_public": True}
    result = post(client, path, command)
    assert result.status_code == 200, result.text
    return result.json()["publication"], command


def test_anonymous_reader_exposes_only_explicit_projection_and_withdraws(signed):
    client, service, identity, _ = signed
    doc, _ = create(client)
    path = ROOT + "/" + doc["id"]
    post(client, path + "/entries", {"request_key": str(uuid4()), "kind": "note", "body": "PRIVATE-MARKER"})
    publication, command = preview_and_publish(client, doc["id"])
    public_path = PUBLIC + "/" + publication["id"]
    assert post(client, path + "/publication", command).json()["publication"]["revision"] == 1
    assert client.get(PUBLIC).json()["total"] == 1
    saved_cookies = dict(client.cookies)
    client.cookies.clear()
    response = client.get(public_path)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert set(response.json()) == {"id", "product", "revision", "title", "summary", "body", "author_label", "sources", "first_published_at", "updated_at"}
    for private in (doc["id"], identity["organization"]["id"], identity["user"]["name"], "PRIVATE-MARKER", "profile", "artifact_key"):
        assert private not in response.text
    assert client.get(PUBLIC).json()["total"] == 1
    assert client.get(path).status_code == 401
    assert client.post(path + "/publication", json=command).status_code == 401
    assert client.get(public_path.replace("pharma", "loyer")).status_code == 404
    client.cookies.update(saved_cookies)
    withdraw = {"expected_revision": 1, "request_key": str(uuid4())}
    assert post(client, path + "/publication/withdraw", withdraw).json()["publication"]["status"] == "withdrawn"
    assert post(client, path + "/publication/withdraw", withdraw).json()["publication"]["revision"] == 2
    assert client.get(public_path).status_code == 404
    assert client.get(PUBLIC).json()["total"] == 0
    # An old retry cannot republish a withdrawn version.
    assert post(client, path + "/publication", command).json()["publication"]["status"] == "withdrawn"
    with service.db.session() as session:
        rows = list(session.scalars(select(PublicationRevision)))
        assert len(rows) == 2 and rows[0].content_json["public_consent"] is True
    history = client.get(path + "/publication").json()["history"]
    assert [item["action"] for item in history] == ["withdraw", "publish"]


def test_exact_preview_consent_expiry_csrf_and_conflicts(signed):
    client, _, _, _ = signed
    doc, _ = create(client)
    path = ROOT + "/" + doc["id"] + "/publication"
    prepared = post(client, path + "/preview", draft()).json()
    command = {**prepared, "request_key": str(uuid4()), "confirm_public": True}
    assert client.post(path, json=command).status_code == 403
    assert post(client, path, {**command, "confirm_public": False}).status_code == 409
    changed = deepcopy(command)
    changed["content"]["body"] += " This was not previewed."
    assert post(client, path, changed).status_code == 409
    assert post(client, path, {**command, "preview_expires_at": "2020-01-01T00:00:00Z"}).status_code == 409
    assert post(client, path, command).status_code == 200
    assert post(client, path, {**command, "request_key": str(uuid4())}).status_code == 409
    assert post(client, path, changed).status_code == 409
    publication, _ = preview_and_publish(client, doc["id"], draft(1, title="Updated public question"))
    assert publication["revision"] == 2
    assert client.get(PUBLIC + "/" + publication["id"]).json()["title"] == "Updated public question"
    assert post(client, path + "/withdraw", {"expected_revision": 1, "request_key": str(uuid4())}).status_code == 409
    assert client.get(PUBLIC).json()["total"] == 1


def test_cross_tenant_public_read_and_private_write_denial(signed):
    client, _, _, _ = signed
    doc, _ = create(client)
    publication, command = preview_and_publish(client, doc["id"])
    _register(client, "other-public@example.ch", "Other organization")
    assert client.get(PUBLIC + "/" + publication["id"]).status_code == 200
    for suffix in ("", "/publication"):
        assert client.get(ROOT + "/" + doc["id"] + suffix).status_code == 404
    assert post(client, ROOT + "/" + doc["id"] + "/publication", command).status_code == 404
    own, _ = create(client)
    own_path = ROOT + "/" + own["id"] + "/publication"
    assert post(client, own_path, command).status_code == 409
    assert post(client, own_path.replace("pharma", "loyer"), command).status_code == 404


def test_viewer_can_read_active_publication_but_cannot_publish(signed):
    client, service, identity, _ = signed
    doc, _ = create(client)
    active(client, doc)
    publication, command = preview_and_publish(client, doc["id"])
    member = _register(client, "public-reader@example.ch").json()
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=member["user"]["id"], organization_id=identity["organization"]["id"], role="viewer"))
        session.commit()
    post(client, "/api/auth/session/organization", {"organization_id": identity["organization"]["id"]})
    path = ROOT + "/" + doc["id"] + "/publication"
    assert client.get(path).json()["publication"]["id"] == publication["id"]
    assert post(client, path, command).status_code == 403
    assert post(client, path + "/preview", draft(1)).status_code == 403
    assert post(client, path + "/withdraw", {"request_key": str(uuid4()), "expected_revision": 1}).status_code == 403


def test_catalogue_literal_search_pagination_product_and_status(signed):
    client, service, _, _ = signed
    doc, _ = create(client)
    publication, _ = preview_and_publish(client, doc["id"], draft(title="Alpha 100% public question", body="A different BETA phrase exists in the authored body."))
    assert client.get(PUBLIC, params={"q": "alpha beta"}).json()["total"] == 1
    assert client.get(PUBLIC, params={"q": "100%"}).json()["total"] == 1
    assert client.get(PUBLIC, params={"q": "_"}).json()["total"] == 0
    assert client.get(PUBLIC.replace("pharma", "loyer")).json()["total"] == 0
    with service.db.session() as session:
        parent = session.get(ProductDossier, doc["id"])
        # Each independent publication keeps a valid owning dossier.
        for index in range(22):
            clone = ProductDossier(organization_id=parent.organization_id, product="pharma", profile_id=str(uuid4()), creation_key=str(uuid4()))
            from helvetic_lens.legal_profile_models import LegalMonitoringProfile
            original = session.get(LegalMonitoringProfile, parent.profile_id)
            copied = LegalMonitoringProfile(id=clone.profile_id, organization_id=parent.organization_id,
                created_by_user_id=original.created_by_user_id, config_json=original.config_json,
                status="draft", revision=1, creation_key=str(uuid4()))
            session.add(copied)
            session.flush()
            session.add(clone)
            session.flush()
            session.add(ProductPublication(organization_id=parent.organization_id, dossier_id=clone.id,
                product="pharma", status="published", revision=1, title=f"Independent title {index}",
                summary="Public summary", body="Public body", author_label="Editor", sources_json=[],
                first_published_at=utcnow(), updated_at=utcnow()))
        session.commit()
    first = client.get(PUBLIC).json()
    second = client.get(PUBLIC, params={"offset": 20}).json()
    assert first["total"] == second["total"] == 23
    assert len(first["items"]) == 20 and len(second["items"]) == 3
    assert not ({x["id"] for x in first["items"]} & {x["id"] for x in second["items"]})
    assert "body" not in first["items"][0]
    assert client.get(PUBLIC, params={"q": " ".join(str(i) for i in range(13))}).status_code == 422
    assert client.get(PUBLIC + "/" + publication["id"]).status_code == 200


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://person:secret@example.com", "https://127.0.0.1/", "https://localhost/", "https://service.internal/"])
def test_invalid_public_links_never_publish(signed, url):
    client, _, _, _ = signed
    doc, _ = create(client)
    response = post(client, ROOT + "/" + doc["id"] + "/publication/preview",
        draft(sources=[{"title": "Invalid source", "url": url}]))
    assert response.status_code == 422
    assert client.get(PUBLIC).json()["total"] == 0


def test_parent_deletion_removes_public_projection_and_audit(signed):
    client, service, _, _ = signed
    doc, _ = create(client)
    publication, _ = preview_and_publish(client, doc["id"])
    with service.db.session() as session:
        session.delete(session.get(ProductDossier, doc["id"]))
        session.commit()
        assert session.scalar(select(PublicationRevision)) is None
    assert client.get(PUBLIC + "/" + publication["id"]).status_code == 404
