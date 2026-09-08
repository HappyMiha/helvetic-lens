"""Transactional matching wake-ups, with one measured admission per worker turn.

Matching saves only IDs. This worker never generates: it admits a separately
fenced brief job after current evidence/runtime checks. Reads never enqueue.
"""

import asyncio
from datetime import UTC, timedelta

from sqlalchemy import select

from . import interest_policy, jobs
from .config import DomainError
from .db import utcnow
from .interest_assessment import fingerprint
from .interest_jobs import TRANSIENT, BriefJobs, _lease, lock_organization
from .models import Job, RegulatoryEventState

TYPE = "interest_brief_admission"
MAX_EVENTS = 5000  # Same upper bound as the complete topic-history batch.
HEARTBEAT_SECONDS = 2
EVENT_LIMITS = frozenset({"not_found", "interest_not_current", "interest_evidence_unavailable",
    "interest_context_exceeded", "interest_inputs_changed", "capability_budget_exceeded",
    "interest_comparison_ambiguous", "document_identity_mismatch"})


def enqueue_after_matching(session, settings, event_ids, trigger):
    """Caller commits the matching checkpoint and this outbox in one transaction."""
    organization_id = session.info["organization_id"]
    policy = interest_policy.read(session, organization_id, settings)
    if not policy["enabled"]:
        return None
    ids = sorted(set(event_ids))
    if not ids:
        return None
    if len(ids) > MAX_EVENTS:
        raise ValueError("Matching admission batch exceeds its complete bound")
    organization_id = session.info["organization_id"]
    # Even a privileged caller cannot enqueue another tenant's event admissions.
    allowed = set(session.scalars(select(RegulatoryEventState.event_id).where(
        RegulatoryEventState.organization_id == organization_id,
        RegulatoryEventState.event_id.in_(ids))))
    if allowed != set(ids):
        raise DomainError("A matching event is no longer admitted.", 404, "not_found")
    trigger_key = fingerprint(trigger)
    policy_key = interest_policy.key(policy)
    admitted = []
    for locale in interest_policy.member_locales(session, organization_id, policy["locale"]):
        key = fingerprint({"version": 2, "events": ids, "trigger": trigger_key, "locale": locale,
                           "policy_key": policy_key})
        job, reused = jobs.enqueue(session, organization_id=organization_id, job_type=TYPE,
            target_type="matching_batch", target_id=key[:32], queue="ai_background", priority=1,
            idempotency_key=f"interest-admission:{key}", progress_total=len(ids), max_attempts=3,
            payload={"event_ids": ids, "locale": locale, "trigger": trigger_key,
                     "policy_key": policy_key, "checkpoint": {"position": 0}},
            steps=[("Admit current shared relevance briefs", {})])
        admitted.append({"job_id": job.id, "locale": locale, "reused": reused})
    return {"job_id": admitted[0]["job_id"], "reused": all(row["reused"] for row in admitted),
            "events": len(ids), "ai_calls": 0, "language_jobs": admitted}



class AdmissionJobs(BriefJobs):
    """Reuse org/lease inspection, not the generation execution path."""

    def _job(self, session, job_id):
        return session.scalar(select(Job).where(Job.id == job_id,
            Job.organization_id == self.organization_id, Job.type == TYPE).with_for_update())

    async def _execute(self, job_id, worker):
        with self.db.session() as session:
            lock_organization(session, self.organization_id)
            job = self._job(session, job_id)
            if job is None:
                raise DomainError("Admission job not found.", 404, "not_found")
            if job.available_at.replace(tzinfo=UTC) > utcnow():
                return jobs.serialize(session, job)
            job = jobs.claim(session, job_id, worker)
            if job is None:
                session.commit()
                return self._read(job_id)
            lease = _lease(job)
            payload = dict(job.payload or {})
            session.commit()

        def guard(session):
            lock_organization(session, self.organization_id)
            current = self._job(session, job_id)
            if (current is None or current.state != "running" or current.cancel_requested
                    or _lease(current) != lease):
                raise jobs.JobCancelled()
            policy = interest_policy.read(session, self.organization_id, self.runner.client.settings)
            interest_policy.check(session, self.organization_id, self.runner.client.settings,
                                  payload.get("policy_key", interest_policy.key(policy)), payload.get("locale"))
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
            ids, locale = payload.get("event_ids"), payload.get("locale")
            checkpoint = payload.get("checkpoint") or {}
            position = checkpoint.get("position")
            binding = {"version": 2 if "policy_key" in payload else 1, "events": ids,
                       "trigger": payload.get("trigger"), "locale": locale,
                       **({"policy_key": payload["policy_key"]} if "policy_key" in payload else {})}
            if (set(payload) not in ({"event_ids", "locale", "trigger", "checkpoint"},
                                    {"event_ids", "locale", "trigger", "checkpoint", "policy_key"})
                    or not isinstance(ids, list) or not 1 <= len(ids) <= MAX_EVENTS
                    or any(not isinstance(value, str) or not value or len(value) > 36 for value in ids)
                    or len(set(ids)) != len(ids) or locale not in {"de", "fr", "it", "rm", "en"}
                    or type(position) is not int or not 0 <= position < len(ids)
                    or job.idempotency_key != "interest-admission:" + fingerprint(binding)
                    or job.target_id != job.idempotency_key.removeprefix("interest-admission:")[:32]):
                raise DomainError("Invalid matching admission checkpoint.", 409, "interest_job_invalid")
            with self.db.session() as session:
                guard(session)
                policy_key = interest_policy.key(interest_policy.read(session, self.organization_id,
                                                                    self.runner.client.settings))
            pulse = asyncio.create_task(heartbeat())
            task = asyncio.create_task(self.runner.schedule(ids[position], locale=locale, guard=guard,
                                                           policy_key=policy_key))
            done, _ = await asyncio.wait({task, pulse}, return_when=asyncio.FIRST_COMPLETED)
            if pulse in done:
                await pulse
            try:
                admitted = await task
                outcome = {"status": admitted["status"], "assessment_id": admitted["id"],
                           "job_id": admitted.get("job_id"), "cached": admitted["cached"],
                           "error_code": admitted.get("error_code")}
            except DomainError as error:
                if error.code not in EVENT_LIMITS:
                    raise
                # Evidence limitations affect this event, not every later event.
                outcome = {"status": "limited", "error_code": error.code}
            with self.db.session() as session:
                current = guard(session)
                position += 1
                accepted = outcome["status"] in {"queued", "running", "succeeded"}
                checkpoint = {"position": position,
                    "admitted": checkpoint.get("admitted", 0) + int(accepted),
                    "limited": checkpoint.get("limited", 0) + int(not accepted)}
                current.payload = {**payload, "checkpoint": checkpoint}
                current.result_type, current.result_id = TYPE, current.target_id
                outcomes = (current.result_json or {}).get("outcomes", [])
                current.result_json = {**checkpoint, "total": len(ids), "ai_calls": 0,
                    "outcomes": [*outcomes, {"event_id": ids[position - 1], **outcome}]}
                jobs.progress(session, job_id, current=position, total=len(ids), step_position=1,
                    step_state="succeeded" if position == len(ids) else "pending")
                if position < len(ids):
                    jobs.yield_batch(session, current)
                else:
                    jobs.complete(session, job_id, result_type=TYPE, result_id=current.target_id,
                        result_json=current.result_json)
                session.commit()
        except (Exception, asyncio.CancelledError) as error:
            if task and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            with self.db.session() as session:
                lock_organization(session, self.organization_id)
                current = self._job(session, job_id)
                if current and current.state == "running" and _lease(current) == lease:
                    if current.cancel_requested or isinstance(error, (jobs.JobCancelled, asyncio.CancelledError)):
                        jobs.cancel(session, job_id)
                    else:
                        code = error.code if isinstance(error, DomainError) else "provider_unavailable"
                        if code == "interest_queue_limit":
                            jobs.defer_until(session, current, utcnow() + timedelta(minutes=5),
                                code=code, detail="Background brief allowance reached; this event remains pending.")
                        else:
                            if code not in TRANSIENT:
                                current.max_attempts = current.attempts
                            jobs.fail(session, job_id, code=code,
                                detail="Automatic brief admission paused. Saved monitoring and evidence remain available.",
                                retry_delay=min(60, 5 * 2 ** (current.attempts - 1)))
                    session.commit()
            if isinstance(error, asyncio.CancelledError):
                raise
        finally:
            if pulse:
                pulse.cancel()
                await asyncio.gather(pulse, return_exceptions=True)
        return self._read(job_id)
