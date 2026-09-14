"""Handover through real authentication, CSRF and native access boundaries."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_auth import _csrf, _register
from test_monitoring_configuration_drafts import example
from test_tender_api import api as api

from helvetic_lens.models import OrganizationMembership


@pytest.mark.parametrize("domain,native", (("tenders", "tender"), ("ip", "trademark"), ("auctions", "auction")))
def test_handover_requires_confirmation_csrf_and_owner_then_native_access_follows_successor(api, domain, native):
    client, app, settings, identity = api
    settings.trademark_watch_enabled = settings.auction_watch_enabled = True
    created = client.post(f"/api/{native}-watch/monitors", json={"configuration": example(domain),
        "request_key": str(uuid4())}, headers=_csrf(client))
    assert created.status_code == 201, created.text
    identifier = created.json()["id"]
    path = f"/api/monitoring-centre/business/{domain}/{identifier}"
    native_path = f"/api/{native}-watch/monitors/{identifier}"
    with TestClient(app) as peer:
        assert peer.post(path + "/handover", json={}).status_code == 401
        other = _register(peer, email=f"handover-{domain}@example.test").json()
        with app.state.service.db.session(include_all_organizations=True) as session:
            session.add(OrganizationMembership(organization_id=identity["organization"]["id"],
                user_id=other["user"]["id"], role="organization_admin"))
            session.commit()
        assert peer.post("/api/auth/session/organization", json={"organization_id": identity["organization"]["id"]},
            headers=_csrf(peer)).status_code == 200
        scope = {"expected_version": 1, "visibility": "workspace", "responsible_user_id": None, "confirmed": True}
        shared = client.put(path + "/scope", json=scope, headers=_csrf(client))
        assert shared.status_code == 200, shared.text
        body = {"expected_version": shared.json()["monitor_version"],
            "successor_user_id": other["user"]["id"], "confirmed": True}
        assert client.post(path + "/handover", json=body).status_code == 403
        assert client.post(path + "/handover", json={**body, "confirmed": False}, headers=_csrf(client)).status_code == 422
        assert client.post(path + "/handover", json={**body, "actor_user_id": other["user"]["id"]},
            headers=_csrf(client)).status_code == 422
        assert peer.post(path + "/handover", json={**body, "successor_user_id": identity["user"]["id"]},
            headers=_csrf(peer)).status_code == 403
        transferred = client.post(path + "/handover", json=body, headers=_csrf(client))
        assert transferred.status_code == 200, transferred.text
        assert transferred.headers["cache-control"] == "no-store"
        value = transferred.json()
        assert value["creator"]["id"] == other["user"]["id"]
        assert value["history"][0]["action"] == "handover"
        assert not value["can_change_scope"]
        assert client.post(path + "/handover", json=body, headers=_csrf(client)).status_code == 403
        assert client.get(native_path).status_code == 200
        assert client.get(native_path + "/email").status_code == 404
        assert peer.get(native_path + "/email").status_code == 200
        private = peer.put(path + "/scope", json={**scope, "expected_version": value["monitor_version"],
            "visibility": "private"}, headers=_csrf(peer))
        assert private.status_code == 200, private.text
        assert client.get(native_path).status_code == 404
        assert peer.get(native_path).status_code == 200
