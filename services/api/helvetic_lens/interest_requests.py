"""Explicit bounded language requests; no runtime/token/inference calls on HTTP."""
from datetime import timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from . import interest_policy, jobs
from .config import DomainError
from .db import utcnow
from .interest_assessment import fingerprint
from .interest_automation import TYPE, enqueue_after_matching
from .interest_brief_reader import authorize
from .interest_jobs import lock_organization
from .models import Job

MAX_PENDING = 8
MAX_DAILY = 40
TARGET = "interest_brief_request"


class BriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    locale: Literal["de", "fr", "it", "rm", "en"] | None = None


def enqueue(session, organization_id, settings, event_id, locale, request_id):
    authorize(session, organization_id, event_id)
    if locale not in {"de", "fr", "it", "rm", "en"}:
        raise DomainError("Unsupported brief language.", 422, "invalid_locale")
    lock_organization(session, organization_id)
    policy = interest_policy.read(session, organization_id, settings)
    if not policy["enabled"]:
        raise DomainError("Automatic briefs are disabled by your organization.", 409, "interest_auto_disabled")
    policy_key = interest_policy.key(policy)
    trigger = {"kind": "user_language_request", "request_id": str(request_id)}
    key = "interest-admission:" + fingerprint({"version": 2, "events": [event_id],
        "trigger": fingerprint(trigger), "locale": locale, "policy_key": policy_key})
    scope = (Job.organization_id == organization_id, Job.type == TYPE, Job.target_type == TARGET)
    exact = session.scalar(select(Job).where(*scope, Job.idempotency_key == key))
    if exact is not None:
        return {"job": jobs.serialize(session, exact), "reused": True, "ai_calls": 0}
    shared = session.scalar(select(Job).where(*scope,
        Job.state.not_in(jobs.TERMINAL_STATES), Job.cancel_requested.is_(False),
        Job.payload["locale"].as_string() == locale,
        Job.payload["event_ids"][0].as_string() == event_id,
        Job.payload["policy_key"].as_string() == policy_key).order_by(Job.created_at).limit(1))
    if shared is not None:
        return {"job": jobs.serialize(session, shared), "reused": True, "ai_calls": 0}
    pending = session.scalar(select(func.count()).select_from(Job).where(*scope, Job.state.not_in(jobs.TERMINAL_STATES)))
    daily = session.scalar(select(func.count()).select_from(Job).where(*scope, Job.created_at >= utcnow() - timedelta(hours=24)))
    if pending >= MAX_PENDING or daily >= MAX_DAILY:
        raise DomainError("Brief request allowance reached. Saved evidence remains available.", 429, "interest_request_limit")
    result = enqueue_after_matching(session, settings, [event_id], trigger, locales=[locale])
    job = session.get(Job, result["job_id"])
    job.target_type = TARGET
    session.flush()
    return {"job": jobs.serialize(session, job), "reused": result["reused"], "ai_calls": 0}
