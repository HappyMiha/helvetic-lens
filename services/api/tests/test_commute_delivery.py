from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.config import Config
from sqlalchemy import select
from test_commute_api import api as _http_fixture
from test_commute_jobs import NOW, capture, refresh, scenario, source_grants
from test_commute_repository import create, seeded
from test_tender_delivery import Mailer
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture
from test_transport_feed import alert_feed, feed, trip_feed

from alembic import command
from helvetic_lens import commute_delivery as mail
from helvetic_lens import commute_email_preferences as preferences
from helvetic_lens import commute_events as events
from helvetic_lens import commute_repository as repository
from helvetic_lens import commute_today
from helvetic_lens.commute_models import (
    CommuteDelivery,
    CommuteDevelopment,
    CommuteEmailPolicy,
    CommuteEventVersion,
    CommuteMonitor,
    CommuteSignal,
    CommuteSourcePermission,
)
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.models import Job, OrganizationMembership, User
from helvetic_lens.transport_feed import ALERTS, TRIPS

db, template = _database_fixture, _template_fixture
api = _http_fixture


def prepared(db, *, delivery=None, journey=None, key="save", alerts=None):
    payload = {**seeded(db), **(journey or {})}
    row = create(db, key=key, payload=payload)
    grants = source_grants(db)
    capture(db, grants[TRIPS], trip_feed(delay=600))
    capture(db, grants[ALERTS], feed() if alerts is None else alerts)
    settings = Settings(_env_file=None, commute_watch_enabled=True, commute_source_enabled=True,
                        auth_email_mode="smtp", auth_smtp_host="smtp.example.invalid",
                        auth_email_from="monitoring@example.invalid", public_base_url="https://example.test")
    with db.session() as session:
        session.get(User, "owner").email_verified_at = NOW
        configured = preferences.configure(session, "owner", row["id"], expected_version=row["version"],
            configuration={"delivery": delivery or {"email": "immediate"}}, consent=True, now=NOW)
        row = repository.command(session, "owner", row["id"], configured["monitor_version"], "start", now=NOW, settings=settings)
        session.commit()
    refresh(db, row, settings)
    return row, grants, settings


def deliver(db, row, settings, mailer, **kwargs):
    with db.session() as session:
        revision = session.get(CommuteMonitor, row["id"]).email_revision
    return mail.deliver(db, settings, monitor_id=row["id"], consent_revision=revision, now=kwargs.pop("now", NOW), mailer=mailer, **kwargs)


def test_opt_in_requires_verified_owner_and_never_backfills_or_reviews_today(db):
    row, _, settings = scenario(db)
    refresh(db, row, settings)
    with db.session() as session:
        initial = preferences.view(session, "owner", row["id"])
        assert initial["revision"] == 0 and not initial["consent_active"]
        for user in ("peer", "viewer"):
            with pytest.raises(DomainError):
                preferences.view(session, user, row["id"])
        for consent in (False, "yes", 1):
            with pytest.raises(DomainError):
                preferences.configure(session, "owner", row["id"], expected_version=row["version"],
                    configuration={"delivery": {"email": "immediate"}}, consent=consent, now=NOW)
        with pytest.raises(DomainError):
            preferences.configure(session, "owner", row["id"], expected_version=row["version"],
                configuration={"delivery": {"email": "immediate"}}, consent=True, now=NOW)
        session.get(User, "owner").email_verified_at = NOW
        enabled = preferences.configure(session, "owner", row["id"], expected_version=row["version"],
            configuration={"delivery": {"email": "immediate"}}, consent=True, now=NOW)
        assert enabled["consent_active"] and enabled["revision"] == 1
        assert session.scalars(select(CommuteDelivery)).all() == []
        assert len(commute_today.today(session, settings, "owner", now=NOW)["items"]) == 1
        assert not session.scalar(select(Job).where(Job.type == "commute_refresh")).cancel_requested
        disabled = preferences.configure(session, "owner", row["id"], expected_version=enabled["monitor_version"],
            configuration={"delivery": {"email": "off"}}, consent=False, now=NOW)
        assert not disabled["consent_active"] and disabled["revision"] == 2
        assert session.get(CommuteEmailPolicy, (row["id"], 1)).recipient_email == "owner@example.test"
        assert session.get(CommuteEmailPolicy, (row["id"], 2)).recipient_email is None
        assert len(commute_today.today(session, settings, "owner", now=NOW)["items"]) == 1


def test_exact_intent_sends_once_and_mail_does_not_mark_today_read(db):
    row, _, settings = prepared(db)
    fake = Mailer()
    with db.session() as session:
        preview = mail.preview(session, settings, "owner", row["id"], now=NOW)
        assert len(preview["items"]) == 1
    assert deliver(db, row, settings, fake) == {"status": "sent", "changes": 1}
    assert deliver(db, row, settings, fake)["status"] == "no_eligible_changes"
    assert len(fake.calls) == 1
    args, headers = fake.calls[0]
    assert args[0] == "owner@example.test" and "/commute-watch?monitor=" in args[2] and "sequence=1" in args[2]
    assert headers["message_id"].startswith("<commute-")
    with db.session() as session:
        assert session.scalar(select(CommuteDevelopment)).reviewed_sequence == 0
        assert session.scalar(select(CommuteSignal)).state == "pending"
        assert session.scalar(select(CommuteDelivery)).state == "sent"
        assert len(commute_today.today(session, settings, "owner", now=NOW)["items"]) == 1


@pytest.mark.parametrize("change", ["revoked", "expired", "review", "mute", "pause_today", "pause", "archive", "address",
                                    "unverified", "off", "source_off", "feature_off", "corrupt", "newer", "configuration", "membership"])
def test_claimed_message_rechecks_every_gate_before_smtp(db, change):
    row, grants, settings = prepared(db)
    fake = Mailer()

    def invalidate():
        if change == "newer":
            capture(db, grants[TRIPS], trip_feed(cancelled=True, second=1), second=1)
            refresh(db, row, settings, second=1)
            return
        with db.session() as session:
            event = session.scalar(select(CommuteDevelopment))
            monitor = session.get(CommuteMonitor, row["id"])
            if change in ("revoked", "expired"):
                permission = session.get(CommuteSourcePermission, grants[TRIPS])
                if change == "revoked":
                    permission.revoked_at = NOW
                else:
                    permission.valid_until = NOW
            elif change in ("review", "mute"):
                events.review_event(session, "owner", event.id, event.version, event.sequence, now=NOW,
                    **({"muted": True} if change == "mute" else {}))
            elif change in ("pause_today", "pause", "archive"):
                repository.command(session, "owner", row["id"], monitor.version, change, now=NOW, settings=settings)
            elif change == "address":
                session.get(User, "owner").email = "changed@example.test"
            elif change == "unverified":
                session.get(User, "owner").email_verified_at = None
            elif change == "off":
                preferences.configure(session, "owner", row["id"], expected_version=monitor.version,
                    configuration={"delivery": {"email": "off"}}, consent=False, now=NOW)
            elif change == "source_off":
                settings.commute_source_enabled = False
            elif change == "feature_off":
                settings.commute_watch_enabled = False
            elif change == "corrupt":
                session.scalar(select(CommuteEventVersion)).evidence_hash = "0" * 64
            elif change == "configuration":
                monitor.revision += 1
            elif change == "membership":
                session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == "owner")).role = "viewer"
            session.commit()

    assert deliver(db, row, settings, fake, before_send=invalidate)["status"] == "suppressed"
    assert fake.calls == []


def test_ambiguous_smtp_is_never_retried_as_a_new_message(db):
    row, _, settings = prepared(db)
    fake = Mailer(fail=True)
    assert deliver(db, row, settings, fake)["status"] == "uncertain"
    assert deliver(db, row, settings, fake)["status"] == "no_eligible_changes"
    assert mail.enqueue_due(db, settings, now=NOW)["enqueued"] == 0
    assert len(fake.calls) == 1
    with db.session() as session:
        assert preferences.view(session, "owner", row["id"])["uncertain_deliveries"] == 1


def test_source_signal_is_deduplicated_across_the_same_owners_monitors(db):
    first, _, settings = prepared(db)
    second, _, _ = prepared(db, key="second")
    fake = Mailer()
    assert deliver(db, first, settings, fake)["status"] == "sent"
    assert deliver(db, second, settings, fake)["status"] == "no_eligible_changes"
    assert len(fake.calls) == 1


def test_outside_window_candidates_require_daily_digest_opt_in(db):
    row, _, _ = prepared(db, journey={"window_start": "08:00", "outside_window": "digest"})
    with db.session() as session:
        assert session.scalar(select(CommuteSignal)).delivery_kind == "digest_candidate"
        assert session.scalars(select(CommuteDelivery)).all() == []
    second, _, settings = prepared(db, key="second", journey={"window_start": "08:00", "outside_window": "digest"},
                                  delivery={"email": "daily_digest", "digest_at": "07:30"})
    fake = Mailer()
    assert deliver(db, second, settings, fake)["status"] == "sent"
    assert deliver(db, second, settings, fake)["status"] == "daily_already_attempted"
    assert len(fake.calls) == 1


def test_quiet_hours_defer_and_immediate_stale_events_are_not_live_alerts(db):
    row, _, settings = prepared(db, delivery={"email": "immediate", "quiet_hours": {"start": "07:00", "end": "08:00"}})
    fake = Mailer()
    assert deliver(db, row, settings, fake)["status"] == "no_eligible_changes"
    assert fake.calls == []
    # A still-pending immediate notification is not sent as a live delay after
    # the saved observation has aged out while quiet hours were active.
    assert deliver(db, row, settings, fake, now=NOW + timedelta(minutes=31))["status"] == "no_eligible_changes"
    assert fake.calls == []


def test_scheduler_is_idempotent_claims_one_attempt_and_recovers_abandoned_sends(db):
    row, _, settings = prepared(db)
    assert mail.enqueue_due(db, settings, now=NOW)["enqueued"] == 1
    assert mail.enqueue_due(db, settings, now=NOW + timedelta(minutes=1))["enqueued"] == 0
    with db.session() as session:
        job = session.scalar(select(Job).where(Job.type == "commute_email"))
        assert job.max_attempts == 1 and job.target_id == row["id"] and job.queue == "maintenance"
        intent = session.scalar(select(CommuteDelivery))
        intent.state, intent.claimed_at = "sending", NOW - timedelta(minutes=6)
        session.commit()
    mail.enqueue_due(db, settings, now=NOW)
    with db.session() as session:
        assert session.scalar(select(CommuteDelivery)).state == "uncertain"


@pytest.mark.asyncio
async def test_http_consent_to_durable_dispatch_uses_the_same_fake_mail_boundary(api, monkeypatch):
    from test_auth import _csrf
    from test_commute_api import ROOT
    from test_commute_api import create as create_http

    from helvetic_lens import commute_api
    from helvetic_lens.auth_mail import AuthMailer

    client, app, settings, payload = api
    database = app.state.service.db
    identity = client.get("/api/auth/session").json()
    monkeypatch.setattr(commute_api, "clock", lambda: NOW)
    monkeypatch.setattr(mail, "clock", lambda value=None: NOW if value is None else value)
    fake = Mailer()
    monkeypatch.setattr(AuthMailer, "send_message", lambda self, *args, **kwargs: fake.send_message(*args, **kwargs))
    settings.commute_source_enabled = True
    settings.auth_smtp_host = "smtp.example.invalid"
    settings.auth_email_from = "monitoring@example.invalid"
    settings.auth_email_mode = "smtp"
    grants = source_grants(database)
    capture(database, grants[TRIPS], trip_feed(cancelled=True))
    capture(database, grants[ALERTS], feed())
    row = create_http(client, payload)
    with database.session() as session:
        session.get(User, identity["user"]["id"]).email_verified_at = NOW
        session.commit()
    path = ROOT + f"/monitors/{row['id']}"
    enabled = client.put(path + "/email", json={"expected_version": row["version"],
        "configuration": {"delivery": {"email": "immediate"}}, "consent": True}, headers=_csrf(client))
    assert enabled.status_code == 200, enabled.text
    started = client.post(path + "/commands", json={"expected_version": enabled.json()["monitor_version"],
        "action": "start"}, headers=_csrf(client))
    assert started.status_code == 200, started.text
    with database.organization_context(identity["organization"]["id"]):
        refresh(database, started.json(), settings)
        assert mail.enqueue_due(database, settings, now=NOW)["enqueued"] == 1
        with database.session() as session:
            job = session.scalar(select(Job).where(Job.type == "commute_email"))
            assert job.priority == 9 and job.max_attempts == 1
            job_id = job.id
        result = await app.state.service.execute_job(job_id)
        assert result["state"] == "succeeded", result
        with database.session() as session:
            assert session.scalar(select(CommuteDelivery)).state == "sent"
    assert len(fake.calls) == 1
    assert client.get(ROOT + "/today").json()["items"]


def test_email_policy_and_intent_rows_do_not_cross_workspace_boundaries(db):
    row, _, settings = prepared(db)
    with db.session() as session:
        intent_id = session.scalar(select(CommuteDelivery.id))
    with db.organization_context("org-b"), db.session() as session:
        assert session.get(CommuteDelivery, intent_id) is None
        assert session.get(CommuteEmailPolicy, (row["id"], 1)) is None
        with pytest.raises(DomainError):
            mail.preview(session, settings, "owner", row["id"], now=NOW)
        fake = Mailer()
        assert mail.deliver(db, settings, monitor_id=row["id"], consent_revision=1, now=NOW, mailer=fake)["status"] == "inactive"
        assert fake.calls == []


def test_populated_email_migration_round_trip_preserves_journey_and_accounts(db):
    row, _, _ = prepared(db)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "b8ea0c593cb0")
        command.upgrade(config, "head")
    with db.session() as session:
        monitor = session.get(CommuteMonitor, row["id"])
        assert monitor.configuration == row["configuration"] and monitor.email_revision == 0
        assert session.scalar(select(CommuteDevelopment)) is not None
        assert session.get(User, "owner").email == "owner@example.test"
        assert session.scalars(select(CommuteDelivery)).all() == []
        assert not preferences.view(session, "owner", row["id"])["consent_active"]


@pytest.mark.parametrize("locale", ["en-CH", "de-CH", "fr-CH", "it-CH", "rm-CH"])
def test_mail_copy_is_localized_and_user_names_stay_inert(locale):
    name = '<img src=x onerror="alert(1)">'
    title, text, html = mail.render(SimpleNamespace(public_base_url="https://example.test"),
        SimpleNamespace(locale=locale), SimpleNamespace(id="private-journey", configuration={"name": name}),
        [{"service_day": "2026-09-14", "href": "/commute-watch?monitor=private-journey&event=exact&sequence=2"}])
    assert title == mail.MAIL_COPY[locale.split("-")[0]][0]
    assert "sequence=2" in text and name in text
    assert '<img src=' not in html and "&lt;img" in html and "&amp;sequence=2" in html


def test_durable_cancellation_checkpoint_prevents_a_claimed_send(db):
    row, _, settings = prepared(db)
    checkpoints = iter((True, False))
    fake = Mailer()
    assert deliver(db, row, settings, fake, checkpoint=lambda: next(checkpoints))["status"] == "suppressed"
    assert fake.calls == []


def test_identical_provider_ids_in_different_static_versions_are_not_deduplicated():
    original = {"source": TRIPS, "provider_entity_id": "reused-provider-id", "service_day": "2026-09-14",
                "entity_sha256": "a" * 64, "feed_observed_at": NOW.isoformat(), "static_version": "20260909"}
    assert mail.signal_hash(original) != mail.signal_hash({**original, "static_version": "20260912"})


def test_daily_overflow_is_rescheduled_instead_of_reoccupying_scheduler_pages(db, monkeypatch):
    row, _, settings = prepared(db, delivery={"email": "daily_digest", "digest_at": "07:30"}, alerts=alert_feed())
    with db.session() as session:
        assert len(session.scalars(select(CommuteDelivery)).all()) == 2
    monkeypatch.setattr(mail, "MAX_BATCH", 1)
    fake = Mailer()
    assert deliver(db, row, settings, fake) == {"status": "sent", "changes": 1}
    assert mail.enqueue_due(db, settings, now=NOW)["enqueued"] == 0
    with db.session() as session:
        remaining = session.scalar(select(CommuteDelivery).where(CommuteDelivery.state == "pending"))
        assert mail.utc(remaining.due_at) == NOW + timedelta(days=1)
