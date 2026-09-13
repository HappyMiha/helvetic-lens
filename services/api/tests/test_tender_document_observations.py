from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from test_tender_documents import capture, seed
from test_tender_matching import NOW
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens import tender_document_observations as observations
from helvetic_lens import tender_documents as documents
from helvetic_lens import tender_email_preferences as email
from helvetic_lens import tender_repository as tenders
from helvetic_lens.config import DomainError
from helvetic_lens.document_sets import DocumentItem, Manifest
from helvetic_lens.models import User
from helvetic_lens.tender_models import (
    TenderDelivery,
    TenderDocumentAccess,
    TenderDocumentObservation,
    TenderDossierVersion,
    TenderMonitor,
)


def item(db, dossier, snapshot, *, kind="document"):
    with db.session() as session:
        row, parsed = documents.read(session, "owner", dossier, snapshot, now=NOW, check_item_access=False)
        return DocumentItem(item_id=row.item_id, kind=kind, title=row.item_id,
                            official_url="https://www.simap.ch/en/project-detail/fixture",
                            access="available", content_sha256=row.content_sha256,
                            snapshot_id=UUID(row.id), parse_status="complete", text_sha256=parsed.text_sha256)


def record(db, dossier, grant, step, *items, coverage="complete", observation_id=None):
    value = Manifest(observation_id=observation_id or uuid4(), source_id="simap", dossier_id=dossier,
                     access_scope_id=UUID(grant), observed_at=NOW + timedelta(seconds=step),
                     coverage=coverage, items=items)
    with db.session() as session:
        result = observations.observe(session, "owner", dossier, value, now=NOW + timedelta(seconds=max(step, 60)))
        session.commit()
    return result, value


def test_material_file_and_qa_revision_reopens_decision_and_queues_same_publication_email(db):
    monitor, dossier, grant, _ = seed(db)
    initial = item(db, dossier, capture(db, dossier, grant))
    baseline, _ = record(db, dossier, grant, 1, initial)
    with db.session() as session:
        before = tenders.get_dossier(session, "owner", dossier, now=NOW)
        assert before["sequence"] == 1  # Baseline must not supersede discovery mail.
        tenders.record_decision(session, "owner", dossier, version=before["version"], sequence=1,
                                decision="bid", key="original-review", now=NOW)
        session.get(User, "owner").email_verified_at = NOW
        email.configure(session, "owner", monitor["id"], expected_version=1,
                        configuration={"delivery": {"email": "immediate"}}, consent=True, now=NOW)
        session.commit()
    replacement = item(db, dossier, capture(db, dossier, grant, b"5 references required"))
    qa = item(db, dossier, capture(db, dossier, grant, b"Q&A version 3", item_id="qa-v3"), kind="qa")
    changed, value = record(db, dossier, grant, 2, replacement, qa)
    with db.session() as session:
        after = tenders.get_dossier(session, "owner", dossier, now=NOW + timedelta(minutes=1))
        assert after["sequence"] == 2 and after["kind"] == "material_update"
        assert after["source_hash"] == before["source_hash"]
        assert after["decision"] == "bid" and after["reviewed_sequence"] == 1
        assert after["review_state"] == "needs_review" and after["document_observation_id"] == changed
        row, state = observations.read_observation(session, "owner", dossier, changed, now=NOW)
        assert row.previous_id == baseline
        assert {(delta["item_id"], delta["kind"]) for delta in row.deltas} == {
            ("requirements", "replaced"), ("qa-v3", "added"),
        }
        assert len(state.documents) == 2
        compared = observations.comparison(session, "owner", dossier, changed, "requirements", now=NOW)
        assert compared["status"] == "changed"
        assert compared["changes"][0]["before"][0]["text"] == "3 references required"
        assert compared["changes"][0]["after"][0]["text"] == "5 references required"
        page = observations.view(session, "owner", dossier, changed, now=NOW, limit=1)
        assert len(page["items"]) == 1 and page["next_cursor"]
        later = observations.view(session, "owner", dossier, changed, now=NOW, limit=1, after_item=page["next_cursor"])
        assert len(later["items"]) == 1 and later["next_cursor"] is None
        assert session.scalar(select(func.count()).select_from(TenderDelivery)) == 1
        intent = session.scalar(select(TenderDelivery))
        assert intent.evidence_version_id == after["evidence_version_id"]
    # Exact retry and a later reordered identical poll do not create more versions/mail.
    with db.session() as session:
        assert observations.observe(session, "owner", dossier, value, now=NOW + timedelta(minutes=1)) == changed
        session.commit()
    assert record(db, dossier, grant, 3, qa, replacement)[0] == changed
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(TenderDossierVersion)) == 2
        assert session.scalar(select(func.count()).select_from(TenderDelivery)) == 1


def test_stale_conflicting_and_wrong_scope_observations_do_not_rewrite_history(db):
    _, dossier, grant, _ = seed(db)
    original = item(db, dossier, capture(db, dossier, grant))
    baseline, value = record(db, dossier, grant, 3, original)
    with pytest.raises(ValueError, match="advance"):
        record(db, dossier, grant, 2, original)
    with db.session() as session, pytest.raises(ValueError, match="Conflicting"):
        observations.observe(session, "owner", dossier,
                             value.model_copy(update={"coverage": "partial"}), now=NOW + timedelta(minutes=1))
    with db.session() as session, pytest.raises(ValueError, match="private dossier"):
        observations.observe(session, "owner", dossier,
                             value.model_copy(update={"dossier_id": str(uuid4())}), now=NOW + timedelta(minutes=1))
    with db.session() as session:
        assert observations.latest(session, grant).id == baseline


def test_explicit_item_denial_closes_retained_original_until_proven_restore(db):
    _, dossier, grant, _ = seed(db)
    identifier = capture(db, dossier, grant)
    original = item(db, dossier, identifier)
    record(db, dossier, grant, 1, original)
    denied = DocumentItem(item_id=original.item_id, kind="document", title="Unavailable",
                          official_url=original.official_url, access="denied")
    record(db, dossier, grant, 2, denied)
    with db.session() as session:
        assert documents.index(session, "owner", dossier, now=NOW)["items"] == []
        with pytest.raises(DomainError):
            documents.read(session, "owner", dossier, identifier, now=NOW)
    record(db, dossier, grant, 3, original)
    with db.session() as session:
        assert documents.read(session, "owner", dossier, identifier, now=NOW)[0].body


def test_grant_revocation_closes_document_only_dossier_review_and_history(db):
    _, dossier, grant, _ = seed(db)
    record(db, dossier, grant, 1, item(db, dossier, capture(db, dossier, grant)))
    observed, _ = record(db, dossier, grant, 2, item(db, dossier, capture(db, dossier, grant, b"5 references")))
    with db.session() as session:
        session.get(TenderDocumentAccess, grant).revoked_at = NOW
        session.commit()
        with pytest.raises(DomainError):
            observations.read_observation(session, "owner", dossier, observed, now=NOW)
        with pytest.raises(DomainError):
            tenders.get_dossier(session, "owner", dossier, now=NOW)


def test_manifest_budget_rolls_back_clock_and_evidence_without_losing_baseline(db, monkeypatch):
    _, dossier, grant, _ = seed(db)
    original = item(db, dossier, capture(db, dossier, grant))
    baseline, _ = record(db, dossier, grant, 1, original)
    replacement = item(db, dossier, capture(db, dossier, grant, b"5 references"))
    monkeypatch.setattr(documents, "MAX_DOSSIER_BYTES", 1)
    with pytest.raises(DomainError, match="capacity"):
        record(db, dossier, grant, 2, replacement)
    with db.session() as session:
        assert observations.latest(session, grant).id == baseline
        assert session.get(TenderDocumentAccess, grant).last_observation_id == baseline
        assert session.scalar(select(func.count()).select_from(TenderDossierVersion)) == 1


def test_retention_purges_manifest_content_and_leaves_bound_history_unavailable(db):
    _, dossier, grant, _ = seed(db)
    baseline, _ = record(db, dossier, grant, 1, item(db, dossier, capture(db, dossier, grant)))
    documents.cleanup(db, now=NOW + timedelta(days=3))
    with db.session() as session:
        row = session.get(TenderDocumentObservation, baseline)
        assert row.state is None and row.deltas is None and row.stored_bytes == 0 and row.fingerprint
        with pytest.raises(DomainError):
            observations.state_of(row)


def test_archive_rejects_new_manifest_without_creating_a_version(db):
    monitor, dossier, grant, _ = seed(db)
    original = item(db, dossier, capture(db, dossier, grant))
    with db.session() as session:
        session.get(TenderMonitor, monitor["id"]).status = "archived"
        session.commit()
    with pytest.raises(DomainError, match="not active"):
        record(db, dossier, grant, 1, original)


def test_later_item_denial_masks_earlier_history_title_and_comparison_text(db):
    _, dossier, grant, _ = seed(db)
    record(db, dossier, grant, 1, item(db, dossier, capture(db, dossier, grant)))
    revised = item(db, dossier, capture(db, dossier, grant, b"5 references"))
    changed, _ = record(db, dossier, grant, 2, revised)
    denied = DocumentItem(item_id=revised.item_id, kind="document", title="Unavailable",
                          official_url=revised.official_url, access="denied")
    record(db, dossier, grant, 3, denied)
    with db.session() as session:
        page = observations.view(session, "owner", dossier, changed, now=NOW)
        assert page["items"][0]["title"] is None and page["items"][0]["snapshot_id"] is None
        result = observations.comparison(session, "owner", dossier, changed, "requirements", now=NOW)
        assert result["status"] == "unavailable" and result["reason"] == "read_unavailable"
        assert "references" not in str(result)
        with pytest.raises(DomainError):
            tenders.get_dossier(session, "owner", dossier, now=NOW)


def test_new_approved_grant_restores_a_baseline_without_claiming_a_specific_change(db):
    _, dossier, grant, raw = seed(db)
    record(db, dossier, grant, 1, item(db, dossier, capture(db, dossier, grant)))
    record(db, dossier, grant, 2, item(db, dossier, capture(db, dossier, grant, b"5 references")))
    with db.session() as session:
        session.get(TenderDocumentAccess, grant).revoked_at = NOW
        renewed = documents.record_access(session, "owner", dossier, source_id="simap", publication_id=raw["id"],
                                          account_reference="renewed-fixture-account", policy_reference="renewed-fixture-policy",
                                          valid_until=NOW + timedelta(days=2), retain_until=NOW + timedelta(days=3), now=NOW)
        renewed_id = renewed.id
        session.commit()
    record(db, dossier, renewed_id, 3, item(db, dossier, capture(db, dossier, renewed_id, b"5 references")))
    with db.session() as session:
        view = tenders.get_dossier(session, "owner", dossier, now=NOW)
        assert view["sequence"] == 3 and view["kind"] == "source_update"
        assert view["changes"][0]["kind"] == "coverage_changed"
