"""Synthetic source, native workflow, fake SMTP: no external mail or source grant."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from test_hazard_cap import NOW, info
from test_hazard_lifecycle import command, complete_poll, coverage
from test_hazard_lifecycle import store as store
from test_hazard_repository import CONFIG, create
from test_hazard_sources import accept, grant, revised
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens import hazard_delivery as mail
from helvetic_lens import hazard_email_preferences as preferences
from helvetic_lens import hazard_events as events
from helvetic_lens import hazard_jobs as worker
from helvetic_lens import hazard_sources as sources
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.hazard_models import HazardDelivery, HazardDevelopment, HazardMonitor
from helvetic_lens.models import Job, OrganizationMembership, User


class Mailer:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def send_message(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.fail:
            raise RuntimeError("Synthetic uncertain transport")
        return "smtp"


def opt_in(db, saved, *, delivery=None):
    with db.session() as session:
        session.get(User, "owner").email_verified_at = NOW
        session.flush()
        result = preferences.configure(session, "owner", saved["id"], expected_version=saved["version"],
            configuration={"delivery": delivery or {"email": "immediate"}}, consent=True, now=NOW)
        session.commit()
    return {**saved, "version": result["monitor_version"]}


def prepared(db, store, *, notifications=True, delivery=None):
    saved = create(db, {**CONFIG, "hazards": ["storm"]})
    permission = grant(db, private_decisions_allowed=True, notifications_allowed=notifications, coverage=(coverage(),))
    accept(db, permission)
    complete_poll(db, permission, cursor=1)
    settings = Settings(_env_file=None, hazard_watch_enabled=True, hazard_source_enabled=True,
        hazard_source_permission_id=permission, auth_email_mode="smtp", auth_smtp_host="smtp.example.invalid",
        auth_email_from="monitoring@example.invalid", public_base_url="https://example.test")
    saved = opt_in(db, saved, delivery=delivery)
    saved = command(db, store, settings, saved, "start")
    assert worker.refresh(db, settings, monitor_id=saved["id"], version=saved["version"], now=NOW, store=store)["changed"] == 1
    return saved, permission, settings


def deliver(db, saved, settings, store, fake, **kwargs):
    with db.session() as session:
        revision = session.get(HazardMonitor, saved["id"]).email_revision
    return mail.deliver(db, settings, monitor_id=saved["id"], consent_revision=revision,
        now=kwargs.pop("now", NOW), store=store, mailer=fake, **kwargs)


def test_verified_explicit_owner_consent_and_no_backfill(db, store):
    saved = create(db, {**CONFIG, "hazards": ["storm"]})
    with db.session() as session:
        for actor in ("peer", "viewer"):
            with pytest.raises(DomainError):
                preferences.view(session, actor, saved["id"])
        for consent in (False, True, "yes", 1):
            with pytest.raises(DomainError):
                preferences.configure(session, "owner", saved["id"], expected_version=1,
                    configuration={"delivery": {"email": "immediate"}}, consent=consent, now=NOW)
    saved = opt_in(db, saved)
    with db.session() as session:
        assert preferences.view(session, "owner", saved["id"])["consent_active"]
        assert session.scalars(select(HazardDelivery)).all() == []
        assert session.get(HazardMonitor, saved["id"]).status == "draft"
        with pytest.raises(DomainError):
            preferences.configure(session, "owner", saved["id"], expected_version=1,
                configuration={"delivery": {"email": "off"}}, consent=False, now=NOW)


def test_material_warning_sends_once_exact_link_without_review_or_source_export(db, store):
    saved, _, settings = prepared(db, store)
    fake = Mailer()
    with db.session() as session:
        preview = mail.preview(session, settings, "owner", saved["id"], now=NOW, store=store)
        assert len(preview["items"]) == 1
    assert deliver(db, saved, settings, store, fake) == {"status": "sent", "changes": 1}
    assert deliver(db, saved, settings, store, fake)["status"] == "no_eligible_changes"
    args, headers = fake.calls[0]
    assert args[0] == "owner@example.test" and "&revision=1" in args[2]
    assert "/hazard-watch?monitor=" in args[2] and headers["message_id"].startswith("<hazard-")
    assert "latitude" not in str(args) and "Fixture authority" not in str(args)
    with db.session() as session:
        assert session.scalar(select(HazardDevelopment)).reviewed_sequence == 0
        assert session.scalar(select(HazardDelivery)).state == "sent"


@pytest.mark.parametrize("change", ["off", "email", "unverified", "membership", "pause", "mute", "review", "dismiss", "source", "geography", "scope", "runtime", "checkpoint"])
def test_final_recheck_suppresses_claimed_warning(db, store, change):
    saved, permission, settings = prepared(db, store)
    fake = Mailer()
    checks = 0
    def checkpoint():
        nonlocal checks
        checks += 1
        return change != "checkpoint" or checks == 1
    def invalidate():
        if change == "pause":
            command(db, store, settings, saved, "pause")
            return
        if change == "geography":
            store.available = False
        elif change == "scope":
            store.scope_available = False
        elif change == "runtime":
            settings.hazard_source_enabled = False
        with db.session() as session:
            if change == "off":
                preferences.configure(session, "owner", saved["id"], expected_version=saved["version"],
                    configuration={"delivery": {"email": "off"}}, consent=False, now=NOW)
            elif change == "email":
                session.get(User, "owner").email = "changed@example.test"
            elif change == "unverified":
                session.get(User, "owner").email_verified_at = None
            elif change == "membership":
                session.execute(update(OrganizationMembership).where(OrganizationMembership.user_id == "owner").values(role="viewer"))
            elif change == "source":
                sources.revoke_permission(session, permission, now=NOW)
            elif change == "mute":
                events.set_mute(session, "owner", saved["id"], "storm", version=saved["version"], muted=True, now=NOW)
            elif change in {"review", "dismiss"}:
                event = session.scalar(select(HazardDevelopment))
                events.set_review(session, "owner", saved["id"], event.id, version=event.version,
                    expected_revision=event.revision, action="reviewed" if change == "review" else "not_relevant", store=store, now=NOW)
            session.commit()
    assert deliver(db, saved, settings, store, fake, before_send=invalidate, checkpoint=checkpoint)["status"] == "suppressed"
    assert fake.calls == []


def test_display_permission_does_not_authorize_email(db, store):
    saved, _, settings = prepared(db, store, notifications=False)
    fake = Mailer()
    with db.session() as session:
        assert session.scalar(select(HazardDevelopment)) is not None
        assert session.scalars(select(HazardDelivery)).all() == []
    assert deliver(db, saved, settings, store, fake)["status"] == "no_eligible_changes"
    assert fake.calls == []


def test_uncertain_transport_is_not_retried_and_old_claim_becomes_uncertain(db, store):
    saved, _, settings = prepared(db, store)
    fake = Mailer(fail=True)
    assert deliver(db, saved, settings, store, fake)["status"] == "uncertain"
    assert deliver(db, saved, settings, store, fake)["status"] == "no_eligible_changes"
    assert len(fake.calls) == 1
    with db.session() as session:
        row = session.scalar(select(HazardDelivery))
        row.state, row.claimed_at = "sending", NOW - timedelta(minutes=6)
        session.commit()
    assert mail.enqueue_due(db, settings, now=NOW, store=store)["enqueued"] == 0
    with db.session() as session:
        assert session.scalar(select(HazardDelivery)).state == "uncertain"


def test_new_instructions_suppress_old_intent_and_enqueue_new_material_revision(db, store):
    saved, permission, settings = prepared(db, store)
    def advance():
        accept(db, permission, revised(infos=info(instruction="New official instructions")), cursor=1, second=1)
        complete_poll(db, permission, cursor=2, second=1)
        worker.refresh(db, settings, monitor_id=saved["id"], version=saved["version"], now=NOW + timedelta(seconds=1), store=store)
    fake = Mailer()
    assert deliver(db, saved, settings, store, fake, before_send=advance)["status"] == "suppressed"
    assert fake.calls == []
    assert deliver(db, saved, settings, store, fake, now=NOW + timedelta(seconds=2))["status"] == "sent"
    assert "revision=2" in fake.calls[0][0][2]


def test_scheduler_deduplicates_email_jobs_and_stopping_suppresses_pending(db, store):
    saved, _, settings = prepared(db, store)
    assert mail.enqueue_due(db, settings, now=NOW, store=store)["enqueued"] == 1
    assert mail.enqueue_due(db, settings, now=NOW, store=store)["enqueued"] == 0
    command(db, store, settings, saved, "pause")
    with db.session() as session:
        assert session.scalar(select(HazardDelivery)).state == "suppressed"
        assert session.scalar(select(Job).where(Job.type == "hazard_email")).cancel_requested


def test_overlapping_places_deduplicate_but_another_organization_is_independent(db, store):
    saved, _, settings = prepared(db, store)
    def other_place(key):
        place = create(db, {**CONFIG, "name": key, "hazards": ["storm"]}, key=key)
        place = opt_in(db, place)
        place = command(db, store, settings, place, "start")
        worker.refresh(db, settings, monitor_id=place["id"], version=place["version"], now=NOW, store=store)
        return place
    second = other_place("Office")
    fake = Mailer()
    assert deliver(db, saved, settings, store, fake)["status"] == "sent"
    assert deliver(db, second, settings, store, fake)["status"] == "no_eligible_changes"
    assert len(fake.calls) == 1
    with db.organization_context("org-b"):
        other = other_place("Other organization")
        assert deliver(db, other, settings, store, fake)["status"] == "sent"
    assert len(fake.calls) == 2


def test_translation_keeps_one_material_intent_and_links_latest_original_revision(db, store):
    saved, permission, settings = prepared(db, store)
    accept(db, permission, revised(infos=info() + info(language="fr-CH", instruction="Restez.")), cursor=1, second=1)
    complete_poll(db, permission, cursor=2, second=1)
    worker.refresh(db, settings, monitor_id=saved["id"], version=saved["version"], now=NOW + timedelta(seconds=1), store=store)
    with db.session() as session:
        intent, = session.scalars(select(HazardDelivery))
        assert intent.material_sequence == 1 and intent.revision == 1
        assert session.scalar(select(HazardDevelopment)).revision == 2
    fake = Mailer()
    assert deliver(db, saved, settings, store, fake, now=NOW + timedelta(seconds=2))["status"] == "sent"
    assert "revision=2" in fake.calls[0][0][2]


def test_quiet_hours_defer_and_stale_source_never_sends(db, store):
    saved, _, settings = prepared(db, store, delivery={"email": "immediate", "quiet_hours": {"start": "11:00", "end": "13:00"}})
    fake = Mailer()
    with db.session() as session:
        intent = session.scalar(select(HazardDelivery))
        assert sources._utc(intent.due_at) == NOW + timedelta(hours=1)
    assert deliver(db, saved, settings, store, fake)["status"] == "no_eligible_changes"
    assert deliver(db, saved, settings, store, fake, now=NOW + timedelta(hours=1))["status"] == "unavailable"
    assert fake.calls == []


@pytest.mark.parametrize("moment,expected", [
    (datetime(2026, 3, 29, 0, tzinfo=UTC), datetime(2026, 3, 29, 1, tzinfo=UTC)),
    (datetime(2026, 10, 25, 0, tzinfo=UTC), datetime(2026, 10, 25, 0, 30, tzinfo=UTC)),
])
def test_digest_uses_real_instant_across_dst_gap_and_fold(moment, expected):
    config = preferences.EmailConfiguration(delivery={"email": "daily_digest", "digest_at": "02:30"})
    assert mail.next_delivery_at(config, moment) == expected


def test_daily_batch_limit_and_recipient_change_are_not_bypassed(db, store):
    saved, _, settings = prepared(db, store, delivery={"email": "daily_digest", "digest_at": "12:00"})
    fake = Mailer()
    assert deliver(db, saved, settings, store, fake)["status"] == "sent"
    assert deliver(db, saved, settings, store, fake)["status"] == "daily_already_attempted"
    assert len(fake.calls) == 1


def test_email_can_be_disabled_after_preference_history_limit(db, store):
    saved, _, _ = prepared(db, store)
    # A lower test limit would mirror implementation. Instead install a retained
    # terminal revision as a migrated account could already have.
    from helvetic_lens.hazard_models import HazardEmailPolicy
    with db.session() as session:
        row = session.get(HazardMonitor, saved["id"])
        original = session.get(HazardEmailPolicy, (row.id, row.email_revision))
        session.add(HazardEmailPolicy(monitor_id=row.id, organization_id=row.organization_id,
            revision=1000, configuration=original.configuration, recipient_email=original.recipient_email, created_at=NOW))
        row.email_revision = 1000
        session.flush()
        off = preferences.configure(session, "owner", row.id, expected_version=row.version,
            configuration={"delivery": {"email": "off"}}, consent=False, now=NOW)
        assert off["revision"] == 1001 and not off["consent_active"]


def test_new_consent_then_translation_does_not_backfill_old_material(db, store):
    saved, permission, settings = prepared(db, store)
    # A later consent revision suppresses the earlier pending intent. The next
    # translation is not a new warning and must not resurrect that material.
    saved = opt_in(db, saved)
    accept(db, permission, revised(infos=info() + info(language="fr-CH", instruction="Restez.")), cursor=1, second=1)
    complete_poll(db, permission, cursor=2, second=1)
    worker.refresh(db, settings, monitor_id=saved["id"], version=saved["version"], now=NOW + timedelta(seconds=1), store=store)
    with db.session() as session:
        intent, = session.scalars(select(HazardDelivery))
        assert intent.state == "suppressed" and intent.consent_revision == 1
    fake = Mailer()
    assert deliver(db, saved, settings, store, fake, now=NOW + timedelta(seconds=2))["status"] == "no_eligible_changes"
    assert fake.calls == []


def test_production_transport_is_disabled_outside_smtp_mode(db, store):
    saved, _, settings = prepared(db, store)
    settings.auth_email_mode = "log"
    result = mail.deliver(db, settings, monitor_id=saved["id"], consent_revision=1, now=NOW, store=store)
    assert result["status"] == "mail_not_live"
    with db.session() as session:
        assert session.scalar(select(HazardDelivery)).state == "pending"
