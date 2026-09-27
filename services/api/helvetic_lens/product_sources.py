"""Read native page-watch state without treating failed attempts as fresh evidence."""
from datetime import UTC, timedelta

from sqlalchemy import select

from .db import utcnow
from .document_monitoring import has_operator
from .models import DocumentWatch, Law, Scan, ScanItem, Version
from .product_models import DossierEntry


def timestamp(value):
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value) if value else None


def document_statuses(session, parent):
    now = utcnow()
    operator = has_operator(session, parent.organization_id)
    results, seen = [], set()
    rows = session.execute(select(Law, DocumentWatch).join(DocumentWatch, DocumentWatch.law_id == Law.id)
        .join(DossierEntry, DossierEntry.data_json["law_id"].as_string() == Law.id)
        .where(DossierEntry.dossier_id == parent.id, DossierEntry.kind == "monitor")
        .order_by(DossierEntry.created_at, DossierEntry.id))
    for law, watch in rows:
        if law.id in seen:
            continue
        seen.add(law.id)
        version = session.get(Version, law.current_version_id) if law.current_version_id else None
        pending = session.execute(select(Scan, ScanItem).join(ScanItem, ScanItem.scan_id == Scan.id)
            .where(ScanItem.law_id == law.id, Scan.status.in_(("queued", "running")))
            .order_by(Scan.created_at.desc(), Scan.id).limit(1)).first()
        next_check, last_success = timestamp(watch.next_auto_check_at), timestamp(watch.last_success_at)
        schedule = ("paused" if not watch.active else "manual" if not watch.auto_check_enabled else
                    "needs_operator" if not operator else "unscheduled" if next_check is None else
                    "due" if next_check <= now else "scheduled")
        results.append({"id": law.id, "name": watch.display_name, "url": law.url,
            "last_checked": timestamp(watch.last_checked).isoformat() if watch.last_checked else None,
            "last_success_at": last_success.isoformat() if last_success else None,
            "last_result": watch.last_result, "last_error": (watch.last_error or "")[:1200],
            "auto_check_enabled": watch.auto_check_enabled, "active": watch.active,
            "next_check_at": next_check.isoformat() if next_check else None, "schedule": schedule,
            "stale": bool(last_success and last_success < now - timedelta(hours=48)),
            "synthetic": bool(version and version.synthetic),
            "saved_version_at": timestamp(version.created_at).isoformat() if version else None,
            "active_scan": {"id": pending[0].id, "status": pending[0].status, "stage": pending[1].stage} if pending else None,
            "checked_at": now.isoformat()})
    return results
