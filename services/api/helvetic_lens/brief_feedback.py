"""Personal usefulness feedback bound to immutable saved briefs; no AI calls."""
from datetime import UTC, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from .config import DomainError
from .db import utcnow
from .interest_brief_reader import authorize
from .interest_jobs import lock_organization
from .models import InterestBriefFeedback, InterestEventAssessment
from .topic_matching import _fingerprint, _iso


class FeedbackInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    expected_previous_id: UUID | None = None
    decision: Literal["useful", "not_useful", "withdrawn"]
    note: str = Field(default="", max_length=1000)


def assessment(session, organization_id, identity, *, lock=False):
    query = select(InterestEventAssessment).where(InterestEventAssessment.id == identity,
        InterestEventAssessment.organization_id == organization_id, InterestEventAssessment.status == "succeeded")
    row = session.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise DomainError("Saved brief not found.", 404, "not_found")
    authorize(session, organization_id, row.event_id)
    return row


def scope(organization_id, principal, identity):
    return select(InterestBriefFeedback).where(InterestBriefFeedback.organization_id == organization_id,
        InterestBriefFeedback.principal_key == principal, InterestBriefFeedback.assessment_id == identity)


def serialize(row):
    return {"id": row.id, "assessment_id": row.assessment_id, "decision": row.decision,
            "note": row.note, "created_at": _iso(row.created_at)} if row else None


def read(session, organization_id, principal, identity, *, cursor="", limit=20):
    assessment(session, organization_id, identity)
    if not 1 <= limit <= 50:
        raise DomainError("Choose 1 to 50 feedback records.", 422, "invalid_feedback_page")
    query = scope(organization_id, principal, identity)
    order = (InterestBriefFeedback.created_at.desc(), InterestBriefFeedback.id.desc())
    latest = session.scalar(query.order_by(*order).limit(1))
    if cursor:
        position = session.scalar(query.where(InterestBriefFeedback.id == cursor))
        if position is None:
            raise DomainError("Reload your feedback history.", 422, "invalid_feedback_page")
        query = query.where(or_(InterestBriefFeedback.created_at < position.created_at,
            (InterestBriefFeedback.created_at == position.created_at) & (InterestBriefFeedback.id < position.id)))
    rows = list(session.scalars(query.order_by(*order).limit(limit + 1)))
    return {"assessment_id": identity, "latest": serialize(latest), "items": [serialize(row) for row in rows[:limit]],
            "has_more": len(rows) > limit, "next_cursor": rows[limit - 1].id if len(rows) > limit else None}


def save(session, organization_id, principal, user_id, identity, data):
    # Also serializes the per-principal daily count across different assessments.
    lock_organization(session, organization_id)
    assessment(session, organization_id, identity, lock=True)
    fingerprint = _fingerprint([identity, data.decision, data.note, str(data.expected_previous_id)])
    request_query = select(InterestBriefFeedback).where(InterestBriefFeedback.organization_id == organization_id,
        InterestBriefFeedback.principal_key == principal, InterestBriefFeedback.request_key == str(data.request_id))

    def reused(previous):
        if previous.request_fingerprint != fingerprint:
            raise DomainError("This feedback request was already used for different content.", 409, "feedback_conflict")
        return {"feedback": serialize(previous), "reused": True}

    previous = session.scalar(request_query)
    if previous:
        return reused(previous)
    latest = session.scalar(scope(organization_id, principal, identity)
        .order_by(InterestBriefFeedback.created_at.desc(), InterestBriefFeedback.id.desc()).limit(1))
    if (latest.id if latest else None) != (str(data.expected_previous_id) if data.expected_previous_id else None):
        raise DomainError("Your feedback changed in another session. Reload before saving.", 409, "feedback_conflict")
    count = session.scalar(select(func.count()).select_from(InterestBriefFeedback).where(
        InterestBriefFeedback.organization_id == organization_id, InterestBriefFeedback.principal_key == principal,
        InterestBriefFeedback.created_at >= utcnow() - timedelta(hours=24)))
    if count >= 100:
        raise DomainError("Your daily feedback allowance is reached.", 429, "feedback_limit")
    created_at = utcnow()
    if latest:
        previous_time = latest.created_at.replace(tzinfo=UTC) if latest.created_at.tzinfo is None else latest.created_at
        created_at = max(created_at, previous_time + timedelta(microseconds=1))
    row = InterestBriefFeedback(organization_id=organization_id, assessment_id=identity, principal_key=principal,
        actor_user_id=user_id, request_key=str(data.request_id), request_fingerprint=fingerprint,
        decision=data.decision, note=data.note, created_at=created_at)
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        previous = session.scalar(request_query)
        if previous:
            return reused(previous)
        raise
    return {"feedback": serialize(row), "reused": False}
