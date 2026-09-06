import json

import httpx
import pytest
from conftest import add_law, import_old
from runtime_fixtures import local_runtime
from test_analysis_runtime_binding import reply, settings, transport

from helvetic_lens.analysis import AnswerDigest, InferenceBudget, ModelClient, structured_completion
from helvetic_lens.config import DomainError
from helvetic_lens.runtime_binding import request_fingerprint


def measurement(payload, **extra):
    return {
        "schema_version": "local-prompt-budget-v1", "method": "llama_cpp_chat_input_tokens",
        "request_sha256": request_fingerprint(payload), "binding_fingerprint": "a" * 64,
        "deployment_id": "a" * 32, "input_tokens": 123, "reserved_output_tokens": payload["max_tokens"],
        "safety_tokens": 128, "context_window_tokens": 4096, "runner_context_tokens": 4096, "fits": True,
        **extra,
    }


def measured_reply(request, content="synthetic reply", **extra):
    response = reply(content)
    response.headers["x-helvetic-token-budget"] = json.dumps(measurement(json.loads(request.content), **extra))
    return response


@pytest.mark.asyncio
@pytest.mark.parametrize("extra", [
    {"request_sha256": "0" * 64}, {"binding_fingerprint": "0" * 64}, {"deployment_id": "0" * 32},
    {"input_tokens": True}, {"input_tokens": "123"}, {"safety_tokens": 0},
    {"reserved_output_tokens": 1}, {"fits": False}, {"runner_context_tokens": 20},
    {"context_window_tokens": 8192, "runner_context_tokens": 8192},
])
async def test_wrong_or_unverified_measurement_is_not_accepted_or_retried(monkeypatch, extra):
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(200, json=local_runtime()) if request.method == "GET" else measured_reply(request, **extra)

    transport(monkeypatch, handler)
    model = ModelClient(settings())
    token = model.begin_trace()
    with pytest.raises(DomainError) as error:
        await model.complete("system", "question")
    trace = model.end_trace(token)
    assert error.value.code == "token_budget_invalid"
    assert [request.method for request in calls] == ["GET", "POST"]
    assert not any(event.get("prompt_token_measurement") for event in trace)


@pytest.mark.asyncio
async def test_repair_is_remeasured_for_its_changed_full_payload_without_inflating_calls(monkeypatch):
    payloads = []

    async def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=local_runtime())
        payloads.append(json.loads(request.content))
        return measured_reply(request, "{broken" if len(payloads) == 1 else '{"supported":true,"citation_rows":[1]}', input_tokens=100 + len(payloads))

    transport(monkeypatch, handler)
    model = ModelClient(settings())
    token = model.begin_trace()
    budget = InferenceBudget(3)
    evidence = [{"version_id": "v1", "passage_id": "p1", "text": "Synthetic wording."}]
    result = await structured_completion(
        model, "system", {"evidence": evidence}, AnswerDigest, evidence,
        validate_citations=False, require_supported=True, numeric_reference_count=1,
        numeric_reference_evidence=evidence, budget=budget,
    )
    trace = model.end_trace(token)
    assert result["citation_rows"] == [1] and budget.used == 2
    measured = [event["prompt_token_measurement"] for event in trace if event.get("prompt_token_measurement")]
    assert [item["input_tokens"] for item in measured] == [101, 102]
    assert measured[0]["request_sha256"] != measured[1]["request_sha256"]
    assert len([event for event in trace if event.get("outcome")]) == 2


@pytest.mark.parametrize("kind", ["ask", "analyse"])
@pytest.mark.parametrize("oversized", [False, True])
def test_http_history_and_completed_plan_keep_measured_budget_separate_from_usage(harness, monkeypatch, kind, oversized):
    client, _, service, _ = harness
    law = add_law(client)
    previous = import_old(client, law["id"])["version"]
    comparison = client.post("/api/comparisons", json={
        "old_version_id": previous["id"], "new_version_id": law["current_version_id"],
    }).json()
    service.settings.apertus_provider = "docker"
    service.settings.apertus_base_url = "http://synthetic-manager/openai/v1"
    service.settings.apertus_model = "test-apertus"
    service.model_client = ModelClient(service.settings, service.integration_logger)
    calls = []

    async def handler(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=local_runtime())
        content = '{"impact":"low","citation_rows":[1]}' if kind == "analyse" else '{"supported":true,"citation_rows":[1]}'
        if oversized:
            return httpx.Response(422, json={"error": {"code": "context_length_exceeded"}}, headers={
                "x-helvetic-runtime-binding": "a" * 64,
                "x-helvetic-token-budget": json.dumps(measurement(json.loads(request.content), input_tokens=4096, fits=False)),
            })
        return measured_reply(request, content)

    transport(monkeypatch, handler)
    route = f"/api/comparisons/{comparison['id']}"
    response = client.post(route + "/" + kind, json={"question": "What is the retention period?"} if kind == "ask" else {})
    assert response.status_code == (422 if oversized and kind == "ask" else 200), response.text
    record = client.get(route + "/ai-history").json()["items"][0]
    assert record["status"] == ("failed" if oversized else "succeeded")
    measured = record["provenance"]["prompt_token_measurements"]
    assert len(measured) == 1 and measured[0]["fits"] is not oversized
    assert measured[0]["input_tokens"] == (4096 if oversized else 123)
    assert record["analysis_plan"]["actual"]["prompt_token_measurements"] == measured
    assert record["provenance"]["provider_calls"] == 1
    assert record["provenance"]["token_counts"] == {}
    assert [request.method for request in calls] == ["GET", "POST"]


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["token_budget_unavailable", "invalid_output_token_limit", "invalid_response_count"])
async def test_preflight_errors_are_actionable_and_never_retried(monkeypatch, code):
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(200, json=local_runtime()) if request.method == "GET" else httpx.Response(422, json={"code": code})

    transport(monkeypatch, handler)
    with pytest.raises(DomainError) as error:
        await ModelClient(settings()).complete("system", "question")
    assert error.value.code == code
    assert "before generation" in error.value.message
    assert len(calls) == 2
