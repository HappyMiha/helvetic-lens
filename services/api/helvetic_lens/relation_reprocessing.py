"""Explicit platform maintenance of retained retrieval candidates, without AI.

Jobs own their cutoff/cursor; candidate edits and cursor advancement commit
together. Never recreate deliveries, reviews, notifications or historical reports.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import load_only

from . import relation_candidates as rules
from .config import DomainError
from .db import utcnow
from .models import (
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryExpression,
    RegulatoryRelation,
    RegulatoryWork,
    RelationCandidate,
)
from .relation_identity import relation_direction

JOB_TYPE = "relation_candidate_reprocess"
SCHEMA = "relation-candidate-reprocess-v1"
BATCH_SIZE = 25


class Checkpoint(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    cursor: str = Field(default="", pattern=r"^(?:[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12})?$")
    processed: int = Field(default=0, ge=0)
    eligible: int | None = Field(default=None, ge=0)
    changed: int = Field(default=0, ge=0)
    rejected: int = Field(default=0, ge=0)
    retained: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    batches: int = Field(default=0, ge=0)
    examples: list[dict] = Field(default_factory=list, max_length=10)


def latest_version_id(session, work_id):
    return session.scalar(select(RegulatoryDocumentVersion.id).join(RegulatoryExpression).where(
        RegulatoryExpression.work_id == work_id,
    ).order_by(RegulatoryDocumentVersion.created_at.desc(), RegulatoryDocumentVersion.id.desc()).limit(1))


def revision_values(session, candidate):
    # Select metadata explicitly: neither full texts nor passage lists are needed
    # for the existing deterministic retrieval policy.
    works = {work.id: work for work in session.scalars(select(RegulatoryWork).where(
        RegulatoryWork.id.in_((candidate.source_work_id, candidate.target_work_id)),
    ).options(load_only(RegulatoryWork.id, RegulatoryWork.title, RegulatoryWork.kind,
                        RegulatoryWork.authority, RegulatoryWork.metadata_json)))}
    event = session.scalar(select(RegulatoryEvent).where(RegulatoryEvent.id == candidate.event_id).options(
        load_only(RegulatoryEvent.id, RegulatoryEvent.work_id, RegulatoryEvent.source_url,
                  RegulatoryEvent.document_version_id, RegulatoryEvent.evidence_json),
    ))
    source, target = works.get(candidate.source_work_id), works.get(candidate.target_work_id)
    if not source or not target or not event or source.id == target.id or event.work_id != source.id:
        return None
    if event.document_version_id and not session.scalar(select(RegulatoryDocumentVersion.id).join(RegulatoryExpression).where(
        RegulatoryDocumentVersion.id == event.document_version_id, RegulatoryExpression.work_id == source.id,
    )):
        return None
    prior = (candidate.evidence_json or {}).get("reprocessing", {})
    if candidate.status in {"promoted", "rejected"} and prior.get("schema_version") != SCHEMA:
        # These reserved terminal states might have been set by an operator.
        return None
    relation = session.scalar(select(RegulatoryRelation).where(
        RegulatoryRelation.state == "confirmed",
        or_((RegulatoryRelation.subject_work_id == source.id) & (RegulatoryRelation.object_work_id == target.id),
            (RegulatoryRelation.subject_work_id == target.id) & (RegulatoryRelation.object_work_id == source.id)),
    ).options(load_only(RegulatoryRelation.id, RegulatoryRelation.state, RegulatoryRelation.subject_work_id,
                        RegulatoryRelation.object_work_id, RegulatoryRelation.relation_type,
                        RegulatoryRelation.provenance_method))
        .order_by(RegulatoryRelation.created_at.desc(), RegulatoryRelation.id.desc()).limit(1))
    scored = rules.score_pair(source, event, target, relation)
    relation_id = relation.id if relation else None
    if not relation and candidate.relation_id:
        previous = session.scalar(select(RegulatoryRelation).where(RegulatoryRelation.id == candidate.relation_id).options(
            load_only(RegulatoryRelation.id, RegulatoryRelation.state, RegulatoryRelation.subject_work_id, RegulatoryRelation.object_work_id),
        ))
        if previous and previous.state == "proposed" and relation_direction(previous, source.id, target.id):
            relation_id = previous.id
    outcome = "retained" if scored else "rejected"
    # Expiration and independent reviews are not renewed or overwritten.
    expired = candidate.expires_at.replace(tzinfo=UTC) <= utcnow()
    status = ("expired" if candidate.status == "expired" or expired else "active") if scored else "rejected"
    values = {
        "rule_revision": rules.RULE_REVISION,
        "relation_id": relation_id,
        "source_version_id": event.document_version_id or latest_version_id(session, source.id),
        "target_version_id": latest_version_id(session, target.id),
        "status": status,
        "score": scored.score if scored else 0.0,
        "score_components_json": scored.components if scored else {},
        "why_json": list(scored.why) if scored else ["Current retrieval rules do not support this lead; this is not a legal no-impact judgment."],
        "evidence_json": {
            **(candidate.evidence_json or {}),
            "event_id": event.id, "event_source_url": event.source_url,
            "source_work": source.id, "target_work": target.id,
            "relation_state": "confirmed" if relation else "proposed",
            "similarity_is_not_evidence": relation is None,
        },
    }
    # A bookkeeping marker alone must not invalidate a still-current AI report.
    # Record provenance when an actual retrieval input/decision changes instead.
    if any(getattr(candidate, key) != value for key, value in values.items()):
        values["evidence_json"]["reprocessing"] = {"schema_version": SCHEMA, "rule_revision": rules.RULE_REVISION, "outcome": outcome}
    return values


def run_batch(session, payload: dict) -> dict:
    if not session.info.get("include_all_organizations"):
        raise DomainError("Relation maintenance requires a platform-scoped session.", 403, "platform_admin_required")
    try:
        if payload.get("schema_version") != SCHEMA or type(payload.get("dry_run")) is not bool:
            raise ValueError("Invalid maintenance payload")
        captured = datetime.fromisoformat(payload["captured_at"])
        if captured.tzinfo is None:
            raise ValueError("Cutoff must be timezone-aware")
        checkpoint = Checkpoint.model_validate(payload.get("checkpoint") if payload.get("checkpoint") is not None else {})
        if (checkpoint.changed > checkpoint.processed or checkpoint.retained + checkpoint.rejected + checkpoint.skipped != checkpoint.processed
                or bool(checkpoint.cursor) != bool(checkpoint.processed)
                or (checkpoint.processed and checkpoint.eligible is None)):
            raise ValueError("Inconsistent counters")
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise DomainError("The relation reprocessing checkpoint is invalid; create a new preview.", 409, "relation_reprocess_checkpoint_invalid") from exc
    if payload.get("rule_revision") != rules.RULE_REVISION:
        return {**checkpoint.model_dump(), "checkpoint": checkpoint.model_dump(), "status": "superseded", "has_more": False, "ai_calls": 0}
    if checkpoint.eligible is None:
        checkpoint.eligible = session.scalar(select(func.count()).select_from(RelationCandidate).where(RelationCandidate.created_at <= captured))
    ids = list(session.scalars(select(RelationCandidate.id).where(
        RelationCandidate.created_at <= captured, RelationCandidate.id > checkpoint.cursor,
    ).order_by(RelationCandidate.id).limit(BATCH_SIZE + 1)))
    for id_ in ids[:BATCH_SIZE]:
        candidate = session.scalar(select(RelationCandidate).where(RelationCandidate.id == id_).with_for_update())
        if candidate is None:
            checkpoint.skipped += 1
        else:
            values = revision_values(session, candidate)
            if values is None:
                checkpoint.skipped += 1
            else:
                outcome = "rejected" if values["status"] == "rejected" else "retained"
                setattr(checkpoint, outcome, getattr(checkpoint, outcome) + 1)
                if any(getattr(candidate, key) != value for key, value in values.items()):
                    checkpoint.changed += 1
                    if len(checkpoint.examples) < 10:
                        checkpoint.examples.append({"candidate_id": id_, "event_id": candidate.event_id,
                            "target_work_id": candidate.target_work_id, "outcome": outcome,
                            "source_title": (session.scalar(select(RegulatoryWork.title).where(RegulatoryWork.id == candidate.source_work_id)) or "")[:300],
                            "target_title": (session.scalar(select(RegulatoryWork.title).where(RegulatoryWork.id == candidate.target_work_id)) or "")[:300],
                            "old_rule_revision": candidate.rule_revision, "old_score": candidate.score,
                            "new_score": values["score"], "reason": values["why_json"]})
                    if not payload["dry_run"]:
                        for key, value in values.items():
                            setattr(candidate, key, value)
                        candidate.updated_at = utcnow()
        checkpoint.processed += 1
        checkpoint.cursor = id_
    checkpoint.batches += 1
    session.flush()
    return {**checkpoint.model_dump(), "checkpoint": checkpoint.model_dump(), "dry_run": payload["dry_run"],
            "rule_revision": rules.RULE_REVISION, "captured_at": captured.astimezone(UTC).isoformat(),
            "status": "pending" if len(ids) > BATCH_SIZE else "complete", "has_more": len(ids) > BATCH_SIZE,
            "removed_since_capture": max(0, checkpoint.eligible - checkpoint.processed) if len(ids) <= BATCH_SIZE else 0,
            "ai_calls": 0}
