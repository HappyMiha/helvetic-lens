from copy import deepcopy
from datetime import timedelta

import pytest
from sqlalchemy import select
from test_road_jobs import NOW, accept, feed, record, refresh, setup
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens import road_events as events
from helvetic_lens import road_repository as repository
from helvetic_lens import road_today as reader
from helvetic_lens.config import DomainError
from helvetic_lens.road_catalog import publish_mapping, revoke_topology
from helvetic_lens.road_models import (
    RoadCorridorReference,
    RoadDevelopment,
    RoadEventVersion,
    RoadMonitor,
    RoadSourceHead,
)
from helvetic_lens.road_sources import revoke_permission
from helvetic_lens.road_topology import CorridorFlow

db, template = _database_fixture, _template_fixture


def inbox(db, settings, *, actor="owner", minute=0, **kwargs):
    with db.session() as session:
        result = reader.inbox(session, settings, actor, now=NOW + timedelta(minutes=minute), **kwargs)
        assert not session.dirty and not session.new and not session.deleted
        return result


def test_major_closure_is_private_and_reading_it_does_not_change_state(db):
    row, _, _, settings = setup(db)
    assert inbox(db, settings)["unverified_routes"]
    refresh(db, row, settings)
    result = inbox(db, settings)
    assert result["has_active_routes"] and result["source_available"] and not result["unverified_routes"]
    item, = result["items"]
    assert item["priority"] == "urgent" and item["event"]["reviewed_sequence"] == 0
    assert item["href"].endswith("sequence=1")
    assert inbox(db, settings, actor="peer")["items"] == []
    assert not inbox(db, settings, actor="peer")["has_active_routes"]
    with db.organization_context("org-b"):
        assert not inbox(db, settings)["has_active_routes"]
    with pytest.raises(DomainError):
        inbox(db, settings, actor="peer", cursor=item["id"])


@pytest.mark.parametrize("xml", [feed(record(code="laneClosures")),
    feed().replace("2026-09-13T09:30:00Z", "2026-09-14T22:00:00Z"),
    feed().replace("<probabilityOfOccurrence>certain", "<probabilityOfOccurrence>probable")])
def test_partial_planned_and_probable_closures_stay_in_today_without_major_inbox_priority(db, xml):
    row, _, _, settings = setup(db, xml=xml)
    refresh(db, row, settings)
    assert inbox(db, settings)["items"] == []
    with db.session() as session:
        assert reader.today(session, settings, "owner", now=NOW)["items"]


@pytest.mark.parametrize("change", ["stale", "source_off", "source_revoked", "topology_revoked", "mapping", "future"])
def test_unverified_data_never_looks_like_a_current_closure_or_a_clear_road(db, change):
    row, permission, topo, settings = setup(db)
    refresh(db, row, settings)
    with db.session() as session:
        if change == "source_off":
            settings.road_source_enabled = False
        elif change == "source_revoked":
            revoke_permission(session, permission, now=NOW)
        elif change == "topology_revoked":
            revoke_topology(session, topo, now=NOW)
        elif change == "mapping":
            ref = session.get(RoadCorridorReference, row["configuration"]["corridor_reference_ids"][0])
            publish_mapping(session, ref.id, topology_id=topo, flow=CorridorFlow(key="north", points=(120, 110, 100)),
                expected_generation=ref.generation, review_reference="synthetic correction", now=NOW)
        elif change == "future":
            session.scalar(select(RoadSourceHead)).received_at = NOW + timedelta(minutes=1)
        session.commit()
    result = inbox(db, settings, minute=10 if change == "stale" else 0)
    assert result["items"] == [] and result["has_active_routes"]
    assert not result["source_available"] or result["unverified_routes"] or result["unverified_count"]


def test_long_running_closure_uses_current_evidence_when_old_snapshot_has_expired(db):
    row, _, _, settings = setup(db)
    refresh(db, row, settings)
    with db.session() as session:
        version = session.scalar(select(RoadEventVersion))
        version.created_at = NOW - timedelta(days=3)
        version.expires_at, version.payload = NOW - timedelta(days=1), None
        session.commit()
    item, = inbox(db, settings)["items"]
    with db.session() as session:
        assert reader.today(session, settings, "owner", now=NOW)["items"] == []
        detail = reader.detail(session, "owner", item["event_id"], sequence=item["sequence"], now=NOW)
        assert detail["snapshot"]["payload"] is None and detail["event"]["payload"]


@pytest.mark.parametrize("action", ["review", "mute", "pause", "archive", "revision"])
def test_inbox_and_today_share_exact_review_mute_and_configuration_state(db, action):
    row, _, _, settings = setup(db)
    refresh(db, row, settings)
    item, = inbox(db, settings)["items"]
    with db.session() as session:
        event = session.get(RoadDevelopment, item["event_id"])
        if action in {"review", "mute"}:
            result = events.review_event(session, "owner", event.id, expected_version=event.version, sequence=event.sequence,
                **({"muted": True} if action == "mute" else {}))
            assert result["reviewed_sequence"] == (0 if action == "mute" else 1)
        elif action == "revision":
            session.get(RoadMonitor, row["id"]).revision += 1
        else:
            repository.command(session, "owner", row["id"], row["version"], action, now=NOW, settings=settings)
        session.commit()
    assert inbox(db, settings)["items"] == []
    with db.session() as session:
        assert reader.today(session, settings, "owner", now=NOW)["items"] == []


def test_clearance_removes_major_inbox_card_but_keeps_new_today_change(db):
    row, permission, _, settings = setup(db)
    refresh(db, row, settings)
    old, = inbox(db, settings)["items"]
    accept(db, permission, feed(record(code="roadCleared")), minute=1, expected_generation=2)
    refresh(db, row, settings, minute=1)
    assert inbox(db, settings, minute=1)["items"] == []
    with pytest.raises(DomainError):
        inbox(db, settings, minute=1, cursor=old["id"])
    with db.session() as session:
        cleared, = reader.today(session, settings, "owner", now=NOW + timedelta(minutes=1))["items"]
        assert cleared["event_id"] == old["event_id"] and cleared["priority"] == "normal"


def test_sparse_inbox_scans_continue_past_inaccessible_rows(db):
    row, _, _, settings = setup(db)
    refresh(db, row, settings)
    with db.session() as session:
        original = session.scalar(select(RoadDevelopment))
        original_version = session.scalar(select(RoadEventVersion))
        def values(value):
            return {c.name: deepcopy(getattr(value, c.name)) for c in value.__table__.columns if c.name != "id"}
        for index in range(110):
            event = RoadDevelopment(**{**values(original), "source_id": f"inaccessible-{index}"})
            session.add(event)
            session.flush()
            session.add(RoadEventVersion(**{**values(original_version), "development_id": event.id}))
        original_version.created_at = NOW - timedelta(seconds=1)
        session.commit()
    first = inbox(db, settings)
    assert first["items"] == [] and first["next_cursor"] and first["unverified_count"] == 100
    second = inbox(db, settings, cursor=first["next_cursor"])
    assert len(second["items"]) == 1 and second["items"][0]["event_id"] == original.id
