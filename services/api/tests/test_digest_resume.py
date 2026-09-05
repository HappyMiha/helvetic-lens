"""Durable digest preparation yields fairly and resumes without full rescans."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select
from test_digest_periods import recipient, seed_events
from test_topic_history import dispatch

from helvetic_lens import digests, jobs
from helvetic_lens.auth_mail import AuthMailer
from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.impact_inbox import ImpactInboxReader
from helvetic_lens.models import (
    DigestDelivery,
    DigestPreference,
    Job,
    OrganizationMembership,
    OrganizationRelationCandidate,
    RelationCandidate,
    User,
    new_id,
)


def setup_delivery(harness, count=61):
    _, _, service, _ = harness
    end = utcnow()
    specs = [{"id": new_id(), "detected_at": end - timedelta(seconds=i + 1),
              "impact": "high" if i in (1, count - 1) else "low"} for i in range(count)]
    seed_events(harness, specs)
    user_id = recipient(service)
    service.save_digest_preference(user_id, enabled=True, frequency="daily", sources=[], severities=["high"])
    return service.enqueue_digest_now(user_id), user_id, specs


def execute(service, id_):
    return asyncio.run(service.execute_job(id_))


def record_mail(monkeypatch):
    sent = []
    monkeypatch.setattr(AuthMailer, "send_message", lambda *args, **kwargs: (sent.append(args), "test-outbox")[1])
    return sent


def checkpoint(service, job_id):
    with service.db.session() as session:
        return dict(session.get(Job, job_id).payload["checkpoint"])


def test_digest_yield_is_atomic_fair_and_finishes_without_new_model_calls(harness, monkeypatch):
    _, _, service, model = harness
    job, _, specs = setup_delivery(harness)
    sent = record_mail(monkeypatch)
    second_user = recipient(service, "second-digest@example.ch")
    service.save_digest_preference(second_user, enabled=True, frequency="daily", sources=[], severities=["high"])
    second = service.enqueue_digest_now(second_user)
    assert dispatch(service, limit=1) == [job["id"]]
    first = execute(service, job["id"])
    assert first["state"] == "queued" and checkpoint(service, job["id"])["processed"] == 50
    assert sent == [] and first["attempts"] == 0
    assert dispatch(service, limit=1) == [second["id"]]
    assert dispatch(service, limit=1) == [job["id"]]
    final = execute(service, job["id"])
    assert final["state"] == "succeeded"
    cp = checkpoint(service, job["id"])
    assert cp["processed"] == 61 and cp["batches"] == 2 and cp["complete"]
    with service.db.session() as session:
        delivery = session.get(DigestDelivery, job["target_id"])
        assert [e["event_id"] for e in delivery.summary["events"]] == [specs[1]["id"], specs[-1]["id"]]
    execute(service, job["id"])
    assert len(sent) == 1 and model.calls == []


def test_failed_page_rolls_back_cursor_and_cancel_retry_keeps_completed_pages(harness, monkeypatch):
    _, _, service, _ = harness
    job, _, _ = setup_delivery(harness, count=101)
    sent = record_mail(monkeypatch)
    assert execute(service, job["id"])["state"] == "queued"
    before = checkpoint(service, job["id"])
    yield_batch = jobs.yield_batch
    def crash(*_args):
        raise DomainError("Test-only failure before checkpoint commit", 503, "test_interruption")
    monkeypatch.setattr(jobs, "yield_batch", crash)
    assert execute(service, job["id"])["state"] == "retrying"
    assert checkpoint(service, job["id"]) == before
    monkeypatch.setattr(jobs, "yield_batch", yield_batch)
    with service.db.session() as session:
        jobs.request_cancel(session, job["id"])
        session.commit()
    service.retry_job(job["id"])
    assert checkpoint(service, job["id"]) == before
    assert execute(service, job["id"])["state"] == "queued"
    assert checkpoint(service, job["id"])["processed"] == 100
    assert execute(service, job["id"])["state"] == "succeeded"
    assert len(sent) == 1


def test_mail_retry_reuses_completed_selection_and_refreshes_only_selected_ids(harness, monkeypatch):
    _, _, service, _ = harness
    job, _, _ = setup_delivery(harness)
    execute(service, job["id"])
    page = ImpactInboxReader.event_page
    scans = []
    def record_page(self, session, filters, **options):
        scans.append(filters.event_ids)
        return page(self, session, filters, **options)
    monkeypatch.setattr(ImpactInboxReader, "event_page", record_page)
    def fail_mail(*_args, **_kwargs):
        raise DomainError("Test-only SMTP failure", 503, "email_delivery_failed")
    monkeypatch.setattr(AuthMailer, "send_message", fail_mail)
    with service.db.session() as session:
        session.get(Job, job["id"]).max_attempts = 1
        session.commit()
    assert execute(service, job["id"])["state"] == "failed"
    assert checkpoint(service, job["id"])["complete"]
    assert scans[0] is None  # Last preparation page, then bounded recipient refresh.
    scans.clear()
    sent = record_mail(monkeypatch)
    service.retry_job(job["id"])
    assert execute(service, job["id"])["state"] == "succeeded"
    assert scans and all(ids is not None and len(ids) == 2 for ids in scans)
    assert len(sent) == 1


def test_changed_filters_restart_selection_without_mixing_old_results(harness, monkeypatch):
    _, _, service, _ = harness
    job, user_id, specs = setup_delivery(harness)
    sent = record_mail(monkeypatch)
    execute(service, job["id"])
    assert checkpoint(service, job["id"])["event_ids"] == [specs[1]["id"]]
    service.save_digest_preference(user_id, enabled=True, frequency="daily", sources=[], severities=["low"])
    assert execute(service, job["id"])["state"] == "queued"
    cp = checkpoint(service, job["id"])
    assert cp["processed"] == 50 and cp["restarts"] == 1 and specs[1]["id"] not in cp["event_ids"]
    assert execute(service, job["id"])["state"] == "succeeded"
    with service.db.session() as session:
        summary = session.get(DigestDelivery, job["target_id"]).summary
        assert len(summary["events"]) == 50 and summary["truncated"]
        assert all(e["severity"] == "low" for e in summary["events"])
    assert len(sent) == 1


def test_unsubscribe_while_preparing_skips_delivery_without_sending(harness, monkeypatch):
    _, _, service, _ = harness
    job, _, _ = setup_delivery(harness)
    sent = record_mail(monkeypatch)
    execute(service, job["id"])
    with service.db.session() as session:
        preference = session.scalar(select(DigestPreference))
        token = digests.preference_token(service.environment_settings, preference.id)
    service.unsubscribe_digest(token)
    assert execute(service, job["id"])["state"] == "succeeded"
    with service.db.session() as session:
        assert session.get(DigestDelivery, job["target_id"]).status == "skipped"
        assert session.scalar(select(DigestPreference)).last_sent_at is None
    assert sent == []


def test_prepared_selection_rechecks_private_state_and_revoked_admissions(harness, monkeypatch):
    _, _, service, _ = harness
    job, user_id, specs = setup_delivery(harness)
    sent = record_mail(monkeypatch)
    cp = None
    while not cp or not cp["complete"]:
        with service.db.session() as session:
            cp = digests.prepare_batch(session, job["target_id"], cp)
            session.commit()
    with service.db.session() as session:
        ImpactInboxReader(service.organization_id, user_id).set_state(session, specs[1]["id"], "muted")
    with service.db.session() as session:
        candidate = session.scalar(select(RelationCandidate).where(RelationCandidate.event_id == specs[-1]["id"]))
        admission = session.scalar(select(OrganizationRelationCandidate).where(OrganizationRelationCandidate.candidate_id == candidate.id))
        session.delete(admission)
        session.commit()
    result = digests.deliver(service.db, service.environment_settings, job["target_id"], selection=cp)
    assert result["status"] == "skipped" and result["item_count"] == 0 and sent == []


def test_foreign_or_corrupt_checkpoint_is_rejected_without_advancing(harness):
    _, _, service, _ = harness
    job, _, _ = setup_delivery(harness)
    with service.db.session() as session:
        cp = digests.prepare_batch(session, job["target_id"])
        for bad in [{**cp, "organization_id": "foreign"}, {**cp, "event_ids": ["x"] * 52},
                    {**cp, "cursor": {"detected_at": "invalid", "id": "x"}}, {**cp, "processed": -1}]:
            with pytest.raises(DomainError) as error:
                digests.prepare_batch(session, job["target_id"], bad)
            assert error.value.code == "digest_checkpoint_invalid"
        assert session.get(DigestDelivery, job["target_id"]).summary == {}


def test_stale_worker_cannot_send_or_cancel_another_workers_delivery(harness, monkeypatch):
    _, _, service, _ = harness
    job, _, _ = setup_delivery(harness)
    sent = record_mail(monkeypatch)
    with service.db.session() as session:
        jobs.claim(session, job["id"], "new-owner")
        session.commit()
    assert digests.deliver(service.db, service.environment_settings, job["target_id"], job_id=job["id"], worker="old-owner") is None
    with service.db.session() as session:
        owned = session.get(Job, job["id"])
        assert owned.state == "running" and owned.lease_owner == "new-owner" and not owned.cancel_requested
    assert sent == []


@pytest.mark.parametrize("empty", [False, True])
def test_late_delivery_never_rewinds_the_last_sent_watermark(harness, monkeypatch, empty):
    _, _, service, _ = harness
    job, _, _ = setup_delivery(harness)
    record_mail(monkeypatch)
    with service.db.session() as session:
        delivery = session.get(DigestDelivery, job["target_id"])
        latest = digests._aware(delivery.period_end) + timedelta(days=1)
        preference = session.get(DigestPreference, delivery.preference_id)
        preference.last_sent_at = latest
        if empty:
            preference.sources = ["does-not-match"]
        session.commit()
    digests.deliver(service.db, service.environment_settings, job["target_id"])
    with service.db.session() as session:
        assert digests._aware(session.scalar(select(DigestPreference)).last_sent_at) == latest


@pytest.mark.parametrize("change", ["remove_membership", "disable_user"])
def test_completed_preparation_does_not_cache_recipient_authorization(harness, monkeypatch, change):
    _, _, service, _ = harness
    job, user_id, _ = setup_delivery(harness)
    sent = record_mail(monkeypatch)
    cp = None
    while not cp or not cp["complete"]:
        with service.db.session() as session:
            cp = digests.prepare_batch(session, job["target_id"], cp)
            session.commit()
    with service.db.session() as session:
        if change == "remove_membership":
            session.delete(session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == user_id)))
        else:
            session.get(User, user_id).active = False
        session.commit()
    with pytest.raises(DomainError) as error:
        digests.deliver(service.db, service.environment_settings, job["target_id"], selection=cp)
    assert error.value.code == "digest_recipient_inactive" and sent == []


def test_preferences_changed_after_preparation_require_restart_before_sending(harness, monkeypatch):
    _, _, service, _ = harness
    job, user_id, _ = setup_delivery(harness)
    sent = record_mail(monkeypatch)
    cp = None
    while not cp or not cp["complete"]:
        with service.db.session() as session:
            cp = digests.prepare_batch(session, job["target_id"], cp)
            session.commit()
    service.save_digest_preference(user_id, enabled=True, frequency="daily", sources=[], severities=["low"])
    with pytest.raises(DomainError) as error:
        digests.deliver(service.db, service.environment_settings, job["target_id"], selection=cp)
    assert error.value.code == "digest_preferences_changed" and sent == []
    with service.db.session() as session:
        restarted = digests.prepare_batch(session, job["target_id"], cp)
        assert restarted["restarts"] == 1 and restarted["processed"] == 50 and not restarted["complete"]


def test_owned_cancel_request_prevents_email_dispatch(harness, monkeypatch):
    _, _, service, _ = harness
    job, _, _ = setup_delivery(harness)
    sent = record_mail(monkeypatch)
    with service.db.session() as session:
        jobs.claim(session, job["id"], "owner")
        jobs.request_cancel(session, job["id"])
        session.commit()
    with pytest.raises(jobs.JobCancelled):
        digests.deliver(service.db, service.environment_settings, job["target_id"], job_id=job["id"], worker="owner")
    assert sent == []
