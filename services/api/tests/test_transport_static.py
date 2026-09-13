"""Imported identities must prove the selected service, segment and time."""

import csv
from datetime import UTC, date, datetime
from io import StringIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from helvetic_lens.transport_static import LegRequest, StaticArchive


@pytest.fixture
def tables():
    return {
        "feed_info.txt": [
            ["feed_version", "feed_start_date", "feed_end_date"], ["20260909", "20260101", "20261231"],
        ],
        "agency.txt": [["agency_id", "agency_timezone"], ["11", "Europe/Berlin"]],
        "routes.txt": [["route_id", "agency_id", "route_short_name", "route_long_name"], ["route", "11", "S1", ""]],
        "trips.txt": [["trip_id", "route_id", "service_id", "direction_id"], ["trip", "route", "weekday", "0"]],
        "calendar.txt": [
            ["service_id", "start_date", "end_date", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
            ["weekday", "20260101", "20261231", "1", "1", "1", "1", "1", "0", "0"],
        ],
        "calendar_dates.txt": [["service_id", "date", "exception_type"]],
        "frequencies.txt": [["trip_id", "start_time", "end_time", "headway_secs", "exact_times"]],
        "stops.txt": [
            ["stop_id", "stop_name", "parent_station", "location_type"],
            ["before", "Before", "", "0"],
            ["board:1", "Zürich", "board", "0"],
            ["board", "Zürich", "", "1"],
            ["off:2", "Basel", "off", "0"],
            ["off", "Basel", "", "1"],
            ["after", "After", "", "0"],
        ],
        "stop_times.txt": [
            ["trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time", "pickup_type", "drop_off_type"],
            ["trip", "before", "1", "23:30:00", "23:30:00", "0", "0"],
            ["trip", "board:1", "3", "25:00:00", "25:05:00", "0", "0"],
            ["trip", "off:2", "9", "26:00:00", "26:05:00", "0", "0"],
            ["trip", "after", "12", "27:30:00", "27:30:00", "0", "0"],
        ],
    }


def archive(tmp_path, tables):
    path = tmp_path / "schedule.zip"
    with ZipFile(path, "w", ZIP_DEFLATED) as target:
        for name, rows in tables.items():
            text = StringIO(newline="")
            csv.writer(text).writerows(rows)
            target.writestr(name, text.getvalue().encode("utf-8-sig"))
    return path


def resolve(path, day=date(2026, 9, 11), version="20260909"):
    with StaticArchive(path, expected_version=version) as source:
        return source.resolve((LegRequest("trip", day, 3, 9),))[0]


def test_exact_segment_has_verified_parents_utf8_names_and_overnight_service_date(tmp_path, tables):
    leg = resolve(archive(tmp_path, tables))
    assert leg.reference.stop_ids == ("board:1", "off:2")
    assert leg.stop_sequences == (3, 9)
    assert leg.reference.parent_stop_ids == ("board", "off")
    assert leg.reference.service_day == date(2026, 9, 11)
    assert leg.reference.direction_id == 0
    assert leg.departure == datetime(2026, 9, 11, 23, 5, tzinfo=UTC)
    assert leg.arrival == datetime(2026, 9, 12, 0, tzinfo=UTC)
    assert leg.boarding_name == "Zürich"
    assert len(leg.archive_sha256) == 64


def test_calendar_exception_removes_regular_service_and_adds_weekend_service(tmp_path, tables):
    tables["calendar_dates.txt"].extend([["weekday", "20260911", "2"], ["weekday", "20260912", "1"]])
    path = archive(tmp_path, tables)
    with pytest.raises(ValueError, match="does not operate"):
        resolve(path)
    assert resolve(path, date(2026, 9, 12)).reference.service_day == date(2026, 9, 12)
    with pytest.raises(ValueError, match="does not operate"):
        resolve(path, date(2026, 9, 13))


@pytest.mark.parametrize("day,expected", [(date(2026, 3, 29), 23), (date(2026, 10, 25), 0)])
def test_import_uses_gtfs_elapsed_clock_on_dst_service_dates(tmp_path, tables, day, expected):
    tables["calendar_dates.txt"].append(["weekday", day.strftime("%Y%m%d"), "1"])
    leg = resolve(archive(tmp_path, tables), day)
    assert leg.departure.hour == expected
    assert (leg.arrival - leg.departure).total_seconds() == 55 * 60


def test_unknown_version_cannot_relabel_verified_identity(tmp_path, tables):
    with pytest.raises(ValueError, match="feed version"):
        resolve(archive(tmp_path, tables), version="20260910")


@pytest.mark.parametrize("table,row,column,value,message", [
    ("trips.txt", 1, 3, "2", "trip identity"),
    ("trips.txt", 1, 1, "other", "Unknown route"),
    ("routes.txt", 1, 1, "other", "Unknown agency"),
    ("agency.txt", 1, 1, "America/New_York", "timezone"),
    ("stops.txt", 2, 2, "missing", "parent station"),
    ("stops.txt", 3, 3, "0", "parent station"),
    ("stop_times.txt", 2, 5, "1", "boarding/alighting"),
    ("stop_times.txt", 3, 6, "2", "boarding/alighting"),
    ("stop_times.txt", 3, 3, "24:00:00", "Non-monotonic"),
    ("stop_times.txt", 3, 2, "3", "Ambiguous"),
    ("stop_times.txt", 3, 1, "missing", "Unknown stop"),
])
def test_incomplete_or_conflicting_source_never_creates_a_leg(tmp_path, tables, table, row, column, value, message):
    tables[table][row][column] = value
    with pytest.raises(ValueError, match=message):
        resolve(archive(tmp_path, tables))


def test_frequency_template_is_not_a_specific_departure(tmp_path, tables):
    tables["frequencies.txt"].append(["trip", "06:00:00", "22:00:00", "300", "0"])
    with pytest.raises(ValueError, match="Frequency trips"):
        resolve(archive(tmp_path, tables))


def test_duplicate_calendar_exception_does_not_silently_choose_one(tmp_path, tables):
    tables["calendar_dates.txt"].extend([["weekday", "20260911", "1"], ["weekday", "20260911", "2"]])
    with pytest.raises(ValueError, match="Ambiguous service exception"):
        resolve(archive(tmp_path, tables))


@pytest.mark.parametrize("name", ["../stops.txt", "folder/stops.txt", "STOPS.txt"])
def test_archive_paths_are_rejected_without_extracting(tmp_path, tables, name):
    tables[name] = tables.pop("stops.txt")
    with pytest.raises(ValueError, match="archive structure"):
        resolve(archive(tmp_path, tables))
    assert not (tmp_path / "stops.txt").exists()


def test_truncated_row_fails_without_inventing_an_arrival(tmp_path, tables):
    tables["stop_times.txt"][3].pop()
    with pytest.raises(ValueError, match="Invalid or oversized"):
        resolve(archive(tmp_path, tables))
