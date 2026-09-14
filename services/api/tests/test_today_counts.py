"""Native private review queues, not a sum of the first visible pages."""

from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import uuid4

import pytest
from sqlalchemy import delete, event
from test_air_watch import configuration
from test_monitoring_centre import centre as centre
from test_river_today import change as river_change
from test_river_today import monitor as river_monitor
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens import monitoring_review_queue as review_queues
from helvetic_lens import today_counts as summary
from helvetic_lens.air_models import AirChange, AirMonitor
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.models import OrganizationMembership
from helvetic_lens.monitoring_contracts import public_pollen_rollout
from helvetic_lens.monitoring_notifications import page as notification_page
from helvetic_lens.prompt_settings import PromptSettings

NOW = datetime(2026, 9, 14, 12, tzinfo=UTC)
URL = "/api/monitoring-centre/today-counts"


def enabled(settings=None):
    settings = settings or Settings(_env_file=None)
    for name in ("air", "river", "tender", "commute", "road", "hazard", "trademark", "auction"):
        setattr(settings, name + "_watch_enabled", True)
    settings.road_source_enabled = True
    settings.deployment_instance = "main"
    settings.monitoring_rollout = public_pollen_rollout()
    return settings


def count(db, domain, expected, *, settings=None, now=NOW, user="owner"):
    statements = []
    def capture(conn, cursor, sql, parameters, context, many):
        statements.append(sql)
    event.listen(db.engine, "before_cursor_execute", capture)
    try:
        with db.session() as session:
            result = summary.counts(session, enabled(settings), user, now=now, prompts=PromptSettings())
            if domain != "legal":
                cursor, notifications = None, []
                for _ in range(100):
                    queue = notification_page(session, enabled(settings), user, domain=domain, now=now,
                                              prompts=PromptSettings(), cursor=cursor)
                    notifications.extend(queue["items"])
                    cursor = queue["next_cursor"]
                    if cursor is None:
                        break
                assert cursor is None and len(notifications) == expected
                assert all(item["domain"] == domain and item["href"].startswith("/") for item in notifications)
            assert not session.new and not session.dirty and not session.deleted
    finally:
        event.remove(db.engine, "before_cursor_execute", capture)
    assert all(sql.lstrip().upper().startswith("SELECT") for sql in statements)
    assert {item["domain"] for item in result["items"]} == set(summary.DOMAINS)
    row = next(item for item in result["items"] if item["domain"] == domain)
    assert row == {"domain": domain, "count": expected, "state": "complete"}
    assert result["total"] == sum(item["count"] for item in result["items"])
    assert not result["coverage_verified"]
    assert all(set(item) == {"domain", "count", "state"} for item in result["items"])
    return result


def test_sparse_continuations_exhaustion_and_cycles_never_become_fake_totals(monkeypatch):
    calls = []
    def page(cursor):
        calls.append(cursor)
        return {None: {"items": [1] * 50, "next_cursor": "sparse"},
                "sparse": {"items": [], "next_cursor": "last"},
                "last": {"items": [1] * 3, "next_cursor": None}}[cursor]
    assert summary._scan(page, deadline=monotonic() + 60) == {"count": 53, "state": "complete"}
    assert calls == [None, "sparse", "last"]
    monkeypatch.setattr(summary, "MAX_PAGES", 2)
    assert summary._scan(page, deadline=monotonic() + 60) == {"count": None, "state": "incomplete"}
    assert summary._scan(page, deadline=0) == {"count": None, "state": "incomplete"}
    calls.clear()
    def cyclic(cursor):
        calls.append(cursor)
        return {"items": [1], "next_cursor": "same"}
    assert summary._scan(cyclic, deadline=monotonic() + 60)["count"] is None
    assert len(calls) == 2


def test_air_and_river_count_all_pages_latest_heads_and_owner_only(db):
    with db.session(include_all_organizations=True) as session:
        air = AirMonitor(organization_id="org-a", owner_user_id="owner", request_key=str(uuid4()),
            request_hash="a" * 64, configuration=configuration(), status="active")
        session.add(air)
        session.flush()
        for sequence in range(1, 55):
            session.add(AirChange(organization_id="org-a", monitor_id=air.id, sequence=sequence,
                development_id="revised" if sequence <= 2 else str(uuid4()), revision=1,
                kind="threshold_crossed", priority=2, evidence={"sample": {"metric": "O3"}},
                decision="reviewed" if sequence == 2 else None, created_at=NOW))
        mine = river_monitor(session)
        for sequence in range(1, 54):
            river_change(session, mine, sequence=sequence)
        river_change(session, river_monitor(session, owner="peer"))
        river_change(session, river_monitor(session, org="org-b"))
        river_change(session, river_monitor(session, status="archived"))
        session.commit()
    result = count(db, "air", 52)
    assert result["total"] == 105
    count(db, "river", 53)
    count(db, "air", 0, user="viewer")
    with db.organization_context("org-b"):
        count(db, "air", 0)
    with db.session() as session:
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == "owner"))
        session.commit()
    with db.session() as session, pytest.raises(DomainError):
        summary.counts(session, enabled(), "owner", now=NOW, prompts=PromptSettings())


def test_pollen_continue_is_reviewed_and_new_material_reopens(db):
    import test_monitoring_runtime as fixture

    from helvetic_lens import monitoring_runtime
    subject = fixture.seed(db)
    fixture.input_sample(db, "0")
    started = fixture.command(db, subject)
    fixture.input_sample(db, "10", 1)
    fixture.refresh(db, subject, started["runtime"]["run_id"], 1)
    now = fixture.NOW + timedelta(hours=1)
    count(db, "pollen", 1, settings=fixture.policy(), now=now)
    with db.session() as session:
        item, = monitoring_runtime.today(session, settings=fixture.policy(), user_id="owner", now=now)["items"]
        monitoring_runtime.review(session, user_id="owner", subject_id=subject,
            entry_id=item["id"], decision="continue", expected_version=0)
        session.commit()
    count(db, "pollen", 0, settings=fixture.policy(), now=now)
    fixture.input_sample(db, "0", 2)
    fixture.refresh(db, subject, started["runtime"]["run_id"], 2)
    count(db, "pollen", 1, settings=fixture.policy(), now=fixture.NOW + timedelta(hours=2))


def test_tender_review_reopen_and_revoked_source(db):
    from test_tender_repository import decide, ingest, read, revised
    from test_tender_today import NOW, seed

    from helvetic_lens.tender_rights import restrict
    monitor, raw, dossier = seed(db)
    count(db, "tenders", 1, now=NOW)
    decide(db, read(db, dossier))
    count(db, "tenders", 0, now=NOW)
    updated = revised(raw)
    updated["terms"]["termsCriteria"][0]["description"] = {"en": "5 references required"}
    ingest(db, monitor, updated)
    count(db, "tenders", 1, now=NOW)
    with db.session() as session:
        restrict(session, scope="publication", target_id=updated["id"], policy_reference="fixture", now=NOW)
        session.commit()
    count(db, "tenders", 0, now=NOW)


def test_commute_current_signal_and_private_owner(db):
    from test_commute_jobs import NOW, refresh, scenario
    row, _, settings = scenario(db)
    refresh(db, row, settings)
    count(db, "commute", 1, settings=settings, now=NOW)
    count(db, "commute", 0, settings=settings, now=NOW, user="peer")


def test_road_source_permission_rechecked(db):
    from test_road_jobs import NOW, refresh, setup

    from helvetic_lens.road_models import RoadSourcePermission
    row, permission, _, settings = setup(db)
    refresh(db, row, settings)
    count(db, "traffic", 1, settings=settings, now=NOW)
    with db.session() as session:
        session.get(RoadSourcePermission, permission).revoked_at = NOW
        session.commit()
    count(db, "traffic", 0, settings=settings, now=NOW)


def test_hazard_geometry_rechecked_and_review_suppressed(db, monkeypatch):
    from test_hazard_events import NOW, GeometryFixture, review, setup
    store = GeometryFixture()
    monkeypatch.setattr(review_queues, "BoundaryStore", lambda path: store)
    monitor, _, _, development = setup(db, store)
    count(db, "warnings", 1, now=NOW)
    store.available = False
    count(db, "warnings", 0, now=NOW)
    store.available = True
    review(db, monitor, development, store, 1)
    count(db, "warnings", 0, now=NOW)


def test_trademark_current_candidate_and_review(db):
    from test_trademark_workflow import NOW, review, running
    _, monitor = running(db)
    count(db, "ip", 1, now=NOW)
    review(db, monitor)
    count(db, "ip", 0, now=NOW)


def test_auction_changes_exclude_reviewed_deadline_tracking(db):
    from test_auction_workflow import NOW, action, running
    _, monitor = running(db)
    count(db, "auctions", 1, now=NOW)
    action(db, monitor, following=True)
    action(db, monitor, decision="inspect")
    count(db, "auctions", 0, now=NOW)


def test_http_private_snapshot_no_store_and_disabled_never_zero(centre):
    client, app, settings, identity = centre
    enabled(settings)
    response = client.get(URL)
    assert response.status_code == 200, response.text
    assert "no-store" in response.headers["cache-control"]
    assert response.json()["total"] == 0 and len(response.json()["items"]) == 10
    settings.air_watch_enabled = False
    response = client.get(URL)
    assert response.json()["total"] is None
    assert next(row for row in response.json()["items"] if row["domain"] == "air")["state"] == "unavailable"
    with app.state.service.db.session(include_all_organizations=True) as session:
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"]))
        session.commit()
    denied = client.get(URL)
    assert denied.status_code in {401, 403} and "no-store" in denied.headers["cache-control"]


def test_over_budget_has_no_global_total(db, monkeypatch):
    monkeypatch.setattr(summary, "SCAN_SECONDS", 0)
    with db.session() as session:
        result = summary.counts(session, enabled(), "owner", now=NOW, prompts=PromptSettings())
    assert result["total"] is None
    assert all(row["count"] is None and row["state"] == "incomplete" for row in result["items"])


def test_legal_personal_read_state_and_invalid_topic_are_not_unread(harness):
    from test_interest_feed import seed

    from helvetic_lens.interest_feed import InterestFeedReader
    from helvetic_lens.models import MonitoringTopic, User
    _, _, service, model = harness
    topic, ids = seed(harness)
    with service.db.session() as session:
        session.add(User(id="count-owner", name="Owner", email="count-owner@example.test", password_hash="unused"))
        session.flush()
        session.add(OrganizationMembership(organization_id=service.organization_id, user_id="count-owner", role="viewer"))
        session.commit()
    count(service.db, "legal", 1, settings=service.settings, now=datetime.now(UTC), user="count-owner")
    reader = InterestFeedReader(service.organization_id, "count-owner", settings=service.settings, prompts=service.prompt_settings)
    with service.db.session() as session:
        reader.set_feed_state(session, ids[0], "read")
    count(service.db, "legal", 0, settings=service.settings, now=datetime.now(UTC), user="count-owner")
    with service.db.session() as session:
        reader.set_feed_state(session, ids[0], "unread")
        session.get(MonitoringTopic, topic["id"]).status = "paused"
        session.commit()
    count(service.db, "legal", 0, settings=service.settings, now=datetime.now(UTC), user="count-owner")
    assert model.calls == []


def test_snapshot_does_not_mix_a_concurrent_new_change_into_later_domain(db, monkeypatch):
    from types import SimpleNamespace

    with db.engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
    with db.session() as session:
        monitor = river_monitor(session)
        river_change(session, monitor)
        monitor_id = monitor.id
        session.commit()
    original = review_queues.air_today.today
    changed = False
    def while_counting(session, user_id, **kwargs):
        nonlocal changed
        result = original(session, user_id, **kwargs)
        if not changed:
            changed = True
            # Independent writer commits after membership establishes the read
            # snapshot but before the River projection is evaluated.
            from helvetic_lens.river_models import RiverMonitor
            with db.session() as writer:
                river_change(writer, writer.get(RiverMonitor, monitor_id), sequence=2)
                writer.commit()
        return result
    monkeypatch.setattr(review_queues.air_today, "today", while_counting)
    settings = enabled()
    service = SimpleNamespace(db=db, prompt_settings=PromptSettings(), relation_runtime_observation=lambda: None)
    first = summary.read(service, settings, "owner")
    assert changed and first["total"] == 1
    assert summary.read(service, settings, "owner")["total"] == 2
