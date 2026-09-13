"""Private auction feed, retained comparisons and stale-cursor boundaries."""

from datetime import timedelta

import pytest
from sqlalchemy import delete, func, select
from test_auction_rules import NOW, profile
from test_auction_sources import accept, price
from test_auction_workflow import action, running, sync
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens import auction_repository as profiles
from helvetic_lens import auction_sources as sources
from helvetic_lens import auction_today as feed
from helvetic_lens import auction_workflow as workflow
from helvetic_lens.auction_workflow_models import AuctionDecision, AuctionItemEvent
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.models import OrganizationMembership

db, template = _database_fixture, _template_fixture
SETTINGS = Settings(_env_file=None, auction_watch_enabled=True)


def page(db, *, user="owner", **args):
    with db.session() as session:
        return feed.page(session, SETTINGS, user, now=args.pop("now", NOW), **args)


def detail(db, monitor, event, *, now=NOW, user="owner"):
    with db.session() as session:
        return feed.detail(session, user, monitor, event, now=now)


def test_new_match_today_inbox_exact_lot_and_reads_do_not_review(db):
    _, monitor = running(db)
    first = page(db)
    assert len(first["items"]) == 1 and first["has_active_monitors"] and not first["coverage_verified"]
    event = first["items"][0]
    assert event["change_codes"] == ["new_match"] and event["title"]
    assert event["href"] == f"/auction-watch?monitor={monitor}&event={event['id']}"
    assert page(db, inbox=True)["items"] == first["items"]
    exact = detail(db, monitor, event["id"])
    assert exact["previous"] is None and exact["snapshot"]["facts"]["prices"][0]["amount_minor"] == 850000
    assert exact["current"]["needs_review"]
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(AuctionDecision)) == 0
    action(db, monitor, decision="inspect")
    assert not page(db)["items"] and not page(db, inbox=True)["items"]
    assert not detail(db, monitor, event["id"])["current"]["needs_review"]


def test_price_crossing_keeps_exact_before_after_and_quiet_bids_do_not_replace_event(db):
    permission, monitor = running(db)
    original = page(db)["items"][0]
    action(db, monitor, following=True)
    action(db, monitor, decision="bid")
    accept(db, permission, cursor=1, prices=[price(1270000)])
    sync(db, monitor, now=NOW + timedelta(seconds=1))
    event = page(db, now=NOW + timedelta(seconds=1))["items"][0]
    accept(db, permission, cursor=2, prices=[price(1290000)])
    sync(db, monitor, now=NOW + timedelta(seconds=2))
    later = page(db, now=NOW + timedelta(seconds=2))["items"][0]
    assert later["id"] == event["id"] and later["detected_at"] == event["detected_at"]
    exact = detail(db, monitor, event["id"], now=NOW + timedelta(seconds=2))
    assert exact["change_codes"] == ["price_above_limit"]
    assert [exact[k]["facts"]["prices"][0]["amount_minor"] for k in ("previous", "snapshot", "current")] == [850000, 1270000, 1290000]
    assert detail(db, monitor, original["id"], now=NOW + timedelta(seconds=2))["newer_available"]
    action(db, monitor, following=False, now=NOW + timedelta(seconds=2))
    assert not page(db, now=NOW + timedelta(seconds=2))["items"]


def test_stale_revoked_and_expired_evidence_never_leaks_into_feed(db):
    permission, monitor = running(db)
    event = page(db)["items"][0]
    stale = page(db, now=NOW + timedelta(seconds=301))
    assert stale["items"] == [] and stale["unavailable_count"] == 1
    with db.session() as session:
        sources.revoke_permission(session, permission, now=NOW)
        session.commit()
    assert not page(db)["items"]
    exact = detail(db, monitor, event["id"])
    assert exact["snapshot"]["facts"] is None and exact["current"]["facts"] is None
    assert not exact["current"]["can_review"]


def test_unrequested_later_change_cannot_silently_dismiss_unread_budget_alert(db):
    notifications = profile().notify.model_dump()
    permission, monitor = running(db, notify={**notifications, "deadline_change": False})
    action(db, monitor, following=True)
    action(db, monitor, decision="inspect")
    accept(db, permission, cursor=1, prices=[price(1270000)])
    sync(db, monitor, now=NOW + timedelta(seconds=1))
    event = page(db, now=NOW + timedelta(seconds=1))["items"][0]
    accept(db, permission, cursor=2, prices=[price(1270000)], ends_at=NOW + timedelta(days=10))
    sync(db, monitor, now=NOW + timedelta(seconds=2))
    retained = page(db, now=NOW + timedelta(seconds=2))["items"][0]
    assert retained["id"] == event["id"] and retained["change_codes"] == ["price_above_limit"]
    assert detail(db, monitor, event["id"], now=NOW + timedelta(seconds=2))["newer_available"]


def test_today_cutoff_does_not_reset_with_fresh_identical_observation(db):
    permission, monitor = running(db)
    with db.session() as session:
        event = session.scalar(select(AuctionItemEvent))
        event.created_at = NOW - timedelta(days=3)
        session.commit()
    accept(db, permission, cursor=1)
    sync(db, monitor, now=NOW + timedelta(seconds=1))
    assert page(db, now=NOW + timedelta(seconds=1))["items"] == []
    assert len(page(db, now=NOW + timedelta(seconds=1), inbox=True)["items"]) == 1
    with db.session() as session:
        workflow.pause(session, "owner", monitor, 2)
        session.commit()
    assert not page(db, inbox=True)["has_active_monitors"]


def test_scope_revocation_and_foreign_cursors_do_not_reveal_other_private_lots(db):
    _, monitor = running(db)
    event = page(db)["items"][0]
    assert page(db, user="peer")["items"] == []
    with pytest.raises(DomainError) as error:
        detail(db, monitor, event["id"], user="peer")
    assert error.value.status == 404
    with db.session() as session:
        other = profiles.create_monitor(session, "owner", profile(name="Other private monitor").model_dump(mode="json"), "other")["id"]
        session.commit()
    with pytest.raises(DomainError):
        detail(db, other, event["id"])
    with pytest.raises(DomainError) as error:
        page(db, user="peer", cursor=event["id"])
    assert error.value.code == "auction_today_changed"
    with db.organization_context("org-b"):
        assert page(db)["items"] == []
    with db.session() as session:
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == "owner",
            OrganizationMembership.organization_id == "org-a"))
        session.commit()
    with pytest.raises(DomainError):
        page(db)


def test_bounded_filtered_pages_continue_and_review_invalidates_cursor(db, monkeypatch):
    permission, monitor = running(db)
    accept(db, permission, cursor=1, lot_id="another")
    sync(db, monitor, now=NOW + timedelta(seconds=1))
    first = page(db, limit=1, now=NOW + timedelta(seconds=1))
    assert first["next_cursor"]
    second = page(db, limit=1, cursor=first["next_cursor"], now=NOW + timedelta(seconds=1))
    assert len(second["items"]) == 1 and second["items"][0]["id"] != first["items"][0]["id"]
    monkeypatch.setattr(feed, "SCAN_LIMIT", 1)
    stale = page(db, now=NOW + timedelta(seconds=302))
    assert not stale["items"] and stale["next_cursor"]
    assert not page(db, cursor=stale["next_cursor"], now=NOW + timedelta(seconds=302))["next_cursor"]
    with db.session() as session:
        row = next(v for v in workflow.list_items(session, "owner", monitor, now=NOW + timedelta(seconds=1))["items"]
                   if v["id"] == first["items"][0]["item_id"])
    action(db, monitor, decision="inspect", row=row, now=NOW + timedelta(seconds=1))
    with pytest.raises(DomainError) as error:
        page(db, cursor=first["next_cursor"], now=NOW + timedelta(seconds=1))
    assert error.value.code == "auction_today_changed"


def test_previous_profile_revision_is_preserved_and_feature_disable_never_reads_source(db, monkeypatch):
    _, monitor = running(db)
    event = page(db)["items"][0]
    with db.session() as session:
        workflow.pause(session, "owner", monitor, 2)
        config = profiles.get_monitor(session, "owner", monitor)["configuration"]
        profiles.edit_monitor(session, "owner", monitor, 3, {**config, "maximum_price_chf_cents": 800000})
        session.commit()
    exact = detail(db, monitor, event["id"])
    assert exact["profile_revision"] == 1 and not exact["current_configuration"]
    assert exact["current"]["facts"] is None
    monkeypatch.setattr(feed, "item_view", lambda *a, **k: pytest.fail("Disabled feature read private source data"))
    with db.session() as session:
        assert feed.page(session, Settings(_env_file=None), "owner", now=NOW)["items"] == []
