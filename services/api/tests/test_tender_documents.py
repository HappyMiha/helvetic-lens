from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, event, select, update
from test_tender_matching import NOW
from test_tender_repository import create, ingest, publication
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens import tender_documents as documents
from helvetic_lens.config import DomainError
from helvetic_lens.document_parsing import parse_document
from helvetic_lens.tender_models import TenderDocumentAccess, TenderDocumentSnapshot, TenderMonitor
from helvetic_lens.tender_rights import restrict


def seed(db):
    monitor = create(db, active=True)
    raw = publication()
    dossier = ingest(db, monitor, raw)[0]
    with db.session() as session:
        grant = documents.record_access(session, "owner", dossier, source_id="simap",
                                        publication_id=raw["id"], account_reference="fixture-account",
                                        policy_reference="fixture-reviewed-policy",
                                        valid_until=NOW + timedelta(days=2), retain_until=NOW + timedelta(days=3), now=NOW)
        grant_id = grant.id
        session.commit()
    return monitor, dossier, grant_id, raw


def capture(db, dossier, grant_id, body=b"3 references required", *, item_id="requirements"):
    parsed, _ = parse_document(body, content_type="text/plain", snapshot_id=uuid4(),
                               access_scope_id=UUID(grant_id), source_id="simap", dossier_id=dossier,
                               item_id=item_id, language="en")
    with db.session() as session:
        identifier = documents.store(session, "owner", dossier, parsed, body, content_type="text/plain", now=NOW)
        session.commit()
    return identifier


def test_restart_deduplicates_same_private_projection_and_index_never_loads_bodies(db):
    _, dossier, grant, _ = seed(db)
    first = capture(db, dossier, grant)
    assert capture(db, dossier, grant) == first
    db.engine.dispose()
    statements = []

    def inspect_sql(conn, cursor, statement, params, context, many):
        statements.append(statement)

    event.listen(db.engine, "before_cursor_execute", inspect_sql)
    try:
        with db.session() as session:
            result = documents.index(session, "owner", dossier, now=NOW)
    finally:
        event.remove(db.engine, "before_cursor_execute", inspect_sql)
    assert len(result["items"]) == 1 and result["items"][0]["id"] == first
    assert all("tender_document_snapshots.body" not in text and "tender_document_snapshots.parsed" not in text for text in statements)
    assert "fixture-account" not in str(result) and "fixture-reviewed-policy" not in str(result)
    with db.session() as session:
        original, parsed = documents.read(session, "owner", dossier, first, now=NOW)
        assert original.body == b"3 references required"
        assert parsed.passages[0].text == "3 references required"


def test_private_documents_are_hidden_from_peer_and_other_tenant(db):
    _, dossier, grant, _ = seed(db)
    identifier = capture(db, dossier, grant)
    with db.session() as session:
        with pytest.raises(DomainError):
            documents.read(session, "peer", dossier, identifier, now=NOW)
        with pytest.raises(DomainError):
            documents.index(session, "peer", dossier, now=NOW)
    with db.organization_context("org-b"), db.session() as session:
        with pytest.raises(DomainError):
            documents.read(session, "owner", dossier, identifier, now=NOW)


@pytest.mark.parametrize("reason", ["expired", "revoked", "source_withdrawal"])
def test_current_permission_is_rechecked_before_listing_or_download(db, reason):
    _, dossier, grant, raw = seed(db)
    identifier = capture(db, dossier, grant)
    clock = NOW
    with db.session() as session:
        if reason == "expired":
            clock += timedelta(days=2)
        elif reason == "revoked":
            session.get(TenderDocumentAccess, grant).revoked_at = NOW
        else:
            restrict(session, scope="publication", target_id=raw["id"], policy_reference="fixture withdrawal", now=NOW)
        session.commit()
    with db.session() as session:
        assert documents.index(session, "owner", dossier, now=clock)["items"] == []
        with pytest.raises(DomainError):
            documents.read(session, "owner", dossier, identifier, now=clock)
        # Retention is separate from current read access.
        assert session.get(TenderDocumentSnapshot, identifier).body is not None


def test_expired_retention_purges_bounded_payloads_and_preserves_unavailable_references(db):
    _, dossier, grant, _ = seed(db)
    ids = [capture(db, dossier, grant, f"version {i}".encode()) for i in range(2)]
    with db.session() as session:
        assert documents.purge_expired(session, now=NOW + timedelta(days=2)) == 0
        assert documents.purge_expired(session, now=NOW + timedelta(days=3), limit=1) == 1
        session.commit()
    with db.session() as session:
        assert documents.purge_expired(session, now=NOW + timedelta(days=3)) == 1
        assert documents.purge_expired(session, now=NOW + timedelta(days=3)) == 0
        session.commit()
        for identifier in ids:
            row = session.get(TenderDocumentSnapshot, identifier)
            assert row.body is None and row.parsed is None and row.stored_bytes == 0
            assert row.content_sha256 and row.purged_at


def test_storage_budget_preserves_originals_and_pause_blocks_new_capture(db, monkeypatch):
    monitor, dossier, grant, _ = seed(db)
    first = capture(db, dossier, grant)
    monkeypatch.setattr(documents, "MAX_DOSSIER_SNAPSHOTS", 1)
    with pytest.raises(DomainError, match="capacity"):
        capture(db, dossier, grant, b"5 references required")
    assert capture(db, dossier, grant) == first
    with db.session() as session:
        session.execute(update(TenderMonitor).where(TenderMonitor.id == monitor["id"]).values(status="paused"))
        session.commit()
    with pytest.raises(DomainError, match="active monitor"):
        capture(db, dossier, grant)
    with db.session() as session:
        assert documents.read(session, "owner", dossier, first, now=NOW)[0].body == b"3 references required"


@pytest.mark.parametrize("target", ["body", "parsed"])
def test_corrupted_stored_evidence_fails_before_any_original_is_returned(db, target):
    _, dossier, grant, _ = seed(db)
    identifier = capture(db, dossier, grant)
    with db.session() as session:
        row = session.get(TenderDocumentSnapshot, identifier)
        if target == "body":
            row.body = b"forged original"
        else:
            row.parsed = {**row.parsed, "source_id": "different source"}
        session.commit()
    with db.session() as session, pytest.raises(DomainError, match="integrity"):
        documents.read(session, "owner", dossier, identifier, now=NOW)


def test_dossier_delete_cascades_only_its_private_grants_and_originals(db):
    monitor, dossier, grant, _ = seed(db)
    capture(db, dossier, grant)
    with db.session() as session:
        session.execute(delete(TenderMonitor).where(TenderMonitor.id == monitor["id"]))
        session.commit()
        assert session.scalar(select(TenderDocumentAccess.id)) is None
        assert session.scalar(select(TenderDocumentSnapshot.id)) is None


def test_quota_spans_grant_renewals_and_preserves_existing_payloads(db, monkeypatch):
    _, dossier, grant, raw = seed(db)
    identifier = capture(db, dossier, grant)
    with db.session() as session:
        size = session.get(TenderDocumentSnapshot, identifier).stored_bytes
        renewal = documents.record_access(session, "owner", dossier, source_id="simap",
                                          publication_id=raw["id"], account_reference="renewed-fixture-account",
                                          policy_reference="renewed-fixture-policy", now=NOW,
                                          valid_until=NOW + timedelta(days=2), retain_until=NOW + timedelta(days=3))
        renewal_id = renewal.id
        session.commit()
    monkeypatch.setattr(documents, "MAX_DOSSIER_BYTES", size)
    with pytest.raises(DomainError, match="capacity"):
        capture(db, dossier, renewal_id, b"5 references required")
    with db.session() as session:
        assert len(documents.index(session, "owner", dossier, now=NOW)["items"]) == 1


def test_global_retention_cleanup_crosses_tenants_without_disclosing_or_mixing_originals(db):
    _, dossier_a, grant_a, _ = seed(db)
    a = capture(db, dossier_a, grant_a)
    with db.organization_context("org-b"):
        _, dossier_b, grant_b, _ = seed(db)
        b = capture(db, dossier_b, grant_b)
    assert a != b
    assert documents.cleanup(db, now=NOW + timedelta(days=3)) == {"purged": 2}
    with db.session(include_all_organizations=True) as session:
        assert all(row.body is None for row in session.scalars(select(TenderDocumentSnapshot)))


def test_access_grant_cannot_point_at_an_unrelated_publication(db):
    _, dossier, _, _ = seed(db)
    with db.session() as session, pytest.raises(ValueError, match="retained dossier"):
        documents.record_access(session, "owner", dossier, source_id="simap", publication_id=str(uuid4()),
                                account_reference="fixture-account", policy_reference="fixture-policy", now=NOW,
                                valid_until=NOW + timedelta(days=2), retain_until=NOW + timedelta(days=3))
