"""Bounded, explainable candidate retrieval for new regulatory events."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .config import Settings
from .db import utcnow
from .models import (
    DocumentWatch,
    LegacyDocumentMapping,
    OrganizationRelationCandidate,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryExpression,
    RegulatoryRelation,
    RegulatoryWork,
    RelationCandidate,
)
from .regulatory_corpus import RegulatoryCorpus, RelationInput

RULE_REVISION = "relation-candidate-v1"
_WORD = re.compile(r"[a-z0-9]{3,}")
_NORM = re.compile(r"\b(?:sr|rs)\s*([0-9]+(?:\.[0-9]+){1,4})\b", re.I)
_ARTICLE = re.compile(r"\b(?:art(?:icle|ikel)?\.?)\s*([0-9]+[a-z]?)\b", re.I)
_STOP = {
    "und", "der", "die", "das", "des", "den", "von", "zur", "zum", "fur",
    "les", "des", "une", "sur", "pour", "dans", "loi", "della", "delle", "degli",
    "the", "and", "for", "with", "from", "law", "gesetz", "legge", "lescha",
}


def normalized_title_tokens(value: str) -> set[str]:
    value = unicodedata.normalize("NFKD", value.casefold())
    ascii_value = "".join(character for character in value if not unicodedata.combining(character))
    return {token for token in _WORD.findall(ascii_value) if token not in _STOP}


def _flatten_strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _flatten_strings(child)]
    if isinstance(value, (list, tuple)):
        return [item for child in value for item in _flatten_strings(child)]
    return []


def _references(*values) -> tuple[set[str], set[str]]:
    text_value = " ".join(item for value in values for item in _flatten_strings(value))
    return set(_NORM.findall(text_value)), {item.casefold() for item in _ARTICLE.findall(text_value)}


@dataclass(frozen=True)
class CandidateScore:
    score: float
    components: dict[str, float]
    why: tuple[str, ...]


def score_candidate(
    source_title: str,
    target_title: str,
    *,
    source_authority: str,
    target_authority: str,
    source_kind: str,
    target_kind: str,
    shared_norms: int = 0,
    shared_articles: int = 0,
) -> CandidateScore | None:
    source_tokens = normalized_title_tokens(source_title)
    target_tokens = normalized_title_tokens(target_title)
    overlap = source_tokens & target_tokens
    union = source_tokens | target_tokens
    title_score = len(overlap) / len(union) if union else 0.0
    norm_score = min(1.0, shared_norms / 2) if shared_norms else 0.0
    article_score = min(1.0, shared_articles / 3) if shared_articles else 0.0
    authority_score = 1.0 if source_authority == target_authority else 0.0
    compatible = {
        ("bill", "act"), ("initiative", "act"),
        ("parliamentary_business", "act"), ("court_decision", "act"),
        ("official_notice", "act"), (source_kind, source_kind),
    }
    type_score = 1.0 if (source_kind, target_kind) in compatible else 0.0
    if not overlap and not shared_norms:
        return None
    components = {
        "title_overlap": round(title_score, 6),
        "norm_reference": norm_score,
        "article_reference": article_score,
        "same_authority": authority_score,
        "compatible_type": type_score,
    }
    score = round(
        title_score * 0.55 + norm_score * 0.25 + article_score * 0.05
        + authority_score * 0.05 + type_score * 0.10,
        6,
    )
    if score < 0.16:
        return None
    why = []
    if overlap:
        why.append("Shared normalized title terms: " + ", ".join(sorted(overlap)[:8]))
    if shared_norms:
        why.append(f"Shared exact SR/RS references: {shared_norms}")
    if shared_articles:
        why.append(f"Shared article references: {shared_articles}")
    if type_score:
        why.append(f"Compatible source/target types: {source_kind} → {target_kind}")
    return CandidateScore(score, components, tuple(why))


def _latest_version(session: Session, work_id: str) -> RegulatoryDocumentVersion | None:
    return session.scalar(
        select(RegulatoryDocumentVersion)
        .join(RegulatoryExpression, RegulatoryExpression.id == RegulatoryDocumentVersion.expression_id)
        .where(RegulatoryExpression.work_id == work_id)
        .order_by(RegulatoryDocumentVersion.created_at.desc())
        .limit(1)
    )


def _fts_work_ids(session: Session, work_ids: set[str], tokens: set[str]) -> set[str]:
    if not work_ids or not tokens:
        return set()
    if session.bind and session.bind.dialect.name == "postgresql":
        query = " | ".join(f"{token}:*" for token in sorted(tokens)[:12])
        rows = session.execute(
            select(RegulatoryWork.id).where(
                RegulatoryWork.id.in_(work_ids),
                text(
                    "to_tsvector('simple', coalesce(regulatory_works.title, '')) "
                    "@@ to_tsquery('simple', :candidate_query)"
                ).bindparams(candidate_query=query),
            ).limit(200)
        )
        return {row[0] for row in rows}
    # SQLite is used for deterministic tests; production uses PostgreSQL's indexed retrieval.
    return {
        work.id
        for work in session.scalars(select(RegulatoryWork).where(RegulatoryWork.id.in_(work_ids)))
        if normalized_title_tokens(work.title) & tokens
    }


def generate_for_events(
    session: Session,
    events: list[RegulatoryEvent],
    corpus: RegulatoryCorpus,
    settings: Settings,
) -> dict:
    now = utcnow()
    expired = session.scalars(
        select(RelationCandidate).where(
            RelationCandidate.status == "active", RelationCandidate.expires_at <= now
        )
    ).all()
    for candidate in expired:
        candidate.status = "expired"
    mappings = session.scalars(select(LegacyDocumentMapping)).all()
    work_by_law = {mapping.law_id: mapping.work_id for mapping in mappings if mapping.work_id}
    watches = [
        watch for watch in session.scalars(select(DocumentWatch).where(DocumentWatch.active.is_(True)))
        if work_by_law.get(watch.law_id)
    ]
    watches_by_work: dict[str, list[DocumentWatch]] = {}
    for watch in watches:
        watches_by_work.setdefault(work_by_law[watch.law_id], []).append(watch)
    watched_ids = set(watches_by_work)
    created_candidates = 0
    delivered = 0

    for event in events:
        source = session.get(RegulatoryWork, event.work_id)
        if not source or not watched_ids:
            continue
        exact_by_target: dict[str, RegulatoryRelation] = {}
        for relation in session.scalars(
            select(RegulatoryRelation).where(
                (RegulatoryRelation.subject_work_id == source.id)
                | (RegulatoryRelation.object_work_id == source.id)
            )
        ):
            target_id = (
                relation.object_work_id
                if relation.subject_work_id == source.id
                else relation.subject_work_id
            )
            if target_id in watched_ids and relation.state == "confirmed":
                exact_by_target[target_id] = relation

        source_norms, source_articles = _references(source.title, source.metadata_json, event.evidence_json)
        target_ids = _fts_work_ids(session, watched_ids - {source.id}, normalized_title_tokens(source.title))
        target_ids.update(exact_by_target)
        ranked = []
        source_version = session.get(RegulatoryDocumentVersion, event.document_version_id) if event.document_version_id else _latest_version(session, source.id)
        for target_id in target_ids:
            target = session.get(RegulatoryWork, target_id)
            if not target:
                continue
            relation = exact_by_target.get(target_id)
            target_norms, target_articles = _references(target.title, target.metadata_json)
            if relation:
                scored = CandidateScore(
                    1.0,
                    {"confirmed_relation": 1.0},
                    (f"Confirmed {relation.relation_type} relation from {relation.provenance_method}.",),
                )
            else:
                scored = score_candidate(
                    source.title,
                    target.title,
                    source_authority=source.authority,
                    target_authority=target.authority,
                    source_kind=source.kind,
                    target_kind=target.kind,
                    shared_norms=len(source_norms & target_norms),
                    shared_articles=len(source_articles & target_articles),
                )
            if scored:
                ranked.append((scored.score, target, relation, scored))
        ranked.sort(key=lambda item: (-item[0], item[1].id))
        ranked = ranked[: settings.relation_candidates_per_event]

        candidate_delivery: dict[str, list[tuple[RelationCandidate, DocumentWatch]]] = {}
        for _, target, relation, scored in ranked:
            target_version = _latest_version(session, target.id)
            if relation is None:
                relation = corpus.record_relation(
                    session,
                    RelationInput(
                        subject_work_id=source.id,
                        object_work_id=target.id,
                        source_version_id=source_version.id if source_version else None,
                        authority=source.authority,
                        relation_type="potentially_impacts",
                        state="proposed",
                        provenance_method="text_rule",
                        evidence={
                            "candidate_only": True,
                            "event_id": event.id,
                            "why": list(scored.why),
                            "score_components": scored.components,
                        },
                        confidence=scored.score,
                        rule_or_model_revision=RULE_REVISION,
                    ),
                )
            candidate = session.scalar(
                select(RelationCandidate).where(
                    RelationCandidate.event_id == event.id,
                    RelationCandidate.target_work_id == target.id,
                )
            )
            if not candidate:
                candidate = RelationCandidate(
                    event_id=event.id,
                    source_work_id=source.id,
                    target_work_id=target.id,
                    created_at=now,
                )
                session.add(candidate)
                created_candidates += 1
            candidate.relation_id = relation.id
            candidate.source_version_id = source_version.id if source_version else None
            candidate.target_version_id = target_version.id if target_version else None
            candidate.status = "active"
            candidate.score = scored.score
            candidate.score_components_json = scored.components
            candidate.why_json = list(scored.why)
            candidate.evidence_json = {
                "event_id": event.id,
                "event_source_url": event.source_url,
                "source_work": source.id,
                "target_work": target.id,
                "relation_state": relation.state,
                "similarity_is_not_evidence": relation.state != "confirmed",
            }
            candidate.rule_revision = RULE_REVISION
            candidate.expires_at = now + timedelta(days=settings.relation_candidate_ttl_days)
            candidate.updated_at = now
            session.flush()
            for watch in watches_by_work[target.id]:
                candidate_delivery.setdefault(watch.organization_id, []).append((candidate, watch))

        for organization_id, items in candidate_delivery.items():
            items.sort(key=lambda item: (-item[0].score, item[0].id))
            for candidate, watch in items[: settings.relation_candidates_per_organization]:
                existing = session.scalar(
                    select(OrganizationRelationCandidate).where(
                        OrganizationRelationCandidate.organization_id == organization_id,
                        OrganizationRelationCandidate.candidate_id == candidate.id,
                    )
                )
                if existing:
                    continue
                session.add(
                    OrganizationRelationCandidate(
                        organization_id=organization_id,
                        candidate_id=candidate.id,
                        watch_id=watch.id,
                        status="pending",
                        created_at=now,
                        updated_at=now,
                    )
                )
                delivered += 1
    session.flush()
    return {"candidates": created_candidates, "deliveries": delivered, "expired": len(expired)}
