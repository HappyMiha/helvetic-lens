"""Actual source metadata, renewal boundaries and personal operator receipts."""
from datetime import timedelta

import pytest
from sqlalchemy import delete, func, select
from test_monitoring_source_operations import NOW, settings
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens import monitoring_source_attention as attention
from helvetic_lens.air_models import AirSourceCache
from helvetic_lens.config import DomainError
from helvetic_lens.models import MonitoringSourceAcknowledgement as Receipt
from helvetic_lens.models import OrganizationMembership, User
from helvetic_lens.road_models import RoadSourcePermission


def admins(db):
    with db.session() as session:
        for identifier in ("owner", "peer"):
            session.get(User, identifier).platform_admin = True
        session.commit()


def read(db, config=None, now=NOW, user="owner"):
    with db.session() as session:
        result = attention.read(session, config or settings(), user, now=now)
        assert not session.new and not session.dirty and not session.deleted
        return result


def acknowledge(db, issue, config=None, now=NOW, user="owner"):
    with db.session() as session:
        value = attention.acknowledge(session, config or settings(), user, issue["key"], issue["fingerprint"], now=now)
        session.commit()
        return value


def test_nine_directions_two_transport_channels_and_bounded_private_receipts(db):
    admins(db)
    data = read(db)
    assert {row["domain"] for row in data["items"]} == {"pollen", "air", "river", "warnings", "commute", "traffic", "tenders", "ip", "auctions"}
    assert {row["channel"] for row in data["items"] if row["domain"] == "commute"} == {"trip_updates", "service_alerts"}
    assert data["unacknowledged"] == len(data["items"]) < 60
    assert all(row["latest_success_at"] is None for row in data["items"])
    first = data["items"][0]
    receipt = acknowledge(db, first)
    assert acknowledge(db, first, now=NOW + timedelta(seconds=1)) == receipt
    assert read(db)["unacknowledged"] == len(data["items"]) - 1
    assert read(db, user="peer")["unacknowledged"] == len(data["items"])
    assert len(read(db)["items"]) == len(data["items"]), "Acknowledgement must not remove the issue"
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(Receipt)) == 1
        with pytest.raises(DomainError, match="attention"):
            attention.acknowledge(session, settings(), "owner", "arbitrary:key", "a" * 64, now=NOW)


@pytest.mark.parametrize("days,expected", [(31, None), (30, "renewal_30_days"), (8, "renewal_30_days"), (7, "renewal_7_days"), (1, "renewal_7_days"), (0, "access_expired")])
def test_renewal_clock_boundaries_never_grant_access(db, days, expected):
    admins(db)
    config = settings(road_source_permission_id="permit")
    with db.session() as session:
        session.add(RoadSourcePermission(id="permit", policy={"secret": "not-public"}, policy_hash="c" * 64,
            accepted_at=NOW - timedelta(days=2), valid_until=NOW + timedelta(days=days)))
        session.commit()
    data = read(db, config)
    codes = [row["code"] for row in data["items"] if row["domain"] == "traffic"]
    assert expected in codes if expected else not any(code.startswith("renewal_") for code in codes)
    assert "not-public" not in str(data)


def test_acknowledged_renewal_reopens_at_urgent_boundary_and_on_source_replacement(db):
    admins(db)
    with db.session() as session:
        for identifier in ("first", "replacement"):
            session.add(RoadSourcePermission(id=identifier, policy={}, policy_hash="c" * 64,
                accepted_at=NOW - timedelta(days=2), valid_until=NOW + timedelta(days=8)))
        session.commit()
    config = settings(road_source_permission_id="first")
    issue = next(row for row in read(db, config)["items"] if row["code"] == "renewal_30_days")
    acknowledge(db, issue, config)
    urgent = next(row for row in read(db, config, now=NOW + timedelta(days=1))["items"] if row["code"] == "renewal_7_days")
    assert urgent["acknowledged_at"] is None and urgent["severity"] == "urgent"
    replacement = next(row for row in read(db, settings(road_source_permission_id="replacement"))["items"] if row["code"] == "renewal_30_days")
    assert replacement["acknowledged_at"] is None and replacement["fingerprint"] != issue["fingerprint"]
    with pytest.raises(DomainError):
        acknowledge(db, issue, config, now=NOW + timedelta(days=1))


def test_poll_retry_recovery_and_future_clock_do_not_remain_acknowledged(db):
    admins(db)
    with db.session() as session:
        session.add(AirSourceCache(key="BAS", data={"private": "no-payload"}, fetched_at=NOW - timedelta(hours=1),
            next_fetch_at=NOW + timedelta(minutes=5), error="secret raw provider error", failures=1))
        session.commit()
    issue = next(row for row in read(db)["items"] if row["key"] == "air:air:acquisition_errors")
    acknowledge(db, issue)
    assert next(row for row in read(db, now=NOW + timedelta(seconds=1))["items"] if row["key"] == issue["key"])["acknowledged_at"]
    with db.session() as session:
        row = session.get(AirSourceCache, "BAS")
        row.next_fetch_at += timedelta(minutes=5)
        session.commit()
    assert next(row for row in read(db)["items"] if row["key"] == issue["key"])["acknowledged_at"] is None
    with pytest.raises(DomainError):
        acknowledge(db, issue)
    with db.session() as session:
        row = session.get(AirSourceCache, "BAS")
        row.error, row.failures, row.fetched_at = None, 0, NOW
        session.commit()
    assert not any(row["code"].startswith("acquisition_") and row["domain"] == "air" for row in read(db)["items"])
    with db.session() as session:
        session.get(AirSourceCache, "BAS").fetched_at = NOW + timedelta(minutes=1)
        session.commit()
    data = read(db)
    assert any(row["code"] == "acquisition_invalid_clock" for row in data["items"])
    assert "secret" not in str(data) and "no-payload" not in str(data)


def test_current_role_revocation_and_account_erasure(db):
    admins(db)
    issue = read(db)["items"][0]
    acknowledge(db, issue)
    with db.session() as session:
        session.get(User, "owner").platform_admin = False
        session.commit()
    with pytest.raises(DomainError):
        read(db)
    with pytest.raises(DomainError):
        acknowledge(db, issue)
    with db.session() as session:
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == "owner"))
        session.execute(delete(User).where(User.id == "owner"))
        session.commit()
        assert session.scalar(select(func.count()).select_from(Receipt)) == 0


def test_source_generation_replacement_reopens_unknown_acquisition(db):
    from helvetic_lens.auction_source_models import AuctionSourcePermission, AuctionSourceSelection
    admins(db)
    config = settings(aste_source_permission_id="native")
    with db.session() as session:
        session.add(AuctionSourcePermission(id="native", policy={}, policy_hash="a" * 64,
            accepted_at=NOW - timedelta(days=1), valid_until=NOW + timedelta(days=90)))
        session.flush()
        session.add(AuctionSourceSelection(source_key="native", permission_id="native", generation=1, cursor_version=0))
        session.commit()
    issue = next(row for row in read(db, config)["items"] if row["key"] == "auctions:auctions:acquisition_unobserved")
    acknowledge(db, issue, config)
    with db.session() as session:
        session.get(AuctionSourceSelection, "native").generation = 2
        session.commit()
    current = next(row for row in read(db, config)["items"] if row["key"] == issue["key"])
    assert current["acknowledged_at"] is None and current["fingerprint"] != issue["fingerprint"]


def test_pollen_partial_access_preserves_expired_and_renewal_attention(db):
    from test_monitoring_runtime import policy
    admins(db)
    config = policy()
    channel = config.pollen_source_policy.channels[0]
    valid = channel.model_copy(update={"valid_from": NOW - timedelta(days=3), "valid_until": NOW + timedelta(days=3)})
    expired = channel.model_copy(update={"version": "old-channel", "valid_from": NOW - timedelta(days=3), "valid_until": NOW - timedelta(days=1)})
    config.pollen_source_policy = config.pollen_source_policy.model_copy(update={"channels": (valid, expired)})
    codes = {row["code"] for row in read(db, config)["items"] if row["domain"] == "pollen"}
    assert {"access_partial", "access_expired", "renewal_7_days"} <= codes


def test_real_http_auth_csrf_strict_binding_and_role_withdrawal(tmp_path):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_auth import _csrf, _register, _settings

    from helvetic_lens.main import create_app
    app = create_app(_settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    path = "/api/admin/monitoring-sources/attention"
    with TestClient(app) as client:
        assert client.get(path).status_code == 401
        identity = _register(client).json()
        assert client.get(path).status_code == 403

        with app.state.service.db.session() as session:
            session.get(User, identity["user"]["id"]).platform_admin = True
            session.commit()
        response = client.get(path)
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        issue = response.json()["items"][0]
        body = {key: issue[key] for key in ("key", "fingerprint")}
        assert client.post(path + "/acknowledge", json=body).status_code == 403
        assert client.post(path + "/acknowledge", json={**body, "user_id": "other"}, headers=_csrf(client)).status_code == 422
        accepted = client.post(path + "/acknowledge", json=body, headers=_csrf(client))
        assert accepted.status_code == 200, accepted.text
        assert accepted.headers["cache-control"] == "no-store"
        rejected = client.post(path + "/acknowledge", json={**body, "fingerprint": "0" * 64}, headers=_csrf(client))
        assert rejected.status_code == 409 and rejected.headers["cache-control"] == "no-store"
        with app.state.service.db.session() as session:
            session.get(User, identity["user"]["id"]).platform_admin = False
            session.commit()
        assert client.post(path + "/acknowledge", json=body, headers=_csrf(client)).status_code == 403
        assert client.get(path).status_code == 403


def test_receipt_migration_roundtrip_preserves_source_and_operator(db):
    from pathlib import Path

    from alembic.config import Config
    from sqlalchemy import inspect

    from alembic import command
    admins(db)
    with db.session() as session:
        session.add(AirSourceCache(key="retained", data={"retained": "source"}, next_fetch_at=NOW, fetched_at=NOW, failures=0))
        session.commit()
    acknowledge(db, read(db)["items"][0])
    root = Path(__file__).resolve().parents[1]
    with db.engine.begin() as connection:
        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(root / "alembic"))
        config.attributes["connection"] = connection
        command.downgrade(config, "9c7f5069bdef")
        assert "monitoring_source_acknowledgements" not in inspect(connection).get_table_names()
    db.migrate()
    with db.session() as session:
        assert session.get(AirSourceCache, "retained").data == {"retained": "source"}
        assert session.get(User, "owner").platform_admin
        assert session.scalar(select(func.count()).select_from(Receipt)) == 0


def test_renewal_crossing_during_lock_wait_requires_fresh_review(db, monkeypatch):
    from datetime import datetime

    admins(db)
    config = settings(road_source_permission_id="renewal")
    with db.session() as session:
        session.add(RoadSourcePermission(id="renewal", policy={}, policy_hash="b" * 64,
            accepted_at=NOW - timedelta(days=1), valid_until=NOW + timedelta(days=8)))
        session.commit()
    issue = next(row for row in read(db, config)["items"] if row["code"] == "renewal_30_days")
    clock = [NOW]
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0]
    original = attention.lock_platform_users
    def delayed(session, user):
        original(session, user)
        clock[0] = NOW + timedelta(days=2)
    monkeypatch.setattr(attention, "datetime", Clock)
    monkeypatch.setattr(attention, "lock_platform_users", delayed)
    with db.session() as session:
        with pytest.raises(DomainError) as error:
            attention.acknowledge(session, config, "owner", issue["key"], issue["fingerprint"])
        assert error.value.code == "source_attention_changed"
        assert session.scalar(select(func.count()).select_from(Receipt)) == 0
