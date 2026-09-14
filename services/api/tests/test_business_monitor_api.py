"""Authenticated three-domain sharing, native readers, CSRF and revocation."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, update
from test_auction_rules import profile as auction_profile
from test_auth import _csrf, _register
from test_tender_api import api as api
from test_tender_matching import profile as tender_profile
from test_trademark_matching import portfolio

from helvetic_lens import jobs
from helvetic_lens.models import OrganizationMembership

ROOT = "/api/monitoring-centre/business"


@pytest.mark.parametrize("domain,native,factory", (
    ("tenders", "tender-watch", tender_profile), ("ip", "trademark-watch", portfolio),
    ("auctions", "auction-watch", auction_profile),
))
def test_http_sharing_native_readers_assignment_private_email_and_revocation(api, domain, native, factory):
    client, app, settings, identity = api
    settings.trademark_watch_enabled = settings.auction_watch_enabled = True
    database = app.state.service.db
    configuration = factory().model_dump(mode="json")
    created = client.post(f"/api/{native}/monitors", json={"configuration": configuration,
        "request_key": str(uuid4())}, headers=_csrf(client))
    assert created.status_code == 201, created.text
    monitor = created.json()
    native_path = f"/api/{native}/monitors/{monitor['id']}"
    scope_path = f"{ROOT}/{domain}/{monitor['id']}/scope"
    assert monitor["visibility"] == "private" and monitor["owner_user_id"] == identity["user"]["id"]
    with TestClient(app) as peer:
        assert peer.get(scope_path).status_code == 401
        other = _register(peer, email=f"{domain}-peer@example.test").json()
        assert peer.get(scope_path).status_code == 404
        with database.session(include_all_organizations=True) as session:
            session.add(OrganizationMembership(organization_id=identity["organization"]["id"],
                user_id=other["user"]["id"], role="organization_admin"))
            session.commit()
        switched = peer.post("/api/auth/session/organization", json={"organization_id": identity["organization"]["id"]}, headers=_csrf(peer))
        assert switched.status_code == 200
        assert peer.get(scope_path).status_code == 404
        body = {"expected_version": 1, "visibility": "workspace", "responsible_user_id": other["user"]["id"], "confirmed": True}
        assert client.put(scope_path, json=body).status_code == 403
        assert client.put(scope_path, json={**body, "actor_user_id": other["user"]["id"]}, headers=_csrf(client)).status_code == 422
        assert client.put(scope_path, json={**body, "confirmed": False}, headers=_csrf(client)).status_code == 422
        shared = client.put(scope_path, json=body, headers=_csrf(client))
        assert shared.status_code == 200, shared.text
        assert shared.headers["cache-control"] == "no-store"
        assert shared.json()["responsible"]["id"] == other["user"]["id"]
        assert client.put(scope_path, json=body, headers=_csrf(client)).status_code == 409
        assert peer.get(native_path).status_code == 200
        assert len(peer.get(f"/api/{native}/monitors").json()["items"]) == 1
        assert peer.get(native_path + "/email").status_code == 404
        with database.organization_context(identity["organization"]["id"]), database.session() as session:
            prefix = native.removesuffix("-watch")
            private_job, _ = jobs.enqueue(session, job_type=prefix + "_email", target_type=prefix + "_monitor",
                target_id=monitor["id"], queue="maintenance", idempotency_key="scope-private-email")
            collection_job, _ = jobs.enqueue(session, job_type=prefix + "_refresh", target_type=prefix + "_monitor",
                target_id=monitor["id"], queue="maintenance", idempotency_key="scope-collection")
            private_id, collection_id = private_job.id, collection_job.id
            session.commit()
        assert client.get(f"/api/jobs/{private_id}").status_code == 200
        assert peer.get(f"/api/jobs/{private_id}").status_code == 404
        assert peer.post(f"/api/jobs/{private_id}/cancel", headers=_csrf(peer)).status_code == 404
        assert peer.get(f"/api/jobs/{collection_id}").status_code == 200
        peer_jobs = {row["id"] for row in peer.get("/api/jobs").json()}
        assert collection_id in peer_jobs and private_id not in peer_jobs

        assert len(peer.get(f"/api/monitoring-centre?domain={domain}").json()["items"]) == 1
        assert peer.get(f"/api/monitoring-centre?domain={domain}&personal_only=true").json()["items"] == []
        directory = peer.get(ROOT + "/members?limit=1").json()
        assert len(directory["items"]) == 1 and set(directory["items"][0]) == {"id", "name"}
        assert "email" not in str(directory)
        reassigned = peer.put(scope_path, json={**body, "expected_version": 2,
            "responsible_user_id": identity["user"]["id"]}, headers=_csrf(peer))
        assert reassigned.status_code == 200 and reassigned.json()["monitor_version"] == 3
        history = peer.get(scope_path + "?limit=1").json()
        assert history["history"][0]["actor"]["id"] == other["user"]["id"]
        assert len(peer.get(scope_path + f"?before_version={history['next_before_version']}").json()["history"]) == 1
        with database.session(include_all_organizations=True) as session:
            session.execute(update(OrganizationMembership).where(OrganizationMembership.organization_id == identity["organization"]["id"],
                OrganizationMembership.user_id == other["user"]["id"]).values(role="viewer"))
            session.commit()
        assert peer.get(scope_path).status_code == 200 and peer.get(native_path).status_code == 200
        denied = peer.put(scope_path, json={**body, "expected_version": 3}, headers=_csrf(peer))
        assert denied.status_code == 403 and denied.headers["cache-control"] == "no-store"
        assert peer.get(ROOT + "/members").status_code == 403
        withdrawn = client.put(scope_path, json={**body, "expected_version": 3, "visibility": "private", "responsible_user_id": None}, headers=_csrf(client))
        assert withdrawn.status_code == 200
        assert peer.get(scope_path).status_code == 404 and peer.get(native_path).status_code == 404
        assert peer.get(f"/api/{native}/monitors").json()["items"] == []
        with database.session(include_all_organizations=True) as session:
            session.execute(delete(OrganizationMembership).where(OrganizationMembership.organization_id == identity["organization"]["id"],
                OrganizationMembership.user_id == other["user"]["id"]))
            session.commit()
        assert peer.get(scope_path).status_code in {401, 403}
    assert client.get(f"{ROOT}/customs/{monitor['id']}/scope").status_code == 422
