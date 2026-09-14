"""Bounded, replay-safe projection of permitted journal records into private watches."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from .config import DomainError
from .trademark_models import TrademarkMonitor
from .trademark_sources import _clock as clock
from .trademark_workflow import refresh
from .trademark_workflow_models import TrademarkRuntime

MAX_DUE = 20


def refresh_due(database, settings, *, now=None):
    now = clock(now or datetime.now(UTC))
    if not settings.trademark_watch_enabled:
        return {"refreshed": 0, "unavailable": 0}
    with database.session(include_all_organizations=True) as session:
        due = list(session.execute(select(TrademarkMonitor.id, TrademarkMonitor.organization_id, TrademarkMonitor.owner_user_id)
            .join(TrademarkRuntime, TrademarkRuntime.monitor_id == TrademarkMonitor.id)
            .where(TrademarkMonitor.status == "active", TrademarkRuntime.next_check_at <= now)
            .order_by(TrademarkRuntime.next_check_at, TrademarkMonitor.id).limit(MAX_DUE)))
    result = {"refreshed": 0, "unavailable": 0}
    for monitor_id, organization_id, owner in due:
        with database.organization_context(organization_id), database.session() as session:
            # Same monitor-before-source lock order as interactive actions. A
            # duplicate task observes the committed next_check_at and skips.
            monitor = session.scalar(select(TrademarkMonitor).where(TrademarkMonitor.id == monitor_id,
                TrademarkMonitor.owner_user_id == owner, TrademarkMonitor.status == "active")
                .with_for_update(skip_locked=True).execution_options(populate_existing=True))
            if monitor is None:
                continue
            runtime = session.get(TrademarkRuntime, monitor_id, populate_existing=True)
            due_at = runtime.next_check_at if runtime else None
            if due_at is None or (due_at.replace(tzinfo=UTC) if due_at.tzinfo is None else due_at) > now:
                continue
            try:
                refreshed = refresh(session, owner, monitor_id, now=now)
                result["unavailable" if refreshed["health"] == "source_unavailable" else "refreshed"] += 1
            except DomainError as error:
                # Refresh's savepoint rolled back all partial source projections.
                runtime.health, runtime.last_check_at = "source_unavailable", now
                runtime.next_check_at = now + timedelta(seconds=60)
                if error.code in {"membership_required", "subject_role_denied"}:
                    monitor.status, monitor.version = "paused", monitor.version + 1
                    runtime.health, runtime.next_check_at = "access_unavailable", None
                elif error.code in {"trademark_candidate_capacity", "trademark_event_capacity", "trademark_source_capacity"}:
                    runtime.health = "capacity_reached"
                    runtime.next_check_at = now + timedelta(minutes=5)
                result["unavailable"] += 1
            session.commit()
    return result
