"""Existing durable job/outbox integration for private Pollen runs."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from . import jobs
from .config import DomainError
from .models import Job, MonitoringSubject
from .monitoring_live_models import MonitoringRuntime
from .monitoring_runtime import _configuration, _gate, _require_live, refresh_from_cache
from .monitoring_subjects import _actor, _owned
from .pollen_collector import collect_hourly
from .pollen_sources import HOURLY_METHOD, OBSERVATION_SOURCE


def enqueue_due(database, settings, *, now=None):
    if settings.deployment_instance != "monitoring-v2" or not settings.monitoring_rollout.enabled:
        return {"enqueued": 0}
    now = now or datetime.now(UTC)
    with database.session(include_all_organizations=True) as session:
        candidates = list(session.execute(select(MonitoringRuntime.subject_id, MonitoringRuntime.run_id,
            MonitoringSubject.organization_id, MonitoringSubject.owner_user_id).join(MonitoringSubject,
            MonitoringSubject.id == MonitoringRuntime.subject_id).where(MonitoringSubject.status == "active",
            MonitoringRuntime.next_poll_at <= now).order_by(MonitoringRuntime.next_poll_at, MonitoringRuntime.subject_id).limit(100)))
    enqueued = 0
    for subject_id, run_id, organization_id, owner_id in candidates:
        with database.organization_context(organization_id), database.session() as session:
            try:
                _require_live(settings, organization_id)
                _actor(session, owner_id, write=True)
                subject = _owned(session, organization_id, owner_id, subject_id)
                _gate(settings, _configuration(session, subject), now)
            except DomainError:
                runtime = session.get(MonitoringRuntime, subject_id)
                if runtime:
                    runtime.health = "access_or_source_unavailable"
                    runtime.next_poll_at = now + timedelta(minutes=20)
                    session.commit()
                continue
            pending = session.scalar(select(Job.id).where(Job.organization_id == organization_id,
                Job.type == "pollen_refresh", Job.target_id == subject_id,
                Job.state.in_({"queued", "dispatched", "running", "retrying"})).limit(1))
            if pending:
                runtime = session.get(MonitoringRuntime, subject_id)
                if runtime:
                    runtime.next_poll_at = now + timedelta(minutes=1)
                    session.commit()
                continue
            _, reused = jobs.enqueue(session, job_type="pollen_refresh", target_type="monitoring_subject",
                target_id=subject_id, queue="ingest", idempotency_key=f"pollen:{run_id}:{int(now.timestamp()) // 1200}",
                payload={"run_id": run_id}, max_attempts=3)
            session.commit()
            enqueued += not reused
    return {"enqueued": enqueued}


def refresh(database, settings, *, subject_id, run_id, checkpoint=lambda: None):
    checkpoint()
    now = datetime.now(UTC)
    with database.session() as session:
        subject = session.get(MonitoringSubject, subject_id)
        if subject is None:
            return {"status": "inactive"}
        owner_id = subject.owner_user_id
        try:
            _require_live(settings, subject.organization_id)
            _actor(session, owner_id, write=True)
            runtime = session.get(MonitoringRuntime, subject_id)
            if subject.status != "active" or runtime is None or runtime.run_id != run_id:
                return {"status": "inactive"}
            configuration = _configuration(session, subject)
            _gate(settings, configuration, now)
        except DomainError:
            return {"status": "access_or_source_unavailable"}
    # Fetch only public station/channel data, once per shared channel lease.
    # Recheck private authorization after I/O, before any state or delivery write.
    outcomes = []
    for approval in settings.pollen_source_policy.channels:
        checkpoint()
        if (approval.period != "forecast_instant" and approval.source_id == OBSERVATION_SOURCE
                and approval.method_version in {HOURLY_METHOD, "meteoswiss-automatic-daily-v1"} and configuration.station_id in approval.stations
                and any(s.allergen in approval.allergens for s in configuration.selections)):
            outcomes.append(collect_hourly(database, settings, station_id=configuration.station_id, approval=approval, now=now, checkpoint=checkpoint))
        elif approval.period == "forecast_instant":
            from .pollen_forecast import collect_point
            # Deliberately bounded to the documented captured 00 UTC cycle.
            # Later cycles require a separately reviewed scheduling contract.
            issue = now.replace(hour=0, minute=0, second=0, microsecond=0)
            valid = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=24)
            for selection in configuration.selections:
                if selection.allergen not in approval.allergens or configuration.station_id not in approval.stations:
                    continue
                instants = {valid}
                for rule in selection.rules:
                    if rule.period == "forecast_instant" and rule.rapid_increase:
                        instants.add(valid - timedelta(hours=rule.rapid_increase.window_hours))
                for instant in sorted(instants):
                    outcomes.append(collect_point(database, settings, approval=approval, allergen=selection.allergen,
                                  issue=issue, valid=instant, now=now, checkpoint=checkpoint))
    checkpoint()
    with database.session() as session:
        try:
            result = refresh_from_cache(session, settings=settings, user_id=owner_id, subject_id=subject_id,
                                        run_id=run_id, now=datetime.now(UTC))
            if result["status"] in {"ready", "waiting", "unavailable"} and any(
                outcome.get("source_error") or outcome["status"] in {"official_source_unavailable", "forecast_unavailable", "lease_expired"}
                for outcome in outcomes):
                session.get(MonitoringRuntime, subject_id).health = "source_unavailable"
                result["status"] = "source_unavailable"
            session.commit()
            return result
        except DomainError:
            session.rollback()
            return {"status": "access_or_source_unavailable"}
