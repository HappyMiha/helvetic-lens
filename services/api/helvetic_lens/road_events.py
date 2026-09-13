"""Private material history from permitted source evidence; no network or email.

Caller owns the transaction and locks the current monitor before processing.
Source and topology rights are independent. Raw graph/XML/comments never become
an event response. A missing source notice is not evidence of an open road.
"""

import json
from copy import deepcopy
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select, update

from .config import DomainError
from .road_catalog import CatalogReadBudget, _map_hash, _reference, _rights, resolve_reference
from .road_evaluation import evaluate_record
from .road_models import (
    RoadConfigurationRevision,
    RoadCorridorMap,
    RoadCurrentSituation,
    RoadDevelopment,
    RoadEventVersion,
    RoadSituationVersion,
    RoadSourcePermission,
    RoadTopologyRevision,
)
from .road_repository import configuration, owned
from .road_sources import _clock, _encoded, _hash, _head, _utc, read_state, read_version, require_permission
from .road_topology import RoadIntersection

FIELDS = ("event_kind", "validity", "location")
MAX_EVENT_BYTES = 128 * 1024
MAX_HISTORY_BYTES = 32 * 1024**2
MAX_DEVELOPMENTS = 1000
MAX_VERSIONS = 10_000
MAX_EVALUATIONS = 100_000


def _fail(code, status=409):
    raise DomainError("Private road event evidence is unavailable.", status, code) from None


def _read(payload, hashed):
    if payload is None:
        _fail("road_event_expired")
    if len(payload) > MAX_EVENT_BYTES or _hash(payload) != hashed:
        _fail("road_event_invalid", 503)
    try:
        result = json.loads(payload)
        if _encoded(result) != payload or not isinstance(result, dict):
            _fail("road_event_invalid", 503)
        return result
    except (ValueError, TypeError):
        _fail("road_event_invalid", 503)


def _fact(record, decision, fields):
    window = decision.temporal.window
    result = {"kind": record.kind, "phase": decision.temporal.phase, "probability": record.probability,
              "valid_from": window.start.isoformat() if window else None,
              "valid_until": window.end.isoformat() if window and window.end else None}
    if "delay" in fields and record.kind == "congestion":
        result["delay_seconds"] = record.delay_seconds
    if "lanes" in fields:
        result.update(lanes_restricted=record.lanes_restricted, lanes_operational=record.lanes_operational,
                      lanes_original=record.lanes_original)
    return result


def _material(payload):
    # Preserve the exact current permitted delay, but do not create a new
    # material history item for every second of prediction jitter.
    value = deepcopy(payload)
    for corridor in value.get("corridors", {}).values():
        facts = {}
        for fact in corridor.get("facts", []):
            if fact.get("delay_seconds") is not None:
                fact["delay_seconds"] = int(fact["delay_seconds"] // 300) * 300
            facts[_hash(_encoded(fact))] = fact
        corridor["facts"] = [facts[key] for key in sorted(facts)]
    return _hash(_encoded(value))


def _project(session, entry, config, old, *, now, fields, budget, mappings):
    situation = entry.situation
    unavailable = {ref: {"state": "unavailable", "facts": [], "coverage": "unknown"}
                   for ref in (old or {}).get("corridors", {})}
    if not entry.present:
        return ({"state": "unavailable", "reason": "source_notice_missing", "corridors": unavailable} if old else None), True
    if (situation.confidentiality != "noRestriction" or situation.information_status != "real" or situation.unsupported):
        return ({"state": "unavailable", "reason": "source_visibility_or_capability", "corridors": unavailable} if old else None), True
    contributions, degraded = {}, False
    for reference_id in sorted(str(value) for value in config.corridor_reference_ids):
        facts, transitions, uncertain, relevant = {}, [], False, False
        for record in situation.records:
            location = record.location
            match = RoadIntersection("unknown", "location_unavailable")
            if location is not None:
                key = (reference_id, location.country, location.table, location.version)
                if key not in mappings:
                    try:
                        mappings[key] = resolve_reference(session, reference_id, table_key=key[1:], now=now,
                                                          display=True, read_budget=budget)
                    except DomainError as error:
                        if error.code == "road_catalog_read_limit":
                            raise
                        mappings[key] = None
                resolved = mappings[key]
                if resolved is not None:
                    match = resolved.topology.intersection(location, resolved.corridor)
            decision = evaluate_record(record, match, config.materiality, now=now)
            # A delay-derived eligibility decision itself requires delay use,
            # even when the exact number is omitted from the eventual response.
            if record.kind == "congestion" and "delay" not in fields:
                uncertain = uncertain or match.state != "no_match"
                continue
            if decision.state == "unknown":
                uncertain = True
            elif decision.state == "eligible":
                fact = _fact(record, decision, fields)
                facts[_hash(_encoded(fact))] = fact
                relevant = True
            elif decision.state == "transition" and match.state == "match":
                transitions.append(("cleared" if record.probability == "certain" else "possible_clearance")
                                   if record.kind == "source_clearance" else decision.temporal.phase)
            elif match.state == "match":
                relevant = relevant or bool(old)
        previous = (old or {}).get("corridors", {}).get(reference_id)
        if facts:
            ordered = [facts[key] for key in sorted(facts)]
            contributions[reference_id] = {"state": "active" if any(f["phase"] == "active" for f in ordered) else "planned",
                "facts": ordered, "coverage": "partial" if uncertain else "verified"}
        elif uncertain:
            if previous or old:
                contributions[reference_id] = {"state": "unavailable", "facts": [], "coverage": "unknown"}
        elif transitions and previous:
            # Explicit roadCleared is distinct from withdrawal, expiry and end.
            phase = "cleared" if set(transitions) == {"cleared"} else transitions[0] if len(set(transitions)) == 1 else "ended"
            contributions[reference_id] = {"state": phase, "facts": [], "coverage": "verified"}
        elif previous or (relevant and old):
            contributions[reference_id] = {"state": "not_relevant", "facts": [], "coverage": "verified"}
        degraded = degraded or uncertain
    if not contributions:
        return None, degraded
    states = {item["state"] for item in contributions.values()}
    state = "active" if "active" in states else "planned" if "planned" in states else "unavailable" if "unavailable" in states else "ended"
    return {"state": state, "corridors": contributions}, degraded


def process_snapshot(session, monitor, permission_id, *, now):
    """Write material changes and evidence atomically inside a caller savepoint."""
    now = _clock(now)
    config = configuration(monitor.configuration)
    revision = session.scalar(select(RoadConfigurationRevision).where(RoadConfigurationRevision.monitor_id == monitor.id,
        RoadConfigurationRevision.organization_id == monitor.organization_id, RoadConfigurationRevision.revision == monitor.revision))
    if revision is None or revision.configuration_hash != config.fingerprint() or revision.configuration != monitor.configuration:
        _fail("road_monitor_configuration_invalid", 503)
    _, policy = require_permission(session, permission_id, now=now, fields=FIELDS)
    state = read_state(session, permission_id, now=now)
    head = _head(session)
    evaluations = sum(len(entry.situation.records) for entry in state.situations) * len(config.corridor_reference_ids)
    if evaluations > MAX_EVALUATIONS:
        _fail("road_event_evaluation_limit")
    previous = {row.source_id: row for row in session.scalars(select(RoadDevelopment).where(
        RoadDevelopment.monitor_id == monitor.id, RoadDevelopment.organization_id == monitor.organization_id,
        RoadDevelopment.configuration_revision == monitor.revision, RoadDevelopment.permission_id == permission_id))}
    bound = {current.source_id: version for current, version in session.execute(select(RoadCurrentSituation, RoadSituationVersion)
        .join(RoadSituationVersion, RoadSituationVersion.id == RoadCurrentSituation.version_id)
        .where(RoadCurrentSituation.permission_id == permission_id))}
    count = session.scalar(select(func.count()).select_from(RoadDevelopment).where(RoadDevelopment.monitor_id == monitor.id))
    versions, history_bytes = session.execute(select(func.count(), func.coalesce(func.sum(RoadEventVersion.content_size), 0))
        .select_from(RoadEventVersion).join(RoadDevelopment).where(RoadDevelopment.monitor_id == monitor.id)).one()
    changed, degraded, budget, mappings = 0, False, CatalogReadBudget(), {}
    for entry in state.situations:
        row = previous.get(entry.situation.source_id)
        old = _read(row.payload, row.payload_hash) if row and row.payload is not None else None
        # Expired private bytes may not be revived as new evidence by an unseen
        # delta. The current source version must still have permitted bytes.
        source_version = bound.get(entry.situation.source_id)
        if source_version is None or source_version.content is None or _utc(source_version.expires_at) <= now:
            _fail("road_event_source_binding_invalid", 503)
        projected, partial = _project(session, entry, config, old, now=now, fields=policy.allowed_fields,
                                      budget=budget, mappings=mappings)
        degraded = degraded or partial
        if projected is None:
            continue
        relevant_ids = set(projected["corridors"])
        used_maps = sorted({value.mapping_id for key, value in mappings.items() if value and key[0] in relevant_ids
                            and any(record.location and key[1:] == (record.location.country, record.location.table, record.location.version)
                                    for record in entry.situation.records)})
        expiry = min(now + timedelta(seconds=policy.derived_retention_seconds), _utc(source_version.expires_at), _utc(policy.valid_until))
        for identifier in used_maps:
            mapped = session.get(RoadCorridorMap, identifier)
            topo, _ = _rights(session, mapped.topology_id, now=now, matching=True, display=True)
            expiry = min(expiry, _utc(topo.valid_until))
        payload = _encoded(projected)
        if len(payload) > MAX_EVENT_BYTES:
            _fail("road_event_storage_limit")
        proof = {"source_version_id": source_version.id, "source_content_hash": source_version.content_hash,
                 "source_semantic_hash": source_version.semantic_hash, "source_generation": head.generation,
                 "mapping_ids": used_maps, "fields": list(FIELDS) + [f for f in ("delay", "lanes") if f in policy.allowed_fields],
                 "observed_at": state.published_at.isoformat(), "kind": "permitted_normalized_road_fields"}
        payload_hash = _hash(payload)
        if row is None:
            if count >= MAX_DEVELOPMENTS:
                _fail("road_event_storage_limit")
            row = RoadDevelopment(monitor_id=monitor.id, organization_id=monitor.organization_id,
                configuration_revision=monitor.revision, permission_id=permission_id, source_id=entry.situation.source_id,
                development_key=entry.situation.development_id, payload_hash="", material_hash="", proof={}, proof_hash="",
                expires_at=expiry, updated_at=now)
            session.add(row)
            session.flush()
            count += 1
        material_hash = _material(projected)
        material = material_hash != row.material_hash
        row.payload, row.payload_hash, row.proof, row.proof_hash = payload, payload_hash, proof, _hash(_encoded(proof))
        row.expires_at = expiry
        row.material_hash = material_hash
        if material:
            size = len(payload) + len(_encoded(proof))
            if versions >= MAX_VERSIONS or history_bytes + size > MAX_HISTORY_BYTES:
                _fail("road_event_storage_limit")
            row.sequence += 1
            row.version += 1
            row.updated_at = now
            snapshot = RoadEventVersion(development_id=row.id, organization_id=row.organization_id, sequence=row.sequence,
                payload=payload, payload_hash=payload_hash, proof=proof, proof_hash=row.proof_hash, content_size=size,
                expires_at=expiry, created_at=now)
            session.add(snapshot)
            session.flush()
            from .road_delivery import record_intent
            record_intent(session, monitor, row, snapshot, now)
            versions, history_bytes, changed = versions + 1, history_bytes + size, changed + 1
    session.flush()
    return {"changed": changed, "degraded": degraded, "source_generation": head.generation}


def _proof(session, row, version, *, now):
    if _utc(version.expires_at) <= now or version.payload is None:
        _fail("road_event_expired")
    proof = version.proof
    if _hash(_encoded(proof)) != version.proof_hash:
        _fail("road_event_proof_invalid", 503)
    require_permission(session, row.permission_id, now=now, fields=proof["fields"])
    source = session.get(RoadSituationVersion, proof["source_version_id"])
    if (source is None or source.permission_id != row.permission_id or source.source_id != row.source_id
            or source.content_hash != proof["source_content_hash"] or source.content is None or _utc(source.expires_at) <= now):
        _fail("road_event_source_unavailable")
    read_version(session, row.permission_id, source.id, now=now, fields=proof["fields"])
    for identifier in proof["mapping_ids"]:
        mapped = session.get(RoadCorridorMap, identifier)
        if mapped is None or mapped.content is None:
            _fail("road_event_mapping_unavailable")
        _rights(session, mapped.topology_id, now=now, matching=True, display=True)
        reference = _reference(session, mapped.reference_id)
        if not reference.enabled or _map_hash(mapped, reference) != mapped.binding_hash:
            _fail("road_event_mapping_unavailable")
    return _read(version.payload, version.payload_hash)


def owned_event(session, user_id, event_id, *, write=False):
    row = session.scalar(select(RoadDevelopment).where(RoadDevelopment.id == event_id)
                         .execution_options(populate_existing=True))
    if row is None:
        _fail("road_event_not_found", 404)
    monitor = owned(session, user_id, row.monitor_id, write=write)
    return row, monitor


def event_view(session, row, *, now):
    attribution = None
    try:
        payload = _proof(session, row, row, now=now)
        availability = "available"
        _, policy = require_permission(session, row.permission_id, now=now)
        attribution = policy.attribution
        observed = datetime.fromisoformat(row.proof["observed_at"])
        head = _head(session)
        if (head is None or head.permission_id != row.permission_id or head.published_at is None
                or head.received_at is None or observed > now or _utc(head.published_at) > now or _utc(head.received_at) > now):
            availability = "unavailable"
            payload = None
        elif (head.generation != row.proof["source_generation"]
              or (now - observed).total_seconds() > policy.max_age_seconds):
            # Source collection can advance before private processing. The old
            # proof remains readable but cannot be presented as a live closure.
            availability = "stale"
        if payload is not None:
            for identifier in row.proof["mapping_ids"]:
                mapped = session.get(RoadCorridorMap, identifier)
                topology = session.get(RoadTopologyRevision, mapped.topology_id)
                latest = session.scalar(select(RoadCorridorMap.id).join(RoadTopologyRevision).where(
                    RoadCorridorMap.reference_id == mapped.reference_id,
                    RoadTopologyRevision.country == topology.country, RoadTopologyRevision.table == topology.table,
                    RoadTopologyRevision.version == topology.version).order_by(RoadCorridorMap.generation.desc()).limit(1))
                if latest != mapped.id:
                    availability = "stale"
    except DomainError:
        payload, availability = None, "unavailable"
    return {"id": row.id, "monitor_id": row.monitor_id, "configuration_revision": row.configuration_revision,
            "version": row.version, "sequence": row.sequence, "reviewed_sequence": row.reviewed_sequence,
            "muted": row.muted, "payload": payload, "availability": availability, "updated_at": _utc(row.updated_at).isoformat(),
            "attribution": attribution if payload is not None else None}


def events_page(session, user_id, monitor_id, *, now, limit=20, after_id=None):
    from .road_repository import _limit
    monitor = owned(session, user_id, monitor_id)
    _limit(limit)
    now = _clock(now)
    query = select(RoadDevelopment).where(RoadDevelopment.monitor_id == monitor.id)
    if after_id is not None:
        cursor, _ = owned_event(session, user_id, after_id)
        if cursor.monitor_id != monitor.id:
            _fail("road_event_cursor_invalid", 404)
        query = query.where(RoadDevelopment.id > after_id)
    rows = list(session.scalars(query.order_by(RoadDevelopment.id).limit(limit + 1)))
    return {"items": [event_view(session, row, now=now) for row in rows[:limit]],
            "next_cursor": rows[limit - 1].id if len(rows) > limit else None}


def history_page(session, user_id, event_id, *, now, after_sequence=0, limit=20):
    from .road_repository import _limit
    row, _ = owned_event(session, user_id, event_id)
    _limit(limit)
    now = _clock(now)
    if type(after_sequence) is not int or after_sequence < 0:
        _fail("road_event_cursor_invalid", 422)
    rows = list(session.scalars(select(RoadEventVersion).where(RoadEventVersion.development_id == row.id,
        RoadEventVersion.sequence > after_sequence).order_by(RoadEventVersion.sequence).limit(limit + 1)))
    result = []
    for version in rows[:limit]:
        result.append(version_view(session, row, version, now=now))
    return {"items": result, "next_cursor": rows[limit - 1].sequence if len(rows) > limit else None}


def version_view(session, row, version, *, now):
    try:
        payload = _proof(session, row, version, now=now)
        attribution = require_permission(session, row.permission_id, now=now)[1].attribution
    except DomainError:
        payload, attribution = None, None
    return {"sequence": version.sequence, "payload": payload, "attribution": attribution,
            "availability": "available" if payload is not None else "unavailable",
            "created_at": _utc(version.created_at).isoformat()}


def review_event(session, user_id, event_id, *, expected_version, sequence, muted=None):
    row, monitor = owned_event(session, user_id, event_id, write=True)
    if (type(expected_version) is not int or type(sequence) is not int or sequence != row.sequence
            or row.version != expected_version or (muted is not None and type(muted) is not bool)):
        _fail("road_event_version_conflict")
    reviewed = sequence if muted is None else row.reviewed_sequence
    updated = session.execute(update(RoadDevelopment).where(RoadDevelopment.id == row.id,
        RoadDevelopment.organization_id == monitor.organization_id, RoadDevelopment.version == expected_version,
        RoadDevelopment.sequence == sequence).values(reviewed_sequence=reviewed, version=expected_version + 1,
        muted=row.muted if muted is None else muted).execution_options(synchronize_session=False))
    if updated.rowcount != 1:
        _fail("road_event_version_conflict")
    return {"version": expected_version + 1, "reviewed_sequence": reviewed}


def purge_events(session, *, now):
    """Delete derived bytes after expiry/revocation; keep scoped sequence/hash audit."""
    now = _clock(now)
    denied = select(RoadSourcePermission.id).where(or_(RoadSourcePermission.revoked_at.is_not(None),
                                                      RoadSourcePermission.valid_until <= now))
    denied_events = select(RoadDevelopment.id).where(RoadDevelopment.permission_id.in_(denied))
    denied_topos = select(RoadTopologyRevision.id).where(or_(RoadTopologyRevision.revoked_at.is_not(None),
                                                            RoadTopologyRevision.valid_until <= now))
    denied_maps = set(session.scalars(select(RoadCorridorMap.id).where(RoadCorridorMap.topology_id.in_(denied_topos))))
    # Each monitor has a hard row/byte bound. Scan proof metadata in bounded SQL
    # batches; source bytes are not loaded for retention.
    for model in (RoadDevelopment, RoadEventVersion):
        deny = model.permission_id.in_(denied) if model is RoadDevelopment else model.development_id.in_(denied_events)
        session.execute(update(model).where(or_(model.expires_at <= now, deny)).values(payload=None)
                        .execution_options(synchronize_session="fetch"))
        if denied_maps:
            rows = session.execute(select(model.id, model.proof).where(model.payload.is_not(None)))
            for identifier, proof in rows.yield_per(100):
                if denied_maps.intersection(proof.get("mapping_ids", ())):
                    session.execute(update(model).where(model.id == identifier).values(payload=None))
    session.flush()
