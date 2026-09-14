from uuid import uuid4

import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from test_auction_rules import profile
from test_auth import _csrf, _register, _settings

from helvetic_lens.main import create_app

ROOT = "/api/auction-watch"


def test_native_source_status_is_authenticated_read_only_and_never_starts_collection(api):
    from sqlalchemy import func, select

    from helvetic_lens.aste_models import AsteCollector
    client, app, settings = api
    response = client.get(ROOT + "/source-status")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert response.json() == {"state": "permission_required", "coverage_verified": False, "collection": None}
    settings.aste_source_permission_id = str(uuid4())
    assert client.get(ROOT + "/source-status").json()["state"] == "permission_unavailable"
    with app.state.service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(AsteCollector)) == 0
    assert client.post(ROOT + "/source-status", headers=_csrf(client), json={}).status_code == 405
    client.cookies.clear()
    assert client.get(ROOT + "/source-status").status_code == 401


@pytest.fixture
def api(tmp_path):
    settings = _settings(tmp_path, auction_watch_enabled=True)
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        _register(client)
        yield client, app, settings


def test_http_profile_roundtrip_and_no_forged_source_evidence(api):
    client, _, _ = api
    config = profile().model_dump(mode="json")
    payload = {"configuration": config, "request_key": str(uuid4())}
    assert client.get(ROOT + "/capabilities").json()["start_available"] is False
    assert not client.post(ROOT + "/preview", headers=_csrf(client), json={"configuration": config}).json()["live_results_checked"]
    response = client.post(ROOT + "/monitors", headers=_csrf(client), json=payload)
    assert response.status_code == 201 and response.headers["cache-control"] == "no-store"
    saved, path = response.json(), ROOT + "/monitors/" + response.json()["id"]
    assert client.post(ROOT + "/monitors", headers=_csrf(client), json=payload).json() == saved
    assert client.post(ROOT + "/monitors", headers=_csrf(client), json={**payload, "source_evidence": {"status": "open"}}).status_code == 422
    modified = {**config, "name": "Second profile revision"}
    body = {"configuration": modified, "expected_version": 1}
    assert client.patch(path, headers=_csrf(client), json=body).json()["version"] == 2
    assert client.patch(path, headers=_csrf(client), json=body).status_code == 409
    assert len(client.get(path + "/revisions").json()["items"]) == 2
    assert client.get(path + "/revisions", params={"limit": 101}).status_code == 422
    denied_start = client.post(path + "/start", headers=_csrf(client), json={"expected_version": 2})
    assert denied_start.status_code == 409 and denied_start.json()["code"] == "auction_source_not_configured"
    centre = client.get("/api/monitoring-centre", params={"domain": "auctions"})
    assert centre.status_code == 200, centre.text
    item, = centre.json()["items"]
    assert item["href"] == f"/auction-watch?monitor={saved['id']}"
    assert item["last_check_at"] is None and item["next_check_at"] is None
    assert client.request("DELETE", path, headers=_csrf(client), json={"expected_version": 2}).status_code == 409
    assert client.post(path + "/archive", headers=_csrf(client), json={"expected_version": 2}).json()["status"] == "archived"
    assert client.request("DELETE", path, headers=_csrf(client), json={"expected_version": 3}).json() == {"deleted": True}
    assert client.get(path).status_code == 404


def test_http_csrf_same_organization_peer_and_feature_denial(api):
    from sqlalchemy import select

    from helvetic_lens.auction_models import AuctionMonitor
    from helvetic_lens.models import OrganizationMembership
    client, app, settings = api
    body = {"configuration": profile().model_dump(mode="json"), "request_key": str(uuid4())}
    assert client.post(ROOT + "/monitors", json=body).status_code == 403
    saved = client.post(ROOT + "/monitors", headers=_csrf(client), json=body).json()
    path = ROOT + "/monitors/" + saved["id"]
    with app.state.service.db.session(include_all_organizations=True) as session:
        organization = session.scalar(select(AuctionMonitor.organization_id).where(AuctionMonitor.id == saved["id"]))
    with TestClient(app) as peer:
        identity = _register(peer, email="auction-peer@example.test").json()
        with app.state.service.db.session(include_all_organizations=True) as session:
            session.add(OrganizationMembership(organization_id=organization, user_id=identity["user"]["id"], role="organization_admin"))
            session.commit()
        assert peer.post("/api/auth/session/organization", headers=_csrf(peer), json={"organization_id": organization}).status_code == 200
        for endpoint in (path, path + "/revisions", path + "/email", path + "/email/preview", path + "/reminders"):
            response = peer.get(endpoint)
            assert response.status_code == 404 and response.headers["cache-control"] == "no-store"
        assert peer.get(ROOT + "/monitors").json()["items"] == []
        assert peer.post(path + "/archive", headers=_csrf(peer), json={"expected_version": 1}).status_code == 404
    settings.auction_watch_enabled = False
    denied = client.get(path)
    assert denied.status_code == 404 and denied.headers["cache-control"] == "no-store"
    assert "Vehicle interests" not in denied.text


def test_http_source_backed_follow_review_pause_and_delete(api, monkeypatch):
    from datetime import timedelta

    from sqlalchemy import func, select
    from test_auction_rules import NOW
    from test_auction_sources import accept, grant, price

    from helvetic_lens import auction_api
    from helvetic_lens.auction_workflow_models import AuctionDecision, AuctionItem

    client, app, _ = api
    now = NOW
    monkeypatch.setattr(auction_api, "_now", lambda: now)
    database = app.state.service.db
    permission = grant(database, private_decisions_allowed=True)
    accept(database, permission)
    config = profile().model_dump(mode="json")
    preview = client.post(ROOT + "/preview", headers=_csrf(client), json={"configuration": config}).json()
    assert preview["start_available"] and preview["live_results_checked"] and not preview["coverage_verified"]
    monitor = client.post(ROOT + "/monitors", headers=_csrf(client), json={"configuration": config, "request_key": str(uuid4())}).json()
    path = ROOT + "/monitors/" + monitor["id"]
    assert client.post(path + "/start", json={"expected_version": 1}).status_code == 403
    started = client.post(path + "/start", headers=_csrf(client), json={"expected_version": 1})
    assert started.status_code == 200 and started.json()["status"] == "active"
    assert client.post(path + "/refresh", headers=_csrf(client)).json()["health"] == "current"
    row, = client.get(path + "/items").json()["items"]
    first_feed = client.get(ROOT + "/today")
    assert first_feed.status_code == 200 and first_feed.headers["cache-control"] == "no-store"
    event, = first_feed.json()["items"]
    exact = client.get(path + "/events/" + event["id"])
    assert exact.status_code == 200 and exact.json()["item_id"] == row["id"]
    assert client.get(ROOT + "/today", params={"limit": 51}).status_code == 422
    item_path = path + "/items/" + row["id"]
    followed = client.post(item_path + "/follow", headers=_csrf(client), json={"expected_version": row["version"],
        "expected_state_hash": row["state_hash"], "following": True})
    assert followed.status_code == 200 and followed.json()["following"]
    row = followed.json()
    response = client.post(item_path + "/decision", headers=_csrf(client), json={"expected_version": row["version"],
        "expected_state_hash": row["state_hash"], "decision": "bid"})
    assert response.status_code == 200 and not response.json()["needs_review"]
    assert response.headers["cache-control"] == "no-store"
    assert client.get(ROOT + "/inbox").json()["items"] == []
    assert client.post(item_path + "/bid", headers=_csrf(client), json={"amount": 999999}).status_code == 404
    now = NOW + timedelta(seconds=1)
    accept(database, permission, cursor=1, prices=[price(1270000)])
    assert client.post(path + "/refresh", headers=_csrf(client)).status_code == 200
    row, = client.get(path + "/items", params={"following_only": True}).json()["items"]
    assert row["needs_review"] and row["decision"] == "bid"
    crossing, = client.get(ROOT + "/inbox").json()["items"]
    assert crossing["change_codes"] == ["price_above_limit"]
    assert client.get(path + "/events/" + crossing["id"]).json()["previous"]["facts"]["prices"][0]["amount_minor"] == 850000
    versions = client.get(item_path + "/history", params={"limit": 1}).json()
    assert versions["next_cursor"] and versions["items"][0]["facts"]["prices"][0]["amount_minor"] == 1270000
    centre = client.get("/api/monitoring-centre", params={"domain": "auctions"}).json()["items"][0]
    assert centre["last_check_at"] and centre["next_check_at"] and centre["health"] == "current"
    assert client.post(path + "/pause", headers=_csrf(client), json={"expected_version": 2}).json()["status"] == "paused"
    assert client.post(path + "/refresh", headers=_csrf(client)).status_code == 409
    assert client.post(path + "/archive", headers=_csrf(client), json={"expected_version": 3}).json()["status"] == "archived"
    assert client.request("DELETE", path, headers=_csrf(client), json={"expected_version": 4}).json() == {"deleted": True}
    with database.session(include_all_organizations=True) as session:
        assert session.scalar(select(func.count()).select_from(AuctionItem)) == 0
        assert session.scalar(select(func.count()).select_from(AuctionDecision)) == 0


def test_auction_migration_roundtrip_preserves_other_monitors(api):
    from pathlib import Path

    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from sqlalchemy import select

    from alembic import command
    from helvetic_lens.db import Base
    from helvetic_lens.trademark_models import TrademarkMonitor

    client, app, settings = api
    settings.trademark_watch_enabled = True
    from test_trademark_matching import portfolio
    retained = client.post("/api/trademark-watch/monitors", headers=_csrf(client),
        json={"configuration": portfolio().model_dump(mode="json"), "request_key": str(uuid4())})
    assert retained.status_code == 201
    identifier = retained.json()["id"]
    with app.state.service.db.engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"include_object":
            lambda obj, name, kind, reflected, compare_to: name.startswith("auction_") if kind == "table" else True})
        assert compare_metadata(context, Base.metadata) == []
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "5efb1c69dc50")
        assert connection.execute(select(TrademarkMonitor.id).where(TrademarkMonitor.id == identifier)).scalar() == identifier
        command.upgrade(config, "head")
        assert compare_metadata(context, Base.metadata) == []
