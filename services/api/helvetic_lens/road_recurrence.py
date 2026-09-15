"""Bounded explicit-offset DATEX recurring intervals, without guessed local zones."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

DAY_US = 86400 * 1000000
MAX_STEPS = 8192
MAX_WINDOWS = 4096
HORIZON_DAYS = 370


@dataclass(frozen=True)
class RoadDaily:
    start_us: int
    end_us: int
    offset_minutes: int


@dataclass(frozen=True)
class RoadCalendar:
    days: tuple[int, ...] = ()
    weeks: tuple[int, ...] = ()
    months: tuple[int, ...] = ()


def canonical_periods(value):
    """Keep old canonical bytes/hashes when recurrence fields are absent/empty."""
    if isinstance(value, dict):
        return {k: canonical_periods(v) for k, v in value.items()
                if k not in {'daily', 'calendar'} or v}
    if isinstance(value, (tuple, list)):
        return [canonical_periods(v) for v in value]
    return value


def has_recurrence(validity):
    return any(p.daily or p.calendar for p in (*validity.periods, *validity.exceptions))


def calendar_matches(day, selectors):
    return not selectors or any(
        (not s.days or day.weekday() in s.days)
        and (not s.weeks or (day.day - 1) // 7 + 1 in s.weeks)
        and (not s.months or day.month in s.months)
        for s in selectors)


class ExpansionLimit(ValueError):
    pass


@dataclass
class ExpansionBudget:
    remaining: int = MAX_STEPS

    def spend(self):
        self.remaining -= 1
        if self.remaining < 0:
            raise ExpansionLimit('Recurring schedule exceeds evaluation budget')


def expand(period, overall, lower, upper, budget):
    from .road_feed import RoadPeriod

    start = max(overall.start, period.start or overall.start, lower)
    ends = [e for e in (overall.end, period.end, upper) if e is not None]
    end = min(ends)
    if end <= start:
        return []
    if not period.daily:
        if period.calendar:
            raise ExpansionLimit('Calendar has no explicit source clock')
        return [RoadPeriod(start, end)]
    result = []
    for daily in period.daily:
        zone = timezone(timedelta(minutes=daily.offset_minutes))
        # Include the prior start day for an interval spanning midnight.
        date = start.astimezone(zone).date() - timedelta(days=1)
        final = end.astimezone(zone).date()
        while date <= final:
            budget.spend()
            if calendar_matches(date, period.calendar):
                midnight = datetime.combine(date, datetime.min.time(), tzinfo=zone)
                a = midnight + timedelta(microseconds=daily.start_us)
                b = midnight + timedelta(microseconds=daily.end_us)
                if daily.end_us < daily.start_us:
                    b += timedelta(days=1)
                a, b = max(start, a.astimezone(UTC)), min(end, b.astimezone(UTC))
                if b > a:
                    result.append(RoadPeriod(a, b))
                    if len(result) > MAX_WINDOWS:
                        raise ExpansionLimit('Recurring schedule exceeds interval budget')
            date += timedelta(days=1)
    return result
