"""Sample actual source metadata; gaps are not reconstructed or interpolated."""
import hashlib
import json
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete, select, tuple_

from .config import DomainError
from .models import MonitoringOperationalSample as Sample
from .monitoring_source_attention import administrator, binding
from .monitoring_source_operations import age, snapshot, stamp, utc

CHANNELS = ("pollen", "river", "air", "warnings", "commute:trip_updates",
    "commute:service_alerts", "traffic", "tenders", "auctions", "ip")
SAMPLE_SECONDS = 300
RETENTION_DAYS = 30
MAX_ROWS = RETENTION_DAYS * 86400 // SAMPLE_SECONDS + 1
METRICS = {"latest_acquisition_age": "latest_success_at",
    "oldest_acquisition_age": "oldest_success_at", "publication_age": "source_published_at"}


def clock(now=None):
    now = now or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Use an aware sampling clock")
    return now.astimezone(UTC)


def bucket(now):
    return datetime.fromtimestamp(int(now.timestamp()) // SAMPLE_SECONDS * SAMPLE_SECONDS, UTC)


def capture(database, settings, *, now=None):
    now = clock(now)
    slot = bucket(now)
    with database.session() as session:
        old = select(Sample.channel, Sample.bucket_at).where(
            Sample.bucket_at < slot - timedelta(days=RETENTION_DAYS)).order_by(Sample.bucket_at, Sample.channel).limit(4000)
        removed = len(list(session.scalars(delete(Sample).where(
            tuple_(Sample.channel, Sample.bucket_at).in_(old)).returning(Sample.channel))))
        existing = set(session.scalars(select(Sample.channel).where(Sample.bucket_at == slot)))
        if existing >= set(CHANNELS):
            session.commit()
            return {"sampled": 0, "removed": removed}
        data = snapshot(session, settings, now=now)
        values = []
        for source in data["items"]:
            for channel in source.get("channels") or [source]:
                key = source["id"] + ":" + channel["id"] if source["id"] == "commute" else source["id"]
                if key not in CHANNELS:
                    raise ValueError("Unregistered source history channel")
                acquisition = channel["acquisition"]
                # Whitelist metadata. Never store raw errors, source JSON, URLs,
                # permission documents, credentials or private monitor content.
                metadata = {name: acquisition[name] for name in (
                    "state", "record_count", "never_succeeded_count", "error_count", "invalid_clock",
                    "oldest_success_at", "latest_success_at", "source_published_at", "next_request_at")}
                metadata.update(section_enabled=source["section_enabled"], collector=channel["collector"],
                    access=channel["access"]["state"], expires_at=channel["access"]["expires_at"],
                    binding=hashlib.sha256(json.dumps(binding(session, settings, source["id"], channel["id"]),
                        sort_keys=True, default=str).encode()).hexdigest())
                values.append({"channel": key, "bucket_at": slot, "recorded_at": now, "values": metadata})
        if {row["channel"] for row in values} != set(CHANNELS):
            raise ValueError("Incomplete source history inventory")
        if session.bind.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        inserted = list(session.scalars(insert(Sample).values(values).on_conflict_do_nothing(
            index_elements=[Sample.channel, Sample.bucket_at]).returning(Sample.channel)))
        session.commit()
        return {"sampled": len(inserted), "removed": removed}


def history(session, user_id, channel, days, *, now=None):
    now = clock(now)
    administrator(session, user_id)
    if channel not in CHANNELS or days not in (1, 7, 30):
        raise DomainError("Select a supported source and history period.", 422, "source_history_selection")
    start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=days * 24 - 1)
    rows = list(session.scalars(select(Sample).where(Sample.channel == channel,
        Sample.bucket_at >= start, Sample.bucket_at <= bucket(now), Sample.recorded_at <= now)
        .order_by(Sample.bucket_at).limit(MAX_ROWS)))
    grouped = {}
    for row in rows:
        hour = utc(row.bucket_at).replace(minute=0, second=0, microsecond=0)
        grouped.setdefault(hour, []).append(row)
    points, previous_binding = [], None
    for index in range(days * 24):
        at = start + timedelta(hours=index)
        members = grouped.get(at, [])
        expected = min(12, int((bucket(now) - at).total_seconds()) // SAMPLE_SECONDS + 1)
        counts, access_states, collector_states, bindings = {}, {}, {}, set()
        for row in members:
            value = row.values
            counts[value["state"]] = counts.get(value["state"], 0) + 1
            access_states[value["access"]] = access_states.get(value["access"], 0) + 1
            collector_states[value["collector"]] = collector_states.get(value["collector"], 0) + 1
            bindings.add(value["binding"])
        changed = len(bindings) > 1 or bool(members and previous_binding is not None and
            members[0].values["binding"] != previous_binding)
        if members:
            previous_binding = members[-1].values["binding"]
        metrics = {}
        for metric, name in METRICS.items():
            measured = [age(datetime.fromisoformat(row.values[name]), utc(row.recorded_at))
                for row in members if row.values[name] is not None]
            known = [value for value in measured if value is not None]
            metrics[metric] = {"min_seconds": min(known) if known else None,
                "max_seconds": max(known) if known else None, "known_samples": len(known)}
        latest = members[-1].values if members else None
        points.append({"at": stamp(at), "samples": len(members), "expected_samples": expected,
            "missing_samples": max(0, expected - len(members)), "states": counts,
            "access_states": access_states, "collector_states": collector_states,
            "disabled_samples": sum(not row.values["section_enabled"] for row in members),
            "binding_changed": changed, "metrics": metrics,
            "last_state": {key: latest[key] for key in ("state", "access", "collector", "section_enabled")}
                if latest else None})
    return {"channel": channel, "days": days, "checked_at": stamp(now), "from": stamp(start),
        "sample_seconds": SAMPLE_SECONDS, "retention_days": RETENTION_DAYS,
        "first_sample_at": stamp(rows[0].recorded_at) if rows else None,
        "last_sample_at": stamp(rows[-1].recorded_at) if rows else None, "points": points}


def source_history_router(service):
    def identity(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        actor = getattr(request.state, "identity", None)
        if actor is None:
            raise DomainError("Sign in to inspect source history.", 401, "authentication_required")
        if not actor.platform_admin:
            raise DomainError("Platform administrator access is required.", 403, "platform_admin_required")
        return actor

    router = APIRouter(prefix="/api/admin/monitoring-sources/history")

    @router.get("")
    def read(channel: str = "pollen", days: int = 1, actor=Depends(identity)):
        with service.db.session() as session:
            return history(session, actor.user_id, channel, days)

    return router
