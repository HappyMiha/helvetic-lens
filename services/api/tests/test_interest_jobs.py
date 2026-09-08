"""Actual durable state/local gateway with synthetic model approval and replies."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from sqlalchemy import func, select
from test_interest_execution import artifacts, execution

from helvetic_lens import jobs
from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.interest_assessment_store import AssessmentStore
from helvetic_lens.interest_execution import LocalBriefRunner
from helvetic_lens.interest_jobs import TYPE, BriefJobs
from helvetic_lens.models import InterestEventAssessment, Job, OutboxMessage, RegulatoryDocumentVersion

__all__ = ["artifacts", "execution"]


def schedule(value):
    return asyncio.run(value[1].schedule(value[2]))


def perform(value, job_id, worker="synthetic-worker"):
    return asyncio.run(BriefJobs(value[1]).execute(job_id, worker))


def record(value, model, identity):
    with value[0].db.session() as session:
        return session.get(model, identity)


def test_schedule_outbox_execute_service_and_exact_reuse(execution):
    service, runner, _, _, state, *_ = execution
    first = schedule(execution)
    second = schedule(execution)
    assert first == second and first["status"] == "queued"
    assert not state["generated"]
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job).where(Job.type == TYPE)) == 1
        outbox = session.scalar(select(OutboxMessage).where(OutboxMessage.job_id == first["job_id"]))
        assert outbox.payload == {"job_id": first["job_id"]}
        job = session.get(Job, first["job_id"])
        assert job.queue == "ai_background" and job.priority == 2
        assert set(job.payload) == {"assessment_id", "input_fingerprint", "locale"}
    service.model_client = runner.client
    result = asyncio.run(service.execute_job(first["job_id"], "synthetic-worker"))
    assert result["state"] == "succeeded", result
    assert result["steps"][0]["state"] == "succeeded"
    assert result["result"]["id"] == first["id"]
    assert len(state["generated"]) == 1
    assert perform(execution, first["job_id"])["state"] == "succeeded"
    assert schedule(execution)["cached"]
    assert len(state["generated"]) == 1


def test_concurrent_broker_deliveries_generate_once(execution):
    queued = schedule(execution)
    async def run():
        return await asyncio.gather(*(BriefJobs(execution[1]).execute(queued["job_id"], f"worker-{i}") for i in range(4)))
    results = asyncio.run(run())
    assert any(row["state"] == "succeeded" for row in results)
    assert len(execution[4]["generated"]) == 1
    assert record(execution, InterestEventAssessment, queued["id"]).attempts == 1


@pytest.mark.parametrize("stage", ["before", "generate"])
def test_changed_inputs_never_publish_queued_snapshot(execution, stage):
    queued = schedule(execution)
    def change(phase):
        if phase == "generate":
            with execution[0].db.session() as session:
                session.get(RegulatoryDocumentVersion, execution[3]).text += " corrected"
                session.commit()
    if stage == "before":
        change("generate")
    else:
        execution[4]["hook"] = change
    result = perform(execution, queued["job_id"])
    assert result["state"] == "failed", result
    row = record(execution, InterestEventAssessment, queued["id"])
    assert row.status == "superseded" and row.result is None
    assert len(execution[4]["generated"]) == (0 if stage == "before" else 1)


@pytest.mark.parametrize("stage", ["queued", "generate"])
def test_cancel_withdraws_execution_without_publishing(execution, stage):
    queued = schedule(execution)
    def cancel(phase):
        if phase == "generate":
            with execution[0].db.session() as session:
                jobs.request_cancel(session, queued["job_id"])
                session.commit()
    if stage == "queued":
        cancel("generate")
        assert record(execution, InterestEventAssessment, queued["id"]).status == "failed"
    else:
        execution[4]["hook"] = cancel
    result = perform(execution, queued["job_id"])
    assert result["state"] == "cancelled", result
    assert record(execution, InterestEventAssessment, queued["id"]).result is None
    assert len(execution[4]["generated"]) == (0 if stage == "queued" else 1)


def test_heartbeat_cancels_inflight_provider_await(execution, monkeypatch):
    monkeypatch.setattr("helvetic_lens.interest_jobs.HEARTBEAT_SECONDS", .01)
    queued = schedule(execution)
    entered = asyncio.Event()
    async def hook(phase):
        if phase == "generate":
            entered.set()
            await asyncio.Event().wait()
    execution[4]["hook"] = hook
    async def run():
        task = asyncio.create_task(BriefJobs(execution[1]).execute(queued["job_id"], "worker"))
        await asyncio.wait_for(entered.wait(), 10)
        with execution[0].db.session() as session:
            jobs.request_cancel(session, queued["job_id"])
            session.commit()
        return await asyncio.wait_for(task, 5)
    assert asyncio.run(run())["state"] == "cancelled"
    assert record(execution, InterestEventAssessment, queued["id"]).result is None


@pytest.mark.parametrize("same_owner", [False, True])
def test_lost_lease_cannot_finish_new_workers_job(execution, same_owner):
    queued = schedule(execution)
    def hook(phase):
        if phase == "generate":
            with execution[0].db.session() as session:
                row = session.get(Job, queued["job_id"])
                row.lease_owner = "synthetic-worker" if same_owner else "new-worker"
                row.leased_at = utcnow() + timedelta(seconds=1)
                session.commit()
    execution[4]["hook"] = hook
    result = perform(execution, queued["job_id"])
    assert result["state"] == "running" and result["result"] is None
    assert record(execution, InterestEventAssessment, queued["id"]).result is None


def test_crashed_lease_recovers_assessment_and_fences_old_token(execution):
    queued = schedule(execution)
    with execution[0].db.session() as session:
        job = jobs.claim(session, queued["job_id"], "crashed-worker")
        store = AssessmentStore(execution[0].organization_id)
        original = store.claim(session, queued["id"], job.payload["input_fingerprint"])
        job.heartbeat_at = utcnow() - timedelta(minutes=10)
        session.commit()
    with execution[0].db.session() as session:
        assert jobs.reconcile(session, 30)["recovered"] == 1
        session.commit()
    result = perform(execution, queued["job_id"])
    assert result["state"] == "succeeded", result
    with execution[0].db.session() as session:
        assert not store.fail(session, queued["id"], original, "provider_unavailable")
        assert store.get(session, queued["id"]).attempts == 2


def test_transport_retry_delay_and_three_attempt_limit(execution):
    queued = schedule(execution)
    execution[4]["disconnect"] = True
    for attempt in range(1, 4):
        result = perform(execution, queued["job_id"])
        assert result["state"] == ("retrying" if attempt < 3 else "failed"), (attempt, result["error"])
        count = len(execution[4]["requests"])
        perform(execution, queued["job_id"])
        assert len(execution[4]["requests"]) == count
        with execution[0].db.session() as session:
            session.get(Job, queued["job_id"]).available_at = utcnow() - timedelta(seconds=1)
            session.commit()
    assert record(execution, InterestEventAssessment, queued["id"]).attempts == 3
    assert len(execution[4]["generated"]) <= 6
    with execution[0].db.session() as session:
        jobs.retry(session, queued["job_id"])
        session.commit()
    execution[4]["disconnect"] = False
    assert perform(execution, queued["job_id"])["state"] == "failed"
    assert record(execution, InterestEventAssessment, queued["id"]).attempts == 3


@pytest.mark.parametrize("limit", ["MAX_PENDING", "MAX_DAILY"])
def test_admission_quota_rolls_back_assessment_and_outbox(execution, monkeypatch, limit):
    monkeypatch.setattr(f"helvetic_lens.interest_jobs.{limit}", 0)
    with pytest.raises(DomainError) as error:
        schedule(execution)
    assert error.value.code == "interest_queue_limit"
    assert not execution[4]["generated"]
    with execution[0].db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job).where(Job.type == TYPE)) == 0
        assert session.scalar(select(func.count()).select_from(InterestEventAssessment)) == 0
        assert session.scalar(select(func.count()).select_from(OutboxMessage).join(Job).where(Job.type == TYPE)) == 0


def test_unapproved_profile_cannot_enqueue(execution):
    execution[6]["profiles"][0]["status"] = "revoked"
    execution[7]()
    with pytest.raises(DomainError):
        schedule(execution)
    assert not execution[4]["generated"]
    with execution[0].db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job).where(Job.type == TYPE)) == 0


def test_tampered_job_binding_fails_without_contacting_model(execution):
    queued = schedule(execution)
    with execution[0].db.session() as session:
        row = session.get(Job, queued["job_id"])
        row.payload = {**row.payload, "locale": "fr"}
        session.commit()
    count = len(execution[4]["requests"])
    assert perform(execution, queued["job_id"])["state"] == "failed"
    assert len(execution[4]["requests"]) == count


def test_dispatch_does_not_steal_running_lease_or_bypass_backoff(execution):
    queued = schedule(execution)
    sent = []
    with execution[0].db.session() as session:
        job = jobs.claim(session, queued["job_id"], "worker")
        jobs.dispatch(session, lambda *args: sent.append(args))
        session.refresh(job)
        assert job.state == "running" and job.lease_owner == "worker"
        assert not any(row[2]["job_id"] == job.id for row in sent)
        jobs.fail(session, job.id, code="provider_unavailable", detail="Synthetic failure", retry_delay=30)
        message = session.scalar(select(OutboxMessage).where(
            OutboxMessage.job_id == job.id, OutboxMessage.state == "pending"))
        message.available_at = utcnow() - timedelta(seconds=1)
        session.flush()
        jobs.dispatch(session, lambda *args: sent.append(args))
        assert not any(row[2]["job_id"] == job.id for row in sent)
        assert message.available_at == job.available_at
        session.commit()


def test_changed_admission_cancels_stale_job_without_losing_history(execution):
    first = schedule(execution)
    with execution[0].db.session() as session:
        session.get(RegulatoryDocumentVersion, execution[3]).text += " corrected"
        session.commit()
    second = schedule(execution)
    assert second["id"] != first["id"] and second["job_id"] != first["job_id"]
    assert record(execution, Job, first["job_id"]).state == "cancelled"
    assert record(execution, InterestEventAssessment, first["id"]).status == "superseded"
    assert perform(execution, first["job_id"])["state"] == "cancelled"
    assert not execution[4]["generated"]


def test_concurrent_admission_has_one_job_and_one_outbox(execution):
    async def run():
        return await asyncio.gather(*(execution[1].schedule(execution[2]) for _ in range(4)))
    results = asyncio.run(run())
    assert len({row["job_id"] for row in results}) == 1
    with execution[0].db.session() as session:
        assert session.scalar(select(func.count()).select_from(OutboxMessage).join(Job).where(Job.type == TYPE)) == 1
    assert not execution[4]["generated"]


def test_foreign_organization_cannot_claim_or_read_job_even_in_privileged_session(execution, monkeypatch):
    queued = schedule(execution)
    db = execution[0].db
    original = db.session
    # Existing second tenant from the standard fixture; access still needs an
    # explicit predicate even when a dispatcher holds a privileged connection.
    from helvetic_lens.models import Organization
    with db.session(include_all_organizations=True) as session:
        other = Organization(name="Other synthetic organization", slug="brief-other")
        session.add(other)
        session.commit()
        other_id = other.id
    monkeypatch.setattr(db, "session", lambda **kwargs: original(include_all_organizations=True))
    client = LocalBriefRunner(db, other_id, execution[1].client)
    before = len(execution[4]["requests"])
    with pytest.raises(DomainError) as error:
        asyncio.run(BriefJobs(client).execute(queued["job_id"], "foreign-worker"))
    assert error.value.status == 404
    assert len(execution[4]["requests"]) == before
    assert record(execution, Job, queued["job_id"]).state == "queued"


def test_separate_connections_coalesce_simultaneous_admission(execution):
    ready = Barrier(4, timeout=15)
    def hook(phase):
        if phase == "count":
            ready.wait()
    execution[4]["hook"] = hook
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: schedule(execution), range(4)))
    assert len({row["job_id"] for row in results}) == 1
    with execution[0].db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job).where(Job.type == TYPE)) == 1
        assert session.scalar(select(func.count()).select_from(OutboxMessage).join(Job).where(Job.type == TYPE)) == 1
    assert not execution[4]["generated"]


def test_postgres_dispatch_skips_locked_job_without_locking_its_outbox(execution):
    if execution[0].db.engine.dialect.name != "postgresql":
        pytest.skip("Requires actual PostgreSQL row locks")
    queued = schedule(execution)
    sent = []
    def dispatch():
        with execution[0].db.session() as session:
            result = jobs.dispatch(session, lambda *args: sent.append(args))
            session.commit()
            return result
    with execution[0].db.session() as session:
        row = session.scalar(select(Job).where(Job.id == queued["job_id"]).with_for_update())
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(dispatch).result(timeout=5)
        assert not any(item[2]["job_id"] == row.id for item in sent)
        # The skipped dispatch must leave this outbox available to its owner.
        message = session.scalar(select(OutboxMessage).where(OutboxMessage.job_id == row.id).with_for_update(nowait=True))
        assert message.state == "pending"
        session.commit()
    dispatch()
    assert sum(item[2]["job_id"] == queued["job_id"] for item in sent) == 1


def test_exhausted_crash_recovery_closes_unfinished_assessment(execution):
    queued = schedule(execution)
    with execution[0].db.session() as session:
        job = jobs.claim(session, queued["job_id"], "crashed-worker")
        AssessmentStore(execution[0].organization_id).claim(session, queued["id"], job.payload["input_fingerprint"])
        job.attempts = job.max_attempts
        job.heartbeat_at = utcnow() - timedelta(minutes=10)
        session.commit()
    with execution[0].db.session() as session:
        jobs.reconcile(session, 30)
        session.commit()
    assessment = record(execution, InterestEventAssessment, queued["id"])
    assert record(execution, Job, queued["job_id"]).state == "failed"
    assert assessment.status == "failed" and assessment.attempt_key is None and assessment.result is None
