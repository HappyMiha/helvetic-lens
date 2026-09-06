"""Opt-in wall-clock digest recurrence; persisted periods remain UTC instants."""
import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import DomainError


def validate_schedule(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) - {"timezone", "time", "quiet_start", "quiet_end"}:
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
    result = {"timezone": zone, "time": clock}
    if "quiet_start" in value or "quiet_end" in value:
        start, end = value.get("quiet_start"), value.get("quiet_end")
        if (start is None) != (end is None) or (start is not None and (
            start == end or any(not isinstance(v, str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", v) for v in (start, end))
        )):
            raise DomainError("Choose different start and end times, or clear both quiet-hours fields.", 422, "digest_quiet_hours_invalid")
        result.update(quiet_start=start, quiet_end=end)
    return result


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


def quiet_until(now: datetime, schedule: dict | None) -> datetime | None:
    """Return the next allowed UTC minute, or None when sending is allowed now.

    Traverse real instants so repeated and missing local hours cannot accidentally
    bypass quiet time. Equal start/end is rejected instead of meaning 24h silence.
    """
    if not schedule or not schedule.get("quiet_start"):
        return None
    schedule = validate_schedule(schedule)
    zone = ZoneInfo(schedule["timezone"])
    start, end = schedule["quiet_start"], schedule["quiet_end"]
    now = now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)
    def quiet(stamp):
        clock = stamp.astimezone(zone).strftime("%H:%M")
        return start <= clock < end if start < end else clock >= start or clock < end
    if not quiet(now):
        return None
    candidate = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(2 * 24 * 60 + 1):
        if not quiet(candidate):
            return candidate
        candidate += timedelta(minutes=1)
    raise DomainError("Quiet hours could not be resolved.", 422, "digest_quiet_hours_invalid")
