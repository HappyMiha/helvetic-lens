"""C2 private configuration and verified-source transition contract.

This module neither resolves user-entered identifiers nor grants feed access.
Only a trusted importer/adapter may supply the resolved leg and normalized event.
"""

import hashlib
import json
import re
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from .transport_reference import ZURICH, Selector, commute_window, intervals_overlap, matches, service_instant
from .transport_static import ResolvedLeg


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class CommuteConfiguration(Contract):
    template_id: Literal["commute-watch"] = "commute-watch"
    template_version: Literal[1] = 1
    name: str = Field(min_length=1, max_length=100)
    # Catalog references resolve independently for each verified service date.
    # UUIDs are not an assertion that an arbitrary trip/stop string is trusted.
    leg_reference_ids: tuple[UUID, ...] = Field(min_length=1, max_length=8)
    weekdays: tuple[StrictInt, ...] = Field(min_length=1, max_length=7)
    window_start: str = Field(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    window_end: str = Field(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    delay_threshold_minutes: int = Field(strict=True, ge=1, le=180)
    delay_reset_minutes: int = Field(strict=True, ge=0, le=179)
    cancellations: bool = Field(default=True, strict=True)
    skipped_boarding_or_alighting: bool = Field(default=True, strict=True)
    service_notices: bool = Field(default=True, strict=True)
    outside_window: Literal["ignore", "digest"] = "ignore"

    @model_validator(mode="after")
    def selections(self):
        if not self.name.strip() or self.window_start == self.window_end:
            raise ValueError("Name the commute and choose distinct wall-time boundaries")
        if len(set(self.leg_reference_ids)) != len(self.leg_reference_ids):
            raise ValueError("Journey leg selections must be distinct")
        if (len(set(self.weekdays)) != len(self.weekdays)
                or any(type(day) is not int or not 0 <= day <= 6 for day in self.weekdays)):
            raise ValueError("Choose distinct weekdays from Monday=0 to Sunday=6")
        if self.delay_reset_minutes >= self.delay_threshold_minutes:
            raise ValueError("The delay reset must be below the alert threshold")
        return self

    def fingerprint(self):
        return digest(self.model_dump(mode="json"))


class Affected(Contract):
    agency_id: str | None = Field(default=None, max_length=256)
    route_id: str | None = Field(default=None, max_length=256)
    direction_id: int | None = Field(default=None, strict=True, ge=0, le=1)
    stop_id: str | None = Field(default=None, max_length=256)
    trip_id: str | None = Field(default=None, max_length=256)
    service_day: date | None = None

    @model_validator(mode="after")
    def valid_selector(self):
        self.selector()
        return self

    def selector(self):
        return Selector(**self.model_dump())


class TransportObservation(Contract):
    source: Literal["swiss_gtfs_trip_updates", "swiss_gtfs_service_alerts"]
    entity_id: str = Field(min_length=1, max_length=256)
    revision_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    observed_at: AwareDatetime
    feed_version: str | None = Field(default=None, min_length=1, max_length=256)
    availability: Literal["present", "missing", "expired"] = "present"
    kind: Literal["delay", "cancelled", "skipped_stop", "notice"] | None = None
    # Only explicit, verified delay/time observations; absent never means zero.
    delay_seconds: int | None = Field(default=None, strict=True, ge=-86400, le=86400)
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    selectors: tuple[Affected, ...] = Field(min_length=1, max_length=100)
    confirmed_served_stop_ids: tuple[str, ...] = Field(default=(), max_length=100)

    @field_validator("observed_at", "valid_from", "valid_until")
    @classmethod
    def utc_times(cls, value):
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def source_capabilities(self):
        if self.confirmed_served_stop_ids and (self.source != "swiss_gtfs_trip_updates"
                or self.kind != "delay" or self.availability != "present"
                or len(set(self.confirmed_served_stop_ids)) != len(self.confirmed_served_stop_ids)
                or any(not value.strip() or len(value) > 256 for value in self.confirmed_served_stop_ids)):
            raise ValueError("Served-stop proof requires distinct explicit trip-update stop identities")
        if not self.entity_id.strip() or self.valid_from >= self.valid_until:
            raise ValueError("An event needs an identity and a positive validity interval")
        if self.availability != "present":
            if self.kind is not None or self.delay_seconds is not None:
                raise ValueError("Disappearance/expiry cannot assert restoration or a delay")
        elif self.kind is None:
            raise ValueError("A present event needs an explicit supported source fact")
        if self.kind == "delay" and self.delay_seconds is None:
            raise ValueError("An explicit delay observation is required")
        if self.kind != "delay" and self.delay_seconds is not None:
            raise ValueError("Delay belongs only to a delay observation")
        if self.source == "swiss_gtfs_service_alerts" and self.kind not in {None, "notice"}:
            raise ValueError("Swiss service-alert text cannot establish a structured transport effect")
        if self.source == "swiss_gtfs_service_alerts" and any(s.trip_id is not None for s in self.selectors):
            raise ValueError("Trip selectors are not supported in the Swiss service-alert profile")
        if self.source == "swiss_gtfs_trip_updates":
            if self.kind == "notice" or any(s.trip_id is None for s in self.selectors):
                raise ValueError("Trip updates require a service-day trip identity")
            if len({(s.trip_id, s.service_day) for s in self.selectors}) != 1:
                raise ValueError("One trip update cannot describe multiple service-day trips")
            if self.kind == "skipped_stop" and any(s.stop_id is None for s in self.selectors):
                raise ValueError("Skipped-stop updates require explicit stop IDs")
            if self.kind == "delay" and any(s.stop_id is None for s in self.selectors):
                raise ValueError("Delay observations require an explicit boarding-stop identity")
        return self


Condition = Literal["normal", "delay_minor", "delay_material", "cancelled", "partial_disruption", "notice", "restored"]


class CommuteCheckpoint(Contract):
    stream_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    observed_at: AwareDatetime
    observation_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    condition: Condition | None
    availability: Literal["present", "missing", "expired", "stale", "unmapped", "invalid_window"]
    immediate_eligible: bool = Field(strict=True)
    intent_window: str | None = None
    episode_active: bool = Field(default=False, strict=True)
    disrupted_stop_ids: tuple[str, ...] = ()


def evaluate_commute(configuration: CommuteConfiguration, reference_id: UUID, leg: ResolvedLeg,
                     observation: TransportObservation, *, monitor_id: UUID, now: datetime,
                     max_age_seconds: int, previous: CommuteCheckpoint | None = None,
                     paused_on: date | None = None, muted=False):
    """One event/service-day development, preserving history through outages.

    Callers persist the returned checkpoint/history atomically and independently
    enforce owner, current configuration/source rights and delivery consent.
    The digest result is a candidate only, never permission to send email.
    """
    if (now.tzinfo is None or now.utcoffset() is None or type(max_age_seconds) is not int
            or not 1 <= max_age_seconds <= 3600 or type(muted) is not bool):
        raise ValueError("Use an aware clock, explicit source freshness bound and boolean mute")
    if reference_id not in configuration.leg_reference_ids:
        raise ValueError("The resolved leg is not selected by this configuration")
    now = now.astimezone(UTC)
    for instant in (leg.departure, leg.arrival):
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("The resolved journey times must be aware")
    if leg.departure.astimezone(UTC) >= leg.arrival.astimezone(UTC):
        raise ValueError("The resolved journey must have positive duration")
    reference = leg.reference
    if type(reference.service_day) is not date or not re.fullmatch(r"[a-f0-9]{64}", leg.archive_sha256):
        raise ValueError("The resolved leg needs its verified service date and archive fingerprint")
    service_start = service_instant(reference.service_day, "00:00:00")
    if any(not service_start <= instant.astimezone(UTC) < service_start + timedelta(days=7)
           for instant in (leg.departure, leg.arrival)):
        raise ValueError("Resolved times fall outside their GTFS service-day offsets")
    stream_id = digest({"monitor": str(monitor_id), "configuration": configuration.fingerprint(),
                        "reference": str(reference_id), "static": reference.static_version,
                        "archive": leg.archive_sha256, "trip": reference.trip_id,
                        "day": reference.service_day.isoformat(), "source": observation.source,
                        "entity": observation.entity_id})
    if previous and previous.stream_id != stream_id:
        raise ValueError("Checkpoint belongs to another private configuration/event/service day")
    observed_hash = digest(observation.model_dump(mode="json"))
    if observation.observed_at > now:
        return {"checkpoint": previous, "transition": "rejected", "delivery": "none", "reason": "future_observation"}
    if previous and observation.observed_at < previous.observed_at:
        return {"checkpoint": previous, "transition": "ignored", "delivery": "none", "reason": "older_observation"}
    if previous and observation.observed_at == previous.observed_at and previous.observation_sha256 != observed_hash:
        raise ValueError("Conflicting observations share the same source timestamp")
    condition = previous.condition if previous else None
    episode_active = previous.episode_active if previous else False
    disrupted_stops = set(previous.disrupted_stop_ids) if previous else set()
    availability, eligible, intersects, window = observation.availability, False, False, None
    reason = observation.availability
    if now - observation.observed_at > timedelta(seconds=max_age_seconds):
        availability, reason = "stale", "stale_source"
    elif observation.valid_until <= now:
        availability, reason = "expired", "validity_ended"
    elif not observation.feed_version or observation.feed_version != reference.static_version:
        availability, reason = "unmapped", "static_version_unverified"
    if availability == "present":
        selectors = [s for s in observation.selectors if matches(reference, s.selector(), feed_version=observation.feed_version)]
        if observation.kind == "skipped_stop":
            selectors = [s for s in selectors if s.stop_id in (reference.stop_ids[0], reference.stop_ids[-1])]
        if observation.kind == "delay":
            selectors = [s for s in selectors if s.stop_id == reference.stop_ids[0]]
        local_departure = leg.departure.astimezone(ZURICH)
        day = local_departure.date()
        if configuration.window_end < configuration.window_start and local_departure.strftime("%H:%M") < configuration.window_end:
            day -= timedelta(days=1)
        try:
            window = commute_window(day, configuration.window_start, configuration.window_end, configuration.weekdays)
        except ValueError:
            availability, reason = "invalid_window", "nonexistent_wall_time"
        intersects = bool(selectors and window and window[0] <= leg.departure < window[1]
                          and intervals_overlap(window, (observation.valid_from, observation.valid_until))
                          and intervals_overlap((leg.departure, leg.arrival), (observation.valid_from, observation.valid_until)))
        if intersects:
            if observation.kind == "cancelled":
                condition = "cancelled"
            elif observation.kind == "skipped_stop":
                condition = "partial_disruption"
                disrupted_stops.update(s.stop_id for s in selectors)
            elif observation.kind == "notice":
                condition = "notice"
            else:
                disrupted_stops.difference_update(observation.confirmed_served_stop_ids)
                seconds = observation.delay_seconds
                material = seconds >= configuration.delay_threshold_minutes * 60
                holding = condition == "delay_material" and seconds > configuration.delay_reset_minutes * 60
                if disrupted_stops:
                    condition = "partial_disruption"
                elif material or holding:
                    condition = "delay_material"
                elif seconds > 0:
                    condition = "delay_minor"
                else:
                    condition = "restored" if episode_active or condition == "restored" else "normal"
            eligible = window[0] <= now < window[1] and observation.valid_from <= now
            reason = "inside_window" if eligible else "outside_window"
            if observation.kind == "delay" and disrupted_stops:
                reason = "skipped_stop_resumption_unconfirmed"
        elif availability == "present":
            reason = "no_journey_intersection"
    old = previous.condition if previous else None
    major = {"delay_material", "cancelled", "partial_disruption", "notice"}
    if availability == "present" and intersects:
        if condition in major:
            episode_active = True
        elif condition in {"normal", "restored"}:
            episode_active = False
    transition = ("restored" if condition == "restored" and old != condition else
                  "material" if condition != old and (condition in major or old in major) else "stable")
    if availability != "present" or not intersects:
        transition = "unavailable" if availability != "present" else "irrelevant"
    selected = (configuration.cancellations if condition == "cancelled" else
                configuration.skipped_boarding_or_alighting if condition == "partial_disruption" else
                configuration.service_notices if condition == "notice" else True)
    window_key = window[0].isoformat() if window else None
    intent_window = previous.intent_window if previous else None
    becoming_relevant = bool(eligible and condition in major and previous and intent_window != window_key)
    delivery = "none"
    if availability == "present" and intersects and selected and not muted and paused_on != now.astimezone(ZURICH).date():
        if eligible and (transition in {"material", "restored"} or becoming_relevant):
            delivery = "immediate"
        elif not eligible and transition in {"material", "restored"} and configuration.outside_window == "digest":
            delivery = "digest_candidate"
    checkpoint = CommuteCheckpoint(stream_id=stream_id, observed_at=observation.observed_at,
                                    observation_sha256=observed_hash, condition=condition,
                                    availability=availability, immediate_eligible=eligible,
                                    intent_window=window_key if delivery == "immediate" else intent_window,
                                    episode_active=episode_active, disrupted_stop_ids=tuple(sorted(disrupted_stops)))
    return {"checkpoint": checkpoint, "transition": transition, "delivery": delivery, "reason": reason,
            "priority": "urgent" if delivery == "immediate" and condition == "cancelled" else "normal"}


def evaluate_journey(configuration: CommuteConfiguration, legs: dict[UUID, ResolvedLeg],
                     observation: TransportObservation, *, monitor_id: UUID, now: datetime,
                     max_age_seconds: int, previous: dict[UUID, CommuteCheckpoint] | None = None,
                     paused_on: date | None = None, muted=False):
    """Consolidate one normalized source event across the selected journey legs.

    Preserve each segment's reasons/checkpoint but emit at most one notification
    candidate. Missing references cannot silently turn a partial plan into verified
    full journey coverage. Persistence/outbox ownership remains the caller's job.
    """
    selected = set(configuration.leg_reference_ids)
    if set(legs) != selected or previous and set(previous) - selected:
        raise ValueError("Resolve exactly the selected journey references before evaluation")
    contributions = {
        str(identifier): evaluate_commute(configuration, identifier, legs[identifier], observation,
                                          monitor_id=monitor_id, now=now, max_age_seconds=max_age_seconds,
                                          previous=(previous or {}).get(identifier),
                                          paused_on=paused_on, muted=muted)
        for identifier in configuration.leg_reference_ids
    }
    deliveries = {result["delivery"] for result in contributions.values()}
    delivery = "immediate" if "immediate" in deliveries else "digest_candidate" if "digest_candidate" in deliveries else "none"
    development = digest({"monitor": str(monitor_id), "configuration": configuration.fingerprint(),
                          "source": observation.source, "entity": observation.entity_id,
                          "service_days": sorted({leg.reference.service_day.isoformat() for leg in legs.values()})})
    return {"development_id": development, "contributions": contributions, "delivery": delivery,
            "priority": "urgent" if any(result.get("priority") == "urgent" for result in contributions.values()) else "normal"}
