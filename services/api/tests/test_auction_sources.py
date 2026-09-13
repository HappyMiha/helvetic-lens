"""Synthetic native-adapter outputs and grants, never a live source approval."""

import hashlib
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from pydantic import ValidationError
from sqlalchemy import func, select, update
from test_auction_rules import NOW, facts, price
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from alembic import command
from helvetic_lens import auction_sources as source
from helvetic_lens.auction_source_models import (
    AuctionSourcePermission,
    AuctionSourceReceipt,
    AuctionSourceRecordHead,
    AuctionSourceRecordRevision,
)
from helvetic_lens.config import DomainError
from helvetic_lens.db import Base

db, template = _database_fixture, _template_fixture
RAW = b"Synthetic official auction transport. No real source licence."
BASE = "https://auction.example.invalid/auction/"


def policy(**changes):
    return source.AuctionSourcePolicy(**{
        "source_key": "fixture-ti", "reference": "Synthetic reviewed source permission", "attribution": "Synthetic office",
        "endpoint": BASE, "cantons": ("TI",), "categories": ("vehicles",),
        "accepted_at": NOW - timedelta(days=1), "valid_until": NOW + timedelta(days=2),
        "min_poll_seconds": 600, "max_age_seconds": 300, "raw_retention_seconds": 600,
        "normalized_retention_seconds": 3600, "automated_access_allowed": True,
        "store_source_allowed": True, "retain_minimal_audit": True, "matching_allowed": True,
        "display_allowed": True, **changes})


def grant(db, *, generation=0, **changes):
    with db.session() as session:
        identifier = source.record_permission(session, policy=policy(**changes))
        source.activate_permission(session, identifier, expected_generation=generation, now=NOW)
        session.commit()
        return identifier


def accept(db, permission, *, cursor=0, generation=1, raw=RAW, key=None, at=None, now=None, request_url=BASE + "12", **values):
    at = at or NOW + timedelta(seconds=cursor)
    record = facts(raw_sha256=hashlib.sha256(raw).hexdigest(), observed_at=at, **values)
    with db.session() as session:
        result = source.accept_record(session, permission, raw, record, request_key=key or str(uuid4()),
            request_url=request_url, expected_generation=generation, expected_cursor_version=cursor,
            received_at=at, now=now or at)
        session.commit()
        return result


def counts(db):
    with db.session() as session:
        return tuple(session.scalar(select(func.count()).select_from(model)) for model in
            (AuctionSourceRecordRevision, AuctionSourceRecordHead, AuctionSourceReceipt))


def test_record_revisions_retain_exact_price_and_deadline_history(db):
    permission = grant(db, private_decisions_allowed=True)
    first = accept(db, permission)
    second = accept(db, permission, cursor=1, prices=[price(1270000)], ends_at=NOW + timedelta(days=4))
    assert first["state_sequence"] == 1 and second["state_sequence"] == 2
    with db.session() as session:
        old = source.read_revision(session, permission, first["revision_id"], now=NOW + timedelta(seconds=1))
        new = source.read_revision(session, permission, second["revision_id"], now=NOW + timedelta(seconds=1))
        assert old.prices[0].amount_minor == 850000 and new.prices[0].amount_minor == 1270000
        assert old.ends_at != new.ends_at
        current = source.read_current(session, "fixture-ti", now=NOW + timedelta(seconds=1))
        assert current["items"][0]["revision_id"] == second["revision_id"]
        assert not current["coverage_verified"]
    assert counts(db) == (2, 1, 2)


def test_identical_request_retries_are_idempotent_but_changed_replays_conflict(db):
    permission = grant(db)
    first = accept(db, permission, key="same-request")
    assert accept(db, permission, key="same-request") == first
    with pytest.raises(DomainError):
        accept(db, permission, key="same-request", prices=[price(1000000)])
    assert counts(db) == (1, 1, 1)


def test_fresh_unchanged_state_has_new_observation_without_new_state_revision(db):
    permission = grant(db)
    before = accept(db, permission)
    after = accept(db, permission, cursor=1)
    assert after["revision_id"] != before["revision_id"]
    assert after["state_sequence"] == before["state_sequence"] and not after["state_changed"]
    with db.session() as session:
        assert source.read_revision(session, permission, after["revision_id"], now=NOW + timedelta(seconds=1)).observed_at == NOW + timedelta(seconds=1)


def test_partial_listing_does_not_remove_a_previously_observed_lot(db):
    permission = grant(db)
    first = accept(db, permission, lot_id="lot-1")
    second = accept(db, permission, cursor=1, lot_id="lot-2")
    with db.session() as session:
        page = source.read_current(session, "fixture-ti", now=NOW + timedelta(seconds=1), limit=1)
        next_page = source.read_current(session, "fixture-ti", now=NOW + timedelta(seconds=1), after=page["next_cursor"])
        assert {page["items"][0]["revision_id"], next_page["items"][0]["revision_id"]} == {first["revision_id"], second["revision_id"]}
        assert not page["coverage_verified"] and next_page["next_cursor"] is None


@pytest.mark.parametrize("url", ["https://foreign.example.invalid/auction/12", "http://auction.example.invalid/auction/12",
    BASE + "../private", BASE + "%2e%2e/private", BASE + "%252e%252e/private", BASE + "12?token=x", BASE + "12#secret",
    "https://auction.example.invalid/auction-evil/12", "https://x:y@auction.example.invalid/auction/12"])
def test_source_requests_cannot_escape_reviewed_origin_and_path(db, url):
    permission = grant(db)
    with pytest.raises(DomainError):
        accept(db, permission, request_url=url)
    assert counts(db) == (0, 0, 0)


@pytest.mark.parametrize("values", [{"canton": "ZH"}, {"source_key": "unapproved"}, {"category": "real_estate"},
    {"source_url": "https://foreign.example.invalid/auction/12"}])
def test_normalized_records_cannot_claim_unapproved_source_scope(db, values):
    permission = grant(db)
    with pytest.raises(DomainError):
        accept(db, permission, **values)
    assert counts(db) == (0, 0, 0)


def test_old_source_generation_and_out_of_order_cursor_cannot_write(db):
    permission = grant(db)
    accept(db, permission)
    with pytest.raises(DomainError):
        accept(db, permission, cursor=0, key="stale-cursor")
    with pytest.raises(DomainError):
        accept(db, permission, cursor=1, at=NOW - timedelta(seconds=1))
    replacement = grant(db, generation=1)
    with pytest.raises(DomainError):
        accept(db, permission, cursor=1)
    with db.session() as session:
        assert source.read_current(session, "fixture-ti", now=NOW)["items"] == []
    accept(db, replacement, generation=2)
    assert counts(db) == (2, 2, 2)


def test_stale_observation_never_reports_current_coverage(db):
    permission = grant(db)
    accept(db, permission)
    with db.session() as session:
        row, = source.read_current(session, "fixture-ti", now=NOW + timedelta(seconds=301))["items"]
        assert row["state"] == "unavailable" and "facts" not in row


def test_retention_expires_payloads_and_revocation_immediately_removes_remaining_content(db):
    permission = grant(db, export_allowed=True)
    result = accept(db, permission)
    with db.session() as session:
        assert source.read_original(session, permission, result["revision_id"], now=NOW) == RAW
        assert source.purge_content(session, now=NOW + timedelta(seconds=600)) == {"raw_rows": 1, "normalized_rows": 0}
        with pytest.raises(DomainError):
            source.read_original(session, permission, result["revision_id"], now=NOW + timedelta(seconds=600))
        assert source.read_revision(session, permission, result["revision_id"], now=NOW + timedelta(seconds=600))
        source.revoke_permission(session, permission, now=NOW + timedelta(seconds=601))
        session.commit()
        stored = session.get(AuctionSourceRecordRevision, result["revision_id"], populate_existing=True)
        assert stored.raw_payload is None and stored.normalized_payload is None
        assert stored.raw_hash and stored.state_hash
        with pytest.raises(DomainError):
            source.read_revision(session, permission, result["revision_id"], now=NOW + timedelta(seconds=602))


@pytest.mark.parametrize("purpose", ["notification", "export", "decision"])
def test_display_permission_never_grants_delivery_export_or_decisions(db, purpose):
    permission = grant(db)
    with db.session() as session, pytest.raises(DomainError) as error:
        source.require_permission(session, permission, now=NOW, purpose=purpose)
    assert error.value.status == 403


def test_changed_policy_or_payload_hash_is_unavailable(db):
    permission = grant(db)
    result = accept(db, permission)
    with db.session() as session:
        session.execute(update(AuctionSourceRecordRevision).where(AuctionSourceRecordRevision.id == result["revision_id"])
            .values(normalized_payload=b'{}'))
        session.commit()
        with pytest.raises(DomainError):
            source.read_revision(session, permission, result["revision_id"], now=NOW)
        session.execute(update(AuctionSourcePermission).where(AuctionSourcePermission.id == permission).values(policy_hash="0" * 64))
        session.commit()
        with pytest.raises(DomainError):
            source.require_permission(session, permission, now=NOW)


def test_capacity_failure_rolls_back_without_advancing_head_or_cursor(db, monkeypatch):
    permission = grant(db)
    accept(db, permission)
    monkeypatch.setattr(source, "MAX_REVISIONS", 1)
    with pytest.raises(DomainError):
        accept(db, permission, cursor=1, prices=[price(1270000)])
    assert counts(db) == (1, 1, 1)
    with db.session() as session:
        assert source.read_current(session, "fixture-ti", now=NOW)["cursor_version"] == 1


def test_permission_requires_explicit_time_and_bounded_scope():
    for changes in ({"endpoint": BASE.rstrip("/")}, {"cantons": ("XX",)}, {"retain_minimal_audit": False},
                    {"valid_until": NOW - timedelta(days=3)}, {"raw_retention_seconds": 999999}):
        with pytest.raises(ValidationError):
            policy(**changes)


def test_retention_worker_purges_payloads_even_with_section_switched_off(db, monkeypatch):
    from helvetic_lens import celery_app as worker

    permission = grant(db, raw_retention_seconds=5, normalized_retention_seconds=10)
    saved = accept(db, permission)
    monkeypatch.setattr(worker.settings, "auction_watch_enabled", False)
    monkeypatch.setattr(worker, "Database", lambda settings: db)
    original = source.cleanup
    monkeypatch.setattr(source, "cleanup", lambda database: original(database, now=NOW + timedelta(seconds=11)))
    assert worker.cleanup_auction_source.run() == {"raw_rows": 1, "normalized_rows": 1}
    assert worker.cleanup_auction_source.run() == {"raw_rows": 0, "normalized_rows": 0}
    with db.session() as session:
        row = session.get(AuctionSourceRecordRevision, saved["revision_id"])
        assert row.raw_payload is None and row.normalized_payload is None
        assert row.raw_hash == hashlib.sha256(RAW).hexdigest()
    assert worker.celery_app.conf.beat_schedule["cleanup-auction-source"]["schedule"] == 60.0


def test_journal_migration_matches_metadata_and_preserves_private_profiles(db):
    from test_auction_rules import profile

    from helvetic_lens import auction_repository as repository
    from helvetic_lens.auction_models import AuctionMonitor
    with db.session() as session:
        monitor = repository.create_monitor(session, "owner", profile().model_dump(mode="json"), "profile-migration")
        session.commit()
    with db.engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"include_object":
            lambda obj, name, kind, reflected, compare_to: name.startswith("auction_") if kind == "table" else True})
        assert compare_metadata(context, Base.metadata) == []
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "6fac2d70ed61")
        assert connection.execute(select(AuctionMonitor.id).where(AuctionMonitor.id == monitor["id"])).scalar() == monitor["id"]
        command.upgrade(config, "head")
        assert compare_metadata(context, Base.metadata) == []
