"""Organization-authorized baseline editor and paged complete saved comparisons."""

from pydantic import ValidationError
from sqlalchemy import select

from .config import DomainError
from .corpus_access import accessible_versions
from .interest_assessment import fingerprint
from .interest_material import audit
from .models import NativeDocumentComparison, RegulatoryDocumentVersion, RegulatoryExpression, RegulatoryWork
from .native_comparisons import _event, _pair, selection, unavailable
from .topic_matching import _iso


def _version(row):
    return {"id": row.id, "version_key": row.version_key, "saved_at": _iso(row.created_at),
            "evidence_url": f"/corpus-evidence/{row.id}"}


def _current(session, organization_id, event_id):
    from .interest_admission import _saved_document
    event = _event(session, organization_id, event_id)
    native, _, _ = _saved_document(session, organization_id, event.document_version_id,
        event.work_id, "event", event.expression_id)
    if native.legacy_version_id:
        unavailable()
    return event, native


def candidates(session, organization_id, event_id, *, after="", limit=30):
    event, current = _current(session, organization_id, event_id)
    query = accessible_versions(organization_id).with_only_columns(
        RegulatoryDocumentVersion.id, RegulatoryDocumentVersion.version_key,
        RegulatoryDocumentVersion.created_at).where(
        RegulatoryDocumentVersion.expression_id == current.expression_id,
        RegulatoryDocumentVersion.id != current.id, RegulatoryDocumentVersion.id > after,
        RegulatoryDocumentVersion.legacy_version_id.is_(None),
        RegulatoryDocumentVersion.artifact_key.is_not(None), RegulatoryDocumentVersion.source_url.is_not(None),
        RegulatoryDocumentVersion.text.is_not(None), RegulatoryDocumentVersion.text != ""
    ).order_by(RegulatoryDocumentVersion.id).limit(limit + 1)
    rows = session.execute(query).all()
    return {"items": [_version(row) for row in rows[:limit]],
            "next_after": rows[limit - 1].id if len(rows) > limit else None,
            "after_version_id": event.document_version_id}


def page(session, organization_id, event_id, *, offset=0, limit=20, material_only=True, comparison_id=""):
    event, current = _current(session, organization_id, event_id)
    chosen = selection(session, organization_id, event_id)
    title = session.scalar(select(RegulatoryWork.title).where(RegulatoryWork.id == event.work_id))
    result = {"event_id": event.id, "title": title, "after": _version(current), "before": None,
              "language": session.scalar(select(RegulatoryExpression.language).where(RegulatoryExpression.id == current.expression_id)),
              "revision": chosen.revision if chosen else 0, "status": "unselected", "comparison_id": None,
              "counts": None, "material_count": None, "items": [], "pagination": None}
    if chosen is None or chosen.comparison_id is None:
        if comparison_id:
            raise DomainError("The comparison selection changed. Reload the comparison.", 409, "native_selection_conflict")
        return result
    comparison = session.scalar(select(NativeDocumentComparison).where(
        NativeDocumentComparison.id == chosen.comparison_id,
        NativeDocumentComparison.organization_id == organization_id))
    if comparison_id and comparison_id != chosen.comparison_id:
        raise DomainError("The comparison selection changed. Reload the comparison.", 409, "native_selection_conflict")
    try:
        if comparison is None:
            unavailable()
        before, current, binding = _pair(session, organization_id, event,
            comparison.old_version_id, comparison.new_version_id)
        if comparison.input_fingerprint != fingerprint(binding):
            unavailable()
        audit(comparison, before, current)
    except (DomainError, ValidationError):
        # No old excerpts/source labels are exposed after access is revoked.
        result["status"] = "stale"
        return result
    items = [item for item in comparison.diff["items"] if not material_only or item.get("material") is True]
    result.update(status="ready", before=_version(before), comparison_id=comparison.id,
                  counts=comparison.diff["counts"], material_count=comparison.diff["material_count"],
                  items=[{key: item.get(key) for key in ("id", "kind", "classification", "old", "new")}
                         for item in items[offset:offset + limit]],
                  pagination={"offset": offset, "total": len(items),
                    "next_offset": offset + limit if offset + limit < len(items) else None,
                    "previous_offset": max(0, offset - limit) if offset else None})
    return result
