"""Owner-private Today and exact material comparisons; reads never collect or review."""

from datetime import datetime, timedelta

from sqlalchemy import and_, or_, select

from .config import DomainError
from .monitoring_subjects import _actor
from .road_catalog import CatalogReadBudget
from .road_events import FIELDS, event_view, owned_event, version_view
from .road_models import RoadDevelopment, RoadEventVersion, RoadMonitor
from .road_repository import describe_current_reference
from .road_sources import _clock, _head, _utc, require_permission

LOOKBACK = timedelta(days=2)
SCAN_LIMIT = 100


def labels(session, payload, *, now, budget):
    result = []
    for identifier in (payload or {}).get("corridors", {}):
        try:
            result.append(describe_current_reference(session, identifier, now=now, budget=budget))
        except DomainError:
            result.append({"id": identifier, "state": "unavailable"})
    return result


def detail(session, user_id, event_id, *, now, sequence=None, monitor_id=None):
    now = _clock(now)
    row, monitor = owned_event(session, user_id, event_id)
    if monitor_id is not None and monitor_id != monitor.id:
        raise DomainError("Road update not found.", 404, "road_event_not_found")
    sequence = row.sequence if sequence is None else sequence
    if type(sequence) is not int or not 1 <= sequence <= 10000:
        raise DomainError("Invalid road update sequence.", 422, "road_event_sequence_invalid")
    statement = select(RoadEventVersion).where(RoadEventVersion.development_id == row.id,
        RoadEventVersion.organization_id == monitor.organization_id)
    selected = session.scalar(statement.where(RoadEventVersion.sequence == sequence))
    if selected is None:
        raise DomainError("Saved road update not found.", 404, "road_event_version_not_found")
    previous = session.scalar(statement.where(RoadEventVersion.sequence == sequence - 1))
    current = event_view(session, row, now=now)
    snapshot = version_view(session, row, selected, now=now)
    before = version_view(session, row, previous, now=now) if previous else None
    label_payload = {"corridors": {key: {} for value in (current, snapshot, before or {})
                                  for key in (value.get("payload") or {}).get("corridors", {})}}
    return {"event": current, "snapshot": snapshot, "previous": before,
            "corridors": labels(session, label_payload, now=now, budget=CatalogReadBudget()),
            "current_configuration": row.configuration_revision == monitor.revision,
            "newer_available": sequence < row.sequence}


def urgent(current, *, now):
    if current["availability"] != "available" or current["payload"] is None:
        return False
    for corridor in current["payload"]["corridors"].values():
        if corridor["state"] != "active" or corridor["coverage"] != "verified":
            continue
        for fact in corridor["facts"]:
            if (fact["kind"] not in {"road_closure", "carriageway_closure"}
                    or fact["phase"] != "active" or fact["probability"] != "certain"):
                continue
            start, end = fact.get("valid_from"), fact.get("valid_until")
            if (start is None or _utc(datetime.fromisoformat(start)) <= now) and (
                    end is None or _utc(datetime.fromisoformat(end)) > now):
                return True
    return False


def today(session, settings, user_id, *, now, cursor=None, limit=20):
    return _page(session, settings, user_id, now=now, cursor=cursor, limit=limit, closures_only=False)


def inbox(session, settings, user_id, *, now, cursor=None, limit=20):
    now = _clock(now)
    organization = _actor(session, user_id)
    monitors = select(RoadMonitor.id).where(RoadMonitor.organization_id == organization,
        RoadMonitor.owner_user_id == user_id, RoadMonitor.status == "active")
    has_routes = session.scalar(monitors.limit(1)) is not None
    available, unsettled = False, has_routes
    if settings.road_watch_enabled and settings.road_source_enabled:
        try:
            _, policy = require_permission(session, settings.road_source_permission_id, now=now, fields=FIELDS)
            head = _head(session)
            available = bool(head and head.permission_id == settings.road_source_permission_id
                and head.published_at and head.received_at and _utc(head.received_at) <= now
                and timedelta(0) <= now - _utc(head.published_at) <= timedelta(seconds=policy.max_age_seconds))
            unsettled = session.scalar(monitors.where(or_(RoadMonitor.health != "ready",
                RoadMonitor.last_poll_at.is_(None), RoadMonitor.last_poll_at < now - timedelta(seconds=policy.max_age_seconds)))
                .limit(1)) is not None
        except DomainError:
            pass
    result = _page(session, settings, user_id, now=now, cursor=cursor, limit=limit, closures_only=True)
    return {**result, "has_active_routes": has_routes, "source_available": available,
            "unverified_routes": unsettled}


def _page(session, settings, user_id, *, now, cursor, limit, closures_only):
    organization = _actor(session, user_id)
    now = _clock(now)
    if type(limit) is not int or not 1 <= limit <= 50:
        raise DomainError("Choose a bounded Today page.", 422, "road_event_limit_invalid")
    if not settings.road_watch_enabled or not settings.road_source_enabled:
        return {"items": [], "next_cursor": None, **({"unverified_count": 0} if closures_only else {})}
    # One latest material version per event. A cursor binds an immutable version,
    # so review, revision, or a newer material update invalidates it explicitly.
    query = select(RoadDevelopment, RoadMonitor, RoadEventVersion).join(RoadMonitor,
        and_(RoadMonitor.id == RoadDevelopment.monitor_id,
             RoadMonitor.organization_id == RoadDevelopment.organization_id)).join(RoadEventVersion,
        and_(RoadEventVersion.development_id == RoadDevelopment.id,
             RoadEventVersion.organization_id == RoadDevelopment.organization_id,
             RoadEventVersion.sequence == RoadDevelopment.sequence)).where(
        RoadMonitor.organization_id == organization, RoadMonitor.owner_user_id == user_id,
        RoadMonitor.status == "active", RoadDevelopment.configuration_revision == RoadMonitor.revision,
        RoadDevelopment.permission_id == settings.road_source_permission_id,
        RoadDevelopment.muted.is_(False), RoadDevelopment.sequence > RoadDevelopment.reviewed_sequence,
        RoadEventVersion.created_at <= now)
    if not closures_only:
        query = query.where(RoadEventVersion.created_at >= now - LOOKBACK)
    if cursor is not None:
        anchor = session.execute(query.where(RoadEventVersion.id == cursor)).first()
        if anchor is None:
            raise DomainError("The Today list changed. Refresh it.", 409, "road_today_changed")
        version = anchor[2]
        query = query.where(or_(RoadEventVersion.created_at < version.created_at,
            and_(RoadEventVersion.created_at == version.created_at, RoadEventVersion.id < version.id)))
    rows = list(session.execute(query.order_by(RoadEventVersion.created_at.desc(), RoadEventVersion.id.desc()).limit(SCAN_LIMIT + 1)))
    items, budget, unverified = [], CatalogReadBudget(), 0
    for index, (row, monitor, version) in enumerate(rows[:SCAN_LIMIT]):
        current = event_view(session, row, now=now)
        snapshot = version_view(session, row, version, now=now)
        is_urgent = urgent(current, now=now)
        if current["availability"] != "available":
            unverified += 1
        if current["payload"] is None or (not closures_only and snapshot["payload"] is None):
            continue
        if closures_only and not is_urgent:
            continue
        items.append({"id": version.id, "monitor_id": monitor.id, "name": monitor.configuration["name"],
            "event_id": row.id, "sequence": row.sequence, "detected_at": _utc(version.created_at).isoformat(),
            "event": current, "corridors": labels(session, current["payload"], now=now, budget=budget),
            "priority": "urgent" if is_urgent else "normal", "reason": "unread_road_change",
            "href": f"/road-watch?monitor={monitor.id}&event={row.id}&sequence={row.sequence}"})
        if len(items) == limit:
            return {"items": items, "next_cursor": version.id if index + 1 < len(rows) else None,
                    **({"unverified_count": unverified} if closures_only else {})}
    return {"items": items, "next_cursor": rows[SCAN_LIMIT - 1][2].id if len(rows) > SCAN_LIMIT else None,
            **({"unverified_count": unverified} if closures_only else {})}
