"""Private B8 journeys against synthetic source grants and real migrated storage."""

from datetime import timedelta
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import delete, func, select
from test_auction_rules import NOW, profile
from test_auction_sources import accept, grant, price
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from alembic import command
from helvetic_lens import auction_repository as profiles
from helvetic_lens import auction_sources as sources
from helvetic_lens import auction_workflow as workflow
from helvetic_lens.auction_models import AuctionMonitor
from helvetic_lens.auction_workflow_models import (
    AuctionDecision,
    AuctionItem,
    AuctionItemEvent,
    AuctionRuntime,
)
from helvetic_lens.config import DomainError
from helvetic_lens.db import Base
from helvetic_lens.models import OrganizationMembership

db, template = _database_fixture, _template_fixture


def create(db, **changes):
    with db.session() as session:
        monitor = profiles.create_monitor(session, "owner", profile(**changes).model_dump(mode="json"), "create")
        session.commit()
    return monitor["id"]


def running(db, **changes):
    permission = grant(db, private_decisions_allowed=True)
    accept(db, permission)
    monitor = create(db, **changes)
    with db.session() as session:
        workflow.start(session, "owner", monitor, 1, now=NOW)
        workflow.refresh(session, "owner", monitor, now=NOW)
        session.commit()
    return permission, monitor


def view(db, monitor, *, now=NOW):
    with db.session() as session:
        return workflow.list_items(session, "owner", monitor, now=now)["items"][0]


def sync(db, monitor, *, now=NOW):
    with db.session() as session:
        result = workflow.refresh(session, "owner", monitor, now=now)
        session.commit()
        return result


def action(db, monitor, *, now=NOW, decision=None, following=None, row=None):
    row = row or view(db, monitor, now=now)
    with db.session() as session:
        arguments = dict(expected_version=row["version"], expected_state_hash=row.get("state_hash"), now=now)
        result = workflow.decide(session, "owner", monitor, row["id"], decision=decision, **arguments) if decision else (
            workflow.follow(session, "owner", monitor, row["id"], following=following, **arguments))
        session.commit()
        return result


def events(db):
    with db.session() as session:
        return [{"sequence": row.sequence, "codes": row.change_codes, "notify": row.notify} for row in
            session.scalars(select(AuctionItemEvent).order_by(AuctionItemEvent.sequence))]


def test_no_source_does_not_start_or_claim_complete_coverage(db):
    monitor = create(db)
    with db.session() as session:
        preview = workflow.preview(session, "owner", profile().model_dump(mode="json"), now=NOW)
        assert preview["draft_available"] and not preview["start_available"] and not preview["coverage_verified"]
        with pytest.raises(DomainError, match="unavailable"):
            workflow.start(session, "owner", monitor, 1, now=NOW)
        assert session.get(AuctionMonitor, monitor).status == "draft"
        assert session.get(AuctionRuntime, monitor) is None


def test_start_discovers_explained_match_follow_and_internal_decision(db):
    _, monitor = running(db)
    row = view(db, monitor)
    assert row["assessment"]["status"] == "match" and row["needs_review"]
    assert row["facts"]["prices"][0]["amount_minor"] == 850000
    assert not row["following"] and row["decision"] is None
    assert action(db, monitor, following=True)["following"]
    row = action(db, monitor, decision="bid")
    assert row["decision"] == "bid" and not row["needs_review"]
    assert action(db, monitor, decision="bid")["version"] == row["version"]
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(AuctionDecision)) == 2
        assert session.scalar(select(AuctionDecision).order_by(AuctionDecision.item_version.desc())).actor_user_id == "owner"
    assert events(db) == [{"sequence": 1, "codes": ["new_match"], "notify": True}]


def test_budget_crossing_between_polls_reopens_once_and_later_bids_stay_quiet(db):
    permission, monitor = running(db)
    action(db, monitor, following=True)
    action(db, monitor, decision="inspect")
    accept(db, permission, cursor=1, prices=[price(1270000)])
    accept(db, permission, cursor=2, prices=[price(1290000)])
    sync(db, monitor, now=NOW + timedelta(seconds=2))
    row = view(db, monitor, now=NOW + timedelta(seconds=2))
    assert row["needs_review"] and row["decision"] == "inspect" and row["material_sequence"] == 2
    assert row["assessment"]["status"] == "excluded"  # Followed lots persist above budget.
    assert events(db)[-1] == {"sequence": 2, "codes": ["price_above_limit"], "notify": True}
    action(db, monitor, now=NOW + timedelta(seconds=2), decision="no_bid")
    accept(db, permission, cursor=3, prices=[price(1300000)])
    sync(db, monitor, now=NOW + timedelta(seconds=3))
    assert not view(db, monitor, now=NOW + timedelta(seconds=3))["needs_review"]
    assert len(events(db)) == 2


def test_deadline_changed_away_and_back_and_cancellation_have_distinct_generations(db):
    permission, monitor = running(db)
    initial = view(db, monitor)
    end = initial["facts"]["ends_at"]
    action(db, monitor, decision="monitor")
    accept(db, permission, cursor=1, ends_at=NOW + timedelta(days=10))
    accept(db, permission, cursor=2, ends_at=end)
    sync(db, monitor, now=NOW + timedelta(seconds=2))
    row = view(db, monitor, now=NOW + timedelta(seconds=2))
    assert row["deadline_generation"] == 3 and row["needs_review"]
    accept(db, permission, cursor=3, status="cancelled")
    sync(db, monitor, now=NOW + timedelta(seconds=3))
    assert view(db, monitor, now=NOW + timedelta(seconds=3))["deadline_generation"] == 4
    assert events(db)[-1]["codes"] == ["cancelled"]


def test_source_change_between_read_and_decision_rejects_old_state(db):
    permission, monitor = running(db)
    row = view(db, monitor)
    accept(db, permission, cursor=1, prices=[price(1270000)])
    with pytest.raises(DomainError):
        action(db, monitor, now=NOW + timedelta(seconds=1), row=row, decision="bid")
    pending = view(db, monitor, now=NOW + timedelta(seconds=1))
    assert pending["state"] == "unavailable" and pending["facts"] is None and not pending["can_review"]
    sync(db, monitor, now=NOW + timedelta(seconds=1))
    with pytest.raises(DomainError):
        action(db, monitor, now=NOW + timedelta(seconds=1), row=row, decision="bid")


def test_fresh_evidence_with_same_state_does_not_invalidate_review_or_duplicate_events(db):
    permission, monitor = running(db)
    row = action(db, monitor, decision="inspect")
    accept(db, permission, cursor=1)
    sync(db, monitor, now=NOW + timedelta(seconds=1))
    fresh = view(db, monitor, now=NOW + timedelta(seconds=1))
    assert fresh["version"] == row["version"] and not fresh["needs_review"]
    assert len(events(db)) == 1 and fresh["facts"]["observed_at"] != row["facts"]["observed_at"]


def test_revocation_redacts_source_but_owner_can_stop_following(db):
    permission, monitor = running(db)
    action(db, monitor, following=True)
    with db.session() as session:
        sources.revoke_permission(session, permission, now=NOW)
        session.commit()
    row = view(db, monitor)
    assert row["following"] and row["facts"] is None and row["assessment"] is None
    with pytest.raises(DomainError):
        action(db, monitor, row=row, decision="bid")
    assert not action(db, monitor, row=row, following=False)["following"]
    assert sync(db, monitor)["health"] == "source_unavailable"
    with db.session() as session:
        with pytest.raises(DomainError):
            workflow.history(session, "owner", monitor, row["id"], now=NOW)


def test_unknown_price_is_visible_without_a_match_notification(db):
    permission = grant(db, private_decisions_allowed=True)
    accept(db, permission, prices=[])
    monitor = create(db)
    with db.session() as session:
        workflow.start(session, "owner", monitor, 1, now=NOW)
        session.commit()
    sync(db, monitor)
    row = view(db, monitor)
    assert row["assessment"]["status"] == "unknown" and row["facts"]["prices"] == []
    assert events(db)[0]["codes"] == ["candidate_unknown"] and not events(db)[0]["notify"]


def test_profile_change_reassesses_retained_lot_and_reopens_decision(db):
    _, monitor = running(db)
    action(db, monitor, decision="inspect")
    with db.session() as session:
        workflow.pause(session, "owner", monitor, 2)
        profiles.edit_monitor(session, "owner", monitor, 3, profile(maximum_price_chf_cents=800000).model_dump(mode="json"))
        workflow.start(session, "owner", monitor, 4, now=NOW)
        session.commit()
    assert view(db, monitor)["state"] == "unavailable"
    sync(db, monitor)
    row = view(db, monitor)
    assert row["needs_review"] and row["assessment"]["status"] == "excluded"
    assert events(db)[-1]["codes"] == ["profile_changed"]


def test_peer_other_organization_and_revoked_owner_cannot_see_private_tracking(db):
    _, monitor = running(db)
    item = view(db, monitor)
    with db.session() as session:
        for user in ("peer", "viewer"):
            with pytest.raises(DomainError) as denied:
                workflow.list_items(session, user, monitor, now=NOW)
            assert denied.value.status == 404
    with db.organization_context("org-b"), db.session() as session:
        with pytest.raises(DomainError):
            workflow.history(session, "owner", monitor, item["id"], now=NOW)
        assert session.scalar(select(func.count()).select_from(AuctionItem)) == 0
    with db.session() as session:
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == "owner", OrganizationMembership.organization_id == "org-a"))
        session.commit()
        with pytest.raises(DomainError) as denied:
            workflow.list_items(session, "owner", monitor, now=NOW)
        assert denied.value.status == 403


def test_partial_source_paging_continues_without_losing_or_cancelling_items(db, monkeypatch):
    permission, monitor = running(db)
    accept(db, permission, cursor=1, lot_id="other-lot")
    monkeypatch.setattr(workflow, "PAGE_SIZE", 1)
    for _ in range(3):
        sync(db, monitor, now=NOW + timedelta(seconds=1))
    with db.session() as session:
        page = workflow.list_items(session, "owner", monitor, now=NOW + timedelta(seconds=1), limit=1)
        assert page["next_cursor"] and not page["coverage_verified"]
        later = workflow.list_items(session, "owner", monitor, now=NOW + timedelta(seconds=1), limit=1, after=page["next_cursor"])
        assert len(later["items"]) == 1 and later["items"][0]["id"] != page["items"][0]["id"]
        assert all(v["facts"]["status"] == "open" for v in page["items"] + later["items"])


def test_history_retains_quiet_bids_and_purges_do_not_leave_private_payload_copies(db):
    permission, monitor = running(db)
    accept(db, permission, cursor=1, prices=[price(860000)])
    sync(db, monitor, now=NOW + timedelta(seconds=1))
    row = view(db, monitor, now=NOW + timedelta(seconds=1))
    with db.session() as session:
        history = workflow.history(session, "owner", monitor, row["id"], now=NOW + timedelta(seconds=1))
        assert [v["facts"]["prices"][0]["amount_minor"] for v in history["items"]] == [860000, 850000]
        assert session.get(AuctionItem, row["id"]).material_sequence == 1
        sources.purge_content(session, now=NOW + timedelta(hours=2))
        session.commit()
        history = workflow.history(session, "owner", monitor, row["id"], now=NOW + timedelta(hours=2))
        assert all(v["state"] == "unavailable" and "facts" not in v for v in history["items"])


def test_private_workflow_migration_matches_metadata_and_preserves_profiles(db):
    _, monitor = running(db)
    with db.engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"include_object":
            lambda obj, name, kind, reflected, compare_to: name.startswith("auction_") if kind == "table" else True})
        assert compare_metadata(context, Base.metadata) == []
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "70bd3e81fe72")
        assert connection.execute(select(AuctionMonitor.id).where(AuctionMonitor.id == monitor)).scalar() == monitor
        command.upgrade(config, "head")
        assert compare_metadata(context, Base.metadata) == []


def test_scheduler_is_due_bounded_replay_safe_and_pauses_revoked_owner(db, monkeypatch):
    from helvetic_lens import auction_jobs, celery_app
    from helvetic_lens.config import Settings

    permission = grant(db, private_decisions_allowed=True)
    accept(db, permission)
    monitor = create(db)
    config = Settings(_env_file=None, auction_watch_enabled=True)
    with db.session() as session:
        workflow.start(session, "owner", monitor, 1, now=NOW)
        session.commit()
    assert auction_jobs.refresh_due(db, config, now=NOW) == {"refreshed": 1, "unavailable": 0}
    assert auction_jobs.refresh_due(db, config, now=NOW) == {"refreshed": 0, "unavailable": 0}
    assert len(events(db)) == 1
    with db.session() as session:
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == "owner", OrganizationMembership.organization_id == "org-a"))
        session.commit()
    assert auction_jobs.refresh_due(db, config, now=NOW + timedelta(seconds=60)) == {"refreshed": 0, "unavailable": 1}
    with db.session() as session:
        assert session.get(AuctionMonitor, monitor).status == "paused"
        runtime = session.get(AuctionRuntime, monitor)
        assert runtime.health == "access_unavailable" and runtime.next_check_at is None
    assert celery_app.celery_app.conf.beat_schedule["schedule-auction-monitoring"]["schedule"] == 15.0
    config.auction_watch_enabled = False
    assert auction_jobs.refresh_due(object(), config, now=NOW) == {"refreshed": 0, "unavailable": 0}
