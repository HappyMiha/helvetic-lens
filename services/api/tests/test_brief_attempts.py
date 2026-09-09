"""Attempt evidence survives retry, cancellation and lost worker ownership."""
import asyncio
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import select
from test_interest_execution import artifacts, execution, records, run

from alembic import command
from helvetic_lens import brief_attempts
from helvetic_lens.config import DomainError
from helvetic_lens.models import InterestAssessmentAttempt, InterestEventAssessment

__all__ = ["artifacts", "execution"]


def history(execution, identity):
    with execution[0].db.session() as session:
        return brief_attempts.read(session, execution[0].organization_id, identity)["items"]


def test_failed_repair_then_success_retains_both_attempts_and_cache_does_not_add_one(execution, harness):
    state=execution[4]
    state["invalid"]=2
    with pytest.raises(DomainError):
        run(execution)
    record=records(execution)[0]
    first=history(execution, record.id)
    assert len(first)==1 and first[0]["status"]=="failed"
    assert first[0]["measurement"]["http_attempts_started"]==2
    assert first[0]["measurement"]["measured_input_tokens"]==800
    assert first[0]["measurement"]["reported_output_tokens"] is None
    with execution[0].db.session() as session:
        assert execution[1].store.retry(session, record.id, record.input_fingerprint)
        session.commit()
    state["invalid"]=0
    successful=run(execution)
    assert successful["status"]=="succeeded"
    result=history(execution, record.id)
    assert [row["status"] for row in result]==["succeeded","failed"]
    assert result[1]==first[0]
    assert result[0]["measurement"]["http_attempts_started"]==1
    before=len(state["generated"])
    assert run(execution)["cached"] is True
    assert len(state["generated"])==before and history(execution, record.id)==result
    response=harness[0].get(f"/api/integration-logs/briefs/{record.id}/attempts")
    assert response.status_code==200 and response.json()["items"]==result
    assert "attempt_key" not in response.text and "runtime_binding" not in response.text


@pytest.mark.parametrize("failure", ["cancelled", "timeout"])
def test_interrupted_attempt_preserves_unknown_usage_without_masking_error(execution, failure):
    def interrupt(phase):
        if phase=="generate":
            raise asyncio.CancelledError() if failure=="cancelled" else TimeoutError()
    execution[4]["hook"]=interrupt
    with pytest.raises(asyncio.CancelledError if failure=="cancelled" else DomainError):
        run(execution)
    saved=records(execution)[0]
    row=history(execution,saved.id)[0]
    assert row["status"]=="failed" and row["error_code"]==("cancelled" if failure=="cancelled" else "model_timeout")
    assert row["measurement"]["http_attempts_started"]==1
    assert row["measurement"]["reported_output_tokens"] is None
    assert row["measurement"]["observed_queue_ms"] is None


def test_sample_coverage_rejects_untrusted_fields_and_distinguishes_zero(execution):
    saved=run(execution)
    measured=saved["provenance"]["execution"]["generation_measurements"][0]
    result=brief_attempts.summarize([
        {"prompt_token_measurement":measured},
        {"outcome":"success","usage":{"completion_tokens":0,"secret":"not-copied"},
         "queue_wait_ms":0,"queue_wait_observed":True},
        {"outcome":"success","usage":{"completion_tokens":True},"queue_wait_ms":0}],2,20)
    assert result["reported_output_tokens"]==0 and result["reported_output_requests"]==1
    assert result["observed_queue_ms"]==0 and result["observed_queue_requests"]==1
    assert result["measured_input_requests"]==1
    assert "secret" not in str(result)
    for key in ["http_attempts_started","reported_output_requests","measured_input_requests"]:
        with pytest.raises(ValueError):
            brief_attempts.Measurement.model_validate({**result,key:True})
    with pytest.raises(ValueError):
        brief_attempts.Measurement.model_validate({**result,"reported_output_tokens":None})


def test_old_fenced_attempt_cannot_close_newer_attempt_or_replace_its_measurements(execution):
    saved=run(execution)
    service=execution[0]
    with service.db.organization_context(str(uuid4())), service.db.session() as foreign_session:
        assert list(foreign_session.scalars(select(InterestAssessmentAttempt))) == []
    with service.db.session() as session:
        original=session.scalar(select(InterestAssessmentAttempt))
        original_id,original_usage=original.id,deepcopy(original.measurement)
        record=session.get(InterestEventAssessment,saved["id"])
        # Simulate a retry after an interrupted historical attempt, without changing its identity.
        record.status="failed"
        session.commit()
        assert execution[1].store.retry(session,record.id,record.input_fingerprint)
        new_token=execution[1].store.claim(session,record.id,record.input_fingerprint)
        session.commit()
        assert not execution[1].store.fail(session,record.id,original_id,"cancelled")
        assert not brief_attempts.record(session,service.organization_id,record.id,original_id,original_usage)
        assert not brief_attempts.record(session,str(uuid4()),record.id,new_token,original_usage)
        session.commit()
        assert session.get(InterestAssessmentAttempt,new_token).status=="running"
        assert session.get(InterestAssessmentAttempt,original_id).measurement==original_usage
        with pytest.raises(DomainError):
            brief_attempts.read(session,str(uuid4()),record.id)


def test_diagnostic_write_failure_does_not_discard_valid_ai_result(execution, monkeypatch):
    def unavailable(*args,**kwargs):
        raise RuntimeError("synthetic private connection details")
    monkeypatch.setattr(brief_attempts,"record",unavailable)
    saved=run(execution)
    assert saved["status"]=="succeeded"
    assert history(execution,saved["id"])[0]["measurement"] is None


@pytest.mark.parametrize("exhausted", [False, True])
def test_crashed_worker_retains_unknown_attempt_instead_of_fabricated_usage(execution, exhausted):
    from test_interest_jobs import (
        test_crashed_lease_recovers_assessment_and_fences_old_token,
        test_exhausted_crash_recovery_closes_unfinished_assessment,
    )
    scenario = (test_exhausted_crash_recovery_closes_unfinished_assessment if exhausted
                else test_crashed_lease_recovers_assessment_and_fences_old_token)
    scenario(execution)
    rows = history(execution, records(execution)[0].id)
    assert rows[-1]["status"] == "failed" and rows[-1]["finished_at"] is not None
    assert rows[-1]["measurement"] is None
    assert len(rows) == (1 if exhausted else 2)
    if not exhausted:
        assert rows[0]["status"] == "succeeded" and rows[0]["measurement"]["http_attempts_started"] == 1


def test_attempt_migration_preserves_assessment_and_original_context(execution):
    saved=run(execution)
    service=execution[0]
    with service.db.session() as session:
        context=deepcopy(session.get(InterestEventAssessment,saved["id"]).history_context)
    root=Path(__file__).resolve().parents[1]
    cfg=Config(str(root/"alembic.ini"))
    cfg.set_main_option("script_location",str(root/"alembic"))
    with service.db.engine.begin() as connection:
        cfg.attributes["connection"]=connection
        command.downgrade(cfg,"dd3f478ea10b")
        command.upgrade(cfg,"head")
    with service.db.session() as session:
        record=session.get(InterestEventAssessment,saved["id"])
        assert record.result==saved["result"] and record.history_context==context
        assert brief_attempts.read(session,service.organization_id,record.id)["items"]==[]
