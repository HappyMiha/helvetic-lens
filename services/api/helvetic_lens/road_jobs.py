"""Durable per-owner processing of shared road evidence; no provider calls or mail."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from . import jobs
from .config import DomainError
from .monitoring_subjects import _actor, _savepoint
from .road_catalog import CatalogReadBudget, _rights, resolve_reference
from .road_events import FIELDS, process_snapshot
from .road_models import RoadCorridorMap, RoadDevelopment, RoadMonitor, RoadTopologyRevision
from .road_sources import _clock, _head, _utc, read_state, require_permission


def clock():
    return datetime.now(UTC)


def ready(session, settings, config, *, now):
    if settings is None or not settings.road_watch_enabled or not settings.road_source_enabled or not settings.road_source_permission_id:
        raise DomainError("Road source processing is unavailable.", 409, "road_source_not_ready")
    require_permission(session, settings.road_source_permission_id, now=now, fields=FIELDS)
    state = read_state(session, settings.road_source_permission_id, now=now)
    keys = {(r.location.country, r.location.table, r.location.version) for entry in state.situations
            if entry.present for r in entry.situation.records if r.location is not None}
    budget = CatalogReadBudget()
    for reference in sorted(str(value) for value in config.corridor_reference_ids):
        tables = set(session.execute(select(RoadTopologyRevision.country, RoadTopologyRevision.table, RoadTopologyRevision.version)
            .join(RoadCorridorMap, RoadCorridorMap.topology_id == RoadTopologyRevision.id)
            .where(RoadCorridorMap.reference_id == reference)).all())
        candidates = tables.intersection(keys) if keys else tables
        usable = False
        for key in sorted(candidates):
            try:
                resolve_reference(session, reference, table_key=tuple(key), now=now, display=True, read_budget=budget)
                usable = True
                break
            except DomainError:
                continue
        if not usable:
            raise DomainError("A selected road corridor has no current verified mapping.", 409, "road_corridor_not_ready")
    return True


def enqueue(session, row, now):
    active = session.scalar(select(jobs.Job.id).where(jobs.Job.type == "road_refresh",
        jobs.Job.target_type == "road_monitor", jobs.Job.target_id == row.id,
        jobs.Job.organization_id == row.organization_id, jobs.Job.cancel_requested.is_(False),
        jobs.Job.state.not_in(jobs.TERMINAL_STATES)).limit(1))
    if active:
        return 0
    _, existing = jobs.enqueue(session, job_type="road_refresh", target_type="road_monitor", target_id=row.id,
        queue="ingest", priority=5, payload={"version": row.version},
        idempotency_key=f"road:{row.id}:{row.version}:{int(now.timestamp()) // 60}")
    return int(not existing)


def cancel_work(session, row):
    from .road_email_preferences import cancel_email_work
    cancel_email_work(session, row)
    session.execute(update(jobs.Job).where(jobs.Job.target_type == "road_monitor", jobs.Job.target_id == row.id,
        jobs.Job.organization_id == row.organization_id, jobs.Job.state.not_in(jobs.TERMINAL_STATES)).values(cancel_requested=True))


def enqueue_due(database, settings, *, now=None):
    if not settings.road_watch_enabled:
        return {"enqueued": 0}
    now = _clock(now or clock())
    with database.session(include_all_organizations=True) as session:
        candidates = list(session.execute(select(RoadMonitor.id, RoadMonitor.organization_id).where(
            RoadMonitor.status == "active", RoadMonitor.next_poll_at <= now)
            .order_by(RoadMonitor.next_poll_at, RoadMonitor.id).limit(100)))
    count = 0
    for identifier, org in candidates:
        with database.organization_context(org), database.session() as session:
            row = session.scalar(select(RoadMonitor).where(RoadMonitor.id == identifier).with_for_update()
                                 .execution_options(populate_existing=True))
            if row is None or row.status != "active" or _utc(row.next_poll_at) > now:
                continue
            try:
                _actor(session, row.owner_user_id, write=True)
                count += enqueue(session, row, now)
            except DomainError:
                row.health = "access_unavailable"
                cancel_work(session, row)
            row.next_poll_at = now + timedelta(seconds=60)
            session.commit()
    return {"enqueued": count}


def refresh(database, settings, *, monitor_id, version, now=None, checkpoint=lambda: None, job_id=None, lease_owner=None):
    if not settings.road_watch_enabled or not settings.road_source_enabled:
        return {"state": "disabled"}
    clock_fn = clock if now is None else lambda: now
    now = _clock(clock_fn())
    permission_id = settings.road_source_permission_id
    checkpoint()
    with database.session() as session:
        row = session.scalar(select(RoadMonitor).where(RoadMonitor.id == monitor_id).with_for_update()
                             .execution_options(populate_existing=True))
        if row is None or row.status != "active" or row.version != version:
            return {"state": "superseded"}
        try:
            _actor(session, row.owner_user_id, write=True)
        except DomainError:
            row.health = "access_unavailable"
            cancel_work(session, row)
            session.commit()
            return {"state": "access_unavailable"}
        try:
            with _savepoint(session):
                result = process_snapshot(session, row, permission_id, now=now)
                finished = _clock(clock_fn())
                if (not settings.road_watch_enabled or not settings.road_source_enabled
                        or settings.road_source_permission_id != permission_id):
                    raise DomainError("Road processing configuration changed.", 409, "road_source_configuration_changed")
                _, policy = require_permission(session, permission_id, now=finished, fields=FIELDS)
                head = _head(session)
                if (head is None or head.permission_id != permission_id or head.published_at is None
                        or not 0 <= (finished - _utc(head.published_at)).total_seconds() <= policy.max_age_seconds):
                    raise DomainError("Road source is stale.", 409, "road_source_stale")
                mapped_ids = set()
                for event in session.scalars(select(RoadDevelopment).where(RoadDevelopment.monitor_id == row.id,
                        RoadDevelopment.configuration_revision == row.revision, RoadDevelopment.permission_id == permission_id)):
                    if event.payload is not None:
                        if _utc(event.expires_at) <= finished:
                            raise DomainError("Road evidence expired during processing.", 409, "road_event_expired")
                        mapped_ids.update(event.proof.get("mapping_ids", ()))
                topology_ids = session.scalars(select(RoadCorridorMap.topology_id).where(RoadCorridorMap.id.in_(mapped_ids))
                                               .distinct().order_by(RoadCorridorMap.topology_id))
                for topology_id in topology_ids:
                    _rights(session, topology_id, now=finished, matching=True, display=True)
                if job_id is not None:
                    # Recheck/capture the lease in this same transaction. A
                    # second connection heartbeat would deadlock SQLite after
                    # staged writes, and cannot make cancellation atomic.
                    lease_clock = datetime.now(UTC)
                    active = session.execute(update(jobs.Job).where(jobs.Job.id == job_id,
                        jobs.Job.organization_id == row.organization_id, jobs.Job.target_type == "road_monitor",
                        jobs.Job.target_id == row.id, jobs.Job.state == "running", jobs.Job.lease_owner == lease_owner,
                        jobs.Job.cancel_requested.is_(False),
                        jobs.Job.heartbeat_at >= lease_clock - timedelta(seconds=settings.job_lease_seconds))
                        .values(heartbeat_at=lease_clock, updated_at=lease_clock).execution_options(synchronize_session=False))
                    if active.rowcount != 1:
                        raise jobs.JobCancelled()
            row.health = "unavailable" if result["degraded"] else "ready"
        except DomainError as error:
            result = {"changed": 0, "reason": error.code}
            row.health = "stale" if error.code == "road_source_stale" else "unavailable"
        row.last_poll_at, row.next_poll_at = now, now + timedelta(seconds=60)
        session.commit()
    return {"state": "processed", **result}
