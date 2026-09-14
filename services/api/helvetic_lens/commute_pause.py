"""Read-only display of the existing Zurich calendar-day notification pause."""
from datetime import UTC, datetime, time, timedelta

from .transport_reference import ZURICH


def notification_pause_until(monitor, *, now=None):
    now = now or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("A timezone-aware clock is required")
    today = now.astimezone(ZURICH).date()
    if monitor.status != "active" or monitor.paused_on != today:
        return None
    # Calendar midnight, not 24 elapsed hours: Zurich days can be 23 or 25 hours.
    end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=ZURICH)
    return end.astimezone(UTC).isoformat()
