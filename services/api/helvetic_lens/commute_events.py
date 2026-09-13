"""Atomic transport developments, review signals and consent-bound mail intents."""

import json
from copy import deepcopy
from uuid import UUID

from sqlalchemy import func, select, update

from .commute_catalog import encode_leg, resolve_configuration
from .commute_contracts import CommuteCheckpoint, TransportObservation, digest, evaluate_commute
from .commute_interchanges import require_interchanges
from .commute_models import CommuteDevelopment, CommuteEventVersion, CommuteMonitor, CommuteSignal
from .commute_repository import configuration, owned, positive
from .commute_sources import require_permission, utc
from .config import DomainError
from .transport_feed import TRIPS, project_entity
from .transport_reference import ZURICH

MAX_DEVELOPMENTS = 1000
MAX_VERSIONS = 10_000
MAX_HISTORY_BYTES = 32 * 1024 * 1024
MAX_VERSION_BYTES = 128 * 1024


def _usage(session, monitor):
    return session.execute(select(func.count(CommuteEventVersion.id), func.coalesce(func.sum(CommuteEventVersion.payload_bytes), 0))
        .join(CommuteDevelopment, CommuteDevelopment.id == CommuteEventVersion.development_id)
        .where(CommuteDevelopment.monitor_id == monitor.id,
               CommuteDevelopment.organization_id == monitor.organization_id)).one()


def _json_size(value):
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def process_snapshot(session, monitor, state, permission, snapshot, *, service_day, now):
    """Caller holds the monitor row lock and a transaction/savepoint.

    Candidate, immutable history and mutable checkpoint are written together.
    A process retry evaluates the same checkpoint rather than sending again.
    """
    require_permission(session, permission.id, snapshot.source, now=now)
    config = configuration(monitor.configuration)
    legs = resolve_configuration(session, config, service_day=service_day, static_version=snapshot.feed_version)
    interchanges = require_interchanges(session, config, legs)
    rows = list(session.scalars(select(CommuteDevelopment).where(CommuteDevelopment.monitor_id == monitor.id,
        CommuteDevelopment.organization_id == monitor.organization_id, CommuteDevelopment.configuration_revision == monitor.revision,
        CommuteDevelopment.permission_id == permission.id, CommuteDevelopment.source == snapshot.source,
        CommuteDevelopment.service_day == service_day, CommuteDevelopment.static_version == snapshot.feed_version)))
    previous = {row.entity_key: row for row in rows}
    trips = {(leg.reference.trip_id, leg.reference.service_day) for leg in legs.values()}
    entities = {entity.development_id: entity for entity in snapshot.entities
                if snapshot.source != TRIPS or (entity.trip_id, entity.service_day) in trips}
    changed, signals, usable, degraded = 0, 0, 0, False
    for entity_key in sorted(set(entities) | set(previous)):
        entity, row = entities.get(entity_key), previous.get(entity_key)
        checkpoints, observations, contributions, editions = {}, {}, {}, {}
        for reference_id, leg in legs.items():
            old_checkpoint = (row.checkpoints or {}).get(reference_id) if row else None
            old_observation = (row.observations or {}).get(reference_id) if row else None
            projection = project_entity(snapshot, entity, leg) if entity else None
            observation = projection.observation if projection else None
            if observation is None and old_observation:
                last = TransportObservation.model_validate(old_observation)
                observation = TransportObservation(**{**last.model_dump(), "kind": None, "delay_seconds": None,
                    "confirmed_served_stop_ids": (), "availability": "missing", "observed_at": snapshot.observed_at,
                    "revision_sha256": snapshot.sha256})
            if observation is None:
                continue
            result = evaluate_commute(config, UUID(reference_id), leg, observation, monitor_id=UUID(monitor.id),
                now=now, max_age_seconds=permission.max_age_seconds,
                previous=CommuteCheckpoint.model_validate(old_checkpoint) if old_checkpoint else None,
                paused_on=monitor.paused_on, muted=row.muted if row else False)
            checkpoint = result["checkpoint"]
            if checkpoint is None or result["transition"] in ("rejected", "ignored"):
                if old_checkpoint:
                    checkpoints[reference_id], observations[reference_id] = old_checkpoint, old_observation
                continue
            if row is None and (checkpoint.condition is None or result["transition"] == "irrelevant"):
                continue
            checkpoints[reference_id] = checkpoint.model_dump(mode="json")
            observations[reference_id] = observation.model_dump(mode="json")
            contributions[reference_id] = {key: value for key, value in result.items() if key != "checkpoint"}
            contributions[reference_id].update(condition=checkpoint.condition, availability=checkpoint.availability)
            if projection and projection.observation is None:
                contributions[reference_id]["reason"] = projection.reason
            if projection and projection.header:
                editions[reference_id] = {"header": [list(edition) for edition in projection.header],
                    "description": [list(edition) for edition in projection.description],
                    "active_periods": [[start.isoformat() if start else None, end.isoformat() if end else None]
                                       for start, end in projection.active_periods]}
        if not contributions:
            continue
        for ref, result in contributions.items():
            if legs[ref].arrival > now:
                usable += int(result["availability"] == "present" and result["transition"] != "irrelevant")
                degraded = degraded or result["availability"] != "present"
        if row is None:
            total = session.scalar(select(func.count()).select_from(CommuteDevelopment).where(
                CommuteDevelopment.monitor_id == monitor.id, CommuteDevelopment.organization_id == monitor.organization_id))
            if total >= MAX_DEVELOPMENTS:
                raise DomainError("Commute history capacity is reached.", 409, "commute_storage_limit")
            key = digest({"monitor": monitor.id, "revision": monitor.revision, "source": snapshot.source,
                          "permission": permission.id, "entity": entity_key, "day": service_day.isoformat(),
                          "static": snapshot.feed_version})
            row = CommuteDevelopment(monitor_id=monitor.id, organization_id=monitor.organization_id, key=key,
                configuration_revision=monitor.revision, source=snapshot.source, permission_id=permission.id,
                entity_key=entity_key, service_day=service_day, static_version=snapshot.feed_version)
            session.add(row)
            session.flush()
        summary = {ref: {name: result.get(name) for name in ("condition", "availability", "reason")}
                   for ref, result in contributions.items()}
        current = {"states": summary, "editions": editions}
        previous_current = row.current or {}
        semantic_changed = digest(current) != digest(previous_current)
        deliveries = {result["delivery"] for result in contributions.values()}
        delivery = "immediate" if "immediate" in deliveries else "digest_candidate" if "digest_candidate" in deliveries else "none"
        # Official notice text/validity changes update a notice even when its
        # generic condition stays NOTICE. Timing/consent/mute rules still apply.
        notice_changed = bool(row.sequence and editions and editions != previous_current.get("editions"))
        if notice_changed and config.service_notices and not row.muted and monitor.paused_on != now.astimezone(ZURICH).date():
            relevant = [ref for ref, result in contributions.items() if result["availability"] == "present"
                        and result["condition"] == "notice" and result["transition"] != "irrelevant"]
            if any(checkpoints[ref]["immediate_eligible"] for ref in relevant):
                delivery = "immediate"
            elif relevant and config.outside_window == "digest":
                delivery = "digest_candidate"
        row.checkpoints, row.observations = checkpoints, observations
        row.current, row.updated_at = current, now
        if not semantic_changed and delivery == "none":
            continue
        evidence = {"source": snapshot.source, "feed_sha256": snapshot.sha256,
                    "provider_entity_id": entity.source_id if entity else None,
                    "entity_sha256": entity.sha256 if entity else None,
                    "feed_observed_at": snapshot.observed_at.isoformat(), "recorded_at": now.isoformat(),
                    "static_version": snapshot.feed_version, "service_day": service_day.isoformat(),
                    "configuration_revision": monitor.revision, "current": current,
                    "legs": {reference: encode_leg(legs[reference]) for reference in observations},
                    "observations": observations, "contributions": contributions, "interchanges": interchanges,
                    "evidence_kind": "normalized_source_fields"}
        size = _json_size(evidence)
        count, used = _usage(session, monitor)
        if size > MAX_VERSION_BYTES or count >= MAX_VERSIONS or used + size > MAX_HISTORY_BYTES:
            raise DomainError("Commute history capacity is reached.", 409, "commute_storage_limit")
        row.sequence += 1
        row.version += 1
        session.add(CommuteEventVersion(development_id=row.id, organization_id=monitor.organization_id,
            sequence=row.sequence, evidence=evidence, evidence_hash=digest(evidence), payload_bytes=size, created_at=now))
        created_signal = None
        if delivery != "none":
            priority = "urgent" if any(result.get("priority") == "urgent" for result in contributions.values()) else "normal"
            created_signal = CommuteSignal(development_id=row.id, organization_id=monitor.organization_id,
                sequence=row.sequence, delivery_kind=delivery, priority=priority, created_at=now)
            session.add(created_signal)
            signals += 1
        session.flush()
        if created_signal is not None:
            from .commute_delivery import record_intent
            record_intent(session, monitor, row, created_signal, evidence, now)
            session.flush()
        changed += 1
    return {"changed": changed, "signals": signals, "usable": usable, "degraded": degraded}


def owned_development(session, user_id, development_id, *, now, write=False):
    row = session.scalar(select(CommuteDevelopment).where(CommuteDevelopment.id == development_id)
                         .execution_options(populate_existing=True))
    if row is None:
        raise DomainError("Commute event not found.", 404, "commute_event_not_found")
    monitor = owned(session, user_id, row.monitor_id, write=write)
    if write:
        session.scalar(select(CommuteMonitor).where(CommuteMonitor.id == monitor.id,
            CommuteMonitor.organization_id == monitor.organization_id).with_for_update()
            .execution_options(populate_existing=True))
        session.refresh(row)
    try:
        require_permission(session, row.permission_id, row.source, now=now)
    except DomainError:
        raise DomainError("Commute event source is unavailable.", 404, "commute_event_unavailable") from None
    return monitor, row


def event_view(row, *, now=None, max_age_seconds=None):
    current = deepcopy(row.current)
    if now is not None and max_age_seconds is not None:
        for reference, raw in row.observations.items():
            observation = TransportObservation.model_validate(raw)
            summary = current.get("states", {}).get(reference)
            if summary is None:
                continue
            summary.update(observed_at=observation.observed_at.isoformat(), delay_seconds=observation.delay_seconds)
            if (now - observation.observed_at).total_seconds() > max_age_seconds:
                summary.update(availability="stale", reason="stale_source")
            elif observation.valid_until <= now:
                summary.update(availability="expired", reason="validity_ended")
    return {"id": row.id, "monitor_id": row.monitor_id, "source": row.source, "configuration_revision": row.configuration_revision,
            "service_day": row.service_day.isoformat(), "version": row.version, "sequence": row.sequence,
            "reviewed_sequence": row.reviewed_sequence, "muted": row.muted, "current": current}


def events_page(session, user_id, monitor_id, *, now, limit=20, after_id=None):
    monitor = owned(session, user_id, monitor_id)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise DomainError("Invalid event page size.", 422, "commute_limit_invalid")
    query = select(CommuteDevelopment).where(CommuteDevelopment.monitor_id == monitor.id,
                                           CommuteDevelopment.organization_id == monitor.organization_id)
    if after_id:
        anchor = session.scalar(query.where(CommuteDevelopment.id == after_id))
        if anchor is None:
            raise DomainError("Refresh the event list.", 422, "commute_cursor_invalid")
        query = query.where(CommuteDevelopment.id > after_id)
    rows = list(session.scalars(query.order_by(CommuteDevelopment.id).limit(limit + 1)))
    items = []
    for row in rows[:limit]:
        try:
            permission = require_permission(session, row.permission_id, row.source, now=now)
            items.append({**event_view(row, now=now, max_age_seconds=permission.max_age_seconds), "available": True})
        except DomainError:
            items.append({"id": row.id, "available": False})
    return {"items": items, "next_cursor": rows[limit - 1].id if len(rows) > limit else None}


def history_page(session, user_id, development_id, *, now, after_sequence=0, limit=20):
    _, row = owned_development(session, user_id, development_id, now=now)
    if type(limit) is not int or not 1 <= limit <= 100 or type(after_sequence) is not int or after_sequence < 0:
        raise DomainError("Invalid history page.", 422, "commute_history_query_invalid")
    rows = list(session.scalars(select(CommuteEventVersion).where(CommuteEventVersion.development_id == row.id,
        CommuteEventVersion.organization_id == row.organization_id, CommuteEventVersion.sequence > after_sequence)
        .order_by(CommuteEventVersion.sequence).limit(limit + 1)))
    for version in rows:
        if digest(version.evidence) != version.evidence_hash:
            raise DomainError("Commute event evidence is inconsistent.", 503, "commute_event_invalid")
    return {"items": [{"id": version.id, "created_at": utc(version.created_at).isoformat(),
                        "sequence": version.sequence, "evidence": deepcopy(version.evidence),
                        "evidence_hash": version.evidence_hash} for version in rows[:limit]],
            "next_cursor": rows[limit - 1].sequence if len(rows) > limit else None}


def review_event(session, user_id, development_id, version, sequence, *, now, muted=None):
    monitor, row = owned_development(session, user_id, development_id, now=now, write=True)
    positive(version)
    positive(sequence)
    if muted is not None and type(muted) is not bool:
        raise DomainError("Invalid mute value.", 422, "commute_mute_invalid")
    if monitor.status == "archived" or row.version != version or row.sequence != sequence:
        raise DomainError("The event changed. Reload it before reviewing.", 409, "commute_event_conflict")
    values = {"version": version + 1}
    if muted is None:
        values["reviewed_sequence"] = sequence
    else:
        values["muted"] = muted
    changed = session.execute(update(CommuteDevelopment).where(CommuteDevelopment.id == row.id,
        CommuteDevelopment.organization_id == row.organization_id, CommuteDevelopment.version == version,
        CommuteDevelopment.sequence == sequence).values(**values).execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        raise DomainError("The event changed. Reload it.", 409, "commute_event_conflict")
    if muted is not False:
        session.execute(update(CommuteSignal).where(CommuteSignal.development_id == row.id,
            CommuteSignal.organization_id == row.organization_id, CommuteSignal.sequence <= sequence,
            CommuteSignal.state == "pending").values(state="reviewed" if muted is None else "muted"))
    session.refresh(row)
    permission = require_permission(session, row.permission_id, row.source, now=now)
    return event_view(row, now=now, max_age_seconds=permission.max_age_seconds)
