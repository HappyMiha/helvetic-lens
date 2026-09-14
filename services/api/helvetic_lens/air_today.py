"""Shared owner-private Today projection for cards and review counts."""

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import aliased

from .air_contracts import utc
from .air_models import AirChange, AirMonitor
from .air_runtime import change_view, view
from .config import DomainError
from .monitoring_subjects import _actor


def today(session, user_id, *, before=None, before_id=None):
    organization = _actor(session, user_id)
    if bool(before) != bool(before_id):
        raise DomainError("Both history cursor fields are required.", 422, "air_cursor_invalid")
    newer = aliased(AirChange)
    query = select(AirChange, AirMonitor).join(AirMonitor, AirMonitor.id == AirChange.monitor_id).where(
        AirMonitor.owner_user_id == user_id, AirMonitor.organization_id == organization,
        AirMonitor.status != "archived",
        ~exists(select(newer.id).where(newer.development_id == AirChange.development_id,
                                      newer.sequence > AirChange.sequence)),
    )
    if before:
        query = query.where(or_(AirChange.created_at < utc(before),
            and_(AirChange.created_at == utc(before), AirChange.id < str(before_id))))
    rows = list(session.execute(query.order_by(AirChange.created_at.desc(), AirChange.id.desc()).limit(51)))
    return {
        "items": [{**change_view(event), "monitor_id": monitor.id,
                   "monitor_name": monitor.configuration["name"], "monitor_status": monitor.status,
                   "health": view(monitor)["health"],
                   "muted": event.evidence["sample"]["metric"] in monitor.configuration["muted_metrics"]}
                  for event, monitor in rows[:50]],
        "next": {"before": utc(rows[49][0].created_at).isoformat(), "before_id": rows[49][0].id}
        if len(rows) > 50 else None,
    }
