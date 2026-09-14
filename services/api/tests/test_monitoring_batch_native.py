"""Real six-direction collectors and native review state, not mocked adapters."""

from datetime import timedelta

import pytest
from sqlalchemy import select
from test_air_watch import api as _air_fixture
from test_river_watch import api as _river_fixture
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens import monitoring_batch_review as batch
from helvetic_lens import monitoring_evidence_ask as evidence
from helvetic_lens.config import DomainError

air_api, river_api = _air_fixture, _river_fixture


def apply(db, settings, record, now, user="owner"):
    from helvetic_lens.monitoring_notifications import page
    from helvetic_lens.prompt_settings import PromptSettings
    with db.session() as session:
        queue = page(session, settings, user, domain=record.domain, now=now, prompts=PromptSettings())
        for item in queue["items"]:
            batch.preview(session, settings, user, [evidence.Record(**item["record"])], now=now, locale="en-CH")
        result = batch.preview(session, settings, user, [record], now=now, locale="en-CH")
        assert result["items"][0]["actions"] == ["reviewed"]
        binding = result["items"][0]["binding"]
        batch.apply(session, settings, user, [(record, binding, "reviewed")], now=now, locale="en-CH")
        session.commit()
    with db.session() as session:
        with pytest.raises(DomainError):
            batch.apply(session, settings, user, [(record, binding, "reviewed")], now=now, locale="en-CH")
        return evidence.native(session, settings, user, record, now=now)[0]


def test_pollen_review_preserves_exact_entry(db):
    from test_monitoring_runtime import NOW, command, input_sample, policy, seed

    from helvetic_lens import monitoring_runtime
    subject = seed(db)
    input_sample(db, "20")
    command(db, subject)
    with db.session() as session:
        entry = monitoring_runtime.history(session, user_id="owner", subject_id=subject)["items"][0]
    result = apply(db, policy(), evidence.Record("pollen", subject, entry["id"]), NOW)
    assert result["entry"]["review"]["decision"] == "reviewed"
    assert result["entry"]["current"]["value"] == "20"


def test_river_review_is_native_and_preserves_threshold(river_api):
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
    result = apply(service.db, config, evidence.Record("river", monitor["id"], entry.id), later, identity["user"]["id"])
    assert result["event"]["decision"] == "reviewed" and result["event"]["review_version"] == 1


def test_air_review_is_native(air_api):
    from test_air_watch import changes, command, create, feed, run, source_rows
    client, service, config, identity, now = air_api
    monitor = command(client, create(client), "start")
    run(service, monitor, now)
    later = now + timedelta(hours=1)
    feed(service.db, later, source_rows(later, 60))
    run(service, monitor, later)
    entry = changes(client, monitor)[0]
    result = apply(service.db, config, evidence.Record("air", monitor["id"], entry["id"]), later, identity["user"]["id"])
    assert result["event"]["decision"] == "reviewed" and result["event"]["review_version"] == 1


def test_commute_review_is_native_and_not_muted(db):
    from test_commute_jobs import NOW, refresh, scenario

    from helvetic_lens.commute_models import CommuteDevelopment
    monitor, _, config = scenario(db)
    refresh(db, monitor, config)
    with db.session() as session:
        event = session.scalar(select(CommuteDevelopment.id))
    result = apply(db, config, evidence.Record("commute", monitor["id"], event, 1), NOW)
    assert result["event"]["reviewed_sequence"] == 1 and not result["event"]["muted"]


def test_road_review_is_native_and_not_muted(db):
    from test_road_jobs import NOW, current, refresh, setup
    monitor, _, _, config = setup(db)
    refresh(db, monitor, config)
    event = current(db, monitor)
    result = apply(db, config, evidence.Record("traffic", monitor["id"], event["id"], 1), NOW)
    assert result["event"]["reviewed_sequence"] == 1 and not result["event"]["muted"]


def test_hazard_review_keeps_official_state(db, monkeypatch):
    from test_hazard_lifecycle import ScopeFixture
    from test_hazard_meteoalarm_workflow import NOW, setup

    from helvetic_lens import hazard_boundary_store
    store = ScopeFixture()
    monitor, _, config, _, event = setup(db, store)
    monkeypatch.setattr(hazard_boundary_store, "BoundaryStore", lambda _: store)
    record = evidence.Record("warnings", monitor["id"], event, 1)
    with db.session() as session:
        before, _ = evidence.native(session, config, "owner", record, now=NOW)
    result = apply(db, config, record, NOW)
    assert result["reviewed"] and result["decision"] == before["decision"] and not result["muted"]
