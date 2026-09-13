from uuid import uuid4

import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from test_auth import _csrf, _register, _settings
from test_hazard_repository import CONFIG

from helvetic_lens.main import create_app

ROOT = "/api/hazard-watch"


@pytest.fixture
def api(tmp_path):
    settings = _settings(tmp_path, hazard_watch_enabled=True)
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        _register(client)
        yield client, app, settings


def save(client):
    body = {"configuration": CONFIG, "request_key": str(uuid4())}
    response = client.post(ROOT + "/monitors", headers=_csrf(client), json=body)
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    assert client.post(ROOT + "/monitors", headers=_csrf(client), json=body).json() == response.json()
    return response.json()


def test_http_email_consent_csrf_owner_and_recipient_binding(api):
    from sqlalchemy import select

    from helvetic_lens.hazard_models import HazardMonitor
    from helvetic_lens.models import User
    client, app, settings = api
    saved = save(client)
    path = ROOT + "/monitors/" + saved["id"]
    response = client.get(path + "/email")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert response.json()["configuration"]["delivery"]["email"] == "off"
    body = {"expected_version": 1, "configuration": {"delivery": {"email": "immediate"}}, "consent": True}
    assert client.put(path + "/email", json=body).status_code == 403
    with app.state.service.db.session(include_all_organizations=True) as session:
        monitor = session.scalar(select(HazardMonitor).where(HazardMonitor.id == saved["id"]))
        user = session.get(User, monitor.owner_user_id)
        from helvetic_lens.db import utcnow
        user.email_verified_at = utcnow()
        session.commit()
    assert client.put(path + "/email", headers=_csrf(client), json={**body, "recipient_email": "other@example.test"}).status_code == 422
    assert client.put(path + "/email", headers=_csrf(client), json={**body, "consent": 1}).status_code == 422
    enabled = client.put(path + "/email", headers=_csrf(client), json=body)
    assert enabled.status_code == 200 and enabled.json()["consent_active"]
    assert client.get(path).json()["status"] == "draft"
    assert client.get(path + "/email-preview").json()["status"] == "unavailable"
    with TestClient(app) as peer:
        _register(peer, email="hazard-mail-peer@example.test")
        for suffix in ("/email", "/email-preview"):
            assert peer.get(path + suffix).status_code == 404
        assert peer.put(path + "/email", headers=_csrf(peer), json={**body, "expected_version": 2}).status_code == 404
    disabled = client.put(path + "/email", headers=_csrf(client), json={"expected_version": 2,
        "configuration": {"delivery": {"email": "off"}}, "consent": False})
    assert disabled.status_code == 200 and not disabled.json()["consent_active"]


def test_http_location_preview_save_edit_history_archive_delete(api):
    client, _, _ = api
    assert client.get(ROOT + "/capabilities").json()["start_available"] is False
    preview = client.post(ROOT + "/preview", headers=_csrf(client), json={"configuration": CONFIG})
    assert preview.status_code == 200 and preview.json()["draft_available"]
    saved = save(client)
    path = ROOT + "/monitors/" + saved["id"]
    assert client.get(path).json() == saved
    assert client.get(ROOT + "/monitors").json()["items"] == [saved]
    body = {"expected_version": 1, "configuration": {**CONFIG, "name": "Office"}}
    edited = client.patch(path, headers=_csrf(client), json=body)
    assert edited.status_code == 200 and edited.json()["revision"] == 2
    assert client.patch(path, headers=_csrf(client), json=body).status_code == 409
    revisions = client.get(path + "/revisions", params={"limit": 1}).json()
    assert revisions["items"][0]["configuration"]["name"] == "Office"
    assert client.get(path + "/revisions", params={"before": revisions["next_cursor"]}).json()["items"][0]["configuration"]["name"] == "Home"
    assert client.request("DELETE", path, headers=_csrf(client), json={"expected_version": 2}).status_code == 409
    assert client.post(path + "/archive", headers=_csrf(client), json={"expected_version": 2}).json()["status"] == "archived"
    assert client.request("DELETE", path, headers=_csrf(client), json={"expected_version": 3}).json() == {"deleted": True}
    assert client.get(path).status_code == 404


def test_http_denials_csrf_foreign_owner_and_disabled_feature_do_not_cache_private_data(api):
    client, app, settings = api
    saved = save(client)
    path = ROOT + "/monitors/" + saved["id"]
    denied = client.patch(path, json={"expected_version": 1, "configuration": CONFIG})
    assert denied.status_code == 403 and denied.headers["cache-control"] == "no-store"
    with TestClient(app) as peer:
        denied = peer.get(path)
        assert denied.status_code == 401 and denied.headers["cache-control"] == "no-store"
        _register(peer, email="hazard-peer@example.test")
        for suffix in ("", "/revisions"):
            denied = peer.get(path + suffix)
            assert denied.status_code == 404 and denied.headers["cache-control"] == "no-store"
            assert "47.56" not in denied.text
        assert peer.get(ROOT + "/monitors", params={"after_id": saved["id"]}).status_code == 404
        assert peer.post(path + "/archive", headers=_csrf(peer), json={"expected_version": 1}).status_code == 404
    settings.hazard_watch_enabled = False
    for route in (path, ROOT + "/capabilities", ROOT + "/monitors"):
        denied = client.get(route)
        assert denied.status_code == 404 and denied.headers["cache-control"] == "no-store"


def test_http_cannot_forge_location_verification_source_grant_or_owner_and_does_not_echo_private_input(api):
    client, _, _ = api
    for extra in ({"owner_user_id": "other"}, {"source_approved": True}, {"email_consent": True}):
        response = client.post(ROOT + "/monitors", headers=_csrf(client),
            json={"configuration": {**CONFIG, **extra}, "request_key": str(uuid4())})
        assert response.status_code == 422 and response.headers["cache-control"] == "no-store"
        assert "47.56" not in response.text
    invalid = {**CONFIG, "location": {**CONFIG["location"], "latitude": "PRIVATE_LOCATION_VALUE"}}
    response = client.post(ROOT + "/preview", headers=_csrf(client), json={"configuration": invalid})
    assert response.status_code == 422
    assert "PRIVATE_LOCATION_VALUE" not in response.text
    assert client.get(ROOT + "/monitors").json()["items"] == []
    assert client.get(ROOT + "/monitors", params={"limit": 101}).status_code == 422


def test_monitoring_centre_has_private_warning_drafts_without_coordinate_export_or_live_claim(api):
    client, app, settings = api
    saved = save(client)
    result = client.get("/api/monitoring-centre", params={"domain": "warnings"})
    assert result.status_code == 200
    page = result.json()
    assert len(page["templates"]) == 9
    assert next(t for t in page["templates"] if t["id"] == "warnings")["availability"] == "available"
    row = page["items"][0]
    assert row["id"] == saved["id"] and row["health"] == "not_started"
    assert row["href"] == "/hazard-watch?monitor=" + saved["id"]
    assert row["last_check_at"] is None and row["next_check_at"] is None
    assert "47.56" not in result.text and "latitude" not in result.text
    with TestClient(app) as peer:
        _register(peer, email="hazard-inventory-peer@example.test")
        assert peer.get("/api/monitoring-centre", params={"domain": "warnings"}).json()["items"] == []
        assert peer.get("/api/monitoring-centre", params={"cursor": "warnings:" + saved["id"]}).status_code == 422
    settings.hazard_watch_enabled = False
    row = client.get("/api/monitoring-centre", params={"domain": "warnings"}).json()["items"][0]
    assert row["href"] is None and row["health"] == "disabled"


def test_private_preview_uses_installed_catalogue_without_starting_or_accepting_client_proof(api):
    from datetime import UTC, datetime, timedelta

    from test_hazard_boundary_store import archive

    from helvetic_lens.hazard_boundary_store import install_catalogue

    client, _, settings = api
    path, checksum = archive(settings.storage_path)
    install_catalogue(settings.storage_path, path, archive_sha256=checksum, version="2026-01",
                      expires_on=datetime.now(UTC).date() + timedelta(days=1))
    config = {**CONFIG, "location": {"kind": "municipality", "country": "CH", "canton": "BE", "municipality_code": "1"}}
    response = client.post(ROOT + "/preview", headers=_csrf(client), json={"configuration": config})
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    proof = response.json()
    assert proof["geography"]["state"] == "verified"
    assert proof["geography"]["municipality_name"] == "Synthetic municipality"
    assert proof["blocking_reasons"] == ["hazard_source_not_configured"]
    assert proof["start_available"] is False and proof["live_results_checked"] is False
    assert client.get(ROOT + "/monitors").json()["items"] == []
    assert "storage" not in response.text and "gpkg" not in response.text
    config["location"]["canton"] = "JU"
    mismatch = client.post(ROOT + "/preview", headers=_csrf(client), json={"configuration": config}).json()
    assert mismatch["geography"]["reason"] == "municipality_canton_mismatch"
    assert "hazard_location_not_verified" in mismatch["blocking_reasons"]
    forged = client.post(ROOT + "/preview", headers=_csrf(client), json={"configuration": config, "geography": {"state": "verified"}})
    assert forged.status_code == 422


def test_private_warning_event_api_exact_reader_review_history_and_denial(api, monkeypatch):
    from sqlalchemy import select
    from test_hazard_cap import NOW
    from test_hazard_events import GeometryFixture
    from test_hazard_sources import accept, grant

    from helvetic_lens import hazard_api, hazard_events
    from helvetic_lens.hazard_boundary_store import BoundaryStore
    from helvetic_lens.hazard_models import HazardMonitor

    client, app, settings = api
    geometry = GeometryFixture()
    monkeypatch.setattr(hazard_api, "utcnow", lambda: NOW)
    monkeypatch.setattr(BoundaryStore, "verify_location", lambda self, location, **kwargs: geometry.verify_location(location, **kwargs))
    monkeypatch.setattr(BoundaryStore, "match_warning", lambda self, areas, location, **kwargs: geometry.match_warning(areas, location, **kwargs))
    saved = save(client)
    database = app.state.service.db
    permission = grant(database, private_decisions_allowed=True)
    receipt = accept(database, permission)
    with database.session(include_all_organizations=True) as session:
        organization_id = session.scalar(select(HazardMonitor.organization_id).where(HazardMonitor.id == saved["id"]))
    with database.session() as session:
        session.info["organization_id"] = organization_id
        monitor = session.scalar(select(HazardMonitor).where(HazardMonitor.id == saved["id"]))
        # Synthetic active fixture only; API capabilities still refuse start.
        monitor.status, monitor.version = "active", 2
        session.flush()
        projected = hazard_events.project_message(session, monitor.owner_user_id, monitor.id, permission,
            receipt["evidence_id"], monitor_version=2, source_generation=1, source_cursor=1, store=geometry, now=NOW)
        session.commit()
    path = ROOT + "/monitors/" + saved["id"] + "/events"
    reader = path + "/" + projected["development_id"]
    listing = client.get(path)
    assert listing.status_code == 200 and listing.headers["cache-control"] == "no-store"
    assert listing.json()["items"][0]["state"] == "active" and not listing.json()["coverage_verified"]
    detail = client.get(reader)
    for suffix in ("/today", "/inbox"):
        summary = client.get(ROOT + suffix)
        assert summary.status_code == 200 and summary.headers["cache-control"] == "no-store"
        assert summary.json()["items"][0]["href"] == reader.replace("/api/hazard-watch/monitors/", "/hazard-watch?monitor=").replace("/events/", "&event=") + "&revision=1"
        assert "Stay indoors" not in summary.text and "latitude" not in summary.text
        assert client.get(ROOT + suffix, params={"limit": 21}).status_code == 422
    assert detail.json()["source"]["message"]["infos"][0]["instruction"] == "Stay indoors."
    body = {"expected_version": detail.json()["version"], "expected_revision": detail.json()["revision"], "action": "reviewed"}
    assert client.post(reader + "/review", json=body).status_code == 403
    reviewed = client.post(reader + "/review", json=body, headers=_csrf(client))
    assert reviewed.status_code == 200 and reviewed.json()["reviewed"]
    assert client.get(ROOT + "/today").json()["items"] == []
    assert client.get(ROOT + "/inbox").json()["items"] == []
    audit = client.get(reader + "/reviews")
    assert audit.json()["items"][0]["action"] == "reviewed" and audit.json()["items"][0]["revision"] == 1
    assert client.post(reader + "/review", json=body, headers=_csrf(client)).status_code == 409
    assert client.get(reader + "/history").json()["items"][0]["revision"] == 1
    assert client.get(reader, params={"revision": 1}).json()["historical"]
    assert client.get(path, params={"limit": 21}).status_code == 422
    mute_path = ROOT + "/monitors/" + saved["id"] + "/mutes"
    assert client.get(mute_path).json()["muted_hazards"] == []
    mute_body = {"expected_version": 2, "muted": True}
    assert client.patch(mute_path + "/storm", json=mute_body).status_code == 403
    muted = client.patch(mute_path + "/storm", json=mute_body, headers=_csrf(client))
    assert muted.status_code == 200 and muted.json()["muted_hazards"] == ["storm"]
    assert client.get(reader).json()["muted"]
    with TestClient(app) as peer:
        assert peer.get(reader).status_code == 401
        assert peer.get(ROOT + "/today").status_code == 401
        _register(peer, email="hazard-event-peer@example.test")
        assert peer.get(ROOT + "/today").json()["items"] == []
        for route in (path, reader, reader + "/history", reader + "/reviews", mute_path):
            denied = peer.get(route)
            assert denied.status_code == 404 and denied.headers["cache-control"] == "no-store"
            assert "Stay indoors" not in denied.text
        assert peer.post(reader + "/review", json=body, headers=_csrf(peer)).status_code == 404
    geometry.available = False
    hidden = client.get(reader)
    assert hidden.json()["state"] == "unavailable" and "source" not in hidden.json()
    settings.hazard_watch_enabled = False
    assert client.get(reader).status_code == 404
    assert client.get(ROOT + "/today").status_code == 404
    assert client.get(ROOT + "/inbox").status_code == 404


async def test_http_lifecycle_readiness_job_ownership_and_stop_after_source_loss(api, monkeypatch):
    from sqlalchemy import select
    from test_hazard_cap import NOW
    from test_hazard_lifecycle import ScopeFixture, complete_poll, coverage
    from test_hazard_sources import accept, grant, policy

    from helvetic_lens import hazard_api, hazard_jobs
    from helvetic_lens.hazard_boundary_store import BoundaryStore
    from helvetic_lens.hazard_models import HazardMonitor
    from helvetic_lens.hazard_sources import HazardRule
    from helvetic_lens.models import OrganizationMembership

    client, app, settings = api
    geometry = ScopeFixture()
    monkeypatch.setattr(hazard_api, "utcnow", lambda: NOW)
    monkeypatch.setattr(hazard_jobs, "clock", lambda: NOW)
    monkeypatch.setattr(BoundaryStore, "verify_location", lambda self, location, **kw: geometry.verify_location(location, **kw))
    monkeypatch.setattr(BoundaryStore, "verify_source_scope", lambda self, location, cantons, **kw: geometry.verify_source_scope(location, cantons, **kw))
    monkeypatch.setattr(BoundaryStore, "match_warning", lambda self, areas, location, **kw: geometry.match_warning(areas, location, **kw))
    saved = save(client)
    path = ROOT + "/monitors/" + saved["id"]
    assert not client.get(path + "/readiness").json()["start_available"]
    body = {"expected_version": 1, "action": "start"}
    assert client.post(path + "/commands", json=body, headers=_csrf(client)).status_code == 409
    assert client.get(path + "/actions").json()["items"] == []
    database = app.state.service.db
    permission = grant(database, private_decisions_allowed=True,
        rules=(*policy().rules, HazardRule(hazard="flood", value_name="fixture", value="flood")),
        coverage=(coverage(), coverage("flood")))
    accept(database, permission)
    complete_poll(database, permission, cursor=1)
    settings.hazard_source_enabled, settings.hazard_source_permission_id = True, permission
    ready = client.get(path + "/readiness")
    assert ready.json()["start_available"] and ready.headers["cache-control"] == "no-store"
    assert client.post(path + "/commands", json=body).status_code == 403
    started = client.post(path + "/commands", json=body, headers=_csrf(client))
    assert started.status_code == 200 and started.json()["status"] == "active"
    job, = [job for job in client.get("/api/jobs").json() if job["target_type"] == "hazard_monitor"]
    assert client.get("/api/jobs/" + job["id"]).status_code == 200
    with database.session(include_all_organizations=True) as session:
        organization = session.scalar(select(HazardMonitor.organization_id).where(HazardMonitor.id == saved["id"]))
    with database.organization_context(organization):
        assert all(row["target_type"] != "hazard_monitor" for row in app.state.service.jobs())
    with TestClient(app) as peer:
        identity = _register(peer, email="hazard-lifecycle-peer@example.test").json()
        with database.session(include_all_organizations=True) as session:
            session.add(OrganizationMembership(organization_id=organization, user_id=identity["user"]["id"], role="organization_admin"))
            session.commit()
        assert peer.post("/api/auth/session/organization", headers=_csrf(peer), json={"organization_id": organization}).status_code == 200
        assert not [row for row in peer.get("/api/jobs").json() if row["target_type"] == "hazard_monitor"]
        for suffix in ("/readiness", "/actions"):
            assert peer.get(path + suffix).status_code == 404
        assert peer.get("/api/jobs/" + job["id"]).status_code == 404
        assert peer.post("/api/jobs/" + job["id"] + "/cancel", headers=_csrf(peer)).status_code == 404
    with database.organization_context(organization):
        processed = await app.state.service.execute_job(job["id"])
    assert processed["state"] == "succeeded", processed
    assert len(client.get(ROOT + "/today").json()["items"]) == 1
    centre = client.get("/api/monitoring-centre", params={"domain": "warnings"}).json()["items"][0]
    assert centre["last_check_at"] and centre["next_check_at"] and centre["health"] == "ready"
    settings.hazard_source_enabled = False
    geometry.available = False
    paused = client.post(path + "/commands", json={"expected_version": 2, "action": "pause"}, headers=_csrf(client))
    assert paused.status_code == 200 and paused.json()["status"] == "paused"
    # Completed jobs remain history; stopping does not rewrite their outcome.
    assert client.get("/api/jobs/" + job["id"]).json()["state"] == "succeeded"
    assert client.post(path + "/commands", json={"expected_version": 3, "action": "resume"}, headers=_csrf(client)).status_code == 409
    archived = client.post(path + "/commands", json={"expected_version": 3, "action": "archive"}, headers=_csrf(client))
    assert archived.status_code == 200
    audit = client.get(path + "/actions").json()
    assert [row["action"] for row in audit["items"]] == ["archive", "pause", "start"]
    assert "proof" not in str(audit) and "latitude" not in str(audit)


async def test_http_consent_to_durable_worker_fake_smtp_and_exact_reader(api, monkeypatch):
    from sqlalchemy import select
    from test_hazard_cap import NOW
    from test_hazard_delivery import Mailer
    from test_hazard_lifecycle import ScopeFixture, complete_poll, coverage
    from test_hazard_sources import accept, grant, policy

    from helvetic_lens import hazard_api, hazard_delivery, hazard_jobs
    from helvetic_lens.hazard_boundary_store import BoundaryStore
    from helvetic_lens.hazard_models import HazardDelivery, HazardMonitor
    from helvetic_lens.hazard_sources import HazardRule
    from helvetic_lens.models import User
    client, app, settings = api
    geometry, fake = ScopeFixture(), Mailer()
    monkeypatch.setattr(hazard_api, "utcnow", lambda: NOW)
    monkeypatch.setattr(hazard_jobs, "clock", lambda: NOW)
    monkeypatch.setattr(hazard_delivery, "clock", lambda value=None: value or NOW)
    monkeypatch.setattr(hazard_delivery, "AuthMailer", lambda settings: fake)
    monkeypatch.setattr(BoundaryStore, "verify_location", lambda self, location, **kw: geometry.verify_location(location, **kw))
    monkeypatch.setattr(BoundaryStore, "verify_source_scope", lambda self, location, cantons, **kw: geometry.verify_source_scope(location, cantons, **kw))
    monkeypatch.setattr(BoundaryStore, "match_warning", lambda self, areas, location, **kw: geometry.match_warning(areas, location, **kw))
    saved = save(client)
    path = ROOT + "/monitors/" + saved["id"]
    database = app.state.service.db
    with database.session(include_all_organizations=True) as session:
        monitor = session.get(HazardMonitor, saved["id"])
        organization = monitor.organization_id
        session.get(User, monitor.owner_user_id).email_verified_at = NOW
        session.commit()
    permission = grant(database, private_decisions_allowed=True, notifications_allowed=True,
        rules=(*policy().rules, HazardRule(hazard="flood", value_name="fixture", value="flood")),
        coverage=(coverage(), coverage("flood")))
    accept(database, permission)
    complete_poll(database, permission, cursor=1)
    settings.hazard_source_enabled, settings.hazard_source_permission_id = True, permission
    settings.auth_email_mode = "smtp"
    email = client.put(path + "/email", headers=_csrf(client), json={"expected_version": 1,
        "configuration": {"delivery": {"email": "immediate"}}, "consent": True})
    assert email.status_code == 200
    assert client.post(path + "/commands", headers=_csrf(client), json={"expected_version": 2, "action": "start"}).status_code == 200
    refresh, = [row for row in client.get("/api/jobs").json() if row["type"] == "hazard_refresh"]
    with database.organization_context(organization):
        assert (await app.state.service.execute_job(refresh["id"]))["state"] == "succeeded"
    preview = client.get(path + "/email-preview").json()
    assert len(preview["items"]) == 1
    assert hazard_delivery.enqueue_due(database, settings, now=NOW)["enqueued"] == 1
    job, = [row for row in client.get("/api/jobs").json() if row["type"] == "hazard_email"]
    with database.organization_context(organization):
        sent = await app.state.service.execute_job(job["id"])
        assert sent["state"] == "succeeded" and sent["result"]["data"]["status"] == "sent"
        with database.session() as session:
            assert session.scalar(select(HazardDelivery)).state == "sent"
    assert len(fake.calls) == 1 and preview["items"][0]["href"] in fake.calls[0][0][2]
    event = preview["items"][0]["event_id"]
    assert client.get(path + "/events/" + event).json()["needs_review"]
    assert len(client.get(ROOT + "/today").json()["items"]) == 1
