"""Retained River changes: privacy, latest revision, paging and review boundaries."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, select
from test_auth import _csrf
from test_river_watch import api as _api_fixture
from test_river_watch import config, sample
from test_tender_repository import db as _db_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens.config import DomainError
from helvetic_lens.models import OrganizationMembership
from helvetic_lens.river_models import RiverChange, RiverMonitor
from helvetic_lens.river_today import today

api, db, template = _api_fixture, _db_fixture, _template_fixture
NOW = datetime(2026, 9, 14, 12, tzinfo=UTC)


def monitor(session, *, owner="owner", org="org-a", status="active", revision=1):
    row = RiverMonitor(organization_id=org, owner_user_id=owner, request_key=str(uuid4()),
        request_hash="a" * 64, configuration=config(), status=status, revision=revision, version=1)
    session.add(row)
    session.flush()
    return row


def change(session, row, *, sequence=1, development=None, decision=None, at=NOW, sample_at=NOW, revision=1):
    result = RiverChange(organization_id=row.organization_id, monitor_id=row.id,
        development_id=development or str(uuid4()), sequence=sequence, revision=revision,
        kind="threshold_crossed", priority=2, decision=decision, review_version=0, created_at=at,
        evidence={"sample": sample(sample_at), "baseline": None, "station_id": "2289",
            "rule": None, "recovered": False, "corrected": False})
    session.add(result)
    session.flush()
    return result


def test_latest_before_review_filter_and_no_implicit_review_or_source_io(db):
    with db.session() as session:
        row = monitor(session)
        old = change(session, row)
        latest = change(session, row, sequence=2, development=old.development_id, decision="reviewed")
        wanted = change(session, row, sequence=3)
        ids = latest.id, wanted.id
        session.commit()
    statements = []
    def capture(conn, cursor, sql, parameters, context, many):
        statements.append(sql)
    event.listen(db.engine, "before_cursor_execute", capture)
    try:
        with db.session() as session:
            all_items = today(session, "owner", now=NOW)
            unread = today(session, "owner", unreviewed=True, now=NOW)
            assert not session.new and not session.dirty
    finally:
        event.remove(db.engine, "before_cursor_execute", capture)
    assert {i["id"] for i in all_items["items"]} == set(ids)
    assert [i["id"] for i in unread["items"]] == [ids[1]]
    assert unread["unreviewed_count"] == 1
    assert all(s.lstrip().upper().startswith("SELECT") for s in statements)
    assert not any("river_source_cache" in s or "river_measurements" in s or "river_deliveries" in s for s in statements)
    assert len(statements) == 6


def test_private_owner_workspace_archive_and_foreign_cursor(db):
    with db.session(include_all_organizations=True) as session:
        mine = change(session, monitor(session, status="paused", revision=2)).id
        foreign = change(session, monitor(session, owner="peer")).id
        change(session, monitor(session, org="org-b"))
        change(session, monitor(session, status="archived"))
        session.commit()
    with db.session() as session:
        item, = today(session, "owner", now=NOW)["items"]
        assert item["id"] == mine and item["monitor_status"] == "paused"
        assert not item["current_configuration"] and "change=" + mine in item["href"]
        assert item["evidence"]["baseline"] is None
        with pytest.raises(DomainError, match="Refresh"):
            today(session, "owner", before=NOW, before_id=foreign, now=NOW)
    with db.organization_context("org-b"), db.session() as session:
        assert len(today(session, "owner", now=NOW)["items"]) == 1
        assert today(session, "owner", now=NOW)["items"][0]["id"] != mine


def test_equal_time_pagination_replaced_anchor_and_new_insert(db):
    with db.session() as session:
        row = monitor(session)
        expected = [change(session, row, sequence=i + 1).id for i in range(53)]
        monitor_id = row.id
        session.commit()
    with db.session() as session:
        first = today(session, "owner", limit=30, now=NOW)
        anchor = session.get(RiverChange, first["next"]["before_id"])
        change(session, session.get(RiverMonitor, monitor_id), sequence=54,
            development=anchor.development_id, at=NOW + timedelta(seconds=1))
        session.commit()
    with db.session() as session:
        second = today(session, "owner", before=datetime.fromisoformat(first["next"]["before"]),
            before_id=first["next"]["before_id"], now=NOW)
        assert not second["next"]
        assert [i["id"] for i in first["items"] + second["items"]] == sorted(expected, reverse=True)
        assert len(today(session, "owner", now=NOW)["items"]) == 30


@pytest.mark.parametrize("minutes,state", [(0, "recent"), (-61, "stale"), (1, "future")])
def test_retained_sample_clock_never_claims_current_source_state(db, minutes, state):
    with db.session() as session:
        change(session, monitor(session), sample_at=NOW + timedelta(minutes=minutes))
        session.commit()
    with db.session() as session:
        item, = today(session, "owner", now=NOW)["items"]
        assert item["sample_state"] == state
        assert "health" not in item and "current" not in item


def test_membership_revocation_and_naive_cursor(db):
    with db.session() as session:
        with pytest.raises(DomainError):
            today(session, "owner", before=NOW.replace(tzinfo=None), before_id=str(uuid4()))
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == "owner"))
        session.commit()
    with db.session() as session, pytest.raises(DomainError):
        today(session, "owner", now=NOW)


def test_http_today_exact_review_conflict_viewer_no_store_and_kill_switch(api):
    client, service, settings, identity, now = api
    user, org = identity["user"]["id"], identity["organization"]["id"]
    with service.db.session() as session:
        row = monitor(session, owner=user, org=org)
        entry = change(session, row, at=now, sample_at=now)
        identifier, change_id = row.id, entry.id
        session.commit()
    path = "/api/river-watch/today"
    response = client.get(path)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert response.json()["unreviewed_count"] == 1
    assert client.get(path, params={"before": now.isoformat()}).status_code == 422
    assert client.get(path, params={"limit": 51}).status_code == 422
    exact = f"/api/river-watch/monitors/{identifier}/changes/{change_id}"
    assert client.get(exact).json()["event"]["id"] == change_id
    body = {"expected_version": 0, "decision": "reviewed"}
    assert client.post(exact + "/review", json=body).status_code == 403
    assert client.post(exact + "/review", json=body, headers=_csrf(client)).status_code == 200
    assert client.get(path, params={"unreviewed": True}).json()["items"] == []
    assert client.post(exact + "/review", json=body, headers=_csrf(client)).status_code == 409
    with service.db.session() as session:
        old = session.get(RiverChange, change_id)
        change(session, session.get(RiverMonitor, identifier), sequence=2, development=old.development_id,
            at=now, sample_at=now)
        session.commit()
    assert client.get(path, params={"unreviewed": True}).json()["unreviewed_count"] == 1
    assert client.post(exact + "/review", json={**body, "expected_version": 1}, headers=_csrf(client)).status_code == 409
    with service.db.session() as session:
        membership = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == user))
        membership.role = "viewer"
        session.commit()
    assert client.get(path).status_code == 200
    assert client.post(exact + "/review", json=body, headers=_csrf(client)).status_code == 403
    settings.river_watch_enabled = False
    assert client.get(path).status_code == 404
