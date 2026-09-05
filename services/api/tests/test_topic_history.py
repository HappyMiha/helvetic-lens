"""History coverage must survive batching, retries and organization fan-out bounds."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from test_topic_matching import add_event, create_topic, plan

from helvetic_lens import jobs, monitoring_topics, topic_matching
from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.models import (
    Job,
    Organization,
    OutboxMessage,
    RegulatoryEvent,
    RegulatoryEventState,
    TopicEventMatch,
)


def saved_events(service, count):
    first = add_event(service)
    with service.db.session() as session:
        template = session.get(RegulatoryEvent, first)
        # Equal admission timestamps exercise the ID tiebreaker across every batch.
        admitted = utcnow() - timedelta(minutes=1)
        session.scalar(
            select(RegulatoryEventState).where(RegulatoryEventState.event_id == first)
        ).created_at = admitted
        ids = [first]
        for index in range(1, count):
            event = RegulatoryEvent(
                work_id=template.work_id,
                expression_id=template.expression_id,
                authority=template.authority,
                event_type=template.event_type,
                dedupe_key=f"history:{index}",
                detected_at=template.detected_at,
                source_url=template.source_url,
                provenance_method=template.provenance_method,
                connector=template.connector,
                connector_health="healthy",
                impact="medium",
                evidence_json=template.evidence_json,
            )
            session.add(event)
            session.flush()
            session.add(RegulatoryEventState(event_id=event.id, created_at=admitted))
            ids.append(event.id)
        session.commit()
    return ids


def execute(service, job_id):
    return asyncio.run(service.execute_job(job_id))


def dispatch(service, limit=100):
    sent = []
    with service.db.session() as session:
        jobs.dispatch(
            session, lambda _topic, _queue, payload, _priority: sent.append(payload["job_id"]), limit=limit
        )
        session.commit()
    return sent


def test_yielded_history_does_not_jump_ahead_of_another_waiting_topic(harness):
    client, _, service, _ = harness
    service.settings = service.settings.model_copy(update={"topic_match_backfill_limit": 1})
    saved_events(service, 3)
    first = create_topic(client, key="fair-history-first")["backfill_job"]["id"]
    second = create_topic(client, key="fair-history-second")["backfill_job"]["id"]
    assert dispatch(service, limit=1) == [first]
    assert execute(service, first)["state"] == "queued"
    assert dispatch(service, limit=1) == [second]
    assert execute(service, second)["progress"]["current"] == 1
    assert dispatch(service, limit=1) == [first]


def test_exclusions_and_removed_history_are_not_reported_as_unchecked_matches(harness):
    client, _, service, _ = harness
    service.settings = service.settings.model_copy(update={"topic_match_backfill_limit": 1})
    saved_events(service, 3)
    topic = create_topic(client, exclusions=["naturalisation"])
    job_id = topic["backfill_job"]["id"]
    first = execute(service, job_id)["result"]["data"]
    assert first["excluded"] == 1 and first["remaining"] == 2
    with service.db.session() as session:
        # Remove an unchecked admission, as a pack change/cleanup could.
        state = session.scalar(
            select(RegulatoryEventState).where(RegulatoryEventState.id > first["cursor"]["id"])
        )
        session.delete(state)
        session.commit()
    last = execute(service, job_id)["result"]["data"]
    assert last["status"] == "complete" and last["remaining"] == 0
    assert last["processed"] == last["excluded"] == 2
    assert last["removed_since_capture"] == 1 and last["matched"] == 0


def test_501_events_resume_through_outbox_without_duplicates_or_model_calls(harness):
    client, _, service, model = harness
    ids = saved_events(service, 501)
    topic = create_topic(client)
    job_id = topic["backfill_job"]["id"]
    assert dispatch(service) == [job_id]
    first = execute(service, job_id)
    assert first["state"] == "queued"
    assert first["progress"] == {"current": 500, "total": 501}
    assert first["result"]["data"]["remaining"] == 1
    assert first["attempts"] == 0
    pending = client.get(f"/api/monitoring-topics/{topic['id']}").json()["history_scan"]
    assert pending["status"] == "queued" and pending["processed"] == 500
    assert dispatch(service) == [job_id]
    finished = execute(service, job_id)
    assert finished["state"] == "succeeded"
    assert finished["result"]["data"]["status"] == "complete"
    assert finished["progress"] == {"current": 501, "total": 501}
    assert finished["result"]["data"]["batches"] == 2
    assert execute(service, job_id)["result"] == finished["result"]  # duplicate broker delivery
    with service.db.session() as session:
        assert set(session.scalars(select(TopicEventMatch.event_id))) == set(ids)
        assert session.scalar(select(func.count()).select_from(TopicEventMatch)) == 501
        assert (
            session.scalar(
                select(func.count()).select_from(OutboxMessage).where(OutboxMessage.state == "pending")
            )
            == 0
        )
    assert model.calls == []


def test_failed_batch_rolls_back_matches_and_retry_keeps_checkpoint(harness, monkeypatch):
    client, _, service, _ = harness
    service.settings = service.settings.model_copy(update={"topic_match_backfill_limit": 2})
    saved_events(service, 5)
    topic = create_topic(client)
    job_id = topic["backfill_job"]["id"]
    first = execute(service, job_id)
    original = topic_matching.generate_for_events

    def fail_after_writes(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("simulated worker failure before checkpoint commit")

    monkeypatch.setattr(topic_matching, "generate_for_events", fail_after_writes)
    for _ in range(3):
        failed = execute(service, job_id)
    assert failed["state"] == "failed"
    assert failed["progress"] == first["progress"]
    assert failed["result"] == first["result"]
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(TopicEventMatch)) == 2
    monkeypatch.setattr(topic_matching, "generate_for_events", original)
    recovered = client.post(f"/api/monitoring-topics/{topic['id']}/history-scan").json()
    assert recovered["history_scan"]["job_id"] == job_id
    assert recovered["history_scan"]["processed"] == 2
    assert execute(service, job_id)["progress"]["current"] == 4
    assert execute(service, job_id)["result"]["data"]["matched"] == 5


def test_successful_batches_do_not_exhaust_retry_budget_and_cancel_resumes(harness):
    client, _, service, _ = harness
    service.settings = service.settings.model_copy(update={"topic_match_backfill_limit": 1})
    saved_events(service, 5)
    topic = create_topic(client)
    job_id = topic["backfill_job"]["id"]
    execute(service, job_id)
    with service.db.session() as session:
        jobs.request_cancel(session, job_id)
        session.commit()
    assert execute(service, job_id)["state"] == "cancelled"
    with service.db.session() as session:
        retried = jobs.retry(session, job_id)
        assert retried.progress_current == 1
        session.commit()
    for _ in range(4):
        last = execute(service, job_id)
    assert last["state"] == "succeeded"
    assert last["result"]["data"]["processed"] == last["result"]["data"]["batches"] == 5


def test_revision_change_supersedes_checkpoint_and_resume_uses_new_revision(harness):
    client, _, service, _ = harness
    service.settings = service.settings.model_copy(update={"topic_match_backfill_limit": 1})
    saved_events(service, 3)
    topic = create_topic(client)
    old_job = topic["backfill_job"]["id"]
    execute(service, old_job)
    client.patch(
        f"/api/monitoring-topics/{topic['id']}/status", json={"status": "paused", "expected_revision": 1}
    )
    assert client.post(f"/api/monitoring-topics/{topic['id']}/history-scan").status_code == 409
    superseded = execute(service, old_job)
    assert superseded["result"]["data"]["status"] == "superseded"
    assert superseded["progress"] == {"current": 1, "total": 3}
    resumed = client.patch(
        f"/api/monitoring-topics/{topic['id']}/status", json={"status": "active", "expected_revision": 2}
    ).json()
    assert resumed["history_scan"]["revision"] == 3
    for _ in range(3):
        last = execute(service, resumed["history_scan"]["job_id"])
    assert last["result"]["data"]["processed"] == 3


def test_first_failed_batch_keeps_capture_time_and_excludes_later_admissions(harness, monkeypatch):
    client, _, service, _ = harness
    ids = saved_events(service, 2)
    topic = create_topic(client)
    job_id = topic["backfill_job"]["id"]
    original = topic_matching.generate_for_events
    monkeypatch.setattr(
        topic_matching,
        "generate_for_events",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("first batch failed")),
    )
    failed = execute(service, job_id)
    with service.db.session() as session:
        started = session.get(Job, job_id).started_at
        state = session.scalar(select(RegulatoryEventState).where(RegulatoryEventState.event_id == ids[-1]))
        state.created_at = started + timedelta(seconds=1)
        session.commit()
    monkeypatch.setattr(topic_matching, "generate_for_events", original)
    finished = execute(service, job_id)
    assert finished["result"]["data"]["processed"] == 1
    assert datetime.fromisoformat(finished["result"]["data"]["captured_at"]) == failed["started_at"].replace(
        tzinfo=UTC
    )
    with service.db.session() as session:
        assert list(session.scalars(select(TopicEventMatch.event_id))) == ids[:1]


def test_owner_after_100_organizations_is_matched_and_other_tenant_cannot_resume(harness):
    client, _, service, _ = harness
    event_id = add_event(service)
    with service.db.session(include_all_organizations=True) as session:
        for index in range(101):
            org = Organization(id=f"a-{index:03}", name=f"Earlier {index}", slug=f"earlier-{index}")
            session.add(org)
            session.flush()
            session.add(RegulatoryEventState(organization_id=org.id, event_id=event_id))
        owner = Organization(id="zz-history-owner", name="History owner", slug="history-owner")
        session.add(owner)
        session.flush()
        session.add(RegulatoryEventState(organization_id=owner.id, event_id=event_id))
        session.commit()
    with service.db.organization_context(owner.id):
        with service.db.session() as session:
            topic = monitoring_topics.create_topic(
                session, plan(), idempotency_key="owner-history", actor_user_id=None
            )
        result = execute(service, topic["backfill_job"]["id"])
        assert result["result"]["data"]["matched"] == 1
    assert client.post(f"/api/monitoring-topics/{topic['id']}/history-scan").status_code == 404
    with service.db.session(include_all_organizations=True) as session:
        assert list(session.scalars(select(TopicEventMatch.organization_id))) == [owner.id]


def test_legacy_limited_history_can_be_upgraded_idempotently(harness):
    client, _, service, _ = harness
    saved_events(service, 2)
    topic = create_topic(client)
    with service.db.session() as session:
        legacy = session.get(Job, topic["backfill_job"]["id"])
        legacy.idempotency_key = f"topic-match:{topic['id']}:1"
        legacy.state = "succeeded"
        legacy.result_json = {"status": "bounded_complete", "has_more": True, "processed": 500}
        session.commit()
    limited = client.get(f"/api/monitoring-topics/{topic['id']}").json()["history_scan"]
    assert limited["status"] == "legacy_limited" and limited["remaining"] is None
    restarted = client.post(f"/api/monitoring-topics/{topic['id']}/history-scan").json()
    again = client.post(f"/api/monitoring-topics/{topic['id']}/history-scan").json()
    new_job = restarted["history_scan"]["job_id"]
    assert new_job == again["history_scan"]["job_id"] != legacy.id
    assert execute(service, new_job)["result"]["data"]["processed"] == 2
    reused = client.post(f"/api/monitoring-topics/{topic['id']}/history-scan").json()
    assert reused["history_scan"]["job_id"] == new_job
    assert reused["history_scan"]["status"] == "complete"


def test_checkpoint_for_another_topic_is_rejected(harness):
    client, _, service, _ = harness
    first = create_topic(client, key="checkpoint-owner-one")
    second = create_topic(client, key="checkpoint-owner-two")
    result = execute(service, first["backfill_job"]["id"])["result"]["data"]
    with service.db.session() as session, pytest.raises(DomainError) as error:
        topic_matching.run_backfill(
            session, second["id"], 1, service.settings, checkpoint=result["checkpoint"]
        )
    assert error.value.code == "topic_checkpoint_invalid"
