"""Shared saved-version access and scalar event links; never fetch document bodies for a list."""
from sqlalchemy import or_, select

from .models import (
    DocumentWatch,
    Law,
    LegacyDocumentMapping,
    OrganizationRelationCandidate,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryExpression,
    RegulatoryWork,
    RelationCandidate,
    Version,
)


def visible(model, organization_id: str):
    return or_(model.owner_organization_id.is_(None), model.owner_organization_id == organization_id)


def accessible_versions(organization_id):
    """Same grants for list links, extracted text and originals, including paused watches."""
    admitted = (select(RegulatoryEventState.id)
        .join(RegulatoryEvent, RegulatoryEvent.id == RegulatoryEventState.event_id)
        .where(RegulatoryEventState.organization_id == organization_id,
               RegulatoryEvent.document_version_id == RegulatoryDocumentVersion.id,
               RegulatoryEvent.work_id == RegulatoryWork.id)
        .correlate(RegulatoryDocumentVersion, RegulatoryWork).exists())
    delivered = (select(OrganizationRelationCandidate.id)
        .join(RelationCandidate, RelationCandidate.id == OrganizationRelationCandidate.candidate_id)
        .join(RegulatoryEvent, RegulatoryEvent.id == RelationCandidate.event_id)
        .where(OrganizationRelationCandidate.organization_id == organization_id,
               RegulatoryEvent.document_version_id == RegulatoryDocumentVersion.id,
               RegulatoryEvent.work_id == RegulatoryWork.id)
        .correlate(RegulatoryDocumentVersion, RegulatoryWork).exists())
    watched = (select(DocumentWatch.id)
        .join(Law, Law.id == DocumentWatch.law_id)
        .join(LegacyDocumentMapping, LegacyDocumentMapping.law_id == Law.id)
        .where(DocumentWatch.organization_id == organization_id,
               LegacyDocumentMapping.work_id == RegulatoryWork.id,
               visible(Law, organization_id), visible(LegacyDocumentMapping, organization_id))
        .correlate(RegulatoryWork).exists())
    linked = (select(Version.id).join(Law, Law.id == Version.law_id)
        .where(Version.id == RegulatoryDocumentVersion.legacy_version_id,
               visible(Version, organization_id), visible(Law, organization_id))
        .correlate(RegulatoryDocumentVersion).exists())
    return (select(RegulatoryDocumentVersion, RegulatoryExpression.language, RegulatoryWork.title)
        .select_from(RegulatoryDocumentVersion)
        .join(RegulatoryExpression, RegulatoryExpression.id == RegulatoryDocumentVersion.expression_id)
        .join(RegulatoryWork, RegulatoryWork.id == RegulatoryExpression.work_id)
        .where(visible(RegulatoryWork, organization_id), or_(admitted, delivered, watched),
               or_(RegulatoryDocumentVersion.legacy_version_id.is_(None), linked)))


def event_evidence_links(session, organization_id, event_ids):
    """Return exact event -> saved viewer URL in one scalar query per bounded page."""
    ids = tuple(set(event_ids))
    if len(ids) > 100:
        raise ValueError("Evidence links require batches of at most 100 events.")
    if not ids:
        return {}
    query = (accessible_versions(organization_id)
        .with_only_columns(RegulatoryEvent.id, RegulatoryDocumentVersion.id,
                           RegulatoryDocumentVersion.legacy_version_id)
        .join(RegulatoryEvent, (RegulatoryEvent.document_version_id == RegulatoryDocumentVersion.id)
              & (RegulatoryEvent.work_id == RegulatoryWork.id))
        .where(RegulatoryEvent.id.in_(ids)))
    return {event_id: f"/evidence/{legacy_id}" if legacy_id else f"/corpus-evidence/{version_id}"
            for event_id, version_id, legacy_id in session.execute(query)}
