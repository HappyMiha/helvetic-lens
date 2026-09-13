"""Saved transport events reach Today without inventing freshness or read state."""

from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_commute_jobs import NOW, capture, refresh, scenario
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture
from test_transport_feed import feed, trip_feed

from helvetic_lens import commute_events as events
from helvetic_lens import commute_repository as repository
from helvetic_lens import commute_today as reader
from helvetic_lens.commute_models import (
    CommuteDevelopment,
    CommuteEventVersion,
    CommuteMonitor,
    CommuteSignal,
    CommuteSourcePermission,
)
from helvetic_lens.config import DomainError
from helvetic_lens.models import Job, OutboxMessage
from helvetic_lens.transport_feed import TRIPS

db, template = _database_fixture, _template_fixture


def page(db, settings, *, second=0, user="owner", **kwargs):
    with db.session() as session:
        result = reader.today(session, settings, user, now=NOW + timedelta(seconds=second), **kwargs)
        assert not session.new and not session.dirty and not session.deleted
        return result


def test_material_event_is_private_read_only_and_exactly_linked(db):
    row, grants, settings = scenario(db, delay=60)
    refresh(db, row, settings)
    assert page(db, settings)["items"] == []
    capture(db, grants[TRIPS], trip_feed(delay=600, second=1), second=1)
    refresh(db, row, settings, second=1)
    with db.session() as session:
        jobs = list(session.scalars(select(Job.id)))
        outbox = list(session.scalars(select(OutboxMessage.id)))
    item, = page(db, settings, second=1)["items"]
    assert item["sequence"] == item["signal_sequence"] == 2
    assert item["reasons"] == ["unread_journey_change"]
    assert item["priority"] == "normal" and item["reference_labels"]
    assert item["href"] == f"/commute-watch?monitor={row['id']}&event={item['event_id']}&sequence=2"
    assert next(iter(item["states"].values()))["delay_seconds"] == 600
    for user in ("peer", "viewer"):
        assert page(db, settings, second=1, user=user)["items"] == []
    with db.session() as session:
        assert session.get(CommuteDevelopment, item["event_id"]).reviewed_sequence == 0
        assert list(session.scalars(select(Job.id))) == jobs
        assert list(session.scalars(select(OutboxMessage.id))) == outbox
    with db.organization_context("org-b"), db.session() as session:
        assert reader.today(session, settings, "owner", now=NOW)["items"] == []
        with pytest.raises(DomainError):
            reader.detail(session, "owner", item["event_id"], now=NOW)


def test_deduplication_and_older_snapshot_never_replace_latest_state(db):
    row, grants, settings = scenario(db)
    refresh(db, row, settings)
    original, = page(db, settings)["items"]
    capture(db, grants[TRIPS], trip_feed(cancelled=True, second=1), second=1)
    refresh(db, row, settings, second=1)
    current, = page(db, settings, second=1)["items"]
    assert current["event_id"] == original["event_id"] and current["sequence"] == 2
    assert current["priority"] == "urgent"
    with db.session() as session:
        linked = reader.detail(session, "owner", current["event_id"], sequence=1, monitor_id=row["id"], now=NOW + timedelta(seconds=1))
        assert linked["newer_available"] and linked["current_configuration"]
        assert next(iter(linked["snapshot"]["evidence"]["current"]["states"].values()))["condition"] == "delay_material"
        assert next(iter(linked["event"]["current"]["states"].values()))["condition"] == "cancelled"
        assert linked["event"]["reference_labels"] == current["reference_labels"]
        assert session.get(CommuteDevelopment, current["event_id"]).reviewed_sequence == 0
        for options in ({"monitor_id": str(uuid4())}, {"sequence": 999}):
            with pytest.raises(DomainError):
                reader.detail(session, "owner", current["event_id"], now=NOW, **options)
        for user in ("peer", "viewer"):
            with pytest.raises(DomainError):
                reader.detail(session, user, current["event_id"], now=NOW)


@pytest.mark.parametrize("action", ["review", "mute", "pause", "pause_today", "archive", "new_revision", "handled_signal"])
def test_handled_or_inapplicable_events_leave_today_but_keep_history(db, action):
    row, grants, settings = scenario(db)
    refresh(db, row, settings)
    capture(db, grants[TRIPS], trip_feed(cancelled=True, second=1), second=1)
    refresh(db, row, settings, second=1)
    item, = page(db, settings, second=1)["items"]
    with db.session() as session:
        event = session.get(CommuteDevelopment, item["event_id"])
        if action in ("review", "mute"):
            events.review_event(session, "owner", event.id, event.version, event.sequence, now=NOW,
                                **({"muted": True} if action == "mute" else {}))
        elif action in ("pause", "pause_today", "archive"):
            repository.command(session, "owner", row["id"], row["version"], action, now=NOW, settings=settings)
        elif action == "new_revision":
            session.get(CommuteMonitor, row["id"]).revision += 1
        else:
            # Even if a previous signal remains pending, a handled newest signal
            # must not revive it (e.g. worker cancellation versus an old digest).
            session.get(CommuteSignal, item["id"]).state = "cancelled"
        session.commit()
    assert page(db, settings, second=1)["items"] == []
    with db.session() as session:
        result = reader.detail(session, "owner", item["event_id"], now=NOW, sequence=1)
        assert result["snapshot"]["sequence"] == 1
        assert result["current_configuration"] == (action != "new_revision")


def test_missing_and_stale_cancellation_is_last_known_not_urgent(db):
    row, grants, settings = scenario(db)
    capture(db, grants[TRIPS], trip_feed(cancelled=True, second=1), second=1)
    refresh(db, row, settings, second=1)
    assert page(db, settings, second=1)["items"][0]["priority"] == "urgent"
    capture(db, grants[TRIPS], feed(second=2), second=2)
    refresh(db, row, settings, second=2)
    for second, availability in ((2, "missing"), (300, "stale")):
        item, = page(db, settings, second=second)["items"]
        state, = item["states"].values()
        assert state["condition"] == "cancelled" and state["availability"] == availability
        assert item["priority"] == "normal"
    assert page(db, settings, second=49 * 3600)["items"] == []


@pytest.mark.parametrize("change", ["revoked", "expired", "corrupt"])
def test_rights_and_evidence_are_checked_at_every_read(db, change):
    row, grants, settings = scenario(db)
    refresh(db, row, settings)
    item, = page(db, settings)["items"]
    with db.session() as session:
        if change == "corrupt":
            version = session.scalar(select(CommuteEventVersion))
            version.evidence_hash = "0" * 64
        else:
            grant = session.get(CommuteSourcePermission, grants[TRIPS])
            if change == "revoked":
                grant.revoked_at = NOW
            else:
                grant.valid_until = NOW
        session.commit()
    assert page(db, settings)["items"] == []
    with db.session() as session, pytest.raises(DomainError):
        reader.detail(session, "owner", item["event_id"], now=NOW)


def clone_candidate(session, event, version, signal, index, *, permitted=True):
    # Bulk history fixture; unique logical events, tied timestamps, real FK and
    # immutable evidence checks, without replaying hundreds of acquisition jobs.
    def values(row):
        return {column.name: deepcopy(getattr(row, column.name)) for column in row.__table__.columns if column.name != "id"}
    cloned = CommuteDevelopment(**{**values(event), "key": f"fixture-{index}", "entity_key": f"fixture-{index}"})
    session.add(cloned)
    session.flush()
    session.add(CommuteEventVersion(**{**values(version), "development_id": cloned.id,
        "evidence_hash": version.evidence_hash if permitted else "0" * 64}))
    next_signal = CommuteSignal(**{**values(signal), "id": str(uuid4()), "development_id": cloned.id})
    session.add(next_signal)
    return next_signal.id


def test_bounded_sparse_pagination_advances_and_never_exposes_denied_titles(db):
    row, _, settings = scenario(db)
    refresh(db, row, settings)
    with db.session() as session:
        event = session.scalar(select(CommuteDevelopment))
        version = session.scalar(select(CommuteEventVersion))
        signal = session.scalar(select(CommuteSignal))
        signal.created_at = NOW - timedelta(seconds=1)
        ids = [clone_candidate(session, event, version, signal, index, permitted=False) for index in range(101)]
        for identifier in ids:
            session.get(CommuteSignal, identifier).created_at = NOW
        session.commit()
    first = page(db, settings)
    assert first["items"] == [] and first["next_cursor"]
    last = page(db, settings, before_id=first["next_cursor"])
    assert len(last["items"]) == 1 and last["next_cursor"] is None
    with pytest.raises(DomainError, match="Today list changed"):
        page(db, settings, user="peer", before_id=first["next_cursor"])


def test_equal_timestamp_pages_have_no_duplicates_and_review_invalidates_cursor(db):
    row, _, settings = scenario(db)
    refresh(db, row, settings)
    with db.session() as session:
        event = session.scalar(select(CommuteDevelopment))
        version = session.scalar(select(CommuteEventVersion))
        signal = session.scalar(select(CommuteSignal))
        for index in range(4):
            clone_candidate(session, event, version, signal, index)
        session.commit()
    seen, cursor = [], None
    while True:
        result = page(db, settings, limit=2, before_id=cursor)
        seen.extend(item["id"] for item in result["items"])
        cursor = result["next_cursor"]
        if not cursor:
            break
    assert len(seen) == len(set(seen)) == 5 and seen == sorted(seen, reverse=True)
    with db.session() as session:
        session.get(CommuteSignal, seen[1]).state = "reviewed"
        session.commit()
    with pytest.raises(DomainError):
        page(db, settings, before_id=seen[1])


def test_outside_window_reason_is_a_candidate_not_delivery_and_disabled_is_empty(db):
    row, _, settings = scenario(db)
    refresh(db, row, settings)
    with db.session() as session:
        session.scalar(select(CommuteSignal)).delivery_kind = "digest_candidate"
        session.commit()
    assert page(db, settings)["items"][0]["reasons"] == ["unread_journey_change", "outside_window_saved"]
    settings.commute_watch_enabled = False
    assert page(db, settings)["items"] == []
