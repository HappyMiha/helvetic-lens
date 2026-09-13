from copy import deepcopy
from types import SimpleNamespace

import pytest
import test_tender_repository as persistence
from sqlalchemy import select, update
from test_tender_matching import NOW, PROJECT
from test_tender_repository import create, decide, ingest, publication, read, revised

from helvetic_lens import tender_delivery as mail
from helvetic_lens import tender_email_preferences as preferences
from helvetic_lens.config import DomainError
from helvetic_lens.models import Job, OrganizationMembership, User
from helvetic_lens.tender_models import TenderDelivery, TenderEmailPolicy, TenderMonitor
from helvetic_lens.tender_rights import restrict

db = persistence.db
template = persistence.template


def settings():
    return SimpleNamespace(
        tender_watch_enabled=True,
        simap_public_source_enabled=True,
        public_base_url="https://example.test",
        auth_email_mode="smtp",
    )


class Mailer:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def send_message(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.fail:
            raise TimeoutError("possibly accepted by SMTP")
        return "smtp"


def consent(db, monitor, *, configuration=None, enabled=True, verify=True):
    with db.session() as session:
        if verify:
            session.get(User, "owner").email_verified_at = NOW
            session.flush()
        version = session.get(TenderMonitor, monitor["id"]).version
        result = preferences.configure(
            session,
            "owner",
            monitor["id"],
            expected_version=version,
            configuration=configuration or {"delivery": {"email": "immediate" if enabled else "off"}},
            consent=enabled,
            now=NOW,
        )
        session.commit()
        return result


def deliver(db, monitor, mailer, **kwargs):
    with db.session() as session:
        revision = session.get(TenderMonitor, monitor["id"]).email_revision
    return mail.deliver(
        db, settings(), monitor_id=monitor["id"], consent_revision=revision, now=NOW, mailer=mailer, **kwargs
    )


def test_explicit_verified_consent_is_separate_from_profile_and_has_immutable_history(db):
    monitor = create(db, active=True)
    with db.session() as session:
        initial = preferences.view(session, "owner", monitor["id"])
        assert not initial["consent_active"] and initial["configuration"]["delivery"]["email"] == "off"
        with pytest.raises(DomainError):
            preferences.configure(
                session,
                "owner",
                monitor["id"],
                expected_version=1,
                configuration={"delivery": {"email": "immediate"}},
                consent=False,
                now=NOW,
            )
        with pytest.raises(DomainError) as error:
            preferences.configure(
                session,
                "owner",
                monitor["id"],
                expected_version=1,
                configuration={"delivery": {"email": "immediate"}},
                consent=True,
                now=NOW,
            )
        assert error.value.code == "email_verification_required"
    configured = consent(db, monitor)
    assert configured["consent_active"] and configured["revision"] == 1
    with db.session() as session:
        row = session.get(TenderMonitor, monitor["id"])
        assert row.revision == 1 and row.configuration == monitor["configuration"]
        for user in ("peer", "viewer"):
            with pytest.raises(DomainError):
                preferences.view(session, user, monitor["id"])
    off = consent(db, monitor, enabled=False)
    assert not off["consent_active"] and off["revision"] == 2
    with db.session() as session:
        assert (
            session.get(TenderEmailPolicy, (monitor["id"], 1)).configuration["delivery"]["email"]
            == "immediate"
        )
    with db.organization_context("org-b"), db.session() as session:
        assert not list(session.scalars(select(TenderEmailPolicy)))


def test_discovery_then_review_then_material_update_preview_and_email_use_same_versions(db):
    monitor, raw, sender = create(db, active=True), publication(), Mailer()
    consent(db, monitor)
    (dossier,) = ingest(db, monitor, raw)
    with db.session() as session:
        preview = mail.preview(session, settings(), "owner", monitor["id"], now=NOW)
        assert len(preview["items"]) == 1 and preview["items"][0]["kind"] == "new_opportunity"
        href = preview["items"][0]["href"]
    assert deliver(db, monitor, sender) == {"status": "sent", "changes": 1}
    assert href in sender.calls[0][0][2]
    assert "termsCriteria" not in str(sender.calls) and "3 references" not in str(sender.calls)
    decide(db, read(db, dossier))
    changed = revised(raw)
    changed["terms"]["termsCriteria"][0]["description"]["en"] = "5 references required"
    ingest(db, monitor, changed)
    with db.session() as session:
        preview = mail.preview(session, settings(), "owner", monitor["id"], now=NOW)
        assert [item["kind"] for item in preview["items"]] == ["material_update"]
    assert read(db, dossier)["review_state"] == "needs_review"
    assert deliver(db, monitor, sender) == {"status": "sent", "changes": 1}
    assert deliver(db, monitor, sender)["status"] == "no_eligible_changes"
    assert len(sender.calls) == 2


def test_no_email_before_consent_and_reenable_never_replays_old_intents(db):
    monitor, raw, sender = create(db, active=True), publication(), Mailer()
    ingest(db, monitor, raw)
    with db.session() as session:
        assert not list(session.scalars(select(TenderDelivery)))
    consent(db, monitor)
    assert deliver(db, monitor, sender)["status"] == "no_eligible_changes"
    raw2 = deepcopy(raw)
    raw2["id"] = raw2["base"]["id"] = "cc2fdbb3-e727-4f71-8ed3-0eb44f209d85"
    # Same initial publication for a fresh profile creates one new opportunity.
    second = create(db, active=True, key="second")
    consent(db, second)
    ingest(db, second, raw2)
    consent(db, second, enabled=False)
    consent(db, second)
    assert deliver(db, second, sender)["status"] == "no_eligible_changes"
    assert sender.calls == []


@pytest.mark.parametrize(
    "change", ["consent", "membership", "source", "address", "pause", "review", "new_version"]
)
def test_after_claim_rechecks_all_current_gates_before_smtp(db, change):
    monitor, raw, sender = create(db, active=True), publication(), Mailer()
    consent(db, monitor)
    (dossier,) = ingest(db, monitor, raw)

    def revoke():
        if change == "consent":
            consent(db, monitor, enabled=False)
        elif change == "review":
            decide(db, read(db, dossier))
        elif change == "new_version":
            newer = revised(raw)
            newer["terms"]["termsCriteria"][0]["description"]["en"] = "New terms"
            ingest(db, monitor, newer)
        else:
            with db.session() as session:
                if change == "membership":
                    session.execute(
                        update(OrganizationMembership)
                        .where(
                            OrganizationMembership.user_id == "owner",
                            OrganizationMembership.organization_id == "org-a",
                        )
                        .values(role="viewer")
                    )
                elif change == "source":
                    restrict(
                        session,
                        scope="project",
                        target_id=PROJECT,
                        policy_reference="revoke-before-email",
                        now=NOW,
                    )
                elif change == "address":
                    session.get(User, "owner").email = "another@example.test"
                else:
                    session.get(TenderMonitor, monitor["id"]).status = "paused"
                session.commit()

    assert deliver(db, monitor, sender, before_send=revoke)["status"] == "suppressed"
    assert not sender.calls


def test_ambiguous_smtp_is_not_retried_or_duplicated_across_monitors(db):
    first, second = create(db, active=True), create(db, active=True, key="second")
    consent(db, first)
    consent(db, second)
    raw = publication()
    ingest(db, first, raw)
    ingest(db, second, raw)
    sender = Mailer(fail=True)
    assert deliver(db, first, sender)["status"] == "uncertain"
    assert deliver(db, first, sender)["status"] == "no_eligible_changes"
    assert deliver(db, second, sender)["status"] == "no_eligible_changes"
    assert len(sender.calls) == 1


def test_scheduler_uses_private_jobs_and_once_daily_delivery(db):
    monitor, sender = create(db, active=True), Mailer()
    local_time = NOW.astimezone(mail.ZoneInfo("Europe/Zurich")).strftime("%H:%M")
    consent(db, monitor, configuration={"delivery": {"email": "daily_digest", "digest_at": local_time}})
    ingest(db, monitor, publication())
    assert mail.enqueue_due(db, settings(), now=NOW) == {"enqueued": 1}
    assert mail.enqueue_due(db, settings(), now=NOW) == {"enqueued": 0}
    with db.session() as session:
        job = session.scalar(select(Job).where(Job.type == "tender_email"))
        assert job.max_attempts == 1 and job.payload == {"consent_revision": 1}
    assert deliver(db, monitor, sender)["status"] == "sent"
    assert deliver(db, monitor, sender)["status"] == "daily_already_attempted"


def test_cancelled_job_after_claim_does_not_send(db):
    monitor, sender = create(db, active=True), Mailer()
    consent(db, monitor)
    ingest(db, monitor, publication())
    states = iter([True, False])
    assert deliver(db, monitor, sender, checkpoint=lambda: next(states))["status"] == "suppressed"
    assert sender.calls == []


def test_ended_following_suppresses_material_update_but_preserves_review_history(db):
    from helvetic_lens.tender_models import TenderDossier

    monitor, raw, sender = create(db, active=True), publication(), Mailer()
    consent(db, monitor)
    (dossier,) = ingest(db, monitor, raw)
    decide(db, read(db, dossier))
    changed = revised(raw)
    changed["terms"]["termsCriteria"][0]["description"]["en"] = "5 references"
    ingest(db, monitor, changed)
    with db.session() as session:
        session.get(TenderDossier, dossier).following = False
        session.commit()
    assert deliver(db, monitor, sender)["status"] == "no_eligible_changes"
    assert read(db, dossier)["decision"] == "bid" and not sender.calls


@pytest.mark.parametrize(
    "start,expected",
    [
        ("2026-03-29T00:00:00+00:00", "2026-03-29T01:00:00+00:00"),
        ("2026-10-25T00:45:00+00:00", "2026-10-26T01:30:00+00:00"),
    ],
)
def test_tender_digest_reuses_gap_and_repeated_clock_policy(start, expected):
    config = preferences.EmailConfiguration(delivery={"email": "daily_digest", "digest_at": "02:30"})
    assert mail.next_delivery_at(config, mail.datetime.fromisoformat(start)).isoformat() == expected


def test_overnight_quiet_hours_delay_intents_before_scheduler(db):
    start = mail.datetime.fromisoformat("2026-09-12T20:30:00+00:00")
    config = preferences.EmailConfiguration(
        delivery={"email": "immediate", "quiet_hours": {"start": "22:00", "end": "07:00"}}
    )
    assert mail.next_delivery_at(config, start).isoformat() == "2026-09-13T05:00:00+00:00"


def test_reviewing_one_lot_after_claim_does_not_discard_other_eligible_lots(db):
    from test_tender_evidence import many_lots

    monitor, sender = create(db, active=True), Mailer()
    consent(db, monitor)
    dossiers = ingest(db, monitor, many_lots())
    assert len(dossiers) == 12
    result = deliver(db, monitor, sender, before_send=lambda: decide(db, read(db, dossiers[0])))
    assert result == {"status": "sent", "changes": 11}
    assert dossiers[0] not in sender.calls[0][0][2]
    assert all(dossier in sender.calls[0][0][2] for dossier in dossiers[1:])


def test_disabled_mail_service_preserves_pending_items_and_uncertainty_is_visible(db):
    monitor = create(db, active=True)
    consent(db, monitor)
    ingest(db, monitor, publication())
    config = settings()
    config.auth_email_mode = "disabled"
    assert mail.enqueue_due(db, config, now=NOW) == {"enqueued": 0}
    assert mail.deliver(db, config, monitor_id=monitor["id"], consent_revision=1, now=NOW) == {
        "status": "mail_not_live"
    }
    with db.session() as session:
        assert session.scalar(select(TenderDelivery)).state == "pending"
    deliver(db, monitor, Mailer(fail=True))
    with db.session() as session:
        assert preferences.view(session, "owner", monitor["id"])["uncertain_deliveries"] == 1
