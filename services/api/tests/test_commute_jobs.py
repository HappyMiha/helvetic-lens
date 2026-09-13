from datetime import timedelta

import pytest
from sqlalchemy import select
from test_commute_contracts import NOW
from test_commute_repository import create, seeded
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture
from test_transport_feed import alert_feed, feed, trip_feed

from helvetic_lens import commute_events as events
from helvetic_lens import commute_jobs as worker
from helvetic_lens import commute_repository as repository
from helvetic_lens.commute_models import (
    CommuteDevelopment,
    CommuteEventVersion,
    CommuteFeedState,
    CommuteMonitor,
    CommuteSignal,
    CommuteSourcePermission,
)
from helvetic_lens.commute_sources import accept_feed, read_feed, record_permission
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.models import Job, OutboxMessage
from helvetic_lens.transport_feed import ALERTS, TRIPS

db, template = _database_fixture, _template_fixture


def source_grants(database):
    with database.session() as session:
        ids = {source: record_permission(session, source=source, policy_reference="synthetic fixture review only",
            accepted_at=NOW - timedelta(days=1), valid_until=NOW + timedelta(days=10), max_age_seconds=180)
            for source in (TRIPS, ALERTS)}
        session.commit()
    return ids


def capture(database, permission, message, *, second=0):
    with database.session() as session:
        result = accept_feed(session, permission, message.SerializeToString(), now=NOW + timedelta(seconds=second))
        session.commit()
        return result


def scenario(database, *, delay=600):
    payload = seeded(database)
    row = create(database, payload=payload)
    grants = source_grants(database)
    capture(database, grants[TRIPS], trip_feed(delay=delay))
    capture(database, grants[ALERTS], feed())
    settings = Settings(_env_file=None, commute_watch_enabled=True)
    with database.session() as session:
        row = repository.command(session, "owner", row["id"], row["version"], "start", now=NOW, settings=settings)
        session.commit()
    return row, grants, settings


def refresh(database, row, settings, *, second=0):
    return worker.refresh(database, settings, monitor_id=row["id"], version=row["version"], now=NOW + timedelta(seconds=second))


def totals(database):
    with database.session() as session:
        return tuple(len(session.scalars(select(model)).all()) for model in (CommuteDevelopment, CommuteEventVersion, CommuteSignal))


def test_feed_to_private_history_is_atomic_replay_safe_and_low_noise(db):
    row, grants, settings = scenario(db, delay=60)
    assert refresh(db, row, settings)["signals"] == 0
    assert totals(db) == (1, 1, 0)
    for second, delay in ((1, 120), (2, 240), (3, 600)):
        capture(db, grants[TRIPS], trip_feed(delay=delay, second=second), second=second)
        refresh(db, row, settings, second=second)
    assert totals(db) == (1, 2, 1)
    assert refresh(db, row, settings, second=3)["signals"] == 0
    assert totals(db) == (1, 2, 1)
    capture(db, grants[TRIPS], trip_feed(cancelled=True, second=4), second=4)
    refresh(db, row, settings, second=4)
    capture(db, grants[TRIPS], trip_feed(delay=0, second=5), second=5)
    refresh(db, row, settings, second=5)
    assert totals(db) == (1, 4, 3)
    with db.session() as session:
        page = events.events_page(session, "owner", row["id"], now=NOW + timedelta(seconds=5))
        event = page["items"][0]
        assert set(s["condition"] for s in event["current"]["states"].values()) == {"restored"}
        history = events.history_page(session, "owner", event["id"], now=NOW + timedelta(seconds=5))
        assert [v["sequence"] for v in history["items"]] == [1, 2, 3, 4]
        assert history["items"][0]["evidence"]["evidence_kind"] == "normalized_source_fields"
        assert next(iter(history["items"][0]["evidence"]["legs"].values()))["archive_sha256"] == "a" * 64
        assert session.scalars(select(CommuteSignal).where(CommuteSignal.priority == "urgent")).one().sequence == 3


def test_disappearance_and_staleness_preserve_last_cancellation_without_restoration(db):
    row, grants, settings = scenario(db)
    capture(db, grants[TRIPS], trip_feed(cancelled=True, second=1), second=1)
    refresh(db, row, settings, second=1)
    capture(db, grants[TRIPS], feed(second=2), second=2)
    refresh(db, row, settings, second=2)
    with db.session() as session:
        event = session.scalars(select(CommuteDevelopment)).one()
        state = next(iter(event.current["states"].values()))
        assert state["condition"] == "cancelled" and state["availability"] == "missing"
    assert totals(db) == (1, 2, 1)
    refresh(db, row, settings, second=300)
    with db.session() as session:
        event = session.scalars(select(CommuteDevelopment)).one()
        assert next(iter(event.current["states"].values()))["availability"] == "stale"
        assert session.get(CommuteMonitor, row["id"]).health == "stale"
    assert totals(db) == (1, 3, 1)


def test_exact_review_and_mute_do_not_auto_review_future_changes(db):
    row, grants, settings = scenario(db)
    refresh(db, row, settings)
    with db.session() as session:
        event = session.scalars(select(CommuteDevelopment)).one()
        reviewed = events.review_event(session, "owner", event.id, event.version, event.sequence, now=NOW)
        assert reviewed["reviewed_sequence"] == 1
        session.commit()
    capture(db, grants[TRIPS], trip_feed(cancelled=True, second=1), second=1)
    refresh(db, row, settings, second=1)
    with db.session() as session:
        event = session.scalars(select(CommuteDevelopment)).one()
        assert event.sequence == 2 and event.reviewed_sequence == 1
        with pytest.raises(DomainError):
            events.review_event(session, "owner", event.id, reviewed["version"], 1, now=NOW)
        muted = events.review_event(session, "owner", event.id, event.version, 2, now=NOW, muted=True)
        assert muted["muted"] and muted["reviewed_sequence"] == 1
        session.commit()
    capture(db, grants[TRIPS], trip_feed(delay=0, second=2), second=2)
    refresh(db, row, settings, second=2)
    assert totals(db) == (1, 3, 2)
    with db.session() as session:
        assert session.scalars(select(CommuteSignal).where(CommuteSignal.state == "pending")).all() == []


def test_revoked_rights_hide_evidence_and_new_grant_does_not_reveal_old_history(db):
    row, grants, settings = scenario(db)
    refresh(db, row, settings)
    with db.session() as session:
        event_id = session.scalars(select(CommuteDevelopment.id)).one()
        session.get(CommuteSourcePermission, grants[TRIPS]).revoked_at = NOW
        session.commit()
    with db.session() as session:
        assert events.events_page(session, "owner", row["id"], now=NOW)["items"] == [{"id": event_id, "available": False}]
        with pytest.raises(DomainError):
            events.history_page(session, "owner", event_id, now=NOW)
    result = refresh(db, row, settings)
    assert "commute_source_permission_unavailable" in result["failures"]
    newer = source_grants(db)
    capture(db, newer[TRIPS], trip_feed(second=1), second=1)
    refresh(db, row, settings, second=1)
    assert totals(db)[0] == 2
    with db.session() as session:
        with pytest.raises(DomainError):
            events.history_page(session, "owner", event_id, now=NOW + timedelta(seconds=1))


def test_bad_or_old_feed_cannot_replace_the_last_accepted_snapshot(db):
    grants = source_grants(db)
    assert capture(db, grants[TRIPS], trip_feed(second=10), second=10) == "accepted"
    assert capture(db, grants[TRIPS], trip_feed(second=10), second=11) == "replay"
    assert capture(db, grants[TRIPS], trip_feed(second=9), second=11) == "older"
    with db.session() as session:
        original = session.get(CommuteFeedState, TRIPS).content_hash
        with pytest.raises(ValueError):
            accept_feed(session, grants[TRIPS], b"<html>sign in</html>", now=NOW + timedelta(seconds=12))
        with pytest.raises(DomainError):
            accept_feed(session, grants[TRIPS], trip_feed(delay=0, second=10).SerializeToString(), now=NOW + timedelta(seconds=12))
        assert session.get(CommuteFeedState, TRIPS).content_hash == original
        with pytest.raises(DomainError):
            read_feed(session, TRIPS, now=NOW + timedelta(seconds=300), require_fresh=True)
        with pytest.raises(DomainError) as future:
            read_feed(session, TRIPS, now=NOW, require_fresh=True)
        assert future.value.code == "commute_feed_future"


def test_capacity_failure_rolls_back_checkpoints_history_and_candidates_together(db, monkeypatch):
    row, grants, settings = scenario(db)
    refresh(db, row, settings)
    before = totals(db)
    with db.session() as session:
        old = session.scalars(select(CommuteDevelopment)).one().checkpoints
    monkeypatch.setattr(events, "MAX_HISTORY_BYTES", 1)
    capture(db, grants[TRIPS], trip_feed(cancelled=True, second=1), second=1)
    result = refresh(db, row, settings, second=1)
    assert "commute_storage_limit" in result["failures"] and totals(db) == before
    with db.session() as session:
        assert session.scalars(select(CommuteDevelopment)).one().checkpoints == old


def test_scheduler_pause_and_superseded_job_use_durable_outbox(db):
    row, _, settings = scenario(db)
    with db.session() as session:
        assert len(session.scalars(select(Job).where(Job.target_id == row["id"])).all()) == 1
        assert len(session.scalars(select(OutboxMessage)).all()) == 1
    assert worker.enqueue_due(db, settings, now=NOW)["enqueued"] == 0
    assert worker.refresh(db, settings, monitor_id=row["id"], version=1, now=NOW)["state"] == "superseded"
    with db.session() as session:
        paused = repository.command(session, "owner", row["id"], row["version"], "pause", now=NOW)
        session.commit()
        assert session.scalars(select(Job)).one().cancel_requested
    assert worker.refresh(db, settings, monitor_id=row["id"], version=paused["version"], now=NOW)["state"] == "superseded"
    assert worker.enqueue_due(db, settings, now=NOW + timedelta(minutes=1))["enqueued"] == 0


def test_worker_and_history_cannot_cross_owner_or_organization(db):
    row, _, settings = scenario(db)
    refresh(db, row, settings)
    with db.session() as session:
        event = session.scalars(select(CommuteDevelopment)).one()
        with pytest.raises(DomainError):
            events.history_page(session, "peer", event.id, now=NOW)
        with pytest.raises(DomainError):
            events.events_page(session, "peer", row["id"], now=NOW)
    with db.organization_context("org-b"):
        assert refresh(db, row, settings)["state"] == "superseded"


def test_notice_language_change_updates_same_development_without_replay_spam(db):
    row, grants, settings = scenario(db, delay=0)
    capture(db, grants[ALERTS], alert_feed(second=1), second=1)
    refresh(db, row, settings, second=1)
    counts = totals(db)
    assert refresh(db, row, settings, second=1)["signals"] == 0
    message = alert_feed(second=2)
    message.entity[0].alert.header_text.translation[0].text = "Changed official notice"
    capture(db, grants[ALERTS], message, second=2)
    assert refresh(db, row, settings, second=2)["signals"] == 1
    assert totals(db) == (counts[0], counts[1] + 1, counts[2] + 1)


def test_history_fingerprint_rejects_changed_evidence(db):
    row, _, settings = scenario(db)
    refresh(db, row, settings)
    with db.session() as session:
        event = session.scalars(select(CommuteDevelopment)).one()
        version = session.scalars(select(CommuteEventVersion)).one()
        version.evidence = {**version.evidence, "feed_sha256": "changed"}
        session.flush()
        with pytest.raises(DomainError) as error:
            events.history_page(session, "owner", event.id, now=NOW)
        assert error.value.code == "commute_event_invalid"


def test_reader_reports_stale_data_without_waiting_for_worker_or_rewriting_history(db):
    row, _, settings = scenario(db)
    refresh(db, row, settings)
    with db.session() as session:
        event = events.events_page(session, "owner", row["id"], now=NOW + timedelta(minutes=5))["items"][0]
        assert next(iter(event["current"]["states"].values()))["availability"] == "stale"
        stored = session.get(CommuteDevelopment, event["id"])
        assert next(iter(stored.current["states"].values()))["availability"] == "present"
        historical = events.history_page(session, "owner", event["id"], now=NOW + timedelta(minutes=5))
        assert next(iter(historical["items"][0]["evidence"]["current"]["states"].values()))["availability"] == "present"


def test_empty_complete_feeds_do_not_claim_on_time_running(db):
    row, grants, settings = scenario(db)
    capture(db, grants[TRIPS], feed(second=1), second=1)
    result = refresh(db, row, settings, second=1)
    assert result["signals"] == 0 and totals(db) == (0, 0, 0)
    with db.session() as session:
        assert session.get(CommuteMonitor, row["id"]).health == "waiting_for_predictions"


def test_worker_migration_preserves_populated_private_drafts(db):
    import json
    from pathlib import Path
    from uuid import uuid4

    from alembic.config import Config
    from sqlalchemy import text

    from alembic import command
    from helvetic_lens.commute_contracts import digest
    from helvetic_lens.commute_sources import utc

    payload = seeded(db)
    identifier = str(uuid4())
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "f6c8da371a9e")
        connection.execute(text("INSERT INTO commute_monitors (id, organization_id, owner_user_id, request_key, request_hash, configuration, revision, version, status, health, created_at) VALUES (:id, 'org-a', 'owner', 'migration-old', :hash, :config, 1, 1, 'draft', 'not_started', :now)"),
            {"id": identifier, "hash": digest(payload), "config": json.dumps(payload), "now": NOW.isoformat()})
        command.upgrade(config, "head")
    with db.session() as session:
        row = session.get(CommuteMonitor, identifier)
        assert row.configuration == payload and row.status == "draft" and row.revision == 1
        assert utc(row.next_poll_at).year == 1970 and row.last_poll_at is None


@pytest.mark.asyncio
async def test_real_job_dispatch_private_http_review_and_same_workspace_job_guards(tmp_path, monkeypatch):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_auth import _csrf, _register, _settings
    from test_commute_api import ROOT
    from test_commute_api import create as create_http

    from helvetic_lens import commute_api
    from helvetic_lens.main import create_app
    from helvetic_lens.models import OrganizationMembership

    settings = _settings(tmp_path, commute_watch_enabled=True)
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    original = worker.refresh
    monkeypatch.setattr(worker, "refresh", lambda *args, **kwargs: original(*args, **kwargs, now=NOW))
    monkeypatch.setattr(commute_api, "clock", lambda: NOW)
    with TestClient(app) as client:
        identity = _register(client).json()
        service, user_id, organization = app.state.service, identity["user"]["id"], identity["organization"]["id"]
        payload = seeded(service.db)
        grants = source_grants(service.db)
        capture(service.db, grants[TRIPS], trip_feed())
        capture(service.db, grants[ALERTS], feed())
        row = create_http(client, payload)
        preview = client.post(ROOT + "/preview", json={"configuration": payload, "service_day": "2026-09-14",
            "static_version": "20260909"}, headers=_csrf(client))
        assert preview.status_code == 200 and preview.json()["start_available"]
        start = client.post(ROOT + f"/monitors/{row['id']}/commands", json={"action": "start", "expected_version": 1}, headers=_csrf(client))
        assert start.status_code == 200 and start.json()["status"] == "active"
        with service.db.organization_context(organization), service.db.session() as session:
            job_id = session.scalars(select(Job.id).where(Job.target_id == row["id"])).one()
        with TestClient(app) as peer:
            other = _register(peer, email="commute-job-peer@example.test").json()
            with service.db.session(include_all_organizations=True) as session:
                session.add(OrganizationMembership(organization_id=organization, user_id=other["user"]["id"], role="organization_admin"))
                session.commit()
            switched = peer.post("/api/auth/session/organization", json={"organization_id": organization}, headers=_csrf(peer))
            assert switched.status_code == 200
            assert peer.get(f"/api/jobs/{job_id}").status_code == 404
            assert row["id"] not in str(peer.get("/api/jobs").json())
            for action in ("cancel", "retry"):
                assert peer.post(f"/api/jobs/{job_id}/{action}", headers=_csrf(peer)).status_code == 404
        with service.db.organization_context(organization):
            result = await service.execute_job(job_id)
            assert result["state"] == "succeeded", result
        response = client.get(ROOT + f"/monitors/{row['id']}/events")
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        event = response.json()["items"][0]
        history_path = ROOT + f"/events/{event['id']}/history"
        assert client.get(history_path).json()["items"][0]["sequence"] == 1
        reviewed = client.post(ROOT + f"/events/{event['id']}/review", json={"expected_version": event["version"], "sequence": 1}, headers=_csrf(client))
        assert reviewed.status_code == 200 and reviewed.json()["reviewed_sequence"] == 1
        with service.db.organization_context(organization), service.db.session() as session:
            assert session.get(CommuteMonitor, row["id"]).owner_user_id == user_id
            session.get(CommuteSourcePermission, grants[TRIPS]).revoked_at = NOW
            session.commit()
        denied = client.get(history_path)
        assert denied.status_code == 404 and denied.headers["cache-control"] == "no-store"
