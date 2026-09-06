"""Same-ID source corrections must not leave an old AI conclusion current."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select, update
from test_digest_periods import recipient
from test_digest_resume import record_mail
from test_relation_analysis import relation_delivery
from test_relation_profile_freshness import analyse

from helvetic_lens import digests
from helvetic_lens.db import utcnow
from helvetic_lens.models import (
    Job,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryRelation,
    RegulatoryWork,
    RelationCandidate,
    RelationImpactAnalysis,
    Version,
)
from helvetic_lens.relation_inputs import capture_inputs

MODELS = {
    "candidate": RelationCandidate,
    "event": RegulatoryEvent,
    "source_work": RegulatoryWork,
    "target_work": RegulatoryWork,
    "source_version": RegulatoryDocumentVersion,
    "target_version": RegulatoryDocumentVersion,
    "target_legacy": Version,
    "official_relation": RegulatoryRelation,
}


def correct(service, saved, name, **values):
    binding = saved["analysis_plan"]["execution"]["evidence_binding"]
    model = MODELS[name]
    with service.db.session() as session:
        # Core UPDATE bypasses ORM before_flush callbacks and stale object caches.
        session.execute(update(model.__table__).where(model.id == binding[name + "_id"]).values(**values))
        session.commit()
        fresh = capture_inputs(session, saved["candidate_id"])
    return binding, fresh


@pytest.mark.parametrize(
    "name,field,value",
    [
        ("source_version", "text", "Corrected source in the same ORM session."),
        ("source_work", "title", "Corrected work in the same ORM session."),
        ("event", "evidence_json", {"correction": "ORM update"}),
        ("candidate", "why_json", ["Corrected candidate"]),
        ("official_relation", "evidence_json", {"correction": "ORM relation"}),
    ],
)
def test_trigger_generated_revision_is_fresh_after_orm_commit(harness, name, field, value):
    _, _, service, _ = harness
    _, saved = analyse(harness, confirmed=name == "official_relation")
    binding = saved["analysis_plan"]["execution"]["evidence_binding"]
    model = MODELS[name]
    with service.db.session() as session:
        record = session.get(model, binding[name + "_id"])
        previous = record.evidence_revision
        setattr(record, field, value)
        session.commit()
        # No explicit refresh: expire_on_commit=False must not hide a DB trigger.
        assert record.evidence_revision == previous + 1
        assert record.evidence_revision == session.scalar(
            select(model.evidence_revision).where(model.id == record.id)
        )
        setattr(record, field, value)
        session.commit()
        assert record.evidence_revision == previous + 1


@pytest.mark.parametrize(
    "name,field,value",
    [
        ("source_version", "text", "Corrected source text with unchanged content_hash."),
        ("target_version", "passages", [{"id": "corrected", "text": "Corrected exception."}]),
        ("source_version", "source_url", "https://example.invalid/corrected-source"),
        ("target_version", "metadata_json", {"scope": "corrected"}),
        ("source_work", "title", "Corrected source title"),
        ("source_work", "metadata_json", {"affected_norm": "corrected reference"}),
        ("target_work", "metadata_json", {"scope": "corrected exception"}),
        ("target_work", "lifecycle_status", "repealed"),
        ("event", "evidence_json", {"official_notice": "Corrected scope"}),
        ("candidate", "why_json", ["Corrected retrieval rationale"]),
        ("official_relation", "evidence_json", {"official_notice": "Correction without new fingerprint"}),
    ],
)
def test_same_id_correction_invalidates_all_current_reads(harness, name, field, value):
    client, _, service, model = harness
    delivery, saved = analyse(harness, confirmed=name == "official_relation")
    with service.db.session() as session:
        jobs_before = session.scalar(select(func.count()).select_from(Job))
    old, fresh = correct(service, saved, name, **{field: value})
    assert old[name + "_id"] == fresh[name + "_id"]
    assert int(fresh[name + "_revision"]) == int(old[name + "_revision"]) + 1
    history = client.get(f"/api/relation-candidates/{delivery}/analyses").json()
    assert history["current"] is None and history["items"][0]["stale"]
    for route in ("/api/impact-inbox", "/api/impact-inbox/page"):
        item = client.get(route).json()["items"][0]["items"][0]
        assert item["current_analysis_id"] is None and item["latest_attempt_id"] == saved["id"]
    for citation in saved["result"]["citations"]:
        assert client.get(citation["url"]).json()["text"] == citation["quote"]
    with service.db.session() as session:
        record = session.get(RelationImpactAnalysis, saved["id"])
        assert record.result == saved["result"] and record.analysis_plan == saved["analysis_plan"]
        assert record.use_count == 1 and session.scalar(select(func.count()).select_from(Job)) == jobs_before
    assert len(model.calls) == 1


def test_same_value_and_operational_updates_preserve_revision_and_cached_analysis(harness):
    client, _, service, model = harness
    delivery, saved = analyse(harness)
    with service.db.session() as session:
        candidate = session.get(RelationCandidate, saved["candidate_id"])
        old_title = session.get(RegulatoryWork, candidate.target_work_id).title
    for name, values in (
        ("target_work", {"title": old_title, "updated_at": utcnow()}),
        ("candidate", {"expires_at": utcnow() + timedelta(days=4), "updated_at": utcnow()}),
        ("event", {"analysis_state": "complete", "connector_health": "healthy", "impact": "high"}),
        ("source_version", {"fetched_at": utcnow()}),
    ):
        old, fresh = correct(service, saved, name, **values)
        assert old == fresh
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"]["id"] == saved["id"]
    assert (
        client.post(f"/api/relation-candidates/{delivery}/analyse-jobs").json()["result"]["data"]["id"]
        == saved["id"]
    )
    assert len(model.calls) == 1


def test_corrected_evidence_uses_new_request_and_failed_retry_does_not_revive_old(harness):
    client, _, service, model = harness
    delivery, saved = analyse(harness)
    correct(service, saved, "source_work", title="Corrected retention proposal")
    model.invalid = True
    assert client.post(f"/api/relation-candidates/{delivery}/analyse-jobs").json()["state"] == "retrying"
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"] is None
    model.invalid = False
    fresh = client.post(f"/api/relation-candidates/{delivery}/analyse-jobs").json()["result"]["data"]
    assert fresh["id"] != saved["id"]
    assert (
        fresh["analysis_plan"]["execution"]["evidence_binding"]
        != saved["analysis_plan"]["execution"]["evidence_binding"]
    )
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"]["id"] == fresh["id"]


def test_legacy_fallback_corrections_cannot_hide_behind_corpus_version_id(harness):
    client, _, service, _ = harness
    delivery, _ = relation_delivery(harness)
    with service.db.session() as session:
        candidate = session.scalar(select(RelationCandidate))
        target = session.get(RegulatoryDocumentVersion, candidate.target_version_id)
        assert target.legacy_version_id
        target.passages = []
        session.commit()
    service.settings.apertus_base_url = "https://model.example/v1"
    saved = client.post(f"/api/relation-candidates/{delivery}/analyse-jobs").json()["result"]["data"]
    assert any(row["source_kind"] == "monitored_work_passage" for row in saved["result"]["citations"])
    correct(
        service,
        saved,
        "target_legacy",
        passages=[{"id": "replacement", "text": "Corrected legacy exception"}],
    )
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"] is None
    assert client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]["current_analysis_id"] is None


@pytest.mark.parametrize("binding", [None, {}, [], {"candidate_revision": "1"}])
def test_missing_or_malformed_evidence_binding_is_history_only(harness, binding):
    client, _, service, _ = harness
    delivery, saved = analyse(harness)
    with service.db.session() as session:
        record = session.get(RelationImpactAnalysis, saved["id"])
        record.analysis_plan = {
            **record.analysis_plan,
            "execution": {**record.analysis_plan["execution"], "evidence_binding": binding},
        }
        session.commit()
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"] is None
    assert client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]["current_analysis_id"] is None


def test_correction_during_generation_is_saved_as_stale_history(harness, monkeypatch):
    client, _, service, model = harness
    delivery, _ = relation_delivery(harness)
    service.settings.apertus_base_url = "https://model.example/v1"
    original = model.complete

    async def complete(*args, **kwargs):
        result = await original(*args, **kwargs)
        with service.db.session() as session:
            candidate = session.scalar(select(RelationCandidate))
            work = session.get(RegulatoryWork, candidate.target_work_id)
            work.metadata_json = {"scope": "correction during inference"}
            session.commit()
        return result

    monkeypatch.setattr(model, "complete", complete)
    saved = client.post(f"/api/relation-candidates/{delivery}/analyse-jobs").json()["result"]["data"]
    assert saved["status"] == "succeeded" and saved["stale"]
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"] is None
    assert len(model.calls) == 1


def test_digest_final_read_drops_corrected_ai_evidence_without_sending(harness, monkeypatch):
    _, _, service, model = harness
    _, saved = analyse(harness)
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
        selection = digests.prepare_batch(session, job["target_id"], settings=service.settings)
    assert selection["complete"] and saved["event_id"] in selection["event_ids"]
    correct(service, saved, "event", evidence_json={"notice": "Corrected after digest preparation"})
    result = digests.deliver(
        service.db,
        service.environment_settings,
        job["target_id"],
        selection=selection,
        analysis_settings=service.settings,
    )
    assert result["status"] == "skipped" and result["item_count"] == 0
    assert sent == [] and len(model.calls) == 1


def test_evidence_migration_roundtrip_preserves_history_without_counter_resurrection(harness):
    from pathlib import Path

    from alembic.config import Config

    from alembic import command

    client, _, service, model = harness
    delivery, saved = analyse(harness)
    correct(service, saved, "source_version", text="Changed after the original saved report")
    directory = Path(__file__).resolve().parents[1]
    config = Config(str(directory / "alembic.ini"))
    config.set_main_option("script_location", str(directory / "alembic"))
    with service.db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "b294ad830761")
        command.upgrade(config, "head")
    with service.db.session() as session:
        binding = capture_inputs(session, saved["candidate_id"])
        assert binding["epoch"] != saved["analysis_plan"]["execution"]["evidence_binding"]["epoch"]
        record = session.get(RelationImpactAnalysis, saved["id"])
        assert record.result == saved["result"] and record.analysis_plan == saved["analysis_plan"]
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"] is None
    assert client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]["current_analysis_id"] is None
    fresh = client.post(f"/api/relation-candidates/{delivery}/analyse-jobs").json()["result"]["data"]
    assert fresh["id"] != saved["id"] and len(model.calls) == 2


def test_correction_during_preparation_does_not_bind_old_text_to_new_revision(harness, monkeypatch):
    client, _, service, model = harness
    delivery, _ = relation_delivery(harness)
    service.settings.apertus_base_url = "https://model.example/v1"
    original = service._relation_text_tokens
    changed = False
    with service.db.session() as session:
        jobs_before = session.scalar(select(func.count()).select_from(Job))

    def during_preparation(*values):
        nonlocal changed
        if not changed:
            changed = True
            with service.db.session() as session:
                candidate = session.scalar(select(RelationCandidate))
                version = session.get(RegulatoryDocumentVersion, candidate.source_version_id)
                version.passages = [{"id": "corrected", "text": "Corrected while collecting the dossier"}]
                session.commit()
        return original(*values)

    monkeypatch.setattr(service, "_relation_text_tokens", during_preparation)
    response = client.post(f"/api/relation-candidates/{delivery}/analyse-jobs")
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "relation_evidence_changed"
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == jobs_before
        assert session.scalar(select(func.count()).select_from(RelationImpactAnalysis)) == 0
    assert model.calls == []


def test_foreign_legacy_revision_is_not_exposed_in_binding(harness):
    from helvetic_lens.models import Organization

    client, _, service, _ = harness
    delivery, saved = analyse(harness)
    binding = saved["analysis_plan"]["execution"]["evidence_binding"]
    assert binding["target_legacy_id"]
    with service.db.session() as session:
        foreign = Organization(name="Foreign organization", slug="foreign-evidence-revision")
        session.add(foreign)
        session.flush()
        session.get(Version, binding["target_legacy_id"]).owner_organization_id = foreign.id
        session.commit()
        current = capture_inputs(session, saved["candidate_id"])
        assert current["target_legacy_id"] == current["target_legacy_revision"] == ""
    with service.db.session(include_all_organizations=True) as session:
        current = capture_inputs(session, saved["candidate_id"])
        assert current["target_legacy_id"] == current["target_legacy_revision"] == ""
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"] is None
    assert client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]["current_analysis_id"] is None
