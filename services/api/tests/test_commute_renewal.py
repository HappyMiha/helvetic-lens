"""Real bounded ZIP parsing renews identities, not guessed route labels."""

from copy import deepcopy
from datetime import date
from hashlib import sha256
from uuid import UUID

import pytest
from sqlalchemy import select
from test_commute_contracts import configuration
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture
from test_transport_static import archive, resolve
from test_transport_static import tables as _tables_fixture

from helvetic_lens import commute_renewal as renewal
from helvetic_lens.commute_catalog import publish_legs, resolve_configuration
from helvetic_lens.commute_models import CommuteDatedLeg
from helvetic_lens.commute_repository import create_monitor, get_monitor
from helvetic_lens.config import DomainError
from helvetic_lens.transport_static import StaticArchive

db, template, tables = _database_fixture, _template_fixture, _tables_fixture
DAY = date(2026, 9, 14)


def seed(db, tmp_path, tables):
    leg = resolve(archive(tmp_path, tables))
    with db.session() as session:
        identifier, = publish_legs(session, (leg,))
        session.commit()
    tables["feed_info.txt"][1][0] = "20260912"
    tables["trips.txt"][1][0] = "new-trip-id"
    for row in tables["stop_times.txt"][1:]:
        row[0] = "new-trip-id"
    return identifier


def renew(db, tmp_path, tables, identifier, day=DAY):
    with StaticArchive(archive(tmp_path, tables), expected_version="20260912") as source, db.session() as session:
        result = renewal.renew_references(session, source, ((identifier, day),))
        session.commit()
    return result["items"][0]


def test_new_trip_id_date_and_archive_preserve_the_private_saved_configuration(db, tmp_path, tables):
    identifier = seed(db, tmp_path, tables)
    config = configuration().model_copy(update={"leg_reference_ids": (UUID(identifier),)})
    with db.session() as session:
        original = create_monitor(session, "owner", config.model_dump(mode="json"), "renewal-fixture")
        session.commit()
    assert renew(db, tmp_path, tables, identifier)["status"] == "mapped"
    assert renew(db, tmp_path, tables, identifier)["status"] == "mapped"
    with db.session() as session:
        assert get_monitor(session, "owner", original["id"]) == original
        old = resolve_configuration(session, config, service_day=date(2026, 9, 11), static_version="20260909")[identifier]
        new = resolve_configuration(session, config, service_day=DAY, static_version="20260912")[identifier]
        assert old.reference.trip_id == "trip" and new.reference.trip_id == "new-trip-id"
        assert old.archive_sha256 != new.archive_sha256
        assert new.departure.day == 14  # GTFS 25:05 local is next-day 23:05 UTC.
        assert len(session.scalars(select(CommuteDatedLeg)).all()) == 2


@pytest.mark.parametrize("change", ["time", "agency", "route", "direction", "stops", "calendar"])
def test_similar_but_different_journey_never_replaces_saved_meaning(db, tmp_path, tables, change):
    identifier = seed(db, tmp_path, tables)
    if change == "time":
        tables["stop_times.txt"][2][4] = "25:06:00"
    elif change == "agency":
        tables["routes.txt"][1][1] = "other-agency"
    elif change == "route":
        tables["trips.txt"][1][1] = "other-route"
    elif change == "direction":
        tables["trips.txt"][1][3] = "1"
    elif change == "stops":
        # Same endpoints and time, but a different intermediate route segment.
        tables["stop_times.txt"].append(["new-trip-id", "before", "5", "25:15:00", "25:15:00", "0", "0"])
    else:
        tables["calendar_dates.txt"].append(["weekday", "20260914", "2"])
    assert renew(db, tmp_path, tables, identifier)["status"] == "unresolved"
    with db.session() as session:
        assert len(session.scalars(select(CommuteDatedLeg)).all()) == 1


def test_two_exact_trips_are_ambiguous_and_do_not_publish_a_random_choice(db, tmp_path, tables):
    identifier = seed(db, tmp_path, tables)
    tables["trips.txt"].append(["another-trip", "route", "weekday", "0"])
    tables["stop_times.txt"].extend([["another-trip", *row[1:]] for row in deepcopy(tables["stop_times.txt"][1:])])
    assert renew(db, tmp_path, tables, identifier)["status"] == "ambiguous"
    with db.session() as session:
        assert len(session.scalars(select(CommuteDatedLeg)).all()) == 1


def test_added_weekend_and_outside_feed_are_distinct(db, tmp_path, tables):
    identifier = seed(db, tmp_path, tables)
    saturday = date(2026, 9, 19)
    assert renew(db, tmp_path, tables, identifier, saturday)["status"] == "unresolved"
    tables["calendar_dates.txt"].append(["weekday", "20260919", "1"])
    assert renew(db, tmp_path, tables, identifier, saturday)["status"] == "mapped"
    assert renew(db, tmp_path, tables, identifier, date(2027, 1, 1))["status"] == "outside_feed"


def test_renewal_uses_new_exact_sequences_even_when_csv_rows_are_not_sorted(db, tmp_path, tables):
    identifier = seed(db, tmp_path, tables)
    for row in tables["stop_times.txt"][1:]:
        row[2] = str(int(row[2]) * 2)
    tables["stop_times.txt"][1:] = reversed(tables["stop_times.txt"][1:])
    assert renew(db, tmp_path, tables, identifier)["status"] == "mapped"
    with db.session() as session:
        row = session.get(CommuteDatedLeg, (identifier, DAY, "20260912"))
        assert row.resolved["stop_sequences"] == [6, 18]


def test_frequency_instance_cannot_be_relabelled_as_a_fixed_departure(db, tmp_path, tables):
    identifier = seed(db, tmp_path, tables)
    tables["frequencies.txt"].append(["new-trip-id", "06:00:00", "22:00:00", "300", "0"])
    assert renew(db, tmp_path, tables, identifier)["status"] == "unsupported_frequency"


@pytest.mark.parametrize("boundary", ["MAX_TRIPS", "MAX_ENDPOINTS", "MAX_CANDIDATES"])
def test_large_candidate_expansion_is_rejected_before_publishing(db, tmp_path, tables, monkeypatch, boundary):
    identifier = seed(db, tmp_path, tables)
    monkeypatch.setattr(renewal, boundary, 0)
    with pytest.raises(ValueError):
        renew(db, tmp_path, tables, identifier)
    with db.session() as session:
        assert len(session.scalars(select(CommuteDatedLeg)).all()) == 1


def test_pinned_renewed_mapping_cannot_be_silently_rewritten(db, tmp_path, tables):
    identifier = seed(db, tmp_path, tables)
    assert renew(db, tmp_path, tables, identifier)["status"] == "mapped"
    tables["stops.txt"][2][1] = "Changed source label"
    with pytest.raises(DomainError, match="Conflicting dated"):
        renew(db, tmp_path, tables, identifier)


def test_operator_dry_run_is_nonpersistent_and_apply_requires_pinned_checksum(db, tmp_path, tables):
    identifier = seed(db, tmp_path, tables)
    path = archive(tmp_path, tables)
    arguments = {"expected_version": "20260912", "expected_sha256": sha256(path.read_bytes()).hexdigest(),
                 "requests": ((identifier, DAY),)}
    dry = renewal.run_renewal(db, path, **arguments)
    assert dry["items"][0]["status"] == "mapped" and not dry["applied"]
    with db.session() as session:
        assert len(session.scalars(select(CommuteDatedLeg)).all()) == 1
    with pytest.raises(ValueError, match="checksum"):
        renewal.run_renewal(db, path, **{**arguments, "expected_sha256": "0" * 64}, apply=True)
    applied = renewal.run_renewal(db, path, **arguments, apply=True)
    assert applied["applied"] and applied["items"] == dry["items"]
    with db.session() as session:
        assert len(session.scalars(select(CommuteDatedLeg)).all()) == 2


@pytest.mark.parametrize("day,departure", [(date(2026, 3, 29), "02:05:00"), (date(2026, 10, 25), "00:05:00")])
def test_dst_renewal_requires_same_local_time_and_service_day_offset(db, tmp_path, tables, day, departure):
    tables["stop_times.txt"][1][3:5] = ["00:00:00", "00:00:00"]
    tables["stop_times.txt"][2][3:5] = ["01:00:00", "01:05:00"]
    tables["stop_times.txt"][3][3:5] = ["02:00:00", "02:05:00"]
    tables["stop_times.txt"][4][3:5] = ["03:30:00", "03:30:00"]
    identifier = seed(db, tmp_path, tables)
    tables["calendar_dates.txt"].append(["weekday", day.strftime("%Y%m%d"), "1"])
    # At GTFS noon-minus-12h DST, an unchanged elapsed 01:05 can move the
    # observed wall time. Do not substitute that changed departure silently.
    assert renew(db, tmp_path, tables, identifier, day)["status"] == "unresolved"
    hour = int(departure.split(":")[0])
    tables["stop_times.txt"][2][3:5] = [f"{hour}:00:00", departure]
    tables["stop_times.txt"][3][3:5] = [f"{hour+1}:00:00", f"{hour+1}:05:00"]
    assert renew(db, tmp_path, tables, identifier, day)["status"] == "mapped"
