"""Account-erasure prerequisites preserve colleagues' real native decisions."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import delete, inspect, select
from test_business_item_work import act, read, seed
from test_tender_repository import db as db
from test_tender_repository import template as template

from alembic import command
from helvetic_lens.auction_workflow_models import AuctionDecision
from helvetic_lens.models import OrganizationMembership, User
from helvetic_lens.related_models import RelatedPlaceBinding
from helvetic_lens.tender_models import TenderDecision
from helvetic_lens.trademark_workflow_models import TrademarkReview

TABLES = {"tenders": (TenderDecision, "user_id", "no_bid"),
          "ip": (TrademarkReview, "actor_user_id", "counsel"),
          "auctions": (AuctionDecision, "actor_user_id", "inspect")}


def config(connection):
    value = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    value.attributes["connection"] = connection
    return value


@pytest.mark.parametrize("domain", TABLES)
def test_upgrade_preserves_native_decision_then_actor_delete_keeps_colleague_history(db, domain):
    data = seed(db, domain)
    model, column, decision = TABLES[domain]
    previous = act(db, domain, data, user="peer", decision=decision, comment="Retain the workspace decision")
    with db.engine.begin() as connection:
        command.downgrade(config(connection), "8b6e4f58acde")
        assert not next(field for field in inspect(connection).get_columns(model.__tablename__)
                        if field["name"] == column)["nullable"]
        command.upgrade(config(connection), "head")
        assert next(field for field in inspect(connection).get_columns(model.__tablename__)
                    if field["name"] == column)["nullable"]
    with db.session() as session:
        native = session.scalar(select(model))
        identifier, source_revision = native.id, getattr(native, "source_revision_id", None)
        assert getattr(native, column) == "peer"
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == "peer"))
        session.execute(delete(User).where(User.id == "peer"))
        session.commit()
    current = read(db, domain, data)
    assert current["decision"] == previous["decision"] and not current["needs_review"]
    assert current["history"][0]["actor"] is None
    assert current["history"][0]["comment"] == "Retain the workspace decision"
    assert current["history"][0]["binding"] == previous["history"][0]["binding"]
    with db.session() as session:
        native = session.get(model, identifier)
        assert native is not None and getattr(native, column) is None
        assert getattr(native, "source_revision_id", None) == source_revision
    with db.engine.connect() as connection:
        with pytest.raises(RuntimeError, match="after account erasure"):
            command.downgrade(config(connection), "8b6e4f58acde")
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert connection.execute(select(model.id).where(model.id == identifier)).scalar() == identifier


def test_deleting_reviewer_preserves_existing_geography_proof(db):
    from datetime import UTC, datetime
    with db.session() as session:
        row = RelatedPlaceBinding(id="reviewed-geography", feature_key="a" * 64, source_revision="b" * 64,
            binding={"synthetic": True, "boundary_hash": "c" * 64}, fingerprint="d" * 64,
            reviewed_by="peer", created_at=datetime.now(UTC))
        session.add(row)
        session.commit()
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == "peer"))
        session.execute(delete(User).where(User.id == "peer"))
        session.commit()
    with db.session() as session:
        retained = session.get(RelatedPlaceBinding, "reviewed-geography")
        assert retained.reviewed_by is None
        assert retained.binding == {"synthetic": True, "boundary_hash": "c" * 64}
        assert retained.fingerprint == "d" * 64 and retained.revoked_at is None
