"""Read-only contextual entry into the existing explicit monitoring-plan workflow."""
from datetime import UTC

from sqlalchemy import func, select

from .config import DomainError
from .corpus_access import event_evidence_links, visible
from .models import (
    AskRecord,
    Comparison,
    DocumentWatch,
    Law,
    LegacyDocumentMapping,
    RegulatoryEvent,
    RegulatoryWork,
    Version,
)


def describe(session, organization_id, kind, entity_id):
    if kind == "answer":
        return _answer_context(session, organization_id, entity_id)
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


def _answer_context(session, organization_id, record_id):
    # Read only the user's question and eligibility metadata, never answer prose,
    # transcripts, full comparison diffs or saved document bodies.
    row = session.execute(select(
        AskRecord.question, AskRecord.created_at,
        AskRecord.result["supported"].label("supported"),
        AskRecord.result["citations"].label("citations"),
        Comparison.id.label("comparison_id"), Comparison.law_id,
        Comparison.old_version_id, Comparison.new_version_id,
    ).join(Comparison, Comparison.id == AskRecord.comparison_id)
      .join(Law, Law.id == Comparison.law_id)
      .where(AskRecord.id == record_id, AskRecord.organization_id == organization_id,
             AskRecord.status == "succeeded", visible(Comparison, organization_id), visible(Law, organization_id))).first()
    # SQLite JSON extraction represents JSON true as integer 1; PostgreSQL
    # returns bool. Do not accept truthy strings or arbitrary objects.
    supported = row is not None and (row.supported is True or type(row.supported) is int and row.supported == 1)
    if not supported or not isinstance(row.citations, list) or not row.citations:
        raise DomainError("The saved cited answer is unavailable.", 404, "not_found")
    version_ids = {row.old_version_id, row.new_version_id}
    visible_ids = set(session.scalars(select(Version.id).where(
        Version.id.in_(version_ids), Version.law_id == row.law_id, visible(Version, organization_id))))
    if visible_ids != version_ids or not all(
        isinstance(item, dict) and isinstance(item.get("version_id"), str) and item["version_id"] in version_ids
        and isinstance(item.get("passage_id"), str) and item["passage_id"].strip()
        for item in row.citations
    ):
        raise DomainError("The saved cited answer is unavailable.", 404, "not_found")
    context = describe(session, organization_id, "comparison", row.comparison_id)
    created_at = row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at
    return {**context, "kind": "answer", "id": record_id,
            "question": row.question[:2000], "answer_created_at": created_at.isoformat(),
            "comparison_id": row.comparison_id,
            "reference_url": f"/compare/{row.comparison_id}?task=ask"}
