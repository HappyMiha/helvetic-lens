"""Private retained-change reader. No collection, delivery or implicit review."""
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import aliased

from .config import DomainError
from .monitoring_subjects import _actor
from .river_contracts import utc
from .river_models import RiverChange, RiverMonitor
from .river_runtime import change_view, fresh


def today(session, user_id, *, before=None, before_id=None, unreviewed=False, limit=30, now=None):
    organization = _actor(session, user_id)
    now = now or datetime.now(UTC)
    if not 1 <= limit <= 50 or bool(before) != bool(before_id):
        raise DomainError("Invalid River page.", 422, "river_cursor_invalid")
    if before is not None and (before.tzinfo is None or before.utcoffset() is None):
        raise DomainError("Use an explicit timezone for the page cursor.", 422, "river_cursor_invalid")
    newer = aliased(RiverChange)
    scope = (
        RiverMonitor.owner_user_id == user_id, RiverMonitor.organization_id == organization,
        RiverChange.organization_id == organization, RiverMonitor.status != "archived",
        ~exists(select(newer.id).where(newer.monitor_id == RiverChange.monitor_id,
            newer.organization_id == organization, newer.development_id == RiverChange.development_id,
            newer.sequence > RiverChange.sequence)),
    )
    query = select(RiverChange, RiverMonitor).join(RiverMonitor, RiverMonitor.id == RiverChange.monitor_id).where(*scope)
    count = session.scalar(select(func.count()).select_from(RiverChange)
        .join(RiverMonitor, RiverMonitor.id == RiverChange.monitor_id).where(*scope, RiverChange.decision.is_(None)))
    if unreviewed:
        query = query.where(RiverChange.decision.is_(None))
    if before is not None:
        # Validate ownership and immutable timestamp even if the anchor has since
        # been reviewed/replaced. Do not let a foreign id reveal private evidence.
        identifier = str(UUID(str(before_id)))
        anchor = session.scalar(select(RiverChange).join(RiverMonitor, RiverMonitor.id == RiverChange.monitor_id).where(
            RiverMonitor.owner_user_id == user_id, RiverMonitor.organization_id == organization,
            RiverChange.organization_id == organization, RiverChange.id == identifier))
        if anchor is None or utc(anchor.created_at) != utc(before):
            raise DomainError("Refresh the River page.", 422, "river_cursor_invalid")
        query = query.where(or_(RiverChange.created_at < utc(before),
            and_(RiverChange.created_at == utc(before), RiverChange.id < identifier)))
    rows = list(session.execute(query.order_by(RiverChange.created_at.desc(), RiverChange.id.desc()).limit(limit + 1)))
    items = []
    for change, monitor in rows[:limit]:
        sample = change.evidence.get("sample")
        # This describes retained evidence only, not the latest source or safety.
        sample_state = "unknown" if not sample else "future" if utc(sample["timestamp"]) > now else "recent" if fresh(sample, now) else "stale"
        items.append({**change_view(change), "monitor_id": monitor.id,
            "monitor_name": monitor.configuration["name"], "monitor_status": monitor.status,
            "current_configuration": change.revision == monitor.revision,
            "sample_state": sample_state,
            "href": f"/river-watch?monitor={monitor.id}&change={change.id}"})
    return {"items": items, "unreviewed_count": count,
        "next": {"before": utc(rows[limit - 1][0].created_at).isoformat(), "before_id": rows[limit - 1][0].id}
        if len(rows) > limit else None}
