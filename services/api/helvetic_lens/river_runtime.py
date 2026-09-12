"""Private C6 lifecycle and deterministic web developments, without email opt-in."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, update

from . import jobs
from .config import DomainError
from .models import Job
from .monitoring_subjects import _actor, _savepoint
from .river_contracts import RiverConfiguration, utc
from .river_models import RiverChange, RiverMeasurement, RiverMonitor, RiverRevision, RiverSourceCache
from .river_sources import catalogue, digest


def owned(session, user_id, monitor_id, *, write=False):
    organization = _actor(session, user_id, write=write)
    row = session.scalar(select(RiverMonitor).where(RiverMonitor.id == monitor_id,
        RiverMonitor.organization_id == organization, RiverMonitor.owner_user_id == user_id).with_for_update())
    if row is None:
        raise DomainError("River / Lake monitor not found.", 404, "river_not_found")
    return row


def view(row):
    state = deepcopy(row.state)
    health = row.health
    for coverage in state.get("coverage", {}).values():
        if coverage["status"] == "current" and not fresh(coverage["sample"], datetime.now(UTC)):
            coverage["status"] = "stale"
            health = "partial_unknown"
    return {"id": row.id, "configuration": deepcopy(row.configuration), "revision": row.revision,
            "version": row.version, "status": row.status, "health": health, "state": state,
            "last_poll_at": utc(row.last_poll_at).isoformat() if row.last_poll_at else None,
            "delivery": "private_web", "email_enabled": False}


def station(session, station_id):
    for row in catalogue(session)["stations"]:
        if row["id"] == station_id:
            return row
    raise DomainError("Choose an available official station.", 422, "river_station_unavailable")


def samples(session, station_id, *, start=None):
    statement = select(RiverMeasurement).where(RiverMeasurement.station_id == station_id)
    if start:
        statement = statement.where(RiverMeasurement.measured_at >= start)
    rows = session.scalars(statement.order_by(RiverMeasurement.measured_at, RiverMeasurement.id))
    return [deepcopy(row.evidence) for row in rows]


def fresh(sample, now):
    return sample is not None and -timedelta(minutes=5) <= now - utc(sample["timestamp"]) <= timedelta(minutes=60)


def preview(session, configuration, now):
    config = RiverConfiguration.model_validate(configuration)
    selected = station(session, config.station_id)
    rows = samples(session, config.station_id, start=now - timedelta(hours=49))
    latest = {row["metric"]: row for row in rows}
    coverage = {}
    for metric in [*config.metrics, *(["danger"] if config.official_danger else [])]:
        sample = latest.get(metric)
        cache = session.get(RiverSourceCache, "danger" if metric == "danger" else config.station_id)
        ready = fresh(sample, now) and cache is not None and not cache.error
        coverage[metric] = {"status": "current" if ready else "stale" if sample else "unknown", "sample": sample}
    return {"station": selected, "coverage": coverage, "start_available": any(c["status"] == "current" for c in coverage.values()),
            "delivery": "private_web", "history_days": 30, "recovery_hours": 12,
            "warning_scope": "official_station_state_not_regional_forecast", "configuration": config.model_dump(mode="json")}


def create(session, user_id, configuration, request_key):
    organization = _actor(session, user_id, write=True)
    config = RiverConfiguration.model_validate(configuration).model_dump(mode="json")
    station(session, config["station_id"])
    hashed = digest(config)
    previous = session.scalar(select(RiverMonitor).where(RiverMonitor.organization_id == organization,
        RiverMonitor.owner_user_id == user_id, RiverMonitor.request_key == request_key))
    if previous:
        if previous.request_hash != hashed:
            raise DomainError("This save request already has a different configuration.", 409, "river_request_conflict")
        return view(previous)
    count = session.scalar(select(func.count()).select_from(RiverMonitor).where(RiverMonitor.owner_user_id == user_id))
    if count >= 50:
        raise DomainError("Remove an unused monitor before adding another.", 409, "river_monitor_limit")
    from sqlalchemy.exc import IntegrityError
    try:
        with _savepoint(session):
            row = RiverMonitor(organization_id=organization, owner_user_id=user_id, request_key=request_key,
                request_hash=hashed, configuration=config, revision=1, version=1, state={}, status="draft", health="waiting")
            session.add(row)
            session.flush()
            session.add(RiverRevision(organization_id=organization, monitor_id=row.id, revision=1, configuration=config))
            session.flush()
    except IntegrityError:
        previous = session.scalar(select(RiverMonitor).where(RiverMonitor.organization_id == organization,
            RiverMonitor.owner_user_id == user_id, RiverMonitor.request_key == request_key))
        if previous and previous.request_hash == hashed:
            return view(previous)
        raise DomainError("The save request conflicted. Reload the monitor list.", 409, "river_request_conflict") from None
    return view(row)


def expected(row, version):
    if row.version != version:
        raise DomainError("This monitor changed. Reload it before continuing.", 409, "river_version_conflict")


def edit(session, user_id, monitor_id, version, configuration):
    row = owned(session, user_id, monitor_id, write=True)
    expected(row, version)
    if row.status not in {"draft", "paused"}:
        raise DomainError("Pause this monitor before editing it.", 409, "river_pause_before_edit")
    config = RiverConfiguration.model_validate(configuration).model_dump(mode="json")
    station(session, config["station_id"])
    row.configuration, row.revision, row.version, row.state = config, row.revision + 1, row.version + 1, {}
    row.health = "waiting"
    session.add(RiverRevision(organization_id=row.organization_id, monitor_id=row.id, revision=row.revision, configuration=config))
    session.flush()
    return view(row)


def enqueue(session, row, now):
    pending = session.scalar(select(Job.id).where(Job.target_type == "river_monitor", Job.target_id == row.id,
        Job.state.in_({"queued", "dispatched", "running", "retrying"})).limit(1))
    if pending:
        return False
    _, reused = jobs.enqueue(session, job_type="river_refresh", target_type="river_monitor", target_id=row.id,
        queue="ingest", idempotency_key=f"river:{row.id}:{row.version}:{int(now.timestamp()) // 600}",
        payload={"version": row.version}, max_attempts=3)
    return not reused


def command(session, user_id, monitor_id, version, action, now):
    row = owned(session, user_id, monitor_id, write=True)
    expected(row, version)
    transitions = {"start": ({"draft"}, "active"), "pause": ({"active"}, "paused"),
                   "resume": ({"paused"}, "active"), "archive": ({"draft", "active", "paused"}, "archived")}
    allowed, target = transitions[action]
    if row.status not in allowed:
        raise DomainError("This action is unavailable in the current state.", 409, "river_state_conflict")
    if target == "active" and not preview(session, row.configuration, now)["start_available"]:
        raise DomainError("Preview current official data before starting monitoring.", 409, "river_source_not_ready")
    row.status, row.version = target, row.version + 1
    if target == "active":
        row.next_poll_at = now
        enqueue(session, row, now)
    else:
        session.execute(update(Job).where(Job.target_type == "river_monitor", Job.target_id == row.id,
            Job.state.in_({"queued", "dispatched", "running", "retrying"})).values(cancel_requested=True))
    session.flush()
    return view(row)


def remove(session, user_id, monitor_id, version):
    row = owned(session, user_id, monitor_id, write=True)
    expected(row, version)
    session.execute(update(Job).where(Job.target_type == "river_monitor", Job.target_id == row.id,
        Job.state.in_({"queued", "dispatched", "running", "retrying"})).values(cancel_requested=True))
    session.delete(row)
    session.flush()


def _rule_value(rule, sample, timeline):
    if rule.kind == "absolute":
        return Decimal(sample["value"]), None
    target = utc(sample["timestamp"]) - timedelta(minutes=rule.window_minutes)
    start = next((row for row in timeline if utc(row["timestamp"]) == target), None)
    if start is None or start["unit"] != sample["unit"] or start["datum"] != sample["datum"] or start["aggregation"] != sample["aggregation"]:
        return None, None
    window = [row for row in timeline if target <= utc(row["timestamp"]) <= utc(sample["timestamp"])]
    if any(utc(right["timestamp"]) - utc(left["timestamp"]) > timedelta(minutes=10)
           or right["datum"] != sample["datum"] or right["unit"] != sample["unit"] or right["aggregation"] != sample["aggregation"]
           for left, right in zip(window, window[1:], strict=False)):
        return None, None  # Never interpolate or bridge an incomplete change window.
    change = Decimal(sample["value"]) - Decimal(start["value"])
    return change * (100 if rule.unit == "cm" else 1), start


def evaluate(session, row, now):
    config = RiverConfiguration.model_validate(row.configuration)
    source_rows = samples(session, config.station_id, start=now - timedelta(hours=49))
    state = deepcopy(row.state or {})
    conditions = state.setdefault("conditions", {})
    sequence = session.scalar(select(func.max(RiverChange.sequence)).where(RiverChange.monitor_id == row.id)) or 0
    current = preview(session, row.configuration, now)
    row.health = "ready" if all(c["status"] == "current" for c in current["coverage"].values()) else "partial_unknown"
    state["coverage"] = current["coverage"]
    definitions = [(digest(rule.model_dump(mode="json")), rule.metric, rule) for rule in config.rules]
    if config.official_danger:
        definitions.append(("official-danger", "danger", None))
    for key, metric, rule in definitions:
        previous = conditions.setdefault(key, {"status": "unknown", "last_known": None, "watermark": None})
        timeline = [sample for sample in source_rows if sample["metric"] == metric]
        fresh_source = current["coverage"][metric]["status"] == "current"
        if not timeline or not fresh_source:
            previous["status"] = "unknown"
            continue
        pending = [sample for sample in timeline if previous["watermark"] is None or utc(sample["timestamp"]) > utc(previous["watermark"])]
        if previous["watermark"] is None:
            pending = timeline[-1:]  # Starting is not a replay of past alerts.
        for sample in pending:
            if previous["watermark"] and utc(sample["timestamp"]) - utc(previous["watermark"]) > timedelta(minutes=20):
                state["last_gap"] = {"from": previous["watermark"], "to": sample["timestamp"], "recovery_limit_hours": 12}
            value, baseline = (Decimal(sample["value"]), None) if rule is None else _rule_value(rule, sample, timeline)
            previous["watermark"] = sample["timestamp"]
            if value is None:
                previous["status"] = "unknown"
                continue
            observed = int(value) if rule is None else int(value > rule.threshold)
            before = previous["last_known"]
            changed = before != observed and (before is not None or observed > (1 if rule is None else 0))
            previous["status"], previous["last_known"] = "current", observed
            previous["value"] = str(value)
            if not changed:
                continue
            sequence += 1
            kind = ("danger_escalation" if before is None or observed > before else "danger_downgrade") if rule is None else ("threshold_crossed" if observed else "threshold_cleared")
            development = digest([row.id, row.revision, key])
            event = RiverChange(organization_id=row.organization_id, monitor_id=row.id, development_id=development,
                sequence=sequence, revision=row.revision, kind=kind, priority=1 if kind == "danger_escalation" else 2,
                evidence={"sample": sample, "baseline": baseline, "rule": rule.model_dump(mode="json") if rule else None,
                          "previous_state": before, "current_state": observed, "evaluated_value": str(value),
                          "station_id": config.station_id, "recovered": not fresh(sample, now)}, review_version=0)
            session.add(event)
            session.flush()
            previous["latest_change_id"] = event.id
    if any(condition["status"] == "unknown" for condition in conditions.values()):
        row.health = "partial_unknown"
    row.state, row.last_poll_at, row.next_poll_at = state, now, now + timedelta(minutes=10)
    session.flush()
    return {"status": row.health, "sequence": sequence}


def change_view(row):
    return {"id": row.id, "development_id": row.development_id, "sequence": row.sequence,
            "revision": row.revision, "kind": row.kind, "priority": row.priority, "evidence": deepcopy(row.evidence),
            "decision": row.decision, "review_version": row.review_version, "created_at": utc(row.created_at).isoformat()}


def review(session, user_id, monitor_id, change_id, expected_version, decision):
    monitor = owned(session, user_id, monitor_id, write=True)
    change = session.scalar(select(RiverChange).where(RiverChange.monitor_id == monitor.id, RiverChange.id == change_id).with_for_update())
    if change is None:
        raise DomainError("Change not found.", 404, "river_not_found")
    if change.review_version != expected_version:
        raise DomainError("This review changed. Reload before reviewing.", 409, "river_version_conflict")
    newer = session.scalar(select(RiverChange.id).where(RiverChange.development_id == change.development_id,
        RiverChange.sequence > change.sequence).limit(1))
    if newer:
        raise DomainError("A newer development needs review.", 409, "river_newer_change")
    change.decision, change.review_version = decision, change.review_version + 1
    return change_view(change)
