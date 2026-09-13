from uuid import uuid4

import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from test_auth import _csrf, _register, _settings
from test_trademark_matching import portfolio

from helvetic_lens.main import create_app

ROOT = "/api/trademark-watch"


@pytest.fixture
def api(tmp_path):
    settings = _settings(tmp_path, trademark_watch_enabled=True)
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        _register(client)
        yield client, app, settings


def test_http_portfolio_roundtrip_no_source_activation_and_no_forged_calibration(api):
    client, _, _ = api
    config = portfolio().model_dump(mode="json")
    payload = {"configuration": config, "request_key": str(uuid4())}
    assert client.get(ROOT + "/capabilities").json()["start_available"] is False
    assert not client.post(ROOT + "/preview", headers=_csrf(client), json={"configuration": config}).json()["live_results_checked"]
    response = client.post(ROOT + "/monitors", headers=_csrf(client), json=payload)
    assert response.status_code == 201 and response.headers["cache-control"] == "no-store"
    saved, path = response.json(), ROOT + "/monitors/" + response.json()["id"]
    assert client.post(ROOT + "/monitors", headers=_csrf(client), json=payload).json() == saved
    assert client.post(ROOT + "/monitors", headers=_csrf(client), json={**payload, "calibration": {"lexical_minimum": 1}}).status_code == 422
    modified = {**config, "name": "Second portfolio revision"}
    body = {"configuration": modified, "expected_version": 1}
    assert client.patch(path, headers=_csrf(client), json=body).json()["version"] == 2
    assert client.patch(path, headers=_csrf(client), json=body).status_code == 409
    assert len(client.get(path + "/revisions").json()["items"]) == 2
    assert client.get(path + "/revisions", params={"limit": 101}).status_code == 422
    assert client.post(path + "/start", headers=_csrf(client), json={"expected_version": 2}).status_code == 404
    assert client.request("DELETE", path, headers=_csrf(client), json={"expected_version": 2}).status_code == 409
    assert client.post(path + "/archive", headers=_csrf(client), json={"expected_version": 2}).json()["status"] == "archived"
    assert client.request("DELETE", path, headers=_csrf(client), json={"expected_version": 3}).json() == {"deleted": True}
    assert client.get(path).status_code == 404


def test_http_csrf_same_organization_peer_and_feature_denial(api):
    from sqlalchemy import select

    from helvetic_lens.models import OrganizationMembership
    from helvetic_lens.trademark_models import TrademarkMonitor
    client, app, settings = api
    body = {"configuration": portfolio().model_dump(mode="json"), "request_key": str(uuid4())}
    assert client.post(ROOT + "/monitors", json=body).status_code == 403
    saved = client.post(ROOT + "/monitors", headers=_csrf(client), json=body).json()
    path = ROOT + "/monitors/" + saved["id"]
    with app.state.service.db.session(include_all_organizations=True) as session:
        organization = session.scalar(select(TrademarkMonitor.organization_id).where(TrademarkMonitor.id == saved["id"]))
    with TestClient(app) as peer:
        identity = _register(peer, email="trademark-peer@example.test").json()
        with app.state.service.db.session(include_all_organizations=True) as session:
            session.add(OrganizationMembership(organization_id=organization, user_id=identity["user"]["id"], role="organization_admin"))
            session.commit()
        assert peer.post("/api/auth/session/organization", headers=_csrf(peer), json={"organization_id": organization}).status_code == 200
        for endpoint in (path, path + "/revisions"):
            response = peer.get(endpoint)
            assert response.status_code == 404 and response.headers["cache-control"] == "no-store"
        assert peer.get(ROOT + "/monitors").json()["items"] == []
        assert peer.post(path + "/archive", headers=_csrf(peer), json={"expected_version": 1}).status_code == 404
    settings.trademark_watch_enabled = False
    denied = client.get(path)
    assert denied.status_code == 404 and denied.headers["cache-control"] == "no-store"
    assert "ALMORA" not in denied.text
