"""Cross-tenant admission races, worker deferral and explicit retry capacity."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from test_interest_automation import execute, wake
from test_interest_execution import artifacts, execution
from test_interest_jobs import schedule
from test_interest_recovery import failed, history

from helvetic_lens import jobs
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.db import utcnow
from helvetic_lens.interest_jobs import TYPE, enqueue, lock_organization
from helvetic_lens.models import InterestEventAssessment, Job, Organization, OutboxMessage

__all__ = ["artifacts", "execution"]


def foreign_job(service, state="queued", *, age=0, job_type=TYPE):
    with service.db.session(include_all_organizations=True) as session:
        org = Organization(name="Private organization", slug=str(uuid4()))
        session.add(org)
        session.flush()
        row, _ = jobs.enqueue(session, organization_id=org.id, job_type=job_type,
            target_type="synthetic", target_id="private-event", queue="ai_background",
            idempotency_key=str(uuid4()))
        row.state, row.created_at = state, utcnow() - timedelta(hours=age)
        session.commit()
        return row.id


def totals(service):
    with service.db.session() as session:
        return tuple(session.scalar(select(func.count()).select_from(model))
                     for model in (InterestEventAssessment, Job, OutboxMessage))


@pytest.mark.parametrize("state", ["queued", "dispatched", "running", "retrying", "waiting_for_model"])
def test_foreign_pending_blocks_new_job_without_leaking_or_partial_writes(execution, state):
    service = execution[0]
    service.settings.interest_brief_global_max_pending = 1
    foreign_job(service, state)
    before = totals(service)
    with pytest.raises(DomainError) as error:
        schedule(execution)
    assert error.value.code == "interest_queue_limit"
    assert "Private" not in str(error.value) and "private-event" not in str(error.value)
    assert totals(service) == before
    assert not execution[4]["generated"]


@pytest.mark.parametrize("state", ["succeeded", "failed", "cancelled"])
def test_terminal_jobs_release_pending_but_still_consume_rolling_daily_admission(execution, state):
    service = execution[0]
    service.settings.interest_brief_global_max_daily = 1
    identity = foreign_job(service, state)
    before = totals(service)
    with pytest.raises(DomainError, match="Server background"):
        schedule(execution)
    assert totals(service) == before
    with service.db.session(include_all_organizations=True) as session:
        session.get(Job, identity).created_at = utcnow() - timedelta(hours=25)
        session.commit()
    assert schedule(execution)["job_status"] == "queued"
    # Exact reuse remains possible at full global capacity, without more jobs.
    assert schedule(execution)["job_status"] == "queued"


def test_unrelated_jobs_do_not_consume_brief_capacity(execution):
    execution[0].settings.interest_brief_global_max_pending = 1
    foreign_job(execution[0], job_type="analysis")
    assert schedule(execution)["job_status"] == "queued"


def test_full_host_defers_worker_without_losing_event_then_resumes(execution):
    service = execution[0]
    service.settings.interest_brief_global_max_pending = 1
    other = foreign_job(service)
    identity = wake(execution)
    before = totals(service)
    blocked = execute(service, identity)
    assert blocked["state"] == "queued" and blocked["error"]["code"] == "interest_queue_limit"
    with service.db.session() as session:
        row = session.get(Job, identity)
        assert row.payload["checkpoint"]["position"] == row.attempts == 0
        row.available_at = utcnow() - timedelta(seconds=1)
        session.commit()
    assert totals(service) == before
    with service.db.session(include_all_organizations=True) as session:
        jobs.request_cancel(session, other)
        session.commit()
    assert execute(service, identity)["state"] == "succeeded"
    assert not execution[4]["generated"]


def test_retry_reacquires_pending_capacity_without_resetting_history_or_daily_budget(execution):
    service, queued = failed(execution)
    service.settings.interest_brief_global_max_pending = 1
    service.settings.interest_brief_global_max_daily = 1
    other = foreign_job(service)
    before = totals(service)
    with pytest.raises(DomainError, match="Server background"):
        service.retry_job(queued["job_id"])
    assert history(service, queued["id"])["history"] == []
    assert totals(service) == before
    with service.db.session(include_all_organizations=True) as session:
        jobs.request_cancel(session, other)
        session.commit()
    # More daily jobs than the newly lowered limit: retry is not a new admission.
    assert service.retry_job(queued["job_id"])["state"] == "queued"
    assert len(history(service, queued["id"])["history"]) == 1
    assert totals(service)[1] == before[1]


@pytest.mark.parametrize("field", ["interest_brief_global_max_pending", "interest_brief_global_max_daily"])
@pytest.mark.parametrize("value", [0, -1, 10001])
def test_operator_limits_are_positive_bounded(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_concurrent_retry_and_new_tenant_share_one_remaining_slot(execution):
    service, queued = failed(execution)
    service.settings.interest_brief_global_max_pending = 1
    before_calls = len(execution[4]["requests"])
    with service.db.session(include_all_organizations=True) as session:
        org = Organization(name="Other tenant", slug=str(uuid4()))
        session.add(org)
        session.commit()
        org_id = org.id
    barrier = Barrier(2)

    def retry():
        barrier.wait(timeout=15)
        try:
            return service.retry_job(queued["job_id"])["id"]
        except DomainError as error:
            assert error.code == "interest_queue_limit"
            return None

    def fresh():
        barrier.wait(timeout=15)
        with service.db.organization_context(org_id), service.db.session() as session:
            lock_organization(session, org_id)
            row = InterestEventAssessment(organization_id=org_id, event_id=execution[2],
                input_fingerprint=uuid4().hex, input_manifest={"locale": "en"}, status="queued")
            session.add(row)
            session.flush()
            try:
                result = enqueue(session, org_id, row, "en", settings=service.settings)
            except DomainError as error:
                assert error.code == "interest_queue_limit"
                return None
            session.commit()
            return result["job_id"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        attempts = [pool.submit(retry), pool.submit(fresh)]
        results = [attempt.result(timeout=30) for attempt in attempts]
    assert sum(result is not None for result in results) == 1
    assert len(history(service, queued["id"])["history"]) == int(results[0] is not None)
    with service.db.session(include_all_organizations=True) as session:
        assert session.scalar(select(func.count()).select_from(Job).where(
            Job.type == TYPE, Job.state.not_in(jobs.TERMINAL_STATES))) == 1
    assert len(execution[4]["requests"]) == before_calls


def test_concurrent_organizations_cannot_overbook_and_rollback_releases_capacity(execution):
    service, _, event_id = execution[:3]
    service.settings.interest_brief_global_max_pending = 3
    service.settings.interest_brief_global_max_daily = 3
    with service.db.session(include_all_organizations=True) as session:
        orgs = [Organization(name="Concurrent private tenant", slug=str(uuid4())) for _ in range(8)]
        session.add_all(orgs)
        session.commit()
        org_ids = [row.id for row in orgs]

    def reserve(org_id, *, rollback=False):
        with service.db.organization_context(org_id), service.db.session() as session:
            lock_organization(session, org_id)
            row = InterestEventAssessment(organization_id=org_id, event_id=event_id,
                input_fingerprint=uuid4().hex, input_manifest={"locale": "en"}, status="queued")
            session.add(row)
            session.flush()
            try:
                result = enqueue(session, org_id, row, "en", settings=service.settings)
            except DomainError as error:
                assert error.code == "interest_queue_limit"
                return None
            session.rollback() if rollback else session.commit()
            return result

    assert reserve(org_ids[0], rollback=True)
    barrier = Barrier(len(org_ids))

    def concurrent(org_id):
        barrier.wait(timeout=15)
        return reserve(org_id)

    with ThreadPoolExecutor(max_workers=len(org_ids)) as pool:
        results = list(pool.map(concurrent, org_ids))
    accepted = [row for row in results if row]
    assert len(accepted) == 3
    with service.db.session(include_all_organizations=True) as session:
        for model in (InterestEventAssessment, Job, OutboxMessage):
            assert session.scalar(select(func.count()).select_from(model).where(
                model.organization_id.in_(org_ids))) == 3
    # The temporary global aggregate override must not disable tenant isolation.
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job).where(Job.organization_id.in_(org_ids))) == 0
    # Completion frees pending slots, but the global daily limit still prevents
    # another tenant from creating a fresh admission in the same rolling day.
    with service.db.session(include_all_organizations=True) as session:
        for row in session.scalars(select(Job).where(Job.organization_id.in_(org_ids))):
            row.state = "succeeded"
        session.commit()
    assert reserve(org_ids[-1]) is None
