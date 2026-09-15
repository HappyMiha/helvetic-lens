"""Business source paging stays bounded while native private history survives."""

from datetime import timedelta

import pytest
from sqlalchemy import event, select
from test_auction_sources import accept as auction_accept
from test_auction_sources import price
from test_auction_workflow import NOW as AUCTION_NOW
from test_auction_workflow import running as auction_running
from test_tender_repository import db as db
from test_tender_repository import template as template
from test_trademark_sources import NOW as IP_NOW
from test_trademark_sources import accept as ip_accept
from test_trademark_workflow import running as ip_running
from test_trademark_workflow import source_facts

from helvetic_lens import auction_sources, auction_workflow, trademark_sources, trademark_workflow
from helvetic_lens.auction_source_models import AuctionSourceRecordHead, AuctionSourceRecordRevision
from helvetic_lens.config import DomainError
from helvetic_lens.trademark_source_models import TrademarkRegisterHead, TrademarkRegisterRevision


@pytest.mark.parametrize("domain", ["ip", "auctions"])
def test_streamed_source_pages_keep_hash_permission_and_native_projection_checks(db, domain):
    database = db
    if domain == "ip":
        source, workflow, head_model, revision_model = trademark_sources, trademark_workflow, TrademarkRegisterHead, TrademarkRegisterRevision
        permission, monitor = ip_running(db, calibrated=True)
        ip_accept(db, permission, cursor=1, facts=source_facts(owners=["Updated owner AG"]))
        for index in range(50):
            ip_accept(db, permission, cursor=index + 2, facts=source_facts(official_id=f"negative-{index}", mark="Quantum"))
        now = IP_NOW + timedelta(seconds=51)
    else:
        source, workflow, head_model, revision_model = auction_sources, auction_workflow, AuctionSourceRecordHead, AuctionSourceRecordRevision
        permission, monitor = auction_running(db, brands=["BMW"])
        auction_accept(db, permission, cursor=1, prices=[price(900000)])
        for index in range(50):
            auction_accept(db, permission, cursor=index + 2, lot_id=f"negative-{index}", brand="Zyxwv")
        now = AUCTION_NOW + timedelta(seconds=51)

    def verify():
        query_counts = []
        for size in (1, 50):
            queries = []
            def counted(_connection, _cursor, statement, *_):
                queries.append(statement)
            with database.session(include_all_organizations=True) as session:
                _, policy = source.require_permission(session, permission, now=now)
                event.listen(database.engine, "before_cursor_execute", counted)
                try:
                    page = source.read_current(session, policy.source_key, now=now, limit=size)
                finally:
                    event.remove(database.engine, "before_cursor_execute", counted)
                assert len(page["items"]) == size and page["next_cursor"] is not None
                assert all(row["state"] == "available" for row in page["items"])
                query_counts.append(len(queries))
                if size == 50:
                    tail = source.read_current(session, policy.source_key, now=now, limit=50, after=page["next_cursor"])
                    assert len(tail["items"]) == 1 and tail["next_cursor"] is None
                    assert len({row["record_key"] for row in page["items"] + tail["items"]}) == 51
        assert query_counts == [4, 4]
        with database.session() as session:
            for _ in range(7):
                result = workflow.refresh(session, "owner", monitor, now=now)
                session.commit()
                if result["health"] != "catching_up":
                    break
            assert result["health"] == "current"
            reader = workflow.list_candidates if domain == "ip" else workflow.list_items
            items = reader(session, "owner", monitor, now=now)["items"]
            assert len(items) == 1 and items[0]["version"] == 2
            original_id = items[0]["id"]
        # A record omitted as a definite nonmatch must still enter the private
        # workflow on a later match, then retain history if it stops matching.
        for cursor, selected in ((52, True), (53, False)):
            if domain == "ip":
                ip_accept(db, permission, cursor=cursor, facts=source_facts(official_id="negative-49", mark="ALMORA" if selected else "Quantum"))
            else:
                auction_accept(db, permission, cursor=cursor, lot_id="negative-49", brand="BMW" if selected else "Zyxwv")
            later = now + timedelta(seconds=cursor - 51)
            with database.session() as session:
                for _ in range(7):
                    result = workflow.refresh(session, "owner", monitor, now=later)
                    session.commit()
                    if result["health"] != "catching_up":
                        break
                assert result["health"] == "current"
                items = reader(session, "owner", monitor, now=later)["items"]
                assert len(items) == 2
                assert next(row for row in items if row["id"] == original_id)["version"] == 2
                assert next(row for row in items if row["id"] != original_id)["version"] == (1 if selected else 2)
        with database.session(include_all_organizations=True) as session:
            head = session.scalar(select(head_model).where(head_model.permission_id == permission).order_by(head_model.record_key))
            session.get(revision_model, head.revision_id).raw_payload = b"corrupt retained original"
            session.commit()
        with database.session(include_all_organizations=True) as session:
            _, policy = source.require_permission(session, permission, now=now)
            page = source.read_current(session, policy.source_key, now=later, limit=50)
            assert page["items"][0]["state"] == "unavailable"
            source.revoke_permission(session, permission, now=later)
            session.commit()
        with database.session(include_all_organizations=True) as session:
            with pytest.raises(DomainError):
                source.read_current(session, policy.source_key, now=later, after=page["next_cursor"])
    verify()
