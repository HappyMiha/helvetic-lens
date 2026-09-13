"""Internal static-import boundary; catalog writes are never user request data."""

import re
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select

from .commute_contracts import digest
from .commute_models import CommuteDatedLeg, CommuteLegReference
from .config import DomainError
from .monitoring_subjects import _actor, _savepoint
from .transport_reference import ZURICH, VerifiedLeg, service_instant
from .transport_static import ResolvedLeg


def encode_leg(leg: ResolvedLeg):
    reference = leg.reference
    if (type(reference.service_day) is not date or not re.fullmatch(r"[a-f0-9]{64}", leg.archive_sha256)
            or any(t.tzinfo is None or t.utcoffset() is None for t in (leg.departure, leg.arrival))
            or leg.departure >= leg.arrival or not 2 <= len(reference.stop_ids) <= 2000
            or len(leg.stop_sequences) != len(reference.stop_ids)
            or any(type(s) is not int or s < 0 for s in leg.stop_sequences)
            or tuple(sorted(set(leg.stop_sequences))) != leg.stop_sequences):
        raise ValueError("A catalog leg requires verified dated sequence/time/archive identity")
    start = service_instant(reference.service_day, "00:00:00")
    if any(not start <= t < start + timedelta(days=7) for t in (leg.departure, leg.arrival)):
        raise ValueError("Catalog times disagree with their service date")
    if any(not isinstance(s, str) or not s.strip() or len(s) > 150
           for s in (leg.boarding_name, leg.alighting_name, leg.route_name)):
        raise ValueError("Catalog labels must be bounded source names")
    payload = asdict(leg)
    payload["reference"]["service_day"] = reference.service_day.isoformat()
    for field in ("stop_ids", "parent_stop_ids"):
        payload["reference"][field] = list(payload["reference"][field])
    payload["stop_sequences"] = list(leg.stop_sequences)
    payload["departure"] = leg.departure.astimezone(UTC).isoformat()
    payload["arrival"] = leg.arrival.astimezone(UTC).isoformat()
    return payload


def decode_leg(row: CommuteDatedLeg):
    payload = row.resolved
    if digest(payload) != row.resolved_hash:
        raise DomainError("Verified timetable evidence is unavailable.", 503, "commute_catalog_invalid")
    try:
        reference = dict(payload["reference"])
        reference["service_day"] = date.fromisoformat(reference["service_day"])
        reference["stop_ids"] = tuple(reference["stop_ids"])
        reference["parent_stop_ids"] = tuple(reference["parent_stop_ids"])
        values = {**payload, "reference": VerifiedLeg(**reference), "stop_sequences": tuple(payload["stop_sequences"])}
        for field in ("departure", "arrival"):
            values[field] = datetime.fromisoformat(payload[field])
        leg = ResolvedLeg(**values)
        encode_leg(leg)
        if reference["service_day"] != row.service_day or reference["static_version"] != row.static_version:
            raise ValueError("Dated catalog key mismatch")
        return leg
    except (ValueError, KeyError, TypeError):
        raise DomainError("Verified timetable evidence is unavailable.", 503, "commute_catalog_invalid") from None


def reference_identity(leg):
    reference = leg.reference
    local_departure = leg.departure.astimezone(ZURICH)
    return {"agency_id": reference.agency_id, "route_id": reference.route_id,
            "direction_id": reference.direction_id, "stop_ids": list(reference.stop_ids),
            "departure_wall_time": local_departure.strftime("%H:%M:%S"),
            "departure_day_offset": (local_departure.date() - reference.service_day).days}


def publish_legs(session, legs: tuple[ResolvedLeg, ...]):
    """Trusted importer persists bounded exact results; no private owner/query data.

    Re-importing identical data is idempotent. Conflicting evidence for a pinned
    reference/date/version is rejected instead of rewriting saved journey meaning.
    """
    if not 1 <= len(legs) <= 32:
        raise ValueError("Publish between one and 32 verified legs per import")
    ids = []
    with _savepoint(session):
        for leg in legs:
            payload = encode_leg(leg)
            reference = leg.reference
            identity = reference_identity(leg)
            hashed = digest(identity)
            identifier = str(uuid5(NAMESPACE_URL, "https://helveticlens.ch/commute-reference/" + hashed))
            catalog = session.get(CommuteLegReference, identifier)
            if catalog is None:
                catalog = CommuteLegReference(id=identifier, identity_hash=hashed, identity=identity,
                                             label=f"{leg.route_name}: {leg.boarding_name} → {leg.alighting_name}")
                session.add(catalog)
                session.flush()
            elif catalog.identity_hash != hashed or catalog.identity != identity:
                raise DomainError("Conflicting timetable reference.", 409, "commute_catalog_conflict")
            row = session.get(CommuteDatedLeg, (identifier, reference.service_day, reference.static_version))
            if row is not None and row.resolved_hash != digest(payload):
                raise DomainError("Conflicting dated timetable evidence.", 409, "commute_catalog_conflict")
            if row is None:
                session.add(CommuteDatedLeg(reference_id=identifier, service_day=reference.service_day,
                                           static_version=reference.static_version, resolved=payload,
                                           resolved_hash=digest(payload)))
                session.flush()
            ids.append(identifier)
    return tuple(ids)


def require_references(session, configuration):
    ids = tuple(str(value) for value in configuration.leg_reference_ids)
    rows = list(session.scalars(select(CommuteLegReference).where(CommuteLegReference.id.in_(ids),
                                                               CommuteLegReference.enabled.is_(True))))
    if {row.id for row in rows} != set(ids):
        raise DomainError("Choose available verified journey legs.", 422, "commute_reference_unavailable")
    return {row.id: row for row in rows}


def catalog_page(session, user_id, *, service_day: date, query="", limit=20, after_id=None):
    _actor(session, user_id)
    if type(service_day) is not date or type(limit) is not int or not 1 <= limit <= 100:
        raise DomainError("Invalid timetable page.", 422, "commute_catalog_query_invalid")
    if not isinstance(query, str) or len(query) > 100:
        raise DomainError("Use a bounded station or route search.", 422, "commute_catalog_query_invalid")
    statement = select(CommuteLegReference).where(CommuteLegReference.enabled.is_(True),
        select(CommuteDatedLeg.reference_id).where(CommuteDatedLeg.reference_id == CommuteLegReference.id,
                                                 CommuteDatedLeg.service_day == service_day).exists())
    if query.strip():
        statement = statement.where(CommuteLegReference.label.icontains(query.strip(), autoescape=True))
    if after_id:
        statement = statement.where(CommuteLegReference.id > after_id)
    rows = list(session.scalars(statement.order_by(CommuteLegReference.id).limit(limit + 1)))
    return {"items": [{"id": row.id, "label": row.label, "departure_wall_time": row.identity["departure_wall_time"],
                        "service_day": service_day.isoformat()} for row in rows[:limit]],
            "next_cursor": rows[limit - 1].id if len(rows) > limit else None,
            "coverage": "imported_verified_legs_only", "complete_network": False}


def resolve_configuration(session, configuration, *, service_day: date, static_version: str):
    references = require_references(session, configuration)
    resolved = {}
    for identifier in references:
        row = session.get(CommuteDatedLeg, (identifier, service_day, static_version))
        if row is None:
            raise DomainError("This journey has no verified timetable for the selected date and feed.",
                              409, "commute_dated_reference_unavailable")
        leg = decode_leg(row)
        identity = reference_identity(leg)
        expected_id = str(uuid5(NAMESPACE_URL, "https://helveticlens.ch/commute-reference/" + digest(identity)))
        if (identity != references[identifier].identity or digest(identity) != references[identifier].identity_hash
                or expected_id != identifier):
            raise DomainError("Verified timetable reference is inconsistent.", 503, "commute_catalog_invalid")
        resolved[identifier] = leg
    return resolved


def preview_version(session, configuration, *, service_day, now):
    """Prefer a permitted feed's exact version; otherwise require one unique map.

    Never ask the user to type a static archive identifier or silently choose the
    newest archive while the live service still refers to a different timetable.
    """
    from .commute_sources import SOURCES, read_feed
    versions = set()
    for source in SOURCES:
        try:
            _, _, feed = read_feed(session, source, now=now, require_fresh=True)
            if feed.feed_version:
                versions.add(feed.feed_version)
        except DomainError:
            pass
    if len(versions) == 1:
        return versions.pop()
    if not versions:
        ids = [str(value) for value in configuration.leg_reference_ids]
        versions = set(session.scalars(select(CommuteDatedLeg.static_version).where(
            CommuteDatedLeg.reference_id.in_(ids), CommuteDatedLeg.service_day == service_day)
            .group_by(CommuteDatedLeg.static_version)
            .having(func.count(func.distinct(CommuteDatedLeg.reference_id)) == len(ids)).limit(2)))
        if len(versions) == 1:
            return versions.pop()
    raise DomainError("The journey timetable cannot be selected reliably.", 409,
                      "commute_timetable_ambiguous" if versions else "commute_dated_reference_unavailable")
