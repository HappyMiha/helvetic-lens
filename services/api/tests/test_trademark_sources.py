"""Synthetic register journal and grants, not native IPI acquisition acceptance."""

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture
from test_trademark_matching import facts as fixture_facts

from alembic import command
from helvetic_lens import trademark_sources as source
from helvetic_lens.config import DomainError
from helvetic_lens.db import Base
from helvetic_lens.trademark_source_models import (
    TrademarkRegisterHead,
    TrademarkRegisterRevision,
    TrademarkSourcePermission,
    TrademarkSourceReceipt,
    TrademarkSourceSelection,
)

db, template = _database_fixture, _template_fixture
NOW = datetime(2026, 9, 13, 19, 0, tzinfo=UTC)
RAW = b"<synthetic-record>ALMORA</synthetic-record>"
ENDPOINT = "https://example.invalid/register"


def policy(**changes):
    return source.TrademarkSourcePolicy(**{
        "source_key": "synthetic-ipi", "reference": "Synthetic reviewed terms fixture",
        "attribution": "Synthetic register", "endpoint": ENDPOINT,
        "accepted_at": NOW - timedelta(days=1), "valid_until": NOW + timedelta(days=3),
        "origins": ("national_ch",), "min_poll_seconds": 3600, "max_age_seconds": 300,
        "raw_retention_seconds": 600, "normalized_retention_seconds": 86400,
        "automated_access_allowed": True, "store_source_allowed": True, "retain_minimal_audit": True,
        "matching_allowed": True, "display_allowed": True, **changes,
    })


def grant(db, *, selected=True, generation=0, **changes):
    with db.session() as session:
        permission = source.record_permission(session, policy=policy(**changes))
        if selected:
            source.activate_permission(session, permission, expected_generation=generation, now=NOW)
        session.commit()
        return permission


def accept(db, permission, *, cursor=0, generation=1, raw=RAW, facts=None, key=None, second=None, **kwargs):
    received = NOW + timedelta(seconds=cursor if second is None else second)
    with db.session() as session:
        result = source.accept_record(session, permission, raw,
            facts or fixture_facts(source_sha256=hashlib.sha256(raw).hexdigest()),
            request_key=key or str(uuid4()), request_url=kwargs.pop("request_url", ENDPOINT),
            expected_generation=generation, expected_cursor_version=cursor,
            received_at=received, now=kwargs.pop("now", received), **kwargs)
        session.commit()
        return result


def current(db, **kwargs):
    with db.session() as session:
        return source.read_current(session, "synthetic-ipi", now=kwargs.pop("now", NOW), **kwargs)


def counts(db):
    with db.session() as session:
        return tuple(session.scalar(select(func.count()).select_from(model)) for model in (
            TrademarkRegisterRevision, TrademarkSourceReceipt, TrademarkRegisterHead))


def test_durable_versions_separate_material_and_transport_changes(db):
    permission = grant(db)
    first = accept(db, permission, key="first")
    assert first["change"] == "first_seen" and first["material_sequence"] == 1
    assert accept(db, permission, key="first") == first
    unchanged = accept(db, permission, cursor=1)
    assert unchanged["revision_id"] == first["revision_id"] and unchanged["change"] == "unchanged"
    transport = accept(db, permission, cursor=2, raw=RAW + b"\n")
    assert transport["sequence"] == 2 and transport["material_sequence"] == 1
    assert transport["change"] == "evidence" and not transport["material_changed"]
    changes = {"owners": ["Another Owner AG"], "representatives": ["New Representative"],
        "status": "cancelled", "cancellation_date": "2026-09-13", "goods_services": None}
    material = accept(db, permission, cursor=3,
        facts=fixture_facts(source_sha256=hashlib.sha256(RAW).hexdigest(), **changes))
    assert material["material_sequence"] == 2 and material["change"] == "material"
    assert counts(db) == (3, 4, 1)
    db.engine.dispose()
    latest = current(db, now=NOW + timedelta(seconds=3))
    assert not latest["coverage_verified"] and latest["cursor_version"] == 4
    record = latest["items"][0]["facts"]
    assert record.owners == ("Another Owner AG",) and record.goods_services is None
    assert record.application_date != record.publication_date != record.registration_date
    with db.session() as session:
        previous = source.read_revision(session, permission, first["revision_id"], now=NOW + timedelta(seconds=3))
        assert previous.owners == ("Synthetic Owner AG",) and previous.status is None
    reverted = accept(db, permission, cursor=4)
    assert reverted["material_sequence"] == 3 and reverted["revision_id"] != first["revision_id"]


def test_cursor_request_generation_and_endpoint_fail_without_partial_writes(db):
    permission = grant(db)
    first = accept(db, permission, key="stable")
    for args, code in [({"cursor": 0}, "cursor_conflict"),
                       ({"cursor": 1, "key": "stable"}, "request_conflict"),
                       ({"cursor": 1, "generation": 2}, "selection_conflict"),
                       ({"cursor": 1, "request_url": ENDPOINT + "/redirect"}, "endpoint_denied"),
                       ({"cursor": 1, "second": -1}, "cursor_conflict")]:
        with pytest.raises(DomainError) as error:
            accept(db, permission, **args)
        assert error.value.code.endswith(code)
        assert counts(db) == (1, 1, 1)
    assert current(db)["items"][0]["revision_id"] == first["revision_id"]


def test_permission_replacement_never_inherits_prior_current_records(db):
    old = grant(db)
    first = accept(db, old)
    new = grant(db, generation=1, reference="Second synthetic permission")
    assert current(db)["items"] == []
    with pytest.raises(DomainError, match="unavailable"):
        accept(db, old, cursor=1)
    received = accept(db, new, generation=2)
    assert received["revision_id"] != first["revision_id"]
    assert current(db)["generation"] == 2
    with db.session() as session:
        source.activate_permission(session, new, expected_generation=2, now=NOW)
        session.commit()
    assert current(db)["items"] == []
    # A retained version is usable again only after a new observation in generation 3.
    accept(db, new, generation=3)
    assert len(current(db)["items"]) == 1


def test_retention_purge_does_not_extend_history_and_reacquisition_is_new_evidence(db):
    permission = grant(db, raw_retention_seconds=10, normalized_retention_seconds=20)
    first = accept(db, permission)
    accept(db, permission, cursor=1, second=9)
    with db.session() as session:
        source.purge_content(session, now=NOW + timedelta(seconds=11))
        session.commit()
        row = session.get(TrademarkRegisterRevision, first["revision_id"])
        assert row.raw_payload is None and row.normalized_payload is not None
        assert source.read_revision(session, permission, row.id, now=NOW + timedelta(seconds=11)).mark == "ALMORA"
        source.purge_content(session, now=NOW + timedelta(seconds=21))
        session.commit()
        assert session.get(TrademarkRegisterRevision, row.id, populate_existing=True).normalized_payload is None
    assert current(db, now=NOW + timedelta(seconds=21))["items"][0]["state"] == "unavailable"
    new = accept(db, permission, cursor=2, second=22)
    assert new["revision_id"] != first["revision_id"] and new["material_sequence"] == 1
    assert new["sequence"] == 2 and not new["material_changed"]


def test_revocation_purges_content_and_denies_all_read_and_replay_purposes(db):
    permission = grant(db)
    first = accept(db, permission, key="replay")
    with db.session() as session:
        source.revoke_permission(session, permission, now=NOW)
        session.commit()
        row = session.get(TrademarkRegisterRevision, first["revision_id"])
        assert row.raw_payload is None and row.normalized_payload is None
        assert row.raw_hash and row.record_key and row.material_hash
        for purpose in ("display", "matching", "storage", "notification", "export", "decision"):
            with pytest.raises(DomainError):
                source.read_revision(session, permission, row.id, now=NOW, purpose=purpose)
    with pytest.raises(DomainError):
        accept(db, permission, key="replay")


def test_permission_expiry_and_use_specific_denials(db):
    permission = grant(db, valid_until=NOW + timedelta(seconds=30), display_allowed=False)
    first = accept(db, permission)
    assert current(db, purpose="matching")["items"][0]["state"] == "available"
    with db.session() as session:
        for purpose in ("display", "notification", "export", "decision", "unknown"):
            with pytest.raises(DomainError) as error:
                source.read_revision(session, permission, first["revision_id"], now=NOW, purpose=purpose)
            assert error.value.status == 403
        row = session.get(TrademarkRegisterRevision, first["revision_id"])
        assert source._utc(row.normalized_expires_at) == NOW + timedelta(seconds=30)
        source.purge_content(session, now=NOW + timedelta(seconds=30))
        session.commit()
        assert session.get(TrademarkRegisterRevision, row.id, populate_existing=True).normalized_payload is None
    with pytest.raises(DomainError):
        current(db, now=NOW + timedelta(seconds=30), purpose="matching")


@pytest.mark.parametrize("field,value", [("raw_payload", b"changed"), ("normalized_payload", b"{}"),
    ("material_hash", "0" * 64), ("record_key", "0" * 64)])
def test_corrupt_evidence_is_not_exposed(db, field, value):
    permission = grant(db)
    first = accept(db, permission)
    with db.session() as session:
        if field == "record_key":
            # FK rejects changing identity underneath a retained head/receipt.
            with pytest.raises(IntegrityError):
                session.execute(update(TrademarkRegisterRevision).values(record_key=value))
            session.rollback()
            return
        session.execute(update(TrademarkRegisterRevision).where(TrademarkRegisterRevision.id == first["revision_id"]).values(**{field: value}))
        session.commit()
    assert current(db)["items"][0]["state"] == "unavailable"
    with pytest.raises(DomainError):
        accept(db, permission, cursor=1)
    assert counts(db) == (1, 1, 1)


def test_policy_tampering_and_wrong_origin_hash_are_rejected(db):
    permission = grant(db)
    for facts in (fixture_facts(source_sha256="f" * 64),
                  fixture_facts(source_sha256=hashlib.sha256(RAW).hexdigest(), origin="international_designating_ch")):
        with pytest.raises(DomainError):
            accept(db, permission, facts=facts)
        assert counts(db) == (0, 0, 0)
    with db.session() as session:
        row = session.get(TrademarkSourcePermission, permission)
        row.policy = {**row.policy, "notifications_allowed": True}
        session.commit()
    with pytest.raises(DomainError) as error:
        accept(db, permission)
    assert error.value.code == "trademark_permission_invalid"


def test_bounded_pages_stale_records_and_registry_origins_do_not_imply_coverage(db):
    permission = grant(db, origins=("national_ch", "international_designating_ch"))
    first = accept(db, permission)
    second = accept(db, permission, cursor=1, facts=fixture_facts(source_sha256=hashlib.sha256(RAW).hexdigest(), origin="international_designating_ch"))
    assert first["record_key"] != second["record_key"]
    page = current(db, now=NOW + timedelta(seconds=1), limit=1)
    next_page = current(db, now=NOW + timedelta(seconds=1), limit=1, after=page["next_cursor"])
    assert len(page["items"]) == len(next_page["items"]) == 1 and next_page["next_cursor"] is None
    assert page["items"][0]["record_key"] != next_page["items"][0]["record_key"]
    assert not page["coverage_verified"]
    stale = current(db, now=NOW + timedelta(seconds=301))
    assert [item["state"] for item in stale["items"]].count("unavailable") == 1
    for args in ({"limit": True}, {"limit": 0}, {"limit": 101}, {"after": "bad"}):
        with pytest.raises(DomainError):
            current(db, **args)


def test_capacity_failure_is_atomic_and_receipt_replay_remains_possible(db, monkeypatch):
    permission = grant(db)
    first = accept(db, permission, key="retained")
    monkeypatch.setattr(source, "MAX_REVISIONS", 1)
    with pytest.raises(DomainError):
        accept(db, permission, cursor=1, raw=RAW + b"\n")
    assert counts(db) == (1, 1, 1)
    assert current(db)["cursor_version"] == 1
    monkeypatch.setattr(source, "MAX_RECEIPTS", 1)
    assert accept(db, permission, key="retained") == first
    with pytest.raises(DomainError):
        accept(db, permission, cursor=1)


@pytest.mark.parametrize("changes", [
    {"accepted_at": NOW.replace(tzinfo=None)}, {"valid_until": NOW - timedelta(days=2)},
    {"endpoint": "http://example.invalid"}, {"endpoint": ENDPOINT + "?key=secret"},
    {"endpoint": "https://user:secret@example.invalid"}, {"origins": ("national_ch", "national_ch")},
    {"retain_minimal_audit": False}, {"raw_retention_seconds": 86401}, {"notifications_allowed": "true"},
])
def test_invalid_policy_is_not_recorded(changes):
    with pytest.raises(ValidationError):
        policy(**changes)


def test_no_acquisition_or_storage_rights_cannot_select_source(db):
    for field in ("automated_access_allowed", "store_source_allowed"):
        permission = grant(db, selected=False, **{field: False})
        with db.session() as session:
            with pytest.raises(DomainError):
                source.activate_permission(session, permission, expected_generation=0, now=NOW)
            assert session.scalar(select(func.count()).select_from(TrademarkSourceSelection)) == 0


def test_source_migration_roundtrip_preserves_private_portfolios(db):
    from test_trademark_repository import create

    from helvetic_lens.trademark_models import TrademarkMonitor

    retained = create(db)
    with db.engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"include_object":
            lambda obj, name, kind, reflected, compare_to: name.startswith("trademark_") if kind == "table" else True})
        assert compare_metadata(context, Base.metadata) == []
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "4dfa0b58cb4f")
        assert connection.execute(select(TrademarkMonitor.id).where(TrademarkMonitor.id == retained["id"])).scalar() == retained["id"]
        command.upgrade(config, "head")
        assert compare_metadata(context, Base.metadata) == []


def test_expired_raw_is_never_written_and_expired_normalized_input_is_rejected(db):
    permission = grant(db, raw_retention_seconds=5, normalized_retention_seconds=20)
    saved = accept(db, permission, now=NOW + timedelta(seconds=6))
    with db.session() as session:
        row = session.get(TrademarkRegisterRevision, saved["revision_id"])
        assert row.raw_payload is None and row.normalized_payload is not None
    with pytest.raises(DomainError):
        accept(db, permission, cursor=1, second=0, now=NOW + timedelta(seconds=20))
    assert counts(db) == (1, 1, 1)


def test_cleanup_worker_runs_with_feature_disabled_and_preserves_only_minimal_audit(db, monkeypatch):
    from helvetic_lens import celery_app as worker

    permission = grant(db, raw_retention_seconds=5, normalized_retention_seconds=10)
    saved = accept(db, permission)
    monkeypatch.setattr(worker.settings, "trademark_watch_enabled", False)
    monkeypatch.setattr(worker, "Database", lambda settings: db)
    original = source.cleanup
    monkeypatch.setattr(source, "cleanup", lambda database: original(database, now=NOW + timedelta(seconds=11)))
    result = worker.cleanup_trademark_source.run()
    assert result == {"raw_rows": 1, "normalized_rows": 1, "ipi": {"pages": 0, "checkpoints": 0, "tokens": 0}}
    assert worker.cleanup_trademark_source.run() == {"raw_rows": 0, "normalized_rows": 0,
        "ipi": {"pages": 0, "checkpoints": 0, "tokens": 0}}
    with db.session() as session:
        row = session.get(TrademarkRegisterRevision, saved["revision_id"])
        assert row.raw_payload is None and row.normalized_payload is None
        receipt = session.scalar(select(TrademarkSourceReceipt))
        assert "ALMORA" not in str(receipt.change) and "Synthetic Owner" not in str(receipt.change)
    assert worker.celery_app.conf.beat_schedule["cleanup-trademark-source"]["schedule"] == 60.0


def test_database_rejects_cross_permission_revision_head(db):
    permission = grant(db)
    saved = accept(db, permission)
    other = grant(db, selected=False, source_key="other-source")
    with db.session() as session:
        session.add(TrademarkRegisterHead(permission_id=other, record_key=saved["record_key"],
            revision_id=saved["revision_id"], generation=1, last_seen_at=NOW))
        with pytest.raises(IntegrityError):
            session.commit()
