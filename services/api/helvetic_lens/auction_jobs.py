"""Bounded, replay-safe projection of permitted journal records into private watches."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from .auction_contracts import clock
from .auction_models import AuctionMonitor
from .auction_workflow import refresh
from .auction_workflow_models import AuctionRuntime
from .config import DomainError

MAX_DUE = 20


def refresh_due(database, settings, *, now=None):
    now = clock(now or datetime.now(UTC))
    if not settings.auction_watch_enabled:
        return {"refreshed": 0, "unavailable": 0}
    with database.session(include_all_organizations=True) as session:
        due = list(session.execute(select(AuctionMonitor.id, AuctionMonitor.organization_id, AuctionMonitor.owner_user_id)
            .join(AuctionRuntime, AuctionRuntime.monitor_id == AuctionMonitor.id)
            .where(AuctionMonitor.status == "active", AuctionRuntime.next_check_at <= now)
            .order_by(AuctionRuntime.next_check_at, AuctionMonitor.id).limit(MAX_DUE)))
    result = {"refreshed": 0, "unavailable": 0}
    for monitor_id, organization_id, owner in due:
        with database.organization_context(organization_id), database.session() as session:
            # Same monitor-before-source lock order as interactive actions. A
            # duplicate task observes the committed next_check_at and skips.
            monitor = session.scalar(select(AuctionMonitor).where(AuctionMonitor.id == monitor_id,
                AuctionMonitor.owner_user_id == owner, AuctionMonitor.status == "active")
                .with_for_update(skip_locked=True).execution_options(populate_existing=True))
            if monitor is None:
                continue
            runtime = session.get(AuctionRuntime, monitor_id, populate_existing=True)
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
                elif error.code in {"auction_item_capacity", "auction_item_event_capacity", "auction_source_capacity"}:
                    runtime.health = "capacity_reached"
                    runtime.next_check_at = now + timedelta(minutes=5)
                result["unavailable"] += 1
            session.commit()
    return result
