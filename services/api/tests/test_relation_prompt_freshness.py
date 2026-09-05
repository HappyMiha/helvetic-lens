"""Only effective relation instructions determine current report applicability."""

import pytest
from sqlalchemy import func, select
from test_digest_resume import record_mail, setup_delivery
from test_relation_profile_freshness import analyse

from helvetic_lens import digests
from helvetic_lens.config import DomainError
from helvetic_lens.models import (
    DigestDelivery,
    Job,
    Organization,
    PromptConfiguration,
    RelationImpactAnalysis,
)
from helvetic_lens.prompt_settings import PromptSettingsInput, default_prompt_settings


def save_prompts(client, **updates):
    values = client.get("/api/settings/prompts").json()
    payload = {key: values[key] for key in PromptSettingsInput.model_fields}
    payload.update(updates)
    response = client.patch("/api/settings/prompts", json=payload)
    assert response.status_code == 200, response.text
    return payload


@pytest.mark.parametrize("field", ["impact_instructions", "repair_instructions"])
def test_used_prompt_edit_invalidates_history_and_inbox_without_new_inference(harness, field):
    client, _, service, model = harness
    delivery, saved = analyse(harness)
    with service.db.session() as session:
        before = session.scalar(select(func.count()).select_from(Job))
    save_prompts(client, **{field: "Use concise explanations grounded only in the provided evidence."})
    history = client.get(f"/api/relation-candidates/{delivery}/analyses").json()
    assert history["current"] is None and history["items"][0]["stale"]
    for route in ("/api/impact-inbox", "/api/impact-inbox/page"):
        item = client.get(route).json()["items"][0]["items"][0]
        assert item["status"] == "stale" and item["severity"] == "unknown"
        assert item["current_analysis_id"] is None and item["latest_attempt_id"] == saved["id"]
    citation = saved["result"]["citations"][0]
    assert client.get(citation["url"]).json()["text"] == citation["quote"]
    with service.db.session() as session:
        record = session.get(RelationImpactAnalysis, saved["id"])
        assert record.result == saved["result"] and record.use_count == 1
        assert session.scalar(select(func.count()).select_from(Job)) == before
    assert len(model.calls) == 1


@pytest.mark.parametrize("field,value", [
    ("ask_instructions", "Answer the question using the available document evidence concisely."),
    ("answer_synthesis_instructions", "Combine the saved answers concisely without making new factual claims."),
    ("impact_synthesis_instructions", "Combine the saved batch assessments into a short grounded overview."),
    ("ask_context_mode", "changes_only"),
])
def test_unused_prompts_do_not_invalidate_or_regenerate_relations(harness, field, value):
    client, _, _, model = harness
    delivery, saved = analyse(harness)
    save_prompts(client, **{field: value})
    history = client.get(f"/api/relation-candidates/{delivery}/analyses").json()
    assert history["current"]["id"] == saved["id"] and not history["current"]["stale"]
    repeat = client.post(f"/api/relation-candidates/{delivery}/analyse-jobs").json()
    assert repeat["state"] == "succeeded" and repeat["result"]["data"]["id"] == saved["id"]
    assert len(model.calls) == 1


def test_platform_inheritance_override_and_reset_are_content_based(harness):
    client, _, service, model = harness
    delivery, saved = analyse(harness)
    changed = PromptSettingsInput(impact_instructions="Explain only the direct organizational implications supported by evidence.")
    service.save_platform_prompt_settings(changed)
    route = f"/api/relation-candidates/{delivery}/analyses"
    assert client.get(route).json()["current"] is None
    # A full organization override wins over the platform, even at the same revision.
    assert client.patch("/api/settings/prompts", json=default_prompt_settings().model_dump()).status_code == 200
    assert client.get(route).json()["current"]["id"] == saved["id"]
    service.save_platform_prompt_settings(PromptSettingsInput(impact_instructions="Use a different platform instruction based only on the saved evidence."))
    assert client.get(route).json()["current"]["id"] == saved["id"]
    assert client.post("/api/settings/prompts/reset").status_code == 200
    assert client.get(route).json()["current"] is None
    service.reset_platform_prompt_settings()
    assert client.get(route).json()["current"]["id"] == saved["id"]
    assert len(model.calls) == 1


def test_failed_changed_prompt_attempt_retains_history_but_not_old_current_result(harness):
    client, _, _, model = harness
    delivery, saved = analyse(harness)
    save_prompts(client, impact_instructions="Describe only evidence-supported impacts and name any unresolved uncertainty.")
    model.invalid = True
    route = f"/api/relation-candidates/{delivery}/analyse-jobs"
    assert client.post(route).json()["state"] == "retrying"
    history = client.get(f"/api/relation-candidates/{delivery}/analyses").json()
    assert history["current"] is None and history["latest_attempt"]["status"] == "failed"
    assert next(item for item in history["items"] if item["id"] == saved["id"])["stale"]
    model.invalid = False
    fresh = client.post(route).json()
    assert fresh["state"] == "succeeded"
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"]["id"] == fresh["result"]["data"]["id"]


@pytest.mark.parametrize("fingerprint", [None, {}, "unknown-old-prompt"])
def test_missing_or_malformed_prompt_provenance_is_history_only(harness, fingerprint):
    client, _, service, _ = harness
    delivery, saved = analyse(harness)
    with service.db.session() as session:
        record = session.get(RelationImpactAnalysis, saved["id"])
        record.analysis_plan = {**record.analysis_plan, "execution": {**record.analysis_plan["execution"], "prompt_fingerprint": fingerprint}}
        session.commit()
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"] is None
    assert client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]["current_analysis_id"] is None


def test_digest_prompt_change_restarts_selection_and_never_sends_old_selection(harness, monkeypatch):
    _, _, service, model = harness
    job, _, _ = setup_delivery(harness)
    sent = record_mail(monkeypatch)
    cp = None
    while not cp or not cp["complete"]:
        with service.db.session() as session:
            cp = digests.prepare_batch(session, job["target_id"], cp, settings=service.environment_settings)
    service.save_platform_prompt_settings(PromptSettingsInput(impact_instructions="Review the organizational implications using only the saved source passages."))
    with pytest.raises(DomainError) as error:
        digests.deliver(service.db, service.environment_settings, job["target_id"], selection=cp)
    assert error.value.code == "digest_preferences_changed" and sent == []
    with service.db.session() as session:
        resumed = digests.prepare_batch(session, job["target_id"], cp, settings=service.environment_settings)
    assert resumed["processed"] == 50 and resumed["restarts"] == 1
    assert resumed["prompt_fingerprint"] != cp["prompt_fingerprint"]
    assert resumed["configuration_fingerprint"] == cp["configuration_fingerprint"]
    assert model.calls == []


def test_digest_cannot_borrow_foreign_prompt_override(harness):
    _, _, service, _ = harness
    job, _, _ = setup_delivery(harness)
    platform = PromptSettingsInput(impact_instructions="These platform instructions apply to organizations without their own override.")
    service.save_platform_prompt_settings(platform)
    with service.db.session(include_all_organizations=True) as session:
        other = Organization(name="Foreign prompts", slug="foreign-prompts")
        session.add(other)
        session.flush()
        session.add(PromptConfiguration(id=other.id, organization_id=other.id, values=default_prompt_settings().model_dump()))
        session.commit()
        delivery = session.get(DigestDelivery, job["target_id"])
        assert digests._reader(session, delivery, service.environment_settings).prompts.model_dump() == platform.model_dump()


@pytest.mark.parametrize("values", [{}, None])
def test_empty_saved_override_does_not_inherit_platform_prompts(harness, values):
    _, _, service, _ = harness
    job, _, _ = setup_delivery(harness)
    service.save_platform_prompt_settings(PromptSettingsInput(impact_instructions="These are changed platform instructions which the override must not borrow."))
    with service.db.session() as session:
        session.add(PromptConfiguration(id=service.tenant_record_id, organization_id=service.organization_id, values=values))
        session.commit()
        delivery = session.get(DigestDelivery, job["target_id"])
        assert digests._reader(session, delivery, service.environment_settings).prompts == default_prompt_settings()
    with service.organization_runtime():
        assert service.prompt_settings == default_prompt_settings()
