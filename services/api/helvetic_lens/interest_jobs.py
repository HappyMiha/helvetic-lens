"""Durable, fenced local relevance-brief execution on the existing outbox.

Internal measured admission only. Matching policy and public request/read routes
are separate: neither importing this module nor reading a feed schedules AI.
"""

import asyncio
from datetime import UTC, timedelta

from sqlalchemy import func, select, update

from . import jobs
from .config import DomainError
from .db import utcnow
from .interest_assessment_store import AssessmentStore
from .interest_policy import MAX_DAILY, MAX_PENDING
from .models import InterestEventAssessment, Job, Organization

TYPE = "interest_event_brief"
HEARTBEAT_SECONDS = 2
TRANSIENT = frozenset({"provider_unavailable", "model_timeout", "model_runtime_unavailable",
                       "token_budget_unavailable", "model_transport_error", "model_unreachable",
                       "model_budget_exhausted"})


def _lease(job):
    return (job.lease_owner, job.attempts,
            job.leased_at.replace(tzinfo=UTC) if job.leased_at else None)


def lock_organization(session, organization_id):
    # One short serialization point also works with SQLite's deferred writes.
    changed = session.execute(update(Organization).where(Organization.id == organization_id)
                              .values(id=Organization.id))
    if changed.rowcount != 1:
        raise DomainError("Organization unavailable.", 404, "not_found")


def close_unfinished(session, job):
    """Terminal job transitions withdraw their exact unfinished assessment too."""
    payload = job.payload or {}
    if (job.type != TYPE or job.state not in {"failed", "cancelled"}
            or job.idempotency_key != f"interest-brief:{payload.get('assessment_id')}"):
        return
    record = session.scalar(select(InterestEventAssessment).where(
        InterestEventAssessment.id == payload.get("assessment_id"),
        InterestEventAssessment.organization_id == job.organization_id,
        InterestEventAssessment.event_id == job.target_id,
        InterestEventAssessment.input_fingerprint == payload.get("input_fingerprint"),
    ))
    if (record is None or record.status not in {"queued", "running"}
            or record.input_manifest.get("locale") != payload.get("locale")):
        return
    changed_input = job.error_code in {"interest_inputs_changed", "interest_not_current", "interest_evidence_unavailable"}
    record.status = "superseded" if changed_input else "failed"
    record.error_code = "cancelled" if job.state == "cancelled" else "provider_unavailable"
    record.attempt_key, record.finished_at = None, utcnow()


def enqueue(session, organization_id, record, locale, *, settings=None, policy_key=None):
    """Caller holds the org lock; admission, assessment and outbox commit together."""
    if record.organization_id != organization_id or record.status != "queued":
        raise DomainError("Assessment is not eligible for scheduling.", 409, "interest_not_current")
    key = f"interest-brief:{record.id}"
    existing = session.scalar(select(Job).where(Job.organization_id == organization_id,
                                               Job.idempotency_key == key))
    if existing:
        return {"id": record.id, "job_id": existing.id, "status": record.status,
                "job_status": existing.state, "cached": False}
    for stale in session.scalars(select(Job).join(InterestEventAssessment,
            Job.idempotency_key == "interest-brief:" + InterestEventAssessment.id).where(
        Job.organization_id == organization_id, Job.type == TYPE, Job.target_id == record.event_id,
        Job.state.not_in(jobs.TERMINAL_STATES), InterestEventAssessment.organization_id == organization_id,
        InterestEventAssessment.status == "superseded").with_for_update()):
        jobs.request_cancel(session, stale.id)
    scope = (Job.organization_id == organization_id, Job.type == TYPE)
    pending = session.scalar(select(func.count()).select_from(Job).where(
        *scope, Job.state.not_in(jobs.TERMINAL_STATES)))
    daily = session.scalar(select(func.count()).select_from(Job).where(
        *scope, Job.created_at >= utcnow() - timedelta(hours=24)))
    from .interest_policy import check, read
    policy = (check(session, organization_id, settings, policy_key, locale) if policy_key
              else read(session, organization_id, settings) if settings else
              {"max_pending": MAX_PENDING, "max_daily": MAX_DAILY})
    if pending >= min(policy["max_pending"], MAX_PENDING) or daily >= min(policy["max_daily"], MAX_DAILY):
        raise DomainError("Background brief allowance reached; saved source evidence remains available.",
                          429, "interest_queue_limit")
    job, _ = jobs.enqueue(session, organization_id=organization_id, job_type=TYPE,
        target_type="regulatory_event", target_id=record.event_id, queue="ai_background",
        idempotency_key=key, priority=2, max_attempts=3,
        payload={"assessment_id": record.id, "input_fingerprint": record.input_fingerprint,
                 "locale": locale, **({"policy_key": policy_key} if policy_key else {})}, steps=[("Generate and validate shared relevance brief", {})])
    return {"id": record.id, "job_id": job.id, "status": record.status,
            "job_status": job.state, "cached": False}


class BriefJobs:
    def __init__(self, runner):
        self.runner, self.db, self.organization_id = runner, runner.db, runner.organization_id
        self.store = AssessmentStore(self.organization_id)

    def _job(self, session, job_id):
        return session.scalar(select(Job).where(Job.id == job_id,
            Job.organization_id == self.organization_id, Job.type == TYPE).with_for_update())

    def _read(self, job_id):
        with self.db.session() as session:
            job = self._job(session, job_id)
            if job is None:
                raise DomainError("Brief job not found.", 404, "not_found")
            return jobs.serialize(session, job)

    async def execute(self, job_id, worker):
        with self.db.organization_context(self.organization_id):
            return await self._execute(job_id, worker)

    async def _execute(self, job_id, worker):
        with self.db.session() as session:
            lock_organization(session, self.organization_id)
            job = self._job(session, job_id)
            if job is None:
                raise DomainError("Brief job not found.", 404, "not_found")
            if job.available_at.replace(tzinfo=UTC) > utcnow():
                return jobs.serialize(session, job)
            job = jobs.claim(session, job_id, worker)
            if job is None:
                session.commit()
                return self._read(job_id)
            lease = _lease(job)
            payload, event_id = dict(job.payload or {}), job.target_id
            session.commit()

        def guard(session):
            lock_organization(session, self.organization_id)
            current = self._job(session, job_id)
            if (current is None or current.state != "running" or current.cancel_requested
                    or _lease(current) != lease):
                raise jobs.JobCancelled()
            if "policy_key" in payload:
                from .interest_policy import check
                check(session, self.organization_id, self.runner.client.settings,
                      payload["policy_key"], payload.get("locale"))
            return current

        async def heartbeat():
            while True:
                await asyncio.sleep(HEARTBEAT_SECONDS)
                with self.db.session() as session:
                    current = guard(session)
                    current.heartbeat_at = current.updated_at = utcnow()
                    session.commit()

        task = pulse = None
        try:
            with self.db.session() as session:
                guard(session)
                record = self.store.get(session, payload.get("assessment_id"))
                if (set(payload) not in ({"assessment_id", "input_fingerprint", "locale"},
                                        {"assessment_id", "input_fingerprint", "locale", "policy_key"})
                        or record is None or record.event_id != event_id
                        or record.input_fingerprint != payload["input_fingerprint"]
                        or record.input_manifest.get("locale") != payload["locale"]
                        or job.idempotency_key != f"interest-brief:{record.id}"):
                    raise DomainError("Queued brief binding is invalid.", 409, "interest_job_invalid")
                if record.status == "running" and job.attempts > 1:
                    # A recovered durable lease fences the previous assessment token.
                    self.store.fail(session, record.id, record.attempt_key, "provider_unavailable")
                    session.refresh(record)
                if record.status == "failed" and not self.store.retry(session, record.id, record.input_fingerprint):
                    raise DomainError("Brief generation attempts exhausted.", 409, "interest_attempts_exhausted")
                jobs.progress(session, job_id, current=0, step_position=1, step_state="running")
                session.commit()
            task = asyncio.create_task(self.runner.run(event_id, locale=payload["locale"],
                expected=(payload["assessment_id"], payload["input_fingerprint"]), guard=guard))
            pulse = asyncio.create_task(heartbeat())
            done, _ = await asyncio.wait({task, pulse}, return_when=asyncio.FIRST_COMPLETED)
            if pulse in done:
                await pulse
            result = await task
            if result["status"] != "succeeded":
                raise DomainError("The queued brief was not published.", 409, "interest_not_published")
            with self.db.session() as session:
                guard(session)
                jobs.progress(session, job_id, current=1, step_position=1, step_state="succeeded")
                jobs.complete(session, job_id, result_type=TYPE, result_id=result["id"],
                    result_json={"assessment_id": result["id"], "cached": result["cached"]})
                session.commit()
        except (Exception, asyncio.CancelledError) as error:
            if task and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            with self.db.session() as session:
                lock_organization(session, self.organization_id)
                current = self._job(session, job_id)
                if (current and current.state == "running"
                        and _lease(current) == lease):
                    if current.cancel_requested or isinstance(error, (jobs.JobCancelled, asyncio.CancelledError)):
                        jobs.cancel(session, job_id)
                    else:
                        code = error.code if isinstance(error, DomainError) else "provider_unavailable"
                        if code not in TRANSIENT:
                            current.max_attempts = current.attempts
                        jobs.fail(session, job_id, code=code,
                            detail="The shared brief could not be completed; saved source evidence remains available.",
                            retry_delay=min(60, 5 * 2 ** (current.attempts - 1)))
                    session.commit()
            if isinstance(error, asyncio.CancelledError):
                raise
        finally:
            if pulse:
                pulse.cancel()
                await asyncio.gather(pulse, return_exceptions=True)
        return self._read(job_id)
