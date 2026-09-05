"""Bounded related-entity lookups for a saved inbox candidate batch."""

from dataclasses import dataclass

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, load_only

from .config import DomainError
from .models import (
    Comparison,
    DocumentWatch,
    Law,
    LegacyDocumentMapping,
    OrganizationRelationCandidate,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryRelation,
    RegulatoryWork,
    RelationCandidate,
    Version,
)


@dataclass
class InboxContext:
    candidates: dict[str, RelationCandidate]
    events: dict[str, RegulatoryEvent]
    works: dict[str, RegulatoryWork]
    watches: dict[str, DocumentWatch]
    law_ids: set[str]
    relations: dict[str, RegulatoryRelation]
    comparisons: dict[str, str]
    artifacts: dict[str, str]
    successors: dict[str, tuple[str, bool]]


def visible(model, organization_id: str):
    return or_(model.owner_organization_id.is_(None), model.owner_organization_id == organization_id)


def load_context(
    session: Session, organization_id: str, deliveries: list[OrganizationRelationCandidate]
) -> InboxContext:
    if len(deliveries) > 100:
        raise ValueError("Inbox context requires batches of at most 100 candidates.")
    if any(delivery.organization_id != organization_id for delivery in deliveries):
        raise DomainError("The saved impact candidate is unavailable.", 404, "not_found")

    def records(model, ids, attributes, *conditions):
        if not ids:
            return {}
        rows = session.scalars(
            select(model)
            .where(model.id.in_(ids), *conditions)
            .options(load_only(*attributes, raiseload=True))
        )
        return {row.id: row for row in rows}

    candidates = records(
        RelationCandidate,
        {delivery.candidate_id for delivery in deliveries},
        (
            RelationCandidate.id,
            RelationCandidate.event_id,
            RelationCandidate.source_work_id,
            RelationCandidate.target_work_id,
            RelationCandidate.relation_id,
            RelationCandidate.why_json,
        ),
    )
    events = records(
        RegulatoryEvent,
        {candidate.event_id for candidate in candidates.values()},
        (
            RegulatoryEvent.id,
            RegulatoryEvent.impact,
            RegulatoryEvent.event_type,
            RegulatoryEvent.connector,
            RegulatoryEvent.authority,
            RegulatoryEvent.detected_at,
            RegulatoryEvent.source_url,
            RegulatoryEvent.document_version_id,
        ),
    )
    works = records(
        RegulatoryWork,
        {
            id_
            for candidate in candidates.values()
            for id_ in (candidate.source_work_id, candidate.target_work_id)
        },
        (RegulatoryWork.id, RegulatoryWork.title, RegulatoryWork.kind, RegulatoryWork.stable_official_url),
        visible(RegulatoryWork, organization_id),
    )
    watches = records(
        DocumentWatch,
        {delivery.watch_id for delivery in deliveries},
        (DocumentWatch.id, DocumentWatch.law_id, DocumentWatch.display_name, DocumentWatch.active),
        DocumentWatch.organization_id == organization_id,
    )
    law_ids = (
        set(
            session.scalars(
                select(Law.id).where(
                    Law.id.in_({watch.law_id for watch in watches.values()}), visible(Law, organization_id)
                )
            )
        )
        if watches
        else set()
    )
    relations = records(
        RegulatoryRelation,
        {candidate.relation_id for candidate in candidates.values() if candidate.relation_id},
        (
            RegulatoryRelation.id,
            RegulatoryRelation.state,
            RegulatoryRelation.relation_type,
            RegulatoryRelation.provenance_method,
        ),
    )
    comparisons = {}
    if law_ids:
        ranked = (
            select(
                Comparison.id,
                Comparison.law_id,
                func.row_number()
                .over(
                    partition_by=Comparison.law_id,
                    order_by=(Comparison.created_at.desc(), Comparison.id.desc()),
                )
                .label("position"),
            )
            .where(Comparison.law_id.in_(law_ids), visible(Comparison, organization_id))
            .subquery()
        )
        comparisons = {
            row.law_id: row.id
            for row in session.execute(select(ranked.c.law_id, ranked.c.id).where(ranked.c.position == 1))
        }
    version_ids = {event.document_version_id for event in events.values() if event.document_version_id}
    artifacts = (
        dict(
            session.execute(
                select(RegulatoryDocumentVersion.id, Version.id)
                .join(
                    Version,
                    Version.id == RegulatoryDocumentVersion.legacy_version_id,
                )
                .where(RegulatoryDocumentVersion.id.in_(version_ids), visible(Version, organization_id))
            ).all()
        )
        if version_ids
        else {}
    )
    replacement_sources = {
        candidate.source_work_id
        for candidate in candidates.values()
        if candidate.source_work_id in works
        and candidate.relation_id in relations
        and relations[candidate.relation_id].state == "confirmed"
        and relations[candidate.relation_id].relation_type == "replaces"
    }
    successors = {}
    if replacement_sources:
        # Multiple legacy URLs may map to the same work. Prefer this organization's
        # active watch, then a paused watch, then the oldest accessible mapping.
        ranked = select(
            LegacyDocumentMapping.work_id,
            Law.id.label("law_id"),
            DocumentWatch.active,
            func.row_number()
            .over(
                partition_by=LegacyDocumentMapping.work_id,
                order_by=(
                    case((DocumentWatch.active.is_(True), 0), (DocumentWatch.id.is_not(None), 1), else_=2),
                    LegacyDocumentMapping.created_at,
                    LegacyDocumentMapping.id,
                ),
            )
            .label("position"),
        )
        ranked = ranked.join(Law, Law.id == LegacyDocumentMapping.law_id).outerjoin(
            DocumentWatch,
            (DocumentWatch.law_id == Law.id) & (DocumentWatch.organization_id == organization_id),
        )
        ranked = ranked.where(
            LegacyDocumentMapping.work_id.in_(replacement_sources),
            visible(LegacyDocumentMapping, organization_id),
            visible(Law, organization_id),
        ).subquery()
        successors = {
            row.work_id: (row.law_id, bool(row.active))
            for row in session.execute(
                select(ranked.c.work_id, ranked.c.law_id, ranked.c.active).where(ranked.c.position == 1)
            )
        }
    return InboxContext(
        candidates, events, works, watches, law_ids, relations, comparisons, artifacts, successors
    )
