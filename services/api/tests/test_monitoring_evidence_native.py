"""Exercise the six personal directions using actual source ingestion fixtures."""

from datetime import timedelta

import pytest
from sqlalchemy import select
from test_air_watch import api as _air_api_fixture
from test_river_watch import api as _river_api_fixture
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens import monitoring_evidence_ask as ask
from helvetic_lens.config import DomainError

air_api, river_api = _air_api_fixture, _river_api_fixture


def check(db, config, record, now, user="owner"):
    with db.session() as session:
        value = ask.answer(session, config, user, record, now=now, locale="en-CH")
        assert value["extracts"] and not session.new and not session.dirty and not session.deleted
        same = ask.answer(session, config, user, record, now=now, locale="en-CH", expected_binding=value["binding"])
        assert value == same
        later = ask.answer(session, config, user, record, now=now + timedelta(seconds=1),
            locale="en-CH", expected_binding=value["binding"])
        assert later["binding"] == value["binding"] and later["extracts"] == value["extracts"]
        return value


def test_pollen_exact_sample_and_source_withdrawal(db):
    from test_monitoring_runtime import NOW, command, input_sample, policy, seed

    from helvetic_lens import monitoring_runtime
    subject = seed(db)
    input_sample(db, "20")
    command(db, subject)
    with db.session() as session:
        entry = monitoring_runtime.history(session, user_id="owner", subject_id=subject)["items"][0]
    record = ask.Record("pollen", subject, entry["id"])
    value = check(db, policy(), record, NOW)
    assert any(row["quote"] == "20" for row in value["extracts"])
    withdrawn = policy()
    withdrawn.pollen_source_policy = type(withdrawn.pollen_source_policy)(channels=[])
    with db.session() as session, pytest.raises(DomainError):
        ask.answer(session, withdrawn, "owner", record, now=NOW, locale="en-CH", expected_binding=value["binding"])


def test_river_native_threshold_and_cross_owner(river_api):
    from test_river_watch import command, create, events, run, sample, store
    client, service, config, identity, now = river_api
    monitor = command(client, create(client), "start")
    run(service, monitor["id"], now)
    later = now + timedelta(minutes=10)
    with service.db.session() as session:
        store(session, sample(later, value="2.6"))
        session.commit()
    run(service, monitor["id"], later)
    entry = events(service, monitor["id"])[0]
    record = ask.Record("river", monitor["id"], entry.id)
    check(service.db, config, record, later, identity["user"]["id"])
    with service.db.session() as session, pytest.raises(DomainError):
        ask.answer(session, config, "missing", record, now=later, locale="en-CH")


def test_air_native_hourly_value(air_api):
    from test_air_watch import changes, command, create, feed, run, source_rows
    client, service, config, identity, now = air_api
    monitor = command(client, create(client), "start")
    run(service, monitor, now)
    later = now + timedelta(hours=1)
    feed(service.db, later, source_rows(later, 60))
    run(service, monitor, later)
    entry = changes(client, monitor)[0]
    check(service.db, config, ask.Record("air", monitor["id"], entry["id"]), later, identity["user"]["id"])


def test_commute_native_saved_feed_and_permission_revocation(db):
    from test_commute_jobs import NOW, refresh, scenario

    from helvetic_lens.commute_models import CommuteDevelopment, CommuteSourcePermission
    monitor, grants, config = scenario(db)
    refresh(db, monitor, config)
    with db.session() as session:
        event = session.scalar(select(CommuteDevelopment.id))
    record = ask.Record("commute", monitor["id"], event, 1)
    value = check(db, config, record, NOW)
    with db.session() as session:
        for identifier in grants.values():
            session.get(CommuteSourcePermission, identifier).revoked_at = NOW
        session.commit()
    with db.session() as session, pytest.raises(DomainError):
        ask.answer(session, config, "owner", record, now=NOW, locale="en-CH", expected_binding=value["binding"])


def test_road_native_snapshot_and_revoked_source(db):
    from test_road_jobs import NOW, current, refresh, setup

    from helvetic_lens.road_sources import revoke_permission
    monitor, permission, _, config = setup(db)
    refresh(db, monitor, config)
    event = current(db, monitor)
    record = ask.Record("traffic", monitor["id"], event["id"], 1)
    value = check(db, config, record, NOW)
    with db.session() as session:
        revoke_permission(session, permission, now=NOW)
        session.commit()
    with db.session() as session, pytest.raises(DomainError):
        ask.answer(session, config, "owner", record, now=NOW, locale="en-CH", expected_binding=value["binding"])


def test_hazard_original_instructions_and_revoked_source(db, monkeypatch):
    from test_hazard_lifecycle import ScopeFixture
    from test_hazard_meteoalarm_workflow import NOW, setup

    from helvetic_lens import hazard_boundary_store
    from helvetic_lens.hazard_sources import revoke_permission
    store = ScopeFixture()
    monitor, permission, config, _, event = setup(db, store)
    monkeypatch.setattr(hazard_boundary_store, "BoundaryStore", lambda _: store)
    record = ask.Record("warnings", monitor["id"], event, 1)
    check(db, config, record, NOW)
    with db.session() as session:
        _, source = ask.native(session, config, "owner", record, now=NOW)
        assert any("instruction" in row["pointer"] for row in ask.extracts(source))
        revoke_permission(session, permission, now=NOW)
        session.commit()
    with db.session() as session, pytest.raises(DomainError):
        ask.answer(session, config, "owner", record, now=NOW, locale="en-CH")
