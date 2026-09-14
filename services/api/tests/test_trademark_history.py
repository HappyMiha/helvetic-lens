from datetime import timedelta

import pytest
from sqlalchemy import delete, select
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture
from test_trademark_sources import NOW, accept
from test_trademark_workflow import review, rows, running, source_facts, sync

from helvetic_lens import trademark_history as history
from helvetic_lens import trademark_jobs as jobs
from helvetic_lens import trademark_sources as sources
from helvetic_lens import trademark_today as feed
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.models import OrganizationMembership
from helvetic_lens.trademark_models import TrademarkMonitor

db, template = _database_fixture, _template_fixture
SETTINGS = Settings(_env_file=None, trademark_watch_enabled=True)


def page(db, **kwargs):
    with db.session() as session:
        return feed.page(session, SETTINGS, kwargs.pop("user", "owner"), now=kwargs.pop("now", NOW), **kwargs)


def test_feed_to_exact_evidence_and_immutable_review_history(db):
    permission, monitor = running(db)
    first, = page(db)["items"]
    assert first["priority"] == "high" and "candidate=" in first["href"]
    row = review(db, monitor)
    assert not page(db, inbox=True)["items"]
    accept(db, permission, cursor=1, facts=source_facts(owners=["New Holder SA"]))
    later = NOW + timedelta(seconds=1)
    sync(db, monitor, later)
    changed, = page(db, inbox=True, now=later)["items"]
    assert changed["id"] != first["id"] and "changed_owners" in changed["change_codes"]
    with db.session() as session:
        value = history.event_detail(session, "owner", monitor, row["id"], changed["id"], now=later)
        assert value["previous"]["facts"]["owners"] == ["Synthetic Owner AG"]
        assert value["snapshot"]["facts"]["owners"] == ["New Holder SA"]
        assert value["assessment"]["classification"] == "candidate_for_ip_review"
        assert value["current"]["decision"] == "relevant" and not value["legal_conflict_confirmed"]
        prior = history.event_detail(session, "owner", monitor, row["id"], first["id"], now=later)
        assert prior["newer_available"] and prior["snapshot"]["facts"]["owners"] == ["Synthetic Owner AG"]
        versions = history.history(session, "owner", monitor, row["id"], now=later, limit=1)
        assert versions["next_cursor"] == 2
        assert len(history.history(session, "owner", monitor, row["id"], now=later, before=2)["items"]) == 1
        audit, = history.reviews(session, "owner", monitor, row["id"])["items"]
        assert audit["decision"] == "relevant" and audit["sequence"] == 1
        sources.revoke_permission(session, permission, now=later)
        session.commit()
        hidden = history.event_detail(session, "owner", monitor, row["id"], changed["id"], now=later)
        assert hidden["assessment"] is None and hidden["previous"]["facts"] is None and hidden["snapshot"]["facts"] is None
        assert hidden["current"]["facts"] is None
    assert not page(db, now=later)["items"]


def test_bounded_filtered_feed_and_private_changed_cursors(db, monkeypatch):
    permission, monitor = running(db)
    accept(db, permission, cursor=1, facts=source_facts(official_id="second-mark"))
    later = NOW + timedelta(seconds=1)
    sync(db, monitor, later)
    first = page(db, now=later, limit=1)
    assert first["next_cursor"]
    second = page(db, now=later, limit=1, cursor=first["next_cursor"])
    assert len(second["items"]) == 1 and first["items"][0]["id"] != second["items"][0]["id"]
    monkeypatch.setattr(feed, "SCAN_LIMIT", 1)
    stale = page(db, now=later + timedelta(minutes=6))
    assert not stale["items"] and stale["next_cursor"]
    assert not page(db, now=later + timedelta(minutes=6), cursor=stale["next_cursor"])["next_cursor"]
    assert not page(db, user="peer")["items"]
    with pytest.raises(DomainError):
        page(db, user="peer", now=later, cursor=first["next_cursor"])
    row = next(v for v in rows(db, monitor, later) if v["id"] == first["items"][0]["candidate_id"])
    review(db, monitor, row=row, now=later)
    with pytest.raises(DomainError):
        page(db, now=later, cursor=first["next_cursor"])


def test_scheduler_projects_due_once_and_pauses_when_membership_is_removed(db):
    permission, monitor = running(db)
    later = NOW + timedelta(seconds=61)
    accept(db, permission, cursor=1, second=61, facts=source_facts(status="cancelled"))
    assert jobs.refresh_due(db, SETTINGS, now=later) == {"refreshed": 1, "unavailable": 0}
    assert jobs.refresh_due(db, SETTINGS, now=later) == {"refreshed": 0, "unavailable": 0}
    assert rows(db, monitor, later)[0]["sequence"] == 2
    with db.session() as session:
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == "owner",
            OrganizationMembership.organization_id == "org-a"))
        session.commit()
    assert jobs.refresh_due(db, SETTINGS, now=later + timedelta(seconds=60))["unavailable"] == 1
    with db.session(include_all_organizations=True) as session:
        assert session.scalar(select(TrademarkMonitor).where(TrademarkMonitor.id == monitor)).status == "paused"
    assert jobs.refresh_due(object(), Settings(_env_file=None), now=NOW)["refreshed"] == 0
