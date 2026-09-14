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
    start = client.post(path + "/start", headers=_csrf(client), json={"expected_version": 2})
    assert start.status_code == 409 and start.json()["code"] == "trademark_source_not_configured"
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


def test_http_candidate_review_reopens_and_preserves_before_after(api, monkeypatch):
    from datetime import timedelta

    from test_trademark_sources import NOW, accept, grant
    from test_trademark_workflow import source_facts

    from helvetic_lens import trademark_api
    client, app, _ = api
    now = NOW
    monkeypatch.setattr(trademark_api, "_now", lambda: now)
    database = app.state.service.db
    permission = grant(database, private_decisions_allowed=True)
    accept(database, permission)
    config = portfolio().model_dump(mode="json")
    preview = client.post(ROOT + "/preview", headers=_csrf(client), json={"configuration": config}).json()
    assert preview["start_available"] and not preview["coverage_verified"]
    monitor = client.post(ROOT + "/monitors", headers=_csrf(client), json={"configuration": config, "request_key": str(uuid4())}).json()
    path = ROOT + "/monitors/" + monitor["id"]
    assert client.post(path + "/start", json={"expected_version": 1}).status_code == 403
    assert client.post(path + "/start", headers=_csrf(client), json={"expected_version": 1}).json()["status"] == "active"
    assert client.post(path + "/refresh", headers=_csrf(client)).status_code == 200
    row, = client.get(path + "/candidates").json()["items"]
    cp = path + "/candidates/" + row["id"]
    body = {"expected_version": row["version"], "expected_evaluation_hash": row["evaluation_hash"], "decision": "relevant"}
    assert client.post(cp + "/review", json=body).status_code == 403
    assert client.post(cp + "/review", headers=_csrf(client), json={**body, "calibration": {}}).status_code == 422
    assert client.post(cp + "/review", headers=_csrf(client), json=body).json()["decision"] == "relevant"
    assert client.post(cp + "/review", headers=_csrf(client), json=body).status_code == 409
    assert not client.get(ROOT + "/inbox").json()["items"]
    accept(database, permission, cursor=1, facts=source_facts(owners=["New Holder SA"]))
    now = NOW + timedelta(seconds=1)
    assert client.post(path + "/refresh", headers=_csrf(client)).status_code == 200
    event, = client.get(ROOT + "/inbox").json()["items"]
    assert event["priority"] == "high" and "changed_owners" in event["change_codes"]
    exact = client.get(cp + "/events/" + event["id"])
    assert exact.status_code == 200 and exact.headers["cache-control"] == "no-store"
    assert exact.json()["previous"]["facts"]["owners"] == ["Synthetic Owner AG"]
    assert exact.json()["current"]["needs_review"]
    assert client.get(cp + "/reviews").json()["items"][0]["decision"] == "relevant"
    assert client.get(cp + "/history?limit=1").json()["next_cursor"] == 2
    centre = client.get("/api/monitoring-centre", params={"domain": "ip"}).json()["items"][0]
    assert centre["last_check_at"] and centre["next_check_at"]
    assert client.post(cp + "/send-to-counsel", headers=_csrf(client), json={}).status_code == 404
    assert client.post(path + "/pause", headers=_csrf(client), json={"expected_version": 2}).json()["status"] == "paused"
    assert client.post(path + "/archive", headers=_csrf(client), json={"expected_version": 3}).json()["status"] == "archived"
    assert client.request("DELETE", path, headers=_csrf(client), json={"expected_version": 4}).json() == {"deleted": True}
    assert client.get(cp).status_code == 404
