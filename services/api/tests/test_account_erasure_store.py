"""Actual physical erasure retains shared corpus, colleagues and FK integrity."""

import pytest
from sqlalchemy import select
from test_account_deletion_plan import monitor
from test_business_item_work import act, read, seed
from test_business_monitor_handover import transfer
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens.account_deletion_plan import inventory
from helvetic_lens.account_erasure_store import erase_selected, select_private_rows
from helvetic_lens.models import Organization, User
from helvetic_lens.monitoring_centre import MODELS


def erase(db, user_id="owner", organization="org-a"):
    with db.session(include_all_organizations=True) as session:
        plan = inventory(session, user_id, organization)
        assert plan.public["can_delete"], plan.public["blockers"]
        user = session.get(User, user_id)
        selection = select_private_rows(session, user, plan.erase_organizations)
        erase_selected(session, user, selection)
        session.commit()
        return selection


def test_erase_all_nine_owned_monitors_and_empty_workspace_but_keep_colleagues(db):
    identifiers = {domain: monitor(db, domain) for domain in MODELS}
    others = {domain: monitor(db, domain, user="peer") for domain in MODELS}
    selection = erase(db)
    assert selection.counts["users"] == 1 and selection.counts["organizations"] == 1
    with db.session(include_all_organizations=True) as session:
        assert session.get(User, "owner") is None
        assert session.get(User, "peer").active
        assert session.get(Organization, "org-b") is None
        assert session.get(Organization, "org-a") is not None
        for domain, model in MODELS.items():
            assert session.get(model, identifiers[domain]) is None
            assert session.get(model, others[domain]) is not None
        assert session.connection().exec_driver_sql("PRAGMA foreign_key_check").all() == []


@pytest.mark.parametrize("domain", ("tenders", "ip", "auctions"))
def test_physical_erasure_after_handover_keeps_shared_native_decisions_and_evidence(db, domain):
    data = seed(db, domain)
    decision = {"tenders": "no_bid", "ip": "counsel", "auctions": "inspect"}[domain]
    before = act(db, domain, data, decision=decision, comment="Shared reason to retain")
    transfer(db, domain, data[0], data[2])
    erase(db)
    retained = read(db, domain, data, user="peer")
    assert retained["decision"] == before["decision"] and not retained["needs_review"]
    assert retained["history"][0]["actor"] is None
    assert retained["history"][0]["binding"] == before["history"][0]["binding"]
    assert retained["history"][0]["comment"] == "Shared reason to retain"
    with db.session(include_all_organizations=True) as session:
        assert session.scalar(select(User.id).where(User.id == "owner")) is None
        assert session.connection().exec_driver_sql("PRAGMA foreign_key_check").all() == []


def corpus(db):
    from datetime import UTC, datetime

    from helvetic_lens.models import (
        RegulatoryDate,
        RegulatoryDocumentVersion,
        RegulatoryEvent,
        RegulatoryExpression,
        RegulatoryWork,
    )
    with db.session(include_all_organizations=True) as session:
        for label, organization in (("private", "org-b"), ("official", None)):
            session.add(RegulatoryWork(id=label, owner_organization_id=organization, kind="act", authority="fixture",
                canonical_key=label, title=label))
            session.flush()
            session.add(RegulatoryExpression(id=label, work_id=label, language="en", expression_key=label))
            session.flush()
            session.add(RegulatoryDocumentVersion(id=label, expression_id=label, version_key=label,
                text="Synthetic source content", artifact_key=("a" if organization else "b") * 64 + ".txt"))
            session.flush()
            session.add(RegulatoryEvent(id=label, work_id=label, expression_id=label, document_version_id=label,
                authority="fixture", event_type="new_version", dedupe_key=label,
                detected_at=datetime.now(UTC), provenance_method="official_metadata"))
            session.flush()
            for kind in ("work", "expression", "version", "event"):
                session.add(RegulatoryDate(entity_type=kind, entity_id=label, kind="published_at",
                    date_value="2026-09-14", precision="day", provenance="official_metadata"))
        # A private pointer to the same content-addressed file does not own the
        # official copy. Normal orphan cleanup must retain that shared file.
        session.add(RegulatoryDocumentVersion(id="private-shared-file", expression_id="private", version_key="shared",
            text="Shared bytes", artifact_key="b" * 64 + ".txt"))
        session.commit()


def test_private_native_corpus_dates_and_files_are_erased_under_actual_retention(db, tmp_path):
    import os
    from datetime import UTC, datetime, timedelta

    from helvetic_lens.config import Settings
    from helvetic_lens.maintenance import cleanup_operational_data
    from helvetic_lens.models import (
        RegulatoryDate,
        RegulatoryDocumentVersion,
        RegulatoryEvent,
        RegulatoryExpression,
        RegulatoryWork,
    )
    corpus(db)
    settings = Settings(_env_file=None, data_dir=tmp_path / "artifact-fixture", orphan_artifact_retention_hours=1)
    folder = settings.storage_path / "artifacts"
    folder.mkdir(parents=True)
    private, shared = folder / ("a" * 64 + ".txt"), folder / ("b" * 64 + ".txt")
    private.write_text("Synthetic private bytes", encoding="utf-8")
    shared.write_text("Synthetic shared bytes", encoding="utf-8")
    now = datetime.now(UTC)
    old = (now - timedelta(hours=2)).timestamp()
    os.utime(private, (old, old))
    os.utime(shared, (old, old))
    selection = erase(db)
    assert selection.artifacts == {private.name, shared.name}
    with db.session(include_all_organizations=True) as session:
        for model in (RegulatoryWork, RegulatoryExpression, RegulatoryDocumentVersion, RegulatoryEvent):
            assert session.get(model, "private") is None
            assert session.get(model, "official") is not None
        assert session.scalar(select(RegulatoryDate.id).where(RegulatoryDate.entity_id == "private")) is None
        assert len(list(session.scalars(select(RegulatoryDate.id).where(RegulatoryDate.entity_id == "official")))) == 4
    result = cleanup_operational_data(db, settings, now=now)
    assert result["orphan_artifacts"] == 1
    assert not private.exists() and shared.read_text(encoding="utf-8") == "Synthetic shared bytes"


def test_preview_counts_a_bridged_document_version_once_and_erases_both_records(db):
    from helvetic_lens.account_erasure_store import private_document_version_count
    from helvetic_lens.models import Law, RegulatoryDocumentVersion, Version

    corpus(db)
    with db.session(include_all_organizations=True) as session:
        session.add(Law(id="legacy-private", owner_organization_id="org-b", canonical_identity="fixture-private",
            name="Private law", url="https://example.invalid/private"))
        session.flush()
        session.add(Version(id="legacy-private", law_id="legacy-private", owner_organization_id="org-b",
            title="Private version", content_hash="a" * 64, extractor="fixture", text="Private text", passages=[],
            artifact_key="a" * 64 + ".txt", content_type="text/plain", filename="private.txt", origin="upload"))
        session.flush()
        session.get(RegulatoryDocumentVersion, "private").legacy_version_id = "legacy-private"
        session.commit()
        selection = select_private_rows(session, session.get(User, "owner"), ["org-b"])
        assert private_document_version_count(session, selection) == 2
    erase(db)
    with db.session(include_all_organizations=True) as session:
        assert session.get(Version, "legacy-private") is None
        assert session.get(RegulatoryDocumentVersion, "private") is None
        assert session.get(RegulatoryDocumentVersion, "official") is not None


def test_retained_workspace_reference_refuses_entire_erasure_without_changing_data(db):
    from helvetic_lens.config import DomainError
    from helvetic_lens.models import RegulatoryEventState, RegulatoryWork
    corpus(db)
    with db.session(include_all_organizations=True) as session:
        session.add(RegulatoryEventState(organization_id="org-a", event_id="private"))
        session.commit()
    with pytest.raises(DomainError) as denied:
        erase(db)
    assert denied.value.code == "account_deletion_retained_reference"
    with db.session(include_all_organizations=True) as session:
        assert session.get(User, "owner") is not None
        assert session.get(Organization, "org-b") is not None
        assert session.get(RegulatoryWork, "private") is not None
        assert session.scalar(select(RegulatoryEventState.id)) is not None


def test_connector_run_provenance_survives_deleted_workspace_and_private_job(db):
    from datetime import UTC, datetime

    from helvetic_lens import jobs
    from helvetic_lens.models import ConnectorRun, ConnectorSchedule
    with db.organization_context("org-b"), db.session() as session:
        schedule = ConnectorSchedule(id="shared-schedule", connector="fixture", stream="official",
            interval_seconds=60, next_run_at=datetime.now(UTC))
        session.add(schedule)
        session.flush()
        job, _ = jobs.enqueue(session, job_type="connector_sync", target_type="connector_schedule", target_id=schedule.id,
            queue="maintenance", idempotency_key="source-request")
        session.add(ConnectorRun(id="shared-run", schedule_id=schedule.id, job_id=job.id,
            requested_by_organization_id="org-b", connector="fixture", stream="official", status="succeeded"))
        session.commit()
    erase(db)
    with db.session(include_all_organizations=True) as session:
        run = session.get(ConnectorRun, "shared-run")
        assert run is not None and run.job_id is None and run.requested_by_organization_id is None
        assert session.get(ConnectorSchedule, "shared-schedule") is not None


def test_in_flight_worker_with_cached_job_cannot_restore_erased_private_work(db):
    from sqlalchemy.orm.exc import StaleDataError

    from helvetic_lens import jobs
    from helvetic_lens.models import Job
    identifier = monitor(db, "air")
    with db.session() as session:
        job, _ = jobs.enqueue(session, job_type="air_refresh", target_type="air_monitor", target_id=identifier,
            queue="maintenance", idempotency_key="in-flight-private")
        job_id = job.id
        session.flush()
        assert jobs.claim(session, job_id, "synthetic-worker") is not None
        session.commit()
    with db.session() as stale:
        cached = stale.get(Job, job_id)
        assert cached.state == "running"
        erase(db)
        with pytest.raises(StaleDataError):
            jobs.complete(stale, job_id, result_json={"private": "late result"})
            stale.commit()
        stale.rollback()
    with db.session() as session:
        assert not jobs.heartbeat(session, job_id, "synthetic-worker")
        assert jobs.claim(session, job_id, "another-worker") is None
        assert session.get(Job, job_id) is None
        assert session.get(MODELS["air"], identifier) is None
