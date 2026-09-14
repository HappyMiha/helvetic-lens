"""Actual metadata sampling, retention and readable unknown/gap boundaries."""
import json
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from test_monitoring_source_attention import admins
from test_monitoring_source_operations import NOW, settings
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens import monitoring_source_history as history
from helvetic_lens.air_models import AirSourceCache
from helvetic_lens.config import DomainError
from helvetic_lens.models import MonitoringOperationalSample as Sample


def read(db, channel="air", days=1, now=NOW, user="owner"):
    with db.session() as session:
        result = history.history(session, user, channel, days, now=now)
        assert not session.new and not session.dirty and not session.deleted
        return result


def seed(db, at=NOW, error=None):
    with db.session() as session:
        session.add(AirSourceCache(key="BAS", data={"private": "do-not-retain"},
            fetched_at=at, error=error, failures=int(bool(error)), next_fetch_at=NOW + timedelta(hours=1)))
        session.commit()


def test_actual_snapshot_all_nine_two_channels_idempotence_no_secret_or_private_data(db):
    admins(db)
    seed(db, NOW - timedelta(minutes=15), "secret-provider-response")
    assert history.capture(db, settings(), now=NOW)["sampled"] == 10
    with db.session() as session:
        before = {r.channel: r.values for r in session.scalars(select(Sample))}
        assert set(before) == set(history.CHANNELS)
        assert "secret-provider" not in json.dumps(before) and "do-not-retain" not in json.dumps(before)
        session.get(AirSourceCache, "BAS").error = None
        session.commit()
    assert history.capture(db, settings(), now=NOW + timedelta(seconds=120))["sampled"] == 0
    with db.session() as session:
        assert {r.channel: r.values for r in session.scalars(select(Sample))} == before
    point = read(db)["points"][-1]
    assert point["states"] == {"errors": 1}
    assert point["metrics"]["latest_acquisition_age"] == {"min_seconds": 900, "max_seconds": 900, "known_samples": 1}
    assert point["metrics"]["publication_age"]["max_seconds"] is None


def test_recorded_recovery_missing_samples_and_future_clocks_are_distinct(db):
    admins(db)
    seed(db, NOW - timedelta(hours=1), "error")
    history.capture(db, settings(), now=NOW)
    with db.session() as session:
        row = session.get(AirSourceCache, "BAS")
        row.error, row.failures, row.fetched_at = None, 0, NOW + timedelta(minutes=10)
        session.commit()
    history.capture(db, settings(), now=NOW + timedelta(minutes=10))
    point = read(db, now=NOW + timedelta(minutes=10))["points"][-1]
    assert point["samples"] == 2 and point["expected_samples"] == 3 and point["missing_samples"] == 1
    assert point["states"] == {"errors": 1, "recorded": 1}
    assert point["metrics"]["latest_acquisition_age"]["min_seconds"] == 0
    assert point["metrics"]["latest_acquisition_age"]["max_seconds"] == 3600
    with db.session() as session:
        session.get(AirSourceCache, "BAS").fetched_at = NOW + timedelta(hours=10)
        session.commit()
    history.capture(db, settings(), now=NOW + timedelta(hours=1))
    later = read(db, now=NOW + timedelta(hours=1))["points"][-1]
    assert later["states"] == {"invalid_clock": 1}
    assert later["metrics"]["latest_acquisition_age"]["max_seconds"] is None


@pytest.mark.parametrize("days", [1, 7, 30])
def test_empty_history_is_complete_gap_inventory_not_reconstructed_or_zero(db, days):
    admins(db)
    result = read(db, days=days, now=NOW + timedelta(minutes=59))
    assert len(result["points"]) == days * 24
    assert result["first_sample_at"] is None and result["last_sample_at"] is None
    assert all(p["missing_samples"] == 12 and p["samples"] == 0 and not p["states"] for p in result["points"])
    assert all(p["metrics"]["oldest_acquisition_age"]["max_seconds"] is None for p in result["points"])


def test_binding_change_and_permission_loss_preserved_without_implied_coverage(db):
    admins(db)
    history.capture(db, settings(road_source_permission_id="old"), now=NOW)
    history.capture(db, settings(road_source_permission_id="new"), now=NOW + timedelta(minutes=5))
    point = read(db, "traffic", now=NOW + timedelta(minutes=5))["points"][-1]
    assert point["binding_changed"] and point["last_state"]["access"] == "missing"
    assert point["metrics"]["publication_age"]["known_samples"] == 0
    assert '"old"' not in json.dumps(point) and '"new"' not in json.dumps(point)


def test_retention_only_removes_old_samples_never_source_or_receipts(db):
    from helvetic_lens.models import MonitoringSourceAcknowledgement as Receipt
    admins(db)
    seed(db)
    with db.session() as session:
        session.add(Receipt(user_id="owner", issue_key="air:air:acquisition_errors", fingerprint="a" * 64, acknowledged_at=NOW))
        session.commit()
    history.capture(db, settings(), now=NOW - timedelta(days=31))
    history.capture(db, settings(), now=NOW - timedelta(days=30))
    result = history.capture(db, settings(), now=NOW)
    assert result == {"sampled": 10, "removed": 10}
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(Sample)) == 20
        assert session.get(AirSourceCache, "BAS").data == {"private": "do-not-retain"}
        assert session.scalar(select(func.count()).select_from(Receipt)) == 1


def test_future_recorded_samples_are_hidden_and_naive_sampling_clock_rejected(db):
    admins(db)
    history.capture(db, settings(), now=NOW + timedelta(seconds=1))
    assert read(db)["last_sample_at"] is None
    with pytest.raises(ValueError):
        history.capture(db, settings(), now=NOW.replace(tzinfo=None))


def test_real_worker_samples_with_latest_settings_and_no_source_collection(db, monkeypatch):
    from helvetic_lens import celery_app
    admins(db)
    base = db.settings if hasattr(db, "settings") else settings(database_url=str(db.engine.url))
    monkeypatch.setattr(celery_app, "settings", base)
    monkeypatch.setattr(celery_app, "Database", lambda value: db)
    monkeypatch.setattr(db.engine, "dispose", lambda: None)
    called = []
    def current(database, environment):
        called.append(database)
        return settings(air_watch_enabled=False)
    monkeypatch.setattr(celery_app, "load_connector_settings", current)
    result = celery_app.sample_monitoring_source_history.run()
    assert result["sampled"] == 10 and called == [db]
    with db.session() as session:
        row = session.scalar(select(Sample).where(Sample.channel == "air"))
        assert row.values["section_enabled"] is False
    schedule = celery_app.celery_app.conf.beat_schedule["sample-monitoring-source-history"]
    assert schedule["schedule"] == 300 and schedule["options"]["expires"] == 300


def test_current_admin_and_supported_selection_required(db):
    with pytest.raises(DomainError):
        read(db)
    admins(db)
    for channel, days in (("customs", 1), ("air", 365), ("commute", 1)):
        with pytest.raises(DomainError) as error:
            read(db, channel, days)
        assert error.value.code == "source_history_selection"


def test_real_http_history_is_private_no_store_read_only(tmp_path):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_auth import _register, _settings

    from helvetic_lens.main import create_app
    from helvetic_lens.models import User
    app = create_app(_settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    path = "/api/admin/monitoring-sources/history"
    with TestClient(app) as client:
        assert client.get(path).status_code == 401
        actor = _register(client).json()
        denied = client.get(path)
        assert denied.status_code == 403 and denied.headers["cache-control"] == "no-store"
        with app.state.service.db.session() as session:
            session.get(User, actor["user"]["id"]).platform_admin = True
            session.commit()
        for channel in history.CHANNELS:
            response = client.get(path, params={"channel": channel, "days": 1})
            assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
            assert response.json()["channel"] == channel
        assert client.get(path, params={"days": 2}).status_code == 422
        assert client.get(path, params={"channel": "customs"}).status_code == 422
        with app.state.service.db.session() as session:
            assert session.scalar(select(func.count()).select_from(Sample)) == 0


def test_recovered_permission_and_disabled_collector_remain_in_hour_counts(db):
    from helvetic_lens.road_models import RoadSourcePermission
    admins(db)
    config = settings(road_source_permission_id="permit", road_source_enabled=True, road_source_key="synthetic")
    with db.session() as session:
        session.add(RoadSourcePermission(id="permit", policy={}, policy_hash="a" * 64,
            accepted_at=NOW - timedelta(days=1), valid_until=NOW + timedelta(days=3)))
        session.commit()
    history.capture(db, config, now=NOW)
    with db.session() as session:
        session.get(RoadSourcePermission, "permit").revoked_at = NOW
        session.commit()
    history.capture(db, settings(road_source_permission_id="permit", road_watch_enabled=False), now=NOW + timedelta(minutes=5))
    with db.session() as session:
        session.get(RoadSourcePermission, "permit").revoked_at = None
        session.commit()
    history.capture(db, config, now=NOW + timedelta(minutes=10))
    point = read(db, "traffic", now=NOW + timedelta(minutes=10))["points"][-1]
    assert point["access_states"] == {"record_current": 2, "revoked": 1}
    assert point["collector_states"] == {"configured": 2, "disabled": 1}
    assert point["disabled_samples"] >= 1
    assert point["last_state"]["access"] == "record_current"


def test_migration_roundtrip_preserves_native_data_and_personal_receipts(db):
    from pathlib import Path

    from alembic.config import Config
    from sqlalchemy import inspect

    from alembic import command
    from helvetic_lens.models import MonitoringSourceAcknowledgement as Receipt
    admins(db)
    seed(db)
    with db.session() as session:
        session.add(Receipt(user_id="owner", issue_key="air:air:acquisition_errors", fingerprint="a" * 64, acknowledged_at=NOW))
        session.commit()
    history.capture(db, settings(), now=NOW)
    root = Path(__file__).resolve().parents[1]
    with db.engine.begin() as connection:
        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(root / "alembic"))
        config.attributes["connection"] = connection
        command.downgrade(config, "ad80517acef0")
        assert "monitoring_operational_samples" not in inspect(connection).get_table_names()
        assert "monitoring_source_samples" in inspect(connection).get_table_names()
    db.migrate()
    with db.session() as session:
        assert session.get(AirSourceCache, "BAS").data == {"private": "do-not-retain"}
        assert session.scalar(select(func.count()).select_from(Receipt)) == 1
        assert session.scalar(select(func.count()).select_from(Sample)) == 0


def test_cleanup_is_bounded_and_catches_up_without_forging_missing_intervals(db):
    admins(db)
    history.capture(db, settings(), now=NOW)
    with db.session() as session:
        values = session.scalar(select(Sample).where(Sample.channel == "air")).values
        for index in range(4001):
            at = NOW - timedelta(days=40, minutes=index * 5)
            session.add(Sample(channel="air", bucket_at=at, recorded_at=at, values=values))
        session.commit()
    assert history.capture(db, settings(), now=NOW) == {"sampled": 0, "removed": 4000}
    assert history.capture(db, settings(), now=NOW) == {"sampled": 0, "removed": 1}
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(Sample)) == 10
    assert sum(p["samples"] for p in read(db, days=30)["points"]) == 1
