"""Synthetic CAP and reviewed fixture grants only; no live source authorization."""

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from pydantic import ValidationError
from sqlalchemy import func, inspect, select, update
from sqlalchemy.exc import IntegrityError
from test_hazard_cap import NOW, SENT, info, message
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from alembic import command
from helvetic_lens import hazard_sources as sources
from helvetic_lens.config import DomainError
from helvetic_lens.db import Base
from helvetic_lens.hazard_cap import HazardCAPError
from helvetic_lens.hazard_source_models import (
    HazardCurrentWarning,
    HazardMessageEvidence,
    HazardSourcePermission,
    HazardSourceReceipt,
)

db = _database_fixture
template = _template_fixture


def policy(**updates):
    return sources.HazardSourcePolicy(**{
        "source_key": "fixture", "reference": "Synthetic reviewed grant", "attribution": "Fixture authority",
        "endpoint": "https://example.invalid/cap", "sender": "fixture@example.invalid",
        "accepted_at": NOW - timedelta(days=1), "valid_until": NOW + timedelta(days=30),
        "min_poll_seconds": 60, "max_age_seconds": 300, "raw_retention_seconds": 3600,
        "normalized_retention_seconds": 86400, "store_full_message": True, "retain_minimal_audit": True,
        "matching_allowed": True, "display_allowed": True, "notifications_allowed": False,
        "covered_cantons": ("BS",), "geocode_version": "2026-01",
        "rules": (sources.HazardRule(hazard="storm", value_name="fixture", value="storm"),),
        "importance": (("Severe", "warning"), ("Extreme", "alarm"), ("Moderate", "information"), ("Minor", "information")),
        **updates,
    })


def grant(db, *, selected=True, expected_generation=0, **updates):
    with db.session() as session:
        permission = sources.record_permission(session, policy=policy(**updates))
        if selected:
            sources.activate_permission(session, permission, expected_generation=expected_generation, now=NOW)
        session.commit()
        return permission


def accept(db, permission, xml=None, *, second=0, cursor=0, generation=1, key=None, **kwargs):
    received = NOW + timedelta(seconds=second)
    with db.session() as session:
        result = sources.accept_message(session, permission, (message() if xml is None else xml).encode(),
            request_key=key or str(uuid4()), request_url="https://example.invalid/cap",
            expected_generation=generation, expected_cursor_version=cursor, received_at=received,
            now=kwargs.pop("now", received), **kwargs)
        session.commit()
        return result


def revised(*, identifier="second", previous="fixture-1", previous_sent=SENT, kind="Update", infos=None,
            sent="2026-09-13T09:30:00+00:00"):
    return message(identifier=identifier, kind=kind, sent=sent,
                   refs=f"fixture@example.invalid,{previous},{previous_sent}", infos=infos)


def current(db, *, now=NOW, **kwargs):
    with db.session() as session:
        return sources.read_current(session, "fixture", now=now, **kwargs)


def counts(db):
    with db.session() as session:
        return tuple(session.scalar(select(func.count()).select_from(model)) for model in (
            HazardMessageEvidence, HazardSourceReceipt, HazardCurrentWarning))


def test_durable_material_history_exact_predecessor_and_historical_reader(db):
    permission = grant(db)
    first = accept(db, permission)
    high = accept(db, permission, revised(infos=info(level="Extreme")), second=1, cursor=1)
    clear = accept(db, permission, revised(identifier="clear", previous="second",
        previous_sent="2026-09-13T09:30:00+00:00", sent="2026-09-13T09:45:00+00:00",
        infos=info(level="Minor", extra="<responseType>AllClear</responseType>")), second=2, cursor=2)
    db.engine.dispose()
    head = current(db, now=NOW + timedelta(seconds=2))
    assert not head["coverage_verified"]
    assert head["items"][0]["state"] == "resolved"
    assert head["items"][0]["material_sequence"] == 3
    assert clear["change"]["previous_keys"] == [high["change"]["message_key"]]
    assert counts(db) == (3, 3, 1)
    with db.session() as session:
        before = sources.read_message(session, permission, first["evidence_id"], now=NOW + timedelta(seconds=2))
        assert before.infos[0].severity == "Severe"
        row = session.get(HazardMessageEvidence, high["evidence_id"])
        assert row.classification == {"hazards": ["storm"], "importance": "alarm", "complete": True}


def test_replays_preserve_immutable_content_ttl_and_do_not_restore_ancestor(db):
    permission = grant(db)
    first = accept(db, permission, key="initial")
    assert accept(db, permission, key="initial", second=10) == {**first, "replay": True}
    high = accept(db, permission, revised(infos=info(level="Extreme")), second=20, cursor=1)
    replay = accept(db, permission, cursor=2, second=30)
    assert not replay["change"]["material"] and replay["change"]["material_sequence"] == 1
    assert current(db, now=NOW + timedelta(seconds=30))["items"][0]["evidence_id"] == high["evidence_id"]
    with db.session() as session:
        row = session.get(HazardMessageEvidence, first["evidence_id"])
        assert sources._utc(row.first_received_at) == NOW
        assert sources._utc(row.last_seen_at) == NOW + timedelta(seconds=30)
        assert sources._utc(row.normalized_expires_at) == NOW + timedelta(days=1)
        assert sources.read_message(session, permission, row.id, now=NOW + timedelta(seconds=30)).received_at == NOW
    assert counts(db) == (2, 3, 1)


def test_translation_and_changed_instructions_have_distinct_review_sequences(db):
    permission = grant(db)
    accept(db, permission)
    translation = accept(db, permission, revised(infos=info() + info(language="fr-CH", instruction="Restez.")),
                         second=1, cursor=1)
    assert translation["change"]["kind"] == "refreshed" and translation["change"]["material_sequence"] == 1
    change = accept(db, permission, revised(identifier="third", previous="second", previous_sent="2026-09-13T09:30:00+00:00",
        sent="2026-09-13T09:45:00+00:00", infos=info(instruction="Evacuate.")), second=2, cursor=2)
    assert change["change"]["material_sequence"] == 2


def test_invalid_sibling_missing_predecessor_and_request_conflict_leave_cursor_intact(db):
    permission = grant(db)
    accept(db, permission, key="first")
    accept(db, permission, revised(), second=1, cursor=1)
    for xml, error in ((revised(identifier="late"), "hazard_reference_superseded"),
                       (revised(identifier="missing-ref", previous="missing"), "hazard_predecessor_missing")):
        with pytest.raises(HazardCAPError, match=error):
            accept(db, permission, xml, second=2, cursor=2)
    with pytest.raises(DomainError) as failure:
        accept(db, permission, message(identifier="different"), key="first", second=2, cursor=2)
    assert failure.value.code == "hazard_source_request_conflict"
    assert counts(db) == (2, 2, 1)
    assert current(db, now=NOW + timedelta(seconds=2))["cursor_version"] == 2


def test_cancel_is_not_all_clear_and_unrelated_notice_never_resolves_absent_warning(db):
    permission = grant(db)
    first = accept(db, permission)
    accept(db, permission, message(identifier="unrelated"), second=1, cursor=1)
    assert all(item["state"] == "active" for item in current(db, now=NOW + timedelta(seconds=1))["items"])
    cancel = accept(db, permission, revised(kind="Cancel", infos=""), second=2, cursor=2)
    assert cancel["change"]["kind"] == "cancelled"
    states = {item["development_key"]: item["state"] for item in current(db, now=NOW + timedelta(seconds=2))["items"]}
    assert states[first["change"]["development_id"]] == "cancelled"
    assert sorted(states.values()) == ["active", "cancelled"]
    with db.session() as session:
        assert session.get(HazardMessageEvidence, cancel["evidence_id"]).classification["hazards"] == ["storm"]


def test_stale_current_is_unavailable_without_resolving_stored_head(db):
    permission = grant(db)
    first = accept(db, permission)
    result = current(db, now=NOW + timedelta(minutes=6))
    assert result["items"][0]["state"] == "unavailable"
    assert result["items"][0]["reason"] == "hazard_evidence_stale"
    with db.session() as session:
        assert sources.read_message(session, permission, first["evidence_id"], now=NOW + timedelta(minutes=6)).state == "active"
        assert session.scalar(select(HazardCurrentWarning)).state == "active"


def test_expired_cap_even_if_just_refetched_does_not_become_current_or_all_clear(db):
    permission = grant(db)
    expired = message().replace("2026-09-14T09:00:00+00:00", "2026-09-13T09:30:00+00:00")
    accept(db, permission, expired)
    item = current(db)["items"][0]
    assert item["state"] == "unavailable" and item["reason"] == "hazard_warning_period_expired"


def test_retention_erases_bytes_but_keeps_id_tombstones_without_rehydration(db):
    permission = grant(db, raw_retention_seconds=10, normalized_retention_seconds=60)
    first = accept(db, permission)
    with db.session() as session:
        sources.purge_content(session, now=NOW + timedelta(seconds=10))
        session.commit()
    with db.session() as session:
        row = session.get(HazardMessageEvidence, first["evidence_id"])
        assert row.raw_payload is None and row.normalized_payload is not None
        sources.purge_content(session, now=NOW + timedelta(seconds=60))
        session.commit()
    with db.session() as session:
        row = session.get(HazardMessageEvidence, first["evidence_id"])
        assert row.raw_payload is None and row.normalized_payload is None and row.classification == {}
        assert row.raw_hash and row.message_key
    with pytest.raises(DomainError) as failure:
        accept(db, permission, cursor=1, second=60)
    assert failure.value.code == "hazard_evidence_expired"
    assert current(db, now=NOW + timedelta(seconds=60))["items"][0]["state"] == "unavailable"
    assert counts(db) == (1, 1, 1)


def test_revocation_removes_content_and_rechecks_cached_objects_for_all_purposes(db):
    permission = grant(db)
    first = accept(db, permission)
    with db.session() as session:
        sources.require_permission(session, permission, now=NOW)
        sources.revoke_permission(session, permission, now=NOW)
        session.commit()
        for purpose in ("storage", "matching", "display", "notification"):
            with pytest.raises(DomainError) as failure:
                sources.read_message(session, permission, first["evidence_id"], purpose=purpose, now=NOW)
            assert failure.value.code == "hazard_permission_unavailable"
        row = session.get(HazardMessageEvidence, first["evidence_id"], populate_existing=True)
        assert row.raw_payload is None and row.normalized_payload is None


@pytest.mark.parametrize("purpose,field", [("matching", "matching_allowed"), ("display", "display_allowed"),
                                         ("notification", "notifications_allowed")])
def test_separate_source_uses_require_current_explicit_rights(db, purpose, field):
    permission = grant(db, **{field: False})
    first = accept(db, permission)
    with db.session() as session, pytest.raises(DomainError) as failure:
        sources.read_message(session, permission, first["evidence_id"], now=NOW, purpose=purpose)
    assert failure.value.code == "hazard_source_use_denied"


def test_reselection_requires_new_receipt_and_does_not_copy_evidence_across_grants(db):
    old = grant(db)
    accept(db, old)
    new = grant(db, expected_generation=1)
    assert current(db)["items"] == []
    with pytest.raises(DomainError):
        accept(db, old, cursor=1)
    with pytest.raises(HazardCAPError, match="hazard_predecessor_missing"):
        accept(db, new, revised(), generation=2)
    accept(db, new, generation=2)
    with db.session() as session:
        sources.activate_permission(session, old, expected_generation=2, now=NOW)
        session.commit()
    assert current(db)["items"] == []
    accept(db, old, generation=3)
    assert len(current(db)["items"]) == 1
    assert counts(db) == (2, 3, 2)


def test_caller_rollback_and_failed_final_flush_leave_no_partial_evidence(db, monkeypatch):
    permission = grant(db)
    with db.session() as session:
        sources.accept_message(session, permission, message().encode(), request_key="rollback",
            request_url="https://example.invalid/cap", expected_generation=1, expected_cursor_version=0,
            received_at=NOW, now=NOW)
        session.rollback()
    assert counts(db) == (0, 0, 0)
    with db.session() as session:
        original = session.flush

        def failing_flush(*args, **kwargs):
            if any(isinstance(row, HazardSourceReceipt) for row in session.new):
                raise IntegrityError("synthetic final constraint", {}, None)
            return original(*args, **kwargs)

        monkeypatch.setattr(session, "flush", failing_flush)
        with pytest.raises(DomainError):
            sources.accept_message(session, permission, message().encode(), request_key="failed",
                request_url="https://example.invalid/cap", expected_generation=1, expected_cursor_version=0,
                received_at=NOW, now=NOW)
        monkeypatch.setattr(session, "flush", original)
        session.commit()
    assert counts(db) == (0, 0, 0)
    assert current(db)["cursor_version"] == 0


def test_cursor_conflicts_monotonic_receipts_and_endpoint_sender_binding(db):
    permission = grant(db)
    accept(db, permission, second=10)
    with pytest.raises(DomainError) as failure:
        accept(db, permission, second=20)
    assert failure.value.code == "hazard_source_cursor_conflict"
    with pytest.raises(DomainError) as failure:
        accept(db, permission, cursor=1)
    assert failure.value.code == "hazard_source_receipt_rollback"
    with pytest.raises(DomainError) as failure:
        accept(db, permission, message().replace("fixture@example.invalid", "other@example.invalid"), cursor=1, second=10)
    assert failure.value.code == "hazard_source_sender_mismatch"
    with db.session() as session, pytest.raises(DomainError) as failure:
        sources.accept_message(session, permission, message().encode(), request_key="redirect",
            request_url="https://other.invalid/cap", expected_generation=1, expected_cursor_version=1,
            received_at=NOW + timedelta(seconds=10), now=NOW + timedelta(seconds=10))
    assert failure.value.code == "hazard_source_receipt_invalid"
    assert counts(db) == (1, 1, 1)


def test_expired_receipt_cannot_insert_content_past_its_retention(db):
    permission = grant(db, raw_retention_seconds=0, normalized_retention_seconds=10)
    with pytest.raises(DomainError) as failure:
        accept(db, permission, now=NOW + timedelta(seconds=10))
    assert failure.value.code == "hazard_source_receipt_stale"
    assert counts(db) == (0, 0, 0)


def test_classification_never_guesses_unmapped_event_or_severity_from_text(db):
    permission = grant(db)
    unknown = message().replace("<value>storm</value>", "<value>unmapped</value>")
    result = accept(db, permission, unknown)
    with db.session() as session:
        assert session.get(HazardMessageEvidence, result["evidence_id"]).classification == {
            "hazards": [], "importance": "warning", "complete": False}
    result = accept(db, permission, message(identifier="unknown-severity", infos=info(level="Unknown")), cursor=1)
    with db.session() as session:
        classification = session.get(HazardMessageEvidence, result["evidence_id"]).classification
        assert not classification["complete"] and classification["importance"] is None


def test_corrupt_permission_or_evidence_is_not_exported(db):
    permission = grant(db)
    first = accept(db, permission)
    with db.session() as session:
        session.execute(update(HazardMessageEvidence).where(HazardMessageEvidence.id == first["evidence_id"])
                        .values(normalized_payload=b"corrupted"))
        session.commit()
    with db.session() as session, pytest.raises(DomainError):
        sources.read_message(session, permission, first["evidence_id"], now=NOW)
    with db.session() as session:
        session.execute(update(HazardSourcePermission).where(HazardSourcePermission.id == permission).values(policy_hash="0" * 64))
        session.commit()
    with pytest.raises(DomainError) as failure:
        current(db)
    assert failure.value.code == "hazard_permission_invalid"


def test_bounded_history_failure_leaves_previous_head_and_receipt(db, monkeypatch):
    permission = grant(db)
    accept(db, permission)
    monkeypatch.setattr(sources, "MAX_RECEIPTS", 1)
    with pytest.raises(DomainError) as failure:
        accept(db, permission, revised(), cursor=1)
    assert failure.value.code == "hazard_receipt_limit"
    assert counts(db) == (1, 1, 1)


def test_permission_expiry_rejects_all_reads_and_purges_both_payloads(db):
    permission = grant(db, valid_until=NOW + timedelta(seconds=10))
    first = accept(db, permission)
    later = NOW + timedelta(seconds=10)
    with db.session() as session:
        with pytest.raises(DomainError) as failure:
            sources.read_message(session, permission, first["evidence_id"], now=later)
        assert failure.value.code == "hazard_permission_unavailable"
        sources.purge_content(session, now=later)
        session.commit()
    with db.session() as session:
        row = session.get(HazardMessageEvidence, first["evidence_id"])
        assert row.raw_payload is None and row.normalized_payload is None


def test_zero_raw_retention_and_elapsed_raw_ttl_never_write_raw_bytes(db):
    permission = grant(db, raw_retention_seconds=0)
    first = accept(db, permission)
    with db.session() as session:
        row = session.get(HazardMessageEvidence, first["evidence_id"])
        assert row.raw_payload is None and row.normalized_payload is not None
    other = grant(db, expected_generation=1, raw_retention_seconds=5)
    result = accept(db, other, generation=2, now=NOW + timedelta(seconds=6))
    with db.session() as session:
        row = session.get(HazardMessageEvidence, result["evidence_id"])
        assert row.raw_payload is None and row.normalized_payload is not None


def test_source_permission_and_current_head_cannot_reference_another_permission(db):
    permission = grant(db)
    first = accept(db, permission)
    other = grant(db, selected=False)
    with db.session() as session, pytest.raises(IntegrityError):
        session.add(HazardCurrentWarning(permission_id=other, evidence_id=first["evidence_id"],
            development_key=first["change"]["development_id"], generation=1, material_sequence=1, state="active"))
        session.flush()
    with db.session() as session, pytest.raises(DomainError):
        sources.read_message(session, other, first["evidence_id"], now=NOW)


def test_unknown_request_id_cannot_mutate_a_retained_or_expired_identifier(db):
    permission = grant(db, raw_retention_seconds=0, normalized_retention_seconds=10)
    accept(db, permission)
    for seconds in (1, 10):
        with pytest.raises(DomainError) as failure:
            accept(db, permission, message(infos=info(instruction="Changed instructions.")), cursor=1, second=seconds)
        assert failure.value.code == "hazard_conflicting_identity"
    assert counts(db) == (1, 1, 1)


def test_corrupt_missing_head_never_restores_an_old_message_as_current(db):
    from sqlalchemy import delete

    permission = grant(db)
    accept(db, permission)
    with db.session() as session:
        session.execute(delete(HazardCurrentWarning))
        session.commit()
    with pytest.raises(DomainError) as failure:
        accept(db, permission, cursor=1)
    assert failure.value.code == "hazard_history_head_unavailable"
    assert counts(db) == (1, 1, 0)


def test_byte_budget_checked_before_decoding_retained_content(db, monkeypatch):
    permission = grant(db)
    accept(db, permission)
    monkeypatch.setattr(sources, "MAX_RETAINED_BYTES", 1)
    with pytest.raises(DomainError) as failure:
        accept(db, permission, revised(), cursor=1)
    assert failure.value.code == "hazard_history_byte_limit"
    assert counts(db) == (1, 1, 1)


@pytest.mark.parametrize("bound,code", [("MAX_RETAINED_BYTES", "hazard_history_byte_limit"),
                                      ("MAX_RAW_BYTES", "hazard_raw_storage_limit"),
                                      ("MAX_EVIDENCE_ROWS", "hazard_evidence_limit")])
def test_storage_bounds_reject_new_evidence_atomically(db, monkeypatch, bound, code):
    permission = grant(db)
    monkeypatch.setattr(sources, bound, 0)
    with pytest.raises(DomainError) as failure:
        accept(db, permission)
    assert failure.value.code == code
    assert counts(db) == (0, 0, 0)
    assert current(db)["cursor_version"] == 0


def test_pagination_is_stable_bounded_and_never_claims_complete_coverage(db):
    permission = grant(db)
    for i in range(3):
        accept(db, permission, message(identifier=f"fixture-{i}"), cursor=i)
    seen, cursor = [], None
    for _ in range(3):
        page = current(db, limit=1, after_key=cursor)
        assert not page["coverage_verified"]
        seen.extend(item["development_key"] for item in page["items"])
        cursor = page["next_cursor"]
    assert cursor is None and len(set(seen)) == 3 and seen == sorted(seen)


@pytest.mark.parametrize("values", [
    {"accepted_at": NOW.replace(tzinfo=None)}, {"endpoint": "http://example.invalid/cap"},
    {"endpoint": "https://secret@example.invalid/cap"}, {"store_full_message": False},
    {"retain_minimal_audit": False}, {"covered_cantons": ("BS", "BS")},
    {"valid_until": NOW - timedelta(days=2)}, {"raw_retention_seconds": 90000},
])
def test_invalid_reviewed_contract_rejected(values):
    with pytest.raises(ValidationError):
        policy(**values)


def test_migration_matches_hazard_metadata_and_preserves_private_places(db):
    with db.engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"include_object":
            lambda obj, name, kind, reflected, compare_to: name.startswith("hazard_") if kind == "table" else True})
        assert compare_metadata(context, Base.metadata) == []
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "f824a6f3d6fa")
        tables = inspect(connection).get_table_names()
        assert "hazard_monitors" in tables and "road_email_policies" in tables
        assert "hazard_message_evidence" not in tables
        command.upgrade(config, "head")
        assert compare_metadata(context, Base.metadata) == []
