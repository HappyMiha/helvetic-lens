"""Persisted scheduling and organization fan-out for official connectors."""

from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import jobs as durable_jobs
from .config import DomainError, Settings
from .db import utcnow
from .models import (
    ConnectorItemError,
    ConnectorRun,
    ConnectorSchedule,
    ConnectorState,
    DocumentWatch,
    FeedState,
    Job,
    LegacyDocumentMapping,
    Organization,
    OutboxMessage,
    RegulatoryEvent,
    RegulatoryEventState,
)

ACTIVE_JOB_STATES = frozenset(
    {"queued", "dispatched", "running", "retrying", "waiting_for_model"}
)
SWISS_TIME = ZoneInfo("Europe/Zurich")
_CLOCK = re.compile(r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")


@dataclass(frozen=True)
class ScheduleDefinition:
    connector: str
    stream: str
    interval_seconds: int
    jitter_seconds: int
    overlap_policy: str
    rate_limit_seconds: float


DEFAULT_SCHEDULES = (
    ScheduleDefinition("fedlex", "rss-de", 900, 90, "RSS watermark with connector overlap", 0.2),
    ScheduleDefinition("fedlex", "rss-fr", 900, 90, "RSS watermark with connector overlap", 0.2),
    ScheduleDefinition("fedlex", "rss-it", 900, 90, "RSS watermark with connector overlap", 0.2),
    ScheduleDefinition("fedlex", "reconcile-cc", 86_400, 900, "bounded keyset cycle", 0.2),
    ScheduleDefinition("fedlex", "reconcile-oc", 86_400, 900, "bounded keyset cycle", 0.2),
    ScheduleDefinition("fedlex", "reconcile-fga", 86_400, 900, "bounded keyset cycle", 0.2),
    ScheduleDefinition("swiss-parliament", "recent", 3_600, 300, "recent-tail overlap", 0.2),
    ScheduleDefinition(
        "swiss-parliament",
        "notices",
        1_800,
        180,
        "official Modified/ID watermark",
        0.2,
    ),
    ScheduleDefinition("swiss-parliament", "active", 21_600, 900, "known-active reconciliation", 0.2),
    ScheduleDefinition("swiss-parliament", "catalogue", 86_400, 900, "complete ID keyset cycle", 0.2),
    ScheduleDefinition(
        "federal-supreme-court",
        "latest",
        3_600,
        300,
        "five insertion-date overlap",
        2.0,
    ),
    ScheduleDefinition(
        "federal-supreme-court",
        "reconcile",
        86_400,
        900,
        "current/previous-year insertion-date cycle",
        2.0,
    ),
)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _iso(value: datetime | None) -> str | None:
    return _aware(value).isoformat() if value else None


def _jitter(schedule: ConnectorSchedule, base: datetime) -> int:
    if schedule.jitter_seconds <= 0:
        return 0
    digest = hashlib.sha256(f"{schedule.id}:{base.isoformat()}".encode()).digest()
    return int.from_bytes(digest[:4], "big") % (schedule.jitter_seconds + 1)


def _clock(value: str | None) -> time | None:
    if not value:
        return None
    if not _CLOCK.fullmatch(value):
        raise DomainError("Use HH:MM for a synchronization window.", 422, "invalid_sync_window")
    return time.fromisoformat(value)


def _inside_window(now: datetime, start: str | None, end: str | None) -> bool:
    if not start and not end:
        return True
    if not start or not end:
        return False
    local = _aware(now).astimezone(SWISS_TIME).time().replace(tzinfo=None)
    start_time, end_time = _clock(start), _clock(end)
    if start_time == end_time:
        return True
    if start_time < end_time:
        return start_time <= local < end_time
    return local >= start_time or local < end_time


def _next_window(now: datetime, start: str | None) -> datetime:
    start_time = _clock(start)
    if start_time is None:
        return _aware(now) + timedelta(minutes=5)
    local = _aware(now).astimezone(SWISS_TIME)
    candidate = datetime.combine(local.date(), start_time, tzinfo=SWISS_TIME)
    if candidate <= local:
        candidate += timedelta(days=1)
    return candidate.astimezone(UTC)


def _next_due(schedule: ConnectorSchedule, now: datetime) -> datetime:
    base = max(_aware(now), _aware(schedule.next_run_at))
    return base + timedelta(seconds=schedule.interval_seconds + _jitter(schedule, base))


def seed_schedules(session: Session, now: datetime | None = None) -> int:
    """Add missing defaults without overwriting administrator choices."""

    now = _aware(now or utcnow())
    existing = {
        (item.connector, item.stream): item
        for item in session.scalars(select(ConnectorSchedule)).all()
    }
    created = 0
    for position, definition in enumerate(DEFAULT_SCHEDULES):
        if (definition.connector, definition.stream) in existing:
            continue
        session.add(
            ConnectorSchedule(
                connector=definition.connector,
                stream=definition.stream,
                enabled=True,
                interval_seconds=definition.interval_seconds,
                jitter_seconds=definition.jitter_seconds,
                next_run_at=now + timedelta(seconds=position * 30),
                policy_json={
                    "overlap": definition.overlap_policy,
                    "minimum_request_interval_seconds": definition.rate_limit_seconds,
                    "timezone": "Europe/Zurich",
                },
            )
        )
        created += 1
    session.flush()
    return created


def _active_job(session: Session, schedule_id: str) -> Job | None:
    return session.scalar(
        select(Job)
        .where(
            Job.type == "connector_sync",
            Job.target_type == "connector_schedule",
            Job.target_id == schedule_id,
            Job.state.in_(ACTIVE_JOB_STATES),
        )
        .order_by(Job.created_at.desc())
        .limit(1)
    )


def queue_pressure(session: Session, settings: Settings) -> dict:
    active = int(
        session.scalar(
            select(func.count()).select_from(Job).where(
                Job.type == "connector_sync",
                Job.state.in_(ACTIVE_JOB_STATES),
            )
        )
        or 0
    )
    pending = int(
        session.scalar(
            select(func.count()).select_from(OutboxMessage).where(
                OutboxMessage.queue == "ingest",
                OutboxMessage.state == "pending",
            )
        )
        or 0
    )
    try:
        free_megabytes = shutil.disk_usage(settings.storage_path).free // (1024 * 1024)
    except OSError:
        free_megabytes = 0
    reasons = []
    if active >= settings.connector_max_active_jobs:
        reasons.append("active_limit")
    if pending >= settings.connector_max_queue_depth:
        reasons.append("queue_depth")
    if free_megabytes < settings.connector_min_free_megabytes:
        reasons.append("disk_space")
    return {
        "blocked": bool(reasons),
        "reasons": reasons,
        "active": active,
        "active_limit": settings.connector_max_active_jobs,
        "pending": pending,
        "pending_limit": settings.connector_max_queue_depth,
        "free_megabytes": free_megabytes,
        "minimum_free_megabytes": settings.connector_min_free_megabytes,
    }


def _enqueue(
    session: Session,
    schedule: ConnectorSchedule,
    *,
    organization_id: str,
    trigger: str,
    settings: Settings,
    now: datetime,
) -> tuple[Job, ConnectorRun, bool]:
    active = _active_job(session, schedule.id)
    if active:
        run = session.scalar(select(ConnectorRun).where(ConnectorRun.job_id == active.id))
        return active, run, True
    run = ConnectorRun(
        schedule_id=schedule.id,
        requested_by_organization_id=organization_id,
        connector=schedule.connector,
        stream=schedule.stream,
        trigger=trigger,
        status="queued",
    )
    session.add(run)
    session.flush()
    due_slot = int(_aware(schedule.next_run_at).timestamp()) if trigger == "scheduled" else run.id
    job, reused = durable_jobs.enqueue(
        session,
        job_type="connector_sync",
        target_type="connector_schedule",
        target_id=schedule.id,
        queue="ingest",
        idempotency_key=f"connector:{schedule.id}:{due_slot}",
        payload={
            "run_id": run.id,
            "connector": schedule.connector,
            "stream": schedule.stream,
            "trigger": trigger,
        },
        priority=4 if trigger == "scheduled" else 2,
        progress_total=3,
        max_attempts=settings.job_max_attempts,
        steps=[
            ("Discover one bounded source page", {}),
            ("Persist shared evidence", {}),
            ("Fan out organization feed state", {}),
        ],
        organization_id=organization_id,
    )
    run.job_id = job.id
    schedule.last_job_id = job.id
    schedule.last_enqueued_at = now
    schedule.updated_at = now
    return job, run, reused


def enqueue_due(
    session: Session,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> dict:
    now = _aware(now or utcnow())
    seed_schedules(session, now)
    pressure = queue_pressure(session, settings)
    if pressure["blocked"]:
        return {"queued": 0, "deferred": 0, "pressure": pressure}
    organization_id = session.scalar(select(Organization.id).order_by(Organization.created_at).limit(1))
    if not organization_id:
        return {"queued": 0, "deferred": 0, "pressure": pressure}
    capacity = max(0, settings.connector_max_active_jobs - pressure["active"])
    schedules = list(
        session.scalars(
            select(ConnectorSchedule)
            .where(
                ConnectorSchedule.enabled.is_(True),
                ConnectorSchedule.next_run_at <= now,
            )
            .order_by(ConnectorSchedule.next_run_at, ConnectorSchedule.connector)
            .limit(capacity)
            .with_for_update(skip_locked=True)
        )
    )
    queued, deferred = 0, 0
    for schedule in schedules:
        if not _inside_window(now, schedule.window_start, schedule.window_end):
            schedule.next_run_at = _next_window(now, schedule.window_start)
            schedule.updated_at = now
            deferred += 1
            continue
        _, _, reused = _enqueue(
            session,
            schedule,
            organization_id=organization_id,
            trigger="scheduled",
            settings=settings,
            now=now,
        )
        schedule.next_run_at = _next_due(schedule, now)
        if not reused:
            queued += 1
    return {"queued": queued, "deferred": deferred, "pressure": pressure}


def enqueue_manual(
    session: Session,
    settings: Settings,
    connector: str,
    stream: str,
    organization_id: str,
    *,
    now: datetime | None = None,
) -> tuple[Job, ConnectorRun, bool]:
    now = _aware(now or utcnow())
    schedule = session.scalar(
        select(ConnectorSchedule)
        .where(
            ConnectorSchedule.connector == connector,
            ConnectorSchedule.stream == stream,
        )
        .with_for_update()
    )
    if not schedule:
        raise DomainError(
            "Choose a supported connector and synchronization stream.",
            422,
            "connector_schedule_invalid",
        )
    pressure = queue_pressure(session, settings)
    active = _active_job(session, schedule.id)
    if pressure["blocked"] and not active:
        raise DomainError(
            "Synchronization is temporarily paused by queue or disk backpressure.",
            503,
            "connector_backpressure",
        )
    return _enqueue(
        session,
        schedule,
        organization_id=organization_id,
        trigger="manual",
        settings=settings,
        now=now,
    )


def update_schedule(
    session: Session,
    connector: str,
    stream: str,
    *,
    enabled: bool,
    interval_seconds: int,
    jitter_seconds: int,
    window_start: str | None,
    window_end: str | None,
    now: datetime | None = None,
) -> ConnectorSchedule:
    if interval_seconds < 60 or interval_seconds > 2_592_000:
        raise DomainError(
            "Choose an interval between one minute and 30 days.",
            422,
            "invalid_sync_interval",
        )
    if jitter_seconds < 0 or jitter_seconds > min(interval_seconds // 2, 86_400):
        raise DomainError(
            "Jitter must be non-negative and no more than half the interval.",
            422,
            "invalid_sync_jitter",
        )
    if bool(window_start) != bool(window_end):
        raise DomainError(
            "Set both synchronization window times or leave both empty.",
            422,
            "invalid_sync_window",
        )
    _clock(window_start)
    _clock(window_end)
    schedule = session.scalar(
        select(ConnectorSchedule)
        .where(
            ConnectorSchedule.connector == connector,
            ConnectorSchedule.stream == stream,
        )
        .with_for_update()
    )
    if not schedule:
        raise DomainError("The connector schedule was not found.", 404, "not_found")
    now = _aware(now or utcnow())
    schedule.enabled = enabled
    schedule.interval_seconds = interval_seconds
    schedule.jitter_seconds = jitter_seconds
    schedule.window_start = window_start or None
    schedule.window_end = window_end or None
    schedule.updated_at = now
    if enabled and (not schedule.next_run_at or _aware(schedule.next_run_at) > now):
        schedule.next_run_at = now
    return schedule


def start_run(session: Session, run_id: str, now: datetime | None = None) -> ConnectorRun:
    run = session.get(ConnectorRun, run_id)
    if not run:
        raise DomainError("The connector run was not found.", 404, "not_found")
    state = session.scalar(
        select(ConnectorState).where(
            ConnectorState.connector == run.connector,
            ConnectorState.stream == run.stream,
        )
    )
    first_attempt = run.started_at is None
    run.status = "running"
    # Preserve the first attempt boundary. A connector may commit official
    # records and then lose its worker before fan-out; the durable retry must
    # still discover those already persisted events.
    run.started_at = run.started_at or _aware(now or utcnow())
    run.finished_at = None
    run.error_detail = None
    run.duration_ms = None
    if first_attempt:
        run.input_cursor_json = state.cursor_json if state else None
    return run


def fail_run(
    session: Session,
    run_id: str,
    detail: str,
    *,
    now: datetime | None = None,
) -> ConnectorRun:
    run = session.get(ConnectorRun, run_id)
    if not run:
        raise DomainError("The connector run was not found.", 404, "not_found")
    finished = _aware(now or utcnow())
    run.status = "failed"
    run.error_detail = detail[:2000]
    run.failed_count = max(1, run.failed_count)
    run.finished_at = finished
    if run.started_at:
        run.duration_ms = max(0, int((finished - _aware(run.started_at)).total_seconds() * 1000))
    return run


def _events_for_run(session: Session, run: ConnectorRun) -> list[RegulatoryEvent]:
    if not run.started_at:
        return []
    candidates = session.scalars(
        select(RegulatoryEvent).where(
            RegulatoryEvent.connector == run.connector,
            RegulatoryEvent.created_at >= run.started_at,
        )
    ).all()
    return [
        event
        for event in candidates
        if (event.evidence_json or {}).get("stream") == run.stream
    ]


def _fan_out(session: Session, run: ConnectorRun, events: list[RegulatoryEvent]) -> int:
    if not events:
        return 0
    mappings = session.scalars(
        select(LegacyDocumentMapping).where(
            LegacyDocumentMapping.work_id.in_({event.work_id for event in events})
        )
    ).all()
    law_by_work: dict[str, set[str]] = {}
    for mapping in mappings:
        law_by_work.setdefault(mapping.work_id, set()).add(mapping.law_id)
    law_ids = {law_id for values in law_by_work.values() for law_id in values}
    watches = (
        session.scalars(
            select(DocumentWatch).where(
                DocumentWatch.law_id.in_(law_ids),
                DocumentWatch.active.is_(True),
            )
        ).all()
        if law_ids
        else []
    )
    watches_by_law: dict[str, list[DocumentWatch]] = {}
    for watch in watches:
        watches_by_law.setdefault(watch.law_id, []).append(watch)
    inserted = 0
    touched: dict[str, list[str]] = {}
    for event in events:
        for law_id in law_by_work.get(event.work_id, set()):
            for watch in watches_by_law.get(law_id, []):
                exists = session.scalar(
                    select(RegulatoryEventState.id).where(
                        RegulatoryEventState.organization_id == watch.organization_id,
                        RegulatoryEventState.event_id == event.id,
                    )
                )
                if not exists:
                    session.add(
                        RegulatoryEventState(
                            organization_id=watch.organization_id,
                            event_id=event.id,
                        )
                    )
                    inserted += 1
                touched.setdefault(watch.organization_id, []).append(event.id)
    for organization_id, event_ids in touched.items():
        state = session.scalar(
            select(FeedState).where(
                FeedState.organization_id == organization_id,
                FeedState.connector == run.connector,
                FeedState.stream == run.stream,
            )
        )
        if not state:
            state = FeedState(
                organization_id=organization_id,
                connector=run.connector,
                stream=run.stream,
            )
            session.add(state)
        state.cursor = event_ids[-1]
        state.values = {
            "last_run_id": run.id,
            "event_ids": list(dict.fromkeys(event_ids))[-100:],
            "unread_added": len(set(event_ids)),
        }
        state.updated_at = utcnow()
    return inserted


def finish_run(
    session: Session,
    run_id: str,
    result: dict,
    *,
    now: datetime | None = None,
) -> ConnectorRun:
    run = session.get(ConnectorRun, run_id)
    if not run:
        raise DomainError("The connector run was not found.", 404, "not_found")
    events = _events_for_run(session, run)
    run.new_count = sum(event.event_type in {"created", "notice_published"} for event in events)
    run.changed_count = sum(event.event_type not in {"created", "notice_published"} for event in events)
    run.output_cursor_json = result.get("next_cursor")
    run.status = result.get("status") or "failed"
    run.error_detail = (result.get("error") or "")[:2000] or None
    page_id = result.get("page_id")
    run.failed_count = (
        int(
            session.scalar(
                select(func.count()).select_from(ConnectorItemError).where(
                    ConnectorItemError.page_id == page_id
                )
            )
            or 0
        )
        if page_id
        else (1 if run.status in {"degraded", "failed"} else 0)
    )
    # Fan-out inserts are idempotent. Keep the earlier count when a worker
    # retries after completing fan-out but before marking the durable job done.
    run.fanout_count = max(run.fanout_count, _fan_out(session, run, events))
    finished = _aware(now or utcnow())
    run.finished_at = finished
    if run.started_at:
        run.duration_ms = max(0, int((finished - _aware(run.started_at)).total_seconds() * 1000))
    return run


def serialize_run(run: ConnectorRun | None) -> dict | None:
    if not run:
        return None
    return {
        "id": run.id,
        "job_id": run.job_id,
        "trigger": run.trigger,
        "status": run.status,
        "input_cursor": run.input_cursor_json,
        "output_cursor": run.output_cursor_json,
        "new": run.new_count,
        "changed": run.changed_count,
        "failed": run.failed_count,
        "fanout": run.fanout_count,
        "duration_ms": run.duration_ms,
        "error": run.error_detail,
        "started_at": _iso(run.started_at),
        "finished_at": _iso(run.finished_at),
    }


def serialize_schedule(
    session: Session,
    schedule: ConnectorSchedule,
    *,
    now: datetime | None = None,
) -> dict:
    now = _aware(now or utcnow())
    state = session.scalar(
        select(ConnectorState).where(
            ConnectorState.connector == schedule.connector,
            ConnectorState.stream == schedule.stream,
        )
    )
    latest = session.scalar(
        select(ConnectorRun)
        .where(ConnectorRun.schedule_id == schedule.id)
        .order_by(ConnectorRun.created_at.desc())
        .limit(1)
    )
    last_success = _aware(state.last_success_at) if state and state.last_success_at else None
    return {
        "id": schedule.id,
        "connector": schedule.connector,
        "stream": schedule.stream,
        "enabled": schedule.enabled,
        "interval_seconds": schedule.interval_seconds,
        "jitter_seconds": schedule.jitter_seconds,
        "window_start": schedule.window_start,
        "window_end": schedule.window_end,
        "timezone": "Europe/Zurich",
        "policy": schedule.policy_json,
        "next_run_at": _iso(schedule.next_run_at),
        "last_enqueued_at": _iso(schedule.last_enqueued_at),
        "health": state.health if state else "unknown",
        "health_message": state.health_message if state else None,
        "cursor": state.cursor_json if state else None,
        "checkpoint": state.page_checkpoint_json if state else {},
        "last_success_at": _iso(last_success),
        "freshness_lag_seconds": int((now - last_success).total_seconds())
        if last_success
        else None,
        "partial_coverage": bool(latest and latest.status == "partial"),
        "last_run": serialize_run(latest),
    }


def schedule_status(session: Session, settings: Settings) -> dict:
    seed_schedules(session)
    schedules = session.scalars(
        select(ConnectorSchedule).order_by(
            ConnectorSchedule.connector,
            ConnectorSchedule.stream,
        )
    ).all()
    return {
        "items": [serialize_schedule(session, item) for item in schedules],
        "pressure": queue_pressure(session, settings),
    }
