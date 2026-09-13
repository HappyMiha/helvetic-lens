"""Private road developments reach Today and retain exact comparisons."""

from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_road_feed import NOW, feed, record
from test_road_jobs import current, refresh, setup
from test_road_sources import accept
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens import road_events as events
from helvetic_lens import road_repository as repository
from helvetic_lens import road_today as reader
from helvetic_lens.config import DomainError
from helvetic_lens.models import Job, OrganizationMembership, OutboxMessage
from helvetic_lens.road_catalog import revoke_topology
from helvetic_lens.road_models import RoadDevelopment, RoadEventVersion, RoadMonitor, RoadSourcePermission
from helvetic_lens.road_sources import revoke_permission

db, template = _database_fixture, _template_fixture


def page(db, settings, *, minute=0, user="owner", **kwargs):
    with db.session() as session:
        result = reader.today(session, settings, user, now=NOW + timedelta(minutes=minute), **kwargs)
        assert not session.new and not session.dirty and not session.deleted
        return result


def test_private_read_only_alert_and_exact_previous_current_comparison(db):
    row, permission, _, settings = setup(db)
    refresh(db, row, settings)
    initial, = page(db, settings)["items"]
    assert initial["priority"] == "urgent" and initial["sequence"] == 1
    assert initial["reason"] == "unread_road_change"
    assert initial["corridors"][0]["name"] == "Synthetic northbound"
    with db.session() as session:
        before = (list(session.scalars(select(Job.id))), list(session.scalars(select(OutboxMessage.id))))
        detail = reader.detail(session, "owner", initial["event_id"], now=NOW)
        assert detail["previous"] is None and detail["snapshot"]["sequence"] == 1
    accept(db, permission, feed(record(code="laneClosures")), minute=1, expected_generation=2)
    refresh(db, row, settings, minute=1)
    later, = page(db, settings, minute=1)["items"]
    assert later["event_id"] == initial["event_id"] and later["id"] != initial["id"]
    assert later["priority"] == "normal" and later["sequence"] == 2
    assert later["href"] == f"/road-watch?monitor={row['id']}&event={initial['event_id']}&sequence=2"
    with db.session() as session:
        old = reader.detail(session, "owner", initial["event_id"], sequence=1, monitor_id=row["id"], now=NOW + timedelta(minutes=1))
        assert old["newer_available"] and old["current_configuration"]
        old_fact = next(iter(old["snapshot"]["payload"]["corridors"].values()))["facts"][0]
        latest_fact = next(iter(old["event"]["payload"]["corridors"].values()))["facts"][0]
        assert old_fact["kind"] == "road_closure" and latest_fact["kind"] == "lane_restriction"
        latest = reader.detail(session, "owner", initial["event_id"], sequence=2, now=NOW + timedelta(minutes=1))
        assert latest["previous"]["payload"] == old["snapshot"]["payload"]
        assert session.get(RoadDevelopment, initial["event_id"]).reviewed_sequence == 0
        assert before == (list(session.scalars(select(Job.id))), list(session.scalars(select(OutboxMessage.id))))
        for options in ({"monitor_id": str(uuid4())}, {"sequence": 999}, {"sequence": 0}):
            with pytest.raises(DomainError):
                reader.detail(session, "owner", initial["event_id"], now=NOW, **options)
    for actor in ("peer", "viewer"):
        assert page(db, settings, user=actor)["items"] == []
        with db.session() as session, pytest.raises(DomainError):
            reader.detail(session, actor, initial["event_id"], now=NOW)
    with db.organization_context("org-b"), db.session() as session:
        assert reader.today(session, settings, "owner", now=NOW)["items"] == []
        with pytest.raises(DomainError):
            reader.detail(session, "owner", initial["event_id"], now=NOW)


@pytest.mark.parametrize("change", ["mute", "review", "pause", "archive", "revision", "source_off", "source_selection", "feature_off"])
def test_handled_or_inapplicable_changes_leave_today(db, change):
    row, _, _, settings = setup(db)
    refresh(db, row, settings)
    item, = page(db, settings)["items"]
    with db.session() as session:
        event = session.get(RoadDevelopment, item["event_id"])
        if change in {"mute", "review"}:
            result = events.review_event(session, "owner", event.id, expected_version=event.version, sequence=event.sequence,
                                         **({"muted": True} if change == "mute" else {}))
            assert result["reviewed_sequence"] == (0 if change == "mute" else 1)
        elif change in {"pause", "archive"}:
            repository.command(session, "owner", row["id"], row["version"], change, now=NOW)
        elif change == "revision":
            session.get(RoadMonitor, row["id"]).revision += 1
        elif change == "source_off":
            settings.road_source_enabled = False
        elif change == "source_selection":
            settings.road_source_permission_id = str(uuid4())
        else:
            settings.road_watch_enabled = False
        session.commit()
    assert page(db, settings)["items"] == []
    with db.session() as session:
        assert reader.detail(session, "owner", item["event_id"], now=NOW)["snapshot"]["payload"]


def test_unmute_restores_unread_change_and_new_change_invalidates_cursor(db):
    row, permission, _, settings = setup(db)
    refresh(db, row, settings)
    item, = page(db, settings)["items"]
    with db.session() as session:
        event = session.get(RoadDevelopment, item["event_id"])
        muted = events.review_event(session, "owner", event.id, expected_version=event.version, sequence=1, muted=True)
        events.review_event(session, "owner", event.id, expected_version=muted["version"], sequence=1, muted=False)
        session.commit()
    assert page(db, settings)["items"][0]["event"]["reviewed_sequence"] == 0
    accept(db, permission, feed(record(code="roadCleared")), minute=1, expected_generation=2)
    refresh(db, row, settings, minute=1)
    assert page(db, settings, minute=1)["items"][0]["priority"] == "normal"
    with pytest.raises(DomainError) as error:
        page(db, settings, minute=1, cursor=item["id"])
    assert error.value.code == "road_today_changed"


@pytest.mark.parametrize("change", ["source", "topology", "expired", "corrupt", "membership"])
def test_revocation_and_corruption_are_rechecked_on_today_and_exact_links(db, change):
    row, permission, topo, settings = setup(db)
    refresh(db, row, settings)
    item, = page(db, settings)["items"]
    with db.session() as session:
        if change == "source":
            revoke_permission(session, permission, now=NOW)
        elif change == "topology":
            revoke_topology(session, topo, now=NOW)
        elif change == "expired":
            session.get(RoadSourcePermission, permission).valid_until = NOW
        elif change == "corrupt":
            session.scalar(select(RoadEventVersion)).payload_hash = "0" * 64
        else:
            membership = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == "owner",
                                                                                OrganizationMembership.organization_id == "org-a"))
            session.delete(membership)
        session.commit()
    if change == "membership":
        with pytest.raises(DomainError):
            page(db, settings)
        with db.session() as session, pytest.raises(DomainError):
            reader.detail(session, "owner", item["event_id"], now=NOW)
    else:
        assert page(db, settings)["items"] == []
        with db.session() as session:
            detail = reader.detail(session, "owner", item["event_id"], now=NOW)
            assert detail["snapshot"]["payload"] is None
            assert detail["snapshot"]["attribution"] is None


@pytest.mark.parametrize("xml", [feed().replace("2026-09-13T09:30:00Z", "2026-09-14T22:00:00Z"),
    feed().replace("<probabilityOfOccurrence>certain", "<probabilityOfOccurrence>probable")])
def test_planned_and_probable_closures_are_not_urgent(db, xml):
    row, _, _, settings = setup(db, xml=xml)
    refresh(db, row, settings)
    assert page(db, settings)["items"][0]["priority"] == "normal"


def test_stale_closures_and_expired_windows_never_become_live_urgent_alerts(db):
    row, _, _, settings = setup(db)
    refresh(db, row, settings)
    assert page(db, settings, minute=10)["items"][0]["priority"] == "normal"
    assert page(db, settings, minute=10)["items"][0]["event"]["availability"] == "stale"
    assert page(db, settings, minute=49 * 60)["items"] == []
    item = current(db, row)
    fact = next(iter(item["payload"]["corridors"].values()))["facts"][0]
    fact["valid_until"] = NOW.isoformat()
    assert not reader.urgent(item, now=NOW)


def test_new_source_generation_removes_urgency_before_private_worker_catches_up(db):
    row, permission, _, settings = setup(db)
    refresh(db, row, settings)
    accept(db, permission, feed(situations=""), minute=1, expected_generation=2)
    item, = page(db, settings, minute=1)["items"]
    assert item["event"]["availability"] == "stale" and item["priority"] == "normal"
    refresh(db, row, settings, minute=1)
    missing, = page(db, settings, minute=1)["items"]
    assert missing["priority"] == "normal" and missing["event"]["payload"]["state"] == "unavailable"


def test_bounded_sparse_pagination_and_foreign_cursors(db):
    row, _, _, settings = setup(db)
    refresh(db, row, settings)
    with db.session() as session:
        original = session.scalar(select(RoadDevelopment))
        original_version = session.scalar(select(RoadEventVersion))
        def values(value):
            return {c.name: deepcopy(getattr(value, c.name)) for c in value.__table__.columns if c.name != "id"}
        for index in range(1, 121):
            event = RoadDevelopment(**values(original))
            event.source_id = f"synthetic-{index}"
            session.add(event)
            session.flush()
            version = RoadEventVersion(**{**values(original_version), "development_id": event.id})
            # Deliberately inaccessible proof: the referenced source belongs to
            # the original event, and must not be projected for these new IDs.
            session.add(version)
        session.commit()
    seen, cursor = [], None
    while True:
        result = page(db, settings, limit=1, cursor=cursor)
        seen.extend(item["event_id"] for item in result["items"])
        cursor = result["next_cursor"]
        if cursor is None:
            break
    assert seen == [original.id]
    # Force a deterministically empty first scan by moving the valid event last.
    with db.session() as session:
        session.get(RoadEventVersion, original_version.id).created_at = NOW - timedelta(seconds=1)
        session.commit()
    first = page(db, settings, limit=50)
    assert first["items"] == [] and first["next_cursor"]
    assert page(db, settings, limit=50, cursor=first["next_cursor"])["items"][0]["event_id"] == original.id
    with pytest.raises(DomainError):
        page(db, settings, user="peer", cursor=original_version.id)
