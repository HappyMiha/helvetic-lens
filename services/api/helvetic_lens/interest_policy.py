"""Fresh tenant policy; saving settings never performs inference or catch-up."""
from datetime import timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from .config import DomainError
from .db import utcnow
from .interest_assessment import fingerprint
from .models import InterestBriefPolicy, Job, OrganizationMembership, User

MAX_PENDING = 4
MAX_DAILY = 20


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool = False
    locale: Literal["de", "fr", "it", "rm", "en"] = "en"
    max_pending: int = Field(default=MAX_PENDING, ge=1, le=MAX_PENDING)
    max_daily: int = Field(default=MAX_DAILY, ge=1, le=MAX_DAILY)


class PolicyInput(Policy):
    revision: int = Field(ge=0)


def read(session, organization_id, settings):
    record = session.scalar(select(InterestBriefPolicy).where(
        InterestBriefPolicy.organization_id == organization_id).execution_options(populate_existing=True))
    policy = (Policy.model_validate(record.values) if record else Policy(
        enabled=settings.interest_brief_auto_enabled, locale=settings.interest_brief_auto_locale))
    return {**policy.model_dump(), "revision": record.revision if record else 0,
            "source": "organization" if record else "environment",
            "updated_at": record.updated_at.isoformat() if record else None}


def key(policy):
    return fingerprint({name: policy[name] for name in (*Policy.model_fields, "revision")})


def check(session, organization_id, settings, expected, locale):
    policy = read(session, organization_id, settings)
    if not policy["enabled"] or locale not in {"de", "fr", "it", "rm", "en"} or key(policy) != expected:
        raise DomainError("Automatic brief policy changed; the old work will not continue.",
                          409, "interest_policy_changed")
    return policy


def usage(session, organization_id):
    from .jobs import TERMINAL_STATES
    scope = (Job.organization_id == organization_id, Job.type == "interest_event_brief")
    return {"pending": session.scalar(select(func.count()).select_from(Job).where(
                *scope, Job.state.not_in(TERMINAL_STATES))),
            "last_24_hours": session.scalar(select(func.count()).select_from(Job).where(
                *scope, Job.created_at >= utcnow() - timedelta(hours=24)))}


def public(session, organization_id, settings):
    return {**read(session, organization_id, settings), "usage": usage(session, organization_id),
            "hard_limits": {"max_pending": MAX_PENDING, "max_daily": MAX_DAILY}, "ai_calls": 0}


def save(session, organization_id, settings, data):
    from . import jobs
    from .interest_jobs import lock_organization
    lock_organization(session, organization_id)
    previous = read(session, organization_id, settings)
    if previous["revision"] != data.revision:
        raise DomainError("Another administrator changed these settings. Reload before saving.",
                          409, "interest_policy_conflict")
    values = data.model_dump(exclude={"revision"})
    if previous["source"] == "organization" and all(previous[name] == value for name, value in values.items()):
        return public(session, organization_id, settings)
    record = session.get(InterestBriefPolicy, organization_id)
    if record is None:
        record = InterestBriefPolicy(organization_id=organization_id)
        session.add(record)
    record.values, record.revision, record.updated_at = values, data.revision + 1, utcnow()
    session.flush()
    # Stop admission cursors and policy-bound generation only. Historical results
    # and explicitly scheduled/unbound legacy work are not silently rewritten.
    candidates = session.scalars(select(Job).where(Job.organization_id == organization_id,
        Job.type.in_({"interest_brief_admission", "interest_event_brief"}),
        Job.state.not_in(jobs.TERMINAL_STATES)).with_for_update())
    cancelled = 0
    for job in candidates:
        if job.type == "interest_brief_admission" or (job.payload or {}).get("policy_key"):
            jobs.request_cancel(session, job.id)
            cancelled += 1
    return {**public(session, organization_id, settings), "cancel_requested": cancelled}


def member_locales(session, organization_id, fallback):
    """One variant per active member language, never one inference per user."""
    values = session.scalars(select(User.locale).join(OrganizationMembership,
        OrganizationMembership.user_id == User.id).where(
        OrganizationMembership.organization_id == organization_id, User.active.is_(True)).distinct())
    languages = {value.split("-")[0] for value in values if value}
    return sorted(languages & {"de", "fr", "it", "rm", "en"}) or [fallback]
