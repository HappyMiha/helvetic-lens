"""Real journal/page transactions with synthetic publisher XML and reviewed fixtures."""

import xml.etree.ElementTree as ET
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from test_ipi_protocol import HEADERS, record, response
from test_trademark_sources import NOW, grant
from test_trademark_sources import db as _database_fixture
from test_trademark_sources import template as _template_fixture

from helvetic_lens import ipi_acquisition as ipi
from helvetic_lens import trademark_sources as source
from helvetic_lens.config import DomainError
from helvetic_lens.ipi_models import IPIAlias, IPIIdentity, IPIPageEvidence, IPISeenIdentity, IPITraversal
from helvetic_lens.ipi_protocol import CORE, IPIProtocolError, q
from helvetic_lens.trademark_source_models import (
    TrademarkRegisterRevision,
    TrademarkSourcePermission,
    TrademarkSourceSelection,
)

db, template = _database_fixture, _template_fixture


def permission(db, **changes):
    return grant(db, endpoint=ipi.ENDPOINT, origins=tuple(sorted(ipi.ORIGINS)), **changes)


def claim(db, permission_id, now=NOW):
    with db.session() as session:
        result = ipi.claim(session, permission_id, now=now)
        session.commit()
        return result


def page(ticket, *, records=None, offset=0, total=None, continuation=None):
    records = [record()] if records is None else records
    wrapper = f'<api:Continuations><api:Continuation name="NextPage">{continuation}</api:Continuation></api:Continuations>' if continuation else ""
    root = ET.fromstring(response(payload=b"", count=len(records), total=len(records) if total is None else total,
        offset=offset, continuation=wrapper))
    root.set("requestUuid", ticket["request_uuid"])
    for raw in records:
        element = ET.SubElement(root[0], q(CORE, "Data"), {"id": "reused-response-id", "role": "Trademark"})
        element.append(ET.fromstring(raw))
    return ET.tostring(root)


def admit(db, ticket, payload, now=NOW):
    with db.session() as session:
        result = ipi.admit(session, ticket, status=200, headers=HEADERS, payload=payload, now=now, received_at=now)
        session.commit()
        return result


def counts(db):
    with db.session() as session:
        return tuple(session.scalar(select(func.count()).select_from(model)) for model in
            (IPIIdentity, IPIAlias, IPISeenIdentity, IPIPageEvidence, TrademarkRegisterRevision))


def another_record():
    return record().replace(b"12345/2026", b"99999/2026").replace(b"123456", b"999999")


def test_native_pages_resume_after_session_restart_and_reach_current_journal(db):
    approved = permission(db)
    first = claim(db, approved)
    body = page(first, total=2, continuation="opaque-first")
    accepted = admit(db, first, body)
    assert accepted["traversal"]["state"] == "running"
    assert claim(db, approved)["state"] == "waiting"
    assert admit(db, first, body)["replayed"]
    second = claim(db, approved, NOW + timedelta(seconds=3))
    assert second["page_index"] == 1 and b"opaque-first" in second["request"]
    assert second["request_uuid"] != first["request_uuid"]
    accepted = admit(db, second, page(second, records=[another_record()], offset=1, total=2), NOW + timedelta(seconds=3))
    assert accepted["traversal"]["state"] == "completed"
    assert accepted["traversal"]["unique_count"] == 2
    assert accepted["traversal"]["duplicate_count"] == 0
    assert not accepted["coverage_verified"]
    with db.session() as session:
        current = source.read_current(session, "synthetic-ipi", now=NOW + timedelta(seconds=4))
        assert len(current["items"]) == 2
        evidence = session.get(IPIPageEvidence, (first["traversal_id"], 0))
        assert evidence.raw_payload == body and evidence.response_hash == source._hash(body)
    assert claim(db, approved, NOW + timedelta(seconds=5))["state"] == "waiting"


def test_invalid_second_record_rolls_back_first_record_aliases_and_checkpoint(db):
    ticket = claim(db, permission(db))
    invalid = another_record().replace(b"V7_1", b"V8_0")
    with pytest.raises(IPIProtocolError, match="ipi_st96_version_unavailable"):
        admit(db, ticket, page(ticket, records=[record(), invalid]))
    assert counts(db) == (0, 0, 0, 0, 0)
    with db.session() as session:
        scan = session.get(IPITraversal, ticket["traversal_id"])
        assert scan.page_count == 0 and scan.lease_token == ticket["lease_token"]
        assert session.get(TrademarkSourceSelection, "synthetic-ipi").cursor_version == 0
    assert admit(db, ticket, page(ticket))["traversal"]["state"] == "completed"


def test_reappearing_updated_record_preserves_identity_change_and_traversal_limits(db):
    approved = permission(db)
    first = claim(db, approved)
    admit(db, first, page(first, total=2, continuation="next"))
    second = claim(db, approved, NOW + timedelta(seconds=3))
    changed = record().replace(b"Synthetic Owner AG", b"New Owner AG")
    result = admit(db, second, page(second, records=[changed], offset=1, total=2), NOW + timedelta(seconds=3))
    assert result["traversal"]["unique_count"] == result["traversal"]["duplicate_count"] == 1
    assert not result["traversal"]["coverage_verified"]
    assert counts(db)[0] == 1 and counts(db)[-1] == 2


def test_changing_publisher_total_is_retained_without_a_snapshot_claim(db):
    approved = permission(db)
    first = claim(db, approved)
    admit(db, first, page(first, total=3, continuation="next"))
    second = claim(db, approved, NOW + timedelta(seconds=3))
    result = admit(db, second, page(second, records=[another_record()], offset=1, total=2), NOW + timedelta(seconds=3))
    assert result["traversal"]["totals_changed"]
    assert result["traversal"]["state"] == "completed"
    assert result["traversal"]["last_reported_total"] == 2
    assert not result["coverage_verified"]


@pytest.mark.parametrize("problem", ["offset", "cycle", "request_id"])
def test_bad_continuation_page_does_not_advance_journal(db, problem):
    approved = permission(db)
    first = claim(db, approved)
    admit(db, first, page(first, total=3, continuation="same-token"))
    second = claim(db, approved, NOW + timedelta(seconds=3))
    body = page(second, records=[another_record()], offset=0 if problem == "offset" else 1, total=3,
        continuation="same-token" if problem == "cycle" else "other-token")
    if problem == "request_id":
        body = body.replace(second["request_uuid"].encode(), b"unrelated-request")
    before = counts(db)
    with pytest.raises((DomainError, IPIProtocolError)):
        admit(db, second, body, NOW + timedelta(seconds=3))
    assert counts(db) == before


def test_reclaimed_lease_and_source_replacement_reject_inflight_old_response(db):
    approved = permission(db)
    first = claim(db, approved)
    assert claim(db, approved)["state"] == "busy"
    later = NOW + timedelta(seconds=ipi.LEASE_SECONDS + 1)
    second = claim(db, approved, later)
    assert second["lease_token"] != first["lease_token"]
    with pytest.raises(DomainError, match="Trademark"):
        admit(db, first, page(first), later)
    permission(db, generation=1)
    with pytest.raises(DomainError):
        admit(db, second, page(second), later)
    assert counts(db) == (0, 0, 0, 0, 0)


def test_revocation_prevents_admission_and_erases_retained_parent_and_checkpoint(db):
    approved = permission(db)
    first = claim(db, approved)
    admit(db, first, page(first, total=2, continuation="private-opaque-token"))
    second = claim(db, approved, NOW + timedelta(seconds=3))
    with db.session() as session:
        session.get(TrademarkSourcePermission, approved).revoked_at = NOW + timedelta(seconds=4)
        session.commit()
    with pytest.raises(DomainError):
        admit(db, second, page(second, offset=1, total=2), NOW + timedelta(seconds=5))
    with db.session() as session:
        ipi.cleanup(session, now=NOW + timedelta(seconds=5))
        session.commit()
        assert session.get(IPIPageEvidence, (first["traversal_id"], 0)).raw_payload is None
        assert session.get(IPITraversal, first["traversal_id"]).next_request is None


def test_retry_after_persists_and_is_never_shortened_by_restarting_worker(db):
    approved = permission(db)
    ticket = claim(db, approved)
    with db.session() as session:
        result = ipi.fail(session, ticket, code="ipi_http_429", now=NOW, retry_after_seconds=86401)
        session.commit()
    assert result["next_attempt_at"] == (NOW + timedelta(seconds=86401)).isoformat()
    assert claim(db, approved, NOW + timedelta(seconds=86400))["state"] == "waiting"
    # Token expired during the required wait: abandon explicitly, never reuse expired bytes.
    result = claim(db, approved, NOW + timedelta(seconds=86401))
    assert result["state"] == "abandoned" and result["last_error"] == "ipi_continuation_expired"


def test_missing_canonical_alias_is_explicit_not_a_second_business_identity(db):
    approved = permission(db)
    first = claim(db, approved)
    admit(db, first, page(first, total=2, continuation="next"))
    second = claim(db, approved, NOW + timedelta(seconds=3))
    renamed_application = record().replace(b"12345/2026", b"54321/2026")
    before = counts(db)
    with pytest.raises(DomainError) as error:
        admit(db, second, page(second, records=[renamed_application], offset=1, total=2), NOW + timedelta(seconds=3))
    assert error.value.code == "ipi_canonical_alias_missing"
    assert counts(db) == before


def test_known_alias_collision_cannot_merge_two_existing_register_identities(db):
    approved = permission(db)
    first = claim(db, approved)
    admit(db, first, page(first, records=[record(), another_record()], total=3, continuation="next"))
    second = claim(db, approved, NOW + timedelta(seconds=3))
    collision = record().replace(b"123456", b"999999")
    with pytest.raises(DomainError) as error:
        admit(db, second, page(second, records=[collision], offset=2, total=3), NOW + timedelta(seconds=3))
    assert error.value.code == "ipi_identity_conflict"
    assert counts(db)[0] == 2


def test_native_ingestion_drives_private_review_and_reopens_material_changes(db):
    from test_trademark_workflow import create, review, rows, sync

    from helvetic_lens import trademark_workflow as workflow
    from helvetic_lens.trademark_models import TrademarkMonitor

    approved = permission(db, private_decisions_allowed=True)
    first = claim(db, approved)
    admit(db, first, page(first, total=2, continuation="updated-item"))
    monitor = create(db)
    with db.session() as session:
        workflow.start(session, "owner", monitor, 1, now=NOW)
        session.commit()
    sync(db, monitor)
    candidate, = rows(db, monitor)
    assert candidate["facts"]["mark"] == "ALMORA"
    assert candidate["facts"]["source_document_sha256"]
    review(db, monitor, row=candidate, decision="relevant")
    second = claim(db, approved, NOW + timedelta(seconds=3))
    changed = record().replace(b"Synthetic Owner AG", b"Native Corrected Owner AG")
    admit(db, second, page(second, records=[changed], offset=1, total=2), NOW + timedelta(seconds=3))
    sync(db, monitor, NOW + timedelta(seconds=3))
    updated, = rows(db, monitor, NOW + timedelta(seconds=3))
    assert updated["id"] == candidate["id"]
    assert updated["facts"]["owners"] == ["Native Corrected Owner AG"]
    assert updated["needs_review"]
    with db.session() as session:
        with pytest.raises(DomainError):
            workflow.list_candidates(session, "peer", monitor, now=NOW + timedelta(seconds=3))
    with db.organization_context("org-b"):
        with db.session() as session:
            assert session.get(TrademarkMonitor, monitor) is None


def test_native_schema_roundtrip_matches_models_and_keeps_private_portfolios(db):
    from pathlib import Path

    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from test_trademark_workflow import create

    from alembic import command
    from helvetic_lens.db import Base
    from helvetic_lens.trademark_models import TrademarkMonitor

    monitor = create(db)
    with db.engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"include_object":
            lambda obj, name, kind, reflected, compare_to: name.startswith("ipi_") if kind == "table" else True})
        assert compare_metadata(context, Base.metadata) == []
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "c5a28346e4c7")
        assert connection.execute(select(TrademarkMonitor.id).where(TrademarkMonitor.id == monitor)).scalar() == monitor
        command.upgrade(config, "head")
        assert compare_metadata(context, Base.metadata) == []
