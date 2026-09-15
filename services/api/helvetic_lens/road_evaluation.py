"""Pure temporal/materiality decisions after source rights and topology review.

The caller must use fresh, permission-checked evidence. Expiry or withdrawal is a
source-state transition requiring prior-event context, never physical all-clear.
"""

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .road_feed import RoadPeriod, RoadRecord
from .road_recurrence import (
    HORIZON_DAYS,
    MAX_STEPS,
    MAX_WINDOWS,
    ExpansionBudget,
    ExpansionLimit,
    expand,
    has_recurrence,
)
from .road_topology import RoadIntersection

RoadKind = Literal["road_closure", "carriageway_closure", "lane_restriction", "congestion", "accident", "roadworks"]
TIME_UNSUPPORTED = {"validity", "validity_period", "recurring_period", "validity_status"}


class RoadMateriality(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    event_kinds: tuple[RoadKind, ...] = ("road_closure", "carriageway_closure", "lane_restriction", "congestion", "accident", "roadworks")
    minimum_delay_seconds: int = Field(default=900, ge=0, le=86400)
    include_planned: bool = True

    @model_validator(mode="after")
    def distinct_kinds(self):
        if not self.event_kinds or len(set(self.event_kinds)) != len(self.event_kinds):
            raise ValueError("Select distinct road event types")
        return self


@dataclass(frozen=True)
class RoadTemporalState:
    phase: Literal["active", "planned", "inactive", "expired", "suspended", "withdrawn", "ended", "unknown"]
    reason: str
    window: RoadPeriod | None = None


@dataclass(frozen=True)
class RoadDecision:
    state: Literal["eligible", "filtered", "unknown", "transition"]
    reason: str
    temporal: RoadTemporalState


def _earliest_end(*values):
    finite = [value for value in values if value is not None]
    return min(finite) if finite else None


def _merge(windows):
    result = []
    for window in sorted(windows, key=lambda item: item.start):
        if not result or (result[-1].end is not None and result[-1].end < window.start):
            result.append(window)
        else:
            previous = result.pop()
            end = None if previous.end is None or window.end is None else max(previous.end, window.end)
            result.append(RoadPeriod(previous.start, end))
    return result


def _windows(validity, *, lower=None, upper=None, budget=None):
    overall = validity.overall
    groups = []
    for entries in (validity.periods or (overall,), validity.exceptions):
        bounded = []
        for period in entries:
            if lower is not None:
                bounded.extend(expand(period, overall, lower, upper, budget))
                if len(bounded) > MAX_WINDOWS:
                    raise ExpansionLimit("Recurring schedule exceeds combined interval budget")
                continue
            start = max(overall.start, period.start or overall.start)
            end = _earliest_end(overall.end, period.end)
            if end is None or end > start:
                bounded.append(RoadPeriod(start, end))
        groups.append(_merge(bounded))
    result, exception_index = [], 0
    for window in groups[0]:
        cursor = window.start
        # Both groups are disjoint and ordered after merging. Keep one cursor
        # so a recurring exception set does not create a quadratic cross-product.
        while exception_index < len(groups[1]):
            exception = groups[1][exception_index]
            if exception.end is not None and exception.end <= cursor:
                exception_index += 1
                continue
            if window.end is not None and exception.start >= window.end:
                break
            if exception.start > cursor:
                result.append(RoadPeriod(cursor, _earliest_end(exception.start, window.end)))
                if len(result) > MAX_WINDOWS:
                    raise ExpansionLimit("Recurring exclusions exceed interval budget")
            if exception.end is None or (window.end is not None and exception.end >= window.end):
                cursor = None
                break
            cursor = max(cursor, exception.end)
            exception_index += 1
        if cursor is not None and (window.end is None or cursor < window.end):
            result.append(RoadPeriod(cursor, window.end))
            if len(result) > MAX_WINDOWS:
                raise ExpansionLimit("Recurring exclusions exceed interval budget")
    return tuple(result)


def temporal_state(record: RoadRecord, *, now: datetime, budget=None) -> RoadTemporalState:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Use an aware road evaluation clock")
    now = now.astimezone(UTC)
    if record.cancelled is True:
        return RoadTemporalState("withdrawn", "source_notice_withdrawn")
    if record.ended is True:
        return RoadTemporalState("ended", "source_notice_ended")
    validity = record.validity
    if "validity" in record.unsupported or "validity_status" in record.unsupported:
        return RoadTemporalState("unknown", "validity_extension_unsupported")
    if validity.status == "suspended":
        if validity.overrunning:
            return RoadTemporalState("unknown", "contradictory_validity")
        return RoadTemporalState("suspended", "source_suspended")
    # DATEX explicitly overrides the time specification for active/suspended.
    # Overrunning expressly means still in progress beyond the previous duration.
    if validity.status == "active" or validity.overrunning:
        return RoadTemporalState("active", "source_overrunning" if validity.overrunning else "source_active_override")
    if validity.status != "definedByValidityTimeSpec" or TIME_UNSUPPORTED.intersection(record.unsupported):
        return RoadTemporalState("unknown", "validity_schedule_unsupported")
    if validity.overall.end is not None and now >= validity.overall.end:
        return RoadTemporalState("expired", "validity_window_expired")
    lower = upper = None
    if has_recurrence(validity):
        if budget is not None and budget.remaining <= 0:
            return RoadTemporalState("unknown", "recurrence_evaluation_limit")
        local_budget = ExpansionBudget(min(MAX_STEPS, budget.remaining) if budget is not None else MAX_STEPS)
        available_steps = local_budget.remaining
        try:
            day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            lower, upper = day - timedelta(days=HORIZON_DAYS), day + timedelta(days=HORIZON_DAYS)
            windows = _windows(validity, lower=lower, upper=upper, budget=local_budget)
        except (ExpansionLimit, OverflowError):
            return RoadTemporalState("unknown", "recurrence_evaluation_limit")
        finally:
            if budget is not None:
                budget.remaining -= available_steps - max(0, local_budget.remaining)
    else:
        windows = _windows(validity)
    for window in windows:
        if window.start <= now and (window.end is None or now < window.end):
            if (lower is not None and window.start == lower and validity.overall.start < lower
                    or upper is not None and window.end == upper
                    and (validity.overall.end is None or validity.overall.end > upper)):
                return RoadTemporalState("unknown", "recurrence_interval_incomplete")
            return RoadTemporalState("active", "within_validity_window", window)
        if window.start > now:
            if upper is not None and window.end == upper and (validity.overall.end is None or validity.overall.end > upper):
                return RoadTemporalState("unknown", "recurrence_interval_incomplete")
            return RoadTemporalState("planned", "next_validity_window", window)
    if upper is not None and (validity.overall.end is None or validity.overall.end > upper):
        return RoadTemporalState("unknown", "recurrence_lookahead_exhausted")
    if windows and all(window.end is not None and window.end <= now for window in windows):
        return RoadTemporalState("expired", "validity_windows_finished")
    return RoadTemporalState("inactive", "excluded_by_validity")


def evaluate_record(record: RoadRecord, intersection: RoadIntersection, preferences: RoadMateriality,
                    *, now: datetime, temporal=None) -> RoadDecision:
    if record.confidentiality != "noRestriction":
        return RoadDecision("unknown", "restricted_source_record", RoadTemporalState("unknown", "source_visibility_denied"))
    temporal = temporal or temporal_state(record, now=now)
    if intersection.state == "no_match":
        return RoadDecision("filtered", "outside_selected_corridor_direction", temporal)
    if intersection.state == "unknown":
        return RoadDecision("unknown", intersection.reason, temporal)
    unsupported = set(record.unsupported)
    if record.validity.status in {"active", "suspended"}:
        unsupported.difference_update({"recurring_period", "validity_period"})
    if unsupported or temporal.phase == "unknown":
        return RoadDecision("unknown", "unsupported_source_capability", temporal)
    if temporal.phase in {"withdrawn", "ended", "expired", "suspended"} or record.kind == "source_clearance":
        return RoadDecision("transition", "requires_previous_event_context", temporal)
    if temporal.phase == "inactive":
        return RoadDecision("filtered", "outside_validity_window", temporal)
    if record.kind not in preferences.event_kinds:
        return RoadDecision("filtered", "event_type_not_selected", temporal)
    if temporal.phase == "planned" and not preferences.include_planned:
        return RoadDecision("filtered", "planned_events_disabled", temporal)
    if record.kind == "congestion":
        delay = record.delay_seconds
        if delay is None or not math.isfinite(delay) or delay < 0:
            return RoadDecision("unknown", "numeric_delay_unavailable", temporal)
        if delay < preferences.minimum_delay_seconds:
            return RoadDecision("filtered", "below_delay_threshold", temporal)
    if record.probability not in {"certain", "probable", "riskOf"}:
        return RoadDecision("unknown", "source_probability_unsupported", temporal)
    return RoadDecision("eligible", "selected_material_road_event" if record.probability == "certain"
                        else "potential_material_road_event", temporal)
