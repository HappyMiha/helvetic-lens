"""Read-only source readiness snapshots for explicit topic review."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from .models import (
    ConnectorRun,
    ConnectorSchedule,
    ConnectorState,
    SourcePackDefinition,
    SourcePackSubscription,
)
from .source_capabilities import SOURCE_CAPABILITY_INDEX


def _iso(value: datetime | None) -> str | None:
    return _aware(value).isoformat() if value else None


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def snapshot(session: Session, pack_ids: list[str], *, now: datetime) -> dict:
    # Caller supplies an already validated plan (maximum twenty pack IDs).
    if len(pack_ids) > 20:
        raise ValueError("Topic coverage accepts at most twenty source packs.")
    definitions = list(session.execute(select(
        SourcePackDefinition.id, SourcePackDefinition.name_json, SourcePackDefinition.filters_json,
    ).where(SourcePackDefinition.id.in_(pack_ids), SourcePackDefinition.active.is_(True))
      .order_by(SourcePackDefinition.position, SourcePackDefinition.id)))
    subscriptions = {row.pack_id: row for row in session.execute(select(
        SourcePackSubscription.pack_id, SourcePackSubscription.enabled, SourcePackSubscription.state,
    ).where(SourcePackSubscription.pack_id.in_(pack_ids),
            SourcePackSubscription.organization_id == session.info["organization_id"]))}
    pack_keys = {row.id: {tuple(item) for item in (row.filters_json or {}).get("streams", [])}
                 for row in definitions}
    keys = sorted({key for values in pack_keys.values() for key in values if key in SOURCE_CAPABILITY_INDEX})
    schedule, state, run = ConnectorSchedule, ConnectorState, ConnectorRun
    latest_status = select(run.status).where(run.schedule_id == schedule.id).order_by(
        run.created_at.desc(), run.id.desc()).limit(1).correlate(schedule).scalar_subquery()
    schedules = { (row.connector, row.stream): row for row in session.execute(select(
        schedule.connector, schedule.stream, schedule.enabled, schedule.interval_seconds,
        schedule.jitter_seconds, schedule.window_start, schedule.window_end, schedule.next_run_at,
        latest_status.label("last_run_status"),
    ).where(tuple_(schedule.connector, schedule.stream).in_(keys)))} if keys else {}
    states = { (row.connector, row.stream): row for row in session.execute(select(
        state.connector, state.stream, state.health, state.last_success_at,
    ).where(tuple_(state.connector, state.stream).in_(keys)))} if keys else {}
    items = []
    for definition in definitions:
        subscription = subscriptions.get(definition.id)
        streams = []
        for key in sorted(pack_keys[definition.id]):
            capability = SOURCE_CAPABILITY_INDEX.get(key)
            if not capability:
                continue
            configured, recorded = schedules.get(key), states.get(key)
            streams.append({
                "connector": key[0], "stream": key[1], "publisher": capability.publisher,
                "localized_copy": capability.localized_copy,
                "catalogue_state": capability.catalogue_state,
                "configured": configured is not None,
                "enabled": bool(configured and configured.enabled),
                "interval_seconds": configured.interval_seconds if configured else None,
                "jitter_seconds": configured.jitter_seconds if configured else None,
                "window_start": configured.window_start if configured else None,
                "window_end": configured.window_end if configured else None,
                "next_run_at": _iso(configured.next_run_at) if configured else None,
                "next_attempt_past_due": bool(configured and configured.enabled
                    and configured.next_run_at and _aware(configured.next_run_at) < _aware(now)),
                "last_reported_health": recorded.health if recorded else "unknown",
                "last_success_at": _iso(recorded.last_success_at) if recorded else None,
                "last_run_status": configured.last_run_status if configured else None,
            })
        items.append({
            "id": definition.id, "name": definition.name_json,
            "subscription_enabled": bool(subscription and subscription.enabled),
            "subscription_state": subscription.state if subscription else "inactive",
            "unknown_stream_count": len(pack_keys[definition.id]) - len(streams),
            "streams": streams,
        })
    return {"captured_at": _iso(now), "timezone": "Europe/Zurich", "items": items,
            "enabled_pack_count": sum(item["subscription_enabled"] for item in items),
            "scope": "selected_packs_saved_operational_state", "ai_calls": 0}
