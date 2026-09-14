"""Real authenticated HTTP workflow, domain readers and private persistence."""
from uuid import uuid4

import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from test_auth import _csrf, _register, _settings
from test_related_readers import NOW, Boundaries, seed_sources

from helvetic_lens import related_api
from helvetic_lens.main import create_app

ROOT = "/api/related-developments"


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(related_api, "clock", lambda: NOW)
    monkeypatch.setattr(related_api, "BoundaryStore", lambda path: Boundaries())
    settings = _settings(tmp_path, hazard_watch_enabled=True, hazard_source_enabled=True, river_watch_enabled=True,
        road_watch_enabled=True, road_source_enabled=True)
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        identity = _register(client).json()
        database = app.state.service.db
        with database.organization_context(identity["organization"]["id"]):
            seed_sources(database, identity["user"]["id"])
        yield client, app, settings


def post(client, path, data):
    return client.post(ROOT + path, headers=_csrf(client), json=data)


def prepared(client):
    members = []
    for domain in ("warnings", "river", "traffic"):
        page = client.get(ROOT + "/candidates", params={"domain": domain})
        assert page.status_code == 200, page.text
        reference = page.json()["items"][0]["reference"]
        assert "geographic_evidence" not in page.text
        inspect = post(client, "/bindings/inspect", {"reference": reference})
        assert inspect.status_code == 200, inspect.text
        proof = inspect.json()
        assert proof["fact"]["geographic_evidence"]
        result = post(client, "/bindings", {"id": str(uuid4()), "reference": reference,
            "municipality_code": "2701", "boundary_version": "2026-01", "boundary_hash": "a" * 64,
            "evidence_hash": "b" * 64, "source_revision": proof["fact"]["source_revision"],
            "source_feature_hash": proof["source_feature_hash"], "valid_until": "2026-09-14T00:00:00+00:00", "reviewed": True})
        assert result.status_code == 201, result.text
        members.append(reference)
    return members


def test_three_source_create_split_rejoin_history_archive_with_no_review_transfer(api):
    client, _, _ = api
    members = prepared(client)
    preview = post(client, "/preview", {"members": members})
    assert preview.status_code == 200 and preview.json()["can_save"], preview.text
    data = {"title": "Private local story", "members": members, "request_key": str(uuid4())}
    result = post(client, "/stories", data)
    assert result.status_code == 201, result.text
    saved = result.json()
    assert post(client, "/stories", data).json() == saved
    path = "/stories/" + saved["id"]
    for version, values in ((1, members[:2]), (2, members)):
        changed = post(client, path, {"title": saved["title"], "members": values, "expected_version": version,
            "request_key": str(uuid4()), "action": "revise"})
        assert changed.status_code == 200, changed.text
        assert len(changed.json()["members"]) == len(values)
    history = client.get(ROOT + path + "/history").json()["items"]
    assert [item["action"] for item in history] == ["merge", "split", "create"]
    historical = client.get(ROOT + path, params={"revision": 2}).json()
    assert historical["historical"] and len(historical["members"]) == 2
    archived = post(client, path, {"expected_version": 3, "action": "archive", "request_key": str(uuid4())})
    assert archived.status_code == 200, archived.text
    assert client.get(ROOT + "/stories").json()["items"] == []
    assert client.get(ROOT + "/stories", params={"archived": True}).json()["items"][0]["id"] == saved["id"]
    assert post(client, path, {"expected_version": 4, "action": "restore", "request_key": str(uuid4())}).status_code == 200
    assert not any(m["reviewed"] for m in client.get(ROOT + path).json()["members"])


def test_auth_csrf_foreign_history_cursors_and_input_failures_are_no_store(api):
    client, app, settings = api
    members = prepared(client)
    body = {"title": "Private local story", "members": members, "request_key": str(uuid4())}
    saved = post(client, "/stories", body).json()
    path = "/stories/" + saved["id"]
    denied = client.post(ROOT + "/stories", json=body)
    assert denied.status_code == 403 and denied.headers["cache-control"] == "no-store"
    for invalid in ({**body, "members": members[:1]}, {**body, "source_ready": True},
                    {**body, "members": [{**members[0], "revision": True}, members[1]]}):
        rejected = post(client, "/stories", invalid)
        assert rejected.status_code == 422 and rejected.headers["cache-control"] == "no-store"
    with TestClient(app) as peer:
        assert peer.get(ROOT + path).status_code == 401
        _register(peer, email="related-peer@example.test")
        for suffix in (path, path + "/history", "/stories?after=" + saved["id"]):
            result = peer.get(ROOT + suffix)
            assert result.status_code == 404 and saved["title"] not in result.text
            assert result.headers["cache-control"] == "no-store"
        assert post(peer, "/bindings/inspect", {"reference": members[0]}).status_code == 403
    settings.road_source_enabled = False
    detail = client.get(ROOT + path)
    assert detail.json()["association_state"] == "unverified"
    assert client.get(ROOT + "/capabilities").json()["available"]
