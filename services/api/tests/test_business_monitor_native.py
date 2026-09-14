"""Shared business evidence retains native source and decision boundaries."""

from datetime import timedelta

import pytest
from sqlalchemy import select, update
from test_business_monitor_sharing import configure
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens.config import DomainError, Settings
from helvetic_lens.models import User


@pytest.mark.parametrize("domain", ("ip", "auctions"))
def test_responsible_colleague_runs_reviews_source_gates_and_old_links_without_creator(db, domain):
    if domain == "ip":
        from test_trademark_sources import NOW
        from test_trademark_workflow import running

        from helvetic_lens import trademark_jobs as jobs
        from helvetic_lens import trademark_repository as repository
        from helvetic_lens import trademark_sources as sources
        from helvetic_lens import trademark_today as today
        from helvetic_lens import trademark_workflow as workflow
        from helvetic_lens.trademark_workflow_models import TrademarkReview as Decision
        from helvetic_lens.trademark_workflow_models import TrademarkRuntime as Runtime
        listing = workflow.list_candidates
    else:
        from test_auction_rules import NOW
        from test_auction_workflow import running

        from helvetic_lens import auction_jobs as jobs
        from helvetic_lens import auction_repository as repository
        from helvetic_lens import auction_sources as sources
        from helvetic_lens import auction_today as today
        from helvetic_lens import auction_workflow as workflow
        from helvetic_lens.auction_workflow_models import AuctionDecision as Decision
        from helvetic_lens.auction_workflow_models import AuctionRuntime as Runtime
        listing = workflow.list_items
    permission, monitor = running(db)
    with db.session() as session:
        version = repository.get_monitor(session, "owner", monitor)["version"]
    shared = configure(db, domain, monitor, version=version, now=NOW)
    assert shared["status"] == "paused"
    with db.session() as session:
        for actor in ("peer", "viewer"):
            assert listing(session, actor, monitor, now=NOW)["items"]
        workflow.start(session, "peer", monitor, shared["monitor_version"], now=NOW)
        session.get(User, "owner").active = False
        session.get(Runtime, monitor).next_check_at = NOW
        session.commit()
    settings = Settings(_env_file=None, trademark_watch_enabled=True, auction_watch_enabled=True)
    assert jobs.refresh_due(db, settings, now=NOW)["refreshed"] == 1
    with db.session() as session:
        candidate = listing(session, "peer", monitor, now=NOW)["items"][0]
        if domain == "ip":
            args = {"expected_version": candidate["version"], "expected_evaluation_hash": candidate["evaluation_hash"], "decision": "relevant", "now": NOW}
            decision = workflow.review
        else:
            args = {"expected_version": candidate["version"], "expected_state_hash": candidate["state_hash"], "decision": "inspect", "now": NOW}
            decision = workflow.decide
        with pytest.raises(DomainError):
            decision(session, "viewer", monitor, candidate["id"], **args)
        result = decision(session, "peer", monitor, candidate["id"], **args)
        assert result["decision"] == args["decision"]
        assert session.scalars(select(Decision.actor_user_id)).all() == ["peer"]
        session.commit()
    with db.session() as session:
        sources.revoke_permission(session, permission, now=NOW)
        session.commit()
    with db.session() as session:
        unreadable = listing(session, "peer", monitor, now=NOW)["items"][0]
        assert unreadable["state"] != "available"
        assert unreadable.get("facts") is None
        with pytest.raises(DomainError):
            decision(session, "peer", monitor, candidate["id"], **{**args, "expected_version": result["version"]})
        # Keep evidence/history, but stop collection when its responsible account disappears.
        session.get(User, "peer").active = False
        session.get(Runtime, monitor).next_check_at = NOW + timedelta(seconds=1)
        session.commit()
    assert jobs.refresh_due(db, settings, now=NOW + timedelta(seconds=1))["unavailable"] == 1
    with db.session() as session:
        session.execute(update(User).where(User.id.in_(("owner", "peer"))).values(active=True))
        session.commit()
    with db.session() as session:
        current = repository.get_monitor(session, "owner", monitor)
        assert current["status"] == "paused"
        assert current["runtime"]["health"] == "access_unavailable"
        version = current["version"]
    configure(db, domain, monitor, version=version, scope="private", responsible=None, now=NOW)
    with db.session() as session:
        with pytest.raises(DomainError):
            listing(session, "peer", monitor, now=NOW)
        assert today.page(session, settings, "peer", now=NOW)["items"] == []


def test_shared_tender_collector_uses_responsible_member_and_retains_unresolved_work(db):
    from test_tender_jobs import Source, cycle, settings
    from test_tender_matching import NOW
    from test_tender_repository import create

    from helvetic_lens import tender_lifecycle, tender_repository
    from helvetic_lens.tender_today import today

    monitor = create(db, active=True)
    shared = configure(db, "tenders", monitor["id"], now=NOW)
    with db.session() as session:
        resumed = tender_lifecycle.command(session, settings(), "peer", monitor["id"], shared["monitor_version"], "resume", now=NOW)
        session.get(User, "owner").active = False
        session.commit()
    source = Source()
    cycle(db, resumed, source)
    with db.session() as session:
        records = today(session, "peer", now=NOW + timedelta(minutes=5))["items"]
        assert len(records) == 1 and records[0]["review_state"] == "new"
        version = tender_repository.get_monitor(session, "peer", monitor["id"])["version"]
    configure(db, "tenders", monitor["id"], actor="peer", version=version, responsible=None, now=NOW)
    with db.session() as session:
        paused = tender_repository.get_monitor(session, "peer", monitor["id"])
        assert paused["status"] == "paused"
        with pytest.raises(DomainError):
            tender_lifecycle.command(session, settings(), "peer", monitor["id"], paused["version"], "resume", now=NOW)
        assert len(tender_repository.list_dossiers(session, "viewer", monitor["id"], now=NOW + timedelta(minutes=5))["items"]) == 1


def test_shared_export_uses_current_reader_even_after_creator_deactivation(db):
    from test_trademark_exports import setup
    from test_trademark_sources import NOW

    from helvetic_lens import trademark_exports as exports
    from helvetic_lens import trademark_sources as sources
    from helvetic_lens import trademark_workflow as workflow
    from helvetic_lens.trademark_workflow_models import TrademarkCandidateEvent

    permission, monitor = setup(db)
    configure(db, "ip", monitor, version=2, now=NOW)
    with db.session() as session:
        session.get(User, "owner").active = False
        session.commit()
    with db.session() as session:
        candidate = workflow.list_candidates(session, "peer", monitor, now=NOW)["items"][0]
        event = session.scalar(select(TrademarkCandidateEvent).where(TrademarkCandidateEvent.candidate_id == candidate["id"]))
        packet = exports.prepare(session, "peer", monitor, candidate["id"], expected_version=candidate["version"],
            expected_evaluation_hash=candidate["evaluation_hash"], request_key="shared-export", event_id=event.id, now=NOW)
        session.commit()
    with db.session() as session:
        assert exports.read(session, "peer", monitor, candidate["id"], packet["id"], now=NOW)["content_sha256"] == packet["content_sha256"]
        sources.revoke_permission(session, permission, now=NOW)
        session.commit()
    with db.session() as session, pytest.raises(DomainError):
        exports.read(session, "peer", monitor, candidate["id"], packet["id"], now=NOW)
