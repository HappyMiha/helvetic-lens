"""Source transfer rules must justify the exact saved connection, never proximity."""

from dataclasses import replace
from datetime import UTC, date, datetime
from hashlib import sha256
from uuid import UUID

import pytest
from sqlalchemy import select
from test_commute_contracts import configuration
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture
from test_transport_static import archive
from test_transport_static import tables as _tables_fixture

from helvetic_lens.commute_catalog import publish_legs, resolve_configuration
from helvetic_lens.commute_interchanges import (
    journey_interchanges,
    publish_interchanges,
    require_interchanges,
    resolve_interchanges,
)
from helvetic_lens.commute_models import CommuteDatedLeg, CommuteInterchange
from helvetic_lens.commute_repository import create_monitor, preview
from helvetic_lens.config import DomainError
from helvetic_lens.transport_static import LegRequest, StaticArchive

db, template, tables = _database_fixture, _template_fixture, _tables_fixture
DAY = date(2026, 9, 11)
HEADER = ["from_stop_id", "to_stop_id", "transfer_type", "min_transfer_time",
          "from_trip_id", "to_trip_id", "from_route_id", "to_route_id"]


@pytest.fixture
def connected(tables):
    tables["trips.txt"].append(["next", "route", "weekday", "0"])
    tables["stops.txt"].append(["off:3", "Basel platform 3", "off", "0"])
    tables["stop_times.txt"].extend([
        ["next", "off:3", "2", "26:04:00", "26:04:00", "0", "0"],
        ["next", "after", "4", "26:30:00", "26:30:00", "0", "0"],
    ])
    tables["transfers.txt"] = [HEADER, ["off", "off", "2", "240", "", "", "", ""]]
    return tables


def opened(tmp_path, connected):
    return StaticArchive(archive(tmp_path, connected), expected_version="20260909")


def legs(source):
    return source.resolve((LegRequest("trip", DAY, 3, 9), LegRequest("next", DAY, 2, 4)))


def result(tmp_path, connected):
    with opened(tmp_path, connected) as source:
        return resolve_interchanges(source, legs(source))[0]


def test_parent_rule_applies_to_actual_endpoints_with_exact_minimum(tmp_path, connected):
    proof = result(tmp_path, connected)
    assert proof["state"] == "minimum_met"
    assert proof["scheduled_seconds"] == proof["min_transfer_time"] == 240
    assert (proof["from_stop_id"], proof["to_stop_id"]) == ("off:2", "off:3")
    assert proof["row_number"] == 2
    assert len(proof["from_leg_hash"]) == len(proof["archive_sha256"]) == 64


@pytest.mark.parametrize("kind,minimum,expected", [
    ("0", "", "recommended"), ("", "", "recommended"), ("1", "", "timed"),
    ("2", "241", "insufficient_time"), ("2", "0", "minimum_met"), ("3", "", "forbidden"),
])
def test_rule_meaning_is_not_a_live_guarantee(tmp_path, connected, kind, minimum, expected):
    connected["transfers.txt"][1][2:4] = [kind, minimum]
    assert result(tmp_path, connected)["state"] == expected


def test_specific_trip_overrides_general_forbidden_but_equal_maxima_are_ambiguous(tmp_path, connected):
    connected["transfers.txt"][1][2:4] = ["3", ""]
    specific = ["off:2", "off:3", "2", "120", "trip", "next", "route", "route"]
    connected["transfers.txt"].append(specific)
    assert result(tmp_path, connected)["state"] == "minimum_met"
    connected["transfers.txt"].append(["off", "off", "2", "120", "trip", "next", "", ""])
    assert result(tmp_path, connected)["state"] == "ambiguous"


@pytest.mark.parametrize("specific", [
    ["trip", "next", "", ""], ["trip", "", "", "route"],
    ["", "next", "route", ""], ["trip", "", "", ""],
    ["", "next", "", ""], ["", "", "route", "route"],
    ["", "", "route", ""], ["", "", "", "route"],
])
def test_all_trip_and_route_specificity_ranks_override_stop_only(tmp_path, connected, specific):
    connected["transfers.txt"].append(["off", "off", "3", "", *specific])
    assert result(tmp_path, connected)["state"] == "forbidden"


def test_matching_station_name_or_unrelated_parent_on_leg_is_not_a_transfer(tmp_path, connected):
    connected["transfers.txt"][1][0] = "board"  # Parent exists on leg, not at its alighting endpoint.
    assert result(tmp_path, connected)["state"] == "unverified"
    del connected["transfers.txt"]
    assert result(tmp_path, connected)["state"] == "unverified"


@pytest.mark.parametrize("kind", ["4", "5"])
def test_linked_vehicle_rules_are_not_ordinary_walkable_connections(tmp_path, connected, kind):
    connected["transfers.txt"] = [HEADER, ["", "", kind, "", "trip", "next", "", ""]]
    assert result(tmp_path, connected)["state"] == "unsupported_linked_trip"


@pytest.mark.parametrize("column,value", [(2, "6"), (3, "-1"), (3, "1.5"), (3, ""), (3, "604801")])
def test_invalid_applicable_rule_never_falls_back(tmp_path, connected, column, value):
    connected["transfers.txt"][1][column] = value
    with pytest.raises(ValueError):
        result(tmp_path, connected)


def test_fabricated_leg_archive_or_time_is_rejected(tmp_path, connected):
    with opened(tmp_path, connected) as source:
        before, after = legs(source)
        with pytest.raises(ValueError, match="archive identity"):
            resolve_interchanges(source, (replace(before, archive_sha256="0" * 64), after))
        with pytest.raises(ValueError, match="pinned timetable"):
            resolve_interchanges(source, (replace(before, alighting_name="Invented"), after))


def test_same_trip_contiguous_segments_need_no_walking_inference(tmp_path, connected):
    connected["transfers.txt"][1][2:4] = ["3", ""]
    with opened(tmp_path, connected) as source:
        selected = source.resolve((LegRequest("trip", DAY, 3, 9), LegRequest("trip", DAY, 9, 12)))
        assert resolve_interchanges(source, selected)[0]["state"] == "same_trip"


def test_catalog_proof_survives_reload_and_denial_or_corruption_never_authorizes_start(db, tmp_path, connected):
    with opened(tmp_path, connected) as source, db.session() as session:
        report = publish_interchanges(session, source, legs(source))
        assert publish_interchanges(session, source, legs(source)) == report
        config = configuration().model_copy(update={"leg_reference_ids": tuple(map(UUID, report["reference_ids"]))})
        monitor = create_monitor(session, "owner", config.model_dump(mode="json"), "interchange-fixture")
        session.commit()
    with db.session() as session:
        resolved = resolve_configuration(session, config, service_day=DAY, static_version="20260909")
        proof, = require_interchanges(session, config, resolved)
        assert proof["state"] == "minimum_met"
        shown = preview(session, "owner", config.model_dump(mode="json"), service_day=DAY,
                        static_version="20260909", now=datetime(2026, 9, 11, 22, tzinfo=UTC))
        assert shown["interchanges"][0]["state"] == "minimum_met"
        assert "transfer_not_verified" not in shown["blocking_reasons"]
        assert not shown["start_available"]  # Source grant and live feeds are still required.
        assert monitor["status"] == "draft"
        row = session.scalar(select(CommuteInterchange))
        row.proof = {**row.proof, "min_transfer_time": 0}
        session.flush()
        with pytest.raises(DomainError, match="evidence"):
            journey_interchanges(session, config, resolved)


def test_leg_import_alone_does_not_assert_connection(db, tmp_path, connected):
    with opened(tmp_path, connected) as source, db.session() as session:
        selected = legs(source)
        ids = publish_legs(session, selected)
        config = configuration().model_copy(update={"leg_reference_ids": tuple(map(UUID, ids))})
        with pytest.raises(DomainError) as error:
            require_interchanges(session, config, dict(zip(ids, selected, strict=True)))
        assert error.value.code == "commute_transfer_unverified"


def test_operator_dry_run_apply_and_checksum_are_separate(db, tmp_path, connected):
    from helvetic_lens.commute_interchanges import run_import
    path = archive(tmp_path, connected)
    options = {"expected_version": "20260909", "expected_sha256": sha256(path.read_bytes()).hexdigest(),
        "requests": (LegRequest("trip", DAY, 3, 9), LegRequest("next", DAY, 2, 4))}
    assert run_import(db, path, **options)["applied"] is False
    with db.session() as session:
        assert list(session.scalars(select(CommuteDatedLeg))) == []
        assert list(session.scalars(select(CommuteInterchange))) == []
    assert run_import(db, path, **options, apply=True)["applied"] is True
    with pytest.raises(ValueError, match="checksum"):
        run_import(db, path, **{**options, "expected_sha256": "0" * 64}, apply=True)
    with db.session() as session:
        assert len(list(session.scalars(select(CommuteInterchange)))) == 1


def test_verified_two_leg_journey_starts_and_worker_rechecks_connection(db, tmp_path, connected):
    from test_commute_contracts import DAY as MONDAY
    from test_commute_contracts import NOW
    from test_commute_jobs import capture, source_grants
    from test_transport_feed import feed, trip_feed

    from helvetic_lens import commute_jobs as worker
    from helvetic_lens.commute_delivery import preview as mail_preview
    from helvetic_lens.commute_email_preferences import configure as consent
    from helvetic_lens.commute_models import CommuteEventVersion
    from helvetic_lens.commute_repository import command
    from helvetic_lens.config import Settings
    from helvetic_lens.models import User
    from helvetic_lens.transport_feed import ALERTS, TRIPS
    connected["stop_times.txt"][2][3:5] = ["07:45:00", "07:45:00"]
    connected["stop_times.txt"][3][3:5] = ["08:00:00", "08:00:00"]
    connected["stop_times.txt"][-2][3:5] = ["08:04:00", "08:04:00"]
    connected["stop_times.txt"][-1][3:5] = ["08:30:00", "08:30:00"]
    with opened(tmp_path, connected) as source, db.session() as session:
        selected = source.resolve((LegRequest("trip", MONDAY, 3, 9), LegRequest("next", MONDAY, 2, 4)))
        report = publish_interchanges(session, source, selected)
        config = configuration().model_copy(update={"leg_reference_ids": tuple(map(UUID, report["reference_ids"]))})
        row = create_monitor(session, "owner", config.model_dump(mode="json"), "two-leg-start")
        session.commit()
    permissions = source_grants(db)
    capture(db, permissions[TRIPS], trip_feed(cancelled=True))
    capture(db, permissions[ALERTS], feed())
    settings = Settings(_env_file=None, commute_watch_enabled=True, commute_source_enabled=True,
                        auth_email_mode="smtp", auth_smtp_host="smtp.example.invalid", auth_email_from="mail@example.invalid")
    with db.session() as session:
        session.get(User, "owner").email_verified_at = NOW
        saved = consent(session, "owner", row["id"], expected_version=row["version"], consent=True, now=NOW,
                        configuration={"delivery": {"email": "immediate"}})
        row["version"] = saved["monitor_version"]
        shown = preview(session, "owner", config.model_dump(mode="json"), service_day=MONDAY, settings=settings, now=NOW)
        assert shown["start_available"] and not shown["blocking_reasons"]
        row = command(session, "owner", row["id"], row["version"], "start", now=NOW, settings=settings)
        session.commit()
    result = worker.refresh(db, settings, monitor_id=row["id"], version=row["version"], now=NOW)
    assert result["changed"] == result["signals"] == 1
    with db.session() as session:
        assert len(mail_preview(session, settings, "owner", row["id"], now=NOW)["items"]) == 1
        proof = session.scalar(select(CommuteEventVersion)).evidence["interchanges"][0]
        assert proof["state"] == "minimum_met" and proof["min_transfer_time"] == 240
        session.delete(session.scalar(select(CommuteInterchange)))
        session.commit()
        assert mail_preview(session, settings, "owner", row["id"], now=NOW)["items"] == []
    result = worker.refresh(db, settings, monitor_id=row["id"], version=row["version"], now=NOW)
    assert result["signals"] == result["changed"] == 0
    assert "commute_transfer_unverified" in result["failures"]


def test_transfer_scan_bound_fails_before_publication(tmp_path, connected, monkeypatch):
    import helvetic_lens.commute_interchanges as module
    monkeypatch.setattr(module, "MAX_TRANSFER_ROWS", 0)
    with pytest.raises(ValueError, match="oversized GTFS"):
        result(tmp_path, connected)


@pytest.mark.parametrize("day", [date(2026, 3, 29), date(2026, 10, 25)])
def test_minimum_uses_elapsed_time_across_dst_service_days(tmp_path, connected, day):
    connected["calendar_dates.txt"].append(["weekday", day.strftime("%Y%m%d"), "1"])
    with opened(tmp_path, connected) as source:
        selected = source.resolve((LegRequest("trip", day, 3, 9), LegRequest("next", day, 2, 4)))
        proof, = resolve_interchanges(source, selected)
        assert proof["state"] == "minimum_met" and proof["scheduled_seconds"] == 240
