"""Private Air digests with actual source versions and stateful numeric rules."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from test_air_watch import configuration, feed, source_rows
from test_tender_delivery import Mailer
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens import air_delivery as mail
from helvetic_lens import air_email_preferences as preferences
from helvetic_lens import air_runtime as runtime
from helvetic_lens.air_email_models import AirDelivery
from helvetic_lens.air_models import AirChange, AirMonitor, AirSourceCache
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.models import Job, OrganizationMembership, User

db, template = _database_fixture, _template_fixture
NOW = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
AT = NOW + timedelta(hours=1)
SETTINGS = Settings(_env_file=None, air_watch_enabled=True, auth_email_mode="smtp",
    auth_smtp_host="smtp.example.invalid", auth_email_from="monitoring@example.invalid",
    public_base_url="https://example.test")


def consent(db, monitor, *, mode="immediate", now=NOW, delivery=None):
    with db.session() as session:
        row = session.get(AirMonitor, monitor)
        result = preferences.configure(session, "owner", monitor, expected_version=row.version,
            configuration={"delivery": delivery or {"email": mode}}, consent=mode != "off", now=now)
        session.commit()
        return result


def evaluate(db, monitor, at):
    with db.session() as session:
        runtime.evaluate(session, session.get(AirMonitor, monitor), at)
        session.commit()


def setup(db, *, period="hourly_mean", delivery=None):
    feed(db, NOW, source_rows(NOW, 40))
    with db.session() as session:
        session.get(User, "owner").email_verified_at = NOW
        config = configuration()
        config["rules"][0]["period"] = period
        monitor = runtime.create(session, "owner", config, str(uuid4()))["id"]
        session.commit()
    consent(db, monitor, delivery=delivery)
    with db.session() as session:
        runtime.command(session, "owner", monitor, 2, "start", NOW)
        session.commit()
    evaluate(db, monitor, NOW)
    feed(db, AT, source_rows(AT, 60))
    evaluate(db, monitor, AT)
    return monitor


def deliver(db, monitor, fake, **kwargs):
    with db.session() as session:
        revision = session.get(AirMonitor, monitor).email_revision
    return mail.deliver(db, SETTINGS, monitor_id=monitor, consent_revision=revision,
        mailer=fake, now=kwargs.pop("now", AT), **kwargs)


def test_current_private_link_once_without_measurements_or_automatic_review(db):
    monitor = setup(db)
    fake = Mailer()
    with db.session() as session:
        item, = mail.preview(session, SETTINGS, "owner", monitor, now=AT)["items"]
        assert runtime.view(session.get(AirMonitor, monitor))["email_enabled"]
    assert deliver(db, monitor, fake) == {"status": "sent", "changes": 1}
    assert deliver(db, monitor, fake)["status"] == "no_eligible_changes"
    args, headers = fake.calls[0]
    assert args[0] == "owner@example.test" and item["href"] in args[2]
    assert "µg" not in args[2] and "O3" not in args[2]
    assert headers["message_id"].startswith("<air-")
    with db.session() as session:
        assert session.scalar(select(AirChange)).decision is None
    with db.organization_context("org-b"), db.session() as session:
        assert list(session.scalars(select(AirDelivery))) == []
        with pytest.raises(DomainError):
            preferences.view(session, "other", monitor)


@pytest.mark.parametrize("change", ["pause", "archive", "delete", "off", "email", "unverify",
    "membership", "review", "feature", "mute", "withdraw", "correct", "catalog"])
def test_final_send_rechecks_private_access_and_current_air_evidence(db, change):
    monitor = setup(db)
    fake = Mailer()

    def mutate():
        if change == "off":
            consent(db, monitor, mode="off", now=AT)
        elif change in {"withdraw", "correct"}:
            rows = source_rows(AT, 40 if change == "correct" else 60)
            if change == "withdraw":
                rows[0]["o3_ug_m3"] = None
            feed(db, AT, rows)
        else:
            with db.session() as session:
                row = session.get(AirMonitor, monitor)
                if change in {"pause", "archive"}:
                    runtime.command(session, "owner", monitor, row.version, change, AT)
                elif change == "delete":
                    runtime.remove(session, "owner", monitor, row.version)
                elif change == "mute":
                    runtime.mute(session, "owner", monitor, row.version, "O3", True, AT)
                elif change == "email":
                    session.get(User, "owner").email = "changed@example.test"
                elif change == "unverify":
                    session.get(User, "owner").email_verified_at = None
                elif change == "membership":
                    session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == "owner"))
                elif change == "review":
                    session.scalar(select(AirChange)).decision = "reviewed"
                elif change == "catalog":
                    session.get(AirSourceCache, "catalog").error = "source_unavailable"
                session.commit()

    settings = SETTINGS.model_copy(update={"air_watch_enabled": change != "feature"})
    result = mail.deliver(db, settings, monitor_id=monitor, consent_revision=1, now=AT,
        mailer=fake, before_send=mutate)
    assert result["status"] != "sent" and not fake.calls


@pytest.mark.parametrize("period", ["hourly_mean", "rolling_24h_mean"])
def test_corrected_inputs_wait_for_projection_and_send_only_latest_development(db, period):
    monitor = setup(db, period=period)
    with db.session() as session:
        original = session.scalar(select(AirChange))
        original_id, development = original.id, original.development_id
        original_sample = original.evidence["sample"]
    # All values are corrected at the existing clocks, including the 24h window.
    feed(db, AT, source_rows(AT, 40))
    fake = Mailer()
    assert deliver(db, monitor, fake)["status"] == "no_eligible_changes"
    evaluate(db, monitor, AT + timedelta(minutes=1))
    evaluate(db, monitor, AT + timedelta(minutes=2))
    with db.session() as session:
        changes = list(session.scalars(select(AirChange).order_by(AirChange.sequence)))
        assert len(changes) == 2 and changes[-1].kind == "threshold_cleared"
        assert changes[-1].development_id == development and changes[-1].evidence["corrected"]
        assert session.get(AirChange, original_id).evidence["sample"] == original_sample
        latest_id = changes[-1].id
    assert deliver(db, monitor, fake, now=AT + timedelta(minutes=2))["status"] == "sent"
    assert latest_id in fake.calls[0][0][2] and original_id not in fake.calls[0][0][2]


def test_hysteresis_band_keeps_reported_state(db):
    monitor = setup(db)
    feed(db, AT, source_rows(AT, 48))  # Below 50 but above hysteresis recovery at 45.
    evaluate(db, monitor, AT + timedelta(minutes=1))
    with db.session() as session:
        assert len(list(session.scalars(select(AirChange)))) == 1
    assert deliver(db, monitor, Mailer(), now=AT + timedelta(minutes=1))["status"] == "sent"


def test_missing_24h_input_defers_even_with_current_latest_hour(db):
    monitor = setup(db, period="rolling_24h_mean")
    rows = source_rows(AT, 60)
    rows[12]["o3_ug_m3"] = None
    feed(db, AT, rows)
    fake = Mailer()
    assert deliver(db, monitor, fake)["status"] == "no_eligible_changes" and not fake.calls


def test_correction_to_older_mean_inputs_reverses_without_new_latest_reading(db):
    monitor = setup(db, period="rolling_24h_mean")
    with db.session() as session:
        original = session.scalar(select(AirChange))
        sample = original.evidence["sample"]
        original_id = original.id
    rows = source_rows(AT, 40)
    rows[0]["o3_ug_m3"] = 60  # Preserve latest source clock, value and revision.
    feed(db, AT, rows)
    assert deliver(db, monitor, Mailer())["status"] == "no_eligible_changes"
    evaluate(db, monitor, AT + timedelta(minutes=1))
    with db.session() as session:
        newest = session.scalar(select(AirChange).order_by(AirChange.sequence.desc()))
        assert newest.kind == "threshold_cleared" and newest.id != original_id
        assert newest.evidence["sample"]["version_id"] == sample["version_id"]
        assert newest.evidence["sample"]["timestamp"] == sample["timestamp"]
        assert newest.evidence["sample"]["value_hash"] != sample["value_hash"]
        assert session.get(AirChange, original_id).evidence["sample"] == sample
    assert deliver(db, monitor, Mailer(), now=AT + timedelta(minutes=2))["status"] == "sent"


def test_uncertain_smtp_is_not_retried(db):
    monitor = setup(db)
    class Uncertain:
        def send_message(self, *args, **kwargs):
            raise TimeoutError("Unknown server acceptance")
    assert deliver(db, monitor, Uncertain())["status"] == "uncertain"
    assert deliver(db, monitor, Mailer())["status"] == "no_eligible_changes"


def test_stale_source_contract_defers_without_changing_review(db):
    monitor = setup(db)
    with db.session() as session:
        session.get(AirSourceCache, "catalog").fetched_at = AT - timedelta(hours=26)
        session.commit()
    assert deliver(db, monitor, Mailer())["status"] == "no_eligible_changes"
    with db.session() as session:
        assert session.scalar(select(AirChange)).decision is None


def test_saved_digest_local_day_and_quiet_hours(db):
    from zoneinfo import ZoneInfo
    local = AT.astimezone(ZoneInfo("Europe/Zurich"))
    at_time = local.strftime("%H:%M")
    monitor = setup(db, delivery={"email": "daily_digest", "digest_at": at_time})
    fake = Mailer()
    assert deliver(db, monitor, fake)["status"] == "sent"
    consent(db, monitor, mode="off", now=AT)
    consent(db, monitor, now=AT, delivery={"email": "daily_digest", "digest_at": at_time})
    assert deliver(db, monitor, fake)["status"] == "daily_already_attempted"
    consent(db, monitor, now=AT, delivery={"email": "immediate", "quiet_hours": {
        "start": at_time, "end": (local + timedelta(hours=1)).strftime("%H:%M")}})
    feed(db, AT, source_rows(AT, 40))
    evaluate(db, monitor, AT + timedelta(minutes=1))
    assert deliver(db, monitor, fake, now=AT + timedelta(minutes=1))["status"] == "no_eligible_changes"
    assert len(fake.calls) == 1


def test_unverified_owner_cannot_consent_and_reconsent_does_not_backfill(db):
    monitor = setup(db)
    consent(db, monitor, mode="off", now=AT)
    with db.session() as session:
        session.get(User, "owner").email_verified_at = None
        session.commit()
    with pytest.raises(DomainError):
        consent(db, monitor, now=AT)
    with db.session() as session:
        session.get(User, "owner").email_verified_at = AT
        session.commit()
    consent(db, monitor, now=AT + timedelta(seconds=1))
    fake = Mailer()
    assert deliver(db, monitor, fake, now=AT + timedelta(seconds=2))["status"] == "no_eligible_changes"
    assert not fake.calls


@pytest.mark.asyncio
async def test_http_settings_exact_link_worker_and_opt_out(tmp_path, monkeypatch):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_auth import _csrf, _register, _settings

    from helvetic_lens import air_api
    from helvetic_lens.auth_mail import AuthMailer
    from helvetic_lens.main import create_app

    settings = _settings(tmp_path, air_watch_enabled=True)
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    at = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    clock = at - timedelta(seconds=1)
    monkeypatch.setattr(air_api, "_now", lambda: clock)
    monkeypatch.setattr(mail, "_now", lambda value=None: value or clock)
    fake = Mailer()
    monkeypatch.setattr(AuthMailer, "send_message", lambda self, *args, **kwargs: fake.send_message(*args, **kwargs))
    with TestClient(app) as client:
        _register(client)
        fake.calls.clear()
        identity = client.get("/api/auth/session").json()
        db = app.state.service.db
        with db.organization_context(identity["organization"]["id"]):
            feed(db, at, source_rows(at, 60))
            with db.session() as session:
                session.get(User, identity["user"]["id"]).email_verified_at = clock
                session.commit()
            saved = client.post("/api/air-watch/monitors", headers=_csrf(client),
                json={"configuration": configuration(), "request_key": str(uuid4())}).json()
            path = "/api/air-watch/monitors/" + saved["id"]
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
                job_id = session.scalar(select(Job.id).where(Job.type == "air_email"))
            result = await app.state.service.execute_job(job_id)
            assert result["state"] == "succeeded", result
            assert len(fake.calls) == 1 and item["href"] in fake.calls[0][0][2]
            assert client.get(exact).json()["event"]["decision"] is None
            feed(db, at, source_rows(at, 40))
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
    from helvetic_lens.air_models import AirMeasurement
    from helvetic_lens.db import Base
    monitor = setup(db)
    with db.session() as session:
        change_id = session.scalar(select(AirChange.id))
        measurement_id = session.scalar(select(AirMeasurement.id))
    with db.engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"include_object":
            lambda obj, name, kind, reflected, compare_to: name.startswith("air_") if kind == "table" else True})
        assert compare_metadata(context, Base.metadata) == []
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "1af7d89139bc")
        assert connection.execute(select(AirChange.id).where(AirChange.id == change_id)).scalar() == change_id
        assert connection.execute(select(AirMeasurement.id).where(AirMeasurement.id == measurement_id)).scalar() == measurement_id
        command.upgrade(config, "head")
        assert compare_metadata(context, Base.metadata) == []
        assert connection.execute(select(AirMonitor.email_revision).where(AirMonitor.id == monitor)).scalar() == 0


def test_digest_dst_gap_and_repeated_clock():
    from zoneinfo import ZoneInfo
    cfg = preferences.EmailConfiguration(delivery={"email": "daily_digest", "digest_at": "02:30"})
    spring = mail.next_delivery_at(cfg, datetime(2026, 3, 29, 0, tzinfo=UTC))
    assert spring.astimezone(ZoneInfo("Europe/Zurich")).strftime("%H:%M") == "03:00"
    fall = mail.next_delivery_at(cfg, datetime(2026, 10, 25, 0, tzinfo=UTC))
    assert mail.next_delivery_at(cfg, fall + timedelta(minutes=1)).astimezone(ZoneInfo("Europe/Zurich")).day == 26
