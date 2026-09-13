"""C2 pure reference checks; no live connector or unverified identifier inference.

Legs and parent IDs must come from a verified, immutable static timetable snapshot,
not a caller's unvalidated configuration. The eventual API resolves those records.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

ZURICH = ZoneInfo("Europe/Zurich")


def service_seconds(value: str) -> int:
    """Bound our supported service offsets to one week; preserve >24-hour times."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,3}:[0-5]\d:[0-5]\d", value):
        raise ValueError("Invalid GTFS service time")
    hours, minutes, seconds = map(int, value.split(":"))
    if hours >= 168:
        raise ValueError("Service offset exceeds supported seven-day bound")
    return hours * 3600 + minutes * 60 + seconds


def service_instant(day: date, value: str, *, timezone: ZoneInfo = ZURICH) -> datetime:
    """GTFS elapsed time from noon minus 12h, calculated on the UTC timeline."""
    noon = datetime.combine(day, time(12), timezone).astimezone(UTC)
    return noon - timedelta(hours=12) + timedelta(seconds=service_seconds(value))


def _wall_candidates(day: date, value: str) -> list[datetime]:
    if not isinstance(value, str) or not re.fullmatch(r"[0-2]\d:[0-5]\d", value):
        raise ValueError("Invalid commute wall time")
    hours, minutes = map(int, value.split(":"))
    if hours > 23:
        raise ValueError("Invalid commute wall time")
    naive = datetime.combine(day, time(hours, minutes))
    candidates = set()
    for fold in (0, 1):
        instant = naive.replace(tzinfo=ZURICH, fold=fold).astimezone(UTC)
        if instant.astimezone(ZURICH).replace(tzinfo=None) == naive:
            candidates.add(instant)
    if not candidates:
        raise ValueError("Commute boundary does not exist on this DST date")
    return sorted(candidates)


def commute_window(day: date, start: str, end: str, weekdays: tuple[int, ...]):
    """Weekday belongs to window's local start date; an overnight end is next day.

    At an autumn clock repeat include both occurrences. A spring gap requires an
    explicit user correction rather than silently moving the saved departure.
    """
    if (
        not weekdays
        or len(set(weekdays)) != len(weekdays)
        or any(type(d) is not int or d < 0 or d > 6 for d in weekdays)
    ):
        raise ValueError("Choose distinct weekdays from Monday=0 through Sunday=6")
    # Validate even when today is disabled: malformed saved settings cannot hide.
    starts = _wall_candidates(day, start)
    if start == end:
        raise ValueError("A commute window must have distinct start and end times")
    end_day = day + timedelta(days=int(end < start))
    ends = _wall_candidates(end_day, end)
    if day.weekday() not in weekdays:
        return None
    return starts[0], ends[-1]


def intervals_overlap(left: tuple[datetime, datetime], right: tuple[datetime, datetime]) -> bool:
    """Half-open intervals: an event ending at departure is outside the window."""
    for start, end in (left, right):
        if any(t.tzinfo is None or t.utcoffset() is None for t in (start, end)):
            raise ValueError("Interval timestamps must be timezone aware")
        if start.astimezone(UTC) >= end.astimezone(UTC):
            raise ValueError("Interval must have positive duration")
    return max(left[0].astimezone(UTC), right[0].astimezone(UTC)) < min(
        left[1].astimezone(UTC), right[1].astimezone(UTC)
    )


@dataclass(frozen=True)
class VerifiedLeg:
    static_version: str
    agency_id: str
    route_id: str
    trip_id: str
    service_day: date
    direction_id: int | None
    # Exact selected segment only; stops earlier/later on the trip are excluded.
    stop_ids: tuple[str, ...]
    # Only parent IDs explicitly provided by this static version, never prefixes.
    parent_stop_ids: tuple[str, ...] = ()

    def __post_init__(self):
        ids = (
            self.static_version,
            self.agency_id,
            self.route_id,
            self.trip_id,
            *self.stop_ids,
            *self.parent_stop_ids,
        )
        if any(not isinstance(v, str) or not v.strip() or len(v) > 256 for v in ids):
            raise ValueError("Reference identifiers must be explicit bounded strings")
        if len(self.stop_ids) < 2:
            raise ValueError("A leg needs ordered boarding and alighting stops")
        if self.direction_id is not None and (
            type(self.direction_id) is not int or self.direction_id not in (0, 1)
        ):
            raise ValueError("Unknown direction must not be guessed")


@dataclass(frozen=True)
class Selector:
    agency_id: str | None = None
    route_id: str | None = None
    direction_id: int | None = None
    stop_id: str | None = None
    trip_id: str | None = None
    service_day: date | None = None

    def __post_init__(self):
        ids = (self.agency_id, self.route_id, self.stop_id, self.trip_id)
        if not any(ids):
            raise ValueError("An empty selector cannot establish a journey intersection")
        if any(v is not None and (not isinstance(v, str) or not v.strip() or len(v) > 256) for v in ids):
            raise ValueError("Invalid selector identifier")
        if self.direction_id is not None and (
            type(self.direction_id) is not int or self.direction_id not in (0, 1)
        ):
            raise ValueError("Invalid selector direction")
        if self.trip_id is not None and self.service_day is None:
            raise ValueError("Trip matching requires its service date")
        if self.service_day is not None and self.trip_id is None:
            raise ValueError("A service date alone cannot identify a trip")


def matches(leg: VerifiedLeg, selector: Selector, *, feed_version: str | None) -> bool:
    """All supplied selector constraints are ANDed; callers OR separate selectors.

    Unknown versions require explicit source reconciliation, never string/name
    heuristics. Transport identity is separate from temporal relevance.
    """
    if not feed_version or feed_version != leg.static_version:
        raise ValueError("Realtime and selected static timetable versions do not match")
    for field in ("agency_id", "route_id", "direction_id", "trip_id"):
        value = getattr(selector, field)
        if value is not None and value != getattr(leg, field):
            return False
    if selector.service_day is not None and selector.service_day != leg.service_day:
        return False
    if selector.stop_id is not None and selector.stop_id not in (*leg.stop_ids, *leg.parent_stop_ids):
        return False
    return True
