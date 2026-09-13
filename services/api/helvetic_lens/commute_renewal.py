"""Bounded background renewal of saved identities from a pinned static archive.

No route is sent to the provider. This reads an already acquired archive and
publishes only unique, exact matches; acquiring/scheduling archives is separate.
"""

import re
from collections import defaultdict
from datetime import date
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from .commute_catalog import publish_legs, reference_identity
from .commute_contracts import digest
from .commute_interchanges import MAX_PAIRS, _publish_verified_pairs, resolve_interchange_pairs
from .commute_models import CommuteInterchange, CommuteLegReference
from .config import DomainError
from .monitoring_subjects import _savepoint
from .transport_reference import ZURICH, service_instant
from .transport_static import LegRequest, StaticArchive, identifier

MAX_TRIPS = 50_000
MAX_ENDPOINTS = 200_000
MAX_CANDIDATES = 32


def _targets(session, requests):
    if not 1 <= len(requests) <= 32 or len(set(requests)) != len(requests):
        raise ValueError("Renew one to 32 distinct reference/date pairs")
    targets = {}
    for reference_id, day in requests:
        if type(day) is not date:
            raise ValueError("Renewal requires explicit service dates")
        row = session.get(CommuteLegReference, reference_id)
        if row is None or not row.enabled:
            raise DomainError("The saved timetable reference is unavailable.", 409, "commute_reference_unavailable")
        identity_hash = digest(row.identity)
        expected = str(uuid5(NAMESPACE_URL, "https://helveticlens.ch/commute-reference/" + identity_hash))
        if identity_hash != row.identity_hash or expected != row.id:
            raise DomainError("The saved timetable identity is inconsistent.", 503, "commute_catalog_invalid")
        targets[(reference_id, day)] = row.identity
    return targets


def _candidates(archive, targets):
    routes, trips = {}, {}
    route_ids = {identity["route_id"] for identity in targets.values()}
    for row in archive.rows("routes.txt", {"route_id", "agency_id"}):
        if row["route_id"] in route_ids:
            if row["route_id"] in routes:
                raise ValueError("Ambiguous renewal route")
            routes[row["route_id"]] = identifier(row["agency_id"])
    by_route = defaultdict(list)
    for key, identity in targets.items():
        if routes.get(identity["route_id"]) == identity["agency_id"] and archive.start <= key[1] <= archive.end:
            by_route[(identity["route_id"], identity["direction_id"])].append(key)
    for row in archive.rows("trips.txt", {"trip_id", "route_id", "service_id", "direction_id"}):
        if row["route_id"] not in route_ids:
            continue
        if row["direction_id"] not in {"", "0", "1"}:
            raise ValueError("Ambiguous renewal direction")
        direction = int(row["direction_id"]) if row["direction_id"] else None
        if (row["route_id"], direction) not in by_route:
            continue
        trip = identifier(row["trip_id"])
        if trip in trips or len(trips) >= MAX_TRIPS:
            raise ValueError("Ambiguous or oversized renewal trip set")
        trips[trip] = (row["route_id"], direction, identifier(row["service_id"]))
    if not trips:
        return {}, set()
    active = archive.active_services({trip[2] for trip in trips.values()}, {key[1] for key in targets})
    relevant = {trip: [key for key in by_route[(route, direction)] if (service, key[1]) in active]
                for trip, (route, direction, service) in trips.items()}
    relevant = {trip: keys for trip, keys in relevant.items() if keys}
    if not relevant:
        return {}, set()
    endpoints = defaultdict(dict)
    wanted_stops = {trip: {stop for key in keys for stop in (targets[key]["stop_ids"][0], targets[key]["stop_ids"][-1])}
                    for trip, keys in relevant.items()}
    count = 0
    for row in archive.rows("stop_times.txt", {"trip_id", "stop_id", "stop_sequence", "departure_time"}):
        trip = row["trip_id"]
        if trip not in relevant or row["stop_id"] not in wanted_stops[trip]:
            continue
        if not re.fullmatch(r"[0-9]{1,8}", row["stop_sequence"]):
            raise ValueError("Invalid renewal stop sequence")
        sequence = int(row["stop_sequence"])
        if sequence in endpoints[trip] or count >= MAX_ENDPOINTS:
            raise ValueError("Ambiguous or oversized renewal endpoint set")
        endpoints[trip][sequence] = (row["stop_id"], row["departure_time"])
        count += 1
    options = defaultdict(set)
    candidates = set()
    for trip, rows in endpoints.items():
        for key in relevant[trip]:
            identity, day = targets[key], key[1]
            for start, (stop, departure) in rows.items():
                if stop != identity["stop_ids"][0]:
                    continue
                local = service_instant(day, departure).astimezone(ZURICH)
                if (local.strftime("%H:%M:%S") != identity["departure_wall_time"]
                        or (local.date() - day).days != identity["departure_day_offset"]):
                    continue
                for end, (last, _) in rows.items():
                    if end <= start or last != identity["stop_ids"][-1]:
                        continue
                    candidate = LegRequest(trip, day, start, end)
                    candidates.add(candidate)
                    if len(candidates) > MAX_CANDIDATES:
                        raise ValueError("Renewal candidates exceed bounded exact resolution")
                    options[key].add(candidate)
    frequencies = set()
    if "frequencies.txt" in archive.archive.namelist():
        for row in archive.rows("frequencies.txt", {"trip_id"}):
            if row["trip_id"] in relevant:
                frequencies.add(row["trip_id"])
    return options, frequencies


def prepare_renewal(session, requests, *, connection_requests=None):
    """Snapshot bounded public identities before any large archive scan."""
    targets = _targets(session, requests)
    ids = {key[0] for key in targets}
    days = sorted({key[1] for key in targets})
    query = select(CommuteInterchange.from_reference_id, CommuteInterchange.to_reference_id).where(
        CommuteInterchange.from_reference_id.in_(ids), CommuteInterchange.to_reference_id.in_(ids)).distinct()
    if connection_requests is not None:
        if len(connection_requests) > MAX_PAIRS or len(set(connection_requests)) != len(connection_requests):
            raise ValueError("Renewal interchange batch exceeds bound")
        connections = tuple(connection_requests)
        for before, after, day in connections:
            if ((before, day) not in targets or (after, day) not in targets
                    or session.execute(query.where(CommuteInterchange.from_reference_id == before,
                        CommuteInterchange.to_reference_id == after).limit(1)).first() is None):
                raise ValueError("Renew only previously imported exact connections")
        return targets, connections
    known = list(session.execute(query.order_by(CommuteInterchange.from_reference_id,
        CommuteInterchange.to_reference_id).limit(MAX_PAIRS + 1)))
    connections = []
    for before_id, after_id in known:
        for day in days:
            before_key, after_key = (before_id, day), (after_id, day)
            if before_key not in targets or after_key not in targets:
                continue
            if len(connections) >= MAX_PAIRS:
                raise ValueError("Renewal interchange batch exceeds bound")
            connections.append((before_id, after_id, day))
    if len(known) > MAX_PAIRS:
        raise ValueError("Renewal interchange graph exceeds bound")
    return targets, tuple(connections)


def resolve_renewal(archive, prepared):
    """Resolve identities and connection rules with no database dependency."""
    targets, connections = prepared
    options, frequencies = _candidates(archive, targets)
    supported = sorted({candidate for values in options.values() for candidate in values if candidate.trip_id not in frequencies},
                       key=lambda item: (item.trip_id, item.service_day, item.boarding_sequence, item.alighting_sequence))
    resolved = dict(zip(supported, archive.resolve(tuple(supported)) if supported else (), strict=True))
    outcomes, mapped = [], {}
    for key, identity in targets.items():
        values = options.get(key, set())
        exact = [resolved[candidate] for candidate in values if candidate in resolved
                 and reference_identity(resolved[candidate]) == identity]
        status = "unresolved"
        if not archive.start <= key[1] <= archive.end:
            status = "outside_feed"
        elif any(candidate.trip_id in frequencies for candidate in values):
            status = "unsupported_frequency"
        elif len(exact) > 1:
            status = "ambiguous"
        elif len(exact) == 1:
            status = "mapped"
            mapped[key] = exact[0]
        outcomes.append({"reference_id": key[0], "service_day": key[1].isoformat(),
                         "static_version": archive.version, "status": status})
    pairs, items = [], []
    for before, after, day in connections:
        item = {"from_reference_id": before, "to_reference_id": after, "service_day": day.isoformat(),
                "static_version": archive.version, "state": "mapping_unavailable"}
        if (before, day) in mapped and (after, day) in mapped:
            pairs.append((mapped[before, day], mapped[after, day]))
            item["state"] = "pending"
        items.append(item)
    proofs = resolve_interchange_pairs(archive, tuple(pairs)) if pairs else ()
    for item, proof in zip((item for item in items if item["state"] == "pending"), proofs, strict=True):
        item.update(state=proof["state"], proof_hash=digest(proof))
    return {"mapped": mapped, "pairs": tuple(pairs), "proofs": proofs,
            "report": {"items": outcomes, "interchanges": items, "archive_sha256": archive.sha256}}


def publish_renewal(session, prepared, resolved):
    """Recheck identities/known connections, then atomically publish scan results."""
    targets, connections = prepared
    for reference_id in sorted({key[0] for key in targets}):
        session.scalar(select(CommuteLegReference).where(CommuteLegReference.id == reference_id).with_for_update()
                       .execution_options(populate_existing=True))
    if prepare_renewal(session, tuple(targets), connection_requests=connections) != prepared:
        raise DomainError("The imported catalog changed during renewal.", 409, "commute_catalog_conflict")
    with _savepoint(session):
        for key, leg in resolved["mapped"].items():
            published, = publish_legs(session, (leg,))
            if published != key[0]:
                raise DomainError("Renewal changed the saved journey.", 503, "commute_catalog_invalid")
        if resolved["pairs"]:
            _publish_verified_pairs(session, resolved["pairs"], resolved["proofs"])
    return resolved["report"]


def renew_references(session, archive, requests):
    """Atomic operator import; automatic workers use the separate three phases."""
    prepared = prepare_renewal(session, requests)
    return publish_renewal(session, prepared, resolve_renewal(archive, prepared))


def run_renewal(database, path, *, expected_version, expected_sha256, requests, apply=False):
    """Operator/background entry point; dry runs leave the database unchanged."""
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise ValueError("Pin the acquired archive's SHA-256")
    if type(apply) is not bool:
        raise ValueError("Explicitly choose whether to apply the renewal")
    with StaticArchive(path, expected_version=expected_version) as archive:
        if archive.sha256 != expected_sha256:
            raise ValueError("Acquired archive checksum does not match")
        with database.session() as session:
            report = renew_references(session, archive, requests)
            if apply:
                session.commit()
            else:
                session.rollback()
            return {**report, "applied": apply}
