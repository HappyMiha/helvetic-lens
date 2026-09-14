"""Private IP review journeys with synthetic grants, never measured legal quality."""

from datetime import timedelta
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import select
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture
from test_trademark_matching import calibration, facts, portfolio
from test_trademark_sources import NOW, RAW, accept, grant

from alembic import command
from helvetic_lens import trademark_calibrations as calibrations
from helvetic_lens import trademark_repository as profiles
from helvetic_lens import trademark_sources as sources
from helvetic_lens import trademark_workflow as workflow
from helvetic_lens.config import DomainError
from helvetic_lens.db import Base
from helvetic_lens.trademark_models import TrademarkMonitor
from helvetic_lens.trademark_workflow_models import (
    TrademarkCandidate,
    TrademarkCandidateEvent,
    TrademarkReview,
)

db, template = _database_fixture, _template_fixture


def create(db, payload=None):
    with db.session() as session:
        row = profiles.create_monitor(session, "owner", payload or portfolio().model_dump(mode="json"), "create")
        session.commit()
        return row["id"]


def running(db, payload=None, *, decisions=True, calibrated=False, record=None):
    permission = grant(db, private_decisions_allowed=decisions)
    if calibrated:
        with db.session() as session:
            identifier = calibrations.retain(session, calibration())
            calibrations.select_current(session, identifier, expected_id=None, now=NOW)
            session.commit()
    accept(db, permission, facts=record)
    monitor = create(db, payload)
    with db.session() as session:
        workflow.start(session, "owner", monitor, 1, now=NOW)
        workflow.refresh(session, "owner", monitor, now=NOW)
        session.commit()
    return permission, monitor


def rows(db, monitor, now=NOW):
    with db.session() as session:
        return workflow.list_candidates(session, "owner", monitor, now=now)["items"]


def review(db, monitor, *, decision="relevant", now=NOW, row=None):
    row = row or rows(db, monitor, now)[0]
    with db.session() as session:
        result = workflow.review(session, "owner", monitor, row["id"], expected_version=row["version"],
            expected_evaluation_hash=row.get("evaluation_hash"), decision=decision, now=now)
        session.commit()
        return result


def sync(db, monitor, now=NOW):
    with db.session() as session:
        result = workflow.refresh(session, "owner", monitor, now=now)
        session.commit()
        return result


def source_facts(**changes):
    import hashlib
    return facts(source_sha256=hashlib.sha256(RAW).hexdigest(), **changes)


def test_no_source_cannot_start_and_exact_matches_disclose_missing_calibration(db):
    monitor = create(db)
    with db.session() as session:
        preview = workflow.preview(session, "owner", portfolio().model_dump(mode="json"), now=NOW)
        assert not preview["start_available"] and not preview["coverage_verified"]
        with pytest.raises(DomainError):
            workflow.start(session, "owner", monitor, 1, now=NOW)
    permission = grant(db, private_decisions_allowed=True)
    accept(db, permission)
    with db.session() as session:
        preview = workflow.preview(session, "owner", portfolio().model_dump(mode="json"), now=NOW)
        assert preview["start_available"] and preview["similarity_unavailable_languages"] == ["en"]
        workflow.start(session, "owner", monitor, 1, now=NOW)
        session.commit()
    sync(db, monitor)
    row, = rows(db, monitor)
    assert row["assessment"]["priority"] == "high" and not row["legal_conflict_confirmed"]
    assert row["assessment"]["goods_services"]["class_overlap"] == [9]
    assert row["needs_review"] and review(db, monitor)["decision"] == "relevant"


def test_review_replay_and_owner_change_away_back_reopens_with_retained_decisions(db):
    permission, monitor = running(db)
    first = review(db, monitor)
    assert not first["needs_review"]
    assert review(db, monitor)["version"] == first["version"]
    accept(db, permission, cursor=1, facts=source_facts(owners=["Changed Owner AG"]))
    accept(db, permission, cursor=2)
    later = NOW + timedelta(seconds=2)
    with pytest.raises(DomainError) as stale:
        review(db, monitor, row=first, now=later)
    assert stale.value.code == "trademark_candidate_refresh_required"
    sync(db, monitor, later)
    row, = rows(db, monitor, later)
    assert row["needs_review"] and row["sequence"] == 3 and row["decision"] == "relevant"
    with db.session() as session:
        events = list(session.scalars(select(TrademarkCandidateEvent).order_by(TrademarkCandidateEvent.sequence)))
        assert len(events) == 3 and all("changed_owners" in e.change_codes for e in events[1:])
        assert session.scalar(select(TrademarkReview)).sequence == 1
    assert review(db, monitor, now=later, decision="counsel")["decision"] == "counsel"


def test_evidence_refresh_does_not_reopen_and_staleness_prevents_review(db):
    permission, monitor = running(db)
    first = review(db, monitor)
    accept(db, permission, cursor=1, facts=source_facts(source_document_sha256="a" * 64))
    sync(db, monitor, NOW + timedelta(seconds=1))
    row, = rows(db, monitor, NOW + timedelta(seconds=1))
    assert row["version"] == first["version"] and row["sequence"] == 1 and not row["needs_review"]
    old = rows(db, monitor, NOW + timedelta(minutes=6))[0]
    assert old["facts"] is None and old["decision"] == "relevant"
    with pytest.raises(DomainError):
        review(db, monitor, row=row, now=NOW + timedelta(minutes=6))


def test_candidate_isolated_and_revocation_preserves_private_decision_only(db):
    permission, monitor = running(db)
    row = review(db, monitor)
    with db.session() as session:
        for actor in ("peer", "viewer"):
            with pytest.raises(DomainError):
                workflow.list_candidates(session, actor, monitor, now=NOW)
        sources.revoke_permission(session, permission, now=NOW)
        session.commit()
    unavailable, = rows(db, monitor)
    assert unavailable["facts"] is None and unavailable["assessment"] is None and unavailable["decision"] == "relevant"
    with pytest.raises(DomainError):
        review(db, monitor, row=row)
    with db.organization_context("org-b"), db.session() as session:
        assert session.get(TrademarkCandidate, row["id"]) is None


def test_decision_permission_not_inferred_from_display(db):
    _, monitor = running(db, decisions=False)
    row, = rows(db, monitor)
    assert row["facts"] and not row["can_review"]
    with pytest.raises(DomainError) as error:
        review(db, monitor, row=row)
    assert error.value.code == "trademark_source_use_denied"


def test_calibration_changes_require_refresh_and_historical_registry_is_immutable(db):
    _, monitor = running(db, calibrated=True, record=source_facts(mark="ALMORE"))
    row = review(db, monitor)
    with db.session() as session:
        old = calibration().fingerprint()
        new = calibrations.retain(session, calibration(version="reviewed-fixture-v2", lexical_minimum=95))
        calibrations.select_current(session, new, expected_id=old, now=NOW)
        session.commit()
    assert rows(db, monitor)[0]["facts"] is None
    with pytest.raises(DomainError):
        review(db, monitor, row=row)
    sync(db, monitor)
    changed, = rows(db, monitor)
    assert changed["sequence"] == 2 and changed["needs_review"] and changed["decision"] == "relevant"
    with db.session() as session:
        assert "evaluation_changed" in session.scalar(select(TrademarkCandidateEvent).where(TrademarkCandidateEvent.sequence == 2)).change_codes
        assert calibrations.read(session, old, now=NOW).lexical_minimum == 70
        calibrations.revoke(session, new, now=NOW)
        session.commit()
    sync(db, monitor)
    assert rows(db, monitor)[0]["sequence"] == 3


def test_multiple_brands_and_profile_change_keep_decisions_and_do_not_replay_removed_brand(db):
    config = portfolio().model_dump(mode="json")
    config["brands"].append({**config["brands"][0], "key": "owner-interest", "name": "OTHER", "owners_of_interest": ["Synthetic Owner AG"]})
    permission, monitor = running(db, config)
    assert len(rows(db, monitor)) == 2
    with db.session() as session:
        workflow.pause(session, "owner", monitor, 2)
        config["brands"] = config["brands"][:1]
        profiles.edit_monitor(session, "owner", monitor, 3, config)
        workflow.start(session, "owner", monitor, 4, now=NOW)
        session.commit()
    sync(db, monitor)
    accept(db, permission, cursor=1, facts=source_facts(status="cancelled"))
    accept(db, permission, cursor=2)
    sync(db, monitor, NOW + timedelta(seconds=2))
    available = [r for r in rows(db, monitor, NOW + timedelta(seconds=2)) if r["state"] == "available"]
    assert len(available) == 1 and available[0]["sequence"] == 4


def test_migration_roundtrip_preserves_source_portfolio_and_auction_tables(db):
    _, monitor = running(db)
    with db.engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"include_object":
            lambda obj, name, kind, reflected, compare_to: name.startswith("trademark_") if kind == "table" else True})
        assert compare_metadata(context, Base.metadata) == []
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "a3e06124c2a5")
        assert connection.execute(select(TrademarkMonitor.id).where(TrademarkMonitor.id == monitor)).scalar() == monitor
        command.upgrade(config, "head")
        assert compare_metadata(context, Base.metadata) == []


def test_malformed_retained_calibration_redacts_current_assessment_until_refresh(db):
    from helvetic_lens.trademark_workflow_models import TrademarkCalibration
    _, monitor = running(db, calibrated=True, record=source_facts(mark="ALMORE"))
    with db.session() as session:
        row = session.get(TrademarkCalibration, calibration().fingerprint())
        row.configuration = {**row.configuration, "lexical_minimum": "unreviewed"}
        session.commit()
    candidate, = rows(db, monitor)
    assert candidate["facts"] is None and not candidate["can_review"]
    sync(db, monitor)
    candidate, = rows(db, monitor)
    assert candidate["sequence"] == 2 and candidate["assessment"]["state"] == "unavailable"
    assert candidate["similarity_unavailable_languages"] == ["en"]
