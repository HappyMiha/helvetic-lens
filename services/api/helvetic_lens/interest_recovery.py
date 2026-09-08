"""Bounded explicit retries of the same failed assessment, with retained receipts."""
from sqlalchemy import func, select

from . import interest_policy, jobs
from .config import DomainError
from .db import utcnow
from .interest_assessment_store import AssessmentStore
from .interest_brief_reader import authorize
from .interest_jobs import TYPE, lock_organization
from .models import InterestEventAssessment, Job, JobStep

MAX_RETRIES = 2


def binding(session, organization_id, record):
    job = session.scalar(select(Job).where(Job.organization_id == organization_id,
        Job.type == TYPE, Job.target_id == record.event_id,
        Job.idempotency_key == "interest-brief:" + record.id))
    payload = (job.payload or {}) if job else {}
    if job is None or (payload.get("assessment_id"), payload.get("input_fingerprint"), payload.get("locale")) != (
            record.id, record.input_fingerprint, record.input_manifest.get("locale")):
        return None, None
    step = session.scalar(select(JobStep).where(JobStep.organization_id == organization_id,
        JobStep.job_id == job.id, JobStep.position == 1))
    return job, step


def describe(session, organization_id, record):
    job, step = binding(session, organization_id, record)
    if job is None or step is None:
        return None
    history = list((step.details or {}).get("brief_retry_history", []))
    return {"job_id": job.id, "job_state": job.state, "attempts_used": record.attempts,
            "attempt_limit": 3, "manual_retries_used": len(history), "manual_retry_limit": MAX_RETRIES,
            "retry_allowed": record.status == "failed" and record.attempts < 3 and len(history) < MAX_RETRIES
                and job.state in {"failed", "cancelled"}, "history": history}


def prepare(session, organization_id, settings, job_id, actor_id=None):
    lock_organization(session, organization_id)
    job = session.scalar(select(Job).where(Job.organization_id == organization_id,
        Job.id == job_id, Job.type == TYPE).with_for_update())
    if job is None:
        raise DomainError("Brief job not found.", 404, "not_found")
    authorize(session, organization_id, job.target_id)
    if job.state not in {"failed", "cancelled"}:
        return job
    record = session.scalar(select(InterestEventAssessment).where(
        InterestEventAssessment.organization_id == organization_id,
        InterestEventAssessment.id == (job.payload or {}).get("assessment_id")))
    if record is None:
        raise DomainError("Saved brief binding is no longer valid.", 409, "interest_inputs_changed")
    bound, step = binding(session, organization_id, record)
    if bound is None or bound.id != job.id or step is None or record.status != "failed":
        raise DomainError("Saved brief binding is no longer valid.", 409, "interest_inputs_changed")
    metadata = describe(session, organization_id, record)
    if not metadata["retry_allowed"]:
        raise DomainError("The saved brief retry allowance is exhausted.", 409, "interest_attempts_exhausted")
    payload = job.payload or {}
    policy = (interest_policy.check(session, organization_id, settings, payload["policy_key"], payload.get("locale"))
              if "policy_key" in payload else interest_policy.read(session, organization_id, settings))
    pending = session.scalar(select(func.count()).select_from(Job).where(Job.organization_id == organization_id,
        Job.type == TYPE, Job.state.not_in(jobs.TERMINAL_STATES)))
    if pending >= policy["max_pending"]:
        raise DomainError("Background brief allowance reached.", 429, "interest_queue_limit")
    receipt = {"requested_at": utcnow().isoformat(), "actor_id": actor_id,
        "assessment_attempts": record.attempts, "previous_state": job.state,
        "previous_error_code": record.error_code, "previous_finished_at": record.finished_at.isoformat() if record.finished_at else None}
    step.details = {**(step.details or {}), "brief_retry_history": [*metadata["history"], receipt]}
    if not AssessmentStore(organization_id).retry(session, record.id, record.input_fingerprint):
        raise DomainError("The saved brief retry allowance is exhausted.", 409, "interest_attempts_exhausted")
    return job
