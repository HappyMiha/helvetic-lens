"""Read-only private Today projection over existing transport review signals."""

from datetime import timedelta

from sqlalchemy import and_, func, or_, select

from .commute_contracts import digest
from .commute_events import event_view, owned_development
from .commute_models import CommuteDevelopment, CommuteEventVersion, CommuteMonitor, CommuteSignal
from .commute_sources import require_permission, utc
from .config import DomainError
from .monitoring_subjects import _actor
from .transport_reference import ZURICH

SCAN_LIMIT = 100
LOOKBACK = timedelta(days=2)


def evidence(session, row, sequence):
    version = session.scalar(select(CommuteEventVersion).where(
        CommuteEventVersion.development_id == row.id,
        CommuteEventVersion.organization_id == row.organization_id,
        CommuteEventVersion.sequence == sequence))
    if version is None:
        raise DomainError("Saved transport update is unavailable.", 404, "commute_version_unavailable")
    value = version.evidence
    if (not isinstance(value, dict) or digest(value) != version.evidence_hash or value.get("source") != row.source
            or value.get("static_version") != row.static_version
            or value.get("service_day") != row.service_day.isoformat()
            or value.get("configuration_revision") != row.configuration_revision):
        raise DomainError("Transport evidence is inconsistent.", 503, "commute_event_invalid")
    return {"id": version.id, "sequence": version.sequence, "evidence": value,
            "evidence_hash": version.evidence_hash, "created_at": utc(version.created_at).isoformat()}


def labels(snapshot):
    return [{"id": identifier, "label": f"{leg['route_name']}: {leg['boarding_name']} → {leg['alighting_name']}"}
            for identifier, leg in snapshot["evidence"]["legs"].items()]


def detail(session, user_id, development_id, *, now, sequence=None, monitor_id=None):
    monitor, row = owned_development(session, user_id, development_id, now=now)
    if monitor_id is not None and monitor.id != monitor_id:
        raise DomainError("The update belongs to another journey.", 404, "commute_event_unavailable")
    permission = require_permission(session, row.permission_id, row.source, now=now)
    snapshot = evidence(session, row, sequence or row.sequence)
    latest = snapshot if snapshot["sequence"] == row.sequence else evidence(session, row, row.sequence)
    return {"event": {**event_view(row, now=now, max_age_seconds=permission.max_age_seconds),
                       "available": True, "reference_labels": labels(latest)},
            "snapshot": snapshot, "newer_available": snapshot["sequence"] < row.sequence,
            "current_configuration": row.configuration_revision == monitor.revision}


def today(session, settings, user_id, *, now, before_id=None, limit=20):
    organization = _actor(session, user_id)
    if not settings.commute_watch_enabled:
        return {"items": [], "next_cursor": None}
    if type(limit) is not int or not 1 <= limit <= 50:
        raise DomainError("Choose a bounded Today page.", 422, "commute_limit_invalid")
    # Use the newest signal even when it is already handled: do not resurrect an
    # older pending signal after a newer one has been reviewed/cancelled.
    latest = select(CommuteSignal.development_id, func.max(CommuteSignal.sequence).label("sequence")).where(
        CommuteSignal.organization_id == organization).group_by(CommuteSignal.development_id).subquery()
    query = select(CommuteSignal, CommuteDevelopment, CommuteMonitor).join(latest,
        and_(latest.c.development_id == CommuteSignal.development_id, latest.c.sequence == CommuteSignal.sequence))
    query = query.join(CommuteDevelopment, and_(CommuteDevelopment.id == CommuteSignal.development_id,
        CommuteDevelopment.organization_id == CommuteSignal.organization_id)).join(CommuteMonitor,
        and_(CommuteMonitor.id == CommuteDevelopment.monitor_id,
             CommuteMonitor.organization_id == CommuteDevelopment.organization_id)).where(
        CommuteSignal.organization_id == organization, CommuteMonitor.organization_id == organization,
        CommuteMonitor.owner_user_id == user_id, CommuteMonitor.status == "active",
        or_(CommuteMonitor.paused_on.is_(None), CommuteMonitor.paused_on != now.astimezone(ZURICH).date()),
        CommuteDevelopment.configuration_revision == CommuteMonitor.revision,
        CommuteDevelopment.muted.is_(False), CommuteSignal.state == "pending",
        CommuteSignal.sequence > CommuteDevelopment.reviewed_sequence,
        CommuteSignal.sequence <= CommuteDevelopment.sequence,
        CommuteSignal.created_at >= now - LOOKBACK, CommuteSignal.created_at <= now)
    if before_id:
        anchor = session.execute(query.where(CommuteSignal.id == before_id)).first()
        if anchor is None:
            raise DomainError("The Today list changed. Refresh it.", 409, "commute_today_changed")
        signal = anchor[0]
        query = query.where(or_(CommuteSignal.created_at < signal.created_at,
            and_(CommuteSignal.created_at == signal.created_at, CommuteSignal.id < signal.id)))
    rows = list(session.execute(query.order_by(CommuteSignal.created_at.desc(), CommuteSignal.id.desc()).limit(SCAN_LIMIT + 1)))
    items = []
    for index, (signal, row, monitor) in enumerate(rows[:SCAN_LIMIT]):
        try:
            permission = require_permission(session, row.permission_id, row.source, now=now)
            snapshot = evidence(session, row, row.sequence)
            current = event_view(row, now=now, max_age_seconds=permission.max_age_seconds)
            states = current["current"]["states"]
            # A silent stale/missing update can follow a material signal. Show
            # its current availability; the old cancellation is not a live alarm.
            urgent = any(value["condition"] == "cancelled" and value["availability"] == "present" for value in states.values())
            items.append({"id": signal.id, "monitor_id": monitor.id, "name": monitor.configuration["name"],
                "event_id": row.id, "sequence": row.sequence, "event_version": row.version,
                "signal_sequence": signal.sequence, "configuration_revision": row.configuration_revision,
                "service_day": row.service_day.isoformat(), "source": row.source,
                "detected_at": utc(signal.created_at).isoformat(), "states": states,
                "reference_labels": labels(snapshot), "priority": "urgent" if urgent else "normal",
                "reasons": ["unread_journey_change", "outside_window_saved"] if signal.delivery_kind == "digest_candidate" else ["unread_journey_change"],
                "href": f"/commute-watch?monitor={monitor.id}&event={row.id}&sequence={row.sequence}"})
        except (DomainError, ValueError, KeyError, TypeError):
            # A sparse page is intentional. Continue using the scanned cursor,
            # without returning unavailable source titles or private evidence.
            continue
        if len(items) == limit:
            return {"items": items, "next_cursor": signal.id if index + 1 < len(rows) else None}
    return {"items": items, "next_cursor": rows[SCAN_LIMIT - 1][0].id if len(rows) > SCAN_LIMIT else None}
