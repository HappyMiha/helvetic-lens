"""Opt-in wall-clock digest recurrence; persisted periods remain UTC instants."""
import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import DomainError


def validate_schedule(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) - {"timezone", "time"}:
        raise DomainError("Choose a timezone and a local delivery time.", 422, "digest_schedule_invalid")
    zone, clock = value.get("timezone", "Europe/Zurich"), value.get("time")
    try:
        if not isinstance(zone, str) or not 1 <= len(zone) <= 64:
            raise ValueError()
        if zone in {"localtime", "posixrules", "Factory"} or zone.startswith(("posix/", "right/")):
            raise ValueError()
        ZoneInfo(zone)
        if clock is not None and (not isinstance(clock, str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", clock)):
            raise ValueError()
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise DomainError("Use an IANA timezone (for example Europe/Zurich) and a time in HH:MM format.", 422, "digest_schedule_invalid") from exc
    return {"timezone": zone, "time": clock}


def next_local_delivery(now: datetime, frequency: str, schedule: dict | None = None) -> datetime:
    now = now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)
    days = {"daily": 1, "weekly": 7}[frequency]
    if not schedule or schedule.get("time") is None:
        return now + timedelta(days=days)
    schedule = validate_schedule(schedule)
    zone = ZoneInfo(schedule["timezone"])
    hour, minute = map(int, schedule["time"].split(":"))
    day = now.astimezone(zone).date() + timedelta(days=days)
    local = datetime(day.year, day.month, day.day, hour, minute)
    # A nonexistent wall time (DST gap or a skipped calendar date) moves to
    # the first valid minute. An ambiguous time uses the first occurrence only.
    for _ in range(2 * 24 * 60 + 1):
        candidate = local.replace(tzinfo=zone, fold=0).astimezone(UTC)
        if candidate.astimezone(zone).replace(tzinfo=None) == local and candidate > now:
            return candidate
        local += timedelta(minutes=1)
    raise DomainError("This local schedule could not be resolved.", 422, "digest_schedule_invalid")
