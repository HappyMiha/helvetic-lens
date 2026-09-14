"""Six personal native source fixtures for exact private evidence packets."""

from datetime import timedelta

import pytest
from sqlalchemy import select
from test_air_watch import api as _air_api_fixture
from test_river_watch import api as _river_api_fixture
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens.config import DomainError
from helvetic_lens.monitoring_evidence_ask import Record
from helvetic_lens.monitoring_personal_evidence import selected

air_api, river_api = _air_api_fixture, _river_api_fixture


@pytest.fixture(params=("pollen", "air", "river", "warnings", "commute", "traffic"))
def scenario(request, monkeypatch):
    domain = request.param
    user = "owner"
    if domain == "air":
        from test_air_watch import changes, command, create, feed, run, source_rows
        client, service, config, identity, now = request.getfixturevalue("air_api")
        database, user = service.db, identity["user"]["id"]
        monitor = command(client, create(client), "start")
        run(service, monitor, now)
        now += timedelta(hours=1)
        feed(database, now, source_rows(now, 60))
        run(service, monitor, now)
        entry = changes(client, monitor)[0]
        record = Record(domain, monitor["id"], entry["id"])
    elif domain == "river":
        from test_river_watch import command, create, events, run, sample, store
        client, service, config, identity, now = request.getfixturevalue("river_api")
        database, user = service.db, identity["user"]["id"]
        monitor = command(client, create(client), "start")
        run(service, monitor["id"], now)
        now += timedelta(minutes=10)
        with database.session() as session:
            store(session, sample(now, value="2.6"))
            session.commit()
        run(service, monitor["id"], now)
        record = Record(domain, monitor["id"], events(service, monitor["id"])[0].id)
    else:
        database = request.getfixturevalue("db")
        if domain == "pollen":
            from test_monitoring_runtime import NOW, command, input_sample, policy, seed

            from helvetic_lens import monitoring_runtime
            identifier = seed(database)
            input_sample(database, "20")
            command(database, identifier)
            with database.session() as session:
                entry = monitoring_runtime.history(session, user_id=user, subject_id=identifier)["items"][0]
            config, now, record = policy(), NOW, Record(domain, identifier, entry["id"])
        elif domain == "commute":
            from test_commute_jobs import NOW, refresh, scenario

            from helvetic_lens.commute_models import CommuteDevelopment
            monitor, _, config = scenario(database)
            refresh(database, monitor, config)
            with database.session() as session:
                identifier = session.scalar(select(CommuteDevelopment.id))
            now, record = NOW, Record(domain, monitor["id"], identifier, 1)
        elif domain == "traffic":
            from test_road_jobs import NOW, current, refresh, setup
            monitor, _, _, config = setup(database)
            refresh(database, monitor, config)
            now, record = NOW, Record(domain, monitor["id"], current(database, monitor)["id"], 1)
        else:
            from test_hazard_lifecycle import ScopeFixture
            from test_hazard_meteoalarm_workflow import NOW, setup

            from helvetic_lens import hazard_boundary_store
            store = ScopeFixture()
            monitor, _, config, _, identifier = setup(database, store)
            monkeypatch.setattr(hazard_boundary_store, "BoundaryStore", lambda _: store)
            now, record = NOW, Record(domain, monitor["id"], identifier, 1)
    return database, config, user, record, now


def test_personal_packet_preserves_native_selection_and_has_no_write_side_effects(scenario):
    database, config, user, record, now = scenario
    with database.session() as session:
        changes = session.connection().exec_driver_sql("SELECT total_changes()").scalar()
        result = selected(session, config, user, record, now=now)
        repeated = selected(session, config, user, record, now=now + timedelta(seconds=1))
        assert repeated["native_record"] == result["native_record"]
        assert repeated["previous_record"] == result["previous_record"]
        assert session.connection().exec_driver_sql("SELECT total_changes()").scalar() == changes
        assert not result["raw_provider_payload_included"]
        assert result["profile_revision"] == result["configuration"]["revision"]
        if record.sequence:
            assert result["sequence"] == record.sequence
        if record.domain == "pollen":
            assert result["native_record"]["current"]["value"] == "20"
        elif record.domain == "river":
            assert result["native_record"]["evidence"]["sample"]["value"] == "2.6"
        elif record.domain == "traffic":
            assert result["native_record"]["availability"] == "available"
            assert result["native_record"]["attribution"]
        elif record.domain == "warnings":
            assert result["native_record"]["source"]["redistribution"]["disclaimer"]
    with database.session() as session, pytest.raises(DomainError):
        selected(session, config, "missing-user", record, now=now)


def test_commute_historical_packet_does_not_read_a_damaged_newer_snapshot(db):
    from test_commute_jobs import NOW, TRIPS, capture, refresh, scenario
    from test_transport_feed import trip_feed

    from helvetic_lens.commute_models import CommuteDevelopment, CommuteEventVersion

    monitor, grants, settings = scenario(db)
    refresh(db, monitor, settings)
    with db.session() as session:
        identifier = session.scalar(select(CommuteDevelopment.id))
        record = Record("commute", monitor["id"], identifier, 1)
        original = selected(session, settings, "owner", record, now=NOW)
    capture(db, grants[TRIPS], trip_feed(cancelled=True, second=1), second=1)
    refresh(db, monitor, settings, second=1)
    with db.session() as session:
        later = selected(session, settings, "owner", Record("commute", monitor["id"], identifier, 2),
            now=NOW + timedelta(seconds=1))
        assert later["previous_record"] == original["native_record"]
        assert later["native_record"] != original["native_record"]
        latest = session.scalar(select(CommuteEventVersion).where(CommuteEventVersion.development_id == identifier,
            CommuteEventVersion.sequence == 2))
        latest.evidence = {"damaged": "must not substitute this new content for the selected old evidence"}
        session.commit()
    with db.session() as session:
        retained = selected(session, settings, "owner", record, now=NOW + timedelta(minutes=5))
        assert retained["newer_available"]
        assert retained["native_record"] == original["native_record"]
        assert retained["previous_record"] is None
        with pytest.raises(DomainError):
            selected(session, settings, "owner", Record("commute", monitor["id"], identifier, 2), now=NOW)


def test_road_packet_preserves_selected_before_after_and_refuses_missing_previous(db):
    from test_road_feed import feed
    from test_road_feed import record as road_record
    from test_road_jobs import NOW, current, refresh, setup
    from test_road_sources import accept

    from helvetic_lens.road_models import RoadEventVersion

    monitor, permit, _, settings = setup(db)
    refresh(db, monitor, settings)
    identifier = current(db, monitor)["id"]
    old_record = Record("traffic", monitor["id"], identifier, 1)
    with db.session() as session:
        original = selected(session, settings, "owner", old_record, now=NOW)
    accept(db, permit, feed(road_record(code="laneClosures")), minute=1, expected_generation=2)
    refresh(db, monitor, settings, minute=1)
    second_record = Record("traffic", monitor["id"], identifier, 2)
    with db.session() as session:
        second = selected(session, settings, "owner", second_record, now=NOW + timedelta(minutes=1))
        assert second["previous_record"] == original["native_record"]
    accept(db, permit, feed(road_record(code="roadCleared")), minute=2, expected_generation=3)
    refresh(db, monitor, settings, minute=2)
    with db.session() as session:
        retained = selected(session, settings, "owner", second_record, now=NOW + timedelta(minutes=10))
        assert retained["newer_available"]
        assert retained["native_record"] == second["native_record"]
        assert retained["previous_record"] == original["native_record"]
        # A retention gap cannot be reported as the initial state of this event.
        first = session.scalar(select(RoadEventVersion).where(RoadEventVersion.development_id == identifier,
            RoadEventVersion.sequence == 1))
        session.delete(first)
        session.commit()
    with db.session() as session, pytest.raises(DomainError):
        selected(session, settings, "owner", second_record, now=NOW + timedelta(minutes=10))


@pytest.mark.parametrize("kind", ("source", "topology"))
def test_road_packet_rechecks_source_and_topology_permission(db, kind):
    from test_road_jobs import NOW, current, refresh, setup

    from helvetic_lens.road_catalog import revoke_topology
    from helvetic_lens.road_sources import revoke_permission

    monitor, permit, topology, settings = setup(db)
    refresh(db, monitor, settings)
    record = Record("traffic", monitor["id"], current(db, monitor)["id"], 1)
    with db.session() as session:
        selected(session, settings, "owner", record, now=NOW)
        if kind == "source":
            revoke_permission(session, permit, now=NOW)
        else:
            revoke_topology(session, topology, now=NOW)
        session.commit()
    with db.session() as session, pytest.raises(DomainError):
        selected(session, settings, "owner", record, now=NOW)


def test_personal_packet_cannot_borrow_current_configuration_when_saved_revision_is_invalid(scenario):
    from helvetic_lens.air_models import AirRevision
    from helvetic_lens.commute_models import CommuteConfigurationRevision
    from helvetic_lens.hazard_models import HazardConfigurationRevision
    from helvetic_lens.models import MonitoringSubjectRevision
    from helvetic_lens.river_models import RiverRevision
    from helvetic_lens.road_models import RoadConfigurationRevision

    database, config, user, record, now = scenario
    models = {"pollen": MonitoringSubjectRevision, "air": AirRevision, "river": RiverRevision,
        "commute": CommuteConfigurationRevision, "warnings": HazardConfigurationRevision, "traffic": RoadConfigurationRevision}
    model = models[record.domain]
    with database.session() as session:
        packet = selected(session, config, user, record, now=now)
        key = model.subject_id if record.domain == "pollen" else model.monitor_id
        revision = session.scalar(select(model).where(key == record.monitor_id, model.revision == packet["profile_revision"]))
        # The current monitor remains intact; only the selected revision is damaged.
        setattr(revision, "configuration_json" if record.domain == "pollen" else "configuration", {})
        session.commit()
    with database.session() as session, pytest.raises(DomainError):
        selected(session, config, user, record, now=now)


def test_hazard_packet_pins_official_update_and_retains_history_during_stale_live_feed(db, monkeypatch):
    from test_hazard_lifecycle import ScopeFixture
    from test_hazard_meteoalarm_store import (
        FIRST,
        SECOND,
        SENDER,
        SENT,
        accept,
        original,
        snapshot,
        weather_info,
    )
    from test_hazard_meteoalarm_workflow import NOW, setup

    from helvetic_lens import hazard_boundary_store, hazard_jobs

    store = ScopeFixture()
    monkeypatch.setattr(hazard_boundary_store, "BoundaryStore", lambda _: store)
    monitor, permit, settings, cursor, identifier = setup(db, store)
    record = Record("warnings", monitor["id"], identifier, 1)
    with db.session() as session:
        first = selected(session, settings, "owner", record, now=NOW)
    later = NOW + timedelta(minutes=2)
    updated = original(identifier=SECOND, kind="Update", sent="2026-09-13T09:30:00+00:00",
        refs=f"{SENDER},{FIRST},{SENT}", infos=weather_info(instruction="New official instructions."))
    accept(db, permit, snapshot(updated, when=later), cursor)
    assert hazard_jobs.refresh(db, settings, monitor_id=monitor["id"], version=monitor["version"],
        now=later, store=store)["changed"] == 1
    with db.session() as session:
        second = selected(session, settings, "owner", Record("warnings", monitor["id"], identifier, 2), now=later)
        assert second["previous_record"] == first["native_record"]
        assert second["native_record"] != first["native_record"]
        historical = selected(session, settings, "owner", record, now=NOW + timedelta(minutes=10))
        assert historical["newer_available"] and historical["native_record"] == first["native_record"]
        assert historical["previous_record"] is None


def test_commute_packet_refuses_revoked_grant_even_with_retained_versions(db):
    from test_commute_jobs import NOW, TRIPS, refresh, scenario

    from helvetic_lens.commute_models import CommuteDevelopment, CommuteSourcePermission

    monitor, grants, settings = scenario(db)
    refresh(db, monitor, settings)
    with db.session() as session:
        record = Record("commute", monitor["id"], session.scalar(select(CommuteDevelopment.id)), 1)
        selected(session, settings, "owner", record, now=NOW)
        session.get(CommuteSourcePermission, grants[TRIPS]).revoked_at = NOW
        session.commit()
    with db.session() as session, pytest.raises(DomainError):
        selected(session, settings, "owner", record, now=NOW)
