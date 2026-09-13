"""Explicit private monitor transitions. Source evidence never authorizes email."""

from sqlalchemy import func, select, update

from . import jobs
from .hazard_models import HazardMonitor, HazardMonitorAction
from .hazard_readiness import ready
from .hazard_repository import _fail, _version, configuration, get_monitor, owned
from .hazard_sources import _clock, _utc
from .monitoring_subjects import _savepoint

MAX_ACTIONS = 10000


def cancel_work(session, monitor):
    from .hazard_email_preferences import cancel_email_work
    cancel_email_work(session, monitor)
    session.execute(update(jobs.Job).where(jobs.Job.organization_id == monitor.organization_id,
        jobs.Job.target_type == "hazard_monitor", jobs.Job.target_id == monitor.id,
        jobs.Job.state.not_in(jobs.TERMINAL_STATES)).values(cancel_requested=True))


def enqueue(session, monitor, now):
    active = session.scalar(select(jobs.Job.id).where(jobs.Job.organization_id == monitor.organization_id,
        jobs.Job.type == "hazard_refresh", jobs.Job.target_type == "hazard_monitor", jobs.Job.target_id == monitor.id,
        jobs.Job.cancel_requested.is_(False), jobs.Job.state.not_in(jobs.TERMINAL_STATES)).limit(1))
    if active:
        return 0
    _, existing = jobs.enqueue(session, job_type="hazard_refresh", target_type="hazard_monitor", target_id=monitor.id,
        queue="ingest", priority=5, payload={"version": monitor.version},
        idempotency_key=f"hazard:{monitor.id}:{monitor.version}:{int(now.timestamp()) // 60}")
    return int(not existing)


def command(session, user_id, monitor_id, version, action, *, settings, store, now):
    now = _clock(now)
    _version(version)
    monitor = owned(session, user_id, monitor_id, write=True)
    if monitor.version != version:
        _fail("hazard_version_conflict")
    previous = monitor.status
    target = {"start": "active", "resume": "active", "pause": "paused", "archive": "archived"}.get(action)
    allowed = {"start": {"draft"}, "resume": {"paused"}, "pause": {"active"}, "archive": {"draft", "active", "paused"}}
    if target is None or previous not in allowed[action]:
        _fail("hazard_action_invalid")
    config = configuration(monitor.configuration)
    # Source permission -> selection -> monitor is the same lock order as event
    # projection. Stopping never needs a working source or boundary catalogue.
    proof = ready(session, settings, config, store=store, now=now) if target == "active" else None
    monitor = session.scalar(select(HazardMonitor).where(HazardMonitor.id == monitor.id,
        HazardMonitor.organization_id == monitor.organization_id, HazardMonitor.owner_user_id == user_id)
        .with_for_update().execution_options(populate_existing=True))
    if monitor.version != version or monitor.status != previous or monitor.configuration != config.model_dump(mode="json"):
        _fail("hazard_version_conflict")
    if session.scalar(select(func.count()).select_from(HazardMonitorAction).where(
            HazardMonitorAction.monitor_id == monitor.id)) >= MAX_ACTIONS and target == "active":
        _fail("hazard_action_history_limit")
    with _savepoint(session):
        changed = session.execute(update(HazardMonitor).where(HazardMonitor.id == monitor.id,
            HazardMonitor.organization_id == monitor.organization_id, HazardMonitor.owner_user_id == user_id,
            HazardMonitor.version == version, HazardMonitor.status == previous).values(status=target, version=version + 1,
                health="waiting" if target == "active" else target, next_poll_at=now if target == "active" else None,
                activation_proof=proof).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            _fail("hazard_version_conflict")
        cancel_work(session, monitor)
        session.refresh(monitor)
        if proof is not None:
            if ready(session, settings, config, store=store, now=now) != proof:
                _fail("hazard_activation_evidence_changed")
            enqueue(session, monitor, now)
        session.add(HazardMonitorAction(organization_id=monitor.organization_id, monitor_id=monitor.id,
            user_id=user_id, action=action, previous_status=previous, status=target, version=version + 1,
            configuration_revision=monitor.revision, proof=proof, created_at=now))
        session.flush()
    return get_monitor(session, user_id, monitor_id)


def history(session, user_id, monitor_id, *, limit=20, before=None):
    monitor = owned(session, user_id, monitor_id)
    if type(limit) is not int or not 1 <= limit <= 20:
        _fail("hazard_page_invalid", 422)
    query = select(HazardMonitorAction).where(HazardMonitorAction.monitor_id == monitor.id,
                                            HazardMonitorAction.organization_id == monitor.organization_id)
    if before is not None:
        _version(before)
        if before > monitor.version:
            _fail("hazard_action_cursor_invalid", 422)
        query = query.where(HazardMonitorAction.version < before)
    rows = list(session.scalars(query.order_by(HazardMonitorAction.version.desc()).limit(limit + 1)))
    return {"items": [{"id": row.id, "action": row.action, "previous_status": row.previous_status, "status": row.status,
                       "version": row.version, "configuration_revision": row.configuration_revision,
                       "created_at": _utc(row.created_at).isoformat()} for row in rows[:limit]],
            "next_cursor": rows[limit - 1].version if len(rows) > limit else None}
