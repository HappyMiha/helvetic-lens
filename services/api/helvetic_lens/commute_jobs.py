"""Durable private processing of already permitted shared source snapshots.

This worker does not fetch feeds or send mail. Source acquisition is a separate
shared operation so users' route selections are never sent to the provider.
"""

from datetime import timedelta

from sqlalchemy import func, select, update

from . import jobs
from .commute_catalog import resolve_configuration
from .commute_events import process_snapshot
from .commute_interchanges import require_interchanges
from .commute_models import CommuteDatedLeg, CommuteDevelopment, CommuteMonitor, CommuteSignal
from .commute_repository import configuration
from .commute_sources import SOURCES, clock, read_feed, utc
from .config import DomainError
from .monitoring_subjects import _actor, _savepoint
from .transport_reference import ZURICH, commute_window


def mapped_days(session, config, static_version, now):
    day = now.astimezone(ZURICH).date()
    references = [str(value) for value in config.leg_reference_ids]
    return list(session.scalars(select(CommuteDatedLeg.service_day).where(
        CommuteDatedLeg.reference_id.in_(references), CommuteDatedLeg.static_version == static_version,
        CommuteDatedLeg.service_day >= day - timedelta(days=6), CommuteDatedLeg.service_day <= day + timedelta(days=1))
        .group_by(CommuteDatedLeg.service_day).having(func.count(func.distinct(CommuteDatedLeg.reference_id)) == len(references))
        .order_by(CommuteDatedLeg.service_day)))


def ready(session, settings, config, *, now, service_day=None, static_version=None):
    if settings is None or not settings.commute_watch_enabled:
        raise DomainError("Commute processing is unavailable.", 409, "commute_source_not_ready")
    for source in SOURCES:
        _, _, snapshot = read_feed(session, source, now=now, require_fresh=True)
        if not snapshot.feed_version:
            raise DomainError("Transport timetable mapping is unavailable.", 409, "commute_source_not_ready")
        if static_version is not None and static_version != snapshot.feed_version:
            raise DomainError("Preview uses another source timetable.", 409, "commute_dated_reference_unavailable")
        days = mapped_days(session, config, snapshot.feed_version, now)
        if service_day is not None:
            days = [day for day in days if day == service_day]
        future, transfer_failure = [], False
        for day in days:
            legs = resolve_configuration(session, config, service_day=day, static_version=snapshot.feed_version)
            eligible = True
            for leg in legs.values():
                departure_day = leg.departure.astimezone(ZURICH).date()
                if config.window_end < config.window_start and leg.departure.astimezone(ZURICH).strftime("%H:%M") < config.window_end:
                    departure_day -= timedelta(days=1)
                try:
                    window = commute_window(departure_day, config.window_start, config.window_end, config.weekdays)
                except ValueError:
                    window = None
                eligible = eligible and bool(window and window[0] <= leg.departure < window[1])
            if eligible and all(leg.arrival > now for leg in legs.values()):
                try:
                    require_interchanges(session, config, legs)
                except DomainError as error:
                    if error.code != "commute_transfer_unverified":
                        raise
                    transfer_failure = True
                    continue
                future.append(day)
        if not future:
            if transfer_failure:
                raise DomainError("A connected journey needs usable verified interchange data.", 409, "commute_transfer_unverified")
            raise DomainError("The upcoming journey has no verified dated timetable.", 409, "commute_dated_reference_unavailable")
    return True


def enqueue(session, row, now):
    active = session.scalar(select(jobs.Job.id).where(jobs.Job.organization_id == row.organization_id,
        jobs.Job.target_type == "commute_monitor", jobs.Job.target_id == row.id,
        jobs.Job.cancel_requested.is_(False),
        jobs.Job.state.not_in(jobs.TERMINAL_STATES)).limit(1))
    if active:
        return 0
    _, existing = jobs.enqueue(session, job_type="commute_refresh", target_type="commute_monitor", target_id=row.id,
        queue="ingest", priority=5, payload={"version": row.version},
        idempotency_key=f"commute:{row.id}:{row.version}:{int(now.timestamp()) // 30}")
    return int(not existing)


def cancel_work(session, row):
    from .commute_email_preferences import cancel_email_work
    cancel_email_work(session, row)
    session.execute(update(jobs.Job).where(jobs.Job.organization_id == row.organization_id,
        jobs.Job.target_type == "commute_monitor", jobs.Job.target_id == row.id,
        jobs.Job.state.not_in(jobs.TERMINAL_STATES)).values(cancel_requested=True))
    developments = select(CommuteDevelopment.id).where(CommuteDevelopment.monitor_id == row.id,
                                                      CommuteDevelopment.organization_id == row.organization_id)
    session.execute(update(CommuteSignal).where(CommuteSignal.organization_id == row.organization_id,
        CommuteSignal.development_id.in_(developments), CommuteSignal.state == "pending").values(state="cancelled"))


def enqueue_due(database, settings, *, now=None):
    if not settings.commute_watch_enabled:
        return {"enqueued": 0}
    now = clock(now)
    with database.session(include_all_organizations=True) as session:
        candidates = list(session.execute(select(CommuteMonitor.id, CommuteMonitor.organization_id).where(
            CommuteMonitor.status == "active", CommuteMonitor.next_poll_at <= now)
            .order_by(CommuteMonitor.next_poll_at, CommuteMonitor.id).limit(100)))
    count = 0
    for identifier, organization in candidates:
        with database.organization_context(organization), database.session() as session:
            row = session.scalar(select(CommuteMonitor).where(CommuteMonitor.id == identifier).with_for_update())
            if row is None or row.status != "active" or utc(row.next_poll_at) > now:
                continue
            try:
                _actor(session, row.owner_user_id, write=True)
                count += enqueue(session, row, now)
            except DomainError:
                row.health = "access_unavailable"
                cancel_work(session, row)
            row.next_poll_at = now + timedelta(seconds=30)
            session.commit()
    return {"enqueued": count}


def refresh(database, settings, *, monitor_id, version, now=None, checkpoint=lambda: None):
    if not settings.commute_watch_enabled:
        return {"state": "disabled"}
    now = clock(now)
    checkpoint()
    with database.session() as session:
        row = session.scalar(select(CommuteMonitor).where(CommuteMonitor.id == monitor_id,
            CommuteMonitor.organization_id == session.info["organization_id"]).with_for_update()
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
        config = configuration(row.configuration)
        changed, signals, usable, degraded, failures = 0, 0, 0, False, []
        for source in SOURCES:
            try:
                with _savepoint(session):
                    state, permission, snapshot = read_feed(session, source, now=now)
                    days = mapped_days(session, config, snapshot.feed_version, now)
                    if not days:
                        raise DomainError("No verified dated timetable.", 409, "commute_dated_reference_unavailable")
                    results = [process_snapshot(session, row, state, permission, snapshot, service_day=day, now=now) for day in days]
                    source_changed = sum(result["changed"] for result in results)
                    source_signals = sum(result["signals"] for result in results)
                changed += source_changed
                signals += source_signals
                usable += sum(result["usable"] for result in results)
                degraded = degraded or any(result["degraded"] for result in results)
                if (now - snapshot.observed_at).total_seconds() > permission.max_age_seconds:
                    failures.append("commute_feed_stale")
            except DomainError as error:
                failures.append(error.code)
        row.health = ("stale" if set(failures) == {"commute_feed_stale"} else "unavailable" if failures or degraded
                      else "ready" if usable else "waiting_for_predictions")
        row.last_poll_at, row.next_poll_at = now, now + timedelta(seconds=30)
        session.commit()
    return {"state": "processed", "changed": changed, "signals": signals, "failures": failures}
