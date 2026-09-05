"""Bounded topic matching over the shared regulatory event corpus."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta

from sqlalchemy import Text, cast, func, or_, select, text
from sqlalchemy.orm import Session

from . import jobs
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
HISTORY_REVISION = "topic-history-v1"
LIVE_REVISION = "topic-live-v1"
EVALUATION_REVISION = "topic-evaluation-v1"


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


def score_event(
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


def _preserve_review(record: TopicEventMatch) -> None:
    """Bind an existing human decision to its original evidence, never reset it.

    The review endpoint will supply an explicit snapshot when implemented. For
    older/scripted decisions capture only known provenance; no invented actor or
    decision date, and a missing evaluation fingerprint stays unverifiable.
    """
    if record.decision_status == "pending":
        return
    snapshot = record.review_snapshot_json or {}
    if snapshot.get("decision") == record.decision_status:
        return
    record.review_snapshot_json = deepcopy({
        "decision": record.decision_status,
        "evidence_fingerprint": record.evidence_fingerprint,
        "evaluation_fingerprint": record.evaluation_fingerprint,
        "rule_fingerprint": record.rule_fingerprint,
        "reasons": record.reason_signals_json,
        "evidence": record.evidence_references_json,
        "confidence": record.confidence_band,
        "matched_at": _iso(record.matched_at),
    })


def _evaluation_fingerprint(session: Session, event: RegulatoryEvent,
                            revision: MonitoringTopicRevision,
                            definitions: dict[str, SourcePackDefinition],
                            evidence_fingerprint: str | None = None) -> str:
    return _fingerprint([
        EVALUATION_REVISION, evidence_fingerprint or _live_evidence_fingerprint(session, event), revision.id,
        [(key, definitions[key].revision, definitions[key].filters_json)
         for key in sorted(revision.source_pack_ids_json) if key in definitions],
    ])


def _persist_evaluation(
    session: Session, event: RegulatoryEvent, work: RegulatoryWork,
    topic: MonitoringTopic, revision: MonitoringTopicRevision,
    scored: tuple[str, list[dict]] | None, definitions: dict[str, SourcePackDefinition],
    settings: Settings, *, evidence_fingerprint: str | None = None,
) -> str:
    """Persist one eligibility result without erasing a human decision.

    Never create rows for every negative event/topic pair. An existing match
    keeps its last positive evidence when it stops matching, alongside the
    latest machine evaluation; the two states have different meanings.
    """
    now = utcnow()
    record = session.scalar(
        select(TopicEventMatch).where(
            TopicEventMatch.organization_id == topic.organization_id,
            TopicEventMatch.topic_revision_id == revision.id,
            TopicEventMatch.event_id == event.id,
        ).with_for_update().execution_options(include_all_organizations=True)
    )
    if not record and not scored:
        return "excluded"
    fingerprint = _evaluation_fingerprint(session, event, revision, definitions, evidence_fingerprint)
    rule_fingerprint = f"{RULE_REVISION}:{revision.revision}"
    status = "matching" if scored else "not_matching"
    if record:
        _preserve_review(record)
        if (record.match_status == status and record.evaluation_fingerprint == fingerprint
                and record.evaluated_rule_fingerprint == rule_fingerprint):
            return "reused" if scored else "excluded"
        outcome = "updated" if scored else "invalidated"
    else:
        record = TopicEventMatch(
            organization_id=topic.organization_id, topic_id=topic.id,
            topic_revision_id=revision.id, event_id=event.id, work_id=work.id,
            expires_at=now,
        )
        outcome = "matched"
    record.match_status = status
    record.evaluation_fingerprint = fingerprint
    record.evaluated_rule_fingerprint = rule_fingerprint
    record.evaluated_at = now
    record.updated_at = now
    if not scored:
        return outcome

    confidence, signals = scored
    expression = session.get(RegulatoryExpression, event.expression_id) if event.expression_id else None
    evidence = {
        "event_id": event.id, "work_id": work.id,
        "expression_id": event.expression_id, "document_version_id": event.document_version_id,
        "source_url": event.source_url or work.stable_official_url,
        "detected_at": _iso(event.detected_at), "provenance_method": event.provenance_method,
        "work_title": work.title, "work_kind": work.kind,
        "expression_title": expression.title if expression else None,
        "expression_language": expression.language if expression else None,
        "event_type": event.event_type, "impact": event.impact,
        "source_evidence": deepcopy(event.evidence_json),
        "work_metadata": deepcopy(work.metadata_json),
        "official_identifiers": [
            {"scheme": item.scheme, "value": item.value, "source_url": item.source_url}
            for item in session.scalars(select(RegulatoryIdentifier).where(RegulatoryIdentifier.work_id == work.id))
        ],
    }
    record.expression_id = event.expression_id
    record.document_version_id = event.document_version_id
    record.reason_signals_json = signals
    record.evidence_references_json = evidence
    record.evidence_fingerprint = _fingerprint({"event": evidence, "signals": signals})
    record.rule_fingerprint = rule_fingerprint
    record.model_provider = None
    record.model_name = None
    record.model_prompt_revision = None
    record.confidence_band = confidence
    record.matched_at = now
    record.expires_at = now + timedelta(days=settings.topic_match_retention_days)
    session.add(record)
    return outcome


def generate_for_events(
    session: Session,
    events: list[RegulatoryEvent],
    settings: Settings,
    *,
    topic_id: str | None = None,
) -> dict:
    """Match only organizations already entitled to each event, under hard caps."""

    # A topic-specific replay belongs only to that topic's organization. Global
    # fan-out caps must not exclude its owner or enumerate other organizations.
    topic_organization = None
    if topic_id:
        topic = session.get(MonitoringTopic, topic_id)
        if not topic:
            raise DomainError("The monitoring topic was not found.", 404, "monitoring_topic_not_found")
        topic_organization = topic.organization_id
    result = {
        "events": 0,
        "organizations_considered": 0,
        "topics_considered": 0,
        "matched": 0,
        "updated": 0,
        "reused": 0,
        "invalidated": 0,
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
        event_fingerprint = _live_evidence_fingerprint(session, event)
        organization_rows = list(
            session.scalars(
                select(RegulatoryEventState.organization_id)
                .where(
                    RegulatoryEventState.event_id == event.id,
                    *([RegulatoryEventState.organization_id == topic_organization] if topic_organization else []),
                )
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
                scored = score_event(session, event, work, expression, revision, definitions)
                if scored:
                    confidence, signals = scored
                    ranked.append((0 if confidence == "high" else 1, topic, revision, confidence, signals))
                else:
                    outcome = _persist_evaluation(session, event, work, topic, revision, None, definitions, settings, evidence_fingerprint=event_fingerprint)
                    if outcome == "invalidated":
                        result["invalidated"] += 1
            ranked.sort(key=lambda item: (item[0], item[1].id))
            if len(ranked) > settings.topic_matches_per_organization_event:
                result["match_bound_hit"] = True
            for _, topic, revision, confidence, signals in ranked[
                : settings.topic_matches_per_organization_event
            ]:
                outcome = _persist_evaluation(session, event, work, topic, revision, (confidence, signals), definitions, settings, evidence_fingerprint=event_fingerprint)
                result[outcome] += 1
    session.flush()
    return result


def _live_evidence_fingerprint(session: Session, event: RegulatoryEvent) -> str:
    work = session.get(RegulatoryWork, event.work_id)
    expression = session.get(RegulatoryExpression, event.expression_id) if event.expression_id else None
    return _fingerprint({
        "event": [event.id, event.work_id, event.expression_id, event.document_version_id,
                  event.event_type, event.impact, event.connector, event.evidence_json,
                  event.source_url, event.provenance_method, _iso(event.detected_at)],
        "work": [work.title, work.kind, work.metadata_json, work.stable_official_url] if work else None,
        "expression": [expression.title, expression.language] if expression else None,
        "source_definitions": [
            [item.id, item.revision, item.filters_json]
            for item in session.scalars(select(SourcePackDefinition)
                .where(SourcePackDefinition.active.is_(True)).order_by(SourcePackDefinition.id))
        ],
        "identifiers": sorted(
            (item.scheme, item.value, item.normalized_value, item.source_url or "")
            for item in session.scalars(select(RegulatoryIdentifier).where(RegulatoryIdentifier.work_id == event.work_id))
        ),
    })


def enqueue_live_events(session: Session, events: list[RegulatoryEvent], settings: Settings) -> dict:
    """Spool every entitled organization into its own durable, bounded matching job.

    Called in the connector's fan-out transaction. The organization limit is a
    SQL page size, never a recall cutoff. Retrying that transaction is idempotent.
    A tenant session can enqueue only its own admissions; only the internal
    connector session may enumerate all organizations.
    """
    result = {"events": len(events), "organizations_considered": 0,
              "queued": 0, "reused": 0, "ai_calls": 0, "status": "queued"}
    for source in sorted(events, key=lambda item: item.id):
        # Serialize spooling the same event across overlapping connector retries.
        event = session.scalar(select(RegulatoryEvent).where(RegulatoryEvent.id == source.id).with_for_update())
        if not event:
            continue
        fingerprint = _live_evidence_fingerprint(session, event)
        after = ""
        while True:
            admissions = list(session.scalars(
                select(RegulatoryEventState).where(
                    RegulatoryEventState.event_id == event.id,
                    RegulatoryEventState.organization_id > after,
                ).order_by(RegulatoryEventState.organization_id)
                .limit(settings.topic_match_organizations_per_event)
            ))
            if not admissions:
                break
            for state in admissions:
                input_key = _fingerprint([RULE_REVISION, EVALUATION_REVISION, fingerprint])
                # Content can change A -> B -> A. A hash-only key would reuse
                # the first completed A job and leave the B evaluation current.
                # The event lock serializes this durable admission generation.
                if state.topic_match_input_fingerprint != input_key:
                    state.topic_match_generation += 1
                    state.topic_match_input_fingerprint = input_key
                key = _fingerprint([state.id, state.topic_match_generation, input_key])
                _job, reused = jobs.enqueue(
                    session, organization_id=state.organization_id,
                    job_type="topic_match_event", target_type="regulatory_event", target_id=event.id,
                    queue="ingest", idempotency_key=f"{LIVE_REVISION}:{RULE_REVISION}:{EVALUATION_REVISION}:{key}",
                    payload={"event_id": event.id, "admission_id": state.id,
                             "evidence_fingerprint": fingerprint},
                    priority=4, steps=[("Match active topics", {})],
                )
                result["reused" if reused else "queued"] += 1
                result["organizations_considered"] += 1
            after = admissions[-1].organization_id
    return result


def run_live_batch(
    session: Session, event_id: str, settings: Settings, *, admission_id: str,
    evidence_fingerprint: str, checkpoint: dict | None = None,
    captured_at: datetime | None = None,
) -> dict:
    """Exhaust current saved topic rules with a keyset cursor and no model calls."""
    organization_id = session.info["organization_id"]
    checkpoint = dict(checkpoint or {})
    if checkpoint and (
        checkpoint.get("version") != LIVE_REVISION
        or checkpoint.get("organization_id") != organization_id
        or checkpoint.get("event_id") != event_id
        or checkpoint.get("admission_id") != admission_id
        or checkpoint.get("evidence_fingerprint") != evidence_fingerprint
    ):
        raise DomainError("The live matching checkpoint does not match this event.", 409, "topic_checkpoint_invalid")
    if not checkpoint:
        checkpoint = {
            "version": LIVE_REVISION, "rule_revision": RULE_REVISION,
            "organization_id": organization_id, "event_id": event_id, "admission_id": admission_id,
            "evidence_fingerprint": evidence_fingerprint,
            "captured_at": _iso(captured_at or utcnow()), "cursor": None,
            "processed": 0, "matched": 0, "updated": 0, "reused": 0, "excluded": 0, "batches": 0,
        }
    admission = session.scalar(select(RegulatoryEventState).where(
        RegulatoryEventState.id == admission_id, RegulatoryEventState.event_id == event_id,
        RegulatoryEventState.organization_id == organization_id,
    ).with_for_update())
    event = session.get(RegulatoryEvent, event_id) if admission else None
    work = session.get(RegulatoryWork, event.work_id) if event else None
    reason = (
        "event_not_visible" if not admission or not event or not work
        else "matching_rule_changed" if checkpoint["rule_revision"] != RULE_REVISION
        else "evidence_changed" if _live_evidence_fingerprint(session, event) != evidence_fingerprint
        else None
    )
    if reason:
        if event and work and reason != "event_not_visible":
            enqueue_live_events(session, [event], settings)
        return {**checkpoint, "status": "superseded", "exclusion_reason": reason,
                "remaining": 0, "has_more": False, "ai_calls": 0, "checkpoint": checkpoint}

    through = datetime.fromisoformat(checkpoint["captured_at"])
    statement = select(MonitoringTopic, MonitoringTopicRevision).join(
        MonitoringTopicRevision,
        (MonitoringTopicRevision.topic_id == MonitoringTopic.id)
        & (MonitoringTopicRevision.revision == MonitoringTopic.current_revision),
    ).where(
        MonitoringTopic.organization_id == organization_id,
        MonitoringTopic.status == "active",
        MonitoringTopicRevision.created_at <= through,
    )
    # First worker start is after the admission commit. Topics created/edited
    # later have their own history replay; neither side of that race loses events.
    if "eligible_topics" not in checkpoint:
        checkpoint["eligible_topics"] = session.scalar(select(func.count()).select_from(statement.subquery()))
    if checkpoint["cursor"]:
        statement = statement.where(MonitoringTopic.id > checkpoint["cursor"])
    # Even if every considered topic matches, writes stay within the batch budget.
    size = min(settings.topic_match_topics_per_organization_event, settings.topic_matches_per_organization_event)
    rows = list(session.execute(statement.order_by(MonitoringTopic.id).limit(size)
                                .with_for_update(of=MonitoringTopic)))
    definitions = {item.id: item for item in session.scalars(
        select(SourcePackDefinition).where(SourcePackDefinition.active.is_(True))
    )}
    expression = session.get(RegulatoryExpression, event.expression_id) if event.expression_id else None
    for topic, revision in rows:
        scored = score_event(session, event, work, expression, revision, definitions)
        if scored:
            confidence, signals = scored
            outcome = _persist_evaluation(session, event, work, topic, revision, (confidence, signals), definitions, settings, evidence_fingerprint=evidence_fingerprint)
            checkpoint[outcome] += 1
        else:
            outcome = _persist_evaluation(session, event, work, topic, revision, None, definitions, settings, evidence_fingerprint=evidence_fingerprint)
            if outcome == "invalidated":
                checkpoint["invalidated"] = checkpoint.get("invalidated", 0) + 1
            checkpoint["excluded"] += 1
    checkpoint["processed"] += len(rows)
    checkpoint["batches"] += 1
    if rows:
        checkpoint["cursor"] = rows[-1][0].id
        statement = statement.where(MonitoringTopic.id > checkpoint["cursor"])
    remaining = session.scalar(select(func.count()).select_from(statement.subquery())) if rows else 0
    checkpoint["remaining"] = remaining
    checkpoint["removed_since_capture"] = max(0, checkpoint["eligible_topics"] - checkpoint["processed"] - remaining)
    session.flush()
    return {**checkpoint, "status": "pending" if remaining else "complete", "has_more": bool(remaining),
            "ai_calls": 0, "checkpoint": checkpoint}


def run_backfill(
    session: Session,
    topic_id: str,
    revision: int,
    settings: Settings,
    *,
    checkpoint: dict | None = None,
    captured_at: datetime | None = None,
) -> dict:
    # Keep one immutable plan for this batch even if an administrator edits it.
    topic = session.scalar(select(MonitoringTopic).where(MonitoringTopic.id == topic_id).with_for_update())
    if not topic:
        raise DomainError("The monitoring topic was not found.", 404, "monitoring_topic_not_found")
    checkpoint = dict(checkpoint or {})
    if checkpoint and (
        checkpoint.get("version") != HISTORY_REVISION
        or checkpoint.get("topic_id") != topic.id
        or checkpoint.get("organization_id") != topic.organization_id
        or checkpoint.get("revision") != revision
    ):
        raise DomainError("The saved history checkpoint does not match this topic.", 409, "topic_checkpoint_invalid")
    reason = (
        "revision_changed" if topic.current_revision != revision
        else f"topic_{topic.status}" if topic.status != "active"
        else "matching_rule_changed" if checkpoint and checkpoint.get("rule_revision") != RULE_REVISION
        else None
    )
    if reason:
        return {"processed": 0, "remaining": 0, "matched": 0, "updated": 0, "reused": 0,
                **checkpoint, "status": "superseded", "exclusion_reason": reason,
                "has_more": False, "ai_calls": 0, "checkpoint": checkpoint}

    if not checkpoint:
        checkpoint = {
            "version": HISTORY_REVISION, "rule_revision": RULE_REVISION,
            "topic_id": topic.id, "organization_id": topic.organization_id, "revision": revision,
            "captured_at": _iso(captured_at or utcnow()), "cursor": None,
            "processed": 0, "matched": 0, "updated": 0, "reused": 0,
            "excluded": 0, "batches": 0,
        }
    through = datetime.fromisoformat(checkpoint["captured_at"])
    statement = (
        select(RegulatoryEventState, RegulatoryEvent)
        .join(RegulatoryEvent, RegulatoryEvent.id == RegulatoryEventState.event_id)
        .where(
            RegulatoryEventState.organization_id == topic.organization_id,
            RegulatoryEventState.created_at <= through,
        )
    )
    if "eligible_events" not in checkpoint:
        checkpoint["eligible_events"] = session.scalar(select(func.count()).select_from(statement.subquery()))
    cursor = checkpoint.get("cursor")
    if cursor:
        after = datetime.fromisoformat(cursor["created_at"])
        statement = statement.where(or_(
            RegulatoryEventState.created_at > after,
            (RegulatoryEventState.created_at == after) & (RegulatoryEventState.id > cursor["id"]),
        ))
    rows = list(session.execute(
        statement.order_by(RegulatoryEventState.created_at, RegulatoryEventState.id)
        .limit(settings.topic_match_backfill_limit + 1)
    ))
    selected = rows[:settings.topic_match_backfill_limit]
    result = generate_for_events(session, [event for _state, event in selected], settings, topic_id=topic.id)
    for key in ("matched", "updated", "reused"):
        checkpoint[key] += result[key]
    checkpoint["invalidated"] = checkpoint.get("invalidated", 0) + result["invalidated"]
    checkpoint["processed"] += len(selected)
    checkpoint["excluded"] += len(selected) - result["matched"] - result["updated"] - result["reused"]
    checkpoint["batches"] += 1
    if selected:
        last = selected[-1][0]
        checkpoint["cursor"] = {"created_at": _iso(last.created_at), "id": last.id}
        # Count actual remaining visible scope, not just a limit+1 sentinel.
        after = last.created_at
        remaining_statement = statement.where(or_(
            RegulatoryEventState.created_at > after,
            (RegulatoryEventState.created_at == after) & (RegulatoryEventState.id > last.id),
        ))
        remaining = session.scalar(select(func.count()).select_from(remaining_statement.subquery()))
    else:
        remaining = 0
    checkpoint["remaining"] = remaining
    checkpoint["removed_since_capture"] = max(
        0, checkpoint["eligible_events"] - checkpoint["processed"] - remaining
    )
    return {**checkpoint, "status": "pending" if remaining else "complete", "has_more": bool(remaining),
            "ai_calls": 0, "checkpoint": checkpoint}


def list_matches(session: Session, topic_id: str, *, limit: int = 100) -> list[dict]:
    topic = session.get(MonitoringTopic, topic_id)
    if not topic:
        raise DomainError("The monitoring topic was not found.", 404, "monitoring_topic_not_found")
    # A retained historical match must not restore a revoked event admission.
    records = session.scalars(
        select(TopicEventMatch).join(RegulatoryEventState,
            (RegulatoryEventState.event_id == TopicEventMatch.event_id)
            & (RegulatoryEventState.organization_id == TopicEventMatch.organization_id))
        .where(TopicEventMatch.topic_id == topic.id)
        .order_by(TopicEventMatch.matched_at.desc(), TopicEventMatch.id.desc())
        .limit(max(1, min(limit, 200)))
    ).all()
    definitions = {item.id: item for item in session.scalars(
        select(SourcePackDefinition).where(SourcePackDefinition.active.is_(True))
    )}
    result = []
    fingerprints: dict[str, str] = {}
    for item in records:
        event = session.get(RegulatoryEvent, item.event_id)
        revision = session.get(MonitoringTopicRevision, item.topic_revision_id)
        if not event or not revision or not session.get(RegulatoryWork, event.work_id):
            continue
        if event.id not in fingerprints:
            fingerprints[event.id] = _live_evidence_fingerprint(session, event)
        validity = (
            "plan_changed" if revision.revision != topic.current_revision
            else f"topic_{topic.status}" if topic.status != "active"
            else "unchecked" if not item.evaluation_fingerprint
            else "rule_changed" if item.evaluated_rule_fingerprint != f"{RULE_REVISION}:{revision.revision}"
            else "evidence_changed" if item.evaluation_fingerprint != _evaluation_fingerprint(session, event, revision, definitions, fingerprints[event.id])
            else item.match_status
        )
        # Reading cannot mutate/forge a review. Legacy decisions with no complete
        # fingerprint are retained, but never asserted to confirm current inputs.
        review = item.review_snapshot_json
        if item.decision_status != "pending" and not review:
            review = {"decision": item.decision_status,
                      "evaluation_fingerprint": item.evaluation_fingerprint,
                      "rule_fingerprint": item.rule_fingerprint,
                      "evidence": item.evidence_references_json, "reasons": item.reason_signals_json,
                      "confidence": item.confidence_band, "matched_at": _iso(item.matched_at)}
        decision_current = bool(
            validity == "matching" and review and review.get("evaluation_fingerprint")
            and review["evaluation_fingerprint"] == item.evaluation_fingerprint
            and review["rule_fingerprint"] == item.evaluated_rule_fingerprint
            and review["decision"] == item.decision_status
        )
        result.append({
            "id": item.id, "topic_id": item.topic_id, "topic_revision_id": item.topic_revision_id,
            "event_id": item.event_id, "work_id": item.work_id, "expression_id": item.expression_id,
            "document_version_id": item.document_version_id,
            "reasons": item.reason_signals_json, "evidence": item.evidence_references_json,
            "rule_fingerprint": item.rule_fingerprint,
            "confidence": item.confidence_band if validity == "matching" else None,
            "last_match_confidence": item.confidence_band,
            "decision": item.decision_status, "decision_is_current": decision_current,
            "review_evidence": review,
            "validity": validity, "is_current": validity == "matching",
            "evaluated_at": _iso(item.evaluated_at),
            "matched_at": _iso(item.matched_at), "expires_at": _iso(item.expires_at),
        })
    return result
