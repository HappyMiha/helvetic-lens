"""Synthetic private Today/Inbox integration against real stored CAP evidence."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select, update
from test_hazard_cap import NOW, info, message
from test_hazard_events import active_fixture, project, review, setup
from test_hazard_events import db as db
from test_hazard_events import store as store
from test_hazard_events import template as template
from test_hazard_sources import accept, revised

from helvetic_lens import hazard_events as events
from helvetic_lens import hazard_sources as sources
from helvetic_lens import hazard_today as feed
from helvetic_lens.config import DomainError
from helvetic_lens.hazard_models import HazardEventRevision, HazardMonitor
from helvetic_lens.models import OrganizationMembership


def page(db, store, *, actor="owner", second=0, enabled=True, **kwargs):
    with db.session() as session:
        return feed.page(session, SimpleNamespace(hazard_watch_enabled=enabled), actor,
                         store=store, now=NOW + timedelta(seconds=second), **kwargs)


def test_current_warning_is_private_exact_link_without_full_text_coordinates_or_side_effects(db, store):
    monitor, _, _, development = setup(db, store)
    result = page(db, store)
    assert result["has_active_places"] and not result["coverage_verified"]
    item, = result["items"]
    assert item["href"] == f"/hazard-watch?monitor={monitor}&event={development}&revision=1"
    assert item["name"] == "Home" and item["importance"] == "warning"
    assert item["last_seen_at"] == NOW.isoformat() and item["attribution"] == "Fixture authority"
    assert "latitude" not in str(item) and "Stay indoors" not in str(item) and "source_hash" not in str(item)
    assert page(db, store, inbox=True)["items"] == [item]
    assert page(db, store)["items"] == [item]  # Reading never reviews.
    assert page(db, store, actor="peer")["items"] == []
    assert page(db, store, enabled=False)["items"] == []
    with db.organization_context("org-b"):
        assert page(db, store)["items"] == []


@pytest.mark.parametrize("action", ["reviewed", "not_relevant"])
def test_review_and_dismiss_hide_then_new_instructions_reopen(db, store, action):
    monitor, permission, _, development = setup(db, store)
    review(db, monitor, development, store, 1, action=action)
    assert not page(db, store)["items"]
    translation = accept(db, permission, revised(infos=info() + info(language="fr-CH", instruction="Restez.")), second=1, cursor=1)
    project(db, monitor, permission, translation, store, second=1)
    assert not page(db, store, second=1, inbox=True)["items"]
    instructions = accept(db, permission, revised(identifier="third", previous="second",
        previous_sent="2026-09-13T09:30:00+00:00", sent="2026-09-13T09:40:00+00:00", infos=info(instruction="Evacuate.")), second=2, cursor=2)
    project(db, monitor, permission, instructions, store, second=2)
    item, = page(db, store, second=2, inbox=True)["items"]
    assert item["revision"] == 3 and item["detected_at"] == (NOW + timedelta(seconds=2)).isoformat()


def test_translation_does_not_refresh_material_window_but_active_inbox_has_no_48_hour_cutoff(db, store):
    monitor, permission, _, development = setup(db, store)
    with db.session() as session:
        session.execute(update(HazardEventRevision).where(HazardEventRevision.development_id == development)
                        .values(created_at=NOW - timedelta(days=3)))
        session.commit()
    translation = accept(db, permission, revised(infos=info() + info(language="fr-CH", instruction="Restez.")), second=1, cursor=1)
    project(db, monitor, permission, translation, store, second=1)
    assert page(db, store, second=1)["items"] == []
    item, = page(db, store, second=1, inbox=True)["items"]
    assert item["revision"] == 2 and item["detected_at"] == (NOW - timedelta(days=3)).isoformat()


def test_mute_suppresses_without_marking_reviewed_and_unmute_restores(db, store):
    monitor, _, _, development = setup(db, store)
    with db.session() as session:
        events.set_mute(session, "owner", monitor, "storm", version=2, muted=True, now=NOW)
        session.commit()
    assert not page(db, store, inbox=True)["items"]
    with db.session() as session:
        events.set_mute(session, "owner", monitor, "storm", version=3, muted=False, now=NOW)
        session.commit()
    assert page(db, store)["items"][0]["event_id"] == development


@pytest.mark.parametrize("cause", ["rights", "geography", "stale", "new_source"])
def test_unavailable_current_evidence_cannot_enter_summary_or_claim_allclear(db, store, cause):
    _, permission, _, _ = setup(db, store)
    if cause == "rights":
        with db.session() as session:
            sources.revoke_permission(session, permission, now=NOW)
            session.commit()
    elif cause == "geography":
        store.available = False
    elif cause == "new_source":
        accept(db, permission, revised(), second=1, cursor=1)
    result = page(db, store, second=301 if cause == "stale" else 1, inbox=True)
    assert result["items"] == [] and result["unavailable_count"] == 1
    assert result["coverage_verified"] is False


@pytest.mark.parametrize("kind", ["cancelled", "resolved", "outside"])
def test_closing_or_irrelevant_update_stays_in_today_but_leaves_active_inbox(db, store, kind):
    monitor, permission, _, _ = setup(db, store)
    xml = revised(kind="Cancel", infos="") if kind == "cancelled" else revised(infos=(
        info(level="Minor", extra="<responseType>AllClear</responseType>") if kind == "resolved"
        else info(geometry="<circle>46.5,6.5 1</circle>")))
    changed = accept(db, permission, xml, second=1, cursor=1)
    project(db, monitor, permission, changed, store, second=1)
    assert not page(db, store, second=1, inbox=True)["items"]
    assert page(db, store, second=1)["items"][0]["state"] == ("not_relevant" if kind == "outside" else kind)


def test_owner_cursors_page_without_duplicates_and_invalidate_after_review(db, store):
    monitor, permission, receipt, first = setup(db, store)
    other = active_fixture(db, key="office")
    second = project(db, other, permission, receipt, store)["development_id"]
    one = page(db, store, limit=1)
    two = page(db, store, limit=1, cursor=one["next_cursor"])
    assert {one["items"][0]["event_id"], two["items"][0]["event_id"]} == {first, second}
    assert two["next_cursor"] is None
    with pytest.raises(DomainError, match="list changed"):
        page(db, store, actor="peer", cursor=one["next_cursor"])
    item = one["items"][0]
    review(db, item["monitor_id"], item["event_id"], store, 1)
    with pytest.raises(DomainError, match="list changed"):
        page(db, store, cursor=one["next_cursor"])


def test_bounded_empty_page_keeps_continuation_after_unavailable_candidates(db, store, monkeypatch):
    monitor, permission, _, _ = setup(db, store)
    for index in range(2):
        receipt = accept(db, permission, message(identifier=f"extra-{index}"), cursor=index + 1)
        project(db, monitor, permission, receipt, store)
    monkeypatch.setattr(feed, "SCAN_LIMIT", 2)
    store.available = False
    first = page(db, store)
    assert first["items"] == [] and first["next_cursor"] and first["unavailable_count"] == 2
    second = page(db, store, cursor=first["next_cursor"])
    assert second["items"] == [] and second["next_cursor"] is None and second["unavailable_count"] == 1


def test_inactive_changed_config_and_revoked_membership_hide_old_events(db, store):
    monitor, _, _, _ = setup(db, store)
    with db.session() as session:
        row = session.get(HazardMonitor, monitor)
        row.status = "paused"
        session.commit()
    assert not page(db, store)["items"]
    with db.session() as session:
        row = session.get(HazardMonitor, monitor)
        row.status, row.revision = "active", 2
        session.commit()
    assert not page(db, store)["items"]
    with db.session() as session:
        member = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == "owner"))
        member.role = "revoked"
        session.commit()
    with pytest.raises(DomainError) as denied:
        page(db, store)
    assert denied.value.status == 403


def test_revision_arriving_during_page_cannot_mix_new_instructions_with_old_cursor(db, store, monkeypatch):
    monitor, permission, _, _ = setup(db, store)
    original = feed.read_event
    def intervening(session, *args, **kwargs):
        receipt = accept(db, permission, revised(infos=info(instruction="Evacuate.")), cursor=1)
        project(db, monitor, permission, receipt, store)
        return original(session, *args, **kwargs)
    monkeypatch.setattr(feed, "read_event", intervening)
    assert page(db, store)["items"] == []
    monkeypatch.setattr(feed, "read_event", original)
    assert page(db, store)["items"][0]["revision"] == 2
