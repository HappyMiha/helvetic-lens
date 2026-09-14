"""Cross-domain diagnostic evidence remains bounded, private and read-only."""
import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens.air_models import AirSourceCache
from helvetic_lens.config import Settings
from helvetic_lens.monitoring_source_operations import permission, snapshot
from helvetic_lens.road_models import RoadSourcePermission

db, template = _database_fixture, _template_fixture
NOW = datetime(2026, 9, 14, 6, tzinfo=UTC)


def settings(**kwargs):
    return Settings(_env_file=None, **kwargs)


def test_all_nine_four_packs_no_source_or_monitor_activation(db):
    queries = []
    def capture(connection, cursor, statement, parameters, context, executemany):
        queries.append(statement)
    event.listen(db.engine, "before_cursor_execute", capture)
    try:
        with db.session() as session:
            data = snapshot(session, settings(), now=NOW)
            assert not session.new and not session.dirty and not session.deleted
    finally:
        event.remove(db.engine, "before_cursor_execute", capture)
    assert len(data["packs"]) == 4
    assert {r["id"] for r in data["items"]} == {"pollen", "river", "air", "warnings", "commute", "traffic", "tenders", "ip", "auctions"}
    assert all(r["href"].startswith("/") for r in data["items"])
    assert all(r["acquisition"]["latest_success_at"] is None for r in data["items"])
    assert all(r["acquisition"]["latest_success_age_seconds"] is None for r in data["items"])
    assert len(queries) < 35
    assert all(q.lstrip().upper().startswith("SELECT") for q in queries)
    assert not any("_monitors" in q or "_deliveries" in q or "raw_payload" in q or "policy," in q for q in queries)


def test_mixed_channels_preserve_oldest_failure_and_unknown_without_error_text(db):
    with db.session() as session:
        for key, at, error in (("catalog", NOW - timedelta(hours=2), None), ("BAS", None, "SECRET-signed-url-token")):
            session.add(AirSourceCache(key=key, data={"private": "never serialized"}, fetched_at=at,
                next_fetch_at=NOW + timedelta(hours=1), error=error, failures=1))
        session.commit()
    with db.session() as session:
        data = snapshot(session, settings(), now=NOW)
    air = next(i for i in data["items"] if i["id"] == "air")["acquisition"]
    assert air["state"] == "errors" and air["record_count"] == 2
    assert air["never_succeeded_count"] == 1 and air["error_count"] == 1
    assert air["oldest_success_age_seconds"] == 7200 and air["source_published_at"] is None
    assert "SECRET" not in json.dumps(data) and "never serialized" not in json.dumps(data)


def test_future_source_clock_is_unknown_age_not_zero(db):
    with db.session() as session:
        session.add(AirSourceCache(key="BAS", data={}, fetched_at=NOW + timedelta(hours=1),
            next_fetch_at=NOW + timedelta(hours=2), failures=0))
        session.commit()
    with db.session() as session:
        air = next(i for i in snapshot(session, settings(), now=NOW)["items"] if i["id"] == "air")["acquisition"]
    assert air["state"] == "invalid_clock" and air["invalid_clock"]
    assert air["latest_success_age_seconds"] is None


@pytest.mark.parametrize("state,accepted,expires,revoked", [
    ("record_current", -1, 1, False), ("expired", -2, 0, False),
    ("not_yet_valid", 1, 2, False), ("revoked", -1, 1, True)])
def test_permission_clock_uses_bound_record_without_exposing_policy(db, state, accepted, expires, revoked):
    with db.session() as session:
        session.add(RoadSourcePermission(id="permission", policy={"endpoint": "SECRET"}, policy_hash="x" * 64,
            accepted_at=NOW + timedelta(hours=accepted), valid_until=NOW + timedelta(hours=expires),
            revoked_at=NOW if revoked else None))
        session.commit()
    with db.session() as session:
        result = permission(session, RoadSourcePermission, "permission", NOW)
        assert result["state"] == state and "SECRET" not in json.dumps(result)
        assert permission(session, RoadSourcePermission, "other", NOW)["state"] == "missing"


def test_disabled_sections_stay_visible_and_missing_keys_not_replaced_by_recorded_data(db):
    data = snapshot_next = None
    with db.session() as session:
        data = snapshot(session, settings(road_watch_enabled=False, road_source_enabled=True,
            road_source_key="", ipi_username="SECRET", ipi_password="SECRET"), now=NOW)
        snapshot_next = snapshot(session, settings(road_watch_enabled=True, road_source_enabled=True,
            road_source_key="SECRET"), now=NOW)
    road = next(i for i in data["items"] if i["id"] == "traffic")
    assert not road["section_enabled"] and road["href"] == "/road-watch"
    assert road["collector"] == "credentials_required" and road["access"]["state"] == "missing"
    road = next(i for i in snapshot_next["items"] if i["id"] == "traffic")
    assert road["collector"] == "configured" and road["access"]["state"] == "missing"
    assert "SECRET" not in json.dumps(data) + json.dumps(snapshot_next)


def test_platform_admin_http_scope_revocation_and_no_store(tmp_path):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_auth import _register, _settings

    from helvetic_lens.main import create_app
    from helvetic_lens.models import User
    app = create_app(_settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    path = "/api/admin/monitoring-sources"
    with TestClient(app) as client:
        assert client.get(path).status_code == 401
        identity = _register(client).json()
        assert client.get(path).status_code == 403
        with app.state.service.db.session(include_all_organizations=True) as session:
            session.get(User, identity["user"]["id"]).platform_admin = True
            session.commit()
        response = client.get(path)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store" and len(response.json()["items"]) == 9
        with app.state.service.db.session(include_all_organizations=True) as session:
            session.get(User, identity["user"]["id"]).platform_admin = False
            session.commit()
        assert client.get(path).status_code == 403


@pytest.mark.parametrize("enabled", [False, True])
def test_hazard_collector_switch_does_not_hide_section_or_invent_channel(db, enabled):
    with db.session() as session:
        data = snapshot(session, settings(hazard_watch_enabled=True, hazard_source_enabled=enabled), now=NOW)
    hazard = next(item for item in data["items"] if item["id"] == "warnings")
    assert hazard["section_enabled"]
    assert hazard["collector"] == ("channel_required" if enabled else "disabled")
    assert hazard["access"]["state"] == "missing"


@pytest.mark.parametrize("future", [False, True])
def test_mobility_receipt_publication_retry_clocks_and_failure_are_distinct(db, future):
    from helvetic_lens.commute_models import CommuteFeedState, CommuteSourcePermission, CommuteSourcePoll
    from helvetic_lens.road_models import RoadSourceHead, RoadSourcePoll
    from helvetic_lens.road_sources import SOURCE
    from helvetic_lens.transport_feed import TRIPS
    published = NOW + timedelta(minutes=10) if future else NOW - timedelta(minutes=10)
    received = NOW - timedelta(minutes=1)
    retry = NOW + timedelta(minutes=5)
    with db.session() as session:
        session.add(RoadSourcePermission(id="road", policy={}, policy_hash="a" * 64,
            accepted_at=NOW - timedelta(days=1), valid_until=NOW + timedelta(days=1)))
        session.add(CommuteSourcePermission(id="commute", source=TRIPS, policy_reference="SECRET",
            accepted_at=NOW - timedelta(days=1), valid_until=NOW + timedelta(days=1), max_age_seconds=1800))
        session.flush()
        session.add(RoadSourcePoll(source=SOURCE, permission_id="road", next_request_at=retry,
            last_success_at=received, failures=1, last_code="SECRET"))
        session.add(RoadSourceHead(source=SOURCE, permission_id="road", generation=1,
            published_at=published, received_at=received))
        session.add(CommuteSourcePoll(source=TRIPS, permission_id="commute", next_request_at=retry,
            failures=1, last_code="SECRET"))
        session.add(CommuteFeedState(source=TRIPS, permission_id="commute", generation=1,
            received_at=received, observed_at=published, content_hash="a" * 64, content=b"SECRET"))
        session.commit()
    with db.session() as session:
        data = snapshot(session, settings(road_source_permission_id="road", commute_gtfs_rt_permission_id="commute"), now=NOW)
        replaced = snapshot(session, settings(road_source_permission_id="replacement", commute_gtfs_rt_permission_id="replacement"), now=NOW)
    road = next(i for i in data["items"] if i["id"] == "traffic")["acquisition"]
    commute = next(i for i in data["items"] if i["id"] == "commute")["channels"][0]["acquisition"]
    for row in (road, commute):
        assert row["state"] == ("invalid_clock" if future else "errors")
        assert row["latest_success_at"] == received.isoformat()
        assert row["source_published_at"] == published.isoformat()
        assert row["next_request_at"] == retry.isoformat()
        assert row["error_count"] == 1 and row["latest_success_age_seconds"] == 60
    assert next(i for i in replaced["items"] if i["id"] == "traffic")["acquisition"]["record_count"] == 0
    assert next(i for i in replaced["items"] if i["id"] == "commute")["channels"][0]["acquisition"]["record_count"] == 0
    assert "SECRET" not in json.dumps(data)


def test_replaced_native_source_generations_do_not_report_old_success(db):
    from helvetic_lens.aste_models import AsteCollector
    from helvetic_lens.auction_source_models import AuctionSourcePermission, AuctionSourceSelection
    from helvetic_lens.ipi_models import IPITraversal
    from helvetic_lens.trademark_source_models import TrademarkSourcePermission, TrademarkSourceSelection
    with db.session() as session:
        for model in (AuctionSourcePermission, TrademarkSourcePermission):
            session.add(model(id="native", policy={"SECRET": "credential"}, policy_hash="a" * 64,
                accepted_at=NOW - timedelta(days=1), valid_until=NOW + timedelta(days=1)))
        session.flush()
        for model in (AuctionSourceSelection, TrademarkSourceSelection):
            session.add(model(source_key="native", permission_id="native", generation=2, cursor_version=0))
        session.add(AsteCollector(source_key="native", permission_id="native", generation=1,
            discovery_due_at=NOW, next_request_at=NOW, last_completed_at=NOW))
        session.add(IPITraversal(source_key="native", permission_id="native", generation=1,
            started_at=NOW - timedelta(hours=1), completed_at=NOW, state="completed",
            request_expires_at=NOW, next_attempt_at=NOW))
        session.commit()
    with db.session() as session:
        data = snapshot(session, settings(aste_source_permission_id="native", ipi_source_permission_id="native"), now=NOW)
    for item in data["items"]:
        if item["id"] in {"auctions", "ip"}:
            assert item["acquisition"]["latest_success_at"] is None
            assert item["acquisition"]["record_count"] == 0
    assert "SECRET" not in json.dumps(data)


def test_latest_ip_traversal_not_previous_failed_run_is_current_diagnostic(db):
    from helvetic_lens.ipi_models import IPITraversal
    from helvetic_lens.trademark_source_models import TrademarkSourcePermission, TrademarkSourceSelection
    with db.session() as session:
        session.add(TrademarkSourcePermission(id="native", policy={}, policy_hash="a" * 64,
            accepted_at=NOW - timedelta(days=1), valid_until=NOW + timedelta(days=1)))
        session.flush()
        session.add(TrademarkSourceSelection(source_key="native", permission_id="native", generation=1, cursor_version=0))
        for hours, error in ((2, "SECRET"), (1, None)):
            session.add(IPITraversal(source_key="native", permission_id="native", generation=1,
                started_at=NOW - timedelta(hours=hours), completed_at=NOW - timedelta(minutes=hours),
                state="completed", request_expires_at=NOW, next_attempt_at=NOW, last_error=error))
        session.commit()
    with db.session() as session:
        data = snapshot(session, settings(ipi_source_permission_id="native"), now=NOW)
    source = next(i for i in data["items"] if i["id"] == "ip")["acquisition"]
    assert source["record_count"] == 1 and source["error_count"] == 0
    assert source["latest_success_age_seconds"] == 60
