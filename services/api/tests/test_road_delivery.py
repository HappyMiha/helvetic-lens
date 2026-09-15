from datetime import timedelta

import pytest
from sqlalchemy import select
from test_road_jobs import NOW, accept, current, feed, record, refresh, setup
from test_tender_delivery import Mailer
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens import road_delivery as mail
from helvetic_lens import road_email_preferences as preferences
from helvetic_lens import road_events as events
from helvetic_lens import road_repository as repository
from helvetic_lens import road_today
from helvetic_lens.config import DomainError
from helvetic_lens.models import Job, OrganizationMembership, User
from helvetic_lens.road_models import (
    RoadDelivery,
    RoadDevelopment,
    RoadEmailPolicy,
    RoadEventVersion,
    RoadMonitor,
    RoadSourceHead,
    RoadSourcePermission,
    RoadTopologyRevision,
)

db, template = _database_fixture, _template_fixture


def opt_in(db, row, *, delivery=None, now=NOW, user_id="owner"):
    with db.session() as session:
        session.get(User, user_id).email_verified_at = NOW
        saved = preferences.configure(session, user_id, row["id"], expected_version=row["version"],
            configuration={"delivery": delivery or {"email": "immediate"}}, consent=True, now=now)
        row = repository.get_monitor(session, user_id, row["id"])
        assert row["version"] == saved["monitor_version"]
        session.commit()
        return row


def prepared(db, *, delivery=None, notifications=True, topology_notifications=None):
    row, permission, topo, settings = setup(db, notifications=notifications, topology_notifications=topology_notifications)
    settings.auth_email_mode = "smtp"
    settings.auth_smtp_host = "smtp.example.invalid"
    settings.auth_email_from = "monitoring@example.invalid"
    settings.public_base_url = "https://example.test"
    row = opt_in(db, row, delivery=delivery)
    assert refresh(db, row, settings)["changed"] == 1
    return row, permission, topo, settings


def deliver(db, row, settings, fake, **kwargs):
    with db.session() as session:
        revision = session.get(RoadMonitor, row["id"]).email_revision
    return mail.deliver(db, settings, monitor_id=row["id"], consent_revision=revision,
        now=kwargs.pop("now", NOW), mailer=fake, **kwargs)


def test_opt_in_requires_verified_owner_and_never_backfills_today(db):
    row, _, _, settings = setup(db, notifications=True)
    refresh(db, row, settings)
    with db.session() as session:
        assert preferences.view(session, "owner", row["id"])["revision"] == 0
        for actor in ("peer", "viewer"):
            with pytest.raises(DomainError):
                preferences.view(session, actor, row["id"])
        for consent in (False, "yes", 1, True):
            with pytest.raises(DomainError):
                preferences.configure(session, "owner", row["id"], expected_version=row["version"],
                    configuration={"delivery": {"email": "immediate"}}, consent=consent, now=NOW)
    row = opt_in(db, row)
    with db.session() as session:
        assert session.scalars(select(RoadDelivery)).all() == []
        assert road_today.today(session, settings, "owner", now=NOW)["items"]
        assert not session.scalar(select(Job).where(Job.type == "road_refresh")).cancel_requested
        off = preferences.configure(session, "owner", row["id"], expected_version=row["version"],
            configuration={"delivery": {"email": "off"}}, consent=False, now=NOW)
        assert off["revision"] == 2 and not off["consent_active"]
        assert session.get(RoadEmailPolicy, (row["id"], 2)).recipient_email is None


def test_exact_intent_sends_once_without_reviewing_or_exporting_source_facts(db):
    row, _, _, settings = prepared(db)
    fake = Mailer()
    with db.session() as session:
        assert len(mail.preview(session, settings, "owner", row["id"], now=NOW)["items"]) == 1
    assert deliver(db, row, settings, fake) == {"status": "sent", "changes": 1}
    assert deliver(db, row, settings, fake)["status"] == "no_eligible_changes"
    assert len(fake.calls) == 1
    args, headers = fake.calls[0]
    assert args[0] == "owner@example.test" and "/road-watch?monitor=" in args[2] and "sequence=1" in args[2]
    assert headers["message_id"].startswith("<road-")
    assert "test-supplier" not in str(args) and "Synthetic northbound" not in str(args)
    with db.session() as session:
        assert session.scalar(select(RoadDevelopment)).reviewed_sequence == 0
        assert session.scalar(select(RoadDelivery)).state == "sent"
        assert len(road_today.today(session, settings, "owner", now=NOW)["items"]) == 1


@pytest.mark.parametrize("change", ["source_revoked", "topology_revoked", "expired", "review", "mute",
    "pause", "archive", "address", "unverified", "off", "source_off", "feature_off", "corrupt",
    "newer", "source_advanced", "configuration", "membership", "source_selected", "mapping_changed"])
def test_claim_rechecks_source_topology_consent_and_state_before_smtp(db, change):
    row, permission, topo, settings = prepared(db)
    fake = Mailer()

    def invalidate():
        if change == "newer":
            accept(db, permission, feed(record(code="laneClosures")), minute=1, expected_generation=2)
            refresh(db, row, settings, minute=1)
            return
        with db.session() as session:
            event = session.scalar(select(RoadDevelopment))
            monitor = session.get(RoadMonitor, row["id"])
            if change == "source_revoked":
                session.get(RoadSourcePermission, permission).revoked_at = NOW
            elif change == "topology_revoked":
                session.get(RoadTopologyRevision, topo).revoked_at = NOW
            elif change == "mapping_changed":
                from helvetic_lens.road_catalog import publish_mapping
                from helvetic_lens.road_models import RoadCorridorReference
                from helvetic_lens.road_topology import CorridorFlow
                reference = session.get(RoadCorridorReference, monitor.configuration["corridor_reference_ids"][0])
                publish_mapping(session, reference.id, topology_id=topo,
                    flow=CorridorFlow(key="north", points=(120, 110, 100)), expected_generation=reference.generation,
                    review_reference="corrected synthetic mapping", now=NOW)
            elif change == "expired":
                session.get(RoadSourcePermission, permission).valid_until = NOW
            elif change in ("review", "mute"):
                events.review_event(session, "owner", event.id, expected_version=event.version, sequence=event.sequence,
                    **({"muted": True} if change == "mute" else {}))
            elif change in ("pause", "archive"):
                repository.command(session, "owner", row["id"], monitor.version, change, now=NOW, settings=settings)
            elif change == "address":
                session.get(User, "owner").email = "changed@example.test"
            elif change == "unverified":
                session.get(User, "owner").email_verified_at = None
            elif change == "off":
                preferences.configure(session, "owner", row["id"], expected_version=monitor.version,
                    configuration={"delivery": {"email": "off"}}, consent=False, now=NOW)
            elif change == "source_off":
                settings.road_source_enabled = False
            elif change == "feature_off":
                settings.road_watch_enabled = False
            elif change == "source_selected":
                settings.road_source_permission_id = "different-permission"
            elif change == "corrupt":
                session.scalar(select(RoadEventVersion)).proof_hash = "0" * 64
            elif change == "source_advanced":
                session.scalar(select(RoadSourceHead)).generation += 1
            elif change == "configuration":
                monitor.revision += 1
            elif change == "membership":
                session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == "owner")).role = "viewer"
            session.commit()

    assert deliver(db, row, settings, fake, before_send=invalidate)["status"] == "suppressed"
    assert not fake.calls


@pytest.mark.parametrize("source,topology", [(False, True), (True, False)])
def test_notification_rights_are_separate_from_display_and_source_processing(db, source, topology):
    row, _, _, settings = prepared(db, notifications=source, topology_notifications=topology)
    assert current(db, row)["payload"] is not None
    with db.session() as session:
        assert session.scalars(select(RoadDelivery)).all() == []
    fake = Mailer()
    assert deliver(db, row, settings, fake)["status"] == "no_eligible_changes"
    assert not fake.calls


@pytest.mark.parametrize("minute", [0, 1])
@pytest.mark.parametrize("second_owner", ["owner", "peer"])
def test_same_source_change_is_deduplicated_only_for_the_same_owner(db, minute, second_owner):
    first, permission, _, settings = prepared(db)
    fake = Mailer()
    assert deliver(db, first, settings, fake)["status"] == "sent"
    if minute:
        accept(db, permission, minute=minute, expected_generation=2)
    with db.session() as session:
        second = repository.create_monitor(session, second_owner, first["configuration"], "second")
        session.commit()
    second = opt_in(db, second, now=NOW + timedelta(minutes=minute), user_id=second_owner)
    with db.session() as session:
        second = repository.command(session, second_owner, second["id"], second["version"], "start",
                                    now=NOW + timedelta(minutes=minute), settings=settings)
        session.commit()
    refresh(db, second, settings, minute=minute)
    assert deliver(db, second, settings, fake, now=NOW + timedelta(minutes=minute))["status"] == (
        "no_eligible_changes" if second_owner == "owner" else "sent")
    assert len(fake.calls) == (1 if second_owner == "owner" else 2)


def test_daily_digest_is_once_per_local_day_and_keeps_new_material_change_unread(db):
    row, permission, _, settings = prepared(db, delivery={"email": "daily_digest", "digest_at": "12:00"})
    fake = Mailer()
    assert deliver(db, row, settings, fake)["status"] == "sent"
    accept(db, permission, feed(record(code="laneClosures")), minute=1, expected_generation=2)
    refresh(db, row, settings, minute=1)
    assert deliver(db, row, settings, fake, now=NOW + timedelta(minutes=1))["status"] == "daily_already_attempted"
    assert len(fake.calls) == 1
    with db.session() as session:
        event = session.scalar(select(RoadDevelopment))
        assert event.sequence == 2 and event.reviewed_sequence == 0


def test_cancelled_claim_and_console_mode_never_send(db):
    row, _, _, settings = prepared(db)
    fake = Mailer()
    calls = iter([True, False])
    assert deliver(db, row, settings, fake, checkpoint=lambda: next(calls))["status"] == "suppressed"
    assert not fake.calls
    settings.auth_email_mode = "console"
    assert mail.deliver(db, settings, monitor_id=row["id"], consent_revision=1, now=NOW)["status"] == "mail_not_live"


def test_consent_conflict_and_lifecycle_cancel_pending_without_review(db):
    row, _, _, settings = prepared(db)
    with db.session() as session:
        with pytest.raises(DomainError):
            preferences.configure(session, "owner", row["id"], expected_version=row["version"] - 1,
                configuration={"delivery": {"email": "off"}}, consent=False, now=NOW)
        repository.command(session, "owner", row["id"], row["version"], "pause", settings=settings, now=NOW)
        assert session.scalar(select(RoadDelivery)).state == "suppressed"
        assert session.scalar(select(RoadDevelopment)).reviewed_sequence == 0


@pytest.mark.asyncio
async def test_http_consent_and_durable_job_dispatch_use_fake_smtp(tmp_path, monkeypatch):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_auth import _csrf, _register, _settings

    from helvetic_lens import road_api
    from helvetic_lens.auth_mail import AuthMailer
    from helvetic_lens.main import create_app

    settings = _settings(tmp_path, road_watch_enabled=True)
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    monkeypatch.setattr(road_api, "clock", lambda: NOW)
    monkeypatch.setattr(mail, "clock", lambda value=None: NOW if value is None else value)
    fake = Mailer()
    monkeypatch.setattr(AuthMailer, "send_message", lambda self, *args, **kwargs: fake.send_message(*args, **kwargs))
    with TestClient(app) as client:
        _register(client)
        fake.calls.clear()  # Registration verification is outside road delivery.
        identity = client.get("/api/auth/session").json()
        database = app.state.service.db
        with database.organization_context(identity["organization"]["id"]):
            row, permission, _, _ = setup(database, user_id=identity["user"]["id"], notifications=True)
        settings.road_source_enabled, settings.road_source_permission_id = True, permission
        with database.session() as session:
            session.get(User, identity["user"]["id"]).email_verified_at = NOW
            session.commit()
        path = f"/api/road-watch/monitors/{row['id']}"
        assert client.get(path + "/email").headers["cache-control"] == "no-store"
        body = {"expected_version": row["version"], "configuration": {"delivery": {"email": "immediate"}}, "consent": True}
        assert client.put(path + "/email", json=body).status_code == 403
        saved = client.put(path + "/email", json=body, headers=_csrf(client))
        assert saved.status_code == 200, saved.text
        assert client.put(path + "/email", json=body, headers=_csrf(client)).status_code == 409
        row["version"] = saved.json()["monitor_version"]
        settings.auth_email_mode, settings.auth_smtp_host = "smtp", "smtp.example.invalid"
        settings.auth_email_from = "monitoring@example.invalid"
        with database.organization_context(identity["organization"]["id"]):
            refresh(database, row, settings)
            inbox_response = client.get("/api/road-watch/inbox")
            assert inbox_response.status_code == 200 and inbox_response.headers["cache-control"] == "no-store"
            inbox_item, = inbox_response.json()["items"]
            assert inbox_item["priority"] == "urgent" and inbox_response.json()["source_available"]
            assert client.get("/api/road-watch/inbox?limit=51").status_code == 422
            assert client.get(path + "/email-preview").json()["items"]
            assert mail.enqueue_due(database, settings, now=NOW)["enqueued"] == 1
            with database.session() as session:
                job = session.scalar(select(Job).where(Job.type == "road_email"))
                assert job.max_attempts == 1 and job.priority == 9
                job_id = job.id
            result = await app.state.service.execute_job(job_id)
            assert result["state"] == "succeeded", result
            with database.session() as session:
                assert session.scalar(select(RoadDelivery)).state == "sent"
            marked = client.post(f"/api/road-watch/events/{inbox_item['event_id']}/review", headers=_csrf(client),
                json={"expected_version": inbox_item["event"]["version"], "sequence": inbox_item["sequence"]})
            assert marked.status_code == 200, marked.text
            assert client.get("/api/road-watch/inbox").json()["items"] == []
            assert client.get("/api/road-watch/today").json()["items"] == []
        assert len(fake.calls) == 1
        client.cookies.clear()
        assert client.get("/api/road-watch/inbox").status_code == 401


def test_ambiguous_smtp_is_never_retried(db):
    row, _, _, settings = prepared(db)
    fake = Mailer(fail=True)
    assert deliver(db, row, settings, fake)["status"] == "uncertain"
    assert deliver(db, row, settings, fake)["status"] == "no_eligible_changes"
    assert mail.enqueue_due(db, settings, now=NOW)["enqueued"] == 0
    assert len(fake.calls) == 1
    with db.session() as session:
        assert preferences.view(session, "owner", row["id"])["uncertain_deliveries"] == 1


def test_scheduler_claims_one_attempt_and_recovers_abandoned_sends(db):
    row, _, _, settings = prepared(db)
    assert mail.enqueue_due(db, settings, now=NOW)["enqueued"] == 1
    assert mail.enqueue_due(db, settings, now=NOW)["enqueued"] == 0
    with db.session() as session:
        job = session.scalar(select(Job).where(Job.type == "road_email"))
        assert job.max_attempts == 1 and job.target_id == row["id"] and job.queue == "monitoring_delivery"
        intent = session.scalar(select(RoadDelivery))
        intent.state, intent.claimed_at = "sending", NOW - timedelta(minutes=6)
        session.commit()
    mail.enqueue_due(db, settings, now=NOW)
    with db.session() as session:
        assert session.scalar(select(RoadDelivery)).state == "uncertain"


def test_policy_and_intent_rows_are_tenant_scoped(db):
    row, _, _, settings = prepared(db)
    with db.session() as session:
        intent_id = session.scalar(select(RoadDelivery.id))
    with db.organization_context("org-b"), db.session() as session:
        assert session.get(RoadDelivery, intent_id) is None
        assert session.get(RoadEmailPolicy, (row["id"], 1)) is None
        fake = Mailer()
        assert mail.deliver(db, settings, monitor_id=row["id"], consent_revision=1, now=NOW, mailer=fake)["status"] == "inactive"
        assert not fake.calls


def test_quiet_hours_never_override_source_freshness(db):
    local_hour = (NOW.hour + 2) % 24
    row, _, _, settings = prepared(db, delivery={"email": "immediate", "quiet_hours": {
        "start": f"{local_hour:02d}:00", "end": f"{(local_hour + 1) % 24:02d}:00"}})
    fake = Mailer()
    assert deliver(db, row, settings, fake)["status"] == "no_eligible_changes"
    assert deliver(db, row, settings, fake, now=NOW + timedelta(hours=1))["status"] == "no_eligible_changes"
    assert not fake.calls
