"""Private IP notifications; synthetic register and fake SMTP, no legal/source acceptance."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import delete, select
from test_tender_delivery import Mailer
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture
from test_trademark_sources import NOW, accept, grant
from test_trademark_workflow import create, review, rows, source_facts, sync

from helvetic_lens import trademark_delivery as mail
from helvetic_lens import trademark_email_preferences as preferences
from helvetic_lens import trademark_repository as profiles
from helvetic_lens import trademark_sources as sources
from helvetic_lens import trademark_workflow as workflow
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.models import Job, OrganizationMembership, User
from helvetic_lens.trademark_email_models import TrademarkDelivery
from helvetic_lens.trademark_models import TrademarkMonitor
from helvetic_lens.trademark_workflow_models import TrademarkCandidate

db, template = _database_fixture, _template_fixture
SETTINGS = Settings(_env_file=None, trademark_watch_enabled=True, auth_email_mode="smtp",
    auth_smtp_host="smtp.example.invalid", auth_email_from="monitoring@example.invalid",
    public_base_url="https://example.test")


def consent(db, monitor, *, mode="immediate", now=NOW, delivery=None):
    with db.session() as session:
        row = session.get(TrademarkMonitor, monitor)
        result = preferences.configure(session, "owner", monitor, expected_version=row.version,
            configuration={"delivery": delivery or {"email": mode}}, consent=mode != "off", now=now)
        session.commit()
        return result


def setup(db, *, notifications=True, delivery=None):
    permission = grant(db, private_decisions_allowed=True, notifications_allowed=notifications)
    accept(db, permission)
    monitor = create(db)
    with db.session() as session:
        session.get(User, "owner").email_verified_at = NOW - timedelta(seconds=2)
        session.commit()
    consent(db, monitor, now=NOW - timedelta(seconds=1), delivery=delivery)
    with db.session() as session:
        workflow.start(session, "owner", monitor, 2, now=NOW)
        workflow.refresh(session, "owner", monitor, now=NOW)
        session.commit()
    return permission, monitor


def deliver(db, monitor, fake, **kwargs):
    with db.session() as session:
        revision = session.get(TrademarkMonitor, monitor).email_revision
    return mail.deliver(db, SETTINGS, monitor_id=monitor, consent_revision=revision,
        mailer=fake, now=kwargs.pop("now", NOW), **kwargs)


def states(db):
    with db.session() as session:
        return list(session.scalars(select(TrademarkDelivery.state).order_by(TrademarkDelivery.created_at)))


def test_private_verified_consent_and_no_history_backfill(db):
    monitor = create(db)
    with db.session() as session:
        for user in ("peer", "viewer"):
            with pytest.raises(DomainError):
                preferences.view(session, user, monitor)
        for value in (False, "yes", 1, True):
            with pytest.raises(DomainError):
                preferences.configure(session, "owner", monitor, expected_version=1,
                    configuration={"delivery": {"email": "immediate"}}, consent=value, now=NOW)
        assert not preferences.view(session, "owner", monitor)["consent_active"]
    _, active = setup(db)
    consent(db, active, mode="off")
    consent(db, active, now=NOW + timedelta(seconds=1))
    sync(db, active, NOW + timedelta(seconds=1))
    assert not deliver(db, active, Mailer(), now=NOW + timedelta(seconds=1))["status"] == "sent"


def test_new_candidate_and_material_change_mail_once_without_review_or_source_facts(db):
    permission, monitor = setup(db)
    fake = Mailer()
    with db.session() as session:
        item, = mail.preview(session, SETTINGS, "owner", monitor, now=NOW)["items"]
    assert deliver(db, monitor, fake) == {"status": "sent", "changes": 1}
    assert deliver(db, monitor, fake)["status"] == "no_eligible_changes"
    args, headers = fake.calls[0]
    assert args[0] == "owner@example.test" and item["href"] in args[2]
    assert all(secret not in str(args) for secret in ("Synthetic Owner AG", "computer software", "ALMORA"))
    assert headers["message_id"].startswith("<trademark-")
    assert "not a confirmed infringement" in args[2]
    with db.session() as session:
        assert session.scalar(select(TrademarkCandidate)).reviewed_sequence == 0
    accept(db, permission, cursor=1, facts=source_facts(owners=["Changed Owner AG"]))
    sync(db, monitor, NOW + timedelta(seconds=1))
    assert deliver(db, monitor, fake, now=NOW + timedelta(seconds=1))["status"] == "sent"
    assert len(fake.calls) == 2 and states(db) == ["sent", "sent"]
    with db.organization_context("org-b"), db.session() as session:
        assert list(session.scalars(select(TrademarkDelivery))) == []
        assert mail.deliver(db, SETTINGS, monitor_id=monitor, consent_revision=1, now=NOW, mailer=fake)["status"] == "inactive"


@pytest.mark.parametrize("change", ["revoke", "pause", "archive", "off", "email", "unverify", "membership", "review", "feature", "material"])
def test_final_boundary_revalidates_private_current_candidate(db, change):
    permission, monitor = setup(db)
    fake = Mailer()

    def mutate():
        if change == "off":
            consent(db, monitor, mode="off")
        elif change == "review":
            review(db, monitor)
        elif change == "feature":
            SETTINGS.trademark_watch_enabled = False
        elif change == "material":
            accept(db, permission, cursor=1, second=0, facts=source_facts(status="cancelled"))
        else:
            with db.session() as session:
                if change == "revoke":
                    sources.revoke_permission(session, permission, now=NOW)
                elif change == "pause":
                    workflow.pause(session, "owner", monitor, session.get(TrademarkMonitor, monitor).version)
                elif change == "archive":
                    workflow.pause(session, "owner", monitor, session.get(TrademarkMonitor, monitor).version)
                    profiles.archive_monitor(session, "owner", monitor, session.get(TrademarkMonitor, monitor).version)
                elif change == "email":
                    session.get(User, "owner").email = "changed@example.test"
                elif change == "unverify":
                    session.get(User, "owner").email_verified_at = None
                elif change == "membership":
                    session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == "owner"))
                session.commit()
    try:
        assert deliver(db, monitor, fake, before_send=mutate)["status"] == "suppressed"
        assert not fake.calls
        assert states(db) == (["pending"] if change == "material" else ["suppressed"])
    finally:
        SETTINGS.trademark_watch_enabled = True


def test_notification_rights_and_source_freshness_are_separate_from_visibility(db):
    _, monitor = setup(db, notifications=False)
    assert rows(db, monitor)[0]["needs_review"]
    fake = Mailer()
    assert deliver(db, monitor, fake)["status"] == "no_eligible_changes"
    assert states(db) == ["suppressed"] and not fake.calls


def test_stale_source_defers_until_fresh_observation(db):
    permission, monitor = setup(db)
    fake = Mailer()
    later = NOW + timedelta(minutes=6)
    assert deliver(db, monitor, fake, now=later)["status"] == "no_eligible_changes"
    assert states(db) == ["pending"]
    accept(db, permission, cursor=1, second=420)
    sync(db, monitor, NOW + timedelta(minutes=7))
    assert deliver(db, monitor, fake, now=NOW + timedelta(minutes=7))["status"] == "sent"


def test_scheduling_off_cancel_and_uncertain_outcome_never_retry(db):
    _, monitor = setup(db)
    assert mail.enqueue_due(db, SETTINGS, now=NOW) == {"enqueued": 1}
    assert mail.enqueue_due(db, SETTINGS, now=NOW) == {"enqueued": 0}
    assert deliver(db, monitor, Mailer(fail=True))["status"] == "uncertain"
    consent(db, monitor, mode="off")
    consent(db, monitor, now=NOW + timedelta(seconds=1))
    fake = Mailer()
    deliver(db, monitor, fake, now=NOW + timedelta(seconds=1))
    assert not fake.calls
    with db.session() as session:
        assert preferences.view(session, "owner", monitor)["uncertain_deliveries"] == 1
        job = session.scalar(select(Job).where(Job.type == "trademark_email"))
        assert job.cancel_requested and job.max_attempts == 1


def test_quiet_hours_and_abandoned_claim_never_resend(db):
    permission, monitor = setup(db, delivery={"email": "immediate", "quiet_hours": {"start": "20:00", "end": "21:01"}})
    fake = Mailer()
    assert deliver(db, monitor, fake)["status"] == "no_eligible_changes"
    later = NOW + timedelta(minutes=1)
    accept(db, permission, cursor=1, second=60)
    sync(db, monitor, later)

    def crash():
        raise RuntimeError("Synthetic worker crash before SMTP")
    with pytest.raises(RuntimeError):
        deliver(db, monitor, fake, now=later, before_send=crash)
    assert states(db) == ["sending"]
    mail.enqueue_due(db, SETTINGS, now=later + timedelta(minutes=6))
    assert states(db) == ["uncertain"] and not fake.calls


def test_daily_local_day_limit_survives_reconsent_and_handles_dst(db):
    _, monitor = setup(db, delivery={"email": "daily_digest", "digest_at": "21:00"})
    fake = Mailer()
    assert deliver(db, monitor, fake)["status"] == "sent"
    consent(db, monitor, mode="off")
    consent(db, monitor, delivery={"email": "daily_digest", "digest_at": "21:00"})
    assert deliver(db, monitor, fake)["status"] == "daily_already_attempted"
    assert len(fake.calls) == 1
    config = preferences.EmailConfiguration(delivery={"email": "daily_digest", "digest_at": "02:30"})
    spring = mail.next_delivery_at(config, datetime(2026, 3, 29, 0, tzinfo=UTC))
    assert spring.astimezone(ZoneInfo("Europe/Zurich")).strftime("%H:%M") == "03:00"
    fall = mail.next_delivery_at(config, datetime(2026, 10, 25, 0, tzinfo=UTC))
    assert mail.next_delivery_at(config, fall + timedelta(minutes=1)).astimezone(ZoneInfo("Europe/Zurich")).day == 26


def test_configuration_only_candidate_change_does_not_send(db):
    _, monitor = setup(db)
    fake = Mailer()
    deliver(db, monitor, fake)
    with db.session() as session:
        row = session.get(TrademarkMonitor, monitor)
        workflow.pause(session, "owner", monitor, row.version)
        profiles.edit_monitor(session, "owner", monitor, row.version, {**row.configuration, "name": "Renamed private portfolio"})
        workflow.start(session, "owner", monitor, row.version, now=NOW + timedelta(seconds=1))
        session.commit()
    sync(db, monitor, NOW + timedelta(seconds=1))
    deliver(db, monitor, fake, now=NOW + timedelta(seconds=1))
    assert len(fake.calls) == 1

@pytest.mark.asyncio
async def test_http_consent_preview_durable_worker_and_opt_out(tmp_path, monkeypatch):
    from uuid import uuid4

    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_auth import _csrf, _register, _settings
    from test_trademark_matching import portfolio

    from helvetic_lens import trademark_api
    from helvetic_lens.auth_mail import AuthMailer
    from helvetic_lens.main import create_app

    settings = _settings(tmp_path, trademark_watch_enabled=True)
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    now = NOW - timedelta(seconds=1)
    monkeypatch.setattr(trademark_api, "_now", lambda: now)
    monkeypatch.setattr(mail, "_now", lambda value=None: value or now)
    fake = Mailer()
    monkeypatch.setattr(AuthMailer, "send_message", lambda self, *args, **kwargs: fake.send_message(*args, **kwargs))
    with TestClient(app) as client:
        _register(client)
        fake.calls.clear()
        identity = client.get("/api/auth/session").json()
        database = app.state.service.db
        with database.organization_context(identity["organization"]["id"]):
            permission = grant(database, private_decisions_allowed=True, notifications_allowed=True)
            accept(database, permission)
            with database.session() as session:
                session.get(User, identity["user"]["id"]).email_verified_at = now
                session.commit()
            saved = client.post("/api/trademark-watch/monitors", headers=_csrf(client),
                json={"configuration": portfolio().model_dump(mode="json"), "request_key": str(uuid4())}).json()
            path = "/api/trademark-watch/monitors/" + saved["id"]
            body = {"expected_version": 1, "configuration": {"delivery": {"email": "immediate"}}, "consent": True}
            assert client.get(path + "/email").headers["cache-control"] == "no-store"
            assert client.put(path + "/email", json=body).status_code == 403
            assert client.put(path + "/email", headers=_csrf(client), json={**body, "recipient_email": "outside@example.test"}).status_code == 422
            assert client.put(path + "/email", headers=_csrf(client), json={**body, "consent": 1}).status_code == 422
            assert client.put(path + "/email", headers=_csrf(client), json=body).status_code == 200
            assert client.put(path + "/email", headers=_csrf(client), json=body).status_code == 409
            settings.auth_email_mode, settings.auth_smtp_host, settings.auth_email_from = "smtp", "smtp.example.invalid", "monitoring@example.invalid"
            now = NOW
            assert client.post(path + "/start", headers=_csrf(client), json={"expected_version": 2}).status_code == 200
            assert client.post(path + "/refresh", headers=_csrf(client)).status_code == 200
            preview = client.get(path + "/email/preview")
            assert preview.headers["cache-control"] == "no-store"
            item, = preview.json()["items"]
            assert "candidate=" in item["href"] and "event=" in item["href"]
            assert mail.enqueue_due(database, settings, now=now)["enqueued"] == 1
            with database.session() as session:
                job_id = session.scalar(select(Job.id).where(Job.type == "trademark_email"))
            result = await app.state.service.execute_job(job_id)
            assert result["state"] == "succeeded", result
            assert len(fake.calls) == 1 and item["href"] in fake.calls[0][0][2]
            assert client.get(path + "/candidates").json()["items"][0]["needs_review"]
            assert client.get(path + "/email/preview").json()["items"] == []
            version = client.get(path).json()["version"]
            off = {"expected_version": version, "configuration": {"delivery": {"email": "off"}}, "consent": False}
            assert not client.put(path + "/email", headers=_csrf(client), json=off).json()["consent_active"]
        client.cookies.clear()
        assert client.get(path + "/email").status_code == 401
        assert client.get(path + "/email/preview").status_code == 401
