from uuid import uuid4

import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from test_auth import _csrf, _register, _settings
from test_road_catalog import TABLE
from test_road_feed import NOW
from test_road_repository import seeded

from helvetic_lens import road_api
from helvetic_lens.main import create_app

ROOT = "/api/road-watch"
TABLE_QUERY = dict(zip(("country", "table", "table_version"), TABLE))


@pytest.fixture
def api(tmp_path, monkeypatch):
    settings = _settings(tmp_path, road_watch_enabled=True)
    monkeypatch.setattr(road_api, "clock", lambda: NOW)
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        _register(client)
        payload, _ = seeded(app.state.service.db)
        yield client, app, settings, payload


def create(client, payload, key=None):
    response = client.post(ROOT + "/monitors", headers=_csrf(client),
        json={"configuration": payload, "request_key": key or str(uuid4())})
    assert response.status_code == 201, response.text
    return response.json()


def test_catalogue_preview_save_edit_history_archive_and_delete(api):
    client, _, _, payload = api
    result = client.get(ROOT + "/catalog", params=TABLE_QUERY)
    assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
    assert [item["id"] for item in result.json()["items"]] == payload["corridor_reference_ids"]
    assert "points" not in result.text and "asset_hash" not in result.text
    preview = client.post(ROOT + "/preview", headers=_csrf(client), json={"configuration": payload, **TABLE_QUERY})
    assert preview.status_code == 200 and not preview.json()["start_available"]
    assert not preview.json()["live_results_checked"]
    key = str(uuid4())
    saved = create(client, payload, key)
    assert create(client, payload, key) == saved
    path = ROOT + "/monitors/" + saved["id"]
    assert client.get(path).json() == saved
    assert client.get(ROOT + "/monitors").json()["items"] == [saved]
    changed = client.patch(path, headers=_csrf(client), json={"expected_version": 1,
                           "configuration": {**payload, "name": "My edited road watch"}})
    assert changed.status_code == 200 and changed.json()["revision"] == 2
    assert client.patch(path, headers=_csrf(client), json={"expected_version": 1, "configuration": payload}).status_code == 409
    history = client.get(path + "/revisions")
    assert [r["revision"] for r in history.json()["items"]] == [1, 2]
    archived = client.post(path + "/commands", headers=_csrf(client), json={"expected_version": 2, "action": "archive"})
    assert archived.status_code == 200 and archived.json()["status"] == "archived"
    deleted = client.request("DELETE", path, headers=_csrf(client), json={"expected_version": 3})
    assert deleted.status_code == 204 and deleted.headers["cache-control"] == "no-store"
    assert client.get(path).status_code == 404


def test_auth_csrf_foreign_owner_and_feature_denials_are_not_cacheable(api):
    client, app, settings, payload = api
    saved = create(client, payload)
    path = ROOT + "/monitors/" + saved["id"]
    body = {"expected_version": 1, "configuration": payload}
    csrf_denied = client.patch(path, json=body)
    assert csrf_denied.status_code == 403 and csrf_denied.headers["cache-control"] == "no-store"
    with TestClient(app) as peer:
        result = peer.get(path)
        assert result.status_code == 401 and result.headers["cache-control"] == "no-store"
        _register(peer, email="road-peer@example.test")
        assert peer.get(ROOT + "/monitors").json()["items"] == []
        for suffix in ("", "/revisions", "/corridors"):
            response = peer.get(path + suffix)
            assert response.status_code == 404 and "Private weekend trip" not in response.text
            assert response.headers["cache-control"] == "no-store"
        assert peer.patch(path, headers=_csrf(peer), json=body).status_code == 404
        assert peer.get(ROOT + "/monitors", params={"after_id": saved["id"]}).status_code == 404
    settings.road_watch_enabled = False
    for route in (path, ROOT + "/capabilities", ROOT + "/catalog"):
        response = client.get(route)
        assert response.status_code == 404 and response.headers["cache-control"] == "no-store"


def test_client_cannot_forge_source_approval_or_enable_unsupported_processing(api):
    client, _, _, payload = api
    saved = create(client, payload)
    path = ROOT + "/monitors/" + saved["id"] + "/commands"
    for action in ("start", "resume"):
        response = client.post(path, headers=_csrf(client), json={"expected_version": 1, "action": action})
        assert response.status_code == 409 and response.json()["code"] == (
            "road_source_not_ready" if action == "start" else "road_monitor_action_invalid")
    forged = client.post(path, headers=_csrf(client), json={"expected_version": 1, "action": "start", "source_ready": True})
    assert forged.status_code == 422 and forged.headers["cache-control"] == "no-store"
    assert client.post(ROOT + "/catalog", headers=_csrf(client), json={"grant": True}).status_code == 405
    invalid = client.post(ROOT + "/monitors", headers=_csrf(client), json={"request_key": str(uuid4()),
        "configuration": {**payload, "materiality": {"minimum_delay_seconds": True}}})
    assert invalid.status_code == 422 and invalid.headers["cache-control"] == "no-store"


def test_catalogue_and_preview_do_not_require_user_supplied_table_numbers(api):
    client, app, _, payload = api
    from test_road_catalog import mapping, topology

    from helvetic_lens.road_catalog import revoke_topology

    result = client.get(ROOT + "/catalog")
    assert result.status_code == 200
    label = result.json()["items"][0]
    assert label["id"] == payload["corridor_reference_ids"][0]
    assert label["name"] == "Synthetic corridor northbound"
    saved = create(client, payload)
    path = ROOT + "/monitors/" + saved["id"]
    assert client.get(path + "/corridors").json()["items"] == [label]
    preview = client.post(ROOT + "/preview", headers=_csrf(client), json={"configuration": payload})
    assert preview.status_code == 200 and preview.json()["corridors"] == [label]
    assert not preview.json()["start_available"]
    for partial in ({"country": "ch"}, {"table": "test", "table_version": "synthetic-v1"}):
        assert client.get(ROOT + "/catalog", params=partial).status_code == 422
        assert client.post(ROOT + "/preview", headers=_csrf(client), json={"configuration": payload, **partial}).status_code == 422
    newer = topology(app.state.service.db, version="synthetic-v2")
    mapping(app.state.service.db, label["id"], newer, generation=1)
    assert client.get(ROOT + "/catalog").json()["items"][0]["generation"] == 2
    with app.state.service.db.session() as session:
        revoke_topology(session, newer, now=NOW)
        session.commit()
    # A denied latest label must not silently revive an older permitted grant.
    assert client.get(ROOT + "/catalog").json()["items"] == []
    redacted = client.get(path + "/corridors")
    assert redacted.json()["items"] == [{"id": label["id"], "state": "unavailable"}]
    assert label["name"] not in redacted.text
    assert client.get(path).json()["configuration"]["name"] == payload["name"]
    # Exact-version readers can still use that version's permitted map. The
    # displayed generation belongs to the stable reference, not the old map.
    assert client.get(ROOT + "/catalog", params=TABLE_QUERY).json()["items"][0]["name"] == label["name"]


def test_monitoring_centre_keeps_road_inventory_private_and_source_gated(api):
    client, app, settings, payload = api
    saved = create(client, payload)
    route = "/api/monitoring-centre"
    page = client.get(route, params={"domain": "traffic"}).json()
    assert len(page["items"]) == 1
    row = page["items"][0]
    assert row["id"] == saved["id"] and row["href"] == "/road-watch?monitor=" + saved["id"]
    assert row["health"] == "not_started" and row["next_check_at"] is None
    assert row["metrics"] == payload["materiality"]["event_kinds"]
    template = next(t for t in page["templates"] if t["id"] == "traffic")
    assert template["availability"] == "available"
    with TestClient(app) as peer:
        _register(peer, email="road-centre-peer@example.test")
        assert peer.get(route, params={"domain": "traffic"}).json()["items"] == []
        assert peer.get(route, params={"cursor": "traffic:" + saved["id"]}).status_code == 422
    settings.road_watch_enabled = False
    row = client.get(route, params={"domain": "traffic"}).json()["items"][0]
    assert row["href"] is None and row["health"] == "disabled"
