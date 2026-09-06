"""Corrected official relations invalidate applicability, without erasing history."""

import pytest
from sqlalchemy import func, select
from test_digest_periods import recipient
from test_digest_resume import record_mail
from test_relation_profile_freshness import analyse

from helvetic_lens import digests
from helvetic_lens.models import Job, RegulatoryRelation, RelationCandidate, RelationImpactAnalysis
from helvetic_lens.relation_analysis import official_relation_binding


@pytest.mark.parametrize(
    "field,value",
    [
        ("state", "rejected"),
        ("state", "proposed"),
        ("relation_type", "cites"),
        ("authority", "corrected-authority"),
        ("provenance_method", "corrected-metadata"),
        ("evidence_fingerprint", "f" * 64),
        ("subject_work_id", "target"),
        ("object_work_id", "source"),
        ("source_version_id", "target-version"),
    ],
)
def test_corrected_official_fields_make_saved_report_history_only(harness, field, value):
    client, _, service, model = harness
    delivery, saved = analyse(harness, confirmed=True)
    with service.db.session() as session:
        candidate = session.get(RelationCandidate, saved["candidate_id"])
        relation = session.get(RegulatoryRelation, candidate.relation_id)
        original = getattr(relation, field)
        replacement = {
            "target": candidate.target_work_id,
            "source": candidate.source_work_id,
            "target-version": candidate.target_version_id,
        }.get(value, value)
        assert replacement != original
        setattr(relation, field, replacement)
        jobs = session.scalar(select(func.count()).select_from(Job))
        session.commit()
    history = client.get(f"/api/relation-candidates/{delivery}/analyses").json()
    assert history["current"] is None and history["items"][0]["stale"]
    for route in ("/api/impact-inbox", "/api/impact-inbox/page"):
        item = client.get(route).json()["items"][0]["items"][0]
        assert item["current_analysis_id"] is None and item["latest_attempt_id"] == saved["id"]
    citation = saved["result"]["citations"][0]
    assert client.get(citation["url"]).json()["text"] == citation["quote"]
    with service.db.session() as session:
        record = session.get(RelationImpactAnalysis, saved["id"])
        assert record.result == saved["result"] and record.analysis_plan == saved["analysis_plan"]
        assert session.scalar(select(func.count()).select_from(Job)) == jobs
        candidate = session.get(RelationCandidate, saved["candidate_id"])
        setattr(session.get(RegulatoryRelation, candidate.relation_id), field, original)
        session.commit()
    # A reverted value is a new evidence revision, not a rollback of its history.
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"] is None
    assert len(model.calls) == 1
    fresh = client.post(f"/api/relation-candidates/{delivery}/analyse-jobs").json()["result"]["data"]
    assert fresh["id"] != saved["id"] and len(model.calls) == 2
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"]["id"] == fresh["id"]


def test_detached_relation_and_missing_binding_are_not_current(harness):
    client, _, service, _ = harness
    delivery, saved = analyse(harness, confirmed=True)
    with service.db.session() as session:
        candidate = session.get(RelationCandidate, saved["candidate_id"])
        relation_id = candidate.relation_id
        candidate.relation_id = None
        session.commit()
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"] is None
    assert client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]["current_analysis_id"] is None
    with service.db.session() as session:
        session.get(RelationCandidate, saved["candidate_id"]).relation_id = relation_id
        record = session.get(RelationImpactAnalysis, saved["id"])
        execution = dict(record.analysis_plan["execution"])
        execution.pop("official_relation_binding")
        record.analysis_plan = {**record.analysis_plan, "execution": execution}
        session.commit()
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"] is None
    assert client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]["current_analysis_id"] is None


def test_new_official_relation_invalidates_previously_unlinked_report(harness):
    client, _, service, model = harness
    delivery, saved = analyse(harness)
    with service.db.session() as session:
        session.get(RelationCandidate, saved["candidate_id"]).relation_id = None
        session.commit()
    saved = client.post(f"/api/relation-candidates/{delivery}/analyse-jobs").json()["result"]["data"]
    calls_before = len(model.calls)
    assert saved["analysis_plan"]["execution"]["official_relation_binding"] == official_relation_binding(None)
    with service.db.session() as session:
        candidate = session.get(RelationCandidate, saved["candidate_id"])
        relation = RegulatoryRelation(
            subject_work_id=candidate.source_work_id,
            object_work_id=candidate.target_work_id,
            authority="test",
            relation_type="cites",
            state="confirmed",
            provenance_method="official_metadata",
            dedupe_key="new-official-freshness",
            evidence_fingerprint="n" * 64,
        )
        session.add(relation)
        session.flush()
        candidate.relation_id = relation.id
        session.commit()
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"] is None
    assert client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]["current_analysis_id"] is None
    assert len(model.calls) == calls_before


def test_correction_changes_request_identity_and_failed_retry_never_revives_old(harness):
    client, _, service, model = harness
    delivery, saved = analyse(harness, confirmed=True)
    with service.db.session() as session:
        candidate = session.get(RelationCandidate, saved["candidate_id"])
        session.get(RegulatoryRelation, candidate.relation_id).authority = "corrected-authority"
        session.commit()
    model.invalid = True
    route = f"/api/relation-candidates/{delivery}/analyse-jobs"
    assert client.post(route).json()["state"] == "retrying"
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"] is None
    model.invalid = False
    fresh = client.post(route).json()
    assert fresh["state"] == "succeeded" and fresh["result"]["data"]["id"] != saved["id"]
    calls = len(model.calls)
    assert client.post(route).json()["result"]["data"]["id"] == fresh["result"]["data"]["id"]
    assert len(model.calls) == calls


def test_digest_final_read_rechecks_corrected_relation_without_sending(harness, monkeypatch):
    _, _, service, model = harness
    _, saved = analyse(harness, confirmed=True)
    user_id = recipient(service)
    service.save_digest_preference(
        user_id,
        enabled=True,
        frequency="daily",
        sources=[],
        severities=[saved["result"]["potential_severity"]],
    )
    job = service.enqueue_digest_now(user_id)
    sent = record_mail(monkeypatch)
    with service.db.session() as session:
        checkpoint = digests.prepare_batch(session, job["target_id"], settings=service.settings)
    assert checkpoint["complete"] and saved["event_id"] in checkpoint["event_ids"]
    with service.db.session() as session:
        candidate = session.get(RelationCandidate, saved["candidate_id"])
        session.get(RegulatoryRelation, candidate.relation_id).state = "rejected"
        session.commit()
    result = digests.deliver(
        service.db,
        service.environment_settings,
        job["target_id"],
        selection=checkpoint,
        analysis_settings=service.settings,
    )
    assert result["status"] == "skipped" and result["item_count"] == 0
    assert sent == [] and len(model.calls) == 1
