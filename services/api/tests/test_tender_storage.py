from datetime import timedelta

import pytest
import test_tender_repository as persistence
from sqlalchemy import func, select
from test_tender_evidence import many_lots
from test_tender_matching import NOW, profile
from test_tender_repository import create, decide, ingest, parsed, publication, read, revised

from helvetic_lens import tender_lifecycle, tender_repository
from helvetic_lens.tender_models import (
    TenderDossier,
    TenderDossierVersion,
    TenderMaterialSection,
    TenderMonitor,
    TenderPublicationSnapshot,
    TenderStorageState,
)
from helvetic_lens.tender_observations import observe_publication
from helvetic_lens.tender_storage import StorageCapacity, StorageLimits, collect_unreferenced

db = persistence.db
template = persistence.template


def usage(session):
    return session.scalar(select(TenderStorageState.used_bytes)) or 0


def test_public_quota_failure_is_atomic_across_all_lots_and_retry_is_idempotent(db):
    monitor, raw = create(db, active=True), many_lots()
    with db.session() as session:
        with pytest.raises(StorageCapacity):
            observe_publication(
                session, monitor["id"], parsed(raw), now=NOW, storage_limits=StorageLimits(public_bytes=1)
            )
        session.commit()
        assert session.scalar(select(func.count()).select_from(TenderDossier)) == 0
        assert session.scalar(select(func.count()).select_from(TenderPublicationSnapshot)) == 0
        assert usage(session) == 0
    assert len(ingest(db, monitor, raw)) == 12
    with db.session() as session:
        used = usage(session)
        total = sum(session.scalars(select(TenderPublicationSnapshot.payload_bytes))) + sum(
            session.scalars(select(TenderMaterialSection.payload_bytes))
        )
        assert used == total and used > 0
        # Even lowering the quota cannot break an exact replay or discard history.
        assert (
            observe_publication(
                session, monitor["id"], parsed(raw), now=NOW, storage_limits=StorageLimits(public_bytes=1)
            )
            == []
        )
        session.commit()
        assert usage(session) == used


def test_lot_version_limit_does_not_apply_only_part_of_a_publication(db):
    monitor, raw = create(db, active=True), many_lots()
    with db.session() as session:
        with pytest.raises(StorageCapacity):
            observe_publication(
                session,
                monitor["id"],
                parsed(raw),
                now=NOW,
                storage_limits=StorageLimits(monitor_versions=11),
            )
        session.commit()
        assert session.scalar(select(func.count()).select_from(TenderDossierVersion)) == 0
        assert session.scalar(select(func.count()).select_from(TenderDossier)) == 0
        assert usage(session) == 0


def test_capacity_preserves_reviewed_history_and_cleanup_never_expires_referenced_versions(db):
    monitor = create(db, active=True)
    raw = publication()
    (dossier,) = ingest(db, monitor, raw)
    decision = decide(db, read(db, dossier))
    with db.session() as session:
        before = usage(session)
        with pytest.raises(StorageCapacity):
            observe_publication(
                session,
                monitor["id"],
                parsed(revised(raw)),
                now=NOW,
                storage_limits=StorageLimits(monitor_versions=1),
            )
        session.commit()
        assert usage(session) == before
        assert collect_unreferenced(session, now=NOW + timedelta(days=3650)) == {
            "removed_public_payloads": 0,
            "released_payload_bytes": 0,
        }
        session.commit()
    assert read(db, dossier) == decision


def test_cleanup_sees_references_in_other_tenants_then_reclaims_only_after_last_owner_deletes(db):
    monitor, raw = create(db, active=True), publication()
    ingest(db, monitor, raw)
    with db.organization_context("org-b"), db.session() as session:
        other = tender_repository.create_profile(session, "owner", profile().model_dump(mode="json"), "b")
        session.get(TenderMonitor, other["id"]).status = "active"
        session.flush()
        observe_publication(session, other["id"], parsed(raw), now=NOW)
        session.commit()
    with db.session() as session:
        before = usage(session)
        tender_lifecycle.remove(session, "owner", monitor["id"], monitor["version"])
        session.commit()
        # GC deliberately runs in org-a context. Org-b references must still pin.
        assert collect_unreferenced(session, now=NOW + timedelta(days=8))["removed_public_payloads"] == 0
        session.commit()
        assert usage(session) == before
    with db.organization_context("org-b"), db.session() as session:
        tender_lifecycle.remove(session, "owner", other["id"], other["version"])
        session.commit()
    with db.session() as session:
        assert collect_unreferenced(session, now=NOW + timedelta(days=6))["removed_public_payloads"] == 0
        first = collect_unreferenced(session, now=NOW + timedelta(days=8), limit=1)
        assert first["removed_public_payloads"] == 1
        session.commit()
        rest = collect_unreferenced(session, now=NOW + timedelta(days=8))
        session.commit()
        assert first["released_payload_bytes"] + rest["released_payload_bytes"] == before
        assert usage(session) == 0
        assert session.scalar(select(func.count()).select_from(TenderPublicationSnapshot)) == 0
        assert session.scalar(select(func.count()).select_from(TenderMaterialSection)) == 0
