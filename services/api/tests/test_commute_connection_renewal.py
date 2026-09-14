"""New timetable dates must renew connection proof, not inherit yesterday's permission."""

from datetime import date
from hashlib import sha256
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from test_commute_interchanges import connected as _connected_fixture
from test_commute_interchanges import legs, opened
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture
from test_transport_static import archive
from test_transport_static import tables as _tables_fixture

from helvetic_lens import commute_renewal as renewal
from helvetic_lens.commute_interchanges import publish_interchanges, resolve_interchange_pairs
from helvetic_lens.commute_models import CommuteDatedLeg, CommuteInterchange
from helvetic_lens.config import DomainError
from helvetic_lens.transport_static import StaticArchive

db, template, tables, connected = _database_fixture, _template_fixture, _tables_fixture, _connected_fixture
DAY = date(2026, 9, 14)


def seed(db, tmp_path, connected):
    with opened(tmp_path, connected) as source, db.session() as session:
        report = publish_interchanges(session, source, legs(source))
        old = report["interchanges"][0]
        session.commit()
    connected["feed_info.txt"][1][0] = "20260912"
    renamed = {"trip": "new-trip", "next": "new-next"}
    for row in connected["trips.txt"][1:]:
        row[0] = renamed[row[0]]
    for row in connected["stop_times.txt"][1:]:
        row[0] = renamed[row[0]]
    return report["reference_ids"], old


def renew(db, tmp_path, connected, ids):
    with StaticArchive(archive(tmp_path, connected), expected_version="20260912") as source, db.session() as session:
        result = renewal.renew_references(session, source, tuple((identifier, DAY) for identifier in ids))
        session.commit()
        return result


@pytest.mark.parametrize("change,state", [("unchanged", "minimum_met"), ("minimum", "insufficient_time"),
                                        ("arrival", "insufficient_time"), ("prohibited", "forbidden"), ("missing", "unverified")])
def test_new_date_and_trip_ids_recheck_source_rules_and_keep_old_proof(db, tmp_path, connected, change, state):
    ids, old = seed(db, tmp_path, connected)
    if change == "minimum":
        connected["transfers.txt"][1][3] = "300"
    elif change == "arrival":
        connected["stop_times.txt"][3][3] = "26:03:00"
    elif change == "prohibited":
        connected["transfers.txt"][1][2:4] = ["3", ""]
    elif change == "missing":
        del connected["transfers.txt"]
    result = renew(db, tmp_path, connected, ids)
    assert [item["status"] for item in result["items"]] == ["mapped", "mapped"]
    assert result["interchanges"][0]["state"] == state
    assert renew(db, tmp_path, connected, ids) == result
    with db.session() as session:
        rows = list(session.scalars(select(CommuteInterchange).order_by(CommuteInterchange.service_day)))
        assert len(rows) == 2 and rows[0].proof == old
        assert rows[1].proof["archive_sha256"] != old["archive_sha256"]
        assert rows[1].proof["from_leg_hash"] != old["from_leg_hash"]
        assert rows[1].proof["state"] == state


def test_trip_specific_rule_for_old_trip_is_not_reused(db, tmp_path, connected):
    connected["transfers.txt"][1][4:6] = ["trip", "next"]
    ids, _ = seed(db, tmp_path, connected)
    assert renew(db, tmp_path, connected, ids)["interchanges"][0]["state"] == "unverified"


def test_identical_renewal_replays_across_archive_creation_clock_change(db, tmp_path, connected, monkeypatch):
    # ZIP member timestamps must not turn the same synthetic input into a new
    # purported source archive when a slower release host crosses a DOS time tick.
    import zipfile
    clock = SimpleNamespace(time=lambda: 0, localtime=lambda *_: (2026, 9, 14, 4, 0, 0, 0, 257, 0))
    monkeypatch.setattr(zipfile, "time", clock)
    ids, old = seed(db, tmp_path, connected)
    connected["stop_times.txt"][3][3] = "26:03:00"
    first = renew(db, tmp_path, connected, ids)
    clock.localtime = lambda *_: (2026, 9, 14, 4, 0, 4, 0, 257, 0)
    assert renew(db, tmp_path, connected, ids) == first
    assert first["interchanges"][0]["state"] == "insufficient_time"
    with db.session() as session:
        rows = list(session.scalars(select(CommuteInterchange).order_by(CommuteInterchange.service_day)))
        assert len(rows) == 2 and rows[0].proof == old

    # Real changed evidence under the same pinned version must still conflict.
    connected["stop_times.txt"][3][3] = "26:02:00"
    with pytest.raises(DomainError) as error:
        renew(db, tmp_path, connected, ids)
    assert error.value.code == "commute_catalog_conflict"


def test_unmapped_endpoint_produces_no_new_connection_proof(db, tmp_path, connected):
    ids, old = seed(db, tmp_path, connected)
    connected["stop_times.txt"][-2][4] = "26:05:00"
    result = renew(db, tmp_path, connected, ids)
    assert [item["status"] for item in result["items"]] == ["mapped", "unresolved"]
    assert result["interchanges"][0]["state"] == "mapping_unavailable"
    with db.session() as session:
        assert session.scalars(select(CommuteInterchange)).one().proof == old


def test_dry_run_rolls_back_both_legs_and_connections(db, tmp_path, connected):
    ids, _ = seed(db, tmp_path, connected)
    path = archive(tmp_path, connected)
    options = {"expected_version": "20260912", "expected_sha256": sha256(path.read_bytes()).hexdigest(),
               "requests": tuple((identifier, DAY) for identifier in ids)}
    report = renewal.run_renewal(db, path, **options)
    assert report["interchanges"][0]["state"] == "minimum_met" and not report["applied"]
    with db.session() as session:
        assert len(session.scalars(select(CommuteDatedLeg)).all()) == 2
        assert len(session.scalars(select(CommuteInterchange)).all()) == 1
    applied = renewal.run_renewal(db, path, **options, apply=True)
    assert applied["interchanges"] == report["interchanges"] and applied["applied"]


def test_connection_bounds_rollback_new_legs_as_well(db, tmp_path, connected, monkeypatch):
    ids, _ = seed(db, tmp_path, connected)
    monkeypatch.setattr(renewal, "MAX_PAIRS", 0)
    with StaticArchive(archive(tmp_path, connected), expected_version="20260912") as source, db.session() as session:
        with pytest.raises(ValueError, match="batch exceeds"):
            renewal.renew_references(session, source, tuple((identifier, DAY) for identifier in ids))
        session.commit()
    with db.session() as session:
        assert len(session.scalars(select(CommuteDatedLeg)).all()) == 2
        assert len(session.scalars(select(CommuteInterchange)).all()) == 1


def test_batch_reads_transfer_table_once_and_does_not_join_unrelated_pairs(tmp_path, connected, monkeypatch):
    with opened(tmp_path, connected) as source:
        first, second = legs(source)
        original, tables_read = source.rows, []

        def counted(name, *args, **kwargs):
            tables_read.append(name)
            yield from original(name, *args, **kwargs)

        monkeypatch.setattr(source, "rows", counted)
        forward, reverse = resolve_interchange_pairs(source, ((first, second), (second, first)))
        assert forward["state"] == "minimum_met" and reverse["state"] == "insufficient_time"
        assert tables_read.count("transfers.txt") == 1
        assert tables_read.count("stop_times.txt") == 1
