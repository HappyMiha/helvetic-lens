from copy import deepcopy

import pytest
from sqlalchemy import select
from test_tender_document_observations import item, record
from test_tender_documents import capture, seed
from test_tender_matching import NOW
from test_tender_repository import create, decide, ingest, publication, read, revised
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens.config import DomainError
from helvetic_lens.tender_models import TenderDocumentAccess, TenderDossierVersion
from helvetic_lens.tender_review_changes import review_changes
from helvetic_lens.tender_rights import restrict


def window(db, dossier, *, through=3, reviewed=1, **kwargs):
    with db.session() as session:
        return review_changes(session, "owner", dossier, through_sequence=through,
                              reviewed_sequence=reviewed, now=NOW, **kwargs)


def public_changes(db):
    monitor, raw = create(db, active=True), publication()
    dossier = ingest(db, monitor, raw)[0]
    decide(db, read(db, dossier))
    changed = revised(raw)
    changed["dates"]["offerDeadline"] = "2026-10-23T15:00:00+02:00"
    ingest(db, monitor, changed)
    last = revised(changed, ordinal=3)
    last["terms"]["termsCriteria"][0]["description"]["en"] = "5 references required"
    ingest(db, monitor, last)
    return dossier, monitor, raw, changed, last


def test_chronological_window_keeps_earlier_deadline_and_later_terms_with_bounded_pages(db):
    dossier, _, _, _, _ = public_changes(db)
    assert {change["field"] for change in read(db, dossier)["changes"]} == {"terms"}
    first = window(db, dossier, limit=1)
    assert first["reviewed_sequence"] == 1 and first["through_sequence"] == 3
    assert first["next_cursor"] == 2
    assert [change["field"] for change in first["items"][0]["changes"]] == ["deadline"]
    second = window(db, dossier, limit=1, after_sequence=first["next_cursor"])
    assert second["next_cursor"] is None and second["items"][0]["sequence"] == 3
    assert [change["field"] for change in second["items"][0]["changes"]] == ["terms"]
    decide(db, read(db, dossier), key="review-all")
    assert window(db, dossier, reviewed=3)["items"] == []
    with pytest.raises(DomainError) as stale:
        window(db, dossier, after_sequence=2)
    assert stale.value.status == 409


def test_new_evidence_invalidates_pagination_and_an_unreviewed_dossier_includes_discovery(db):
    dossier, monitor, _, _, last = public_changes(db)
    ingest(db, monitor, revised(last, ordinal=4))
    with pytest.raises(DomainError) as stale:
        window(db, dossier, after_sequence=2)
    assert stale.value.status == 409
    monitor = create(db, active=True, key="unreviewed")
    new = ingest(db, monitor, publication())[0]
    history = window(db, new, reviewed=0, through=1)
    assert history["reviewed_sequence"] is None
    assert history["items"][0]["sequence"] == 1 and history["items"][0]["available"]


def test_denied_intermediate_publication_is_a_visible_gap_and_integrity_errors_propagate(db):
    dossier, _, _, changed, _ = public_changes(db)
    with db.session() as session:
        restrict(session, scope="publication", target_id=changed["id"], policy_reference="fixture", now=NOW)
        session.commit()
    result = window(db, dossier)
    assert result["items"][0] == {"id": result["items"][0]["id"], "sequence": 2, "available": False}
    assert result["items"][1]["available"]
    with db.session() as session:
        row = session.scalar(select(TenderDossierVersion).where(
            TenderDossierVersion.dossier_id == dossier, TenderDossierVersion.sequence == 3))
        damaged = deepcopy(row.snapshot.evidence)
        damaged["original"]["dates"]["offerDeadline"] = "2026-11-23T15:00:00+02:00"
        row.snapshot.evidence = damaged
        session.commit()
    with pytest.raises(DomainError) as invalid:
        window(db, dossier)
    assert invalid.value.status == 503


def test_private_document_replacements_and_reversal_remain_before_public_update(db):
    monitor, dossier, grant, raw = seed(db)
    original = item(db, dossier, capture(db, dossier, grant))
    record(db, dossier, grant, 1, original)
    decide(db, read(db, dossier))
    replacement = item(db, dossier, capture(db, dossier, grant, b"5 references required"))
    changed, _ = record(db, dossier, grant, 2, replacement)
    reversed_id, _ = record(db, dossier, grant, 3, original)
    public = revised(raw)
    public["dates"]["offerDeadline"] = "2026-10-23T15:00:00+02:00"
    ingest(db, monitor, public)
    result = window(db, dossier, through=4)
    assert [entry["sequence"] for entry in result["items"]] == [2, 3, 4]
    assert [entry["document_observation_id"] for entry in result["items"][:2]] == [changed, reversed_id]
    assert [entry["changes"][0]["field"] for entry in result["items"]] == ["documents", "documents", "deadline"]
    # Current grant withdrawal hides both earlier private changes, while keeping
    # the later permitted public update and explicit unavailable history slots.
    with db.session() as session:
        session.get(TenderDocumentAccess, grant).revoked_at = NOW
        session.commit()
    result = window(db, dossier, through=4)
    assert [entry["available"] for entry in result["items"]] == [False, False, True]
    assert all("document_observation_id" not in entry for entry in result["items"][:2])


def test_review_window_never_crosses_owner_or_organization(db):
    dossier, _, _, _, _ = public_changes(db)
    with db.session() as session, pytest.raises(DomainError) as peer:
        review_changes(session, "peer", dossier, through_sequence=3, reviewed_sequence=1, now=NOW)
    assert peer.value.status == 404
    with db.organization_context("org-b"), pytest.raises(DomainError) as tenant:
        window(db, dossier)
    assert tenant.value.status == 404


@pytest.mark.parametrize("cursor", [-1, 0, 4, True, "2"])
def test_invalid_cursor_cannot_escape_review_window(db, cursor):
    dossier, _, _, _, _ = public_changes(db)
    with pytest.raises(DomainError) as invalid:
        window(db, dossier, after_sequence=cursor)
    assert invalid.value.status == 422
