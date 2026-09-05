"""PostgreSQL-backed job state and transactional dispatch outbox."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import utcnow
from .models import Job, JobStep, OutboxMessage
from .observability import current_correlation

TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled"})
CLAIMABLE_STATES = frozenset({"queued", "dispatched", "retrying", "waiting_for_model"})
QUEUES = frozenset(
    {
        "interactive",
        "ingest",
        "parse_diff",
        "ai_interactive",
        "ai_background",
        "maintenance",
    }
)


class JobCancelled(Exception):
    """Raised at a safe boundary after cancellation was requested."""


def _bounded_error(value: str | None) -> str | None:
    return (value or "").strip()[:2000] or None


def _enqueue_outbox(session: Session, job: Job) -> OutboxMessage:
    pending = session.scalar(
        select(OutboxMessage)
        .where(OutboxMessage.job_id == job.id, OutboxMessage.state == "pending")
        .limit(1)
    )
    if pending:
        return pending
    message = OutboxMessage(
        job_id=job.id,
        queue=job.queue,
        payload={"job_id": job.id},
        available_at=job.available_at,
    )
    session.add(message)
    return message


def enqueue(
    session: Session,
    *,
    job_type: str,
    target_type: str,
    target_id: str,
    queue: str,
    idempotency_key: str,
    payload: dict | None = None,
    priority: int = 5,
    progress_total: int = 1,
    max_attempts: int = 3,
    steps: list[tuple[str, dict]] | None = None,
    organization_id: str | None = None,
) -> tuple[Job, bool]:
    if queue not in QUEUES:
        raise ValueError(f"Unknown durable queue: {queue}")
    organization_id = organization_id or session.info["organization_id"]
    existing = session.scalar(
        select(Job).where(
            Job.organization_id == organization_id,
            Job.idempotency_key == idempotency_key,
        )
    )
    if existing:
        return existing, True
    correlation = current_correlation()
    job = Job(
        organization_id=organization_id,
        request_id=correlation.get("request_id"),
        correlation=correlation,
        type=job_type,
        target_type=target_type,
        target_id=target_id,
        queue=queue,
        priority=max(0, min(9, priority)),
        idempotency_key=idempotency_key,
        payload=payload or {},
        progress_total=max(1, progress_total),
        max_attempts=max(1, max_attempts),
    )
    session.add(job)
    session.flush()
    correlation = {
        **correlation,
        "job_id": job.id,
        "organization_id": organization_id,
        "target_type": target_type[:40],
        "target_id": target_id[:200],
    }
    if target_type == "comparison":
        correlation["comparison_id"] = target_id[:200]
    correlation_payload = payload or {}
    payload_keys = {
        "run_id": "connector_run_id",
        "document_id": "document_id",
        "event_id": "event_id",
        "comparison_id": "comparison_id",
        "analysis_id": "analysis_id",
        "ask_record_id": "ask_record_id",
    }
    for payload_key, correlation_key in payload_keys.items():
        value = correlation_payload.get(payload_key)
        if value:
            correlation[correlation_key] = str(value)[:200]
    job.correlation = correlation
    for position, (name, details) in enumerate(steps or [], 1):
        session.add(
            JobStep(
                job_id=job.id,
                position=position,
                name=name[:100],
                details=details,
            )
        )
    _enqueue_outbox(session, job)
    return job, False


def claim(session: Session, job_id: str, worker: str) -> Job | None:
    job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if not job or job.state not in CLAIMABLE_STATES:
        return None
    now = utcnow()
    if job.cancel_requested:
        job.state, job.finished_at, job.updated_at = "cancelled", now, now
        return None
    if job.attempts >= job.max_attempts:
        job.state, job.finished_at, job.updated_at = "failed", now, now
        job.error_code = "attempts_exhausted"
        job.error_detail = "The durable job exhausted its configured attempt limit."
        return None
    job.state = "running"
    job.attempts += 1
    job.lease_owner = worker[:120]
    job.leased_at = job.heartbeat_at = now
    job.started_at = job.started_at or now
    job.updated_at = now
    return job


def heartbeat(session: Session, job_id: str, worker: str) -> bool:
    job = session.get(Job, job_id)
    if not job or job.state != "running" or job.lease_owner != worker:
        return False
    job.heartbeat_at = job.updated_at = utcnow()
    return not job.cancel_requested


def cancellation_requested(session: Session, job_id: str) -> bool:
    job = session.get(Job, job_id)
    return bool(job and job.cancel_requested)


def progress(
    session: Session,
    job_id: str,
    *,
    current: int,
    total: int | None = None,
    step_position: int | None = None,
    step_state: str | None = None,
    step_details: dict | None = None,
    step_error: str | None = None,
    step_current: int | None = None,
    step_total: int | None = None,
) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise LookupError(job_id)
    now = utcnow()
    job.progress_current = max(0, current)
    if total is not None:
        job.progress_total = max(1, total)
    job.heartbeat_at = job.updated_at = now
    if step_position is not None:
        step = session.scalar(
            select(JobStep).where(
                JobStep.job_id == job_id,
                JobStep.position == step_position,
            )
        )
        if step:
            if step_state:
                step.state = step_state
                if step_state == "running":
                    step.started_at = step.started_at or now
                if step_state in TERMINAL_STATES:
                    step.finished_at = now
            if step_details is not None:
                step.details = {**(step.details or {}), **step_details}
            step.error_detail = _bounded_error(step_error)
            if step_total is not None:
                step.progress_total = max(1, step_total)
            if step_current is not None:
                step.progress_current = max(0, min(step_current, step.progress_total))
            elif step.state == "succeeded":
                step.progress_current = step.progress_total
            elif step.state != "running":
                step.progress_current = 0
    return job


def complete(
    session: Session,
    job_id: str,
    *,
    result_type: str | None = None,
    result_id: str | None = None,
    result_url: str | None = None,
    result_json: dict | None = None,
) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise LookupError(job_id)
    now = utcnow()
    job.state = "cancelled" if job.cancel_requested else "succeeded"
    job.progress_current = job.progress_total
    job.result_type, job.result_id = result_type, result_id
    job.result_url, job.result_json = result_url, result_json
    job.error_code = job.error_detail = None
    job.lease_owner = None
    job.heartbeat_at = job.updated_at = job.finished_at = now
    return job


def fail(session: Session, job_id: str, *, code: str, detail: str, retry_delay: int = 5) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise LookupError(job_id)
    now = utcnow()
    job.error_code, job.error_detail = code[:80], _bounded_error(detail)
    job.lease_owner = None
    job.heartbeat_at = job.updated_at = now
    if job.cancel_requested:
        return cancel(session, job_id)
    elif job.attempts < job.max_attempts:
        job.state = "retrying"
        job.available_at = now + timedelta(seconds=max(1, retry_delay))
        for step in session.scalars(
            select(JobStep).where(JobStep.job_id == job_id, JobStep.state == "running")
        ):
            step.state = "pending"
            step.error_detail = _bounded_error(detail)
            step.started_at = None
        _enqueue_outbox(session, job)
    else:
        job.state, job.finished_at = "failed", now
        for step in session.scalars(
            select(JobStep).where(JobStep.job_id == job_id, JobStep.state == "running")
        ):
            step.state = "failed"
            step.error_detail = _bounded_error(detail)
            step.finished_at = now
    return job


def defer_for_model(session: Session, job_id: str, detail: str, delay: int = 10) -> Job:
    """Release a job without consuming an attempt while local inference warms up."""
    job = session.get(Job, job_id)
    if not job:
        raise LookupError(job_id)
    now = utcnow()
    job.state = "waiting_for_model"
    job.attempts = max(0, job.attempts - 1)
    job.available_at = now + timedelta(seconds=max(2, delay))
    job.error_code = "waiting_for_model"
    job.error_detail = _bounded_error(detail)
    job.lease_owner = None
    job.heartbeat_at = job.updated_at = now
    for step in session.scalars(
        select(JobStep).where(JobStep.job_id == job_id, JobStep.state == "running")
    ):
        step.state = "pending"
        step.started_at = None
        step.error_detail = _bounded_error(detail)
    _enqueue_outbox(session, job)
    return job


def yield_batch(session: Session, job: Job) -> Job:
    """Release successful checkpointed work to the outbox in this transaction.

    The caller commits output and checkpoint with this transition. A successful
    batch resets the consecutive failure budget; further batches are not retries.
    """
    if job.cancel_requested:
        return cancel(session, job.id)
    if job.state != "running":
        raise ValueError("Only a running job can yield a completed batch")
    now = utcnow()
    job.state = "queued"
    job.attempts = 0
    job.available_at = job.heartbeat_at = job.updated_at = now
    job.lease_owner = None
    job.error_code = job.error_detail = None
    _enqueue_outbox(session, job)
    return job


def cancel(session: Session, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise LookupError(job_id)
    now = utcnow()
    job.cancel_requested = True
    job.state, job.finished_at, job.updated_at = "cancelled", now, now
    job.lease_owner = None
    job.heartbeat_at = now
    for step in session.scalars(
        select(JobStep).where(JobStep.job_id == job_id, JobStep.state.not_in(TERMINAL_STATES))
    ):
        step.state, step.finished_at = "cancelled", now
    return job


def request_cancel(session: Session, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise LookupError(job_id)
    if job.state in TERMINAL_STATES:
        return job
    now = utcnow()
    job.cancel_requested = True
    job.updated_at = now
    if job.state in CLAIMABLE_STATES:
        return cancel(session, job_id)
    return job


def retry(session: Session, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise LookupError(job_id)
    if job.state not in {"failed", "cancelled"}:
        return job
    now = utcnow()
    job.state, job.available_at, job.updated_at = "queued", now, now
    job.cancel_requested = False
    job.attempts = 0
    job.error_code = job.error_detail = None
    job.finished_at = None
    succeeded_steps = 0
    for step in session.scalars(select(JobStep).where(JobStep.job_id == job_id)):
        if step.state == "succeeded":
            succeeded_steps += 1
            continue
        step.state = "pending"
        step.progress_current = 0
        step.error_detail = None
        step.started_at = step.finished_at = None
    if job.type != "topic_match_backfill" or not (job.payload or {}).get("checkpoint"):
        job.progress_current = succeeded_steps
    _enqueue_outbox(session, job)
    return job


def reconcile(session: Session, lease_seconds: int) -> dict:
    now = utcnow()
    stale_lease = now - timedelta(seconds=max(30, lease_seconds))
    stale_dispatch = now - timedelta(seconds=30)
    recovered = 0
    for job in session.scalars(
        select(Job).where(
            Job.state == "running",
            Job.heartbeat_at < stale_lease,
        ).with_for_update(skip_locked=True)
    ):
        job.lease_owner = None
        if job.attempts >= job.max_attempts:
            job.state, job.finished_at = "failed", now
            job.error_code = "stale_lease_exhausted"
            job.error_detail = "The worker lease expired and the attempt limit was exhausted."
        else:
            job.state, job.available_at = "retrying", now
            _enqueue_outbox(session, job)
        job.updated_at = now
        recovered += 1
    for job in session.scalars(
        select(Job).where(Job.state == "dispatched", Job.dispatched_at < stale_dispatch)
        .with_for_update(skip_locked=True)
    ):
        job.state, job.available_at, job.updated_at = "queued", now, now
        _enqueue_outbox(session, job)
        recovered += 1
    return {"recovered": recovered}


def dispatch(session: Session, sender: Callable[[str, str, dict, int], None], limit: int = 100) -> dict:
    now = utcnow()
    messages = list(
        session.scalars(
            select(OutboxMessage)
            .where(OutboxMessage.state == "pending", OutboxMessage.available_at <= now)
            .order_by(OutboxMessage.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    sent, failed = 0, 0
    for message in messages:
        job = session.get(Job, message.job_id)
        if not job or job.state in TERMINAL_STATES:
            message.state = "discarded"
            continue
        job.state, job.dispatched_at, job.updated_at = "dispatched", now, now
        session.flush()
        try:
            sender(message.topic, message.queue, message.payload, job.priority)
        except Exception as exc:  # broker errors stay inspectable and retryable
            job.state, job.dispatched_at = "queued", None
            message.attempts += 1
            message.error_detail = _bounded_error(str(exc))
            message.available_at = now + timedelta(seconds=min(60, 2 ** min(message.attempts, 5)))
            failed += 1
            continue
        message.state, message.dispatched_at = "dispatched", now
        message.attempts += 1
        message.error_detail = None
        sent += 1
    return {"sent": sent, "failed": failed}


def serialize(session: Session, job: Job) -> dict:
    steps = list(
        session.scalars(select(JobStep).where(JobStep.job_id == job.id).order_by(JobStep.position))
    )
    queue_position = None
    if job.state in {"queued", "dispatched", "retrying", "waiting_for_model"}:
        queue_position = 1 + int(
            session.scalar(
                select(func.count())
                .select_from(Job)
                .where(
                    Job.queue == job.queue,
                    Job.state.in_(["queued", "dispatched", "retrying", "waiting_for_model"]),
                    Job.created_at < job.created_at,
                )
            )
            or 0
        )
    request = None
    if job.type == "ask":
        payload = job.payload or {}
        request = {
            "question": str(payload.get("question") or "")[:2000],
            "output_locale": payload.get("output_locale"),
        }
    return {
        "id": job.id,
        "organization_id": job.organization_id,
        "type": job.type,
        "target_type": job.target_type,
        "target_id": job.target_id,
        "queue": job.queue,
        "priority": job.priority,
        "state": job.state,
        "progress": {"current": job.progress_current, "total": job.progress_total},
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "queue_position": queue_position,
        "cancel_requested": job.cancel_requested,
        "request": request,
        "error": {"code": job.error_code, "detail": job.error_detail} if job.error_detail else None,
        "result": {
            "type": job.result_type,
            "id": job.result_id,
            "url": job.result_url,
            "data": job.result_json,
        }
        if job.result_type or job.result_json
        else None,
        "lease": {
            "worker": job.lease_owner,
            "leased_at": job.leased_at,
            "heartbeat_at": job.heartbeat_at,
        }
        if job.lease_owner
        else None,
        "steps": [
            {
                "id": step.id,
                "position": step.position,
                "name": step.name,
                "state": step.state,
                "progress": {"current": step.progress_current, "total": step.progress_total},
                "details": step.details,
                "error": step.error_detail,
                "started_at": step.started_at,
                "finished_at": step.finished_at,
            }
            for step in steps
        ],
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }
