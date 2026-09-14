"""Durable private processing of the shared warning journal; no source HTTP/mail."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from . import jobs
from .config import DomainError
from .hazard_boundary_store import BoundaryStore
from .hazard_events import project_message
from .hazard_lifecycle import cancel_work, enqueue
from .hazard_models import HazardMonitor
from .hazard_readiness import ready
from .hazard_reconciliation import MAX_MESSAGES
from .hazard_repository import configuration
from .hazard_source_models import HazardCurrentWarning
from .hazard_sources import _clock, _utc, purge_content
from .monitoring_subjects import _actor, _savepoint


def clock():
    return datetime.now(UTC)


def cleanup(database, *, now=None):
    # Retention still applies while acquisition/private processing is disabled.
    with database.session(include_all_organizations=True) as session:
        result = purge_content(session, now=_clock(now or clock()))
        session.commit()
        return result


def enqueue_due(database, settings, *, now=None):
    if not settings.hazard_watch_enabled or not settings.hazard_source_enabled:
        return {"enqueued": 0}
    now = _clock(now or clock())
    with database.session(include_all_organizations=True) as session:
        candidates = list(session.execute(select(HazardMonitor.id, HazardMonitor.organization_id).where(
            HazardMonitor.status == "active", HazardMonitor.next_poll_at <= now)
            .order_by(HazardMonitor.next_poll_at, HazardMonitor.id).limit(100)))
    count = 0
    for identifier, org in candidates:
        with database.organization_context(org), database.session() as session:
            row = session.scalar(select(HazardMonitor).where(HazardMonitor.id == identifier).with_for_update()
                                 .execution_options(populate_existing=True))
            if row is None or row.status != "active" or row.next_poll_at is None or _utc(row.next_poll_at) > now:
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


def refresh(database, settings, *, monitor_id, version, now=None, store=None, checkpoint=lambda: None, job_id=None, lease_owner=None):
    if not settings.hazard_watch_enabled or not settings.hazard_source_enabled:
        return {"state": "disabled"}
    current_time = clock if now is None else lambda: now
    started = _clock(current_time())
    store = store or BoundaryStore(settings.storage_path)
    checkpoint()
    with database.session() as session:
        row = session.get(HazardMonitor, monitor_id)
        if row is None or row.status != "active" or row.version != version or type(version) is not int:
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
                config = configuration(row.configuration)
                proof = ready(session, settings, config, store=store, now=started)
                heads = list(session.scalars(select(HazardCurrentWarning.evidence_id).where(
                    HazardCurrentWarning.permission_id == proof["permission_id"],
                    HazardCurrentWarning.generation == proof["generation"])
                    .order_by(HazardCurrentWarning.development_key).limit(MAX_MESSAGES + 1)))
                if len(heads) > MAX_MESSAGES:
                    raise DomainError("Warning source batch exceeds the bound.", 409, "hazard_source_batch_limit")
                changed, unavailable = 0, 0
                for evidence in heads:
                    try:
                        result = project_message(session, row.owner_user_id, monitor_id, proof["permission_id"], evidence,
                            monitor_version=version, source_generation=proof["generation"], source_cursor=proof["cursor"],
                            store=store, now=started)
                    except DomainError as error:
                        if error.code not in {"hazard_evidence_unavailable", "hazard_evidence_stale", "hazard_warning_period_expired",
                                             "hazard_source_poll_not_current", "hazard_source_no_longer_listed"}:
                            raise
                        unavailable += 1
                        continue
                    changed += int(result["changed"])
                finished = _clock(current_time())
                if ready(session, settings, config, store=store, now=finished) != proof:
                    raise DomainError("Warning source changed during processing.", 409, "hazard_processing_evidence_changed")
                # Publication and lease/cancellation check share this transaction.
                # A separate heartbeat connection after SQLite writes would block.
                if job_id is not None:
                    lease_now = datetime.now(UTC)
                    active = session.execute(update(jobs.Job).where(jobs.Job.id == job_id,
                        jobs.Job.organization_id == row.organization_id, jobs.Job.target_type == "hazard_monitor",
                        jobs.Job.target_id == monitor_id, jobs.Job.state == "running", jobs.Job.lease_owner == lease_owner,
                        jobs.Job.cancel_requested.is_(False), jobs.Job.heartbeat_at >= lease_now - timedelta(seconds=settings.job_lease_seconds))
                        .values(heartbeat_at=lease_now, updated_at=lease_now).execution_options(synchronize_session=False))
                    if active.rowcount != 1:
                        raise jobs.JobCancelled()
                updated = session.execute(update(HazardMonitor).where(HazardMonitor.id == monitor_id,
                    HazardMonitor.organization_id == row.organization_id, HazardMonitor.version == version,
                    HazardMonitor.status == "active").values(health="unavailable" if unavailable else "ready", last_poll_at=finished,
                    next_poll_at=finished + timedelta(seconds=60)).execution_options(synchronize_session=False))
                if updated.rowcount != 1:
                    raise jobs.JobCancelled()
                session.flush()
            session.commit()
            return {"state": "processed", "changed": changed, "unavailable": unavailable, "coverage_verified": False}
        except DomainError as error:
            session.execute(update(HazardMonitor).where(HazardMonitor.id == monitor_id,
                HazardMonitor.organization_id == row.organization_id, HazardMonitor.version == version,
                HazardMonitor.status == "active").values(health="unavailable", last_poll_at=started,
                    next_poll_at=started + timedelta(seconds=60)).execution_options(synchronize_session=False))
            session.commit()
            return {"state": "unavailable", "reason": error.code}
