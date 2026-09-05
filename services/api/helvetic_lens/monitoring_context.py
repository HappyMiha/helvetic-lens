"""Read-only contextual entry into the existing explicit monitoring-plan workflow."""
from sqlalchemy import func, select

from .config import DomainError
from .corpus_access import event_evidence_links, visible
from .models import Comparison, DocumentWatch, Law, LegacyDocumentMapping, RegulatoryEvent, RegulatoryWork


def describe(session, organization_id, kind, entity_id):
    if kind == "event":
        row = session.execute(select(RegulatoryEvent.id, RegulatoryWork.id.label("work_id"),
            RegulatoryWork.title, func.coalesce(RegulatoryEvent.source_url, RegulatoryWork.stable_official_url).label("source_url"))
            .join(RegulatoryWork, RegulatoryWork.id == RegulatoryEvent.work_id)
            .where(RegulatoryEvent.id == entity_id, visible(RegulatoryWork, organization_id))).first()
        if row is None:
            raise DomainError("The monitoring context is unavailable.", 404, "not_found")
        title, source_url, work_id, law_id = row.title, row.source_url, row.work_id, None
        reference_url = None
        # Registry discovery may expose public metadata without granting saved-body access.
        evidence_url = event_evidence_links(session, organization_id, [entity_id]).get(entity_id)
    else:
        query = select(Law.id, Law.name, Law.url).where(visible(Law, organization_id))
        if kind == "comparison":
            query = query.join(Comparison, Comparison.law_id == Law.id).where(
                Comparison.id == entity_id, visible(Comparison, organization_id))
        elif kind == "law":
            query = query.where(Law.id == entity_id)
        else:
            raise DomainError("Choose a supported monitoring context.", 422, "invalid_request")
        row = session.execute(query).first()
        if row is None:
            raise DomainError("The monitoring context is unavailable.", 404, "not_found")
        title, source_url, law_id = row.name, row.url, row.id
        work_id = session.scalar(select(LegacyDocumentMapping.work_id)
            .join(RegulatoryWork, RegulatoryWork.id == LegacyDocumentMapping.work_id)
            .where(LegacyDocumentMapping.law_id == law_id, visible(LegacyDocumentMapping, organization_id),
                   visible(RegulatoryWork, organization_id)))
        reference_url = f"/compare/{entity_id}" if kind == "comparison" else f"/laws/{entity_id}"
        evidence_url = None
    watches = (select(DocumentWatch.law_id, DocumentWatch.display_name, DocumentWatch.active)
        .join(Law, Law.id == DocumentWatch.law_id)
        .where(DocumentWatch.organization_id == organization_id, visible(Law, organization_id)))
    if work_id:
        watches = watches.join(LegacyDocumentMapping, LegacyDocumentMapping.law_id == Law.id).where(
            LegacyDocumentMapping.work_id == work_id, visible(LegacyDocumentMapping, organization_id))
    else:
        watches = watches.where(Law.id == law_id)
    rows = list(session.execute(watches.order_by(DocumentWatch.display_name, DocumentWatch.id).limit(21)))
    return {"kind": kind, "id": entity_id, "title": title or "", "source_url": source_url,
            "reference_url": reference_url if kind != "event" else None,
            "evidence_url": evidence_url, "requires_confirmation": True, "ai_calls": 0,
            "watch_limit": 20, "more_watches": len(rows) > 20,
            "watches": [{"law_id": item.law_id, "name": item.display_name, "active": item.active,
                         "url": f"/laws/{item.law_id}"} for item in rows[:20]]}
