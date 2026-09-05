"""Explicit, evidence-bound organization review; personal reading state is separate."""
from __future__ import annotations

from copy import deepcopy

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import DomainError
from .db import utcnow
from .inbox_context import visible
from .models import (
    MonitoringTopic,
    MonitoringTopicRevision,
    RegulatoryEventState,
    RegulatoryWork,
    TopicEventMatch,
    TopicMatchReview,
    User,
)
from .topic_matching import _fingerprint, _iso, describe_matches


def match_query(organization_id: str):
    return (select(TopicEventMatch)
        .join(RegulatoryEventState, (RegulatoryEventState.event_id == TopicEventMatch.event_id)
              & (RegulatoryEventState.organization_id == organization_id))
        .join(RegulatoryWork, RegulatoryWork.id == TopicEventMatch.work_id)
        .join(MonitoringTopic, MonitoringTopic.id == TopicEventMatch.topic_id)
        .join(MonitoringTopicRevision, MonitoringTopicRevision.id == TopicEventMatch.topic_revision_id)
        .where(TopicEventMatch.organization_id == organization_id, visible(RegulatoryWork, organization_id),
               MonitoringTopic.organization_id == organization_id, MonitoringTopicRevision.organization_id == organization_id,
               MonitoringTopicRevision.topic_id == MonitoringTopic.id))


def get_match(session: Session, organization_id: str, match_id: str, *, lock=False):
    query = match_query(organization_id).where(TopicEventMatch.id == match_id)
    if lock:
        query = query.with_for_update(of=TopicEventMatch)
    record = session.scalar(query)
    if record is None:
        raise DomainError("This topic match is unavailable in the organization.", 404, "topic_match_not_found")
    return record


def matches_page(session: Session, organization_id: str, topic_id: str, *, cursor="", limit=20):
    if not 1 <= limit <= 50:
        raise DomainError("Choose 1 to 50 matches per page.", 422, "invalid_topic_match_page")
    topic = session.scalar(select(MonitoringTopic).where(MonitoringTopic.id == topic_id, MonitoringTopic.organization_id == organization_id))
    if topic is None:
        raise DomainError("This topic is unavailable.", 404, "monitoring_topic_not_found")
    query = match_query(organization_id).where(TopicEventMatch.topic_id == topic_id)
    if cursor:
        position = session.scalar(query.where(TopicEventMatch.id == cursor))
        if position is None:
            raise DomainError("Open the first match page; this cursor is no longer available.", 422, "invalid_topic_match_page")
        query = query.where(or_(TopicEventMatch.matched_at < position.matched_at,
                               (TopicEventMatch.matched_at == position.matched_at) & (TopicEventMatch.id < position.id)))
    records = list(session.scalars(query.order_by(TopicEventMatch.matched_at.desc(), TopicEventMatch.id.desc()).limit(limit + 1)))
    return {"items": describe_matches(session, records[:limit]), "has_more": len(records) > limit,
            "next_cursor": records[limit - 1].id if len(records) > limit else None}


def serialize(review, actor_name=None):
    return {"id": review.id, "decision": review.decision, "note": review.note,
            "created_at": _iso(review.created_at), "actor_user_id": review.actor_user_id,
            "actor_name": actor_name, "snapshot": review.snapshot_json}


def detail(session: Session, organization_id: str, match_id: str, *, cursor="", limit=20):
    record = get_match(session, organization_id, match_id)
    matches = describe_matches(session, [record])
    if not matches:
        raise DomainError("This topic match is unavailable.", 404, "topic_match_not_found")
    if not 1 <= limit <= 50:
        raise DomainError("Choose 1 to 50 reviews per page.", 422, "invalid_topic_review_page")
    query = select(TopicMatchReview).where(TopicMatchReview.organization_id == organization_id, TopicMatchReview.match_id == match_id)
    if cursor:
        position = session.scalar(query.where(TopicMatchReview.id == cursor))
        if position is None:
            raise DomainError("Open the first review page for this match.", 422, "invalid_topic_review_page")
        query = query.where(or_(TopicMatchReview.created_at < position.created_at,
                               (TopicMatchReview.created_at == position.created_at) & (TopicMatchReview.id < position.id)))
    records = list(session.scalars(query.order_by(TopicMatchReview.created_at.desc(), TopicMatchReview.id.desc()).limit(limit + 1)))
    actors = dict(session.execute(select(User.id, User.name).where(User.id.in_({r.actor_user_id for r in records[:limit] if r.actor_user_id}))).all())
    return {"match": matches[0], "items": [serialize(r, actors.get(r.actor_user_id)) for r in records[:limit]],
            "has_more": len(records) > limit, "next_cursor": records[limit - 1].id if len(records) > limit else None}


def save(session: Session, organization_id: str, match_id: str, *, actor_user_id: str | None,
         decision: str, note: str, request_key: str, expected_evaluation_fingerprint: str,
         expected_review_id: str | None = None):
    if decision not in {"confirmed", "rejected"} or not 3 <= len(note.strip()) <= 2000:
        raise DomainError("Choose a decision and explain it in 3 to 2000 characters.", 422, "invalid_topic_review")
    # Lock the same row as the matching worker: a decision cannot overwrite a newer evaluation/review.
    record = get_match(session, organization_id, match_id, lock=True)
    request_fingerprint = _fingerprint([match_id, actor_user_id, decision, note.strip(),
                                        expected_evaluation_fingerprint, expected_review_id])
    previous_query = select(TopicMatchReview).where(TopicMatchReview.organization_id == organization_id,
                                                   TopicMatchReview.request_key == request_key)
    def receipt(previous):
        if previous.request_fingerprint != request_fingerprint:
            raise DomainError("This review request key was already used for a different decision.", 409, "topic_review_request_conflict")
        return {"review": serialize(previous), "reused": True}
    previous = session.scalar(previous_query)
    if previous:
        return receipt(previous)
    described = describe_matches(session, [record])
    current_review = (record.review_snapshot_json or {}).get("review_id")
    if (not described or not described[0]["is_current"]
            or record.evaluation_fingerprint != expected_evaluation_fingerprint
            or current_review != expected_review_id):
        raise DomainError("The evidence, topic or review changed. Reload and review the current proposal.", 409, "topic_review_stale")
    review = TopicMatchReview(organization_id=organization_id, match_id=match_id,
                              actor_user_id=actor_user_id, request_key=request_key,
                              request_fingerprint=request_fingerprint, decision=decision,
                              note=note.strip(), snapshot_json={}, created_at=utcnow())
    session.add(review)
    try:
        session.flush()
        snapshot = {"review_id": review.id, "decision": decision,
                    "topic_id": record.topic_id, "topic_revision_id": record.topic_revision_id,
                    "event_id": record.event_id, "work_id": record.work_id,
                    "evaluation_fingerprint": record.evaluation_fingerprint,
                    "rule_fingerprint": record.evaluated_rule_fingerprint,
                    "evidence": deepcopy(record.evidence_references_json),
                    "reasons": deepcopy(record.reason_signals_json),
                    "confidence": record.confidence_band, "matched_at": _iso(record.matched_at)}
        review.snapshot_json = snapshot
        record.review_snapshot_json = deepcopy(snapshot)
        record.decision_status = decision
        record.updated_at = utcnow()
        session.commit()
    except IntegrityError:
        session.rollback()
        previous = session.scalar(previous_query)
        if previous:
            return receipt(previous)
        raise
    return {"review": serialize(review), "reused": False}
