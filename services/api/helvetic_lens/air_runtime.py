"""Private C7 lifecycle and deterministic web developments, without email opt-in."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, update

from . import jobs
from .air_contracts import AirConfiguration, utc
from .air_models import AirChange, AirMeasurement, AirMonitor, AirRevision, AirSourceCache
from .air_sources import catalogue, digest
from .config import DomainError
from .models import Job
from .monitoring_subjects import _actor, _savepoint


def owned(session, user_id, monitor_id, *, write=False):
    organization = _actor(session, user_id, write=write)
    row = session.scalar(
        select(AirMonitor)
        .where(
            AirMonitor.id == monitor_id,
            AirMonitor.organization_id == organization,
            AirMonitor.owner_user_id == user_id,
        )
        .with_for_update()
    )
    if row is None:
        raise DomainError("Air Quality monitor not found.", 404, "air_not_found")
    return row


def view(row):
    state = deepcopy(row.state)
    health = row.health
    for coverage in state.get("coverage", {}).values():
        if coverage["status"] == "current" and not fresh(coverage["sample"], datetime.now(UTC)):
            coverage["status"] = "stale"
            health = "partial_unknown"
    return {
        "id": row.id,
        "configuration": deepcopy(row.configuration),
        "revision": row.revision,
        "version": row.version,
        "status": row.status,
        "health": health,
        "state": state,
        "last_poll_at": utc(row.last_poll_at).isoformat() if row.last_poll_at else None,
        "delivery": "private_web",
        "email_enabled": False,
    }


def station(session, station_id):
    for row in catalogue(session)["stations"]:
        if row["id"] == station_id:
            return row
    raise DomainError("Choose an available official station.", 422, "air_station_unavailable")


def samples(session, station_id, *, start=None):
    statement = select(AirMeasurement).where(AirMeasurement.station_id == station_id)
    if start:
        statement = statement.where(AirMeasurement.measured_at >= start)
    rows = session.scalars(statement.order_by(AirMeasurement.measured_at, AirMeasurement.id))
    return [deepcopy(row.evidence) for row in rows]


def fresh(sample, now):
    return sample is not None and timedelta(0) <= now - utc(sample["timestamp"]) <= timedelta(hours=6)


def series(rows, metric, period):
    timeline = [s for s in rows if s["metric"] == metric]
    if period == "hourly_mean":
        return timeline
    by_time = {utc(s["timestamp"]): s for s in timeline}
    derived = []
    for sample in timeline:
        at = utc(sample["timestamp"])
        window = [by_time.get(at - timedelta(hours=i)) for i in range(23, -1, -1)]
        result = deepcopy(sample)
        result["period"], result["method"] = "rolling_24h_mean", "helvetic-24-consecutive-hourly-v1"
        result["derived"] = True
        result["input_versions"] = [s["version_id"] if s else None for s in window]
        result["value_hash"] = digest(result["input_versions"])
        complete = all(
            s
            and s["value"] is not None
            and s["quality"] == "provisional"
            and s["unit"] == sample["unit"]
            and s["method"] == sample["method"]
            for s in window
        )
        result["value"] = (
            format(sum(Decimal(s["value"]) for s in window) / Decimal(24), ".4f") if complete else None
        )
        result["quality"] = "provisional" if complete else "incomplete_window"
        result["corrected"] = any(s and s.get("corrected") for s in window)
        derived.append(result)
    return derived


def preview(session, configuration, now):
    config = AirConfiguration.model_validate(configuration)
    selected = station(session, config.station_id)
    rows = samples(session, config.station_id, start=now - timedelta(hours=96))
    # Empty rows beyond the latest populated hour are provider placeholders.
    # At that common hour, individual missing pollutants stay missing.
    cutoff = max((s["timestamp"] for s in rows if s["value"] is not None), default=None)
    coverage = {}
    definitions = {(m, "hourly_mean") for m in config.metrics} | {(r.metric, r.period) for r in config.rules}
    cache = session.get(AirSourceCache, config.station_id)
    if cache and cache.data.get("latest_observation_at"):
        cutoff = max(cutoff or "", cache.data["latest_observation_at"])
    for metric, period in sorted(definitions):
        timeline = series(rows, metric, period)
        sample = next((s for s in reversed(timeline) if s["timestamp"] == cutoff), None)
        status = "unknown"
        if sample and sample["value"] is not None:
            status = "current" if fresh(sample, now) and cache is not None and not cache.error else "stale"
        coverage[f"{metric}:{period}"] = {"status": status, "sample": sample}
    return {
        "station": selected,
        "coverage": coverage,
        "start_available": any(c["status"] == "current" for c in coverage.values()),
        "delivery": "private_web",
        "history_days": 30,
        "recovery_hours": 72,
        "warning_scope": "station_observation_not_personal_health_advice",
        "configuration": config.model_dump(mode="json"),
    }


def create(session, user_id, configuration, request_key):
    organization = _actor(session, user_id, write=True)
    config = AirConfiguration.model_validate(configuration).model_dump(mode="json")
    station(session, config["station_id"])
    hashed = digest(config)
    previous = session.scalar(
        select(AirMonitor).where(
            AirMonitor.organization_id == organization,
            AirMonitor.owner_user_id == user_id,
            AirMonitor.request_key == request_key,
        )
    )
    if previous:
        if previous.request_hash != hashed:
            raise DomainError(
                "This save request already has a different configuration.", 409, "air_request_conflict"
            )
        return view(previous)
    count = session.scalar(
        select(func.count()).select_from(AirMonitor).where(AirMonitor.owner_user_id == user_id)
    )
    if count >= 50:
        raise DomainError("Remove an unused monitor before adding another.", 409, "air_monitor_limit")
    from sqlalchemy.exc import IntegrityError

    try:
        with _savepoint(session):
            row = AirMonitor(
                organization_id=organization,
                owner_user_id=user_id,
                request_key=request_key,
                request_hash=hashed,
                configuration=config,
                revision=1,
                version=1,
                state={},
                status="draft",
                health="waiting",
            )
            session.add(row)
            session.flush()
            session.add(
                AirRevision(organization_id=organization, monitor_id=row.id, revision=1, configuration=config)
            )
            session.flush()
    except IntegrityError:
        previous = session.scalar(
            select(AirMonitor).where(
                AirMonitor.organization_id == organization,
                AirMonitor.owner_user_id == user_id,
                AirMonitor.request_key == request_key,
            )
        )
        if previous and previous.request_hash == hashed:
            return view(previous)
        raise DomainError(
            "The save request conflicted. Reload the monitor list.", 409, "air_request_conflict"
        ) from None
    return view(row)


def expected(row, version):
    if row.version != version:
        raise DomainError("This monitor changed. Reload it before continuing.", 409, "air_version_conflict")


def edit(session, user_id, monitor_id, version, configuration):
    row = owned(session, user_id, monitor_id, write=True)
    expected(row, version)
    if row.status not in {"draft", "paused"}:
        raise DomainError("Pause this monitor before editing it.", 409, "air_pause_before_edit")
    config = AirConfiguration.model_validate(configuration).model_dump(mode="json")
    station(session, config["station_id"])
    row.configuration, row.revision, row.version, row.state = config, row.revision + 1, row.version + 1, {}
    row.health = "waiting"
    session.add(
        AirRevision(
            organization_id=row.organization_id,
            monitor_id=row.id,
            revision=row.revision,
            configuration=config,
        )
    )
    session.flush()
    return view(row)


def enqueue(session, row, now):
    pending = session.scalar(
        select(Job.id)
        .where(
            Job.target_type == "air_monitor",
            Job.target_id == row.id,
            Job.state.in_({"queued", "dispatched", "running", "retrying"}),
        )
        .limit(1)
    )
    if pending:
        return False
    _, reused = jobs.enqueue(
        session,
        job_type="air_refresh",
        target_type="air_monitor",
        target_id=row.id,
        queue="ingest",
        idempotency_key=f"air:{row.id}:{row.version}:{int(now.timestamp()) // 3600}",
        payload={"version": row.version},
        max_attempts=3,
    )
    return not reused


def command(session, user_id, monitor_id, version, action, now):
    row = owned(session, user_id, monitor_id, write=True)
    expected(row, version)
    transitions = {
        "start": ({"draft"}, "active"),
        "pause": ({"active"}, "paused"),
        "resume": ({"paused"}, "active"),
        "archive": ({"draft", "active", "paused"}, "archived"),
    }
    allowed, target = transitions[action]
    if row.status not in allowed:
        raise DomainError("This action is unavailable in the current state.", 409, "air_state_conflict")
    if target == "active" and not preview(session, row.configuration, now)["start_available"]:
        raise DomainError(
            "Preview current official data before starting monitoring.", 409, "air_source_not_ready"
        )
    row.status, row.version = target, row.version + 1
    if target == "active":
        row.next_poll_at = now
        enqueue(session, row, now)
    else:
        session.execute(
            update(Job)
            .where(
                Job.target_type == "air_monitor",
                Job.target_id == row.id,
                Job.state.in_({"queued", "dispatched", "running", "retrying"}),
            )
            .values(cancel_requested=True)
        )
    session.flush()
    return view(row)


def remove(session, user_id, monitor_id, version):
    row = owned(session, user_id, monitor_id, write=True)
    expected(row, version)
    session.execute(
        update(Job)
        .where(
            Job.target_type == "air_monitor",
            Job.target_id == row.id,
            Job.state.in_({"queued", "dispatched", "running", "retrying"}),
        )
        .values(cancel_requested=True)
    )
    session.delete(row)
    session.flush()


def evaluate(session, row, now):
    config = AirConfiguration.model_validate(row.configuration)
    source_rows = samples(session, config.station_id, start=now - timedelta(hours=96))
    state = deepcopy(row.state or {})
    conditions = state.setdefault("conditions", {})
    sequence = session.scalar(select(func.max(AirChange.sequence)).where(AirChange.monitor_id == row.id)) or 0
    current = preview(session, row.configuration, now)
    state["coverage"] = current["coverage"]
    row.health = (
        "ready" if all(c["status"] == "current" for c in current["coverage"].values()) else "partial_unknown"
    )
    for rule in config.rules:
        key = digest(rule.model_dump(mode="json"))
        prior = conditions.setdefault(
            key,
            {
                "status": "unknown",
                "observed": None,
                "reported": None,
                "watermark": None,
                "last_hash": None,
                "last_alert_at": None,
                "sample": None,
            },
        )
        if rule.metric in config.muted_metrics:
            prior["status"] = "muted"
            continue
        coverage = current["coverage"][f"{rule.metric}:{rule.period}"]
        if coverage["status"] != "current":
            prior["status"] = "unknown"
            continue
        timeline = series(source_rows, rule.metric, rule.period)
        cutoff = coverage["sample"]["timestamp"]
        timeline = [s for s in timeline if s["timestamp"] <= cutoff]
        pending = [
            s
            for s in timeline
            if utc(s["timestamp"]) >= now - timedelta(hours=72)
            and (prior["watermark"] is None or utc(s["timestamp"]) > utc(prior["watermark"]))
        ]
        if prior["watermark"] is None:
            pending = timeline[-1:]
        elif not pending and timeline and timeline[-1]["value_hash"] != prior["last_hash"]:
            pending = timeline[-1:]  # Re-evaluate corrected current values and corrected 24h inputs.
        for sample in pending:
            if prior["watermark"] and utc(sample["timestamp"]) - utc(prior["watermark"]) > timedelta(hours=1):
                state["last_gap"] = {
                    "from": prior["watermark"],
                    "to": sample["timestamp"],
                    "recovery_limit_hours": 72,
                }
            correction = (
                prior["watermark"] == sample["timestamp"] and prior["last_hash"] != sample["value_hash"]
            )
            prior["watermark"], prior["last_hash"] = sample["timestamp"], sample["value_hash"]
            if sample["value"] is None:
                prior["status"] = "unknown"
                continue
            value = Decimal(sample["value"])
            observed = int(value > rule.threshold - (rule.hysteresis if prior["observed"] else 0))
            before, baseline = prior["reported"], prior["sample"]
            prior["observed"], prior["status"] = observed, "current"
            prior["sample"] = deepcopy(sample)
            changed = observed != before and (before is not None or observed == 1)
            # Improvements are never held back by cooldown. A new deterioration waits
            # until a later source hour confirms it beyond the configured cooldown.
            cooling = (
                observed == 1
                and not correction
                and prior["last_alert_at"] is not None
                and utc(sample["timestamp"]) - utc(prior["last_alert_at"])
                < timedelta(hours=rule.cooldown_hours)
            )
            if not changed or cooling:
                if before is None and observed == 0:
                    prior["reported"] = 0
                continue
            sequence += 1
            prior["reported"] = observed
            if observed:
                prior["last_alert_at"] = sample["timestamp"]
            event = AirChange(
                organization_id=row.organization_id,
                monitor_id=row.id,
                development_id=digest([row.id, key]),
                sequence=sequence,
                revision=row.revision,
                kind="threshold_crossed" if observed else "threshold_cleared",
                priority=2,
                evidence={
                    "sample": sample,
                    "baseline": baseline,
                    "rule": rule.model_dump(mode="json"),
                    "previous_state": before,
                    "current_state": observed,
                    "evaluated_value": str(value),
                    "station_id": config.station_id,
                    "monitor_name": config.name,
                    "reason": "selected_station_pollutant_and_period",
                    "corrected": correction or sample.get("corrected", False),
                    "recovered": not fresh(sample, now),
                },
                review_version=0,
            )
            session.add(event)
            session.flush()
            prior["latest_change_id"] = event.id
    if any(c["status"] == "unknown" for c in conditions.values()):
        row.health = "partial_unknown"
    row.state, row.last_poll_at, row.next_poll_at = state, now, now + timedelta(hours=1)
    session.flush()
    return {"status": row.health, "sequence": sequence}


def change_view(row):
    return {
        "id": row.id,
        "development_id": row.development_id,
        "sequence": row.sequence,
        "revision": row.revision,
        "kind": row.kind,
        "priority": row.priority,
        "evidence": deepcopy(row.evidence),
        "decision": row.decision,
        "review_version": row.review_version,
        "created_at": utc(row.created_at).isoformat(),
    }


def mute(session, user_id, monitor_id, version, metric, muted, now):
    row = owned(session, user_id, monitor_id, write=True)
    expected(row, version)
    if row.status == "archived" or metric not in row.configuration["metrics"]:
        raise DomainError("Choose a selected pollutant on a current monitor.", 409, "air_state_conflict")
    config = deepcopy(row.configuration)
    selected = set(config["muted_metrics"])
    selected.add(metric) if muted else selected.discard(metric)
    config["muted_metrics"] = sorted(selected)
    if config == row.configuration:
        return view(row)
    row.configuration, row.revision, row.version = config, row.revision + 1, row.version + 1
    state = deepcopy(row.state)
    for rule in config["rules"]:
        if rule["metric"] == metric:
            prior = state.get("conditions", {}).get(digest(rule))
            if prior:
                prior["status"], prior["watermark"] = "muted" if muted else "unknown", None
    row.state, row.next_poll_at = state, now
    session.add(
        AirRevision(
            organization_id=row.organization_id,
            monitor_id=row.id,
            revision=row.revision,
            configuration=config,
        )
    )
    session.execute(
        update(Job)
        .where(
            Job.target_type == "air_monitor",
            Job.target_id == row.id,
            Job.state.in_({"queued", "dispatched", "running", "retrying"}),
        )
        .values(cancel_requested=True)
    )
    session.flush()
    return view(row)


def review(session, user_id, monitor_id, change_id, expected_version, decision):
    monitor = owned(session, user_id, monitor_id, write=True)
    change = session.scalar(
        select(AirChange)
        .where(AirChange.monitor_id == monitor.id, AirChange.id == change_id)
        .with_for_update()
    )
    if change is None:
        raise DomainError("Change not found.", 404, "air_not_found")
    if change.review_version != expected_version:
        raise DomainError("This review changed. Reload before reviewing.", 409, "air_version_conflict")
    newer = session.scalar(
        select(AirChange.id)
        .where(AirChange.development_id == change.development_id, AirChange.sequence > change.sequence)
        .limit(1)
    )
    if newer:
        raise DomainError("A newer development needs review.", 409, "air_newer_change")
    change.decision, change.review_version = decision, change.review_version + 1
    return change_view(change)
