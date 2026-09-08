"""Public retry must preserve failure evidence and cannot reset AI budgets."""
import asyncio

import pytest
from sqlalchemy import select
from test_interest_automation import enable
from test_interest_execution import artifacts, execution
from test_interest_jobs import perform, record, schedule
from test_interest_policy import save

from helvetic_lens.config import DomainError
from helvetic_lens.interest_recovery import describe
from helvetic_lens.models import InterestEventAssessment, Job, JobStep

__all__ = ["artifacts", "execution"]


def failed(execution):
    service = enable(execution)
    queued = schedule(execution)
    execution[4]["invalid"] = 99
    result = perform(execution, queued["job_id"])
    assert result["state"] == "failed", result
    return service, queued


def history(service, identity):
    with service.db.session() as session:
        return describe(session, service.organization_id, session.get(InterestEventAssessment, identity))


def test_explicit_retry_preserves_failure_and_reuses_job_without_immediate_inference(execution):
    service, queued = failed(execution)
    before = len(execution[4]["requests"])
    old = record(execution, InterestEventAssessment, queued["id"])
    retried = service.retry_job(queued["job_id"], actor_id="synthetic-admin")
    assert retried["state"] == "queued" and retried["id"] == queued["job_id"]
    assert len(execution[4]["requests"]) == before
    service.retry_job(queued["job_id"], actor_id="second-admin")
    saved = history(service, queued["id"])
    assert len(saved["history"]) == 1
    assert saved["history"][0]["previous_error_code"] == old.error_code
    assert saved["history"][0]["actor_id"] == "synthetic-admin"
    execution[4]["invalid"] = 0
    assert perform(execution, queued["job_id"])["state"] == "succeeded"
    response = asyncio.run(service.read_interest_brief(execution[2]))
    assert response["status"] == "available"
    assert response["recovery"]["history"] == saved["history"]
    assert response["recovery"]["attempts_used"] == 2


def test_retry_cannot_reset_cumulative_assessment_or_manual_limits(execution):
    service, queued = failed(execution)
    for attempt in (2, 3):
        assert service.retry_job(queued["job_id"])["state"] == "queued"
        assert perform(execution, queued["job_id"])["state"] == "failed"
        assert record(execution, InterestEventAssessment, queued["id"]).attempts == attempt
    before = len(execution[4]["requests"])
    with pytest.raises(DomainError) as error:
        service.retry_job(queued["job_id"])
    assert error.value.code == "interest_attempts_exhausted"
    assert len(execution[4]["requests"]) == before
    assert len(history(service, queued["id"])["history"]) == 2
    assert record(execution, Job, queued["job_id"]).state == "failed"


def test_policy_change_blocks_retry_without_erasing_failure(execution):
    from uuid import uuid4

    from helvetic_lens.interest_requests import enqueue
    service = enable(execution)
    save(service, enabled=True)
    with service.db.session() as session:
        response = enqueue(session, service.organization_id, service.settings, execution[2], "en", uuid4())
        session.commit()
    admitted = asyncio.run(service.execute_job(response["job"]["id"]))
    outcome = admitted["result"]["data"]["outcomes"][0]
    execution[4]["invalid"] = 99
    assert perform(execution, outcome["job_id"])["state"] == "failed"
    save(service, enabled=False)
    with pytest.raises(DomainError) as error:
        service.retry_job(outcome["job_id"])
    assert error.value.code == "interest_policy_changed"
    assert history(service, outcome["assessment_id"])["history"] == []


def test_retry_respects_pending_generation_allowance(execution):
    from test_interest_automation import second_event
    service, queued = failed(execution)
    save(service, max_pending=1)
    other = second_event(execution)
    asyncio.run(execution[1].schedule(other))
    with pytest.raises(DomainError) as error:
        service.retry_job(queued["job_id"])
    assert error.value.code == "interest_queue_limit"
    assert history(service, queued["id"])["history"] == []


def test_http_retry_is_queued_even_in_inline_mode(execution, harness):
    service, queued = failed(execution)
    before = len(execution[4]["requests"])
    response = harness[0].post(f"/api/jobs/{queued['job_id']}/retry")
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "queued"
    assert len(execution[4]["requests"]) == before


def test_concurrent_postgres_retries_have_one_receipt(execution):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from helvetic_lens import jobs
    from helvetic_lens.interest_recovery import prepare
    service = execution[0]
    if service.db.engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL retry row lock")
    _, queued = failed(execution)
    barrier = Barrier(2)
    def retry(actor):
        barrier.wait(timeout=10)
        with service.db.session() as session:
            prepare(session, service.organization_id, service.settings, queued["job_id"], actor)
            value = jobs.retry(session, queued["job_id"])
            session.commit()
            return value.state
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(retry, ["first", "second"])) == ["queued", "queued"]
    assert len(history(service, queued["id"])["history"]) == 1
    with service.db.session() as session:
        assert len(list(session.scalars(select(JobStep).where(JobStep.job_id == queued["job_id"])))) == 1
