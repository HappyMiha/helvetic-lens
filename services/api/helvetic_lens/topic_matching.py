"""Bounded topic matching over the shared regulatory event corpus."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import Text, cast, or_, select, text
from sqlalchemy.orm import Session

from .config import DomainError, Settings
from .db import utcnow
from .models import (
    MonitoringTopic,
    MonitoringTopicRevision,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryExpression,
    RegulatoryIdentifier,
    RegulatoryWork,
    SourcePackDefinition,
    TopicEventMatch,
)
from .monitoring_topics import IMPORTANCE_RANK
from .relation_candidates import legal_references, normalized_title_tokens
from .source_packs import definition_matches

RULE_REVISION = "topic-match-v1"


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).isoformat()


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _strings(child)]
    if isinstance(value, (list, tuple)):
        return [item for child in value for item in _strings(child)]
    return []


def _values(value: object) -> set[str]:
    return {item.casefold() for item in _strings(value)}


def _fingerprint(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _candidate_revisions(
    session: Session,
    organization_id: str,
    event: RegulatoryEvent,
    work: RegulatoryWork,
    settings: Settings,
    *,
    topic_id: str | None = None,
) -> tuple[list[tuple[MonitoringTopic, MonitoringTopicRevision]], bool]:
    statement = (
        select(MonitoringTopic, MonitoringTopicRevision)
        .join(
            MonitoringTopicRevision,
            (MonitoringTopicRevision.topic_id == MonitoringTopic.id)
            & (MonitoringTopicRevision.revision == MonitoringTopic.current_revision),
        )
        .where(
            MonitoringTopic.organization_id == organization_id,
            MonitoringTopic.status == "active",
        )
    )
    base_statement = statement
    filtered = False
    if topic_id:
        statement = statement.where(MonitoringTopic.id == topic_id)
        base_statement = statement
    else:
        tokens = sorted(normalized_title_tokens(work.title))[:12]
        official_norms, _ = legal_references(
            work.title,
            work.metadata_json,
            event.evidence_json,
            [
                f"{'SR' if item.scheme == 'sr_rs' else item.scheme} {item.normalized_value}"
                for item in session.scalars(
                    select(RegulatoryIdentifier).where(RegulatoryIdentifier.work_id == work.id)
                )
            ],
        )
        searchable = (
            MonitoringTopicRevision.name,
            MonitoringTopicRevision.goal,
            cast(MonitoringTopicRevision.concepts_json, Text),
            cast(MonitoringTopicRevision.synonyms_json, Text),
        )
        exact_predicates = [
            column.ilike(f"%{reference}%")
            for reference in sorted(official_norms)
            for column in searchable
        ]
        if session.bind and session.bind.dialect.name == "postgresql" and tokens:
            query = " | ".join(f"{token}:*" for token in tokens)
            fts_predicate = text(
                "to_tsvector('simple', concat_ws(' ', monitoring_topic_revisions.name, "
                "monitoring_topic_revisions.goal, "
                "cast(monitoring_topic_revisions.concepts_json as text), "
                "cast(monitoring_topic_revisions.synonyms_json as text))) "
                "@@ to_tsquery('simple', :topic_query)"
            ).bindparams(topic_query=query)
            statement = statement.where(or_(fts_predicate, *exact_predicates))
            filtered = True
        elif tokens or exact_predicates:
            # SQLite is the deterministic test store. Keep the same shortlist
            # semantics without pretending it offers PostgreSQL full text.
            lexical_predicates = [
                column.ilike(f"%{token}%") for token in tokens for column in searchable
            ]
            statement = statement.where(or_(*lexical_predicates, *exact_predicates))
            filtered = True
    rows = list(
        session.execute(
            statement.order_by(MonitoringTopic.updated_at.desc(), MonitoringTopic.id)
            .limit(settings.topic_match_topics_per_organization_event + 1)
            .execution_options(include_all_organizations=True)
        )
    )
    # The deterministic shortlist is recall-oriented. Full text/exact lookup
    # runs first; any remaining capacity is filled from the organization's
    # newest active topics and then evaluated by the same controlled filters.
    # This fallback remains capped and never loads an all-topic/all-event cross
    # product into application memory.
    if filtered and len(rows) < settings.topic_match_topics_per_organization_event + 1:
        existing_ids = [topic.id for topic, _revision in rows]
        remaining = settings.topic_match_topics_per_organization_event + 1 - len(rows)
        fallback = base_statement
        if existing_ids:
            fallback = fallback.where(MonitoringTopic.id.not_in(existing_ids))
        rows.extend(
            session.execute(
                fallback.order_by(MonitoringTopic.updated_at.desc(), MonitoringTopic.id)
                .limit(remaining)
                .execution_options(include_all_organizations=True)
            )
        )
    return rows[: settings.topic_match_topics_per_organization_event], (
        len(rows) > settings.topic_match_topics_per_organization_event
    )


def _score(
    session: Session,
    event: RegulatoryEvent,
    work: RegulatoryWork,
    expression: RegulatoryExpression | None,
    revision: MonitoringTopicRevision,
    definitions: dict[str, SourcePackDefinition],
) -> tuple[str, list[dict]] | None:
    plan_packs = [definitions[item] for item in revision.source_pack_ids_json if item in definitions]
    stream = str((event.evidence_json or {}).get("stream", ""))
    if not plan_packs or not any(
        definition_matches(item, event.connector, stream) for item in plan_packs
    ):
        return None
    if work.kind not in revision.document_kinds_json or event.event_type not in revision.event_kinds_json:
        return None
    if IMPORTANCE_RANK.get(event.impact, 1) < IMPORTANCE_RANK[revision.importance_floor]:
        return None
    evidence = event.evidence_json or {}
    metadata = work.metadata_json or {}
    jurisdictions = _values(
        metadata.get("jurisdiction")
        or metadata.get("jurisdictions")
        or evidence.get("jurisdiction")
        or "CH"
    )
    if jurisdictions.isdisjoint(item.casefold() for item in revision.jurisdictions_json):
        return None
    language = (expression.language if expression else evidence.get("language")) or ""
    if language and language.casefold() not in {
        item.casefold() for item in revision.languages_json
    }:
        return None

    identifiers = list(
        session.scalars(select(RegulatoryIdentifier).where(RegulatoryIdentifier.work_id == work.id))
    )
    identifier_values = [
        f"{'SR' if item.scheme == 'sr_rs' else item.scheme} {item.value}"
        for item in identifiers
    ] + [item.normalized_value for item in identifiers]
    haystack = " ".join(
        [
            work.title,
            expression.title if expression else "",
            *identifier_values,
            *_strings(metadata),
            *_strings(evidence),
        ]
    ).casefold()
    if any(item.casefold() in haystack for item in revision.exclusions_json):
        return None

    topic_values = [*revision.concepts_json, *revision.synonyms_json]
    event_norms, event_articles = legal_references(haystack)
    topic_norms, topic_articles = legal_references(topic_values)
    signals: list[dict] = []
    if event_norms & topic_norms:
        signals.append(
            {"type": "official_identifier", "values": sorted(event_norms & topic_norms)}
        )
    if event_articles & topic_articles:
        signals.append({"type": "article_reference", "values": sorted(event_articles & topic_articles)})
    for kind, values in (
        ("concept", revision.concepts_json),
        ("synonym", revision.synonyms_json),
    ):
        for value in values:
            normalized = value.casefold().strip()
            if normalized and normalized in haystack:
                signals.append({"type": kind, "value": value})
    if not signals:
        event_tokens = normalized_title_tokens(haystack)
        for value in revision.concepts_json:
            overlap = normalized_title_tokens(value) & event_tokens
            if overlap:
                signals.append({"type": "fts_term", "value": value, "tokens": sorted(overlap)})
    if not signals:
        return None
    confidence = "high" if any(item["type"] in {"official_identifier", "concept"} for item in signals) else "medium"
    return confidence, signals[:20]


def generate_for_events(
    session: Session,
    events: list[RegulatoryEvent],
    settings: Settings,
    *,
    topic_id: str | None = None,
) -> dict:
    """Match only organizations already entitled to each event, under hard caps."""

    now = utcnow()
    result = {
        "events": 0,
        "organizations_considered": 0,
        "topics_considered": 0,
        "matched": 0,
        "updated": 0,
        "reused": 0,
        "organization_bound_hit": False,
        "topic_bound_hit": False,
        "match_bound_hit": False,
        "ai_calls": 0,
        "ai_candidates_capped_at": settings.topic_match_ai_candidates_per_event,
    }
    definitions = {
        item.id: item
        for item in session.scalars(select(SourcePackDefinition).where(SourcePackDefinition.active.is_(True)))
    }
    for event in events:
        result["events"] += 1
        work = session.get(RegulatoryWork, event.work_id)
        expression = session.get(RegulatoryExpression, event.expression_id) if event.expression_id else None
        if not work:
            continue
        organization_rows = list(
            session.scalars(
                select(RegulatoryEventState.organization_id)
                .where(RegulatoryEventState.event_id == event.id)
                .order_by(RegulatoryEventState.organization_id)
                .limit(settings.topic_match_organizations_per_event + 1)
                .execution_options(include_all_organizations=True)
            )
        )
        if len(organization_rows) > settings.topic_match_organizations_per_event:
            result["organization_bound_hit"] = True
        for organization_id in organization_rows[: settings.topic_match_organizations_per_event]:
            result["organizations_considered"] += 1
            candidates, truncated = _candidate_revisions(
                session, organization_id, event, work, settings, topic_id=topic_id
            )
            result["topic_bound_hit"] = result["topic_bound_hit"] or truncated
            result["topics_considered"] += len(candidates)
            ranked: list[tuple[int, MonitoringTopic, MonitoringTopicRevision, str, list[dict]]] = []
            for topic, revision in candidates:
                scored = _score(session, event, work, expression, revision, definitions)
                if scored:
                    confidence, signals = scored
                    ranked.append((0 if confidence == "high" else 1, topic, revision, confidence, signals))
            ranked.sort(key=lambda item: (item[0], item[1].id))
            if len(ranked) > settings.topic_matches_per_organization_event:
                result["match_bound_hit"] = True
            for _, topic, revision, confidence, signals in ranked[
                : settings.topic_matches_per_organization_event
            ]:
                evidence = {
                    "event_id": event.id,
                    "work_id": work.id,
                    "expression_id": event.expression_id,
                    "document_version_id": event.document_version_id,
                    "source_url": event.source_url or work.stable_official_url,
                    "detected_at": _iso(event.detected_at),
                    "provenance_method": event.provenance_method,
                    "official_identifiers": [
                        {"scheme": item.scheme, "value": item.value, "source_url": item.source_url}
                        for item in session.scalars(
                            select(RegulatoryIdentifier).where(RegulatoryIdentifier.work_id == work.id)
                        )
                    ],
                }
                evidence_fingerprint = _fingerprint(
                    {"event": evidence, "event_evidence": event.evidence_json, "signals": signals}
                )
                rule_fingerprint = f"{RULE_REVISION}:{revision.revision}"
                record = session.scalar(
                    select(TopicEventMatch)
                    .where(
                        TopicEventMatch.organization_id == organization_id,
                        TopicEventMatch.topic_revision_id == revision.id,
                        TopicEventMatch.event_id == event.id,
                    )
                    .execution_options(include_all_organizations=True)
                )
                if record and record.evidence_fingerprint == evidence_fingerprint and record.rule_fingerprint == rule_fingerprint:
                    result["reused"] += 1
                    continue
                if not record:
                    record = TopicEventMatch(
                        organization_id=organization_id,
                        topic_id=topic.id,
                        topic_revision_id=revision.id,
                        event_id=event.id,
                        work_id=work.id,
                        expires_at=now,
                    )
                    session.add(record)
                    result["matched"] += 1
                else:
                    record.decision_status = "pending"
                    result["updated"] += 1
                record.expression_id = event.expression_id
                record.document_version_id = event.document_version_id
                record.reason_signals_json = signals
                record.evidence_references_json = evidence
                record.evidence_fingerprint = evidence_fingerprint
                record.rule_fingerprint = rule_fingerprint
                record.model_provider = None
                record.model_name = None
                record.model_prompt_revision = None
                record.confidence_band = confidence
                record.matched_at = now
                record.updated_at = now
                record.expires_at = now + timedelta(days=settings.topic_match_retention_days)
    session.flush()
    return result


def run_backfill(
    session: Session,
    topic_id: str,
    revision: int,
    settings: Settings,
) -> dict:
    topic = session.get(MonitoringTopic, topic_id)
    if not topic:
        raise DomainError("The monitoring topic was not found.", 404, "monitoring_topic_not_found")
    if topic.status != "active" or topic.current_revision != revision:
        return {"status": "superseded", "matched": 0, "reused": 0, "has_more": False}
    rows = list(
        session.scalars(
            select(RegulatoryEvent)
            .join(RegulatoryEventState, RegulatoryEventState.event_id == RegulatoryEvent.id)
            .where(RegulatoryEventState.organization_id == topic.organization_id)
            .order_by(RegulatoryEvent.detected_at.desc(), RegulatoryEvent.id.desc())
            .limit(settings.topic_match_backfill_limit + 1)
        )
    )
    has_more = len(rows) > settings.topic_match_backfill_limit
    result = generate_for_events(
        session, rows[: settings.topic_match_backfill_limit], settings, topic_id=topic.id
    )
    return {"status": "bounded_complete", "has_more": has_more, **result}


def list_matches(session: Session, topic_id: str, *, limit: int = 100) -> list[dict]:
    topic = session.get(MonitoringTopic, topic_id)
    if not topic:
        raise DomainError("The monitoring topic was not found.", 404, "monitoring_topic_not_found")
    records = session.scalars(
        select(TopicEventMatch)
        .where(TopicEventMatch.topic_id == topic.id)
        .order_by(TopicEventMatch.matched_at.desc(), TopicEventMatch.id.desc())
        .limit(max(1, min(limit, 200)))
    )
    return [
        {
            "id": item.id,
            "topic_id": item.topic_id,
            "topic_revision_id": item.topic_revision_id,
            "event_id": item.event_id,
            "work_id": item.work_id,
            "expression_id": item.expression_id,
            "document_version_id": item.document_version_id,
            "reasons": item.reason_signals_json,
            "evidence": item.evidence_references_json,
            "rule_fingerprint": item.rule_fingerprint,
            "confidence": item.confidence_band,
            "decision": item.decision_status,
            "matched_at": _iso(item.matched_at),
            "expires_at": _iso(item.expires_at),
        }
        for item in records
    ]
