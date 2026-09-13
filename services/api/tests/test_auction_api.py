from uuid import uuid4

import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from test_auction_rules import profile
from test_auth import _csrf, _register, _settings

from helvetic_lens.main import create_app

ROOT = "/api/auction-watch"


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
    assert client.post(path + "/start", headers=_csrf(client), json={"expected_version": 2}).status_code == 404
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
        for endpoint in (path, path + "/revisions"):
            response = peer.get(endpoint)
            assert response.status_code == 404 and response.headers["cache-control"] == "no-store"
        assert peer.get(ROOT + "/monitors").json()["items"] == []
        assert peer.post(path + "/archive", headers=_csrf(peer), json={"expected_version": 1}).status_code == 404
    settings.auction_watch_enabled = False
    denied = client.get(path)
    assert denied.status_code == 404 and denied.headers["cache-control"] == "no-store"
    assert "Vehicle interests" not in denied.text


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
