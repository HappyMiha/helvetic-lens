"""Public catalogue origin is retained only after validating an actor-bound receipt."""
import base64
import json
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from test_auth import _register
from test_product_dossiers import ROOT, active, create, post
from test_product_dossiers import signed as signed
from test_product_search_pagination import mock_source

from helvetic_lens import product_provenance, product_research
from helvetic_lens.db import utcnow
from helvetic_lens.models import OrganizationMembership, User, UserSession


def discover(client, monkeypatch, *, provider="europepmc", product="pharma", query='GLP-1 <b>safety</b>'):
    def response(request):
        if provider == "europepmc":
            return httpx.Response(200, json={"hitCount": 1, "resultList": {"result": [{"source": "MED", "id": "321",
                "title": "<script>Catalogue title</script>", "authorString": "A. Researcher", "firstPublicationDate": "2026-09-01"}]}})
        return httpx.Response(200, json={"results": {"bindings": [{"work": {"value": "https://fedlex.data.admin.ch/eli/cc/2026/321"},
            "title": {"value": "<script>Catalogue title</script>"}}]}})
    with monkeypatch.context() as source_patch:
        mock_source(source_patch, response)
        result = client.get(f"/api/products/{product}/discover", params={"q": query, "provider": provider})
    assert result.status_code == 200, result.text
    return result.json()


def payload(result):
    return {"request_key": str(uuid4()), "receipt": result["items"][0]["discovery_receipt"]}


@pytest.mark.parametrize("provider", ["europepmc", "fedlex"])
def test_import_preserves_exact_metadata_and_query_in_export_and_escaped_brief(signed, monkeypatch, provider):
    client, service, _, model = signed
    doc, _ = create(client)
    path = ROOT + "/" + doc["id"]
    found = discover(client, monkeypatch, provider=provider)
    data = payload(found)
    async def forbidden(*args, **kwargs):
        raise AssertionError("Import must not fetch or repeat the query")
    monkeypatch.setattr(product_research, "public_search", forbidden)
    saved = post(client, path + "/discovery-references", data)
    assert saved.status_code == 201, saved.text
    entry = saved.json()
    origin = entry["data"]["discovery"]
    assert origin["provider"] == provider and origin["query"] == found["query"]
    assert origin["retrieved_at"] == found["checked_at"] and origin["page_number"] == 1
    assert origin["record"] == {k: v for k, v in found["items"][0].items() if k != "discovery_receipt"}
    assert entry["url"] == origin["record"]["url"] and entry["author"] == "Ada Example"
    assert data["receipt"] not in json.dumps(entry) and "signature" not in json.dumps(entry)
    assert post(client, path + "/discovery-references", data).json()["id"] == entry["id"]
    assert client.get(path + "/export").json()["entries"] == [entry]
    brief = client.get(path + "/brief")
    assert brief.status_code == 200 and 'Search provenance was verified on import' in brief.text
    assert '<script>' not in brief.text and '&lt;script&gt;Catalogue title' in brief.text
    assert 'GLP-1 &lt;b&gt;safety&lt;/b&gt;' in brief.text and origin["retrieved_at"] in brief.text
    manual = post(client, path + "/entries", {"request_key": str(uuid4()), "kind": "reference", "url": entry["url"]}).json()
    assert "discovery" not in manual["data"]
    assert "No search provenance recorded" in client.get(path + "/brief").text
    assert not model.calls and not service.fetcher.calls


def test_new_expired_import_fails_but_completed_exact_retry_returns_same_reference(signed, monkeypatch):
    client, _, _, _ = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"] + "/discovery-references"
    found = discover(client, monkeypatch)
    data = payload(found)
    saved = post(client, route, data).json()
    future = utcnow() + timedelta(minutes=31)
    monkeypatch.setattr(product_provenance, "utcnow", lambda: future)
    assert post(client, route, data).json()["id"] == saved["id"]
    expired = post(client, route, {**data, "request_key": str(uuid4())})
    assert expired.status_code == 409 and "expired" in expired.json()["detail"]
    assert client.get(ROOT + "/" + doc["id"]).json()["entry_count"] == 1


@pytest.mark.parametrize("field,value", [("query", "different query"), ("provider", "fedlex"),
    ("retrieved_at", "2026-09-27T00:00:00+00:00"), ("page_number", 2),
    ("record", {"title": "Invented", "url": "https://evil.example/"})])
def test_changed_receipt_is_rejected_without_writing(signed, monkeypatch, field, value):
    client, _, _, _ = signed
    doc, _ = create(client)
    data = payload(discover(client, monkeypatch))
    decoded = json.loads(base64.urlsafe_b64decode(data["receipt"]))
    decoded[field] = value
    data["receipt"] = base64.urlsafe_b64encode(json.dumps(decoded).encode()).decode()
    assert post(client, ROOT + "/" + doc["id"] + "/discovery-references", data).status_code == 409
    assert client.get(ROOT + "/" + doc["id"]).json()["entry_count"] == 0


def test_bad_receipts_extra_client_metadata_and_key_collisions_fail(signed, monkeypatch):
    client, _, _, _ = signed
    doc, _ = create(client)
    path = ROOT + "/" + doc["id"]
    route = path + "/discovery-references"
    data = payload(discover(client, monkeypatch))
    for bad in ("not a receipt", base64.urlsafe_b64encode(b'null').decode(), base64.urlsafe_b64encode(b'{}').decode()):
        assert post(client, route, {**data, "receipt": bad}).status_code == 409
    for bad in ({"receipt": "x" * 24577}, {"receipt": ""}, {"query": "fake"}, {"url": "https://example.ch/"}):
        assert post(client, route, {**data, **bad}).status_code == 422
    assert post(client, path + "/entries", {"request_key": data["request_key"], "kind": "note", "body": "Existing note"}).status_code == 201
    assert post(client, route, data).status_code == 409
    other = payload(discover(client, monkeypatch, query="other query"))
    assert post(client, route, other).status_code == 201
    assert post(client, route, {**data, "request_key": other["request_key"]}).status_code == 409


def test_product_binding_both_clients_and_csrf(signed, monkeypatch):
    client, _, _, _ = signed
    doc, original = create(client)
    legal = post(client, ROOT.replace("pharma", "loyer"), {**original, "creation_key": str(uuid4())}).json()
    route = ROOT.replace("pharma", "loyer") + "/" + legal["id"] + "/discovery-references"
    pharma = payload(discover(client, monkeypatch))
    assert post(client, route, pharma).status_code == 409
    loyer = payload(discover(client, monkeypatch, provider="fedlex", product="loyer"))
    assert client.post(route, json=loyer).status_code == 403
    assert post(client, route, loyer).status_code == 201
    wrong = ROOT.replace("pharma", "loyer") + "/" + doc["id"] + "/discovery-references"
    assert post(client, wrong, loyer).status_code == 404


def test_receipt_does_not_grant_other_workspace_actor_or_draft_access(signed, monkeypatch):
    client, service, identity, _ = signed
    private, _ = create(client)
    shared, _ = create(client)
    active(client, shared)
    route = ROOT + "/" + shared["id"] + "/discovery-references"
    data = payload(discover(client, monkeypatch))
    member = _register(client, "provenance-reader@example.ch").json()
    assert post(client, route, data).status_code == 404
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=member["user"]["id"], organization_id=identity["organization"]["id"], role="viewer"))
        session.commit()
    assert post(client, "/api/auth/session/organization", {"organization_id": identity["organization"]["id"]}).status_code == 200
    assert post(client, route, data).status_code == 403
    with service.db.session() as session:
        session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == member["user"]["id"])).role = "organization_admin"
        session.commit()
    assert post(client, route, data).status_code == 409
    fresh = payload(discover(client, monkeypatch))
    assert post(client, ROOT + "/" + private["id"] + "/discovery-references", fresh).status_code == 404
    assert post(client, route, fresh).status_code == 201
    client.cookies.clear()
    assert client.post(route, json=fresh).status_code == 401


def test_new_login_cannot_reuse_old_session_receipt(signed, monkeypatch):
    client, _, _, _ = signed
    doc, _ = create(client)
    data = payload(discover(client, monkeypatch))
    client.cookies.clear()
    result = client.post("/api/auth/login", json={"email": "owner@example.ch", "password": "correct horse battery staple"})
    assert result.status_code == 200
    assert post(client, ROOT + "/" + doc["id"] + "/discovery-references", data).status_code == 409


@pytest.mark.parametrize("change", ["session", "membership", "user"])
def test_discovery_rechecks_current_authorization_after_source_await(signed, monkeypatch, change):
    client, service, identity, _ = signed
    async def changed(*args, **kwargs):
        with service.db.session() as session:
            if change == "session":
                session.scalar(select(UserSession).where(UserSession.user_id == identity["user"]["id"])).revoked_at = utcnow()
            elif change == "membership":
                session.delete(session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"])))
            else:
                session.get(User, identity["user"]["id"]).active = False
            session.commit()
        return {"items": [], "total": 0, "page_number": 1}
    monkeypatch.setattr(product_research, "public_search", changed)
    result = client.get("/api/products/pharma/discover", params={"q": "safety", "provider": "europepmc"})
    assert result.status_code in (401, 403)
    assert "discovery_receipt" not in result.text


@pytest.mark.parametrize("change", ["role", "session"])
def test_import_rechecks_authorization_inside_write_transaction(signed, monkeypatch, change):
    client, service, identity, _ = signed
    doc, _ = create(client)
    data = payload(discover(client, monkeypatch))
    original = product_provenance.principal
    def changed(session, actor, now, *, write=False):
        if write:
            with service.db.session() as other:
                if change == "role":
                    other.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"])).role = "viewer"
                else:
                    other.scalar(select(UserSession).where(UserSession.user_id == identity["user"]["id"])).revoked_at = utcnow()
                other.commit()
        return original(session, actor, now, write=write)
    monkeypatch.setattr(product_provenance, "principal", changed)
    result = post(client, ROOT + "/" + doc["id"] + "/discovery-references", data)
    assert result.status_code in (401, 403)
    with service.db.session() as session:
        from helvetic_lens.product_models import DossierEntry
        assert session.scalar(select(DossierEntry).where(DossierEntry.dossier_id == doc["id"])) is None


def test_oversized_source_url_is_omitted_and_workspace_hits_never_get_public_receipts(signed, monkeypatch):
    client, _, _, _ = signed
    doc, _ = create(client)
    post(client, ROOT + "/" + doc["id"] + "/entries", {"request_key": str(uuid4()), "kind": "note", "body": "Exact local safety knowledge"})
    private = client.get("/api/products/pharma/discover", params={"q": "safety", "provider": "workspace"}).json()
    assert private["items"] and all("discovery_receipt" not in item for item in private["items"])
    def oversized(request):
        return httpx.Response(200, json={"results": {"bindings": [{"work": {"value": "https://fedlex.data.admin.ch/" + "x" * 2000}, "title": {"value": "Large"}}]}})
    mock_source(monkeypatch, oversized)
    result = client.get("/api/products/pharma/discover", params={"q": "safety", "provider": "fedlex"})
    assert result.status_code == 200, result.text
    assert result.json()["items"] == [] and result.json()["omitted_records"] == 1
