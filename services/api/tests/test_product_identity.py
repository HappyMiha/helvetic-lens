"""The corrected legal name must retain real records and every access boundary."""
import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_auth import _register
from test_legal_profiles import config
from test_private_dossier_monitoring import private, remove
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_guests import accept, guest, invitation
from test_product_publications import draft
from test_product_teams import switch

from helvetic_lens.product_identity import ProductAliasMiddleware, public_product_slug
from helvetic_lens.product_models import ProductDossier
from helvetic_lens.product_reuse import source_url


@pytest.mark.parametrize("first", ["loyer", "legal"])
def test_legal_aliases_share_existing_records_idempotency_and_private_boundaries(signed, first):
    client, service, _, _ = signed
    command = {"creation_key": str(uuid4()), "config": config()}
    created = post(client, f"/api/products/{first}/dossiers", command)
    assert created.status_code == 201, created.text
    identifier = created.json()["id"]
    roots = [f"/api/products/{name}/dossiers/{identifier}" for name in ["loyer", "legal"]]
    for name, root in zip(["loyer", "legal"], roots, strict=True):
        assert post(client, f"/api/products/{name}/dossiers", command).json()["id"] == identifier
        assert client.get(root).json()["id"] == identifier
        assert client.get(root + "/export").status_code == 200
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(ProductDossier)) == 1
        assert session.get(ProductDossier, identifier).product == "loyer"
    note = {"request_key": str(uuid4()), "kind": "note", "body": "Private retained legal evidence"}
    assert client.post(roots[1] + "/entries", json=note).status_code == 403
    saved = post(client, roots[1] + "/entries", note)
    assert saved.status_code == 201, saved.text
    assert post(client, roots[0] + "/entries", note).json()["id"] == saved.json()["id"]
    assert client.get(roots[0]).json()["entries"][0]["body"] == note["body"]
    assert client.get(roots[1].replace("legal", "pharma")).status_code == 404
    _register(client, "unrelated-legal@example.ch", "Unrelated legal workspace")
    for root in roots:
        assert client.get(root).status_code == 404
        assert post(client, root + "/entries", note).status_code == 404
    client.cookies.clear()
    for root in roots:
        response = client.get(root)
        assert response.status_code == 401 and "no-store" in response.headers["cache-control"]
        assert note["body"] not in response.text


def test_explicit_publication_and_withdrawal_work_across_both_spellings(signed):
    client, _, _, _ = signed
    result = post(client, "/api/products/loyer/dossiers", {"creation_key": str(uuid4()), "config": config()})
    root = "/api/products/legal/dossiers/" + result.json()["id"]
    post(client, root + "/entries", {"request_key": str(uuid4()), "kind": "note", "body": "DO-NOT-PUBLISH-LEGAL"})
    prepared = post(client, root + "/publication/preview", draft())
    assert prepared.status_code == 200, prepared.text
    command = {**prepared.json(), "request_key": str(uuid4()), "confirm_public": True}
    publication = post(client, root.replace("legal", "loyer") + "/publication", command)
    assert publication.status_code == 200, publication.text
    identifier = publication.json()["publication"]["id"]
    owner = dict(client.cookies)
    client.cookies.clear()
    for product in ["legal", "loyer"]:
        public = client.get(f"/api/products/{product}/public-dossiers/{identifier}")
        assert public.status_code == 200 and public.headers["cache-control"] == "no-store"
        assert public.json()["title"] == command["content"]["title"]
        assert "DO-NOT-PUBLISH-LEGAL" not in public.text
        assert client.get(f"/api/products/{product}/public-knowledge?q=research").status_code == 200
    assert client.get(f"/api/products/pharma/public-dossiers/{identifier}").status_code == 404
    assert client.get(root).status_code == 401
    switch(client, owner)
    withdrawn = post(client, root + "/publication/withdraw", {"expected_revision": 1, "request_key": str(uuid4())})
    assert withdrawn.status_code == 200
    for product in ["legal", "loyer"]:
        assert client.get(f"/api/products/{product}/public-dossiers/{identifier}").status_code == 404


@pytest.mark.parametrize("role", ["VIEWER", "CONTRIBUTOR", "EDITOR"])
def test_existing_guest_invitation_roles_and_revocation_survive_rename(signed, role):
    client, service, _, _ = signed
    owner = dict(client.cookies)
    account, cookies = guest(client, service)
    doc, legacy, _ = private(client, "loyer")
    canonical = legacy.replace("/loyer/", "/legal/")
    invite = invitation(client, legacy, account, role)
    switch(client, cookies)
    assert client.get(canonical).status_code == 404
    accept(client, canonical, invite)
    for root in [legacy, canonical]:
        response = client.get(root)
        assert response.status_code == 200, response.text
        assert response.json()["id"] == doc["id"]
        assert response.json()["access"]["role"] == role
        assert client.get(root.replace("/loyer/", "/pharma/").replace("/legal/", "/pharma/")).status_code == 404
        note = post(client, root + "/entries", {"request_key": str(uuid4()), "kind": "note", "body": "Scoped legal contribution"})
        assert note.status_code == (403 if role == "VIEWER" else 201), note.text
        assert post(client, root + "/publication/withdraw", {}).status_code == 403
    switch(client, owner)
    remove(client, legacy, account["user"]["id"])
    switch(client, cookies)
    assert all(client.get(root).status_code == 404 for root in [legacy, canonical])


@pytest.mark.parametrize("path,expected", [
    ("/api/products/legal/dossiers/id", "/api/products/loyer/dossiers/id"),
    ("/api/products/legal", "/api/products/loyer"),
    ("/api/products/legalish/dossiers/id", "/api/products/legalish/dossiers/id"),
    ("/api/products/pharma/dossiers/id", "/api/products/pharma/dossiers/id"),
    ("/api/products/loyer/dossiers/id", "/api/products/loyer/dossiers/id"),
    ("/other/api/products/legal", "/other/api/products/legal"),
])
def test_alias_preserves_request_identity_query_body_and_segment_boundaries(path, expected):
    scope = {"type": "http", "path": path, "raw_path": path.encode(), "query_string": b"q=alpha%26beta", "headers": [(b"cookie", b"fixture")], "method": "POST"}
    async def receive():
        return {"type": "http.request", "body": b"unchanged fixture"}
    async def send(_):
        pass
    async def app(mapped, downstream_receive, downstream_send):
        assert mapped["path"] == expected and mapped["raw_path"] == expected.encode()
        assert mapped["query_string"] == scope["query_string"] and mapped["headers"] == scope["headers"]
        assert mapped["method"] == "POST" and (await downstream_receive())["body"] == b"unchanged fixture"
        assert downstream_send is send
    asyncio.run(ProductAliasMiddleware(app)(scope, receive, send))
    assert scope["path"] == path and scope["raw_path"] == path.encode()


def test_new_public_provenance_uses_corrected_host_and_unknown_products_fail_closed():
    for product in ["loyer", "legal"]:
        assert source_url(product, "fixture") == "https://legal.helveticlens.ch/public-dossiers/fixture"
    assert source_url("pharma", "fixture") == "https://pharma.helveticlens.ch/public-dossiers/fixture"
    with pytest.raises(ValueError):
        public_product_slug("legal.evil.example")
