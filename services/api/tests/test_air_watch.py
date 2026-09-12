"""C7 source semantics, real private HTTP/DB lifecycle, Today and recovery."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select, update
from test_auth import _csrf, _register, _settings

from helvetic_lens import air_jobs, air_sources
from helvetic_lens.air_contracts import AirConfiguration
from helvetic_lens.air_models import AirMeasurement, AirMonitor, AirReadingVersion, AirSourceCache
from helvetic_lens.air_runtime import evaluate, series
from helvetic_lens.main import create_app
from helvetic_lens.models import Job, OrganizationMembership

BASE = "/api/air-watch"


def test_complete_withdrawal_never_rewinds_to_an_older_good_hour(api):
    client, service, _, _, now = api
    row = create(client)
    feed(service.db, now, source_rows(now, 60))
    run(service, row, now)
    rows = source_rows(now, 60)
    for field in air_sources.METRICS.values():
        rows[0][field] = None
    feed(service.db, now, rows)
    preview = client.post(
        BASE + "/preview", json={"configuration": configuration()}, headers=_csrf(client)
    ).json()
    assert not preview["start_available"]
    assert all(c["status"] == "unknown" for c in preview["coverage"].values())
    run(service, row, now)
    assert len(changes(client, row)) == 1


@pytest.mark.asyncio
async def test_real_durable_worker_dispatch(api, monkeypatch):
    client, service, _, _, _ = api
    row = command(client, create(client), "start")
    monkeypatch.setattr(air_jobs, "collect", lambda *args, **kwargs: "cached")
    with service.db.session() as session:
        job_id = session.scalar(
            select(Job.id).where(Job.target_type == "air_monitor", Job.target_id == row["id"])
        )
    result = await service.execute_job(job_id)
    assert result["state"] == "succeeded", result
    with service.db.session() as session:
        monitor = session.get(AirMonitor, row["id"])
        assert monitor.last_poll_at is not None
        assert monitor.state["coverage"]["O3:hourly_mean"]["status"] == "current"


def test_additive_air_migration_preserves_river_accounts_and_pollen(api):
    from pathlib import Path

    from alembic.config import Config
    from sqlalchemy import inspect

    from alembic import command as migrate
    from helvetic_lens.models import User

    _, service, _, identity, _ = api
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with service.db.engine.begin() as connection:
        config.attributes["connection"] = connection
        migrate.downgrade(config, "c395ad04e76b")
        tables = inspect(connection).get_table_names()
        assert "air_monitors" not in tables and "air_reading_versions" not in tables
        assert "river_monitors" in tables and "monitoring_subjects" in tables
        migrate.upgrade(config, "head")
        assert "air_reading_versions" in inspect(connection).get_table_names()
    with service.db.session() as session:
        assert session.get(User, identity["user"]["id"]).email == identity["user"]["email"]


def configuration(**changes):
    return {
        "name": "Basel air",
        "station_id": "BAS",
        "metrics": ["O3", "NO2", "PM10", "PM25"],
        "muted_metrics": [],
        "rules": [
            {
                "metric": "O3",
                "period": "hourly_mean",
                "threshold": "50",
                "hysteresis": "5",
                "cooldown_hours": 3,
            }
        ],
        **changes,
    }


def metadata():
    return {
        "dataset_id": "100051",
        "metas": {
            "default": {
                "license": "CC BY 4.0",
                "license_url": air_sources.LICENSE,
                "publisher": "MeteoSchweiz",
                "title": "Luftqualität Station Basel-Binningen",
            }
        },
        "fields": [{"name": "datum_zeit", "type": "datetime"}]
        + [
            {"name": f, "type": "double", "annotations": {"unit": "μg/m3"}}
            for f in air_sources.METRICS.values()
        ],
    }


def source_rows(now, value=40, count=30):
    return [
        {
            "datum_zeit": (now - timedelta(hours=i)).isoformat(),
            "o3_ug_m3": value,
            "no2_ug_m3": 5,
            "pm10_ug_m3": 10,
            "pm2_5_ug_m3": 3,
        }
        for i in range(count)
    ]


def feed(database, now, rows):
    with database.session(include_all_organizations=True) as session:
        session.execute(update(AirSourceCache).values(next_fetch_at=now - timedelta(seconds=1)))
        session.commit()

    def fetch(url):
        if url == air_sources.API:
            return metadata()
        return {"total_count": len(rows), "results": rows if "offset=0&" in url else []}

    assert air_sources.collect(database, "catalog", now=now, fetch=fetch) == "updated"
    assert air_sources.collect(database, "BAS", now=now, fetch=fetch) == "updated"


@pytest.fixture
def api(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    monkeypatch.setattr("helvetic_lens.air_api.collect", lambda *a, **k: "cached")
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=3)
    with TestClient(app) as client:
        identity = _register(client).json()
        service = app.state.service
        feed(service.db, now, source_rows(now))
        with service.db.organization_context(identity["organization"]["id"]):
            yield client, service, settings, identity, now


def create(client, config=None):
    response = client.post(
        BASE + "/monitors",
        json={"request_key": str(uuid4()), "configuration": config or configuration()},
        headers=_csrf(client),
    )
    assert response.status_code == 201, response.text
    return response.json()


def command(client, row, action):
    response = client.post(
        f"{BASE}/monitors/{row['id']}/command",
        json={"expected_version": row["version"], "action": action},
        headers=_csrf(client),
    )
    assert response.status_code == 200, response.text
    return response.json()


def run(service, row, now):
    with service.db.session() as session:
        result = evaluate(session, session.get(AirMonitor, row["id"]), now)
        session.commit()
        return result


def changes(client, row):
    return client.get(f"{BASE}/monitors/{row['id']}/changes").json()["items"]


def test_complete_http_lifecycle_today_review_reopen_mute_and_delete(api):
    client, service, _, _, now = api
    assert client.get(BASE + "/stations").json()["unsupported"][0]["area"] == "Lugano"
    assert client.post(
        BASE + "/preview", json={"configuration": configuration()}, headers=_csrf(client)
    ).json()["start_available"]
    row = command(client, create(client), "start")
    assert run(service, row, now)["sequence"] == 0
    feed(service.db, now + timedelta(hours=1), source_rows(now + timedelta(hours=1), 60))
    run(service, row, now + timedelta(hours=1))
    event = changes(client, row)[0]
    today = client.get(BASE + "/today").json()["items"]
    assert today[0]["id"] == event["id"] and today[0]["monitor_name"] == "Basel air"
    review_url = f"{BASE}/monitors/{row['id']}/changes/{event['id']}/review"
    assert (
        client.post(
            review_url, json={"expected_version": 0, "decision": "reviewed"}, headers=_csrf(client)
        ).status_code
        == 200
    )
    feed(service.db, now + timedelta(hours=2), source_rows(now + timedelta(hours=2), 44))
    run(service, row, now + timedelta(hours=2))
    improved = changes(client, row)[0]
    assert (
        improved["kind"] == "threshold_cleared"
        and improved["development_id"] == event["development_id"]
        and improved["decision"] is None
    )
    assert (
        client.post(
            review_url, json={"expected_version": 1, "decision": "reviewed"}, headers=_csrf(client)
        ).status_code
        == 409
    )
    row = client.post(
        f"{BASE}/monitors/{row['id']}/mute",
        json={"expected_version": row["version"], "metric": "O3", "muted": True},
        headers=_csrf(client),
    ).json()
    assert row["configuration"]["muted_metrics"] == ["O3"]
    assert client.get(BASE + "/today").json()["items"][0]["muted"]
    row = command(client, row, "pause")
    edit = client.patch(
        f"{BASE}/monitors/{row['id']}",
        json={"expected_version": row["version"], "configuration": configuration(name="Edited")},
        headers=_csrf(client),
    )
    assert edit.status_code == 200
    row = command(client, edit.json(), "resume")
    assert client.get(f"{BASE}/monitors/{row['id']}/measurements?limit=2").json()["next"]
    assert len(client.get(f"{BASE}/monitors/{row['id']}/revisions").json()["items"]) == 3
    row = command(client, row, "archive")
    assert client.get(BASE + "/today").json()["items"] == []
    assert (
        client.request(
            "DELETE",
            f"{BASE}/monitors/{row['id']}",
            json={"expected_version": row["version"]},
            headers=_csrf(client),
        ).status_code
        == 204
    )


def test_hysteresis_cooldown_duplicate_recovery_and_improvement(api):
    client, service, _, _, now = api
    row = create(client)
    run(service, row, now)
    for hour, value in enumerate([60, 48, 44, 60, 61], start=1):
        feed(
            service.db, now + timedelta(hours=hour), source_rows(now + timedelta(hours=hour), value, count=1)
        )
        run(service, row, now + timedelta(hours=hour))
        run(service, row, now + timedelta(hours=hour))
    events = changes(client, row)
    assert [e["kind"] for e in reversed(events)] == [
        "threshold_crossed",
        "threshold_cleared",
        "threshold_crossed",
    ]
    assert len({e["development_id"] for e in events}) == 1


def test_missing_value_and_source_failure_never_clear_a_threshold(api):
    client, service, _, _, now = api
    row = create(client)
    feed(service.db, now, source_rows(now, 60))
    run(service, row, now)
    rows = source_rows(now, None)
    feed(service.db, now, rows)
    assert run(service, row, now)["status"] == "partial_unknown"
    assert len(changes(client, row)) == 1
    coverage = client.post(
        BASE + "/preview", json={"configuration": configuration()}, headers=_csrf(client)
    ).json()["coverage"]
    assert coverage["O3:hourly_mean"]["status"] == "unknown"
    assert coverage["O3:hourly_mean"]["sample"]["value"] is None
    with service.db.session() as session:
        session.get(AirSourceCache, "BAS").error = "source_unavailable"
        session.commit()
    assert run(service, row, now)["status"] == "partial_unknown"
    assert len(changes(client, row)) == 1


def test_source_correction_is_versioned_and_reopens_current_development(api):
    client, service, _, _, now = api
    row = create(client)
    feed(service.db, now, source_rows(now, 60))
    run(service, row, now)
    feed(service.db, now, source_rows(now, 40))
    run(service, row, now)
    events = changes(client, row)
    assert events[0]["kind"] == "threshold_cleared" and events[0]["evidence"]["corrected"]
    assert events[0]["development_id"] == events[1]["development_id"]
    assert events[1]["evidence"]["sample"]["value"] == "60"  # Prior explanation is immutable.
    with service.db.session() as session:
        readings = list(
            session.scalars(
                select(AirReadingVersion).where(
                    AirReadingVersion.metric == "O3", AirReadingVersion.measured_at == now
                )
            )
        )
        assert [r.evidence["revision"] for r in readings] == [1, 2, 3]


def test_rolling_mean_uses_24_complete_compatible_hours_and_tracks_corrections(api):
    _, service, _, _, now = api
    with service.db.session() as session:
        rows = [
            r.evidence for r in session.scalars(select(AirMeasurement).order_by(AirMeasurement.measured_at))
        ]
    result = series(rows, "PM10", "rolling_24h_mean")[-1]
    assert result["value"] == "10.0000" and result["derived"] and len(result["input_versions"]) == 24
    incomplete = [
        s
        for s in rows
        if not (s["metric"] == "PM10" and s["timestamp"] == (now - timedelta(hours=12)).isoformat())
    ]
    assert series(incomplete, "PM10", "rolling_24h_mean")[-1]["value"] is None
    changed = deepcopy(rows)
    next(s for s in changed if s["metric"] == "PM10" and s["timestamp"] == now.isoformat())["unit"] = "mg/m3"
    assert series(changed, "PM10", "rolling_24h_mean")[-1]["value"] is None


@pytest.mark.parametrize("problem", ["future", "duplicate", "naive", "nan", "boolean", "missing_field"])
def test_source_rejects_ambiguous_or_invalid_envelopes(problem):
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    rows = source_rows(now, count=1)
    if problem == "future":
        rows[0]["datum_zeit"] = (now + timedelta(hours=1)).isoformat()
    if problem == "duplicate":
        rows += deepcopy(rows)
    if problem == "naive":
        rows[0]["datum_zeit"] = now.replace(tzinfo=None).isoformat()
    if problem == "nan":
        rows[0]["o3_ug_m3"] = "NaN"
    if problem == "boolean":
        rows[0]["o3_ug_m3"] = True
    if problem == "missing_field":
        del rows[0]["pm2_5_ug_m3"]
    with pytest.raises((ValueError, KeyError)):
        air_sources.parse([{"total_count": len(rows), "results": rows}], now)


@pytest.mark.parametrize("invalid_value", [-1, 1e200])
def test_future_nulls_and_negative_withdrawals_are_not_zero(invalid_value):
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    rows = source_rows(now, count=1)
    future = {f: None for f in air_sources.METRICS.values()}
    future["datum_zeit"] = (now + timedelta(hours=1)).isoformat()
    rows[0]["o3_ug_m3"] = invalid_value
    samples = air_sources.parse([{"total_count": 2, "results": rows + [future]}], now)
    assert len(samples) == 4
    ozone = next(s for s in samples if s["metric"] == "O3")
    assert ozone["value"] is None and ozone["quality"] == "invalid"


@pytest.mark.parametrize(
    "change",
    [
        {"station_id": "LUG"},
        {"metrics": ["O3", "O3"]},
        {"muted_metrics": ["NO2"], "metrics": ["O3"]},
        {"rules": [{"metric": "O3", "threshold": "NaN"}]},
        {"rules": [{"metric": "O3", "threshold": "5", "hysteresis": "5"}]},
        {"rules": [{"metric": "O3", "threshold": "5", "period": "daily_max"}]},
    ],
)
def test_configuration_rejects_unsupported_station_and_mixed_periods(change):
    with pytest.raises(ValidationError):
        AirConfiguration.model_validate(configuration(**change))


def test_private_owner_today_history_jobs_csrf_viewer_and_feature_gate(api):
    client, service, settings, identity, now = api
    row = command(client, create(client), "start")
    feed(service.db, now, source_rows(now, 60))
    run(service, row, now)
    assert (
        client.post(
            BASE + "/monitors", json={"request_key": str(uuid4()), "configuration": configuration()}
        ).status_code
        == 403
    )
    with TestClient(client.app) as other:
        outsider = _register(other, email="air-other@example.com").json()
        assert other.get(BASE + "/today").json()["items"] == []
        assert other.get(BASE + "/monitors").json()["items"] == []
        assert other.get(f"{BASE}/monitors/{row['id']}/measurements").status_code == 404
        assert all(j["target_id"] != row["id"] for j in other.get("/api/jobs").json())
        with service.db.session(include_all_organizations=True) as session:
            session.add(
                OrganizationMembership(
                    organization_id=identity["organization"]["id"],
                    user_id=outsider["user"]["id"],
                    role="organization_admin",
                )
            )
            session.commit()
        switched = other.post(
            "/api/auth/session/organization",
            json={"organization_id": identity["organization"]["id"]},
            headers=_csrf(other),
        )
        assert switched.status_code == 200
        assert other.get(BASE + "/today").json()["items"] == []
        for suffix in ("", "/changes", "/measurements", "/revisions"):
            assert other.get(f"{BASE}/monitors/{row['id']}{suffix}").status_code == 404
        with service.db.session() as session:
            job_id = session.scalar(select(Job.id).where(Job.target_id == row["id"]))
        assert other.get(f"/api/jobs/{job_id}").status_code == 404
        assert row["id"] not in str(other.get("/api/jobs").json())
    with service.db.session(include_all_organizations=True) as session:
        member = session.scalar(
            select(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"])
        )
        member.role = "viewer"
        session.commit()
    assert client.get(BASE + "/today").status_code == 200
    assert (
        client.post(
            BASE + "/preview", json={"configuration": configuration()}, headers=_csrf(client)
        ).status_code
        == 403
    )
    settings.air_watch_enabled = False
    assert client.get(BASE + "/today").status_code == 404


def test_job_rechecks_pause_after_network_and_schedules_durably(api, monkeypatch):
    client, service, settings, _, now = api
    row = command(client, create(client), "start")
    with service.db.session() as session:
        assert (
            session.scalar(select(func.count()).select_from(Job).where(Job.target_type == "air_monitor")) == 1
        )

    def pause(*args, **kwargs):
        with service.db.session() as session:
            monitor = session.get(AirMonitor, row["id"])
            monitor.status = "paused"
            monitor.version += 1
            session.commit()

    monkeypatch.setattr(air_jobs, "collect", pause)
    assert (
        air_jobs.refresh(service.db, settings, monitor_id=row["id"], version=row["version"], now=now)[
            "status"
        ]
        == "inactive"
    )
    assert changes(client, row) == []


def test_leases_backoff_metadata_gate_and_retention(api):
    _, service, _, _, now = api
    assert (
        air_sources.collect(service.db, "BAS", now=now, fetch=lambda _: pytest.fail("duplicate source poll"))
        == "cached_or_busy"
    )
    with service.db.session(include_all_organizations=True) as session:
        session.get(AirSourceCache, "BAS").next_fetch_at = now
        session.commit()
    assert air_sources.collect(service.db, "BAS", now=now, fetch=lambda _: {}) == "source_unavailable"
    with service.db.session(include_all_organizations=True) as session:
        cache = session.get(AirSourceCache, "BAS")
        assert cache.error == "source_unavailable" and cache.failures == 1
    broken = metadata()
    broken["metas"]["default"]["license"] = "restricted"
    with pytest.raises(ValueError):
        air_sources.validate_metadata(broken)
    assert air_sources.cleanup(service.db, now=now + timedelta(days=35))["removed_measurements"] == 240
