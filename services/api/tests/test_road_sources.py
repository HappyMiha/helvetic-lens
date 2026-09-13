from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from test_road_feed import NOW, STAMP, comment, feed, record
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from alembic import command
from helvetic_lens import road_sources as sources
from helvetic_lens.config import DomainError
from helvetic_lens.db import Base
from helvetic_lens.road_models import (
    RoadCurrentSituation,
    RoadSituationVersion,
    RoadSourceChange,
    RoadSourceEvidence,
    RoadSourceHead,
    RoadSourcePermission,
)

db = _database_fixture
template = _template_fixture


def policy(**updates):
    return sources.RoadPolicy(**{
        "reference": "synthetic-reviewed-grant", "attribution": "Synthetic FEDRO test evidence",
        "supplier": ("ch", "test-supplier"), "accepted_at": NOW - timedelta(days=1),
        "valid_until": NOW + timedelta(days=180), "max_age_seconds": 300,
        "raw_retention_seconds": 3600, "derived_retention_seconds": 86400,
        "allowed_fields": ("event_kind", "location", "delay", "source_reference"),
        "notifications_allowed": False, **updates,
    })


def grant(db, *, selected=True, expected_generation=0, **updates):
    with db.session() as session:
        permission_id = sources.record_permission(session, policy=policy(**updates))
        if selected:
            sources.activate_permission(session, permission_id, expected_generation=expected_generation, now=NOW)
        session.commit()
    return permission_id


def accept(db, permission_id, xml=None, *, minute=0, expected_generation=1, request_id=None,
           mode="full", continuous=True, now=None):
    received = NOW + timedelta(minutes=minute)
    payload = (feed() if xml is None else xml).replace(STAMP, received.isoformat()).encode()
    with db.session() as session:
        result = sources.accept_snapshot(session, permission_id, payload, request_id=request_id or str(uuid4()),
            expected_generation=expected_generation, mode=mode, continuous=continuous, received_at=received,
            now=received if now is None else now)
        session.commit()
        return result


def counts(db):
    with db.session() as session:
        return tuple(session.scalar(select(func.count()).select_from(model)) for model in (
            RoadSourceEvidence, RoadSituationVersion, RoadSourceChange, RoadCurrentSituation))


def test_history_and_active_state_survive_session_and_engine_reload(db):
    permission_id = grant(db)
    first = accept(db, permission_id)
    second = accept(db, permission_id, feed(record(code="laneClosures")), minute=1, expected_generation=2, mode="delta")
    third = accept(db, permission_id, feed(record(code="laneClosures", cancelled=True)), minute=2,
                   expected_generation=3, mode="delta")
    db.engine.dispose()
    with db.session() as session:
        state = sources.read_state(session, permission_id, now=NOW + timedelta(minutes=2))
        assert state.situations[0].situation.cancelled
        versions = list(session.scalars(select(RoadSituationVersion).order_by(RoadSituationVersion.version_at)))
        assert [sources.read_version(session, permission_id, v.id, now=NOW + timedelta(minutes=2)).records[0].kind
                for v in versions] == ["road_closure", "lane_restriction", "lane_restriction"]
        changes = list(session.scalars(select(RoadSourceChange).order_by(RoadSourceChange.generation)))
        assert [c.kind for c in changes] == ["created", "material_changed", "revoked"]
        assert [c.evidence_id for c in changes] == [first.evidence_id, second.evidence_id, third.evidence_id]
        assert len({c.development_id for c in changes}) == 1
    assert counts(db) == (3, 3, 3, 1)


def test_source_refresh_has_evidence_but_no_new_material_development(db):
    permission_id = grant(db)
    accept(db, permission_id)
    result = accept(db, permission_id, minute=1, expected_generation=2)
    assert result.change_ids == ()
    assert counts(db) == (2, 2, 1, 1)


def test_idempotent_request_and_stale_writer_do_not_duplicate_evidence(db):
    permission_id = grant(db)
    request_id = str(uuid4())
    first = accept(db, permission_id, request_id=request_id)
    again = accept(db, permission_id, request_id=request_id)
    assert again.replay and again.evidence_id == first.evidence_id and again.change_ids == first.change_ids
    assert counts(db) == (1, 1, 1, 1)
    for options, code in (({"request_id": request_id, "mode": "delta"}, "road_request_conflict"),
                          ({"minute": 1}, "road_generation_conflict")):
        with pytest.raises(DomainError) as error:
            accept(db, permission_id, **options)
        assert error.value.code == code
    assert counts(db) == (1, 1, 1, 1)


def test_delta_baseline_and_absence_preserve_unavailable_closure(db):
    permission_id = grant(db)
    with pytest.raises(ValueError, match="road_full_baseline_required"):
        accept(db, permission_id, mode="delta")
    assert counts(db) == (0, 0, 0, 0)
    accept(db, permission_id)
    accept(db, permission_id, feed(situations=""), minute=1, expected_generation=2, mode="delta")
    with db.session() as session:
        state = sources.read_state(session, permission_id, now=NOW + timedelta(minutes=1))
        assert state.situations[0].present and state.situations[0].seen_at == NOW
    accept(db, permission_id, feed(situations=""), minute=2, expected_generation=3)
    with db.session() as session:
        state = sources.read_state(session, permission_id, now=NOW + timedelta(minutes=2))
        assert not state.situations[0].present
        assert state.situations[0].situation.records[0].kind == "road_closure"
        assert not state.situations[0].situation.cancelled
        assert session.scalar(select(RoadSourceChange.kind).where(RoadSourceChange.generation == 4)) == "source_unavailable"


def test_rights_fields_notifications_and_attribution_are_explicit(db):
    permission_id = grant(db)
    accept(db, permission_id)
    with db.session() as session:
        _, reviewed = sources.require_permission(session, permission_id, now=NOW, fields=("event_kind",))
        assert reviewed.attribution == "Synthetic FEDRO test evidence"
        for options in ({"fields": ("public_text",)}, {"notification": True}):
            with pytest.raises(DomainError) as error:
                sources.require_permission(session, permission_id, now=NOW, **options)
            assert error.value.code == "road_derived_use_denied"
        sources.revoke_permission(session, permission_id, now=NOW)
        session.commit()
    with db.session() as session:
        with pytest.raises(DomainError, match="unavailable"):
            sources.read_state(session, permission_id, now=NOW)


def test_recording_permission_does_not_select_or_activate_source(db):
    permission_id = grant(db, selected=False)
    with pytest.raises(DomainError) as error:
        accept(db, permission_id)
    assert error.value.code == "road_permission_not_selected"
    assert counts(db) == (0, 0, 0, 0)


def test_renewal_requires_full_baseline_and_never_revives_revoked_history(db):
    old = grant(db)
    accept(db, old)
    with db.session() as session:
        version_id = session.scalar(select(RoadSituationVersion.id))
        sources.revoke_permission(session, old, now=NOW)
        session.commit()
    new = grant(db, expected_generation=2)
    with db.session() as session:
        with pytest.raises(DomainError) as error:
            sources.read_version(session, new, version_id, now=NOW)
        assert error.value.code == "road_version_unavailable"
        with pytest.raises(DomainError) as error:
            sources.read_version(session, old, version_id, now=NOW)
        assert error.value.code == "road_permission_unavailable"
    with pytest.raises(ValueError, match="road_full_baseline_required"):
        accept(db, new, expected_generation=3, mode="delta")
    accept(db, new, expected_generation=3)
    with db.session() as session:
        assert len(sources.read_state(session, new, now=NOW).situations) == 1


def test_policy_content_and_index_tampering_fail_closed(db):
    permission_id = grant(db)
    with db.session() as session:
        row = session.get(RoadSourcePermission, permission_id)
        row.policy = {**row.policy, "notifications_allowed": True}
        session.commit()
    with db.session() as session:
        with pytest.raises(DomainError) as error:
            sources.require_permission(session, permission_id, now=NOW)
        assert error.value.code == "road_permission_invalid"


@pytest.mark.parametrize("target", ["content", "semantic_hash", "content_size", "source_head"])
def test_damaged_evidence_cannot_be_read_or_used_as_reconciliation_baseline(db, target):
    permission_id = grant(db)
    accept(db, permission_id)
    with db.session() as session:
        row = session.scalar(select(RoadSituationVersion))
        if target == "source_head":
            session.get(RoadSourceHead, sources.SOURCE).snapshot_hash = "0" * 64
        else:
            setattr(row, target, {"content": b"{}", "semantic_hash": "0" * 64, "content_size": 1}[target])
        session.commit()
    with db.session() as session:
        with pytest.raises(DomainError) as error:
            sources.read_state(session, permission_id, now=NOW)
        assert error.value.code in {"road_evidence_invalid", "road_state_evidence_invalid"}
    with pytest.raises(DomainError):
        accept(db, permission_id, minute=1, expected_generation=2)
    assert counts(db) == (1, 1, 1, 1)


def test_expiry_and_freshness_use_current_clock_not_saved_receipt(db):
    permission_id = grant(db, valid_until=NOW + timedelta(minutes=1))
    accept(db, permission_id)
    with pytest.raises(DomainError) as error:
        accept(db, permission_id, expected_generation=2, now=NOW + timedelta(minutes=2))
    assert error.value.code == "road_permission_unavailable"
    with db.session() as session:
        with pytest.raises(DomainError) as error:
            sources.read_state(session, permission_id, now=NOW + timedelta(minutes=2))
        assert error.value.code == "road_permission_unavailable"


def test_old_payload_and_fresh_receipt_cannot_refresh_stale_source(db):
    permission_id = grant(db)
    with pytest.raises(DomainError) as error:
        accept(db, permission_id, now=NOW + timedelta(minutes=6))
    assert error.value.code == "road_source_not_current"
    accept(db, permission_id)
    with db.session() as session:
        with pytest.raises(DomainError) as error:
            sources.read_state(session, permission_id, now=NOW + timedelta(minutes=6))
        assert error.value.code == "road_source_stale"


def test_raw_retention_zero_stores_only_filtered_normalized_evidence(db):
    permission_id = grant(db, raw_retention_seconds=0)
    accept(db, permission_id, feed(record(comments=comment() + comment("PRIVATE_SENTINEL", kind="internalNote"))))
    with db.session() as session:
        evidence = session.scalar(select(RoadSourceEvidence))
        version = session.scalar(select(RoadSituationVersion))
        assert evidence.content is None and evidence.content_size > 0
        assert b"PRIVATE_SENTINEL" not in version.content
        assert sources.read_state(session, permission_id, now=NOW).situations


def test_raw_expiry_purges_bytes_without_removing_allowed_derived_history(db):
    permission_id = grant(db, raw_retention_seconds=30)
    accept(db, permission_id)
    with db.session() as session:
        sources.purge_expired(session, now=NOW + timedelta(seconds=31))
        session.commit()
    with db.session() as session:
        assert session.scalar(select(RoadSourceEvidence.content)) is None
        assert sources.read_state(session, permission_id, now=NOW + timedelta(seconds=31)).situations
    assert counts(db) == (1, 1, 1, 1)


def test_delayed_publication_does_not_store_already_expired_raw_bytes(db):
    permission_id = grant(db, raw_retention_seconds=10)
    accept(db, permission_id, now=NOW + timedelta(seconds=11))
    with db.session() as session:
        assert session.scalar(select(RoadSourceEvidence.content)) is None


def test_reconfirmed_unchanged_event_gets_new_evidence_without_new_material_alert(db):
    permission_id = grant(db, raw_retention_seconds=10, derived_retention_seconds=90)
    accept(db, permission_id)
    # Only the publication clock changes. Record creation/version and material
    # facts stay fixed, but this new full response explicitly reconfirms presence.
    xml = feed().replace(f"<publicationTime>{STAMP}</publicationTime>",
        "<publicationTime>2026-09-13T10:01:00Z</publicationTime>")
    with db.session() as session:
        result = sources.accept_snapshot(session, permission_id, xml.encode(), request_id=str(uuid4()),
            expected_generation=2, mode="full", continuous=True, received_at=NOW + timedelta(minutes=1),
            now=NOW + timedelta(minutes=1))
        assert result.change_ids == ()
        session.commit()
    assert counts(db) == (2, 2, 1, 1)
    with db.session() as session:
        sources.purge_expired(session, now=NOW + timedelta(seconds=91))
        session.commit()
    with db.session() as session:
        state = sources.read_state(session, permission_id, now=NOW + timedelta(seconds=91))
        assert state.situations[0].present and state.situations[0].seen_at == NOW + timedelta(minutes=1)


def test_empty_full_baseline_expiry_also_allows_full_refresh(db):
    permission_id = grant(db, raw_retention_seconds=10, derived_retention_seconds=30)
    accept(db, permission_id, feed(situations=""))
    with db.session() as session:
        sources.purge_expired(session, now=NOW + timedelta(seconds=31))
        session.commit()
    accept(db, permission_id, minute=1, expected_generation=3)


def test_permission_switch_back_uses_fresh_index_and_preserves_history(db):
    first = grant(db)
    accept(db, first)
    second = grant(db, expected_generation=2)
    accept(db, second, expected_generation=3)
    with db.session() as session:
        assert sources.activate_permission(session, first, expected_generation=4, now=NOW) == 5
        session.commit()
    accept(db, first, minute=1, expected_generation=5)
    with db.session() as session:
        assert sources.read_state(session, first, now=NOW + timedelta(minutes=1)).situations
        assert session.scalar(select(func.count()).select_from(RoadSituationVersion).where(
            RoadSituationVersion.permission_id == first)) == 2


def test_derived_expiry_purges_history_and_forces_new_full_baseline(db):
    permission_id = grant(db, raw_retention_seconds=10, derived_retention_seconds=30)
    accept(db, permission_id)
    with db.session() as session:
        sources.purge_expired(session, now=NOW + timedelta(seconds=31))
        session.commit()
    assert counts(db) == (0, 0, 0, 0)
    with pytest.raises(DomainError) as error:
        accept(db, permission_id, minute=1, expected_generation=2)
    assert error.value.code == "road_generation_conflict"
    with pytest.raises(ValueError, match="road_full_baseline_required"):
        accept(db, permission_id, minute=1, expected_generation=3, mode="delta")
    accept(db, permission_id, minute=1, expected_generation=3)


def test_revoked_grant_purge_removes_all_retained_bytes_and_old_jobs_cannot_restore(db):
    permission_id = grant(db)
    accept(db, permission_id)
    with db.session() as session:
        sources.revoke_permission(session, permission_id, now=NOW)
        sources.purge_expired(session, now=NOW)
        session.commit()
    assert counts(db) == (0, 0, 0, 0)
    with pytest.raises(DomainError) as error:
        accept(db, permission_id, expected_generation=3)
    assert error.value.code == "road_permission_unavailable"


@pytest.mark.parametrize("limit", ["MAX_STORED_BYTES", "MAX_STATE_BYTES", "MAX_EVIDENCE_ROWS", "MAX_VERSION_ROWS", "MAX_CHANGE_ROWS"])
def test_storage_limit_is_atomic_and_never_drops_existing_closures(db, monkeypatch, limit):
    permission_id = grant(db)
    accept(db, permission_id)
    monkeypatch.setattr(sources, limit, 1)
    with pytest.raises(DomainError):
        accept(db, permission_id, feed(record(code="roadCleared")), minute=1, expected_generation=2)
    assert counts(db) == (1, 1, 1, 1)


def test_exception_after_staging_versions_rolls_back_all_partial_writes(db):
    permission_id = grant(db)
    accept(db, permission_id)
    original = sources.RoadSourceChange

    def fail(**kwargs):
        raise RuntimeError("synthetic failure before history publication")

    # _capacity needs the mapped class. Raise only when constructing the new row.
    from sqlalchemy import event

    def fail_insert(_mapper, _connection, _target):
        fail()

    event.listen(original, "before_insert", fail_insert)
    try:
        with pytest.raises(RuntimeError, match="synthetic failure"):
            accept(db, permission_id, feed(record(code="roadCleared")), minute=1, expected_generation=2)
    finally:
        event.remove(original, "before_insert", fail_insert)
    assert counts(db) == (1, 1, 1, 1)
    accept(db, permission_id, feed(record(code="roadCleared")), minute=1, expected_generation=2)


def test_foreign_keys_prevent_cross_permission_current_binding(db):
    permission_id = grant(db)
    accept(db, permission_id)
    other = grant(db, selected=False)
    with db.session() as session:
        version_id = session.scalar(select(RoadSituationVersion.id))
        with pytest.raises(IntegrityError):
            session.add(RoadCurrentSituation(permission_id=other, source_id="event-1", version_id=version_id,
                                            seen_at=NOW, present=True))
            session.flush()


def test_migration_matches_road_metadata_and_roundtrip_preserves_existing_tables(db):
    with db.engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"include_object":
            lambda obj, name, kind, reflected, compare_to: name.startswith("road_") if kind == "table" else True})
        assert compare_metadata(context, Base.metadata) == []
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "e1bd3f8c6fe3")
        tables = inspect(connection).get_table_names()
        assert not any(name.startswith("road_") for name in tables)
        assert "commute_static_archives" in tables and "tender_monitors" in tables and "users" in tables
        command.upgrade(config, "head")
        assert len([name for name in inspect(connection).get_table_names() if name.startswith("road_")]) == 16
