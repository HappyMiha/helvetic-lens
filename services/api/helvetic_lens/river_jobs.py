"""Durable C6 refreshes recheck private access after public network I/O."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from .config import DomainError
from .monitoring_subjects import _actor
from .river_models import RiverMonitor
from .river_runtime import enqueue, evaluate
from .river_sources import collect


def enqueue_due(database, settings, *, now=None):
    if not settings.river_watch_enabled:
        return {"enqueued": 0}
    now = now or datetime.now(UTC)
    with database.session(include_all_organizations=True) as session:
        candidates = list(session.execute(select(RiverMonitor.id, RiverMonitor.organization_id).where(
            RiverMonitor.status == "active", RiverMonitor.next_poll_at <= now
        ).order_by(RiverMonitor.next_poll_at, RiverMonitor.id).limit(100)))
    count = 0
    for monitor_id, organization_id in candidates:
        with database.organization_context(organization_id), database.session() as session:
            row = session.scalar(select(RiverMonitor).where(RiverMonitor.id == monitor_id).with_for_update())
            if row is None or row.status != "active":
                continue
            try:
                _actor(session, row.owner_user_id, write=True)
                count += enqueue(session, row, now)
                row.next_poll_at = now + timedelta(minutes=10)
            except DomainError:
                row.health = "access_unavailable"
                row.next_poll_at = now + timedelta(minutes=10)
            session.commit()
    return {"enqueued": count}


def refresh(database, settings, *, monitor_id, version, checkpoint=lambda: None, now=None):
    now = now or datetime.now(UTC)
    if not settings.river_watch_enabled:
        return {"status": "disabled"}
    checkpoint()
    with database.session() as session:
        row = session.get(RiverMonitor, monitor_id)
        if row is None or row.status != "active" or row.version != version:
            return {"status": "inactive"}
        try:
            _actor(session, row.owner_user_id, write=True)
        except DomainError:
            return {"status": "access_unavailable"}
        keys = ["catalog", row.configuration["station_id"]]
        if row.configuration["official_danger"]:
            keys.append("danger")
    for key in keys:
        checkpoint()
        collect(database, key, now=now)
    checkpoint()
    with database.session() as session:
        row = session.scalar(select(RiverMonitor).where(RiverMonitor.id == monitor_id).with_for_update())
        if not settings.river_watch_enabled or row is None or row.status != "active" or row.version != version:
            return {"status": "inactive"}
        try:
            _actor(session, row.owner_user_id, write=True)
            result = evaluate(session, row, now)
        except DomainError:
            row.health = "access_or_source_unavailable"
            row.next_poll_at = now + timedelta(minutes=10)
            result = {"status": row.health}
        session.commit()
        return result
