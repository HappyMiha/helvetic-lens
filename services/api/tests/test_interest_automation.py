"""Matching → transactional outbox → measured admission → saved shared brief."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import delete, func, select
from test_interest_execution import artifacts, execution
from test_topic_history import execute, saved_events
from test_topic_live import enqueue
from test_topic_matching import create_topic

from helvetic_lens import jobs, topic_matching
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.db import utcnow
from helvetic_lens.interest_automation import enqueue_after_matching
from helvetic_lens.interest_jobs import TYPE as GENERATION
from helvetic_lens.models import (
    InterestEventAssessment,
    Job,
    Organization,
    OutboxMessage,
    RegulatoryEvent,
    RegulatoryEventState,
)

__all__ = ["artifacts", "execution"]


def enable(value):
    service, runner = value[:2]
    service.settings.interest_brief_auto_enabled = True
    service.model_client = runner.client
    return service


def wake(value, ids=None, trigger="synthetic-trigger"):
    service = enable(value)
    with service.db.session() as session:
        result = enqueue_after_matching(session, service.settings, ids or [value[2]], trigger)
        session.commit()
    return result["job_id"]


def record(service, identity):
    with service.db.session() as session:
        return session.get(Job, identity)


def test_matching_outbox_admission_generation_and_reader(execution):
    service = enable(execution)
    matching_id, _ = enqueue(service, execution[2])
    finished = execute(service, matching_id)
    assert finished["state"] == "succeeded", finished
    admission_id = finished["result"]["data"]["brief_admission"]["job_id"]
    assert not execution[4]["requests"]  # Matching never contacts a model.
    with service.db.session() as session:
        message = session.scalar(select(OutboxMessage).where(OutboxMessage.job_id == admission_id))
        assert message.payload == {"job_id": admission_id}
        sent = []
        jobs.dispatch(session, lambda _type, _queue, payload, _priority: sent.append(payload["job_id"]))
        session.commit()
        assert admission_id in sent
    admitted = execute(service, admission_id)
    assert admitted["state"] == "succeeded", admitted
    outcome = admitted["result"]["data"]["outcomes"][0]
    assert outcome["status"] == "queued" and not execution[4]["generated"]
    generated = execute(service, outcome["job_id"])
    assert generated["state"] == "succeeded", generated
    assert len(execution[4]["generated"]) == 1
    read = asyncio.run(service.read_interest_brief(execution[2]))
    assert read["status"] == "available" and read["assessment_id"] == outcome["assessment_id"]
    again = execute(service, wake(execution, trigger="another-matching-batch"))
    assert again["result"]["data"]["outcomes"][0]["cached"]
    assert len(execution[4]["generated"]) == 1
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job).where(Job.type == GENERATION)) == 1


def test_backfill_admits_every_batch_atomically_without_ai(harness):
    _, _, service, model = harness
    service.settings.interest_brief_auto_enabled = True
    service.settings.topic_match_backfill_limit = 2
    ids = saved_events(service, 5)
    topic = create_topic(harness[0])
    with service.db.session() as session:
        revision = 1
        first = topic_matching.run_backfill(session, topic["id"], revision, service.settings)
        assert first["brief_admission"]["events"] == 2
        first_id = first["brief_admission"]["job_id"]
        session.rollback()
        assert session.get(Job, first_id) is None
    checkpoint, selected = None, []
    while True:
        with service.db.session() as session:
            result = topic_matching.run_backfill(session, topic["id"], revision, service.settings,
                                                checkpoint=checkpoint)
            child = session.get(Job, result["brief_admission"]["job_id"])
            selected.extend(child.payload["event_ids"])
            session.commit()
        checkpoint = result["checkpoint"]
        if not result["has_more"]:
            break
    assert set(selected) == set(ids) and len(selected) == len(ids)
    assert model.calls == []


def test_disabled_policy_and_replayed_trigger_do_not_create_extra_work(execution):
    service = execution[0]
    with service.db.session() as session:
        assert enqueue_after_matching(session, service.settings, [execution[2]], "off") is None
        service.settings.interest_brief_auto_enabled = True
        first = enqueue_after_matching(session, service.settings, [execution[2]], "same")
        again = enqueue_after_matching(session, service.settings, [execution[2]], "same")
        assert first["job_id"] == again["job_id"] and again["reused"]
        session.rollback()
    assert not execution[4]["requests"]


@pytest.mark.parametrize("change", ["disabled", "locale", "payload", "revoked", "approval"])
def test_queued_admission_rechecks_policy_scope_and_binding(execution, change):
    identity = wake(execution)
    service = execution[0]
    if change == "disabled":
        service.settings.interest_brief_auto_enabled = False
    elif change == "locale":
        service.settings.interest_brief_auto_locale = "de"
    elif change == "approval":
        execution[5]["outcome"] = "fail"
        execution[7]()
    else:
        with service.db.session() as session:
            if change == "revoked":
                session.execute(delete(RegulatoryEventState).where(RegulatoryEventState.event_id == execution[2]))
            else:
                row = session.get(Job, identity)
                row.payload = {**row.payload, "event_ids": ["different-saved-event"]}
            session.commit()
    result = execute(service, identity)
    assert result["state"] in {"failed", "succeeded"}, result
    if change == "revoked":
        assert result["result"]["data"]["outcomes"][0]["error_code"] == "not_found"
    else:
        assert result["state"] == "failed", result
    assert not execution[4]["generated"] and not execution[4]["counts"]
    if change != "approval":
        assert not execution[4]["requests"]


def test_queue_allowance_defers_without_losing_cursor(execution, monkeypatch):
    identity = wake(execution)
    service = execution[0]
    monkeypatch.setattr("helvetic_lens.interest_jobs.MAX_PENDING", 0)
    blocked = execute(service, identity)
    assert blocked["state"] == "queued" and blocked["error"]["code"] == "interest_queue_limit", blocked
    row = record(service, identity)
    assert row.payload["checkpoint"]["position"] == row.attempts == 0
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(InterestEventAssessment)) == 0
        row = session.get(Job, identity)
        row.available_at = utcnow() - timedelta(seconds=1)
        session.commit()
    monkeypatch.setattr("helvetic_lens.interest_jobs.MAX_PENDING", 4)
    assert execute(service, identity)["state"] == "succeeded"
    assert not execution[4]["generated"]


def test_foreign_privileged_admission_is_rejected_before_runtime(execution):
    service = enable(execution)
    with service.db.session(include_all_organizations=True) as session:
        other = Organization(name="Other", slug="other-brief-auto")
        session.add(other)
        session.commit()
    with service.db.organization_context(other.id), service.db.session(include_all_organizations=True) as session:
        with pytest.raises(DomainError):
            enqueue_after_matching(session, service.settings, [execution[2]], "foreign")
    assert not execution[4]["requests"]


def test_duplicate_delivery_coalesces_measured_admission(execution):
    identity = wake(execution)
    async def run():
        return await asyncio.gather(*(execution[0].execute_job(identity, f"worker-{i}") for i in range(4)))
    results = asyncio.run(run())
    assert any(result["state"] == "succeeded" for result in results)
    with execution[0].db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job).where(Job.type == GENERATION)) == 1
    assert len(execution[4]["counts"]) == 1 and not execution[4]["generated"]


def test_operator_locale_is_strict():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Settings(_env_file=None, interest_brief_auto_locale="xx")


def second_event(value):
    service = enable(value)
    with service.db.session() as session:
        original = session.get(RegulatoryEvent, value[2])
        other = RegulatoryEvent(**{key: getattr(original, key) for key in (
            "work_id", "expression_id", "document_version_id", "authority", "event_type",
            "source_url", "provenance_method", "connector", "connector_health", "evidence_json", "detected_at")},
            dedupe_key="synthetic-auto-second")
        session.add(other)
        session.flush()
        session.add(RegulatoryEventState(event_id=other.id))
        session.flush()
        topic_matching.generate_for_events(session, [other], service.settings)
        session.commit()
        return other.id


def test_limited_event_is_audited_then_later_event_admitted(execution):
    ids = sorted([execution[2], second_event(execution)])
    identity = wake(execution, ids)
    service = execution[0]
    with service.db.session() as session:
        session.execute(delete(RegulatoryEventState).where(RegulatoryEventState.event_id == ids[0]))
        session.commit()
    first = execute(service, identity)
    assert first["state"] == "queued" and first["progress"]["current"] == 1, first
    assert not execution[4]["requests"]
    last = execute(service, identity)
    assert last["state"] == "succeeded", last
    data = last["result"]["data"]
    assert data["limited"] == data["admitted"] == 1
    assert [row["event_id"] for row in data["outcomes"]] == ids
    assert data["outcomes"][0]["error_code"] == "not_found"
    assert data["outcomes"][1]["status"] == "queued"
    assert not execution[4]["generated"]


@pytest.mark.parametrize("change", ["cancel", "new_owner", "same_owner", "disable"])
def test_admission_lease_and_policy_checked_after_measurement(execution, change):
    identity = wake(execution)
    service = execution[0]
    def hook(phase):
        if phase != "count":
            return
        with service.db.session() as session:
            row = session.get(Job, identity)
            if change == "cancel":
                jobs.request_cancel(session, identity)
            elif change == "disable":
                service.settings.interest_brief_auto_enabled = False
            else:
                row.lease_owner = "inline" if change == "same_owner" else "new-owner"
                row.leased_at = utcnow() + timedelta(seconds=1)
            session.commit()
    execution[4]["hook"] = hook
    result = execute(service, identity)
    expected = "cancelled" if change == "cancel" else "failed" if change == "disable" else "running"
    assert result["state"] == expected, result
    assert not execution[4]["generated"]
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job).where(Job.type == GENERATION)) == 0


def test_crash_after_admission_reuses_job_before_advancing_cursor(execution):
    identity = wake(execution)
    service = execution[0]
    # The reserved generation survives a worker dying before its cursor commit.
    reserved = asyncio.run(execution[1].schedule(execution[2]))
    with service.db.session() as session:
        row = jobs.claim(session, identity, "dead-worker")
        row.heartbeat_at = utcnow() - timedelta(minutes=10)
        session.commit()
        jobs.reconcile(session, 30)
        session.commit()
        session.get(Job, identity).available_at = utcnow() - timedelta(seconds=1)
        session.commit()
    result = execute(service, identity)
    assert result["state"] == "succeeded", result
    assert result["result"]["data"]["outcomes"][0]["job_id"] == reserved["job_id"]
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job).where(Job.type == GENERATION)) == 1
    assert not execution[4]["generated"]


def test_heartbeat_cancels_blocked_measurement(execution, monkeypatch):
    monkeypatch.setattr("helvetic_lens.interest_automation.HEARTBEAT_SECONDS", .01)
    identity = wake(execution)
    entered = asyncio.Event()
    async def hook(phase):
        if phase == "count":
            entered.set()
            await asyncio.Event().wait()
    execution[4]["hook"] = hook
    async def run():
        task = asyncio.create_task(execution[0].execute_job(identity))
        await asyncio.wait_for(entered.wait(), 10)
        with execution[0].db.session() as session:
            jobs.request_cancel(session, identity)
            session.commit()
        return await asyncio.wait_for(task, 5)
    result = asyncio.run(run())
    assert result["state"] == "cancelled", result
    assert not execution[4]["counts"] and not execution[4]["generated"]


def test_failed_saved_answer_is_not_regenerated_by_another_matching_batch(execution):
    execution[4]["invalid"] = 2
    with pytest.raises(DomainError):
        asyncio.run(execution[1].run(execution[2]))
    before = len(execution[4]["generated"]), len(execution[4]["counts"])
    result = execute(execution[0], wake(execution))
    assert result["state"] == "succeeded", result
    data = result["result"]["data"]
    assert data["limited"] == 1 and data["admitted"] == 0
    assert data["outcomes"][0]["status"] == "failed"
    assert data["outcomes"][0]["error_code"]
    assert (len(execution[4]["generated"]), len(execution[4]["counts"])) == before


def test_partial_batch_cancel_retry_preserves_committed_outcomes(execution):
    identity = wake(execution, [execution[2], second_event(execution)])
    service = execution[0]
    first = execute(service, identity)
    assert first["state"] == "queued" and first["progress"]["current"] == 1
    with service.db.session() as session:
        jobs.request_cancel(session, identity)
        session.commit()
        row = jobs.retry(session, identity)
        assert row.progress_current == 1
        session.commit()
    last = execute(service, identity)
    assert last["state"] == "succeeded"
    data = last["result"]["data"]
    assert len(data["outcomes"]) == data["position"] == data["admitted"] == 2
    assert data["outcomes"][0] == first["result"]["data"]["outcomes"][0]
    assert not execution[4]["generated"]
