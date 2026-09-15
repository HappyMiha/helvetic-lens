"""A clean final page cannot erase unavailable evidence from an earlier page."""

from datetime import timedelta
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import select
from test_auction_sources import accept as auction_accept
from test_auction_workflow import NOW as AUCTION_NOW
from test_auction_workflow import action as auction_action
from test_auction_workflow import running as auction_running
from test_tender_repository import db as db
from test_tender_repository import template as template
from test_trademark_sources import NOW as IP_NOW
from test_trademark_sources import accept as ip_accept
from test_trademark_workflow import review as ip_review
from test_trademark_workflow import running as ip_running
from test_trademark_workflow import source_facts

from alembic import command
from helvetic_lens import auction_workflow, trademark_workflow
from helvetic_lens.auction_source_models import AuctionSourceRecordHead, AuctionSourceRecordRevision
from helvetic_lens.auction_workflow_models import AuctionDecision, AuctionSourceCursor
from helvetic_lens.db import Base
from helvetic_lens.trademark_source_models import TrademarkRegisterHead, TrademarkRegisterRevision
from helvetic_lens.trademark_workflow_models import TrademarkProjectionCursor, TrademarkReview


@pytest.mark.parametrize("domain", ["ip", "auctions"])
@pytest.mark.parametrize("legacy", [False, True])
def test_scan_retains_early_unavailable_evidence_until_a_complete_clean_rescan(db, domain, legacy):
    if domain == "ip":
        workflow, head_model, revision_model = trademark_workflow, TrademarkRegisterHead, TrademarkRegisterRevision
        permission, monitor = ip_running(db, calibrated=True)
        for index in range(50):
            ip_accept(db, permission, cursor=index + 1, facts=source_facts(official_id=f"negative-{index}", mark="Quantum"))
        now = IP_NOW + timedelta(seconds=50)
    else:
        workflow, head_model, revision_model = auction_workflow, AuctionSourceRecordHead, AuctionSourceRecordRevision
        permission, monitor = auction_running(db, brands=["BMW"])
        for index in range(50):
            auction_accept(db, permission, cursor=index + 1, lot_id=f"negative-{index}", brand="Zyxwv")
        now = AUCTION_NOW + timedelta(seconds=50)
    reader = workflow.list_candidates if domain == "ip" else workflow.list_items
    cursor_model = TrademarkProjectionCursor if domain == "ip" else AuctionSourceCursor
    decision_model = TrademarkReview if domain == "ip" else AuctionDecision
    if domain == "ip":
        ip_review(db, monitor, now=now)
    else:
        auction_action(db, monitor, now=now, decision="inspect")
    with db.session() as session:
        before = [(row["id"], row["version"]) for row in reader(session, "owner", monitor, now=now)["items"]]
        decisions = list(session.execute(select(decision_model.__table__)))
        assert len(decisions) == 1
    with db.session(include_all_organizations=True) as session:
        head = session.scalar(select(head_model).where(head_model.permission_id == permission).order_by(head_model.record_key))
        revision = session.get(revision_model, head.revision_id)
        revision_id, original = revision.id, revision.raw_payload
        revision.raw_payload = b"corrupted early-page original"
        session.commit()

    def page():
        # Each page uses a new session, as separate durable jobs do.
        with db.session() as session:
            result = workflow.refresh(session, "owner", monitor, now=now)
            session.commit()
            return result

    first = page()
    assert first["health"] == "catching_up"
    with db.session() as session:
        cursor = session.scalar(select(cursor_model).where(cursor_model.monitor_id == monitor))
        saved_after = cursor.after_key
        assert saved_after is not None and cursor.scan_unavailable_count == 1
    if legacy:
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        with db.engine.connect() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "be91628bdef1")
            command.upgrade(config, "head")
            context = MigrationContext.configure(connection, opts={"include_object":
                lambda obj, name, kind, reflected, other: kind != "table" or name in {
                    "trademark_projection_cursors", "auction_private_source_cursors"}})
            assert compare_metadata(context, Base.metadata) == []
        with db.session() as session:
            cursor = session.scalar(select(cursor_model).where(cursor_model.monitor_id == monitor))
            assert cursor.after_key == saved_after and cursor.scan_unavailable_count is None
    for _ in range(6):
        last = page()
        if last["health"] != "catching_up":
            break
    assert last["health"] == "partial", "A clean final page hid an earlier unavailable source record"
    with db.session(include_all_organizations=True) as session:
        session.get(revision_model, revision_id).raw_payload = original
        session.commit()
    for _ in range(7):
        recovered = page()
        if recovered["health"] != "catching_up":
            break
    assert recovered["health"] == "current"
    with db.session() as session:
        assert [(row["id"], row["version"]) for row in reader(session, "owner", monitor, now=now)["items"]] == before
        cursor = session.scalar(select(cursor_model).where(cursor_model.monitor_id == monitor))
        assert cursor.after_key is None and cursor.scan_unavailable_count == 0
        assert list(session.execute(select(decision_model.__table__))) == decisions
