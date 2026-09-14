"""Consented River delivery through real local boundaries; never production mail."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from test_river_watch import config, sample, store
from test_tender_delivery import Mailer
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens import river_delivery as mail
from helvetic_lens import river_email_preferences as preferences
from helvetic_lens import river_runtime as runtime
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.models import Job, OrganizationMembership, User
from helvetic_lens.river_email_models import RiverDelivery
from helvetic_lens.river_models import RiverChange, RiverMonitor, RiverSourceCache

db, template = _database_fixture, _template_fixture
NOW = datetime(2026, 9, 14, 9, tzinfo=UTC)
AT = NOW + timedelta(minutes=10)
SETTINGS = Settings(_env_file=None, river_watch_enabled=True, auth_email_mode="smtp",
    auth_smtp_host="smtp.example.invalid", auth_email_from="monitoring@example.invalid",
    public_base_url="https://example.test")


def observations(db, at, value="2.6", danger="1"):
    with db.session() as session:
        store(session, sample(at, value=value))
        store(session, sample(at, "danger", danger))
        for key in ("2289", "danger"):
            session.get(RiverSourceCache, key).fetched_at = at
        session.commit()


def consent(db, monitor, *, mode="immediate", now=NOW, delivery=None):
    with db.session() as session:
        row = session.get(RiverMonitor, monitor)
        result = preferences.configure(session, "owner", monitor, expected_version=row.version,
            configuration={"delivery": delivery or {"email": mode}}, consent=mode != "off", now=now)
        session.commit()
        return result


def evaluate(db, monitor, at):
    with db.session() as session:
        runtime.evaluate(session, session.get(RiverMonitor, monitor), at)
        session.commit()


def setup(db, *, delivery=None):
    with db.session() as session:
        for key in ("catalog", "2289", "danger"):
            session.add(RiverSourceCache(key=key, data={"stations": [{"id": "2289", "name": "Basel", "waterbody": "Rhine"}]} if key == "catalog" else {},
                fetched_at=NOW, next_fetch_at=AT, failures=0))
        session.get(User, "owner").email_verified_at = NOW
        session.commit()
    observations(db, NOW, "2.4")
    with db.session() as session:
        monitor = runtime.create(session, "owner", config(metrics=["W"]), str(uuid4()))["id"]
        session.commit()
    consent(db, monitor, delivery=delivery)
    with db.session() as session:
        runtime.command(session, "owner", monitor, 2, "start", NOW)
        session.commit()
    evaluate(db, monitor, NOW)
    observations(db, AT)
    evaluate(db, monitor, AT)
    return monitor


def deliver(db, monitor, fake, **kwargs):
    with db.session() as session:
        revision = session.get(RiverMonitor, monitor).email_revision
    return mail.deliver(db, SETTINGS, monitor_id=monitor, consent_revision=revision,
        mailer=fake, now=kwargs.pop("now", AT), **kwargs)


def states(db):
    with db.session() as session:
        return list(session.scalars(select(RiverDelivery.state).order_by(RiverDelivery.created_at)))


def test_crossing_once_private_link_and_no_automatic_review(db):
    monitor = setup(db)
    fake = Mailer()
    with db.session() as session:
        item, = mail.preview(session, SETTINGS, "owner", monitor, now=AT)["items"]
        assert runtime.view(session.get(RiverMonitor, monitor))["email_enabled"]
    assert deliver(db, monitor, fake) == {"status": "sent", "changes": 1}
    assert deliver(db, monitor, fake)["status"] == "no_eligible_changes"
    args, headers = fake.calls[0]
    assert args[0] == "owner@example.test" and item["href"] in args[2]
    assert "2.6" not in args[2] and "Synthetic FOEN" not in args[2]
    assert headers["message_id"].startswith("<river-")
    with db.session() as session:
        assert session.scalar(select(RiverChange)).decision is None
    with db.organization_context("org-b"), db.session() as session:
        assert list(session.scalars(select(RiverDelivery))) == []
        assert mail.deliver(db, SETTINGS, monitor_id=monitor, consent_revision=1, now=AT, mailer=fake)["status"] == "inactive"


@pytest.mark.parametrize("change", ["pause", "archive", "delete", "off", "email", "unverify", "membership", "review", "feature", "correction"])
def test_final_send_boundary(db, change):
    monitor = setup(db)
    fake = Mailer()

    def mutate():
        if change == "off":
            consent(db, monitor, mode="off", now=AT)
        elif change == "feature":
            SETTINGS.river_watch_enabled = False
        elif change == "correction":
            observations(db, AT, "2.0")
        else:
            with db.session() as session:
                row = session.get(RiverMonitor, monitor)
                if change in {"pause", "archive"}:
                    runtime.command(session, "owner", monitor, row.version, change, AT)
                elif change == "delete":
                    runtime.remove(session, "owner", monitor, row.version)
                elif change == "email":
                    session.get(User, "owner").email = "changed@example.test"
                elif change == "unverify":
                    session.get(User, "owner").email_verified_at = None
                elif change == "membership":
                    session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == "owner"))
                elif change == "review":
                    event = session.scalar(select(RiverChange).where(RiverChange.monitor_id == monitor))
                    runtime.review(session, "owner", monitor, event.id, 0, "reviewed")
                session.commit()
    try:
        assert deliver(db, monitor, fake, before_send=mutate)["status"] == "suppressed"
        assert not fake.calls and states(db) == ([] if change == "delete" else ["suppressed"])
    finally:
        SETTINGS.river_watch_enabled = True


def test_correction_at_same_source_clock_creates_reversal_and_suppresses_old_intent(db):
    monitor = setup(db)
    observations(db, AT, "2.0")
    evaluate(db, monitor, AT + timedelta(seconds=1))
    fake = Mailer()
    assert deliver(db, monitor, fake, now=AT + timedelta(seconds=1))["changes"] == 1
    with db.session() as session:
        changes = list(session.scalars(select(RiverChange).order_by(RiverChange.sequence)))
        assert [c.kind for c in changes] == ["threshold_crossed", "threshold_cleared"]
        assert changes[0].development_id == changes[1].development_id
        assert changes[1].evidence["corrected"] and changes[0].evidence["sample"]["value"] == "2.6"
        assert changes[1].id in fake.calls[0][0][2]
    assert states(db) == ["suppressed", "sent"]


def test_private_unverified_invalid_consent_and_no_backfill(db):
    monitor = setup(db)
    with db.session() as session:
        for user in ("peer", "viewer"):
            with pytest.raises(DomainError):
                preferences.view(session, user, monitor)
        session.get(User, "owner").email_verified_at = None
        session.commit()
    for value in (True, 1, "yes", False):
        with db.session() as session, pytest.raises(DomainError):
            preferences.configure(session, "owner", monitor, expected_version=3,
                configuration={"delivery": {"email": "immediate"}}, consent=value, now=AT)
    with db.session() as session:
        session.get(User, "owner").email_verified_at = NOW
        session.commit()
    consent(db, monitor, mode="off", now=AT)
    consent(db, monitor, now=AT + timedelta(seconds=1))
    evaluate(db, monitor, AT + timedelta(seconds=2))
    assert deliver(db, monitor, Mailer(), now=AT + timedelta(seconds=2))["status"] == "no_eligible_changes"


def test_stale_source_defers_then_fresh_projection_recovers(db):
    monitor = setup(db)
    fake = Mailer()
    later = AT + timedelta(minutes=61)
    assert deliver(db, monitor, fake, now=later)["status"] == "no_eligible_changes"
    assert states(db) == ["pending"]
    observations(db, later + timedelta(minutes=1))
    evaluate(db, monitor, later + timedelta(minutes=1))
    assert deliver(db, monitor, fake, now=later + timedelta(minutes=1))["status"] == "sent"


def test_scheduler_cancellation_uncertain_smtp_and_no_retry(db):
    monitor = setup(db)
    assert mail.enqueue_due(db, SETTINGS, now=AT)["enqueued"] == 1
    assert mail.enqueue_due(db, SETTINGS, now=AT)["enqueued"] == 0
    assert deliver(db, monitor, Mailer(fail=True))["status"] == "uncertain"
    consent(db, monitor, mode="off", now=AT)
    consent(db, monitor, now=AT + timedelta(seconds=1))
    fake = Mailer()
    deliver(db, monitor, fake, now=AT + timedelta(seconds=1))
    with db.session() as session:
        job = session.scalar(select(Job).where(Job.type == "river_email"))
        assert job.max_attempts == 1 and job.cancel_requested
        assert preferences.view(session, "owner", monitor)["uncertain_deliveries"] == 1
    assert not fake.calls


def test_daily_and_quiet_hours(db):
    monitor = setup(db, delivery={"email": "daily_digest", "digest_at": "11:10"})
    fake = Mailer()
    assert deliver(db, monitor, fake)["status"] == "sent"
    consent(db, monitor, mode="off", now=AT)
    consent(db, monitor, now=AT, delivery={"email": "daily_digest", "digest_at": "11:10"})
    assert deliver(db, monitor, fake)["status"] == "daily_already_attempted"
    assert len(fake.calls) == 1


def test_quiet_hours_and_abandoned_worker(db):
    monitor = setup(db, delivery={"email": "immediate", "quiet_hours": {"start": "10:00", "end": "11:11"}})
    fake = Mailer()
    assert deliver(db, monitor, fake)["status"] == "no_eligible_changes"

    def crash():
        raise RuntimeError("Synthetic worker exit before SMTP")
    with pytest.raises(RuntimeError):
        deliver(db, monitor, fake, now=AT + timedelta(minutes=1), before_send=crash)
    mail.enqueue_due(db, SETTINGS, now=AT + timedelta(minutes=7))
    assert states(db) == ["uncertain"] and not fake.calls

@pytest.mark.asyncio
async def test_http_settings_exact_link_worker_and_opt_out(tmp_path, monkeypatch):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_auth import _csrf, _register, _settings

    from helvetic_lens import river_api
    from helvetic_lens.auth_mail import AuthMailer
    from helvetic_lens.main import create_app

    settings = _settings(tmp_path, river_watch_enabled=True)
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    at = datetime.now(UTC).replace(second=0, microsecond=0)
    clock = at - timedelta(seconds=1)
    monkeypatch.setattr(river_api, "_now", lambda: clock)
    monkeypatch.setattr(mail, "_now", lambda value=None: value or clock)
    fake = Mailer()
    monkeypatch.setattr(AuthMailer, "send_message", lambda self, *args, **kwargs: fake.send_message(*args, **kwargs))
    with TestClient(app) as client:
        _register(client)
        fake.calls.clear()
        identity = client.get("/api/auth/session").json()
        db = app.state.service.db
        with db.organization_context(identity["organization"]["id"]):
            with db.session() as session:
                for key in ("catalog", "2289", "danger"):
                    session.add(RiverSourceCache(key=key, data={"stations": [{"id": "2289", "name": "Basel"}]} if key == "catalog" else {},
                        fetched_at=at, next_fetch_at=at + timedelta(minutes=10), failures=0))
                session.get(User, identity["user"]["id"]).email_verified_at = clock
                store(session, sample(at, value="2.6"))
                store(session, sample(at, "danger", "1"))
                session.commit()
            saved = client.post("/api/river-watch/monitors", headers=_csrf(client),
                json={"configuration": config(metrics=["W"]), "request_key": str(uuid4())}).json()
            path = "/api/river-watch/monitors/" + saved["id"]
            body = {"expected_version": 1, "configuration": {"delivery": {"email": "immediate"}}, "consent": True}
            assert client.get(path + "/email").headers["cache-control"] == "no-store"
            assert client.put(path + "/email", json=body).status_code == 403
            assert client.put(path + "/email", headers=_csrf(client), json={**body, "recipient_email": "outsider@example.test"}).status_code == 422
            assert client.put(path + "/email", headers=_csrf(client), json={**body, "consent": "true"}).status_code == 422
            assert client.put(path + "/email", headers=_csrf(client), json=body).status_code == 200
            assert client.put(path + "/email", headers=_csrf(client), json=body).status_code == 409
            settings.auth_email_mode, settings.auth_smtp_host, settings.auth_email_from = "smtp", "smtp.example.invalid", "monitoring@example.invalid"
            clock = at
            assert client.post(path + "/command", headers=_csrf(client),
                json={"expected_version": 2, "action": "start"}).status_code == 200
            evaluate(db, saved["id"], at)
            preview = client.get(path + "/email/preview")
            assert preview.headers["cache-control"] == "no-store"
            item, = preview.json()["items"]
            event, = client.get(path + "/changes").json()["items"]
            exact = path + "/changes/" + event["id"]
            assert client.get(exact).json()["event"]["id"] == event["id"]
            assert client.get(exact).headers["cache-control"] == "no-store"
            assert client.get(path + "/changes/" + str(uuid4())).status_code == 404
            assert mail.enqueue_due(db, settings, now=at)["enqueued"] == 1
            with db.session() as session:
                job_id = session.scalar(select(Job.id).where(Job.type == "river_email"))
            result = await app.state.service.execute_job(job_id)
            assert result["state"] == "succeeded", result
            assert len(fake.calls) == 1 and item["href"] in fake.calls[0][0][2]
            assert client.get(exact).json()["event"]["decision"] is None
            observations(db, at, "2.0")
            evaluate(db, saved["id"], at + timedelta(seconds=1))
            assert client.get(exact).json()["newer_available"]
            version = client.get(path).json()["version"]
            off = {"expected_version": version, "configuration": {"delivery": {"email": "off"}}, "consent": False}
            assert not client.put(path + "/email", headers=_csrf(client), json=off).json()["consent_active"]
            assert not client.get(path).json()["email_enabled"]
        client.cookies.clear()
        for endpoint in (exact, path + "/email", path + "/email/preview"):
            assert client.get(endpoint).status_code == 401


def test_migration_roundtrip_preserves_station_measurements_and_private_changes(db):
    from pathlib import Path

    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext

    from alembic import command
    from helvetic_lens.db import Base
    from helvetic_lens.river_models import RiverMeasurement
    monitor = setup(db)
    with db.session() as session:
        change_id = session.scalar(select(RiverChange.id))
        measurement_id = session.scalar(select(RiverMeasurement.id))
    with db.engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"include_object":
            lambda obj, name, kind, reflected, compare_to: name.startswith("river_") if kind == "table" else True})
        assert compare_metadata(context, Base.metadata) == []
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "09e6c78028ab")
        assert connection.execute(select(RiverChange.id).where(RiverChange.id == change_id)).scalar() == change_id
        assert connection.execute(select(RiverMeasurement.id).where(RiverMeasurement.id == measurement_id)).scalar() == measurement_id
        command.upgrade(config, "head")
        assert compare_metadata(context, Base.metadata) == []
        assert connection.execute(select(RiverMonitor.email_revision).where(RiverMonitor.id == monitor)).scalar() == 0


def test_digest_dst_gap_and_repeated_clock():
    from zoneinfo import ZoneInfo
    cfg = preferences.EmailConfiguration(delivery={"email": "daily_digest", "digest_at": "02:30"})
    spring = mail.next_delivery_at(cfg, datetime(2026, 3, 29, 0, tzinfo=UTC))
    assert spring.astimezone(ZoneInfo("Europe/Zurich")).strftime("%H:%M") == "03:00"
    fall = mail.next_delivery_at(cfg, datetime(2026, 10, 25, 0, tzinfo=UTC))
    assert mail.next_delivery_at(cfg, fall + timedelta(minutes=1)).astimezone(ZoneInfo("Europe/Zurich")).day == 26

def test_corrected_rise_baseline_reverses_latest_development_without_new_clock(db):
    monitor = setup(db)
    with db.session() as session:
        row = session.get(RiverMonitor, monitor)
        runtime.command(session, "owner", monitor, row.version, "pause", AT)
        runtime.edit(session, "owner", monitor, row.version, config(metrics=["W"], official_danger=False,
            rules=[{"metric": "W", "kind": "rise", "threshold": "10", "unit": "cm", "window_minutes": 10}]))
        runtime.command(session, "owner", monitor, row.version, "resume", AT)
        session.commit()
    evaluate(db, monitor, AT)
    with db.session() as session:
        store(session, sample(NOW, value="2.55"))
        session.commit()
    evaluate(db, monitor, AT + timedelta(seconds=1))
    evaluate(db, monitor, AT + timedelta(seconds=2))
    with db.session() as session:
        changes = list(session.scalars(select(RiverChange).where(RiverChange.revision == 2).order_by(RiverChange.sequence)))
        assert [change.kind for change in changes] == ["threshold_crossed", "threshold_cleared"]
        assert changes[0].development_id == changes[1].development_id
        assert changes[1].evidence["sample"]["timestamp"] == changes[0].evidence["sample"]["timestamp"]
        assert changes[1].evidence["baseline"]["value"] == "2.55"
        assert changes[0].evidence["baseline"]["value"] == "2.4"
    fake = Mailer()
    assert deliver(db, monitor, fake, now=AT + timedelta(seconds=2))["changes"] == 1
    assert changes[1].id in fake.calls[0][0][2]

