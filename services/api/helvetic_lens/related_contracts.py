"""Versioned association rule; supplied facts must come from authorized readers.

This module cannot grant source rights or create a geographic binding. Matching
place/time means a possible relationship, never common cause, merged authority,
shared review or a source all-clear. Persistence and private reader adapters own
authorization and revalidation; browser-supplied facts are not trusted inputs.
"""
import json
from datetime import UTC, datetime
from hashlib import sha256
from itertools import combinations
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

RULE_VERSION = "location-time-association-v1"
MAX_MEMBERS = 12
Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Identifier = Annotated[str, Field(min_length=1, max_length=256, pattern=r"^\S(?:.*\S)?$")]


def fingerprint(value):
    def encode(item):
        if isinstance(item, datetime):
            if item.tzinfo is None or item.utcoffset() is None:
                raise ValueError("Use timezone-aware evidence clocks")
            return item.astimezone(UTC).isoformat()
        if isinstance(item, UUID):
            return str(item)
        raise TypeError("Unsupported association proof value")
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=encode).encode()).hexdigest()


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class EventReference(Frozen):
    domain: Literal["warnings", "river", "traffic"]
    monitor_id: UUID
    # Exact private row id: RiverChange.id, HazardDevelopment.id or RoadDevelopment.id.
    event_id: UUID
    revision: int = Field(ge=1)
    evidence_hash: Hash


class AuthorityReference(Frozen):
    namespace: Identifier
    identifier: Identifier


class PlaceBinding(Frozen):
    """An exact feature-to-area binding, separately reviewed from source access."""
    id: UUID
    source_feature: AuthorityReference
    source_revision: Hash
    place_namespace: Literal["swisstopo:bfs_municipality", "swisstopo:hazard_area"]
    place_id: Identifier
    boundary_version: Identifier
    boundary_hash: Hash
    evidence_hash: Hash
    accepted_at: datetime
    valid_until: datetime
    revoked_at: datetime | None = None

    @model_validator(mode="after")
    def clocks(self):
        for value in (self.accepted_at, self.valid_until, self.revoked_at):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError("Geographic bindings require explicit timezones")
        if self.valid_until <= self.accepted_at:
            raise ValueError("Invalid geographic-binding lifetime")
        return self

    def place_key(self):
        return self.place_namespace, self.place_id, self.boundary_version, self.boundary_hash


class EventFact(Frozen):
    reference: EventReference
    authority: AuthorityReference
    source_feature: AuthorityReference
    source_revision: Hash
    # Set only after the domain reader and permission/retention checks succeed.
    availability: Literal["available", "unavailable"]
    source_state: Identifier
    time_kind: Literal["interval", "instant", "unknown"]
    starts_at: datetime | None
    ends_at: datetime | None
    place: PlaceBinding | None

    @model_validator(mode="after")
    def interval(self):
        for value in (self.starts_at, self.ends_at):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError("Events require explicit source timezones")
        if self.starts_at is not None and self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("Invalid source validity interval")
        if self.time_kind == "instant" and (self.starts_at is None or self.ends_at is not None):
            raise ValueError("A source observation instant is a point, not an invented duration")
        return self


class Association(Frozen):
    rule_version: Literal["location-time-association-v1"] = RULE_VERSION
    state: Literal["possible", "no_match", "unknown"]
    reason: Literal["same_verified_area_and_overlapping_time", "same_event", "source_unavailable",
        "geography_unavailable", "geography_changed", "different_places", "time_unknown", "different_times"]
    # Provenance is emitted only for a permitted positive relationship.
    left: EventReference | None = None
    right: EventReference | None = None
    bindings: tuple[UUID, UUID] | None = None
    place_key: tuple[str, str, str, str] | None = None
    overlap_start: datetime | None = None
    overlap_end: datetime | None = None
    overlap_kind: Literal["interval", "instant"] | None = None
    proof_hash: Hash | None = None


def _binding_problem(fact, now):
    place = fact.place
    if place is None or place.revoked_at is not None or not place.accepted_at <= now < place.valid_until:
        return "geography_unavailable"
    if place.source_feature != fact.source_feature or place.source_revision != fact.source_revision:
        return "geography_changed"
    return None


def associate(left: EventFact, right: EventFact, *, now: datetime) -> Association:
    """No I/O, mutation or inference from names, code ordering or detection time."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Use an aware association clock")
    # Revalidate even model_copy/model_construct callers at the internal boundary.
    left = EventFact.model_validate(left.model_dump(mode="python"))
    right = EventFact.model_validate(right.model_dump(mode="python"))
    if left.availability != "available" or right.availability != "available":
        return Association(state="unknown", reason="source_unavailable")
    if left.authority == right.authority:
        return Association(state="no_match", reason="same_event")
    for fact in (left, right):
        if issue := _binding_problem(fact, now):
            return Association(state="unknown", reason=issue)
    assert left.place is not None and right.place is not None
    if left.place.place_key()[:2] != right.place.place_key()[:2]:
        return Association(state="no_match", reason="different_places")
    if left.place.place_key() != right.place.place_key():
        return Association(state="unknown", reason="geography_changed")
    if any(f.time_kind == "unknown" or f.starts_at is None or
           (f.time_kind == "interval" and f.ends_at is None) for f in (left, right)):
        return Association(state="unknown", reason="time_unknown")
    overlap_kind = "instant" if "instant" in (left.time_kind, right.time_kind) else "interval"
    if overlap_kind == "instant":
        point, other = (left, right) if left.time_kind == "instant" else (right, left)
        start = end = point.starts_at
        matches = other.starts_at == start if other.time_kind == "instant" else other.starts_at <= start < other.ends_at
        if not matches:
            return Association(state="no_match", reason="different_times")
    else:
        start, end = max(left.starts_at, right.starts_at), min(left.ends_at, right.ends_at)
        if start >= end:
            return Association(state="no_match", reason="different_times")
    # Stable under caller ordering and offsets; include exact source/binding
    # evidence identities so a correction cannot reuse an old association proof.
    facts = sorted((left, right), key=lambda item: item.reference.model_dump_json())
    payload = {
        "rule": RULE_VERSION,
        "facts": [item.model_dump(mode="python") for item in facts],
        "overlap": [start.astimezone(UTC).isoformat(), end.astimezone(UTC).isoformat()],
    }
    return Association(state="possible", reason="same_verified_area_and_overlapping_time",
        left=facts[0].reference, right=facts[1].reference, bindings=(facts[0].place.id, facts[1].place.id),
        place_key=left.place.place_key(), overlap_start=start.astimezone(UTC),
        overlap_end=end.astimezone(UTC), overlap_kind=overlap_kind, proof_hash=fingerprint(payload))


def story_associations(facts: tuple[EventFact, ...], *, now: datetime) -> tuple[Association, ...]:
    """Check every pair; a time/place chain is not a shared three-source story."""
    if not 2 <= len(facts) <= MAX_MEMBERS:
        raise ValueError("Choose between two and twelve events")
    if len({fact.reference for fact in facts}) != len(facts):
        raise ValueError("Duplicate story member")
    if len({fact.reference.domain for fact in facts}) < 2:
        raise ValueError("Choose events from multiple Monitoring directions")
    return tuple(associate(left, right, now=now) for left, right in combinations(facts, 2))
