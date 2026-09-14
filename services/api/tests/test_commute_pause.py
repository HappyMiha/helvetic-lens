from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest

from helvetic_lens.commute_pause import notification_pause_until


@pytest.mark.parametrize("local_day,start,end,hours", [
    ("2026-03-29", "2026-03-28T23:00:00+00:00", "2026-03-29T22:00:00+00:00", 23),
    ("2026-10-25", "2026-10-24T22:00:00+00:00", "2026-10-25T23:00:00+00:00", 25),
    ("2026-12-31", "2026-12-30T23:00:00+00:00", "2026-12-31T23:00:00+00:00", 24),
])
def test_pause_ends_at_calendar_midnight_not_after_24_hours(local_day, start, end, hours):
    row = SimpleNamespace(status="active", paused_on=date.fromisoformat(local_day))
    beginning, ending = datetime.fromisoformat(start), datetime.fromisoformat(end)
    assert notification_pause_until(row, now=beginning) == end
    assert (ending - beginning).total_seconds() == hours * 3600
    assert notification_pause_until(row, now=ending - timedelta(microseconds=1)) == end
    assert notification_pause_until(row, now=ending) is None
    assert row.status == "active" and row.paused_on == date.fromisoformat(local_day)


@pytest.mark.parametrize("status,paused_on", [
    ("paused", date(2026, 9, 14)), ("archived", date(2026, 9, 14)),
    ("draft", date(2026, 9, 14)), ("active", None),
    ("active", date(2026, 9, 13)), ("active", date(2026, 9, 15)),
])
def test_no_automatic_resume_promise_for_permanent_or_inapplicable_pause(status, paused_on):
    assert notification_pause_until(SimpleNamespace(status=status, paused_on=paused_on),
        now=datetime(2026, 9, 14, 12, tzinfo=UTC)) is None


def test_naive_clock_is_rejected():
    with pytest.raises(ValueError):
        notification_pause_until(SimpleNamespace(status="active", paused_on=None), now=datetime(2026, 9, 14))
