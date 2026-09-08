"""Offline digests keep source evidence and never silently consume filtered periods.

Real API/queue/database paths, synthetic provider and captured mail only.
"""
import asyncio

import pytest
from sqlalchemy import select
from test_digest_briefs import artifacts, execution, preview, ready
from test_digest_resume import record_mail
from test_relation_runtime import digest_job, local_relation, observation

from helvetic_lens import digests
from helvetic_lens.config import DomainError
from helvetic_lens.digest_interest_copy import MESSAGES as COPY
from helvetic_lens.models import DigestDelivery, DigestPreference, Job

__all__ = ["artifacts", "execution", "local_relation"]


@pytest.mark.parametrize("severities", [[], ["unknown"], ["high", "unknown"]])
def test_offline_worker_sends_sources_once_without_reusing_old_ai(local_relation, monkeypatch, severities):
    client, service, model, _, state = local_relation
    job, saved = digest_job(local_relation)
    with service.db.session() as session:
        preference = session.scalar(select(DigestPreference))
        preference.severities = severities
        session.commit()
    sent = record_mail(monkeypatch)
    state["offline"] = True
    result = asyncio.run(service.execute_job(job["id"]))
    assert result["state"] == "succeeded", result
    with service.db.session() as session:
        delivery = session.get(DigestDelivery, job["target_id"])
        assert delivery.status == "succeeded"
        assert delivery.summary["ai_runtime_unverified"]
        assert not delivery.summary["severity_filter_deferred"]
        event = delivery.summary["events"][0]
        assert event["event_id"] == saved["event_id"] and event["severity"] == "unknown"
        assert event["event_url"] == "/?event=" + saved["event_id"]
        # An old AI citation is not promoted as current relation evidence.
        assert event["impacts"][0]["evidence"] is None
        assert saved["result"]["explanation"] not in str(delivery.summary)
        assert session.scalar(select(DigestPreference.last_sent_at)) is not None
    assert len(sent) == 1 and len(model.calls) == 1
    assert COPY["en-CH"]["runtime_unavailable"] in sent[0][3]
    assert "?event=" + saved["event_id"] in sent[0][3]
    citation = saved["result"]["citations"][0]
    assert client.get(citation["url"]).json()["text"] == citation["quote"]
    asyncio.run(service.execute_job(job["id"]))
    assert len(sent) == 1


def test_filtered_offline_period_is_recoverable_without_false_empty_result(local_relation, monkeypatch):
    _, service, model, _, state = local_relation
    job, saved = digest_job(local_relation)
    sent = record_mail(monkeypatch)
    state["offline"] = True
    with service.db.session() as session:
        # Exercise the explicit retry path without waiting for wall-clock backoff.
        session.get(Job, job["id"]).max_attempts = 1
        user = session.scalar(select(DigestPreference.user_id))
        session.commit()
    summary = asyncio.run(preview(service, user))
    assert summary["ai_runtime_unverified"] and summary["severity_filter_deferred"]
    result = asyncio.run(service.execute_job(job["id"]))
    assert result["state"] == "failed" and not sent
    with service.db.session() as session:
        assert session.get(Job, job["id"]).error_code == "digest_analysis_filter_unavailable"
        assert session.scalar(select(DigestPreference.last_sent_at)) is None
        period = session.get(DigestDelivery, job["target_id"]).period_start
    state["offline"] = False
    service.retry_job(job["id"])
    result = asyncio.run(service.execute_job(job["id"]))
    assert result["state"] == "succeeded", result
    with service.db.session() as session:
        delivery = session.get(DigestDelivery, job["target_id"])
        assert delivery.period_start == period
        assert delivery.summary["events"][0]["event_id"] == saved["event_id"]
        assert delivery.summary["events"][0]["severity"] == "medium"
        assert "ai_runtime_unverified" not in delivery.summary
    assert len(sent) == 1 and len(model.calls) == 1


@pytest.mark.parametrize("initially_offline", [False, True])
def test_runtime_transition_restarts_selection_before_sending(local_relation, monkeypatch, initially_offline):
    _, service, model, _, state = local_relation
    job, _ = digest_job(local_relation)
    with service.db.session() as session:
        session.scalar(select(DigestPreference)).severities = []
        session.commit()
    sent = record_mail(monkeypatch)
    state["offline"] = initially_offline
    captured = observation(service)
    with service.db.session() as session:
        selection = digests.prepare_batch(session, job["target_id"], settings=service.settings, runtime=captured)
    state["offline"] = not initially_offline
    changed = observation(service)
    with pytest.raises(DomainError, match="preparation will restart"):
        digests.deliver(service.db, service.environment_settings, job["target_id"], selection=selection,
                       analysis_settings=service.settings, runtime=changed)
    assert not sent
    with service.db.session() as session:
        restarted = digests.prepare_batch(session, job["target_id"], selection, settings=service.settings, runtime=changed)
        assert restarted["complete"] and restarted["restarts"] == 1
        assert session.scalar(select(DigestPreference.last_sent_at)) is None
    result = digests.deliver(service.db, service.environment_settings, job["target_id"], selection=restarted,
                             analysis_settings=service.settings, runtime=changed)
    assert result["status"] == "succeeded" and len(sent) == 1
    assert bool(result["summary"].get("ai_runtime_unverified")) != initially_offline
    assert len(model.calls) == 1


@pytest.mark.parametrize("locale", ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"])
def test_offline_saved_brief_is_withheld_in_recipient_language(execution, monkeypatch, locale):
    service, user, saved = ready(execution, locale=locale)
    state = execution[4]
    state["runtime"] = {}  # Gateway cannot attest any current model.
    summary = asyncio.run(preview(service, user))
    assert summary["ai_runtime_unverified"]
    brief = summary["events"][0]["brief"]
    assert brief["status"] == "runtime_unverified" and "what_happened" not in brief
    generated, counts = len(state["generated"]), len(state["counts"])
    sent = record_mail(monkeypatch)
    job = service.enqueue_digest_now(user)
    result = asyncio.run(service.execute_job(job["id"]))
    assert result["state"] == "succeeded", result
    assert len(sent) == 1 and f'<html lang="{locale}">' in sent[0][4]
    assert COPY[locale]["runtime_unavailable"] in sent[0][3]
    assert saved["result"]["what_happened"]["text"] not in sent[0][3] + sent[0][4]
    assert len(state["generated"]) == generated and len(state["counts"]) == counts
