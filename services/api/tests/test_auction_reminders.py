"""Durable auction ending-soon generations, replay and fresh permission checks."""

from datetime import timedelta

import pytest
from sqlalchemy import delete, select
from test_auction_rules import NOW, profile
from test_auction_sources import accept, price
from test_auction_workflow import action, running, sync
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens import auction_reminders as reminders
from helvetic_lens import auction_sources as sources
from helvetic_lens import auction_workflow as workflow
from helvetic_lens.auction_workflow_models import AuctionReminder
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.models import OrganizationMembership

db, template = _database_fixture, _template_fixture
SETTINGS = Settings(_env_file=None, auction_watch_enabled=True)


def watches(db, hours=24):
    permission, monitor = running(db, notify={**profile().notify.model_dump(), "ending_soon_hours": hours})
    action(db, monitor, following=True)
    return permission, monitor


def stored(db):
    with db.session() as session:
        return [{"id": row.id, "state": row.state, "version": row.version,
                 "generation": row.deadline_generation, "due": row.due_at,
                 "active": row.activated_at, "check": row.check_after}
                for row in session.scalars(select(AuctionReminder).order_by(AuctionReminder.deadline_generation))]


def test_plan_due_once_replay_and_fresh_same_deadline_do_not_duplicate(db):
    permission, monitor = watches(db)
    row, = stored(db)
    assert row["state"] == "scheduled" and row["active"] is None
    assert reminders.activate_due(db, SETTINGS, now=NOW)["ready"] == 1
    ready, = stored(db)
    assert reminders.activate_due(db, SETTINGS, now=NOW) == {"ready": 0, "invalidated": 0, "deferred": 0}
    accept(db, permission, cursor=1, prices=[price(860000)])
    sync(db, monitor, now=NOW + timedelta(seconds=1))
    unchanged, = stored(db)
    assert unchanged["id"] == row["id"] and unchanged["active"] == ready["active"] and unchanged["version"] == ready["version"]
    with db.session() as session:
        assert reminders.view(session, "owner", monitor, row["id"], now=NOW + timedelta(seconds=1))["eligible"]


def test_exact_configured_window_never_activates_early_and_requires_fresh_observation(db):
    permission, monitor = watches(db, hours=2)
    assert reminders.activate_due(db, SETTINGS, now=NOW + timedelta(hours=17))["ready"] == 0
    due = NOW + timedelta(hours=18)
    assert reminders.activate_due(db, SETTINGS, now=due)["deferred"] == 1
    accept(db, permission, cursor=1, at=due + timedelta(seconds=60))
    sync(db, monitor, now=due + timedelta(seconds=60))
    assert reminders.activate_due(db, SETTINGS, now=due + timedelta(seconds=60))["ready"] == 1
    assert reminders.activate_due(db, SETTINGS, now=NOW + timedelta(hours=20))["invalidated"] == 1


def test_deadline_away_and_back_invalidates_old_epoch_and_cancellation_clears_new(db):
    permission, monitor = watches(db)
    reminders.activate_due(db, SETTINGS, now=NOW)
    old = stored(db)[0]["id"]
    accept(db, permission, cursor=1, ends_at=NOW + timedelta(hours=10))
    accept(db, permission, cursor=2, ends_at=NOW + timedelta(hours=20))
    sync(db, monitor, now=NOW + timedelta(seconds=2))
    previous, current = stored(db)
    assert previous["state"] == "invalidated" and current["generation"] == 3
    assert current["id"] != old and current["state"] == "scheduled"
    reminders.activate_due(db, SETTINGS, now=NOW + timedelta(seconds=2))
    accept(db, permission, cursor=3, status="cancelled")
    sync(db, monitor, now=NOW + timedelta(seconds=3))
    assert all(row["state"] == "invalidated" for row in stored(db))
    with db.session() as session:
        value = reminders.view(session, "owner", monitor, old, now=NOW + timedelta(seconds=3))
        assert not value["eligible"] and value["ends_at"] is None


@pytest.mark.parametrize("change", [{"ends_at": None}, {"status": "postponed"}])
def test_unknown_deadline_or_postponement_never_produces_ready_reminder(db, change):
    permission, monitor = watches(db)
    accept(db, permission, cursor=1, **change)
    sync(db, monitor, now=NOW + timedelta(seconds=1))
    assert reminders.activate_due(db, SETTINGS, now=NOW + timedelta(seconds=1))["ready"] == 0
    assert all(row["state"] == "invalidated" for row in stored(db))


def test_unfollow_and_pause_invalidate_pending_work_without_duplicating_on_resume(db):
    _, monitor = watches(db)
    first = stored(db)[0]["id"]
    action(db, monitor, following=False)
    assert stored(db)[0]["state"] == "invalidated"
    action(db, monitor, following=True)
    assert stored(db)[0]["id"] == first and stored(db)[0]["state"] == "scheduled"
    with db.session() as session:
        workflow.pause(session, "owner", monitor, 2)
        session.commit()
    assert stored(db)[0]["state"] == "invalidated"
    with db.session() as session:
        workflow.start(session, "owner", monitor, 3, now=NOW)
        workflow.refresh(session, "owner", monitor, now=NOW)
        session.commit()
    assert stored(db)[0]["id"] == first and len(stored(db)) == 1


def test_revocation_redacts_dates_and_source_but_owner_can_acknowledge(db):
    permission, monitor = watches(db)
    reminders.activate_due(db, SETTINGS, now=NOW)
    row = stored(db)[0]
    with db.session() as session:
        sources.revoke_permission(session, permission, now=NOW)
        session.commit()
        value = reminders.view(session, "owner", monitor, row["id"], now=NOW)
        assert not value["eligible"] and value["ends_at"] is None and value["due_at"] is None
        assert value["current"]["facts"] is None
        acknowledged = reminders.acknowledge(session, "owner", monitor, row["id"], expected_version=row["version"], now=NOW)
        session.commit()
        assert acknowledged["state"] == "acknowledged"


def test_acknowledgement_is_private_and_survives_refollow_while_membership_loss_invalidates(db):
    _, monitor = watches(db)
    reminders.activate_due(db, SETTINGS, now=NOW)
    row = stored(db)[0]
    with db.session() as session:
        with pytest.raises(DomainError) as denied:
            reminders.acknowledge(session, "peer", monitor, row["id"], expected_version=row["version"], now=NOW)
        assert denied.value.status == 404
        reminders.acknowledge(session, "owner", monitor, row["id"], expected_version=row["version"], now=NOW)
        session.commit()
    action(db, monitor, following=False)
    action(db, monitor, following=True)
    assert stored(db)[0]["state"] == "acknowledged"
    assert reminders.activate_due(db, SETTINGS, now=NOW)["ready"] == 0


def test_due_scheduler_rechecks_owner_membership_and_enabled_flag(db):
    _, monitor = watches(db)
    with db.session() as session:
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == "owner",
            OrganizationMembership.organization_id == "org-a"))
        session.commit()
    assert reminders.activate_due(db, SETTINGS, now=NOW)["invalidated"] == 1
    assert reminders.activate_due(object(), Settings(_env_file=None), now=NOW)["ready"] == 0


def test_private_pages_filtered_continuation_and_acknowledged_cursor(db, monkeypatch):
    permission, monitor = watches(db)
    later = NOW + timedelta(seconds=1)
    accept(db, permission, cursor=1, lot_id="another")
    sync(db, monitor, now=later)
    with db.session() as session:
        rows = workflow.list_items(session, "owner", monitor, now=later)["items"]
    for row in rows:
        if not row["following"]:
            action(db, monitor, following=True, row=row, now=later)
    reminders.activate_due(db, SETTINGS, now=later)
    with db.session() as session:
        first = reminders.page(session, "owner", now=later, limit=1)
        assert first["next_cursor"]
        second = reminders.page(session, "owner", now=later, limit=1, cursor=first["next_cursor"])
        assert len(second["items"]) == 1 and second["items"][0]["id"] != first["items"][0]["id"]
        assert not reminders.page(session, "peer", now=later)["items"]
        with pytest.raises(DomainError):
            reminders.page(session, "peer", now=later, cursor=first["next_cursor"])
        monkeypatch.setattr(reminders, "SCAN_LIMIT", 1)
        expired = reminders.page(session, "owner", now=later + timedelta(minutes=6))
        assert expired["items"] == [] and expired["next_cursor"] and expired["unavailable_count"] == 1
        assert reminders.page(session, "owner", now=later + timedelta(minutes=6), cursor=expired["next_cursor"])["next_cursor"] is None
        row = first["items"][0]
        reminders.acknowledge(session, "owner", monitor, row["id"], expected_version=row["version"], now=later)
        with pytest.raises(DomainError) as error:
            reminders.page(session, "owner", now=later, cursor=first["next_cursor"])
        assert error.value.code == "auction_reminders_changed"
    with db.organization_context("org-b"), db.session() as session:
        assert reminders.page(session, "owner", now=later)["items"] == []
