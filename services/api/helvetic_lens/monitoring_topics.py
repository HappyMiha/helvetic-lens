"""Durable, reviewable organization interests and bounded candidate previews."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import jobs as durable_jobs
from .config import DomainError
from .db import utcnow
from .models import (
    MonitoringTopic,
    MonitoringTopicDraft,
    MonitoringTopicRevision,
    RegulatoryEvent,
    RegulatoryExpression,
    RegulatoryWork,
    SourcePackDefinition,
)
from .source_packs import definition_matches

PREVIEW_SCAN_LIMIT = 500
PREVIEW_RESULT_LIMIT = 10
ALLOWED_LANGUAGES = {"de", "fr", "it", "rm", "en"}
ALLOWED_IMPORTANCE = {"high", "medium", "low", "none"}
ALLOWED_DOCUMENT_KINDS = {
    "act",
    "ordinance",
    "parliamentary_business",
    "initiative",
    "bill",
    "court_decision",
    "official_notice",
    "consultation",
    "unclassified_document",
}
ALLOWED_EVENT_KINDS = {
    "created",
    "new_version",
    "amended",
    "repealed",
    "replaced",
    "status_changed",
    "decided",
    "notice_published",
}
STATUS_TRANSITIONS = {
    "active": {"paused", "archived"},
    "paused": {"active", "archived"},
    "archived": set(),
}
IMPORTANCE_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3, "unknown": 1}


class TopicDraftOutput(BaseModel):
    """Strict wire contract for an optional model-authored topic proposal."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=240)
    goal: str = Field(min_length=1, max_length=3000)
    concepts: list[str] = Field(min_length=1, max_length=20)
    synonyms: list[str] = Field(default_factory=list, max_length=30)
    exclusions: list[str] = Field(default_factory=list, max_length=20)
    jurisdictions: list[str] = Field(min_length=1, max_length=12)
    languages: list[str] = Field(min_length=1, max_length=5)
    source_pack_ids: list[str] = Field(min_length=1, max_length=20)
    document_kinds: list[str] = Field(min_length=1, max_length=20)
    event_kinds: list[str] = Field(min_length=1, max_length=20)
    importance_floor: str = "low"


def draft_context(session: Session) -> dict:
    packs = list(
        session.scalars(
            select(SourcePackDefinition).where(
                SourcePackDefinition.parent_id.is_not(None),
                SourcePackDefinition.active.is_(True),
            ).order_by(SourcePackDefinition.position, SourcePackDefinition.id)
        )
    )
    return {
        "source_packs": [
            {
                "id": item.id,
                "name": item.name_json,
                "description": item.description_json,
            }
            for item in packs
        ],
        "languages": sorted(ALLOWED_LANGUAGES),
        "document_kinds": sorted(ALLOWED_DOCUMENT_KINDS),
        "event_kinds": sorted(ALLOWED_EVENT_KINDS),
        "importance_floors": sorted(ALLOWED_IMPORTANCE),
    }


def parse_draft(raw: str) -> TopicDraftOutput:
    value = raw.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.IGNORECASE)
    try:
        return TopicDraftOutput.model_validate_json(value)
    except (ValidationError, ValueError) as error:
        raise DomainError(
            "The model returned an invalid monitoring plan draft.",
            502,
            "monitoring_topic_draft_invalid",
        ) from error


def save_draft(
    session: Session,
    *,
    goal: str,
    plan: dict,
    provider: str,
    model: str,
    prompt_revision: int,
    actor_user_id: str | None,
) -> dict:
    normalized = normalize_plan(plan, session)
    record = MonitoringTopicDraft(
        goal_input=goal,
        plan_json=normalized,
        provider=provider,
        model=model,
        prompt_revision=prompt_revision,
        created_by_user_id=actor_user_id,
    )
    session.add(record)
    session.commit()
    return {
        "id": record.id,
        "plan": normalized,
        "provider": record.provider,
        "model": record.model,
        "prompt_revision": record.prompt_revision,
        "created_at": _iso(record.created_at),
        "requires_confirmation": True,
    }


def _draft_metadata(session: Session, draft_id: str | None) -> tuple[dict | None, MonitoringTopicDraft | None]:
    if not draft_id:
        return None, None
    draft = session.get(MonitoringTopicDraft, draft_id)
    if not draft:
        raise DomainError(
            "The AI draft was not found for this organization.",
            404,
            "monitoring_topic_draft_not_found",
        )
    return {
        "provider": draft.provider,
        "model": draft.model,
        "prompt_revision": draft.prompt_revision,
    }, draft


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).isoformat()


def _clean_list(values: list[str], *, limit: int, item_limit: int = 120) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values[:limit]:
        value = re.sub(r"\s+", " ", raw).strip()[:item_limit]
        key = value.casefold()
        if value and key not in seen:
            result.append(value)
            seen.add(key)
    return result


def normalize_plan(data: dict, session: Session) -> dict:
    name = re.sub(r"\s+", " ", data.get("name", "")).strip()[:240]
    goal = re.sub(r"\s+", " ", data.get("goal", "")).strip()[:3000]
    concepts = _clean_list(data.get("concepts", []), limit=20)
    synonyms = _clean_list(data.get("synonyms", []), limit=30)
    exclusions = _clean_list(data.get("exclusions", []), limit=20)
    jurisdictions = _clean_list(data.get("jurisdictions", []), limit=12, item_limit=40)
    languages = _clean_list(data.get("languages", []), limit=5, item_limit=5)
    source_pack_ids = _clean_list(data.get("source_pack_ids", []), limit=20)
    document_kinds = _clean_list(data.get("document_kinds", []), limit=20, item_limit=40)
    event_kinds = _clean_list(data.get("event_kinds", []), limit=20, item_limit=40)
    importance_floor = data.get("importance_floor", "low")
    if not name or not goal or not concepts:
        raise DomainError(
            "Name, goal, and at least one concept are required.",
            422,
            "monitoring_topic_plan_incomplete",
        )
    if not jurisdictions:
        raise DomainError("Choose at least one jurisdiction.", 422, "monitoring_topic_jurisdiction_required")
    if not languages or not set(languages) <= ALLOWED_LANGUAGES:
        raise DomainError("Choose supported topic languages.", 422, "monitoring_topic_language_invalid")
    if not document_kinds or not set(document_kinds) <= ALLOWED_DOCUMENT_KINDS:
        raise DomainError("Choose supported document kinds.", 422, "monitoring_topic_document_kind_invalid")
    if not event_kinds or not set(event_kinds) <= ALLOWED_EVENT_KINDS:
        raise DomainError("Choose supported event kinds.", 422, "monitoring_topic_event_kind_invalid")
    if importance_floor not in ALLOWED_IMPORTANCE:
        raise DomainError("Choose a supported importance floor.", 422, "monitoring_topic_importance_invalid")
    definitions = {
        item.id
        for item in session.scalars(
            select(SourcePackDefinition).where(
                SourcePackDefinition.id.in_(source_pack_ids),
                SourcePackDefinition.parent_id.is_not(None),
                SourcePackDefinition.active.is_(True),
            )
        )
    }
    if not source_pack_ids or definitions != set(source_pack_ids):
        raise DomainError("Choose available source packs.", 422, "monitoring_topic_source_pack_invalid")
    return {
        "name": name,
        "goal": goal,
        "concepts": concepts,
        "synonyms": synonyms,
        "exclusions": exclusions,
        "jurisdictions": jurisdictions,
        "languages": languages,
        "source_pack_ids": source_pack_ids,
        "document_kinds": document_kinds,
        "event_kinds": event_kinds,
        "importance_floor": importance_floor,
    }


def _revision_payload(record: MonitoringTopicRevision) -> dict:
    return {
        "id": record.id,
        "revision": record.revision,
        "status": record.status,
        "name": record.name,
        "goal": record.goal,
        "concepts": record.concepts_json,
        "synonyms": record.synonyms_json,
        "exclusions": record.exclusions_json,
        "jurisdictions": record.jurisdictions_json,
        "languages": record.languages_json,
        "source_pack_ids": record.source_pack_ids_json,
        "document_kinds": record.document_kinds_json,
        "event_kinds": record.event_kinds_json,
        "importance_floor": record.importance_floor,
        "author_user_id": record.author_user_id,
        "ai_assisted": bool(record.ai_provider),
        "ai_provider": record.ai_provider,
        "ai_model": record.ai_model,
        "prompt_revision": record.prompt_revision,
        "created_at": _iso(record.created_at),
    }


def _current_revision(session: Session, topic: MonitoringTopic) -> MonitoringTopicRevision:
    record = session.scalar(
        select(MonitoringTopicRevision).where(
            MonitoringTopicRevision.topic_id == topic.id,
            MonitoringTopicRevision.revision == topic.current_revision,
        )
    )
    if not record:
        raise DomainError("The current topic revision is missing.", 409, "monitoring_topic_revision_missing")
    return record


def _topic_payload(session: Session, topic: MonitoringTopic, *, history: bool = False) -> dict:
    current = _current_revision(session, topic)
    result = {
        "id": topic.id,
        "status": topic.status,
        "current_revision": topic.current_revision,
        "created_by_user_id": topic.created_by_user_id,
        "created_at": _iso(topic.created_at),
        "updated_at": _iso(topic.updated_at),
        "archived_at": _iso(topic.archived_at),
        "plan": _revision_payload(current),
    }
    if history:
        result["revisions"] = [
            _revision_payload(item)
            for item in session.scalars(
                select(MonitoringTopicRevision)
                .where(MonitoringTopicRevision.topic_id == topic.id)
                .order_by(MonitoringTopicRevision.revision.desc())
            )
        ]
    return result


def list_topics(session: Session, *, include_archived: bool = False) -> list[dict]:
    statement = select(MonitoringTopic)
    if not include_archived:
        statement = statement.where(MonitoringTopic.status != "archived")
    return [
        _topic_payload(session, item, history=True)
        for item in session.scalars(statement.order_by(MonitoringTopic.updated_at.desc()))
    ]


def get_topic(session: Session, topic_id: str) -> dict:
    topic = session.get(MonitoringTopic, topic_id)
    if not topic:
        raise DomainError("The monitoring topic was not found.", 404, "monitoring_topic_not_found")
    return _topic_payload(session, topic, history=True)


def _add_revision(
    session: Session,
    topic: MonitoringTopic,
    plan: dict,
    *,
    status: str,
    actor_user_id: str | None,
    ai_metadata: dict | None = None,
) -> MonitoringTopicRevision:
    revision = MonitoringTopicRevision(
        topic_id=topic.id,
        revision=topic.current_revision,
        status=status,
        name=plan["name"],
        goal=plan["goal"],
        concepts_json=plan["concepts"],
        synonyms_json=plan["synonyms"],
        exclusions_json=plan["exclusions"],
        jurisdictions_json=plan["jurisdictions"],
        languages_json=plan["languages"],
        source_pack_ids_json=plan["source_pack_ids"],
        document_kinds_json=plan["document_kinds"],
        event_kinds_json=plan["event_kinds"],
        importance_floor=plan["importance_floor"],
        author_user_id=actor_user_id,
        ai_provider=(ai_metadata or {}).get("provider"),
        ai_model=(ai_metadata or {}).get("model"),
        prompt_revision=(ai_metadata or {}).get("prompt_revision"),
    )
    session.add(revision)
    return revision


def _enqueue_match_backfill(
    session: Session, topic: MonitoringTopic, *, organization_id: str | None = None
):
    job, _ = durable_jobs.enqueue(
        session,
        job_type="topic_match_backfill",
        target_type="monitoring_topic",
        target_id=topic.id,
        queue="ingest",
        idempotency_key=f"topic-match:{topic.id}:{topic.current_revision}",
        payload={"topic_id": topic.id, "revision": topic.current_revision},
        priority=5,
        progress_total=1,
        steps=[("Match a bounded saved-event window", {})],
        organization_id=organization_id,
    )
    return durable_jobs.serialize(session, job)


def create_topic(
    session: Session,
    data: dict,
    *,
    idempotency_key: str,
    actor_user_id: str | None,
    ai_draft_id: str | None = None,
) -> dict:
    key = idempotency_key.strip()[:120]
    if not key:
        raise DomainError("An idempotency key is required.", 422, "idempotency_key_required")
    existing = session.scalar(select(MonitoringTopic).where(MonitoringTopic.idempotency_key == key))
    if existing:
        return {**_topic_payload(session, existing, history=True), "reused": True}
    plan = normalize_plan(data, session)
    ai_metadata, draft = _draft_metadata(session, ai_draft_id)
    topic = MonitoringTopic(
        idempotency_key=key,
        status="active",
        current_revision=1,
        created_by_user_id=actor_user_id,
    )
    session.add(topic)
    session.flush()
    _add_revision(
        session,
        topic,
        plan,
        status="active",
        actor_user_id=actor_user_id,
        ai_metadata=ai_metadata,
    )
    if draft:
        draft.used_at = utcnow()
    backfill_job = _enqueue_match_backfill(session, topic)
    session.commit()
    return {
        **_topic_payload(session, topic, history=True),
        "reused": False,
        "backfill_job": backfill_job,
    }


def update_topic(
    session: Session,
    topic_id: str,
    data: dict,
    *,
    expected_revision: int,
    actor_user_id: str | None,
    ai_draft_id: str | None = None,
) -> dict:
    topic = session.get(MonitoringTopic, topic_id)
    if not topic:
        raise DomainError("The monitoring topic was not found.", 404, "monitoring_topic_not_found")
    if topic.status == "archived":
        raise DomainError("Archived topics cannot be edited.", 409, "monitoring_topic_archived")
    if topic.current_revision != expected_revision:
        raise DomainError(
            "This topic changed while you were editing it. Reload the latest revision.",
            409,
            "monitoring_topic_revision_conflict",
        )
    plan = normalize_plan(data, session)
    ai_metadata, draft = _draft_metadata(session, ai_draft_id)
    current = _current_revision(session, topic)
    comparable = {key: _revision_payload(current)[key] for key in plan}
    if comparable == plan:
        return {**_topic_payload(session, topic, history=True), "reused": True}
    topic.current_revision += 1
    topic.updated_at = utcnow()
    _add_revision(
        session,
        topic,
        plan,
        status=topic.status,
        actor_user_id=actor_user_id,
        ai_metadata=ai_metadata,
    )
    if draft:
        draft.used_at = utcnow()
    backfill_job = _enqueue_match_backfill(session, topic)
    session.commit()
    return {
        **_topic_payload(session, topic, history=True),
        "reused": False,
        "backfill_job": backfill_job,
    }


def change_status(
    session: Session,
    topic_id: str,
    status: str,
    *,
    expected_revision: int,
    actor_user_id: str | None,
) -> dict:
    topic = session.get(MonitoringTopic, topic_id)
    if not topic:
        raise DomainError("The monitoring topic was not found.", 404, "monitoring_topic_not_found")
    if topic.current_revision != expected_revision:
        raise DomainError("Reload the latest topic revision.", 409, "monitoring_topic_revision_conflict")
    if status == topic.status:
        return {**_topic_payload(session, topic, history=True), "reused": True}
    if status not in STATUS_TRANSITIONS.get(topic.status, set()):
        raise DomainError("This topic status change is not allowed.", 409, "monitoring_topic_status_invalid")
    current = _current_revision(session, topic)
    plan = {key: _revision_payload(current)[key] for key in (
        "name", "goal", "concepts", "synonyms", "exclusions", "jurisdictions", "languages",
        "source_pack_ids", "document_kinds", "event_kinds", "importance_floor",
    )}
    topic.current_revision += 1
    topic.status = status
    topic.updated_at = utcnow()
    if status == "archived":
        topic.archived_at = topic.updated_at
    _add_revision(session, topic, plan, status=status, actor_user_id=actor_user_id)
    backfill_job = _enqueue_match_backfill(session, topic) if status == "active" else None
    session.commit()
    return {
        **_topic_payload(session, topic, history=True),
        "reused": False,
        "backfill_job": backfill_job,
    }


def _values(raw: object) -> set[str]:
    if isinstance(raw, str):
        return {raw.casefold()}
    if isinstance(raw, list):
        return {str(item).casefold() for item in raw}
    return set()


def preview(session: Session, data: dict) -> dict:
    plan = normalize_plan(data, session)
    pack_definitions = list(
        session.scalars(
            select(SourcePackDefinition).where(SourcePackDefinition.id.in_(plan["source_pack_ids"]))
        )
    )
    rows = list(
        session.execute(
            select(RegulatoryEvent, RegulatoryWork, RegulatoryExpression)
            .join(RegulatoryWork, RegulatoryWork.id == RegulatoryEvent.work_id)
            .outerjoin(RegulatoryExpression, RegulatoryExpression.id == RegulatoryEvent.expression_id)
            .order_by(RegulatoryEvent.detected_at.desc(), RegulatoryEvent.id.desc())
            .limit(PREVIEW_SCAN_LIMIT + 1)
        )
    )
    scan_truncated = len(rows) > PREVIEW_SCAN_LIMIT
    candidates: list[dict] = []
    terms = [(value, "concept") for value in plan["concepts"]] + [
        (value, "synonym") for value in plan["synonyms"]
    ]
    for event, work, expression in rows[:PREVIEW_SCAN_LIMIT]:
        stream = str((event.evidence_json or {}).get("stream", ""))
        if not any(definition_matches(item, event.connector, stream) for item in pack_definitions):
            continue
        if work.kind not in plan["document_kinds"] or event.event_type not in plan["event_kinds"]:
            continue
        if IMPORTANCE_RANK.get(event.impact, 1) < IMPORTANCE_RANK[plan["importance_floor"]]:
            continue
        metadata = work.metadata_json or {}
        evidence = event.evidence_json or {}
        jurisdictions = _values(metadata.get("jurisdiction") or metadata.get("jurisdictions") or evidence.get("jurisdiction") or "CH")
        if jurisdictions.isdisjoint(value.casefold() for value in plan["jurisdictions"]):
            continue
        language = (expression.language if expression else evidence.get("language")) or ""
        if language and language.casefold() not in {value.casefold() for value in plan["languages"]}:
            continue
        haystack = " ".join(
            [work.title, expression.title if expression else "", json.dumps(metadata, ensure_ascii=False), json.dumps(evidence, ensure_ascii=False)]
        ).casefold()
        if any(value.casefold() in haystack for value in plan["exclusions"]):
            continue
        matched = [(value, kind) for value, kind in terms if value.casefold() in haystack]
        if not matched:
            continue
        candidates.append(
            {
                "event_id": event.id,
                "work_id": work.id,
                "title": expression.title if expression and expression.title else work.title,
                "event_type": event.event_type,
                "document_kind": work.kind,
                "authority": event.authority,
                "detected_at": _iso(event.detected_at),
                "source_url": event.source_url or work.stable_official_url,
                "importance": event.impact,
                "match_type": "topic_candidate",
                "legal_relation_confirmed": False,
                "reason_signals": [
                    {"type": kind, "value": value} for value, kind in matched[:5]
                ]
                + [{"type": "source_pack", "value": item.id} for item in pack_definitions if definition_matches(item, event.connector, stream)],
            }
        )
    return {
        "candidate_count": len(candidates),
        "count_is_complete": not scan_truncated,
        "scanned_event_limit": PREVIEW_SCAN_LIMIT,
        "representative_limit": PREVIEW_RESULT_LIMIT,
        "items": candidates[:PREVIEW_RESULT_LIMIT],
        "explanation": "Deterministic preview over saved events only; no AI inference and no confirmed legal relation.",
    }
