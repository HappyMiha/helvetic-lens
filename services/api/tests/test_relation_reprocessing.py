"""Explicit rule maintenance: preview, bounded durable apply and intact history."""

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event as sa_event
from sqlalchemy import func, select
from test_administration import csrf, promote, register, settings
from test_digest_periods import seed_events
from test_relation_profile_freshness import analyse

from helvetic_lens import jobs
from helvetic_lens import relation_candidates as rules
from helvetic_lens import relation_reprocessing as reprocess
from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.models import (
    DigestDelivery,
    Job,
    OrganizationRelationCandidate,
    OrganizationRelationReview,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryWork,
    RelationCandidate,
    RelationImpactAnalysis,
    User,
    Version,
    new_id,
)


def enqueue(service, dry_run=False, request_id=None):
    return service.enqueue_relation_reprocessing(request_id or str(uuid4()), dry_run=dry_run)


def execute(service, job):
    return asyncio.run(service.execute_job(job["id"]))


def history(client, delivery):
    return client.get(f"/api/relation-candidates/{delivery}/analyses").json()


def many(harness, count=61):
    _, _, service, _ = harness
    seed_events(harness, [{"id": new_id(), "detected_at": utcnow() - timedelta(minutes=2)} for _ in range(count - 1)])
    with service.db.session(include_all_organizations=True) as session:
        return list(session.scalars(select(RelationCandidate.id).order_by(RelationCandidate.id)))


def test_changed_code_rule_is_stale_before_reprocessing_and_preview_is_non_destructive(harness, monkeypatch):
    client, _, service, model = harness
    delivery, saved = analyse(harness)
    monkeypatch.setattr(rules, "RULE_REVISION", "synthetic-next-rule")
    assert history(client, delivery)["current"] is None
    item = client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]
    assert item["current_analysis_id"] is None and item["severity"] == "unknown"
    response = client.post(f"/api/relation-candidates/{delivery}/analyse-jobs")
    assert response.status_code == 409 and response.json()["code"] == "relation_candidate_needs_reprocessing"
    preview = execute(service, enqueue(service, dry_run=True))
    assert preview["state"] == "succeeded"
    result = preview["result"]["data"]
    assert result["changed"] == result["retained"] == 1 and result["dry_run"]
    with service.db.session() as session:
        candidate = session.get(RelationCandidate, saved["candidate_id"])
        assert candidate.rule_revision != rules.RULE_REVISION
        record = session.get(RelationImpactAnalysis, saved["id"])
        assert record.result == saved["result"] and record.analysis_plan == saved["analysis_plan"]
    applied = execute(service, enqueue(service))
    assert applied["state"] == "succeeded" and applied["result"]["data"]["changed"] == 1
    assert history(client, delivery)["current"] is None
    fresh = client.post(f"/api/relation-candidates/{delivery}/analyse-jobs").json()["result"]["data"]
    assert fresh["id"] != saved["id"] and len(model.calls) == 2
    assert history(client, delivery)["current"]["id"] == fresh["id"]


def test_generic_old_lead_is_rejected_without_deleting_history_or_notifications(harness):
    client, _, service, model = harness
    delivery, saved = analyse(harness)
    with service.db.session() as session:
        candidate = session.get(RelationCandidate, saved["candidate_id"])
        for work_id in (candidate.source_work_id, candidate.target_work_id):
            work = session.get(RegulatoryWork, work_id)
            work.title, work.metadata_json = "Verordnung über die Bundesverordnung", {}
        session.get(RegulatoryEvent, candidate.event_id).evidence_json = {}
        candidate.rule_revision = "relation-candidate-v1"
        session.commit()
        original_deliveries = session.scalar(select(func.count()).select_from(OrganizationRelationCandidate))
    result = execute(service, enqueue(service))["result"]["data"]
    assert result["rejected"] == 1 and result["ai_calls"] == 0
    assert "not a legal" in result["examples"][0]["reason"][0]
    item = client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]
    assert item["status"] == "no_supported_impact" and item["severity"] == "unknown"
    assert item["current_analysis_id"] is None and item["latest_attempt_id"] == saved["id"]
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(OrganizationRelationCandidate)) == original_deliveries
        assert session.scalar(select(func.count()).select_from(DigestDelivery)) == 0
        assert session.get(RelationImpactAnalysis, saved["id"]).result == saved["result"]
    assert len(model.calls) == 1


def test_repeat_apply_reuses_request_and_does_not_advance_evidence_again(harness):
    _, _, service, model = harness
    _, saved = analyse(harness)
    request_id = str(uuid4())
    first = enqueue(service, request_id=request_id)
    execute(service, first)
    assert enqueue(service, request_id=request_id)["id"] == first["id"]
    with service.db.session() as session:
        before = session.get(RelationCandidate, saved["candidate_id"]).evidence_revision
    repeated = execute(service, enqueue(service))["result"]["data"]
    assert repeated["changed"] == 0
    with service.db.session() as session:
        assert session.get(RelationCandidate, saved["candidate_id"]).evidence_revision == before
    assert len(model.calls) == 1


def test_current_unchanged_pair_keeps_usable_report_without_bookkeeping_invalidation(harness):
    client, _, service, model = harness
    delivery, saved = analyse(harness)
    with service.db.session() as session:
        candidate = session.get(RelationCandidate, saved["candidate_id"])
        before = candidate.evidence_revision
        original_evidence = candidate.evidence_json
    for dry_run in (True, False):
        result = execute(service, enqueue(service, dry_run=dry_run))["result"]["data"]
        assert result["retained"] == 1 and result["changed"] == 0
        assert history(client, delivery)["current"]["id"] == saved["id"]
    with service.db.session() as session:
        candidate = session.get(RelationCandidate, saved["candidate_id"])
        assert candidate.evidence_revision == before and candidate.evidence_json == original_evidence
    reused = client.post(f"/api/relation-candidates/{delivery}/analyse-jobs").json()["result"]["data"]
    assert reused["id"] == saved["id"] and len(model.calls) == 1


def test_batches_resume_after_cancel_and_never_hydrate_archived_documents(harness, monkeypatch):
    _, _, service, model = harness
    ids = many(harness)
    loaded = []
    original = reprocess.run_batch
    def observe(session, payload):
        sa_event.listen(session, "loaded_as_persistent", lambda _session, row: loaded.append(row))
        return original(session, payload)
    monkeypatch.setattr(reprocess, "run_batch", observe)
    job = enqueue(service)
    first = execute(service, job)
    assert first["state"] == "queued" and first["result"]["data"]["processed"] == 25
    assert len([row for row in loaded if isinstance(row, RelationCandidate)]) == 25
    assert not any(isinstance(row, (RegulatoryDocumentVersion, Version, RelationImpactAnalysis)) for row in loaded)
    service.cancel_job(job["id"])
    assert execute(service, job)["state"] == "cancelled"
    service.retry_job(job["id"])
    second = execute(service, job)
    assert second["state"] == "queued" and second["result"]["data"]["processed"] == 50
    final = execute(service, job)
    assert final["state"] == "succeeded" and final["result"]["data"]["processed"] == len(ids)
    assert final["result"]["data"]["batches"] == 3 and len(final["result"]["data"]["examples"]) == 10
    assert len([row for row in loaded if isinstance(row, RelationCandidate)]) == len(ids)
    assert model.calls == []


def test_failed_batch_rolls_back_changes_and_cursor_together(harness, monkeypatch):
    _, _, service, _ = harness
    many(harness)
    original = jobs.yield_batch
    def crash(*_):
        raise DomainError("Synthetic crash before commit", 503, "test_crash")
    monkeypatch.setattr(jobs, "yield_batch", crash)
    job = enqueue(service)
    assert execute(service, job)["state"] == "retrying"
    with service.db.session() as session:
        assert "checkpoint" not in session.get(Job, job["id"]).payload
        assert all("reprocessing" not in row.evidence_json for row in session.scalars(select(RelationCandidate)))
    monkeypatch.setattr(jobs, "yield_batch", original)
    assert execute(service, job)["result"]["data"]["processed"] == 25


def test_new_rule_supersedes_partial_job_without_touching_remaining_candidates(harness, monkeypatch):
    _, _, service, _ = harness
    ids = many(harness)
    job = enqueue(service)
    execute(service, job)
    monkeypatch.setattr(rules, "RULE_REVISION", "synthetic-later-rule")
    final = execute(service, job)
    assert final["state"] == "succeeded" and final["result"]["data"]["status"] == "superseded"
    assert final["result"]["data"]["processed"] == 25
    with service.db.session() as session:
        assert all("reprocessing" not in session.get(RelationCandidate, id_).evidence_json for id_ in ids[25:])


@pytest.mark.parametrize("bad", [[], {"cursor": "invalid"}, {"processed": 2}, {"changed": -1}, {"examples": [{}] * 11}])
def test_malformed_checkpoint_refuses_to_restart_silently(harness, bad):
    _, _, service, _ = harness
    job = enqueue(service)
    with service.db.session() as session:
        stored = session.get(Job, job["id"])
        stored.payload = {**stored.payload, "checkpoint": bad}
        session.commit()
    result = execute(service, job)
    assert result["state"] == "retrying"
    with service.db.session() as session:
        assert session.get(Job, job["id"]).error_code == "relation_reprocess_checkpoint_invalid"


def test_independent_review_and_official_urgency_survive_reprocessing(harness):
    client, _, service, model = harness
    delivery, saved = analyse(harness, confirmed=True)
    with service.db.session() as session:
        review = OrganizationRelationReview(organization_candidate_id=delivery, decision="rejected", note="Independent human review")
        session.add(review)
        candidate = session.get(RelationCandidate, saved["candidate_id"])
        candidate.rule_revision = "old-rule"
        event = session.get(RegulatoryEvent, candidate.event_id)
        event.impact = "high"
        session.commit()
        review_id = review.id
    assert execute(service, enqueue(service))["result"]["data"]["retained"] == 1
    item = client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]
    assert item["severity"] == "high" and item["status"] == "confirmed_relation"
    with service.db.session() as session:
        assert session.get(OrganizationRelationReview, review_id).note == "Independent human review"
    assert len(model.calls) == 1


def test_maintenance_requires_platform_admin_including_generic_job_routes(tmp_path):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient

    from helvetic_lens.main import create_app

    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        assert client.get("/api/admin/relation-reprocessing").status_code == 401
        register(client, "maintainer@example.ch")
        assert client.post("/api/admin/relation-reprocessing", json={}, headers=csrf(client)).status_code == 403
        promote(app.state.service, "maintainer@example.ch")
        assert client.get("/api/admin/relation-reprocessing").json()["default_dry_run"]
        assert client.post("/api/admin/relation-reprocessing", json={}).status_code == 403
        job = client.post("/api/admin/relation-reprocessing", json={}, headers=csrf(client)).json()
        assert job["result"]["data"]["dry_run"] is True
        assert any(row["id"] == job["id"] for row in client.get("/api/jobs").json())
        with app.state.service.db.session(include_all_organizations=True) as session:
            session.scalar(select(User).where(User.email == "maintainer@example.ch")).platform_admin = False
            session.commit()
        assert all(row["id"] != job["id"] for row in client.get("/api/jobs").json())
        assert client.get(f"/api/jobs/{job['id']}").status_code == 403
        for action in ("retry", "cancel"):
            assert client.post(f"/api/jobs/{job['id']}/{action}", headers=csrf(client)).status_code == 403


@pytest.mark.parametrize("state", ["promoted", "rejected"])
def test_operator_terminal_candidate_is_counted_but_not_rewritten(harness, state):
    _, _, service, _ = harness
    _, saved = analyse(harness)
    with service.db.session() as session:
        candidate = session.get(RelationCandidate, saved["candidate_id"])
        candidate.status = state
        session.commit()
        # Database triggers advance evidence revisions after the ORM UPDATE.
        session.refresh(candidate)
        before = candidate.evidence_revision
        updated_at = candidate.updated_at
    result = execute(service, enqueue(service))["result"]["data"]
    assert result["skipped"] == 1 and result["changed"] == 0
    with service.db.session() as session:
        candidate = session.get(RelationCandidate, saved["candidate_id"])
        assert candidate.evidence_revision == before
        assert candidate.status == state and candidate.updated_at == updated_at


def test_resume_excludes_late_admissions_and_reports_deleted_candidates(harness):
    _, _, service, _ = harness
    ids = many(harness)
    job = enqueue(service)
    first = execute(service, job)
    assert first["result"]["data"]["eligible"] == 61
    with service.db.session(include_all_organizations=True) as session:
        candidate = session.get(RelationCandidate, ids[-1])
        event = session.get(RegulatoryEvent, candidate.event_id)
        event_values = {column.key: getattr(event, column.key) for column in event.__table__.columns}
        late_event_id = new_id()
        event_values.update(id=late_event_id, dedupe_key=late_event_id, created_at=utcnow())
        candidate_values = {column.key: getattr(candidate, column.key) for column in candidate.__table__.columns}
        late_id = new_id()
        candidate_values.update(id=late_id, event_id=late_event_id, created_at=utcnow())
        session.add(RegulatoryEvent(**event_values))
        session.flush()
        session.add(RelationCandidate(**candidate_values))
        session.delete(candidate)
        session.commit()
    second = execute(service, job)
    assert second["state"] == "queued"
    final = execute(service, job)
    result = final["result"]["data"]
    assert final["state"] == "succeeded" and result["processed"] == 60
    assert result["removed_since_capture"] == 1
    with service.db.session() as session:
        assert "reprocessing" not in session.get(RelationCandidate, late_id).evidence_json


def test_changed_selected_document_version_invalidates_result_without_loading_body(harness):
    client, _, service, model = harness
    delivery, saved = analyse(harness)
    with service.db.session() as session:
        candidate = session.get(RelationCandidate, saved["candidate_id"])
        old = session.get(RegulatoryDocumentVersion, candidate.target_version_id)
        values = {column.key: getattr(old, column.key) for column in old.__table__.columns}
        newer_id = new_id()
        values.update(id=newer_id, version_key="later-synthetic-version", created_at=utcnow(),
                      legacy_version_id=None, text="Synthetic later document", passages=[])
        session.add(RegulatoryDocumentVersion(**values))
        session.commit()
    assert history(client, delivery)["current"] is not None  # Candidate refresh lag is real before the job.
    execute(service, enqueue(service))
    assert history(client, delivery)["current"] is None
    with service.db.session() as session:
        assert session.get(RelationCandidate, saved["candidate_id"]).target_version_id == newer_id
        assert session.get(RelationImpactAnalysis, saved["id"]).result == saved["result"]
    assert len(model.calls) == 1



def test_concurrent_request_id_reuses_one_maintenance_job(harness):
    import copy
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, RLock

    _, _, service, _ = harness
    if service.db.engine.dialect.name != "postgresql":
        pytest.skip("Cross-worker row locking is verified on isolated PostgreSQL")
    barrier, request_id = Barrier(2), str(uuid4())
    workers = [copy.copy(service), copy.copy(service)]
    for worker in workers:
        worker.write_guard = RLock()
    def start(worker):
        barrier.wait(timeout=10)
        return enqueue(worker, request_id=request_id)["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(start, workers))
    assert ids[0] == ids[1]
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job).where(Job.type == reprocess.JOB_TYPE)) == 1
