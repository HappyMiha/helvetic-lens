"""Pinned GTFS interchange evidence; no geographical or name-based inference.

GTFS Schedule reference, transfers.txt (revised 2026-04-27). Import is internal;
request handlers only read the immutable results for exact dated catalog legs.
"""

import re

from .commute_catalog import encode_leg
from .commute_contracts import digest
from .transport_static import LegRequest, identifier

MAX_TRANSFER_ROWS = 1_000_000
MAX_PAIRS = 32
ALLOWED = {"recommended", "timed", "minimum_met", "same_trip"}


def _specificity(row):
    left = 2 if row.get("from_trip_id") else 1 if row.get("from_route_id") else 0
    right = 2 if row.get("to_trip_id") else 1 if row.get("to_route_id") else 0
    # Trip specificity takes precedence over a redundant route on that side.
    return {(2, 2): 6, (2, 1): 5, (1, 2): 5, (2, 0): 4, (0, 2): 4,
            (1, 1): 3, (1, 0): 2, (0, 1): 2, (0, 0): 1}[left, right]


def _endpoints(archive, legs):
    wanted = {stop for leg in legs for stop in (leg.reference.stop_ids[0], leg.reference.stop_ids[-1])}
    stops = {}
    for row in archive.rows("stops.txt", {"stop_id", "parent_station", "location_type"}, limit=300_000):
        key = identifier(row["stop_id"])
        if key in stops:
            raise ValueError("Duplicate interchange stop")
        stops[key] = row
    result = {}
    for stop in wanted:
        row = stops.get(stop)
        if row is None or row["location_type"] not in {"", "0"}:
            raise ValueError("Interchange requires exact boarding locations")
        values = {stop}
        parent = row["parent_station"]
        if parent:
            if parent not in stops or stops[parent]["location_type"] != "1":
                raise ValueError("Unverified interchange parent")
            values.add(parent)
        result[stop] = values
    return result


def _applies(row, before, after, endpoints):
    for prefix, leg, stop in (("from", before, before.reference.stop_ids[-1]),
                              ("to", after, after.reference.stop_ids[0])):
        trip, route, location = (row.get(prefix + suffix, "") for suffix in ("_trip_id", "_route_id", "_stop_id"))
        if trip == leg.reference.trip_id and route and route != leg.reference.route_id:
            raise ValueError("Interchange trip and route disagree")
        if trip and trip != leg.reference.trip_id or route and route != leg.reference.route_id:
            return False
        if location and location not in endpoints[stop]:
            return False
    return True


def resolve_interchanges(archive, legs):
    """Prove each adjacent pair of 2..8 ordered legs against this exact archive.

    Ambiguous/absent/forbidden/insufficient rules are explicit non-start outcomes.
    Parent station rules expand only to their actual endpoint children. There is
    no guessed platform specificity tie-breaker: GTFS requires a unique maximum.
    Linked-vehicle transfers 4/5 need a separate vehicle-continuation contract.
    """
    if not 2 <= len(legs) <= 8:
        raise ValueError("Import interchanges for two to eight ordered legs")
    return resolve_interchange_pairs(archive, tuple(zip(legs, legs[1:])))


def resolve_interchange_pairs(archive, pairs):
    """Verify a bounded renewal batch in one timetable/transfer-table scan."""
    if not 1 <= len(pairs) <= MAX_PAIRS or any(len(pair) != 2 for pair in pairs):
        raise ValueError("Interchange pair batch exceeds import bound")
    legs = tuple(dict.fromkeys(leg for pair in pairs for leg in pair))
    if len(legs) > 32:
        raise ValueError("Interchange leg batch exceeds import bound")
    if any(leg.archive_sha256 != archive.sha256 or leg.reference.static_version != archive.version for leg in legs):
        raise ValueError("Interchange archive identity does not match the legs")
    requests = tuple(LegRequest(leg.reference.trip_id, leg.reference.service_day,
        leg.stop_sequences[0], leg.stop_sequences[-1]) for leg in legs)
    if tuple(legs) != archive.resolve(requests):
        raise ValueError("Interchange legs do not match the pinned timetable")
    endpoints = _endpoints(archive, legs)
    best = [(0, []) for _ in pairs]
    if "transfers.txt" in archive.archive.namelist():
        for number, raw in enumerate(archive.rows("transfers.txt", {"transfer_type"}, limit=MAX_TRANSFER_ROWS), 2):
            row = {key: raw.get(key, "") for key in ("from_stop_id", "to_stop_id", "from_trip_id", "to_trip_id",
                "from_route_id", "to_route_id", "transfer_type", "min_transfer_time")}
            for index, (before, after) in enumerate(pairs):
                if not _applies(row, before, after, endpoints):
                    continue
                kind = row["transfer_type"] or "0"
                if kind not in {"0", "1", "2", "3", "4", "5"}:
                    raise ValueError("Unknown interchange transfer type")
                required = ("from_trip_id", "to_trip_id") if kind in {"4", "5"} else ("from_stop_id", "to_stop_id")
                for key in required:
                    identifier(row[key])
                if any(value and len(value) > 256 for key, value in row.items() if key.endswith("_id")):
                    raise ValueError("Interchange identifier exceeds bound")
                minimum = row["min_transfer_time"]
                if minimum and not re.fullmatch(r"[0-9]{1,6}", minimum):
                    raise ValueError("Invalid minimum interchange time")
                if kind == "2" and not minimum:
                    raise ValueError("Minimum-time transfer has no minimum")
                if minimum and int(minimum) > 604800:
                    raise ValueError("Minimum interchange time exceeds seven days")
                rank, (old_rank, matches) = _specificity(row), best[index]
                if rank >= old_rank:
                    # Retain at most two candidates: enough to prove ambiguity.
                    best[index] = (rank, ([*matches, (number, row)][:2] if rank == old_rank else [(number, row)]))
    results = []
    for (before, after), (_, matches) in zip(pairs, best, strict=True):
        slack = int((after.departure - before.arrival).total_seconds())
        proof = {"archive_sha256": archive.sha256, "static_version": archive.version,
            "from_leg_hash": digest(encode_leg(before)), "to_leg_hash": digest(encode_leg(after)),
            "from_stop_id": before.reference.stop_ids[-1], "to_stop_id": after.reference.stop_ids[0],
            "scheduled_seconds": slack, "min_transfer_time": None, "rule": None, "row_number": None}
        state = "unverified"
        if before.reference.service_day != after.reference.service_day:
            state = "different_service_day"
        elif slack < 0:
            state = "insufficient_time"
        elif (before.reference.trip_id == after.reference.trip_id
              and before.stop_sequences[-1] == after.stop_sequences[0]
              and before.reference.stop_ids[-1] == after.reference.stop_ids[0]):
            # Staying aboard one scheduled trip is not a transfer between routes.
            state = "same_trip"
        elif len(matches) > 1:
            state = "ambiguous"
        elif matches:
            number, row = matches[0]
            kind = int(row["transfer_type"] or "0")
            minimum = int(row["min_transfer_time"]) if row["min_transfer_time"] else None
            proof.update(rule=row, row_number=number, min_transfer_time=minimum)
            state = {0: "recommended", 1: "timed", 2: "minimum_met", 3: "forbidden",
                     4: "unsupported_linked_trip", 5: "unsupported_linked_trip"}[kind]
            if state in ALLOWED and (minimum is not None and slack < minimum or kind == 0 and slack == 0):
                state = "insufficient_time"
        results.append({**proof, "state": state})
    return tuple(results)


def publish_interchanges(session, archive, legs):
    """Internal importer publishes catalog legs and their rules atomically."""
    if not 2 <= len(legs) <= 8:
        raise ValueError("Import interchanges for two to eight ordered legs")
    report = publish_interchange_pairs(session, archive, tuple(zip(legs, legs[1:])))
    identifiers = (report["pairs"][0][0], *(pair[1] for pair in report["pairs"]))
    return {"reference_ids": identifiers, "interchanges": report["interchanges"]}


def publish_interchange_pairs(session, archive, pairs):
    """Atomic batch import, including explicit denied connection outcomes."""
    return _publish_verified_pairs(session, pairs, resolve_interchange_pairs(archive, pairs))


def _publish_verified_pairs(session, pairs, proofs):
    """Persist proofs computed by the trusted resolver, without scanning files."""
    from .commute_catalog import publish_legs
    from .commute_models import CommuteInterchange
    from .config import DomainError
    from .monitoring_subjects import _savepoint
    legs = tuple(dict.fromkeys(leg for pair in pairs for leg in pair))
    identifiers_by_leg = {}
    published_pairs = []
    with _savepoint(session):
        identifiers = publish_legs(session, tuple(legs))
        identifiers_by_leg.update(zip(legs, identifiers, strict=True))
        for (before, after), proof in zip(pairs, proofs, strict=True):
            key = (identifiers_by_leg[before], identifiers_by_leg[after], before.reference.service_day, before.reference.static_version)
            if before.reference.service_day != after.reference.service_day:
                raise ValueError("Import connected legs on the same GTFS service day")
            existing = session.get(CommuteInterchange, key)
            if existing is not None and (existing.proof_hash != digest(proof) or existing.proof != proof):
                raise DomainError("Conflicting pinned interchange evidence.", 409, "commute_catalog_conflict")
            if existing is None:
                session.add(CommuteInterchange(from_reference_id=key[0], to_reference_id=key[1], service_day=key[2],
                    static_version=key[3], proof=proof, proof_hash=digest(proof)))
                session.flush()
            published_pairs.append((key[0], key[1]))
    return {"pairs": tuple(published_pairs), "interchanges": proofs}


def journey_interchanges(session, configuration, resolved):
    """Read exact pair evidence in saved travel order, preserving denied outcomes."""
    from .commute_models import CommuteInterchange
    from .config import DomainError
    ids = [str(value) for value in configuration.leg_reference_ids]
    results = []
    for before_id, after_id in zip(ids, ids[1:]):
        before, after = resolved[before_id], resolved[after_id]
        key = (before_id, after_id, before.reference.service_day, before.reference.static_version)
        row = session.get(CommuteInterchange, key)
        if row is None:
            results.append({"from_reference_id": before_id, "to_reference_id": after_id, "state": "unverified"})
            continue
        proof = row.proof
        if (not isinstance(proof, dict) or digest(proof) != row.proof_hash
                or proof.get("from_leg_hash") != digest(encode_leg(before))
                or proof.get("to_leg_hash") != digest(encode_leg(after))
                or proof.get("archive_sha256") != before.archive_sha256
                or before.archive_sha256 != after.archive_sha256
                or proof.get("static_version") != before.reference.static_version
                or before.reference.service_day != after.reference.service_day):
            raise DomainError("Interchange evidence is unavailable.", 503, "commute_catalog_invalid")
        results.append({**proof, "from_reference_id": before_id, "to_reference_id": after_id})
    return results


def require_interchanges(session, configuration, resolved):
    from .config import DomainError
    results = journey_interchanges(session, configuration, resolved)
    if any(proof["state"] not in ALLOWED for proof in results):
        raise DomainError("The connected journey has no usable verified interchange.", 409, "commute_transfer_unverified")
    return results


def run_import(database, path, *, expected_version, expected_sha256, requests, apply=False):
    """Operator/background import; dry-run rollback by default, no source grants."""
    from .transport_static import StaticArchive
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise ValueError("Pin the acquired archive SHA-256")
    if type(apply) is not bool or not 2 <= len(requests) <= 8:
        raise ValueError("Import two to eight ordered legs and explicitly choose apply")
    with StaticArchive(path, expected_version=expected_version) as archive:
        if archive.sha256 != expected_sha256:
            raise ValueError("Acquired archive checksum does not match")
        with database.session() as session:
            report = publish_interchanges(session, archive, archive.resolve(tuple(requests)))
            if apply:
                session.commit()
            else:
                session.rollback()
            return {**report, "applied": apply}
