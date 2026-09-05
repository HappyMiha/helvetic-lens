"""Read-time configuration changes cannot silently reuse obsolete applicability."""

import json

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from test_digest_resume import record_mail, setup_delivery
from test_relation_profile_freshness import analyse
from test_settings import configuration

from helvetic_lens import digests
from helvetic_lens.config import DomainError
from helvetic_lens.models import (
    ApertusConfiguration,
    DigestDelivery,
    Job,
    Organization,
    RelationImpactAnalysis,
)


@pytest.mark.parametrize("field,value", [
    ("apertus_temperature", 0.7), ("apertus_top_p", 0.8), ("apertus_presence_penalty", 0.4),
    ("apertus_reasoning_effort", "high"), ("apertus_json_mode", True),
    ("apertus_provider", "infomaniak"), ("apertus_product_id", "123"),
    ("apertus_model", "other-local-model"), ("apertus_base_url", "https://other.example/v1"),
    ("apertus_context_chars", 16000), ("apertus_max_tokens", 900),
])
def test_configuration_changes_remove_current_conclusion_without_jobs_or_history_rewrite(harness, field, value):
    client, _, service, model = harness
    delivery, saved = analyse(harness)
    with service.db.session() as session:
        jobs_before = session.scalar(select(func.count()).select_from(Job))
    previous = getattr(service.settings, field)
    setattr(service.settings, field, value)
    history = client.get(f"/api/relation-candidates/{delivery}/analyses").json()
    assert history["current"] is None and history["items"][0]["stale"]
    assert history["items"][0]["result"] == saved["result"]
    for route in ("/api/impact-inbox", "/api/impact-inbox/page"):
        item = client.get(route).json()["items"][0]["items"][0]
        assert item["current_analysis_id"] is None and item["severity"] == "unknown"
        assert item["status"] == "stale" and item["latest_attempt_id"] == saved["id"]
    citation = saved["result"]["citations"][0]
    assert client.get(citation["url"]).json()["text"] == citation["quote"]
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == jobs_before
        assert session.get(RelationImpactAnalysis, saved["id"]).use_count == 1
    assert len(model.calls) == 1
    # Returning to the exact configuration can reuse that still-valid assessment.
    setattr(service.settings, field, previous)
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"]["id"] == saved["id"]


@pytest.mark.parametrize("field,value", [
    ("apertus_api_key", SecretStr("synthetic-rotation")), ("apertus_timeout_seconds", 180),
    ("apertus_request_retries", 4), ("apertus_batch_concurrency", 2),
])
def test_credential_and_transport_edits_preserve_current_answer(harness, field, value):
    client, _, service, model = harness
    delivery, saved = analyse(harness)
    setattr(service.settings, field, value)
    history = client.get(f"/api/relation-candidates/{delivery}/analyses").json()
    assert history["current"]["id"] == saved["id"] and not history["current"]["stale"]
    item = client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]
    assert item["current_analysis_id"] == saved["id"] and len(model.calls) == 1
    assert "synthetic-rotation" not in json.dumps(history)


def test_saved_settings_failed_retry_and_reset_do_not_revive_old_result(harness):
    client, _, service, model = harness
    assert client.patch("/api/settings/apertus", json=configuration()).status_code == 200
    delivery, saved = analyse(harness)
    assert client.patch("/api/settings/apertus", json=configuration(model="new-model")).status_code == 200
    model.invalid = True
    assert client.post(f"/api/relation-candidates/{delivery}/analyse-jobs").json()["state"] == "retrying"
    history = client.get(f"/api/relation-candidates/{delivery}/analyses").json()
    assert history["current"] is None and history["latest_attempt"]["status"] == "failed"
    item = client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]
    assert item["current_analysis_id"] is None and item["severity"] == "unknown"
    model.invalid = False
    fresh = client.post(f"/api/relation-candidates/{delivery}/analyse-jobs").json()
    assert fresh["state"] == "succeeded"
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"]["id"] == fresh["result"]["data"]["id"]
    assert client.post("/api/settings/apertus/reset").status_code == 200
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"] is None
    with service.db.session() as session:
        assert session.get(RelationImpactAnalysis, saved["id"]).result == saved["result"]


def test_digest_restarts_configuration_selection_and_rejects_old_prepared_delivery(harness, monkeypatch):
    client, _, service, model = harness
    job, _, _ = setup_delivery(harness)
    sent = record_mail(monkeypatch)
    cp = None
    while not cp or not cp["complete"]:
        with service.db.session() as session:
            cp = digests.prepare_batch(session, job["target_id"], cp, settings=service.environment_settings)
    assert client.patch("/api/settings/apertus", json=configuration()).status_code == 200
    # Sender resolves this organization's persisted settings, not the base environment.
    with pytest.raises(DomainError) as error:
        digests.deliver(service.db, service.environment_settings, job["target_id"], selection=cp)
    assert error.value.code == "digest_preferences_changed" and sent == []
    with service.db.session() as session:
        resumed = digests.prepare_batch(session, job["target_id"], cp, settings=service.environment_settings)
    assert resumed["restarts"] == 1 and resumed["processed"] == 50
    assert resumed["configuration_fingerprint"] != cp["configuration_fingerprint"]
    assert resumed["preference_fingerprint"] == cp["preference_fingerprint"]
    assert model.calls == []


def test_digest_settings_are_tenant_scoped_even_in_privileged_session(harness):
    client, _, service, _ = harness
    job, _, _ = setup_delivery(harness)
    with service.db.session(include_all_organizations=True) as session:
        other = Organization(name="Foreign settings", slug="foreign-settings")
        session.add(other)
        session.flush()
        session.add(ApertusConfiguration(id=other.id, organization_id=other.id,
                                        values=configuration(model="foreign-model"), key_source="none"))
        session.commit()
        delivery = session.get(DigestDelivery, job["target_id"])
        assert digests._reader(session, delivery, service.environment_settings).settings.apertus_model == service.environment_settings.apertus_model
    assert client.patch("/api/settings/apertus", json=configuration(model="own-model")).status_code == 200
    with service.db.session(include_all_organizations=True) as session:
        delivery = session.get(DigestDelivery, job["target_id"])
        assert digests._reader(session, delivery, service.environment_settings).settings.apertus_model == "own-model"
