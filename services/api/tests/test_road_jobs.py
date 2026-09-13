from datetime import timedelta

import pytest
from sqlalchemy import func, select, update
from test_road_catalog import policy as topology_policy
from test_road_feed import NOW, comment, feed, record, situation
from test_road_sources import accept, grant
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens import road_events as events
from helvetic_lens import road_jobs as worker
from helvetic_lens import road_repository as repository
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.models import Job, User
from helvetic_lens.monitoring_subjects import _savepoint
from helvetic_lens.road_acquisition import cleanup
from helvetic_lens.road_catalog import (
    CorridorIdentity,
    create_reference,
    publish_mapping,
    publish_topology,
    revoke_topology,
)
from helvetic_lens.road_models import RoadDevelopment, RoadEventVersion, RoadMonitor
from helvetic_lens.road_sources import revoke_permission
from helvetic_lens.road_topology import CorridorFlow, TmcPoint, TopologyDefinition

db, template = _database_fixture, _template_fixture


def setup(database, *, xml=None, reverse=False, fields=None, user_id="owner", notifications=False, topology_notifications=None):
    permission = grant(database, allowed_fields=fields or ("event_kind", "validity", "location", "delay", "lanes"),
                       notifications_allowed=notifications)
    accept(database, permission, xml)
    with database.session() as session:
        topo = publish_topology(session, definition=TopologyDefinition(country="4", table="9", version="synthetic-1", points=(
            TmcPoint(code=100, positive=110, distance_to_positive_m=1000),
            TmcPoint(code=110, negative=100, positive=120, distance_to_positive_m=1000),
            TmcPoint(code=120, negative=110))), asset_hash="a" * 64,
            policy=topology_policy(notifications_allowed=notifications if topology_notifications is None else topology_notifications), now=NOW)
        ref = create_reference(session, identity=CorridorIdentity(key="synthetic-north", name="Synthetic northbound", flow_key="north"))
        publish_mapping(session, ref, topology_id=topo,
            flow=CorridorFlow(key="north", points=(120, 110, 100) if reverse else (100, 110, 120)),
            review_reference="test-only", expected_generation=0, now=NOW)
        row = repository.create_monitor(session, user_id, {"name": "Private road", "corridor_reference_ids": [ref]}, "save")
        settings = Settings(_env_file=None, road_watch_enabled=True, road_source_enabled=True, road_source_permission_id=permission)
        row = repository.command(session, user_id, row["id"], 1, "start", settings=settings, now=NOW)
        session.commit()
    return row, permission, topo, settings


def refresh(database, row, settings, *, minute=0):
    return worker.refresh(database, settings, monitor_id=row["id"], version=row["version"], now=NOW + timedelta(minutes=minute))


def totals(database):
    with database.session() as session:
        return tuple(session.scalar(select(func.count()).select_from(model)) for model in (RoadDevelopment, RoadEventVersion))


def current(database, row, *, minute=0):
    with database.session() as session:
        return events.events_page(session, "owner", row["id"], now=NOW + timedelta(minutes=minute))["items"][0]


def states(item):
    return {c["state"] for c in item["payload"]["corridors"].values()}


def test_saved_profile_to_material_history_and_explicit_clearance_preserves_identity(db):
    row, permission, _, settings = setup(db)
    assert refresh(db, row, settings)["changed"] == 1
    first = current(db, row)
    assert states(first) == {"active"}
    assert refresh(db, row, settings)["changed"] == 0 and totals(db) == (1, 1)
    accept(db, permission, feed(record(code="laneClosures")), minute=1, expected_generation=2)
    assert refresh(db, row, settings, minute=1)["changed"] == 1
    accept(db, permission, feed(record(code="roadCleared")), minute=2, expected_generation=3)
    assert refresh(db, row, settings, minute=2)["changed"] == 1
    last = current(db, row, minute=2)
    assert last["id"] == first["id"] and states(last) == {"cleared"}
    with db.session() as session:
        history = events.history_page(session, "owner", first["id"], now=NOW + timedelta(minutes=2))
        assert [item["sequence"] for item in history["items"]] == [1, 2, 3]
        text = str(history)
        assert "primary" not in text and "test-supplier" not in text and "Road closed" not in text


def test_source_record_replacement_and_language_editions_do_not_duplicate_material_events(db):
    xml = feed(record(identifier="a", comments=comment(language="de")) + record(identifier="b", comments=comment(language="fr")))
    row, permission, _, settings = setup(db, xml=xml)
    assert refresh(db, row, settings)["changed"] == 1
    first = current(db, row)
    assert len(next(iter(first["payload"]["corridors"].values()))["facts"]) == 1
    accept(db, permission, feed(record(identifier="replacement", comments=comment("Internal", kind="internalNote"))),
           minute=1, expected_generation=2)
    assert refresh(db, row, settings, minute=1)["changed"] == 0
    assert totals(db) == (1, 1)


def test_opposite_flow_and_initial_clearance_do_not_create_an_alert(db):
    row, _, _, settings = setup(db, reverse=True)
    assert refresh(db, row, settings)["changed"] == 0 and totals(db) == (0, 0)


def test_initial_clearance_is_not_a_new_event(db):
    row, _, _, settings = setup(db, xml=feed(record(code="roadCleared")))
    assert refresh(db, row, settings)["changed"] == 0 and totals(db) == (0, 0)


def test_missing_source_and_withdrawal_never_become_cleared(db):
    row, permission, _, settings = setup(db)
    refresh(db, row, settings)
    accept(db, permission, feed(situations=""), minute=1, expected_generation=2)
    refresh(db, row, settings, minute=1)
    assert states(current(db, row, minute=1)) == {"unavailable"}
    accept(db, permission, feed(record(cancelled=True)), minute=2, expected_generation=3)
    refresh(db, row, settings, minute=2)
    assert states(current(db, row, minute=2)) == {"withdrawn"}
    assert refresh(db, row, settings, minute=10)["reason"] == "road_source_stale"
    item = current(db, row, minute=10)
    assert item["availability"] == "stale" and states(item) == {"withdrawn"}


def test_numeric_congestion_threshold_and_five_minute_material_bands(db):
    def xml(delay):
        return feed(record(source_type="AbnormalTraffic", code="queuingTraffic", delay=delay))
    row, permission, _, settings = setup(db, xml=xml(899))
    assert refresh(db, row, settings)["changed"] == 0
    for minute, delay, expected in ((1, 900, 1), (2, 901, 0), (3, 1200, 1), (4, 800, 1)):
        accept(db, permission, xml(delay), minute=minute, expected_generation=minute + 1)
        assert refresh(db, row, settings, minute=minute)["changed"] == expected
    assert totals(db) == (1, 3)


def test_delay_use_requires_separate_permission_even_without_disclosing_number(db):
    row, _, _, settings = setup(db, xml=feed(record(source_type="AbnormalTraffic", code="queuingTraffic", delay=1800)),
                               fields=("event_kind", "validity", "location"))
    result = refresh(db, row, settings)
    assert result["degraded"] and result["changed"] == 0 and totals(db) == (0, 0)


def test_planned_rescheduling_is_material_without_asserting_current_closure(db):
    xml = feed().replace("2026-09-13T09:30:00Z", "2026-09-14T22:00:00Z")
    row, permission, _, settings = setup(db, xml=xml)
    refresh(db, row, settings)
    assert states(current(db, row)) == {"planned"}
    accept(db, permission, xml.replace("2026-09-14T22:00:00Z", "2026-09-15T22:00:00Z"), minute=1, expected_generation=2)
    assert refresh(db, row, settings, minute=1)["changed"] == 1
    assert states(current(db, row, minute=1)) == {"planned"}


@pytest.mark.parametrize("kind", ["source", "topology"])
def test_revocation_immediately_redacts_current_and_history_then_purges_bytes(db, kind):
    row, permission, topo, settings = setup(db)
    refresh(db, row, settings)
    item = current(db, row)
    with db.session() as session:
        if kind == "source":
            revoke_permission(session, permission, now=NOW)
        else:
            revoke_topology(session, topo, now=NOW)
        session.commit()
    assert current(db, row)["payload"] is None
    with db.session() as session:
        assert events.history_page(session, "owner", item["id"], now=NOW)["items"][0]["payload"] is None
    cleanup(db, now=lambda: NOW)
    with db.session() as session:
        assert session.scalar(select(RoadDevelopment)).payload is None
        assert session.scalar(select(RoadEventVersion)).payload is None


def test_review_is_exact_sequence_and_new_changes_remain_unreviewed(db):
    row, permission, _, settings = setup(db)
    refresh(db, row, settings)
    item = current(db, row)
    with db.session() as session:
        reviewed = events.review_event(session, "owner", item["id"], expected_version=item["version"], sequence=1)
        events.review_event(session, "owner", item["id"], expected_version=reviewed["version"], sequence=1, muted=True)
        session.commit()
    accept(db, permission, feed(record(code="laneClosures")), minute=1, expected_generation=2)
    refresh(db, row, settings, minute=1)
    changed = current(db, row, minute=1)
    assert changed["reviewed_sequence"] == 1 and changed["sequence"] == 2 and changed["muted"]
    with db.session() as session:
        with pytest.raises(DomainError):
            events.review_event(session, "owner", item["id"], expected_version=item["version"], sequence=1)
        with pytest.raises(DomainError):
            events.history_page(session, "peer", item["id"], now=NOW)


def test_pause_archive_delete_and_stale_job_cannot_publish_private_changes(db):
    row, _, _, settings = setup(db)
    with db.session() as session:
        paused = repository.command(session, "owner", row["id"], row["version"], "pause", now=NOW)
        session.commit()
    assert refresh(db, row, settings)["state"] == "superseded" and totals(db) == (0, 0)
    with db.session() as session:
        assert all(job.cancel_requested for job in session.scalars(select(Job).where(Job.target_type == "road_monitor")))
        resumed = repository.command(session, "owner", row["id"], paused["version"], "resume", settings=settings, now=NOW)
        session.commit()
    assert refresh(db, resumed, settings)["changed"] == 1
    with db.session() as session:
        repository.remove_monitor(session, "owner", row["id"], resumed["version"])
        session.commit()
    assert refresh(db, resumed, settings)["state"] == "superseded" and totals(db) == (0, 0)


def test_scheduler_deduplicates_existing_jobs_and_lost_membership_stops_processing(db):
    row, _, _, settings = setup(db)
    assert worker.enqueue_due(db, settings, now=NOW) == {"enqueued": 0}
    with db.session() as session:
        session.execute(update(User).where(User.id == "owner").values(active=False))
        session.commit()
    assert refresh(db, row, settings)["state"] == "access_unavailable" and totals(db) == (0, 0)


def test_capacity_failure_rolls_back_entire_snapshot_and_retry_reuses_original_state(db, monkeypatch):
    xml = feed(situations=situation(identifier="one") + situation(identifier="two"))
    row, _, _, settings = setup(db, xml=xml)
    monkeypatch.setattr(events, "MAX_DEVELOPMENTS", 1)
    assert refresh(db, row, settings)["reason"] == "road_event_storage_limit"
    assert totals(db) == (0, 0)
    monkeypatch.setattr(events, "MAX_DEVELOPMENTS", 1000)
    assert refresh(db, row, settings)["changed"] == 2 and totals(db) == (2, 2)


def test_caller_rollback_cannot_commit_an_event_through_nested_savepoint(db):
    row, permission, _, _ = setup(db)
    with db.session() as session:
        with _savepoint(session):
            events.process_snapshot(session, session.get(RoadMonitor, row["id"]), permission, now=NOW)
        session.rollback()
    assert totals(db) == (0, 0)


@pytest.mark.parametrize("change", ["expiry", "disable", "permission"])
def test_final_processing_guard_rolls_back_staged_history(db, monkeypatch, change):
    row, _, _, settings = setup(db)
    current_clock = [NOW]
    monkeypatch.setattr(worker, "clock", lambda: current_clock[0])
    original = worker.process_snapshot

    def delayed(*args, **kwargs):
        result = original(*args, **kwargs)
        if change == "expiry":
            current_clock[0] = NOW + timedelta(days=200)
        elif change == "disable":
            settings.road_source_enabled = False
        else:
            settings.road_source_permission_id = "other-grant"
        return result

    monkeypatch.setattr(worker, "process_snapshot", delayed)
    result = worker.refresh(db, settings, monitor_id=row["id"], version=row["version"])
    assert result["changed"] == 0 and result["reason"]
    assert totals(db) == (0, 0)


@pytest.mark.asyncio
async def test_durable_job_execution_http_history_and_same_workspace_job_privacy(tmp_path, monkeypatch):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_auth import _csrf, _register, _settings

    from helvetic_lens import road_api
    from helvetic_lens.main import create_app
    from helvetic_lens.models import OrganizationMembership

    settings = _settings(tmp_path, road_watch_enabled=True, road_source_enabled=True)
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    monkeypatch.setattr(worker, "clock", lambda: NOW)
    monkeypatch.setattr(road_api, "clock", lambda: NOW)
    with TestClient(app) as client:
        identity = _register(client).json()
        service = app.state.service
        user, org = identity["user"]["id"], identity["organization"]["id"]
        with service.db.organization_context(org):
            row, permission, _, _ = setup(service.db, user_id=user)
        settings.road_source_permission_id = permission
        with service.db.organization_context(org), service.db.session() as session:
            job_id = session.scalar(select(Job.id).where(Job.target_id == row["id"]))
        with TestClient(app) as peer:
            other = _register(peer, email="road-job-peer@example.test").json()
            with service.db.session(include_all_organizations=True) as session:
                session.add(OrganizationMembership(organization_id=org, user_id=other["user"]["id"], role="organization_admin"))
                session.commit()
            assert peer.post("/api/auth/session/organization", headers=_csrf(peer), json={"organization_id": org}).status_code == 200
            assert peer.get(f"/api/jobs/{job_id}").status_code == 404
            assert row["id"] not in str(peer.get("/api/jobs").json())
            for action in ("cancel", "retry"):
                assert peer.post(f"/api/jobs/{job_id}/{action}", headers=_csrf(peer)).status_code == 404
        with service.db.organization_context(org):
            result = await service.execute_job(job_id)
        assert result["state"] == "succeeded", result
        path = f"/api/road-watch/monitors/{row['id']}"
        response = client.get(path + "/events")
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        event = response.json()["items"][0]
        detail_path = f"/api/road-watch/events/{event['id']}"
        linked = client.get(detail_path, params={"monitor_id": row["id"], "sequence": 1})
        assert linked.status_code == 200 and linked.headers["cache-control"] == "no-store"
        assert linked.json()["previous"] is None and linked.json()["snapshot"]["payload"] == event["payload"]
        today = client.get("/api/road-watch/today")
        assert today.status_code == 200 and today.headers["cache-control"] == "no-store"
        assert today.json()["items"][0]["event_id"] == event["id"]
        for invalid in (0, -1, 10001, 10**100):
            invalid_response = client.get(detail_path, params={"sequence": invalid})
            assert invalid_response.status_code == 422 and invalid_response.headers["cache-control"] == "no-store"
        with TestClient(app) as outsider:
            assert outsider.get(detail_path).status_code == 401
            _register(outsider, email="road-event-outsider@example.test")
            assert outsider.get(detail_path).status_code == 404
            assert outsider.get("/api/road-watch/today").json()["items"] == []
        history = f"/api/road-watch/events/{event['id']}/history"
        assert client.get(history).json()["items"][0]["sequence"] == 1
        review = f"/api/road-watch/events/{event['id']}/review"
        body = {"expected_version": event["version"], "sequence": 1}
        assert client.post(review, json=body).status_code == 403
        assert client.post(review, headers=_csrf(client), json=body).status_code == 200
        assert client.get("/api/road-watch/today").json()["items"] == []
        with service.db.organization_context(org), service.db.session() as session:
            revoke_permission(session, permission, now=NOW)
            session.commit()
        assert client.get(history).json()["items"][0]["payload"] is None
        assert client.get(path + "/events").json()["items"][0]["payload"] is None


@pytest.mark.parametrize("denial", ["cancelled", "other_worker", "expired_lease"])
def test_final_durable_lease_guard_cannot_commit_after_losing_job_ownership(db, denial):
    from datetime import UTC, datetime

    from helvetic_lens import jobs

    row, _, _, settings = setup(db)
    with db.session() as session:
        job = session.scalar(select(Job).where(Job.target_id == row["id"]))
        job.state, job.lease_owner, job.heartbeat_at = "running", "test-worker", datetime.now(UTC)
        if denial == "cancelled":
            job.cancel_requested = True
        elif denial == "other_worker":
            job.lease_owner = "replacement-worker"
        else:
            job.heartbeat_at -= timedelta(seconds=settings.job_lease_seconds + 1)
        identifier = job.id
        session.commit()
    with pytest.raises(jobs.JobCancelled):
        worker.refresh(db, settings, monitor_id=row["id"], version=row["version"], now=NOW,
                       job_id=identifier, lease_owner="test-worker")
    assert totals(db) == (0, 0)


def test_possible_clearance_does_not_become_confirmed_clearance(db):
    row, permission, _, settings = setup(db)
    refresh(db, row, settings)
    xml = feed(record(code="roadCleared")).replace("<probabilityOfOccurrence>certain", "<probabilityOfOccurrence>probable")
    accept(db, permission, xml, minute=1, expected_generation=2)
    refresh(db, row, settings, minute=1)
    assert states(current(db, row, minute=1)) == {"possible_clearance"}
