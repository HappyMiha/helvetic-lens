"""The scheduled shared cache must renew private choices without rewriting them."""

from dataclasses import replace
from datetime import timedelta
from functools import partial
from hashlib import sha256
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select
from test_commute_connection_renewal import seed
from test_commute_contracts import NOW, configuration
from test_commute_interchanges import connected as _connected_fixture
from test_commute_jobs import capture
from test_commute_static_acquisition import DATASET, RESOURCE, URL, response
from test_commute_static_collector import setup
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture
from test_transport_feed import feed
from test_transport_static import archive, resolve
from test_transport_static import tables as _tables_fixture

from helvetic_lens import commute_catalog_worker as worker
from helvetic_lens import commute_static_acquisition as acquisition
from helvetic_lens import commute_static_collector as collector
from helvetic_lens.commute_catalog import publish_legs, resolve_configuration
from helvetic_lens.commute_interchanges import journey_interchanges
from helvetic_lens.commute_models import (
    CommuteDatedLeg,
    CommuteInterchange,
    CommuteLegReference,
    CommuteSourcePermission,
    CommuteStaticPoll,
)
from helvetic_lens.commute_repository import command, create_monitor, get_monitor
from helvetic_lens.config import DomainError
from helvetic_lens.transport_reference import ZURICH
from helvetic_lens.transport_static import StaticArchive

db, template, tables, connected = _database_fixture, _template_fixture, _tables_fixture, _connected_fixture
VERSION = "20260912"


def fresh(database, grants, second, version=VERSION):
    for permission in grants.values():
        message = feed(second=second)
        message.header.feed_version = version
        capture(database, permission, message, second=second)


def run(database, settings, payload, *, second=1, network=True):
    url = URL.replace("20260909.zip", VERSION + ".zip")
    calls = []

    def catalog(*args, **kwargs):
        assert network, "Cached timetable must not request the provider again"
        calls.append("catalog")
        return {"success": True, "result": {"id": DATASET, "resources": [{"id": RESOURCE, "format": "ZIP", "url": url}]}}

    def download(request):
        assert network and str(request.url) == url
        calls.append("zip")
        return response(payload)

    with httpx.Client(transport=httpx.MockTransport(download)) as client:
        result = collector.collect(database, settings, catalog=catalog,
            downloader=partial(acquisition.acquire_archive, client=client), now=lambda: NOW + timedelta(seconds=second))
    return result, calls


@pytest.mark.parametrize("minimum,expected", [(240, "minimum_met"), (600, "insufficient_time")])
def test_shared_collector_renews_next_departure_and_connections_without_changing_private_choices(
        db, tmp_path, connected, monkeypatch, minimum, expected):
    grants, settings = setup(db, tmp_path)
    ids, old_proof = seed(db, tmp_path, connected)
    config = configuration().model_copy(update={"leg_reference_ids": tuple(UUID(value) for value in ids),
                                               "window_start": "00:30", "window_end": "03:00"})
    with db.session() as session:
        original = create_monitor(session, "owner", config.model_dump(mode="json"), "shared-renewal")
        session.commit()
    connected["transfers.txt"][1][3] = str(minimum)
    payload = archive(tmp_path, connected).read_bytes()
    original_rows, scans = StaticArchive.rows, []

    def outside_transaction(source, name, *args, **kwargs):
        assert db.engine.pool.checkedout() == 0, "Archive scans must not keep a database connection"
        scans.append(name)
        yield from original_rows(source, name, *args, **kwargs)

    monkeypatch.setattr(StaticArchive, "rows", outside_transaction)
    fresh(db, grants, 1)
    result, calls = run(db, settings, payload)
    assert result["state"] == "acquired" and calls == ["catalog", "zip"]
    # First local date is Monday. GTFS 25h departures require Sunday's service
    # date, which the fixture explicitly does not operate: no invented service.
    with db.session() as session:
        state = session.get(CommuteStaticPoll, "static").renewal_state
        assert state["offset"] == 1 and state["last_outcomes"] == {"unresolved": 2}
        assert get_monitor(session, "owner", original["id"]) == original
    fresh(db, grants, 901)
    result, calls = run(db, settings, payload, second=901, network=False)
    assert result["state"] == "cached" and calls == []
    assert scans.count("transfers.txt") == 1  # One shared rule scan for the mapped batch.
    with db.session() as session:
        assert get_monitor(session, "owner", original["id"]) == original
        mapped = resolve_configuration(session, config, service_day=NOW.date(), static_version=VERSION)
        assert {leg.reference.trip_id for leg in mapped.values()} == {"new-trip", "new-next"}
        assert all(leg.departure.astimezone(ZURICH).date() == NOW.date() + timedelta(days=1) for leg in mapped.values())
        assert journey_interchanges(session, config, mapped)[0]["state"] == expected
        assert session.get(CommuteInterchange, (ids[0], ids[1], old_proof_day(), "20260909")).proof == old_proof
        if expected == "minimum_met":
            started = command(session, "owner", original["id"], original["version"], "start",
                              settings=settings, now=NOW + timedelta(seconds=901))
            assert started["status"] == "active" and started["configuration"] == original["configuration"]
        else:
            with pytest.raises(DomainError) as error:
                command(session, "owner", original["id"], original["version"], "start",
                        settings=settings, now=NOW + timedelta(seconds=901))
            # Lifecycle API deliberately exposes one readiness error; the
            # specific denied interchange is available in the preview above.
            assert error.value.code == "commute_source_not_ready"
            assert get_monitor(session, "owner", original["id"]) == original


def old_proof_day():
    from datetime import date
    return date(2026, 9, 11)


@pytest.mark.parametrize("change,code", [("revoked", "commute_source_permission_unavailable"),
    ("lease", "static_lease_lost"), ("reference", "commute_reference_unavailable"),
    ("feed", "static_renewal_source_changed")])
def test_changes_during_scan_do_not_advance_cursor_or_publish_mappings(db, tmp_path, connected, monkeypatch, change, code):
    grants, settings = setup(db, tmp_path)
    ids, _ = seed(db, tmp_path, connected)
    fresh(db, grants, 1)
    # Make current local date have a genuine service so publication is attempted.
    connected["calendar_dates.txt"].append(["weekday", "20260913", "1"])
    payload = archive(tmp_path, connected).read_bytes()
    original_rows, changed = StaticArchive.rows, False
    replacement = str(uuid4())

    def mutate(source, name, *args, **kwargs):
        nonlocal changed
        if name == "stop_times.txt" and not changed:
            changed = True
            assert db.engine.pool.checkedout() == 0
            if change == "feed":
                fresh(db, grants, 2, "20260913")
            else:
                with db.session() as session:
                    if change == "revoked":
                        session.get(CommuteSourcePermission, next(iter(grants.values()))).revoked_at = NOW
                    elif change == "lease":
                        session.get(CommuteStaticPoll, "static").lease_token = replacement
                    else:
                        session.get(CommuteLegReference, ids[0]).enabled = False
                    session.commit()
        yield from original_rows(source, name, *args, **kwargs)

    monkeypatch.setattr(StaticArchive, "rows", mutate)
    result, _ = run(db, settings, payload, second=2)
    assert result == {"state": "unavailable", "code": code}
    with db.session() as session:
        poll = session.get(CommuteStaticPoll, "static")
        assert poll.renewal_state == {}
        if change == "lease":
            assert poll.lease_token == replacement
        assert len(session.scalars(select(CommuteDatedLeg)).all()) == 2
        assert len(session.scalars(select(CommuteInterchange)).all()) == 1


def test_persisted_cursor_visits_every_reference_and_resets_for_new_day_or_version(db, tmp_path, tables):
    source_leg = resolve(archive(tmp_path, tables))
    with db.session() as session:
        refs = set(publish_legs(session, tuple(replace(source_leg, departure=source_leg.departure + timedelta(seconds=i))
                                              for i in range(17))))
        session.commit()
    state, visited = {}, set()
    for iteration in range(16):
        with db.session() as session:
            state, prepared = worker.plan(session, state, VERSION, NOW.date())
            assert len(prepared[0]) <= 32
            before = len(visited)
            visited.update(prepared[0])
            assert len(visited) == before + len(prepared[0])
            poll = session.get(CommuteStaticPoll, "static")
            if poll is None:
                poll = CommuteStaticPoll(id="static", next_attempt_at=NOW)
                session.add(poll)
            poll.renewal_state = state
            session.commit()
        # Read a new ORM object/session each time: there is no in-memory cursor.
        with db.session() as session:
            state = session.get(CommuteStaticPoll, "static").renewal_state
        assert state["complete"] is (iteration == 15)
    assert len(visited) == 17 * 8 and {key[0] for key in visited} == refs
    assert {day for _, day in visited} == {NOW.date() + timedelta(days=i - 1) for i in range(8)}
    with db.session() as session:
        assert worker.plan(session, state, VERSION, NOW.date())[1] is None
        next_day, prepared = worker.plan(session, state, VERSION, NOW.date() + timedelta(days=1))
        assert prepared and next_day["anchor"] == (NOW.date() + timedelta(days=1)).isoformat()
        next_version, prepared = worker.plan(session, state, "20260913", NOW.date())
        assert prepared and not next_version["complete"] and next_version["offset"] == 0


def test_scan_deadline_leaves_original_cursor_for_retry(db, tmp_path, connected):
    grants, settings = setup(db, tmp_path)
    seed(db, tmp_path, connected)
    fresh(db, grants, 1)
    token = collector.claim(db, grants, NOW + timedelta(seconds=1))
    path = archive(tmp_path, connected)
    moments = iter((0, worker.SCAN_SECONDS + 1))
    with pytest.raises(acquisition.AcquisitionError, match="static_renewal_timeout"):
        worker.renew_cached(db, settings, path, VERSION, sha256(path.read_bytes()).hexdigest(), token, grants,
                            now=lambda: NOW + timedelta(seconds=1), monotonic=lambda: next(moments))
    with db.session() as session:
        assert session.get(CommuteStaticPoll, "static").renewal_state == {}
        assert len(session.scalars(select(CommuteDatedLeg)).all()) == 2


def test_failed_publication_rolls_back_mappings_and_cursor_then_retries_from_cache(db, tmp_path, connected, monkeypatch):
    grants, settings = setup(db, tmp_path)
    seed(db, tmp_path, connected)
    connected["calendar_dates.txt"].append(["weekday", "20260913", "1"])
    payload = archive(tmp_path, connected).read_bytes()
    original = worker.publish_renewal

    def interrupted(*args, **kwargs):
        original(*args, **kwargs)
        raise OSError("synthetic failure before transaction commit")

    monkeypatch.setattr(worker, "publish_renewal", interrupted)
    fresh(db, grants, 1)
    result, _ = run(db, settings, payload)
    assert result == {"state": "unavailable", "code": "static_cache_error"}
    with db.session() as session:
        assert session.get(CommuteStaticPoll, "static").renewal_state == {}
        assert len(session.scalars(select(CommuteDatedLeg)).all()) == 2
        assert len(session.scalars(select(CommuteInterchange)).all()) == 1
    monkeypatch.setattr(worker, "publish_renewal", original)
    fresh(db, grants, 3001)
    result, calls = run(db, settings, payload, second=3001, network=False)
    assert result["state"] == "cached" and calls == []
    with db.session() as session:
        state = session.get(CommuteStaticPoll, "static").renewal_state
        assert state["offset"] == 1 and state["last_outcomes"] == {"mapped": 2}
        assert len(session.scalars(select(CommuteDatedLeg)).all()) == 4
        assert len(session.scalars(select(CommuteInterchange)).all()) == 2


def test_connection_work_survives_page_boundaries_without_concatenating_singles(db, tmp_path, connected, monkeypatch):
    ids, _ = seed(db, tmp_path, connected)
    monkeypatch.setattr(worker, "BATCH_UNITS", 1)
    state, connections, targets = {}, [], set()
    for _ in range(3):
        with db.session() as session:
            state, prepared = worker.plan(session, state, VERSION, NOW.date())
        targets.update(prepared[0])
        connections.extend(prepared[1])
    day = NOW.date() - timedelta(days=1)
    assert targets == {(value, day) for value in ids}
    assert connections == [(ids[0], ids[1], day)]
    assert state["offset"] == 1 and state["after"] == ["", ""]
