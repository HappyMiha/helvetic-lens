"""C6 complete behavior: real HTTP/DB boundaries and deterministic source fixtures."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select, update
from test_auth import _csrf, _register, _settings

from helvetic_lens import river_jobs, river_sources
from helvetic_lens.main import create_app
from helvetic_lens.models import Job, OrganizationMembership
from helvetic_lens.river_contracts import RiverConfiguration
from helvetic_lens.river_models import (
    RiverChange,
    RiverMeasurement,
    RiverMonitor,
    RiverRevision,
    RiverSourceCache,
)
from helvetic_lens.river_runtime import evaluate

BASE = "/api/river-watch"


def config(**overrides):
    return {"name": "My Rhine", "station_id": "2289", "metrics": ["W", "Q", "WT"], "official_danger": True,
            "rules": [{"metric": "W", "kind": "absolute", "threshold": "2.5", "unit": "m"}], **overrides}


def sample(now, metric="W", value="2.4", station="2289"):
    return {"station_id": station, "metric": metric, "timestamp": now.isoformat(), "value": value,
            "unit": "m" if metric == "W" else "official_level", "source_unit": "m ü.M." if metric == "W" else "official_level",
            "datum": "FOEN:2289:m ü.M." if metric == "W" else None,
            "aggregation": "10min_mean" if metric == "W" else "official_station_state", "quality": "provisional",
            "source_url": river_sources.SOURCE_URL, "source": "Synthetic FOEN fixture", "response_sha256": "a" * 64,
            "fetched_at": now.isoformat()}


def store(session, evidence):
    identity = river_sources.digest([evidence["station_id"], evidence["metric"], evidence["timestamp"]])
    previous = session.get(RiverMeasurement, identity)
    if previous:
        previous.evidence = evidence
    else:
        session.add(RiverMeasurement(id=identity, station_id=evidence["station_id"], metric=evidence["metric"],
            measured_at=datetime.fromisoformat(evidence["timestamp"]), evidence=evidence))
    session.flush()


@pytest.fixture
def api(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    monkeypatch.setattr("helvetic_lens.river_api.collect", lambda *args, **kwargs: "cached")
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    now = now.replace(minute=now.minute // 10 * 10)
    with TestClient(app) as client:
        identity = _register(client).json()
        service = app.state.service
        with service.db.session(include_all_organizations=True) as session:
            for key in ("catalog", "2289", "danger"):
                session.add(RiverSourceCache(key=key, data={"stations": [{"id": "2289", "name": "Basel", "waterbody": "Rhine", "source_url": river_sources.SOURCE_URL}]} if key == "catalog" else {},
                    fetched_at=now, next_fetch_at=now + timedelta(minutes=10), failures=0))
            store(session, sample(now))
            store(session, sample(now, "danger", "1"))
            session.commit()
        with service.db.organization_context(identity["organization"]["id"]):
            yield client, service, settings, identity, now


def create(client, configuration=None, key=None):
    response = client.post(BASE + "/monitors", json={"request_key": key or str(uuid4()), "configuration": configuration or config()}, headers=_csrf(client))
    assert response.status_code == 201, response.text
    return response.json()


def command(client, row, action):
    response = client.post(f'{BASE}/monitors/{row["id"]}/command', json={"expected_version": row["version"], "action": action}, headers=_csrf(client))
    assert response.status_code == 200, response.text
    return response.json()


def run(service, monitor_id, now):
    with service.db.session() as session:
        result = evaluate(session, session.get(RiverMonitor, monitor_id), now)
        session.commit()
        return result


def events(service, monitor_id):
    with service.db.session() as session:
        return list(session.scalars(select(RiverChange).where(RiverChange.monitor_id == monitor_id).order_by(RiverChange.sequence)))


def test_http_preview_save_start_pause_edit_resume_archive_and_delete(api):
    client, service, _, _, _ = api
    preview = client.post(BASE + "/preview", json={"configuration": config()}, headers=_csrf(client)).json()
    assert preview["station"]["name"] == "Basel" and preview["coverage"]["WT"]["status"] == "unknown"
    assert preview["start_available"] and preview["delivery"] == "private_web"
    key = str(uuid4())
    row = create(client, key=key)
    assert create(client, key=key)["id"] == row["id"]
    assert row["status"] == "draft" and not row["email_enabled"]
    active = command(client, row, "start")
    assert active["status"] == "active"
    stale = client.post(f'{BASE}/monitors/{row["id"]}/command', json={"expected_version": row["version"], "action": "pause"}, headers=_csrf(client))
    assert stale.status_code == 409
    response = client.patch(f'{BASE}/monitors/{row["id"]}', json={"expected_version": active["version"], "configuration": config(name="Edited")}, headers=_csrf(client))
    assert response.status_code == 409
    paused = command(client, active, "pause")
    response = client.patch(f'{BASE}/monitors/{row["id"]}', json={"expected_version": paused["version"], "configuration": config(name="Edited")}, headers=_csrf(client))
    assert response.status_code == 200, response.text
    edited = response.json()
    assert edited["revision"] == 2
    assert len(client.get(f'{BASE}/monitors/{row["id"]}/revisions').json()["items"]) == 2
    archived = command(client, command(client, edited, "resume"), "archive")
    deleted = client.request("DELETE", f'{BASE}/monitors/{row["id"]}', json={"expected_version": archived["version"]}, headers=_csrf(client))
    assert deleted.status_code == 204
    assert client.get(f'{BASE}/monitors/{row["id"]}').status_code == 404
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(RiverRevision)) == 0


def test_crossing_danger_priority_duplicate_and_downgrade_same_development(api):
    client, service, _, _, now = api
    row = command(client, create(client), "start")
    run(service, row["id"], now)
    assert events(service, row["id"]) == []
    later = now + timedelta(minutes=10)
    with service.db.session() as session:
        store(session, sample(later, value="2.6"))
        store(session, sample(later, "danger", "3"))
        session.commit()
    run(service, row["id"], later)
    first = events(service, row["id"])
    assert [(e.kind, e.priority) for e in first] == [("threshold_crossed", 2), ("danger_escalation", 1)]
    run(service, row["id"], later)
    assert len(events(service, row["id"])) == 2
    later += timedelta(minutes=10)
    with service.db.session() as session:
        store(session, sample(later, value="2.4"))
        store(session, sample(later, "danger", "2"))
        session.commit()
    run(service, row["id"], later)
    after = events(service, row["id"])
    assert after[0].development_id == after[2].development_id and after[1].development_id == after[3].development_id
    assert after[2].kind == "threshold_cleared" and after[3].kind == "danger_downgrade"
    assert after[3].decision is None
    stale = client.post(f'{BASE}/monitors/{row["id"]}/changes/{after[1].id}/review', json={"expected_version": 0, "decision": "reviewed"}, headers=_csrf(client))
    assert stale.status_code == 409
    response = client.post(f'{BASE}/monitors/{row["id"]}/changes/{after[3].id}/review', json={"expected_version": 0, "decision": "action_required"}, headers=_csrf(client))
    assert response.status_code == 200 and response.json()["review_version"] == 1


def test_change_window_cm_conversion_and_missing_point_is_unknown(api):
    client, service, _, _, now = api
    configuration = config(rules=[{"metric": "W", "kind": "rise", "threshold": "30", "unit": "cm", "window_minutes": 60}], official_danger=False)
    row = create(client, configuration)
    with service.db.session() as session:
        for minutes in range(0, 61, 10):
            if minutes != 30:
                store(session, sample(now - timedelta(minutes=60 - minutes), value=str(2 + minutes / 100)))
        session.commit()
    run(service, row["id"], now)
    assert not events(service, row["id"])
    with service.db.session() as session:
        assert session.get(RiverMonitor, row["id"]).health == "partial_unknown"
    with service.db.session() as session:
        store(session, sample(now - timedelta(minutes=30), value="2.3"))
        # A new configuration run can establish its baseline from a complete window.
        session.get(RiverMonitor, row["id"]).state = {}
        session.commit()
    run(service, row["id"], now)
    event = events(service, row["id"])[0]
    assert event.evidence["evaluated_value"] == "60.0" and event.evidence["baseline"]["value"] == "2.0"


def test_missing_stale_and_outage_do_not_clear_threshold_or_invent_safe_danger(api):
    client, service, _, _, now = api
    row = create(client, config(rules=[{"metric": "W", "threshold": "2", "unit": "m"}]))
    run(service, row["id"], now)
    assert len(events(service, row["id"])) == 1
    run(service, row["id"], now + timedelta(hours=2))
    assert len(events(service, row["id"])) == 1
    with service.db.session() as session:
        monitor = session.get(RiverMonitor, row["id"])
        assert monitor.health == "partial_unknown"
        assert all(s["status"] == "unknown" for s in monitor.state["conditions"].values())


@pytest.mark.parametrize("rule", [
    {"metric": "W", "unit": "m3/s", "threshold": "2"},
    {"metric": "W", "unit": "cm", "threshold": "30"},
    {"metric": "W", "unit": "cm", "kind": "rise", "threshold": "30", "window_minutes": 15},
    {"metric": "W", "unit": "m", "threshold": "NaN"},
    {"metric": "W", "unit": "m", "threshold": "2", "window_minutes": 60},
])
def test_configuration_rejects_ambiguous_units_windows_and_nonfinite(rule):
    with pytest.raises(ValidationError):
        RiverConfiguration.model_validate(config(rules=[rule]))


def test_recovery_replays_crossing_and_reversal_without_duplicate(api):
    client, service, _, _, now = api
    row = create(client, config(official_danger=False))
    run(service, row["id"], now)
    with service.db.session() as session:
        for minutes, value in [(10, "2.7"), (20, "2.4"), (30, "2.4")]:
            store(session, sample(now + timedelta(minutes=minutes), value=value))
        session.commit()
    run(service, row["id"], now + timedelta(minutes=30))
    assert [e.kind for e in events(service, row["id"])] == ["threshold_crossed", "threshold_cleared"]
    run(service, row["id"], now + timedelta(minutes=30))
    assert len(events(service, row["id"])) == 2


def test_private_http_jobs_history_csrf_and_role_boundaries(api):
    client, service, _, identity, _ = api
    row = command(client, create(client), "start")
    job = client.get("/api/jobs").json()
    assert row["id"] in str(job)
    with service.db.session() as session:
        job_id = session.scalar(select(Job.id).where(Job.target_id == row["id"]))
    assert client.post(BASE + "/monitors", json={"request_key": str(uuid4()), "configuration": config()}).status_code == 403
    with TestClient(client.app) as other:
        outsider = _register(other, email="other@example.ch").json()
        # Even a second administrator in the same workspace cannot read private monitors/jobs.
        with service.db.session(include_all_organizations=True) as session:
            session.add(OrganizationMembership(organization_id=identity["organization"]["id"], user_id=outsider["user"]["id"], role="organization_admin"))
            session.commit()
        switch = other.post("/api/auth/session/organization", json={"organization_id": identity["organization"]["id"]}, headers=_csrf(other))
        assert switch.status_code == 200, switch.text
        for suffix in ("", "/changes", "/measurements", "/revisions"):
            assert other.get(f'{BASE}/monitors/{row["id"]}{suffix}').status_code == 404
        assert other.get(f"/api/jobs/{job_id}").status_code == 404
        assert row["id"] not in str(other.get("/api/jobs").json())
    with service.db.session() as session:
        session.execute(update(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"]).values(role="viewer"))
        session.commit()
    assert client.get(f'{BASE}/monitors/{row["id"]}').status_code == 200
    denied = client.post(BASE + "/preview", json={"configuration": config()}, headers=_csrf(client))
    assert denied.status_code == 403


def test_background_pause_race_and_kill_switch(api, monkeypatch):
    client, service, settings, _, now = api
    row = command(client, create(client), "start")
    def pause_during_fetch(*args, **kwargs):
        with service.db.session() as session:
            record = session.get(RiverMonitor, row["id"])
            record.status, record.version = "paused", record.version + 1
            session.commit()
    monkeypatch.setattr(river_jobs, "collect", pause_during_fetch)
    result = river_jobs.refresh(service.db, settings, monitor_id=row["id"], version=row["version"], now=now)
    assert result["status"] == "inactive" and not events(service, row["id"])
    settings.river_watch_enabled = False
    assert river_jobs.enqueue_due(service.db, settings)["enqueued"] == 0
    assert client.get(BASE + "/monitors").status_code == 404


def test_collector_bounds_quality_leases_backoff_and_retention(api):
    _, service, _, _, now = api
    raw = {"data": {"water": {"observations": {"data_10min_mean": [{"timestamp": now.isoformat(), "parameterName": "W", "value": 244.9, "unitSymbol": "m ü.M.", "releaseState": None}]}}}}
    raw["data"]["water"]["observations"]["data_live"] = [{"stationNo": "2289", "timestamp": now.isoformat(), "parameterName": "W", "value": 244.9, "releaseStatus": 0}]
    calls = []
    def fetch(url, payload):
        calls.append((url, payload))
        return raw
    at = now + timedelta(minutes=10)
    assert river_sources.collect(service.db, "2289", now=at, fetch=fetch) == "updated"
    assert river_sources.collect(service.db, "2289", now=at, fetch=fetch) == "cached_or_busy"
    assert len(calls) == 1
    with service.db.session() as session:
        row = session.scalar(select(RiverMeasurement).where(RiverMeasurement.metric == "W"))
        assert row.evidence["quality"] == "provisional" and row.evidence["datum"] == "FOEN:2289:m ü.M."
    def unavailable(*args):
        raise httpx.ConnectError("synthetic outage")
    assert river_sources.collect(service.db, "2289", now=at + timedelta(minutes=10), fetch=unavailable) == "source_unavailable"
    assert river_sources.collect(service.db, "2289", now=at + timedelta(minutes=11), fetch=fetch) == "cached_or_busy"
    with pytest.raises(ValueError):
        river_sources.collect(service.db, '2289"} evil', now=at, fetch=fetch)


def test_independent_histories_and_stable_measurement_pagination(api):
    client, service, _, _, now = api
    row = create(client)
    with service.db.session() as session:
        store(session, sample(now - timedelta(minutes=10)))
        session.commit()
    one = client.get(f'{BASE}/monitors/{row["id"]}/measurements?limit=1').json()
    two = client.get(f'{BASE}/monitors/{row["id"]}/measurements', params={"limit": 1, **one["next"]}).json()
    assert one["items"][0] != two["items"][0]
    assert client.get(f'{BASE}/monitors/{row["id"]}/changes').json()["items"] == []


@pytest.mark.parametrize("problem", ["unit", "station", "quality", "timezone", "duplicate", "nonfinite"])
def test_live_source_never_guesses_incompatible_metadata(problem):
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    aggregate = {"timestamp": now.isoformat(), "parameterName": "W", "value": 244.9, "unitSymbol": "m ü.M.", "releaseState": None}
    live = {"stationNo": "2289", "timestamp": now.isoformat(), "parameterName": "W", "value": 244.9, "releaseStatus": 0}
    if problem == "unit":
        aggregate["unitSymbol"] = "feet"
    if problem == "station":
        live["stationNo"] = "2009"
    if problem == "quality":
        live["releaseStatus"] = True
    if problem == "timezone":
        live["timestamp"] = now.replace(tzinfo=None).isoformat()
    if problem == "nonfinite":
        live["value"] = "NaN"
    raw = {"data": {"water": {"observations": {"data_10min_mean": [aggregate], "data_live": [live, live] if problem == "duplicate" else [live]}}}}
    if problem == "unit":
        assert river_sources._live_samples(raw, "2289", now)[1] == []
    else:
        with pytest.raises(ValueError):
            river_sources._live_samples(raw, "2289", now)


def test_danger_requires_official_field_and_never_uses_water_level():
    now = datetime.now(UTC)
    raw = {"results": {"bindings": [{"station": {"value": "https://environment.ld.admin.ch/foen/hydro/station/2289"},
        "time": {"value": now.isoformat()}, "waterLevel": {"value": "999"}}]}}
    assert river_sources._danger_samples(raw, now)[1] == []


def test_retention_runs_without_active_monitors_and_reader_freshness_expires(api):
    client, service, _, _, now = api
    row = create(client)
    run(service, row["id"], now)
    with service.db.session() as session:
        store(session, sample(now - timedelta(days=31)))
        monitor = session.get(RiverMonitor, row["id"])
        monitor.state = {"coverage": {"W": {"status": "current", "sample": sample(now - timedelta(hours=2))}}}
        monitor.health = "ready"
        session.commit()
    assert client.get(f'{BASE}/monitors/{row["id"]}').json()["health"] == "partial_unknown"
    assert river_sources.cleanup(service.db, now=now)["removed_measurements"] == 1


@pytest.mark.asyncio
async def test_durable_worker_dispatches_the_river_refresh(api, monkeypatch):
    client, service, _, _, now = api
    row = command(client, create(client), "start")
    monkeypatch.setattr(river_jobs, "collect", lambda *args, **kwargs: "cached")
    with service.db.session() as session:
        job_id = session.scalar(select(Job.id).where(Job.target_id == row["id"]))
    result = await service.execute_job(job_id)
    assert result["state"] == "succeeded", result
    with service.db.session() as session:
        monitor = session.get(RiverMonitor, row["id"])
        assert monitor.last_poll_at is not None and monitor.state["coverage"]["W"]["status"] == "current"


def test_additive_migration_roundtrip_preserves_existing_accounts(api):
    from pathlib import Path

    from alembic.config import Config
    from sqlalchemy import inspect

    from alembic import command as migrate
    from helvetic_lens.models import User

    _, service, _, identity, _ = api
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with service.db.engine.begin() as connection:
        config.attributes["connection"] = connection
        migrate.downgrade(config, "b2849cd3f65a")
        assert "river_monitors" not in inspect(connection).get_table_names()
        assert "monitoring_subjects" in inspect(connection).get_table_names()
        migrate.upgrade(config, "head")
        assert "river_monitors" in inspect(connection).get_table_names()
    with service.db.session() as session:
        assert session.get(User, identity["user"]["id"]).email == identity["user"]["email"]
