"""Relation retries reuse only the generation configuration actually requested."""

import json

import pytest
from pydantic import SecretStr
from test_relation_analysis import relation_delivery

from helvetic_lens.config import Settings
from helvetic_lens.prompt_settings import default_prompt_settings
from helvetic_lens.relation_analysis import cache_key, generation_parameters


def key(settings):
    return cache_key(
        organization_candidate_id="delivery", event_id="event", source_version_id="source",
        target_version_id="target", relation_fingerprint=None, evidence=[], profile_revision=1,
        settings=settings, prompts=default_prompt_settings(), runtime_fingerprint="same-runtime",
    )


@pytest.mark.parametrize("field,value", [
    ("apertus_temperature", 0.7), ("apertus_top_p", 0.8), ("apertus_presence_penalty", 0.4),
    ("apertus_reasoning_effort", "high"), ("apertus_json_mode", True),
    ("apertus_provider", "infomaniak"), ("apertus_product_id", "123"),
    ("apertus_model", "other-local-model"), ("apertus_base_url", "https://other.example/v1"),
    ("apertus_context_chars", 16000), ("apertus_max_tokens", 900),
])
def test_answer_affecting_settings_invalidate_relation_cache(field, value):
    settings = Settings(_env_file=None, apertus_provider="custom", apertus_base_url="https://model.example/v1")
    changed = settings.model_copy(update={field: value})
    assert key(settings) != key(changed)
    assert key(changed) == key(changed.model_copy(deep=True))


@pytest.mark.parametrize("field,value", [
    ("apertus_api_key", SecretStr("synthetic-rotated-test-key")),
    ("apertus_timeout_seconds", 180), ("apertus_request_retries", 4),
    ("apertus_batch_concurrency", 2),
])
def test_transport_or_credential_changes_do_not_spend_inference_again(field, value):
    settings = Settings(_env_file=None)
    assert key(settings) == key(settings.model_copy(update={field: value}))


@pytest.mark.parametrize("field,value", [
    ("apertus_temperature", 0.7), ("apertus_top_p", 0.8), ("apertus_presence_penalty", 0.4),
    ("apertus_reasoning_effort", "high"), ("apertus_json_mode", True),
])
def test_changed_controls_create_a_new_durable_analysis_then_reuse_it(harness, field, value):
    client, _, service, model = harness
    delivery, _ = relation_delivery(harness)
    service.settings.apertus_base_url = "https://model.example/v1"
    route = f"/api/relation-candidates/{delivery}/analyse-jobs"
    first = client.post(route).json()
    assert first["state"] == "succeeded"
    original = first["result"]["data"]
    original_controls = original["analysis_plan"]["execution"]["generation_parameters"]
    setattr(service.settings, field, value)
    second = client.post(route).json()
    assert second["state"] == "succeeded"
    fresh = second["result"]["data"]
    assert second["id"] != first["id"] and fresh["id"] != original["id"]
    assert fresh["analysis_plan"]["execution"]["generation_parameters"] == generation_parameters(service.settings)
    assert fresh["analysis_plan"]["execution"]["generation_parameters"] != original_controls
    repeat = client.post(route).json()
    assert repeat["id"] == second["id"] and len(model.calls) == 2
    # Rotating credentials must reuse the same durable request, not generate again.
    service.settings.apertus_api_key = SecretStr("synthetic-rotated-test-key")
    assert client.post(route).json()["id"] == second["id"]
    assert len(model.calls) == 2
    history = client.get(f"/api/relation-candidates/{delivery}/analyses").json()
    assert history["total"] == 2
    assert next(item for item in history["items"] if item["id"] == original["id"])["analysis_plan"]["execution"]["generation_parameters"] == original_controls
    assert "synthetic-rotated-test-key" not in json.dumps(history)
