"""Auditable organization relevance decisions; never edit or regenerate a brief."""
from datetime import UTC, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from .brief_feedback import assessment
from .config import DomainError
from .db import utcnow
from .interest_jobs import lock_organization
from .models import InterestBriefReview
from .topic_matching import _fingerprint, _iso


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    expected_previous_id: UUID | None = None
    target_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: Literal["confirmed", "rejected", "withdrawn"]
    note: str = Field(min_length=3, max_length=2000)


def target(record):
    # A repair/import must not inherit a decision made on different saved prose.
    return _fingerprint([record.id, record.input_fingerprint, record.input_manifest,
                         record.result, record.provenance])


def scope(organization_id, identity):
    return select(InterestBriefReview).where(InterestBriefReview.organization_id == organization_id,
                                             InterestBriefReview.assessment_id == identity)


def serialize(row):
    return {"id": row.id, "assessment_id": row.assessment_id, "actor_user_id": row.actor_user_id,
            "decision": row.decision, "note": row.note, "target_fingerprint": row.target_fingerprint,
            "created_at": _iso(row.created_at)} if row else None


def current(session, organization_id, record):
    # Explicit tenant constraint remains necessary even in an operator session.
    row = session.scalar(scope(organization_id, record.id)
        .order_by(InterestBriefReview.created_at.desc(), InterestBriefReview.id.desc()).limit(1))
    return serialize(row) if row and row.target_fingerprint == target(record) else None


def read(session, organization_id, identity, *, cursor="", limit=20):
    record = assessment(session, organization_id, identity)
    if not 1 <= limit <= 50:
        raise DomainError("Choose 1 to 50 review records.", 422, "invalid_brief_review_page")
    query = scope(organization_id, identity)
    order = (InterestBriefReview.created_at.desc(), InterestBriefReview.id.desc())
    latest = session.scalar(query.order_by(*order).limit(1))
    if cursor:
        position = session.scalar(query.where(InterestBriefReview.id == cursor))
        if position is None:
            raise DomainError("Reload this review history.", 422, "invalid_brief_review_page")
        query = query.where(or_(InterestBriefReview.created_at < position.created_at,
            (InterestBriefReview.created_at == position.created_at) & (InterestBriefReview.id < position.id)))
    rows = list(session.scalars(query.order_by(*order).limit(limit + 1)))
    fingerprint = target(record)
    return {"assessment_id": identity, "locale": record.input_manifest.get("locale"),
            "target_fingerprint": fingerprint, "latest": serialize(latest),
            "matches_saved_assessment": bool(latest and latest.target_fingerprint == fingerprint),
            "items": [serialize(row) for row in rows[:limit]], "has_more": len(rows) > limit,
            "next_cursor": rows[limit - 1].id if len(rows) > limit else None}


def save(session, organization_id, identity, actor_user_id, data):
    lock_organization(session, organization_id)
    record = assessment(session, organization_id, identity, lock=True)
    fingerprint = _fingerprint([identity, actor_user_id, data.decision, data.note,
                                data.target_fingerprint, str(data.expected_previous_id)])
    query = select(InterestBriefReview).where(InterestBriefReview.organization_id == organization_id,
                                              InterestBriefReview.request_key == str(data.request_id))
    def receipt(previous):
        if previous.request_fingerprint != fingerprint:
            raise DomainError("This review request was used for another decision.", 409, "brief_review_conflict")
        return {"review": serialize(previous), "reused": True}
    previous = session.scalar(query)
    if previous:
        return receipt(previous)
    latest = session.scalar(scope(organization_id, identity)
        .order_by(InterestBriefReview.created_at.desc(), InterestBriefReview.id.desc()).limit(1))
    if (data.target_fingerprint != target(record)
            or (str(data.expected_previous_id) if data.expected_previous_id else None) != (latest.id if latest else None)):
        raise DomainError("The saved brief or its review changed. Reload before deciding.", 409, "brief_review_conflict")
    created_at = utcnow()
    if latest:
        previous_time = latest.created_at.replace(tzinfo=UTC) if latest.created_at.tzinfo is None else latest.created_at
        created_at = max(created_at, previous_time + timedelta(microseconds=1))
    row = InterestBriefReview(organization_id=organization_id, assessment_id=identity, actor_user_id=actor_user_id,
        request_key=str(data.request_id), request_fingerprint=fingerprint, target_fingerprint=data.target_fingerprint,
        decision=data.decision, note=data.note, created_at=created_at)
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        previous = session.scalar(query)
        if previous:
            return receipt(previous)
        raise
    return {"review": serialize(row), "reused": False}
