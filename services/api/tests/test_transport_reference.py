from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from helvetic_lens.transport_reference import (
    Selector,
    VerifiedLeg,
    commute_window,
    intervals_overlap,
    matches,
    service_instant,
    service_seconds,
)


def test_overnight_service_and_commute_weekdays_have_distinct_dates():
    friday = date(2026, 9, 11)
    instant = service_instant(friday, "25:35:00")
    assert instant == datetime(2026, 9, 11, 23, 35, tzinfo=UTC)
    window = commute_window(friday, "23:00", "02:00", (4,))
    assert window == (datetime(2026, 9, 11, 21, tzinfo=UTC), datetime(2026, 9, 12, 0, tzinfo=UTC))
    assert intervals_overlap(window, (instant, instant + timedelta(minutes=5)))
    assert commute_window(date(2026, 9, 12), "23:00", "02:00", (4,)) is None


def test_service_dst_uses_elapsed_noon_anchor_not_wall_midnight():
    spring = date(2026, 3, 29)
    autumn = date(2026, 10, 25)
    assert service_instant(spring, "03:00:00") == datetime(2026, 3, 29, 1, tzinfo=UTC)
    assert service_instant(autumn, "03:00:00") == datetime(2026, 10, 25, 2, tzinfo=UTC)
    assert service_instant(spring, "26:00:00") - service_instant(spring, "02:00:00") == timedelta(days=1)


def test_wall_dst_repeat_includes_both_occurrences_but_gap_requires_correction():
    window = commute_window(date(2026, 10, 25), "02:10", "02:40", (6,))
    assert window == (datetime(2026, 10, 25, 0, 10, tzinfo=UTC), datetime(2026, 10, 25, 1, 40, tzinfo=UTC))
    with pytest.raises(ValueError, match="does not exist"):
        commute_window(date(2026, 3, 29), "02:10", "03:00", (6,))


@pytest.mark.parametrize("value", ["24:60:00", "168:00:00", "-1:00:00", "10:01", "1:1:01", "NaN", None])
def test_invalid_service_time_never_defaults_to_midnight(value):
    with pytest.raises(ValueError):
        service_seconds(value)


def test_window_boundaries_and_invalid_intervals():
    start = datetime(2026, 9, 14, 4, tzinfo=UTC)
    window = (start, start + timedelta(hours=2))
    assert not intervals_overlap(window, (start - timedelta(hours=1), start))
    assert not intervals_overlap(window, (window[1], window[1] + timedelta(hours=1)))
    assert intervals_overlap(window, (start, start + timedelta(seconds=1)))
    for invalid in [(start, start), (start.replace(tzinfo=None), start), (window[1], start)]:
        with pytest.raises(ValueError):
            intervals_overlap(window, invalid)
    for begin, end, days in [
        ("24:00", "01:00", (0,)),
        ("06:00", "06:00", (0,)),
        ("06:00", "07:00", (True,)),
        ("06:00", "07:00", (0, 0)),
    ]:
        with pytest.raises(ValueError):
            commute_window(date(2026, 9, 14), begin, end, days)


@pytest.fixture
def leg():
    return VerifiedLeg(
        "fixture-v1",
        "fixture-agency",
        "fixture-route",
        "fixture-trip",
        date(2026, 9, 14),
        0,
        ("fixture:A:1", "fixture:B:2"),
        ("fixture:A", "fixture:B"),
    )


def test_exact_ids_direction_selected_segment_and_parent_mapping(leg):
    assert matches(leg, Selector(route_id=leg.route_id, direction_id=0), feed_version="fixture-v1")
    assert matches(leg, Selector(stop_id="fixture:A"), feed_version="fixture-v1")
    for selector in [
        Selector(route_id=leg.route_id, direction_id=1),
        Selector(agency_id="another-agency", stop_id="fixture:A"),
        Selector(route_id="another-route", stop_id="fixture:A"),
        Selector(stop_id="fixture:A:2"),
        Selector(stop_id="Basel"),
        Selector(stop_id="fixture:outside-selected-leg"),
    ]:
        assert not matches(leg, selector, feed_version="fixture-v1")
    assert not matches(
        replace(leg, direction_id=None),
        Selector(route_id=leg.route_id, direction_id=0),
        feed_version="fixture-v1",
    )


def test_trip_service_day_and_feed_version_cannot_be_inferred(leg):
    assert matches(leg, Selector(trip_id=leg.trip_id, service_day=leg.service_day), feed_version="fixture-v1")
    assert not matches(
        leg, Selector(trip_id=leg.trip_id, service_day=date(2026, 9, 15)), feed_version="fixture-v1"
    )
    for version in (None, "fixture-v2", ""):
        with pytest.raises(ValueError, match="versions do not match"):
            matches(leg, Selector(route_id=leg.route_id), feed_version=version)
    for fields in [
        {},
        {"trip_id": leg.trip_id},
        {"route_id": ""},
        {"route_id": leg.route_id, "direction_id": True},
    ]:
        with pytest.raises(ValueError):
            Selector(**fields)
