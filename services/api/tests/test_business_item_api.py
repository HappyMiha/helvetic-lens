"""Session/CSRF/tenant/native source checks for all three item work commands."""

from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from test_auth import _csrf, _register
from test_tender_api import api as api

from helvetic_lens.models import OrganizationMembership

ROOT = "/api/monitoring-centre/business"


def seed(api, domain, monkeypatch):
    client, app, settings, identity = api
    settings.trademark_watch_enabled = settings.auction_watch_enabled = True
    db, user = app.state.service.db, identity["user"]["id"]
    if domain == "tenders":
        from test_tender_api import create, ingest, transition
        from test_tender_matching import NOW
        from test_tender_repository import publication
        row = transition(client, create(client), "start")
        item = ingest(app, identity, row, publication())[0]
        monitor, version = row["id"], row["version"]
    else:
        if domain == "ip":
            from test_trademark_matching import portfolio as factory
            from test_trademark_sources import NOW, accept, grant

            from helvetic_lens import trademark_workflow as workflow
            native, listing = "trademark-watch", workflow.list_candidates
        else:
            from test_auction_rules import NOW
            from test_auction_rules import profile as factory
            from test_auction_sources import accept, grant

            from helvetic_lens import auction_workflow as workflow
            native, listing = "auction-watch", workflow.list_items
        created = client.post(f"/api/{native}/monitors", json={
            "configuration": factory().model_dump(mode="json"), "request_key": str(uuid4())}, headers=_csrf(client))
        assert created.status_code == 201, created.text
        monitor = created.json()["id"]
        with db.organization_context(identity["organization"]["id"]):
            permission = grant(db, private_decisions_allowed=True)
            accept(db, permission)
            with db.session() as session:
                workflow.start(session, user, monitor, 1, now=NOW)
                workflow.refresh(session, user, monitor, now=NOW)
                item = listing(session, user, monitor, now=NOW)["items"][0]["id"]
                session.commit()
        version = 2

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)

    from helvetic_lens import business_monitor_api
    monkeypatch.setattr(business_monitor_api, "datetime", Clock)
    return monitor, item, version


@pytest.mark.parametrize("domain", ("tenders", "ip", "auctions"))
def test_http_work_native_decisions_csrf_private_shared_viewer_and_withdrawal(api, domain, monkeypatch):
    client, app, _, identity = api
    monitor, item, monitor_version = seed(api, domain, monkeypatch)
    path = f"{ROOT}/{domain}/{monitor}/items/{item}/work"
    initial = client.get(path)
    assert initial.status_code == 200, initial.text
    assert initial.headers["cache-control"] == "no-store"
    assert initial.json()["state"] == "available"
    body = {"expected_version": initial.json()["version"], "expected_binding": initial.json()["binding"],
        "assigned_user_id": identity["user"]["id"], "comment": "Internal assessment only",
        "decision": {"tenders": "bid", "ip": "counsel", "auctions": "inspect"}[domain]}
    assert client.post(path, json=body).status_code == 403
    assert client.post(path, json={**body, "actor_user_id": str(uuid4())}, headers=_csrf(client)).status_code == 422
    assert client.post(path, json={**body, "comment": "x" * 4001}, headers=_csrf(client)).status_code == 422
    assert client.post(path, json={**body, "expected_version": True}, headers=_csrf(client)).status_code == 422
    assert client.get(path + "?limit=51").status_code == 422
    result = client.post(path, json=body, headers=_csrf(client))
    assert result.status_code == 200, result.text
    assert result.json()["history"][0]["decision"] == body["decision"]
    assert result.json()["history"][0]["comment"] == body["comment"]
    assert result.json()["history"][0]["actor"]["id"] == identity["user"]["id"]
    assert client.post(path, json=body, headers=_csrf(client)).status_code == 409
    with TestClient(app) as peer:
        assert peer.get(path).status_code == 401
        other = _register(peer, email=f"item-{domain}@example.test").json()
        assert peer.get(path).status_code == 404
        db = app.state.service.db
        with db.session(include_all_organizations=True) as session:
            session.add(OrganizationMembership(organization_id=identity["organization"]["id"],
                user_id=other["user"]["id"], role="organization_admin"))
            session.commit()
        assert peer.post("/api/auth/session/organization", json={"organization_id": identity["organization"]["id"]}, headers=_csrf(peer)).status_code == 200
        assert peer.get(path).status_code == 404
        scope_path = f"{ROOT}/{domain}/{monitor}/scope"
        scope_body = {"expected_version": monitor_version, "visibility": "workspace", "responsible_user_id": other["user"]["id"], "confirmed": True}
        shared = client.put(scope_path, json=scope_body, headers=_csrf(client))
        assert shared.status_code == 200, shared.text
        visible = peer.get(path)
        assert visible.json()["history"][0]["comment"] == body["comment"]
        note = {**body, "expected_version": result.json()["version"], "decision": None,
            "assigned_user_id": other["user"]["id"], "comment": "Take responsibility"}
        changed = peer.post(path, json=note, headers=_csrf(peer))
        assert changed.status_code == 200, changed.text
        assert changed.json()["assigned"]["id"] == other["user"]["id"]
        assert not changed.json()["needs_review"]
        with db.session(include_all_organizations=True) as session:
            session.execute(update(OrganizationMembership).where(
                OrganizationMembership.organization_id == identity["organization"]["id"],
                OrganizationMembership.user_id == other["user"]["id"]).values(role="viewer"))
            session.commit()
        assert peer.get(path).json()["can_write"] is False
        forbidden = peer.post(path, json={**note, "expected_version": changed.json()["version"]}, headers=_csrf(peer))
        assert forbidden.status_code == 403 and forbidden.headers["cache-control"] == "no-store"
        withdrawn = client.put(scope_path, json={**scope_body, "expected_version": shared.json()["monitor_version"],
            "visibility": "private", "responsible_user_id": None}, headers=_csrf(client))
        assert withdrawn.status_code == 200
        assert peer.get(path).status_code == 404
        assert client.get(path).json()["history"][0]["comment"] == "Take responsibility"
