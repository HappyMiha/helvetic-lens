"""A refreshed candidate cannot reuse applicability from another document version."""

import pytest
from sqlalchemy import func, select
from test_digest_periods import recipient
from test_digest_resume import record_mail
from test_relation_profile_freshness import analyse

from helvetic_lens import digests
from helvetic_lens.models import (
    Job,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RelationCandidate,
    RelationImpactAnalysis,
)
from helvetic_lens.relation_analysis import version_binding


def change_version(service, saved, side, *, remove=False):
    with service.db.session() as session:
        candidate = session.get(RelationCandidate, saved["candidate_id"])
        field = f"{side}_version_id"
        old_id = getattr(candidate, field)
        assert old_id is not None
        if remove:
            setattr(candidate, field, None)
        else:
            old = session.get(RegulatoryDocumentVersion, old_id)
            fresh = RegulatoryDocumentVersion(expression_id=old.expression_id, version_key=old.version_key + "-freshness-test",
                                              content_hash="b" * 64, text=old.text, passages=old.passages, source_url=old.source_url)
            session.add(fresh)
            session.flush()
            setattr(candidate, field, fresh.id)
        session.commit()
        return old_id


@pytest.mark.parametrize("side", ["source", "target"])
@pytest.mark.parametrize("remove", [False, True])
def test_changed_or_removed_version_invalidates_current_without_rewriting_history(harness, side, remove):
    client, _, service, model = harness
    delivery, saved = analyse(harness)
    with service.db.session() as session:
        jobs_before = session.scalar(select(func.count()).select_from(Job))
    old_id = change_version(service, saved, side, remove=remove)
    history = client.get(f"/api/relation-candidates/{delivery}/analyses").json()
    assert history["current"] is None and history["items"][0]["stale"]
    for route in ("/api/impact-inbox", "/api/impact-inbox/page"):
        item = client.get(route).json()["items"][0]["items"][0]
        assert item["current_analysis_id"] is None and item["status"] == "stale"
        assert item["severity"] == "unknown" and item["latest_attempt_id"] == saved["id"]
    citation = saved["result"]["citations"][0]
    assert client.get(citation["url"]).json()["text"] == citation["quote"]
    with service.db.session() as session:
        record = session.get(RelationImpactAnalysis, saved["id"])
        assert record.result == saved["result"] and record.analysis_plan == saved["analysis_plan"]
        assert record.use_count == 1 and session.scalar(select(func.count()).select_from(Job)) == jobs_before
        setattr(session.get(RelationCandidate, saved["candidate_id"]), f"{side}_version_id", old_id)
        session.commit()
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"]["id"] == saved["id"]
    assert len(model.calls) == 1


def test_failed_new_version_analysis_never_revives_old_report(harness):
    client, _, service, model = harness
    delivery, saved = analyse(harness)
    change_version(service, saved, "source")
    model.invalid = True
    route = f"/api/relation-candidates/{delivery}/analyse-jobs"
    assert client.post(route).json()["state"] == "retrying"
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"] is None
    model.invalid = False
    fresh = client.post(route).json()
    assert fresh["state"] == "succeeded" and fresh["result"]["data"]["id"] != saved["id"]
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"]["id"] == fresh["result"]["data"]["id"]


@pytest.mark.parametrize("binding", [None, {}, [], {"source": "", "target": ""}])
def test_absent_or_mismatched_binding_cannot_be_current(harness, binding):
    client, _, service, _ = harness
    delivery, saved = analyse(harness)
    with service.db.session() as session:
        record = session.get(RelationImpactAnalysis, saved["id"])
        record.analysis_plan = {**record.analysis_plan, "execution": {**record.analysis_plan["execution"], "version_binding": binding}}
        session.commit()
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"] is None
    assert client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]["current_analysis_id"] is None


def test_explicit_metadata_only_binding_is_not_missing_provenance(harness):
    client, _, service, _ = harness
    delivery, saved = analyse(harness)
    # Synthetic metadata-only report: known absent IDs differ from missing provenance.
    with service.db.session() as session:
        candidate = session.get(RelationCandidate, saved["candidate_id"])
        candidate.source_version_id = candidate.target_version_id = None
        record = session.get(RelationImpactAnalysis, saved["id"])
        record.analysis_plan = {**record.analysis_plan, "execution": {**record.analysis_plan["execution"], "version_binding": version_binding(None, None)}}
        record.result = {**record.result, "supported": False, "potential_severity": "unknown", "actions": []}
        session.commit()
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"]["id"] == saved["id"]
    item = client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]
    assert item["current_analysis_id"] == saved["id"] and item["severity"] != "high"
    with service.db.session() as session:
        record = session.get(RelationImpactAnalysis, saved["id"])
        record.analysis_plan = {**record.analysis_plan, "execution": {**record.analysis_plan["execution"], "version_binding": {}}}
        session.commit()
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"] is None
    assert client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]["current_analysis_id"] is None


def test_final_digest_read_drops_obsolete_ai_severity_without_sending(harness, monkeypatch):
    _, _, service, model = harness
    _, saved = analyse(harness)
    user_id = recipient(service)
    severity = saved["result"]["potential_severity"]
    service.save_digest_preference(user_id, enabled=True, frequency="daily", sources=[], severities=[severity])
    job = service.enqueue_digest_now(user_id)
    sent = record_mail(monkeypatch)
    with service.db.session() as session:
        cp = digests.prepare_batch(session, job["target_id"], settings=service.settings)
    assert cp["complete"] and saved["event_id"] in cp["event_ids"]
    change_version(service, saved, "target")
    result = digests.deliver(service.db, service.environment_settings, job["target_id"], selection=cp, analysis_settings=service.settings)
    assert result["status"] == "skipped" and result["item_count"] == 0
    assert sent == [] and len(model.calls) == 1


def test_official_urgency_survives_an_obsolete_ai_version_binding(harness):
    client, _, service, _ = harness
    _, saved = analyse(harness, confirmed=True)
    with service.db.session() as session:
        session.get(RegulatoryEvent, saved["event_id"]).impact = "high"
        session.commit()
    change_version(service, saved, "source")
    item = client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]
    assert item["status"] == "confirmed_relation" and item["severity"] == "high"
    assert item["current_analysis_id"] is None and item["latest_attempt_id"] == saved["id"]
