from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from test_auth import _csrf, _register, _settings
from test_commute_contracts import DAY, configuration, leg

from helvetic_lens.commute_catalog import publish_legs
from helvetic_lens.main import create_app

ROOT = "/api/commute-watch"


def test_email_settings_require_explicit_verified_consent_csrf_and_current_version(api):
    from test_commute_jobs import NOW

    from helvetic_lens.models import User

    client, app, _, payload = api
    row = create(client, payload)
    path = ROOT + f"/monitors/{row['id']}/email"
    initial = client.get(path)
    assert initial.status_code == 200 and initial.headers["cache-control"] == "no-store"
    assert not initial.json()["consent_active"] and not initial.json()["delivery_service_available"]
    body = {"expected_version": 1, "configuration": {"delivery": {"email": "immediate"}}, "consent": True}
    assert client.put(path, json=body).status_code == 403
    assert client.put(path, json=body, headers=_csrf(client)).status_code == 409
    assert client.put(path, json={**body, "consent": "true"}, headers=_csrf(client)).status_code == 422
    identity = client.get("/api/auth/session").json()
    with app.state.service.db.session() as session:
        session.get(User, identity["user"]["id"]).email_verified_at = NOW
        session.commit()
    saved = client.put(path, json=body, headers=_csrf(client))
    assert saved.status_code == 200 and saved.json()["consent_active"]
    assert client.get(ROOT + f"/monitors/{row['id']}").json()["revision"] == 1
    assert client.put(path, json=body, headers=_csrf(client)).status_code == 409
    preview = client.get(path + "-preview")
    assert preview.status_code == 200 and preview.json()["status"] == "unavailable"
    with TestClient(app) as peer:
        assert peer.get(path).status_code == 401
        _register(peer, email="email-peer@example.test")
        assert peer.get(path).status_code == 404
        assert peer.get(path + "-preview").status_code == 404
        assert peer.put(path, json=body, headers=_csrf(peer)).status_code == 404
    disabled = client.put(path, json={"expected_version": saved.json()["monitor_version"],
        "configuration": {"delivery": {"email": "off"}}, "consent": False}, headers=_csrf(client))
    assert disabled.status_code == 200 and not disabled.json()["consent_active"]


def test_today_and_exact_event_routes_recheck_session_scope_and_feature_flag(api, monkeypatch):
    from test_commute_jobs import NOW, capture, refresh, source_grants
    from test_transport_feed import feed, trip_feed

    from helvetic_lens import commute_api
    from helvetic_lens.transport_feed import ALERTS, TRIPS

    client, app, settings, payload = api
    monkeypatch.setattr(commute_api, "clock", lambda: NOW)
    database = app.state.service.db
    identity = client.get("/api/auth/session").json()
    row = create(client, payload)
    grants = source_grants(database)
    capture(database, grants[TRIPS], trip_feed(cancelled=True))
    capture(database, grants[ALERTS], feed())
    started = client.post(ROOT + f"/monitors/{row['id']}/commands", headers=_csrf(client),
        json={"expected_version": row["version"], "action": "start"})
    assert started.status_code == 200, started.text
    with database.organization_context(identity["organization"]["id"]):
        refresh(database, started.json(), settings)
    response = client.get(ROOT + "/today")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    item, = response.json()["items"]
    event_path = ROOT + f"/events/{item['event_id']}"
    details = client.get(event_path, params={"sequence": item["sequence"], "monitor_id": row["id"]})
    assert details.status_code == 200 and details.headers["cache-control"] == "no-store"
    assert details.json()["snapshot"]["sequence"] == item["sequence"]
    assert client.get(event_path, params={"monitor_id": str(uuid4())}).status_code == 404
    assert client.get(event_path, params={"sequence": 0}).status_code == 422
    with TestClient(app) as peer:
        assert peer.get(ROOT + "/today").status_code == 401
        assert peer.get(event_path).status_code == 401
        _register(peer, email="today-peer@example.test")
        assert peer.get(ROOT + "/today").json()["items"] == []
        assert peer.get(event_path).status_code == 404
        assert peer.get(ROOT + "/today", params={"cursor": item["id"]}).status_code == 409
    settings.commute_watch_enabled = False
    for path in (ROOT + "/today", event_path):
        response = client.get(path)
        assert response.status_code == 404 and response.json()["code"] == "commute_disabled"
        assert response.headers["cache-control"] == "no-store"


@pytest.fixture
def api(tmp_path):
    settings = _settings(tmp_path, commute_watch_enabled=True)
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        _register(client)
        with app.state.service.db.session() as session:
            reference, = publish_legs(session, (replace(leg(), stop_sequences=(10, 20, 30)),))
            session.commit()
        payload = configuration().model_copy(update={"leg_reference_ids": (UUID(reference),)}).model_dump(mode="json")
        yield client, app, settings, payload


def create(client, payload):
    response = client.post(ROOT + "/monitors", json={"configuration": payload, "request_key": str(uuid4())}, headers=_csrf(client))
    assert response.status_code == 201, response.text
    return response.json()


def test_private_api_catalog_preview_edit_history_and_delete(api):
    client, _, _, payload = api
    catalog = client.get(ROOT + "/catalog", params={"service_day": DAY.isoformat(), "query": "Basel"})
    assert catalog.status_code == 200 and catalog.headers["cache-control"] == "no-store"
    assert [item["id"] for item in catalog.json()["items"]] == payload["leg_reference_ids"]
    preview = client.post(ROOT + "/preview", json={"configuration": payload, "service_day": DAY.isoformat(),
                                                  "static_version": "20260909"}, headers=_csrf(client))
    assert preview.status_code == 200 and not preview.json()["start_available"]
    row = create(client, payload)
    path = ROOT + "/monitors/" + row["id"]
    assert client.get(path).json() == row
    assert client.get(ROOT + "/monitors").json()["items"] == [row]
    edited = client.patch(path, json={"configuration": {**payload, "name": "Morning trip"}, "expected_version": 1}, headers=_csrf(client))
    assert edited.status_code == 200 and edited.json()["revision"] == 2
    stale = client.patch(path, json={"configuration": payload, "expected_version": 1}, headers=_csrf(client))
    assert stale.status_code == 409
    history = client.get(path + "/revisions")
    assert [item["revision"] for item in history.json()["items"]] == [1, 2]
    assert history.json()["items"][0]["configuration"] == payload
    deleted = client.request("DELETE", path, json={"expected_version": 2}, headers=_csrf(client))
    assert deleted.status_code == 204 and deleted.headers["cache-control"] == "no-store"
    assert client.get(path).status_code == 404


def test_start_cannot_be_enabled_by_feature_flag_or_caller_supplied_source_proof(api):
    client, _, _, payload = api
    row = create(client, payload)
    path = ROOT + "/monitors/" + row["id"]
    capabilities = client.get(ROOT + "/capabilities").json()
    assert capabilities["drafts_available"] and not capabilities["start_available"]
    for action in ("start", "resume"):
        response = client.post(path + "/commands", json={"expected_version": 1, "action": action}, headers=_csrf(client))
        assert response.status_code == 409
        assert response.json()["code"] == ("commute_source_not_ready" if action == "start" else "commute_action_invalid")
    forged = client.post(path + "/commands", json={"expected_version": 1, "action": "start", "source_ready": True}, headers=_csrf(client))
    assert forged.status_code == 422 and client.get(path).json()["status"] == "draft"
    assert client.post(ROOT + "/catalog", json={"source_ready": True}, headers=_csrf(client)).status_code == 405


def test_api_requires_csrf_and_hides_private_owner_details(api):
    client, app, _, payload = api
    row = create(client, payload)
    path = ROOT + "/monitors/" + row["id"]
    assert client.patch(path, json={"configuration": payload, "expected_version": 1}).status_code == 403
    with TestClient(app) as peer:
        assert peer.get(path).status_code == 401
        _register(peer, email="commute-peer@example.test")
        for suffix in ("", "/revisions"):
            response = peer.get(path + suffix)
            assert response.status_code == 404 and "Basel commute" not in response.text
            assert response.headers["cache-control"] == "no-store"
        assert peer.get(ROOT + "/monitors").json()["items"] == []
        response = peer.patch(path, json={"configuration": payload, "expected_version": 1}, headers=_csrf(peer))
        assert response.status_code == 404
        assert peer.get(ROOT + "/monitors", params={"after_id": row["id"]}).status_code == 404


def test_disabled_flag_and_invalid_request_data_are_enforced(api):
    client, _, settings, payload = api
    for invalid in ({**payload, "leg_reference_ids": [str(uuid4())]}, {**payload, "weekdays": [True]}):
        response = client.post(ROOT + "/monitors", json={"configuration": invalid, "request_key": str(uuid4())}, headers=_csrf(client))
        assert response.status_code == 422
    assert client.get(ROOT + "/catalog", params={"service_day": "2026-02-30"}).status_code == 422
    settings.commute_watch_enabled = False
    assert client.get(ROOT + "/capabilities").status_code == 404
    assert client.get(ROOT + "/monitors").status_code == 404


def test_browser_preview_needs_no_technical_version_and_returns_friendly_saved_names(api):
    client, _, _, payload = api
    preview = client.post(ROOT + "/preview", json={"configuration": payload, "service_day": DAY.isoformat()}, headers=_csrf(client))
    assert preview.status_code == 200, preview.text
    assert preview.json()["legs"][0]["boarding_name"] == "Basel origin"
    assert preview.json()["start_available"] is False
    row = create(client, payload)
    assert row["reference_labels"][0]["label"] == "Fixture route: Basel origin → Basel destination"
    assert row["last_check_at"] is row["next_check_at"] is None
    history = client.get(ROOT + "/monitors/" + row["id"] + "/revisions").json()
    assert history["items"][0]["reference_labels"] == row["reference_labels"]


def test_commute_inventory_obeys_private_owner_and_feature_switch(api):
    client, app, settings, payload = api
    row = create(client, payload)
    response = client.get("/api/monitoring-centre", params={"domain": "commute"})
    assert response.status_code == 200 and "no-store" in response.headers["cache-control"]
    assert [item["id"] for item in response.json()["items"]] == [row["id"]]
    template = next(item for item in response.json()["templates"] if item["id"] == "commute")
    assert template["href"] == "/commute-watch" and template["availability"] == "available"
    with TestClient(app) as peer:
        _register(peer, email="centre-commute-peer@example.test")
        assert peer.get("/api/monitoring-centre", params={"domain": "commute"}).json()["items"] == []
    settings.commute_watch_enabled = False
    hidden = client.get("/api/monitoring-centre", params={"domain": "commute"}).json()
    assert hidden["items"][0]["href"] is None and hidden["items"][0]["health"] == "disabled"
    assert len(hidden["templates"]) == 9 and not any(item["id"] == "customs" for item in hidden["templates"])
