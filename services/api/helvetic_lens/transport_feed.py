"""Bounded binary GTFS snapshots and explicit facts for a verified journey.

No HTTP, credentials or source grant. Keep the original bytes in a permitted
source store; deterministic entity encodings are fingerprints, not originals.
Unsupported data never establishes on-time running or recovery.
"""

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import cached_property
from typing import Literal

from google.protobuf.message import DecodeError
from google.transit import gtfs_realtime_pb2 as gtfs

from .commute_contracts import Affected, TransportObservation, digest
from .transport_reference import intervals_overlap, matches
from .transport_static import ResolvedLeg, gtfs_date, identifier

Source = Literal["swiss_gtfs_trip_updates", "swiss_gtfs_service_alerts"]
TRIPS = "swiss_gtfs_trip_updates"
ALERTS = "swiss_gtfs_service_alerts"
MAX_BYTES = 32 * 1024 * 1024
MAX_ENTITIES = 50_000


def instant(value):
    try:
        return datetime.fromtimestamp(value, UTC)
    except (ValueError, OverflowError, OSError) as exc:
        raise ValueError("Unsupported GTFS timestamp") from exc


@dataclass(frozen=True)
class FeedEntity:
    source_id: str
    # Trip developments survive a provider's entity-id change within a service day.
    development_id: str
    sha256: str
    encoded: bytes
    trip_id: str | None = None
    service_day: date | None = None


@dataclass(frozen=True)
class FeedSnapshot:
    source: Source
    observed_at: datetime
    feed_version: str | None
    sha256: str
    entities: tuple[FeedEntity, ...]

    @cached_property
    def entity_set(self):
        return frozenset(self.entities)


@dataclass(frozen=True)
class Projection:
    observation: TransportObservation | None
    reason: str
    # Exact source language and text, never generated translations or HTML.
    header: tuple[tuple[str | None, str], ...] = ()
    description: tuple[tuple[str | None, str], ...] = ()
    active_periods: tuple[tuple[datetime | None, datetime | None], ...] = ()


def translations(value):
    if len(value.translation) > 20:
        raise ValueError("Too many source language editions")
    result, languages = [], set()
    for edition in value.translation:
        language = edition.language if edition.HasField("language") else None
        if language is not None and (not language.strip() or len(language) > 35):
            raise ValueError("Invalid source language")
        if language in languages or len(edition.text.encode("utf-8")) > 32768:
            raise ValueError("Duplicate language or oversized source text")
        languages.add(language)
        result.append((language, edition.text))
    return tuple(result)


def decode_feed(payload: bytes, *, source: Source, received_at: datetime) -> FeedSnapshot:
    """Validate the whole replacement before exposing any disappearance.

    Invalid/unknown protobuf fields or enum values reject this snapshot, leaving
    the previous snapshot intact in the caller. Unsupported *known* capabilities
    stay as present entities and receive an explicit projection reason.
    """
    if source not in (TRIPS, ALERTS) or received_at.tzinfo is None or received_at.utcoffset() is None:
        raise ValueError("Use a supported source and aware receipt clock")
    if type(payload) is not bytes or not 0 < len(payload) <= MAX_BYTES:
        raise ValueError("Empty or oversized GTFS response")
    feed = gtfs.FeedMessage()
    try:
        feed.ParseFromString(payload)
    except DecodeError as exc:
        raise ValueError("Invalid binary GTFS response") from exc
    if not feed.IsInitialized():
        raise ValueError("Missing required GTFS fields")
    original = feed.SerializeToString(deterministic=True)
    feed.DiscardUnknownFields()
    if original != feed.SerializeToString(deterministic=True):
        raise ValueError("Unsupported GTFS fields or enum values")
    header = feed.header
    if (header.gtfs_realtime_version != "2.0" or not header.HasField("incrementality")
            or header.incrementality != gtfs.FeedHeader.FULL_DATASET or not header.HasField("timestamp")):
        raise ValueError("Require timestamped GTFS 2.0 FULL_DATASET")
    observed = instant(header.timestamp)
    if observed > received_at.astimezone(UTC):
        raise ValueError("Future source timestamp")
    version = identifier(header.feed_version) if header.HasField("feed_version") else None
    if len(feed.entity) > MAX_ENTITIES:
        raise ValueError("Too many GTFS entities")
    records, ids, trips = [], set(), set()
    for entity in feed.entity:
        entity_id = identifier(entity.id)
        if entity_id in ids or entity.HasField("is_deleted"):
            raise ValueError("Duplicate entity or deletion in FULL_DATASET")
        ids.add(entity_id)
        kinds = [field.name for field, _ in entity.ListFields() if field.name != "id"]
        if kinds != (["trip_update"] if source == TRIPS else ["alert"]):
            raise ValueError("Mixed or unsupported feed entity type")
        development = entity_id
        if source == TRIPS:
            update = entity.trip_update
            trip = update.trip
            identifier(trip.trip_id)
            day = gtfs_date(trip.start_date)
            if trip.HasField("route_id"):
                identifier(trip.route_id)
            if trip.HasField("direction_id") and trip.direction_id not in (0, 1):
                raise ValueError("Invalid trip direction")
            if update.HasField("timestamp") and instant(update.timestamp) > observed:
                raise ValueError("Trip measured after feed timestamp")
            identity = (trip.trip_id, day.isoformat(), trip.start_time)
            if identity in trips:
                raise ValueError("Conflicting updates for the same trip instance")
            trips.add(identity)
            development = digest({"trip": identity})
            if len(update.stop_time_update) > 2000:
                raise ValueError("Too many trip stop updates")
            sequences = []
            for stop in update.stop_time_update:
                if not stop.HasField("stop_sequence") and not stop.HasField("stop_id"):
                    raise ValueError("Unidentified realtime stop")
                if stop.HasField("stop_id"):
                    identifier(stop.stop_id)
                if stop.HasField("stop_sequence"):
                    sequences.append(stop.stop_sequence)
                for field in ("arrival", "departure"):
                    if not stop.HasField(field):
                        continue
                    timing = getattr(stop, field)
                    if timing.HasField("time"):
                        instant(timing.time)
                    if timing.HasField("uncertainty") and timing.uncertainty < 0:
                        raise ValueError("Negative prediction uncertainty")
            if sequences != sorted(set(sequences)):
                raise ValueError("Unordered or repeated stop sequences")
        else:
            alert = entity.alert
            if not 1 <= len(alert.informed_entity) <= 100 or len(alert.active_period) > 100:
                raise ValueError("Missing or oversized alert scope")
            for period in alert.active_period:
                start = instant(period.start) if period.HasField("start") else None
                end = instant(period.end) if period.HasField("end") else None
                if start is None and end is None or start is not None and end is not None and start >= end:
                    raise ValueError("Invalid source active period")
            for field in ("header_text", "description_text", "url", "tts_header_text", "tts_description_text"):
                translations(getattr(alert, field))
        encoded = entity.SerializeToString(deterministic=True)
        records.append(FeedEntity(entity_id, development, hashlib.sha256(encoded).hexdigest(), encoded,
                                  trip.trip_id if source == TRIPS else None, day if source == TRIPS else None))
    return FeedSnapshot(source, observed, version, hashlib.sha256(payload).hexdigest(), tuple(records))


def snapshot_changes(previous: FeedSnapshot, current: FeedSnapshot):
    """Protocol state only: a missing entity is never a restored service.

    Caller applies this only after current permission/freshness checks and stores
    the snapshot and history atomically. An older/conflicting snapshot cannot
    replace the accepted one. A changed static version requires a new mapping.
    """
    if previous.source != current.source:
        raise ValueError("Cannot compare different feed sources")
    if current.observed_at < previous.observed_at:
        return {"state": "older", "missing": (), "present": ()}
    if current.observed_at == previous.observed_at:
        if current.sha256 != previous.sha256:
            raise ValueError("Conflicting feed responses at one timestamp")
        return {"state": "replay", "missing": (), "present": ()}
    if previous.feed_version != current.feed_version:
        return {"state": "static_version_changed", "missing": (), "present": current.entities}
    current_ids = {entity.development_id for entity in current.entities}
    return {"state": "replacement", "present": current.entities,
            "missing": tuple(entity for entity in previous.entities if entity.development_id not in current_ids)}


def project_entity(snapshot: FeedSnapshot, entity: FeedEntity, leg: ResolvedLeg) -> Projection:
    """Map explicit source facts; static times take precedence over delay numbers.

    Only exact sequence-mapped stops are projected. This does not propagate a
    previous stop's delay or a trip-level estimate to the user's boarding stop.
    Those capabilities need a separately verified provider contract.
    """
    if entity not in snapshot.entity_set:
        raise ValueError("Entity does not belong to this snapshot")
    if snapshot.feed_version is None or snapshot.feed_version != leg.reference.static_version:
        return Projection(None, "static_version_unverified")
    message = gtfs.FeedEntity.FromString(entity.encoded)
    reference = leg.reference
    base = dict(source=snapshot.source, entity_id=entity.development_id, revision_sha256=entity.sha256,
                observed_at=snapshot.observed_at, feed_version=snapshot.feed_version)
    if snapshot.source == ALERTS:
        alert = message.alert
        header, description = translations(alert.header_text), translations(alert.description_text)
        periods = tuple((instant(p.start) if p.HasField("start") else None,
                         instant(p.end) if p.HasField("end") else None) for p in alert.active_period)
        evidence = dict(header=header, description=description, active_periods=periods)
        selectors = []
        for selector in alert.informed_entity:
            # Dropping a selector constraint would incorrectly broaden the alert.
            if any(f.name not in {"agency_id", "route_id", "direction_id", "stop_id"}
                   for f, _ in selector.ListFields()):
                return Projection(None, "unsupported_alert_selector", **evidence)
            try:
                affected = Affected(**{f.name: value for f, value in selector.ListFields()})
            except ValueError:
                return Projection(None, "invalid_alert_selector", **evidence)
            selectors.append(affected)
        if not any(matches(reference, s.selector(), feed_version=snapshot.feed_version) for s in selectors):
            return Projection(None, "unrelated_journey", **evidence)
        # Clamp unbounded source intervals only to this explicit journey's range.
        # Retain the original open endpoints separately in evidence.
        ranges = [(start or min(snapshot.observed_at, leg.departure), end or leg.arrival)
                  for start, end in (periods or ((None, None),))]
        ranges = [(start, end) for start, end in ranges if start < end
                  and intervals_overlap((start, end), (leg.departure, leg.arrival))]
        if not ranges:
            return Projection(None, "outside_journey_time", **evidence)
        # Prefer the currently active range. Never bridge gaps between periods.
        start, end = min(ranges, key=lambda p: (not p[0] <= snapshot.observed_at < p[1], p[0]))
        return Projection(TransportObservation(**base, kind="notice", selectors=tuple(selectors),
                                               valid_from=start, valid_until=end), "official_notice", **evidence)
    update, trip = message.trip_update, message.trip_update.trip
    affected = Affected(trip_id=trip.trip_id, service_day=gtfs_date(trip.start_date),
                        route_id=trip.route_id if trip.HasField("route_id") else None,
                        direction_id=trip.direction_id if trip.HasField("direction_id") else None)
    if not matches(reference, affected.selector(), feed_version=snapshot.feed_version):
        return Projection(None, "unrelated_journey")
    if trip.HasField("start_time"):
        return Projection(None, "trip_start_time_mapping_required")
    if update.HasField("timestamp"):
        # Preserve actual measurement freshness; a new feed must not freshen it.
        base["observed_at"] = instant(update.timestamp)
    base.update(valid_from=min(base["observed_at"], leg.departure), valid_until=leg.arrival)
    if base["valid_from"] >= base["valid_until"]:
        return Projection(None, "journey_ended")
    if trip.schedule_relationship == gtfs.TripDescriptor.CANCELED:
        return Projection(TransportObservation(**base, kind="cancelled", selectors=(affected,)), "explicit_cancellation")
    if trip.schedule_relationship != gtfs.TripDescriptor.SCHEDULED:
        return Projection(None, "unsupported_trip_relationship")
    if update.HasField("trip_properties"):
        return Projection(None, "trip_properties_mapping_required")
    if (len(leg.stop_sequences) != len(reference.stop_ids) or not leg.stop_sequences
            or tuple(sorted(set(leg.stop_sequences))) != leg.stop_sequences):
        return Projection(None, "stop_sequence_mapping_required")
    mapped = dict(zip(leg.stop_sequences, reference.stop_ids, strict=True))
    selected = {}
    for stop in update.stop_time_update:
        if not stop.HasField("stop_sequence"):
            return Projection(None, "stop_sequence_mapping_required")
        if stop.stop_sequence not in mapped:
            continue
        stop_id = mapped[stop.stop_sequence]
        if stop.HasField("stop_id") and stop.stop_id != stop_id:
            return Projection(None, "conflicting_stop_identity")
        if stop.HasField("stop_time_properties"):
            return Projection(None, "stop_change_mapping_required")
        selected[stop.stop_sequence] = stop
    endpoints = (leg.stop_sequences[0], leg.stop_sequences[-1])
    skipped = [seq for seq in endpoints if seq in selected
               and selected[seq].schedule_relationship == gtfs.TripUpdate.StopTimeUpdate.SKIPPED]
    if skipped:
        return Projection(TransportObservation(**base, kind="skipped_stop", selectors=tuple(
            Affected(**affected.model_dump(exclude_none=True), stop_id=mapped[seq]) for seq in skipped)), "explicit_skipped_stop")
    boarding = selected.get(endpoints[0])
    if (boarding is None or boarding.schedule_relationship != gtfs.TripUpdate.StopTimeUpdate.SCHEDULED
            or not boarding.HasField("departure")):
        return Projection(None, "boarding_prediction_unavailable")
    departure = boarding.departure
    if departure.HasField("time"):
        delay = int((instant(departure.time) - leg.departure).total_seconds())
    elif departure.HasField("delay"):
        delay = departure.delay
    else:
        return Projection(None, "boarding_prediction_unavailable")
    if not -86400 <= delay <= 86400:
        return Projection(None, "delay_outside_supported_range")
    selector = Affected(**affected.model_dump(exclude_none=True), stop_id=reference.stop_ids[0])
    served = tuple(mapped[seq] for seq in endpoints if seq in selected
                   and selected[seq].schedule_relationship == gtfs.TripUpdate.StopTimeUpdate.SCHEDULED
                   and any(selected[seq].HasField(field)
                           and (getattr(selected[seq], field).HasField("time")
                                or getattr(selected[seq], field).HasField("delay"))
                           for field in ("arrival", "departure")))
    return Projection(TransportObservation(**base, kind="delay", delay_seconds=delay, selectors=(selector,),
                                           confirmed_served_stop_ids=tuple(dict.fromkeys(served))), "explicit_departure")
