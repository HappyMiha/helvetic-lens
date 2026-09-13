"""Consented auction reminders and material notices with fake SMTP only."""

from datetime import timedelta

import pytest
from sqlalchemy import delete, select
from test_auction_rules import NOW, profile
from test_auction_sources import accept, grant, price
from test_auction_workflow import action, create, sync
from test_tender_delivery import Mailer
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens import auction_delivery as mail
from helvetic_lens import auction_email_preferences as preferences
from helvetic_lens import auction_reminders as reminders
from helvetic_lens import auction_sources as sources
from helvetic_lens import auction_workflow as workflow
from helvetic_lens.auction_models import AuctionMonitor
from helvetic_lens.auction_workflow_models import AuctionDelivery, AuctionItem
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.models import Job, OrganizationMembership, User

db, template = _database_fixture, _template_fixture
SETTINGS = Settings(_env_file=None, auction_watch_enabled=True, auth_email_mode="smtp",
    auth_smtp_host="smtp.example.invalid", auth_email_from="monitoring@example.invalid", public_base_url="https://example.test")


def consent(db, monitor, *, mode="immediate", now=NOW, delivery=None):
    with db.session() as session:
        row = session.get(AuctionMonitor, monitor)
        result = preferences.configure(session, "owner", monitor, expected_version=row.version,
            configuration={"delivery": delivery or {"email": mode}}, consent=mode != "off", now=now)
        session.commit()
        return result


def setup(db, *, notifications=True, delivery=None):
    permission = grant(db, private_decisions_allowed=True, notifications_allowed=notifications)
    accept(db, permission)
    monitor = create(db, notify={**profile().notify.model_dump(), "ending_soon_hours": 24})
    with db.session() as session:
        session.get(User, "owner").email_verified_at = NOW
        session.commit()
    consent(db, monitor, now=NOW - timedelta(seconds=1), delivery=delivery)
    with db.session() as session:
        workflow.start(session, "owner", monitor, 2, now=NOW)
        workflow.refresh(session, "owner", monitor, now=NOW)
        session.commit()
    return permission, monitor


def deliver(db, monitor, fake, **kwargs):
    with db.session() as session:
        revision = session.get(AuctionMonitor, monitor).email_revision
    return mail.deliver(db, SETTINGS, monitor_id=monitor, consent_revision=revision,
        mailer=fake, now=kwargs.pop("now", NOW), **kwargs)


def states(db):
    with db.session() as session:
        return list(session.scalars(select(AuctionDelivery.state).order_by(AuctionDelivery.created_at)))


def test_verified_owner_consent_cannot_be_forged_and_does_not_backfill(db):
    monitor = create(db)
    with db.session() as session:
        for user in ("peer", "viewer"):
            with pytest.raises(DomainError):
                preferences.view(session, user, monitor)
        for consent_value in (False, "yes", 1, True):
            with pytest.raises(DomainError):
                preferences.configure(session, "owner", monitor, expected_version=1,
                    configuration={"delivery": {"email": "immediate"}}, consent=consent_value, now=NOW)
        assert not preferences.view(session, "owner", monitor)["consent_active"]
    assert states(db) == []


def test_material_email_once_with_private_link_no_source_payload_or_review(db):
    _, monitor = setup(db)
    fake = Mailer()
    with db.session() as session:
        assert len(mail.preview(session, SETTINGS, "owner", monitor, now=NOW)["items"]) == 1
    assert deliver(db, monitor, fake) == {"status": "sent", "changes": 1}
    assert deliver(db, monitor, fake)["status"] == "no_eligible_changes"
    assert len(fake.calls) == 1 and states(db) == ["sent"]
    args, headers = fake.calls[0]
    assert args[0] == "owner@example.test" and f"monitor={monitor}&event=" in args[2]
    assert "850000" not in str(args) and "Synthetic office" not in str(args)
    assert headers["message_id"].startswith("<auction-")
    with db.session() as session:
        assert session.scalar(select(AuctionItem)).reviewed_sequence == 0


@pytest.mark.parametrize("change", ["revoke", "pause", "off", "email", "membership", "review", "unfollow", "feature"])
def test_final_send_boundary_rechecks_changes(db, change):
    permission, monitor = setup(db)
    action(db, monitor, following=True)
    fake = Mailer()

    def mutate():
        if change == "off":
            consent(db, monitor, mode="off")
        elif change == "review":
            action(db, monitor, decision="inspect")
        elif change == "unfollow":
            action(db, monitor, following=False)
        elif change == "feature":
            SETTINGS.auction_watch_enabled = False
        else:
            with db.session() as session:
                if change == "revoke":
                    sources.revoke_permission(session, permission, now=NOW)
                elif change == "pause":
                    workflow.pause(session, "owner", monitor, session.get(AuctionMonitor, monitor).version)
                elif change == "email":
                    session.get(User, "owner").email = "changed@example.test"
                elif change == "membership":
                    session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == "owner"))
                session.commit()
    try:
        assert deliver(db, monitor, fake, before_send=mutate)["status"] == "suppressed"
        assert not fake.calls and states(db) == ["suppressed"]
    finally:
        SETTINGS.auction_watch_enabled = True


def test_notification_rights_separate_from_ui_and_freshness_defers(db):
    _, monitor = setup(db, notifications=False)
    fake = Mailer()
    assert deliver(db, monitor, fake)["status"] == "no_eligible_changes"
    assert not fake.calls and states(db) == ["suppressed"]


def test_stale_claim_recovers_after_fresh_observation(db):
    permission, monitor = setup(db)
    fake = Mailer()
    later = NOW + timedelta(minutes=6)
    assert deliver(db, monitor, fake, now=later)["status"] == "no_eligible_changes"
    assert states(db) == ["pending"]
    accept(db, permission, cursor=1, at=later + timedelta(minutes=1))
    sync(db, monitor, now=later + timedelta(minutes=1))
    # Event evidence is still retained even though its current-head freshness changed.
    assert deliver(db, monitor, fake, now=later + timedelta(minutes=1))["status"] == "sent"


def test_reminder_email_acknowledgement_and_off_on_do_not_duplicate(db):
    _, monitor = setup(db)
    fake = Mailer()
    deliver(db, monitor, fake)
    action(db, monitor, following=True)
    reminders.activate_due(db, SETTINGS, now=NOW)
    assert deliver(db, monitor, fake)["changes"] == 1
    assert "&reminder=" in fake.calls[-1][0][2]
    consent(db, monitor, mode="off")
    consent(db, monitor)
    assert deliver(db, monitor, fake)["status"] == "no_eligible_changes"
    assert len(fake.calls) == 2
    with db.session() as session:
        row, = reminders.page(session, "owner", now=NOW)["items"]
        reminders.acknowledge(session, "owner", monitor, row["id"], expected_version=row["version"], now=NOW)
        assert reminders.page(session, "owner", now=NOW)["items"] == []
        session.commit()


def test_uncertain_smtp_and_abandoned_claim_never_resend(db):
    _, monitor = setup(db)

    class Uncertain:
        def send_message(self, *args, **kwargs):
            raise TimeoutError("Synthetic unknown SMTP outcome")
    assert deliver(db, monitor, Uncertain())["status"] == "uncertain"
    consent(db, monitor, mode="off")
    consent(db, monitor)
    fake = Mailer()
    deliver(db, monitor, fake)
    assert not fake.calls
    with db.session() as session:
        assert preferences.view(session, "owner", monitor)["uncertain_deliveries"] == 1


def test_scheduler_single_job_and_consent_off_cancels(db):
    _, monitor = setup(db)
    assert mail.enqueue_due(db, SETTINGS, now=NOW) == {"enqueued": 1}
    assert mail.enqueue_due(db, SETTINGS, now=NOW) == {"enqueued": 0}
    consent(db, monitor, mode="off")
    with db.session() as session:
        job = session.scalar(select(Job).where(Job.type == "auction_email"))
        assert job.cancel_requested and job.max_attempts == 1
    assert states(db) == ["suppressed"]


def test_later_unrequested_bid_does_not_email_an_excluded_unfollowed_match(db):
    permission, monitor = setup(db)
    accept(db, permission, cursor=1, prices=[price(1270000)])
    sync(db, monitor, now=NOW + timedelta(seconds=1))
    fake = Mailer()
    deliver(db, monitor, fake, now=NOW + timedelta(seconds=1))
    assert not fake.calls


def test_daily_digest_does_not_repeat_after_reconsent_and_dst_uses_local_day(db):
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo
    _, monitor = setup(db, delivery={"email": "daily_digest", "digest_at": "14:00"})
    fake = Mailer()
    assert deliver(db, monitor, fake)["status"] == "sent"
    action(db, monitor, following=True)
    reminders.activate_due(db, SETTINGS, now=NOW)
    consent(db, monitor, mode="off")
    consent(db, monitor, delivery={"email": "daily_digest", "digest_at": "14:00"})
    assert deliver(db, monitor, fake)["status"] == "daily_already_attempted"
    assert len(fake.calls) == 1
    config = preferences.EmailConfiguration(delivery={"email": "daily_digest", "digest_at": "02:30"})
    spring = mail.next_delivery_at(config, datetime(2026, 3, 29, 0, tzinfo=UTC))
    assert spring.astimezone(ZoneInfo("Europe/Zurich")).strftime("%H:%M") == "03:00"
    fall = mail.next_delivery_at(config, datetime(2026, 10, 25, 0, tzinfo=UTC))
    assert mail.next_delivery_at(config, fall + timedelta(minutes=1)).astimezone(ZoneInfo("Europe/Zurich")).day == 26


def test_quiet_hours_defer_and_abandoned_claim_is_uncertain(db):
    permission, monitor = setup(db, delivery={"email": "immediate", "quiet_hours": {"start": "13:00", "end": "14:01"}})
    fake = Mailer()
    assert deliver(db, monitor, fake)["status"] == "no_eligible_changes"
    assert states(db) == ["pending"]
    later = NOW + timedelta(minutes=1)
    accept(db, permission, cursor=1, at=later)
    sync(db, monitor, now=later)
    def crash():
        raise RuntimeError("Synthetic worker exit before SMTP")
    with pytest.raises(RuntimeError):
        deliver(db, monitor, fake, now=later, before_send=crash)
    assert states(db) == ["sending"]
    mail.enqueue_due(db, SETTINGS, now=later + timedelta(minutes=6))
    assert states(db) == ["uncertain"] and not fake.calls
    assert deliver(db, monitor, fake, now=later + timedelta(minutes=6))["status"] == "no_eligible_changes"


@pytest.mark.parametrize("change", ["acknowledge", "deadline", "cancel", "unknown"])
def test_ready_reminder_rechecked_at_smtp_boundary(db, change):
    permission, monitor = setup(db)
    fake = Mailer()
    deliver(db, monitor, fake)
    action(db, monitor, following=True)
    reminders.activate_due(db, SETTINGS, now=NOW)
    def mutate():
        if change == "acknowledge":
            with db.session() as session:
                row, = reminders.page(session, "owner", now=NOW)["items"]
                reminders.acknowledge(session, "owner", monitor, row["id"], expected_version=row["version"], now=NOW)
                session.commit()
        else:
            patch = {"ends_at": NOW + timedelta(hours=30)} if change == "deadline" else {"status": "cancelled"} if change == "cancel" else {"ends_at": None}
            accept(db, permission, cursor=1, at=NOW, **patch)
            sync(db, monitor)
    assert deliver(db, monitor, fake, before_send=mutate)["status"] in {"suppressed", "no_eligible_changes"}
    assert len(fake.calls) == 1


@pytest.mark.asyncio
async def test_http_email_reminders_and_durable_worker_use_fake_smtp(tmp_path, monkeypatch):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_auth import _csrf, _register, _settings

    from helvetic_lens import auction_api
    from helvetic_lens.auth_mail import AuthMailer
    from helvetic_lens.main import create_app
    settings = _settings(tmp_path, auction_watch_enabled=True)
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    monkeypatch.setattr(auction_api, "_now", lambda: NOW)
    monkeypatch.setattr(mail, "_now", lambda value=None: value or NOW)
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
                session.get(User, identity["user"]["id"]).email_verified_at = NOW
                session.commit()
            config = profile(notify={**profile().notify.model_dump(), "ending_soon_hours": 24}).model_dump(mode="json")
            from uuid import uuid4
            saved = client.post("/api/auction-watch/monitors", headers=_csrf(client),
                json={"configuration": config, "request_key": str(uuid4())}).json()
            path = "/api/auction-watch/monitors/" + saved["id"]
            body = {"expected_version": 1, "configuration": {"delivery": {"email": "immediate"}}, "consent": True}
            assert client.get(path + "/email").headers["cache-control"] == "no-store"
            assert client.put(path + "/email", json=body).status_code == 403
            assert client.put(path + "/email", headers=_csrf(client), json={**body, "recipient_email": "outsider@example.test"}).status_code == 422
            assert client.put(path + "/email", headers=_csrf(client), json=body).status_code == 200
            assert client.put(path + "/email", headers=_csrf(client), json=body).status_code == 409
            settings.auth_email_mode, settings.auth_smtp_host, settings.auth_email_from = "smtp", "smtp.example.invalid", "monitoring@example.invalid"
            assert client.post(path + "/start", headers=_csrf(client), json={"expected_version": 2}).status_code == 200
            assert client.post(path + "/refresh", headers=_csrf(client)).status_code == 200
            row, = client.get(path + "/items").json()["items"]
            assert client.post(path + f"/items/{row['id']}/follow", headers=_csrf(client), json={"expected_version": row["version"],
                "following": True, "expected_state_hash": row["state_hash"]}).status_code == 200
            reminders.activate_due(database, settings, now=NOW)
            reminder, = client.get("/api/auction-watch/reminders").json()["items"]
            exact = path + f"/reminders/{reminder['id']}"
            assert client.get(exact).json()["eligible"]
            assert client.get(path + "/reminders?limit=51").status_code == 422
            assert client.get(path + "/email/preview").json()["items"]
            assert mail.enqueue_due(database, settings, now=NOW)["enqueued"] == 1
            with database.session() as session:
                job_id = session.scalar(select(Job.id).where(Job.type == "auction_email"))
            result = await app.state.service.execute_job(job_id)
            assert result["state"] == "succeeded", result
            assert len(fake.calls) == 1
            body = {"expected_version": reminder["version"]}
            assert client.post(exact + "/acknowledge", json=body).status_code == 403
            assert client.post(exact + "/acknowledge", headers=_csrf(client), json=body).json()["state"] == "acknowledged"
            assert client.post(exact + "/acknowledge", headers=_csrf(client), json=body).status_code == 409
            assert client.get("/api/auction-watch/reminders").json()["items"] == []
            assert client.get(path + "/items").json()["items"][0]["needs_review"]
        client.cookies.clear()
        assert client.get(exact).status_code == 401


def test_bounded_batch_does_not_starve_fresh_lot_behind_stale_lot(db, monkeypatch):
    permission, monitor = setup(db)
    accept(db, permission, cursor=1, lot_id="fresh-lot")
    sync(db, monitor, now=NOW + timedelta(seconds=1))
    later = NOW + timedelta(minutes=6)
    accept(db, permission, cursor=2, lot_id="fresh-lot", at=later)
    sync(db, monitor, now=later)
    monkeypatch.setattr(mail, "MAX_BATCH", 1)
    fake = Mailer()
    assert deliver(db, monitor, fake, now=later)["status"] == "no_eligible_changes"
    assert deliver(db, monitor, fake, now=later)["status"] == "sent"
    assert states(db) == ["pending", "sent"]
    with db.organization_context("org-b"), db.session() as session:
        assert list(session.scalars(select(AuctionDelivery))) == []
        assert mail.deliver(db, SETTINGS, monitor_id=monitor, consent_revision=1, now=later, mailer=fake)["status"] == "inactive"
    assert len(fake.calls) == 1
