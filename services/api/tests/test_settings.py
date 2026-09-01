"""Configuration tests use dummy credentials and HTTP transports, never live inference."""

import json

import httpx
import pytest
from conftest import add_law, import_old
from fastapi.testclient import TestClient
from pydantic import SecretStr

from regwatch.analysis import ModelClient
from regwatch.main import create_app
from regwatch.model_settings import ApertusSettingsInput
from regwatch.models import ApertusConfiguration


def configuration(**changes):
    return {
        "provider": "custom",
        "product_id": "",
        "base_url": "https://inference.example/v1",
        "model": "test-apertus",
        "timeout_seconds": 30,
        "context_chars": 16000,
        "max_tokens": 1200,
        "temperature": 0.25,
        "top_p": 0.9,
        "presence_penalty": 0.2,
        "reasoning_effort": "default",
        "json_mode": True,
        **changes,
    }


def transport(monkeypatch, respond):
    real_client = httpx.AsyncClient
    mocked = httpx.MockTransport(respond)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client(transport=mocked, **kwargs))


def test_settings_save_apply_and_survive_restart_without_exposing_a_key(harness):
    client, fetcher, service, _ = harness
    service.model_client = ModelClient(service.settings)
    original_client = service.model_client
    saved = client.patch(
        "/api/settings/apertus",
        json=configuration(key_action="replace", api_key="test-only-secret"),
    )
    assert saved.status_code == 200
    assert "test-only-secret" not in saved.text and "api_key" not in saved.json()
    assert saved.json()["source"] == "workspace" and saved.json()["api_key_configured"]
    assert service.model_client is not original_client
    assert service.model_client.settings.apertus_api_key.get_secret_value() == "test-only-secret"
    assert client.get("/api/health").json()["apertus"] == {
        "configured": True,
        "model": "test-apertus",
    }
    restarted = create_app(service.environment_settings, fetcher=fetcher)
    with TestClient(restarted) as restored:
        result = restored.get("/api/settings/apertus")
        assert result.json()["base_url"] == "https://inference.example/v1"
        assert result.json()["max_tokens"] == 1200 and result.json()["temperature"] == 0.25
        assert "test-only-secret" not in result.text
        assert (
            restarted.state.service.model_client.settings.apertus_api_key.get_secret_value()
            == "test-only-secret"
        )
        kept = restored.patch("/api/settings/apertus", json=configuration(model="renamed-model"))
        assert kept.status_code == 200 and kept.json()["api_key_configured"]
        assert restarted.state.service.settings.apertus_api_key.get_secret_value() == "test-only-secret"
        assert restored.get("/api/health").json()["apertus"]["model"] == "renamed-model"


def test_key_removal_environment_inheritance_and_reset_do_not_delete_documents(harness):
    client, _, service, _ = harness
    service.environment_settings.apertus_api_key = SecretStr("test-environment-key")
    law = add_law(client)
    client.patch(
        "/api/settings/apertus",
        json=configuration(key_action="replace", api_key="test-workspace-key"),
    )
    removed = client.patch("/api/settings/apertus", json=configuration(key_action="remove"))
    assert removed.status_code == 200 and removed.json()["api_key_configured"] is False
    assert service.settings.apertus_api_key.get_secret_value() == ""
    inherited = client.patch("/api/settings/apertus", json=configuration(key_action="environment"))
    assert inherited.json()["key_source"] == "environment"
    assert service.settings.apertus_api_key.get_secret_value() == "test-environment-key"
    with service.db.session() as session:
        assert session.get(ApertusConfiguration, "default").api_key is None
    reset = client.post("/api/settings/apertus/reset")
    assert reset.status_code == 200 and reset.json()["source"] == "environment"
    assert not reset.json()["configured"] and reset.json()["api_key_configured"]
    assert "test-environment-key" not in reset.text
    assert client.get("/api/laws/" + law["id"]).json()["current_version_id"] == law["current_version_id"]
    with service.db.session() as session:
        assert session.get(ApertusConfiguration, "default") is None


def test_draft_connection_uses_actual_adapter_parameters_without_saving(harness, monkeypatch):
    client, _, _, _ = harness
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"status":"ok"}'}}]})

    transport(monkeypatch, respond)
    reply = client.post(
        "/api/settings/apertus/test",
        json=configuration(key_action="replace", api_key="test-draft-key"),
    )
    assert reply.status_code == 200 and reply.json()["received_reply"]
    assert reply.json()["saved"] is False and "test-draft-key" not in reply.text
    assert len(requests) == 1 and str(requests[0].url) == "https://inference.example/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer test-draft-key"
    assert requests[0].headers["user-agent"] == "ApertusRegWatch/0.1"
    body = json.loads(requests[0].content)
    assert body["model"] == "test-apertus" and body["temperature"] == 0.25
    assert body["max_tokens"] == 1200 and body["response_format"] == {"type": "json_object"}
    assert body["top_p"] == 0.9 and body["presence_penalty"] == 0.2
    assert body["stream"] is False and body["n"] == 1
    assert "max_completion_tokens" not in body and "reasoning_effort" not in body
    assert client.get("/api/settings/apertus").json()["source"] == "environment"
    assert not client.get("/api/health").json()["apertus"]["configured"]


def test_infomaniak_loads_models_from_product_api_without_exposing_token(harness, monkeypatch):
    client, _, _, _ = harness
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {
                        "id": "swiss-ai/Apertus-v1.5-8B",
                        "object": "model",
                        "created": 1750000000,
                        "owned_by": "swiss-ai",
                    },
                    {"id": "another-chat-model", "object": "model"},
                ],
            },
        )

    transport(monkeypatch, respond)
    response = client.post(
        "/api/settings/apertus/models",
        json=configuration(
            provider="infomaniak",
            product_id="111040",
            base_url="https://must-not-be-used.example/v1",
            key_action="replace",
            api_key="test-infomaniak-token",
        ),
    )
    assert response.status_code == 200
    assert response.json()["provider"] == "infomaniak" and response.json()["count"] == 2
    assert response.json()["base_url"] == "https://api.infomaniak.com/2/ai/111040/openai/v1"
    assert response.json()["models"][0] == {
        "id": "swiss-ai/Apertus-v1.5-8B",
        "owned_by": "swiss-ai",
        "created": 1750000000,
    }
    assert "test-infomaniak-token" not in response.text and "api_key" not in response.text
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert str(requests[0].url) == "https://api.infomaniak.com/2/ai/111040/openai/v1/models"
    assert requests[0].headers["authorization"] == "Bearer test-infomaniak-token"
    assert client.get("/api/settings/apertus").json()["source"] == "environment"
    logged = client.get("/api/integration-logs?provider=infomaniak").json()
    assert logged["total"] == 1 and logged["items"][0]["operation"] == "list_models"
    detail = client.get("/api/integration-logs/" + logged["items"][0]["id"])
    assert detail.json()["request_headers"]["Authorization"] == "[REDACTED]"
    assert detail.json()["response_body"]["object"] == "list"
    assert "test-infomaniak-token" not in detail.text


def test_infomaniak_completion_uses_provider_contract(harness, monkeypatch):
    client, _, _, _ = harness
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    transport(monkeypatch, respond)
    response = client.post(
        "/api/settings/apertus/test",
        json=configuration(
            provider="infomaniak",
            product_id="111040",
            key_action="replace",
            api_key="test-infomaniak-token",
            reasoning_effort="low",
            json_mode=False,
        ),
    )
    assert response.status_code == 200
    assert response.json()["base_url"] == "https://api.infomaniak.com/2/ai/111040/openai/v1"
    assert str(requests[0].url) == (
        "https://api.infomaniak.com/2/ai/111040/openai/v1/chat/completions"
    )
    body = json.loads(requests[0].content)
    assert body["max_completion_tokens"] == 1200 and "max_tokens" not in body
    assert body["reasoning_effort"] == "low"
    assert body["stream"] is False and body["n"] == 1
    assert body["top_p"] == 0.9 and body["presence_penalty"] == 0.2


@pytest.mark.parametrize(
    ("upstream_status", "code", "api_status"),
    [
        (401, "model_authentication_failed", 502),
        (403, "model_access_denied", 502),
        (404, "model_not_found", 502),
        (429, "model_rate_limited", 503),
        (504, "model_upstream_timeout", 504),
    ],
)
def test_provider_failure_explains_next_step_without_echoing_provider_body(
    harness, monkeypatch, upstream_status, code, api_status
):
    client, _, _, _ = harness
    transport(
        monkeypatch,
        lambda request: httpx.Response(upstream_status, text="test-provider-body-must-not-be-echoed"),
    )
    response = client.post(
        "/api/settings/apertus/test",
        json=configuration(key_action="replace", api_key="test-draft-secret"),
    )
    assert response.status_code == api_status and response.json()["code"] == code
    assert f"HTTP {upstream_status}" in response.json()["detail"]
    assert "test-provider-body" not in response.text and "test-draft-secret" not in response.text
    assert client.get("/api/settings/apertus").json()["source"] == "environment"


def test_saved_settings_are_used_by_later_real_adapter_requests_and_failures_are_explicit(
    harness, monkeypatch
):
    client, _, service, _ = harness
    service.model_client = ModelClient(service.settings)
    requests = []

    def respond(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(200, json={"choices": [{"message": {"content": '{"status":"ok"}'}}]})
        if len(requests) == 3:
            raise httpx.ConnectError("Test-only connection failure", request=request)
        raise httpx.ReadTimeout("Test-only timeout", request=request)

    transport(monkeypatch, respond)
    client.patch(
        "/api/settings/apertus",
        json=configuration(key_action="replace", api_key="test-saved-key", json_mode=False),
    )
    reply = client.post("/api/model/test")
    assert reply.status_code == 200 and reply.json()["saved"]
    assert requests[0].headers["authorization"] == "Bearer test-saved-key"
    assert "response_format" not in json.loads(requests[0].content)
    failure = client.post("/api/model/test")
    assert failure.status_code == 504 and failure.json()["code"] == "model_timeout"
    assert "test-saved-key" not in failure.text
    unreachable = client.post("/api/model/test")
    assert unreachable.status_code == 503 and unreachable.json()["code"] == "model_unreachable"
    assert client.get("/api/settings/apertus").json()["api_key_configured"]


@pytest.mark.parametrize(
    "changes",
    [
        {"base_url": "https://user:password@inference.example/v1"},
        {"base_url": "https://inference.example/v1?api_key=bad"},
        {"base_url": "https://inference.example/v1/chat/completions"},
        {"base_url": "file:///tmp/model"},
        {"timeout_seconds": 301},
        {"context_chars": 0},
        {"max_tokens": 127},
        {"temperature": 3},
        {"top_p": 1.1},
        {"presence_penalty": -2},
        {"reasoning_effort": "maximum"},
        {"provider": "infomaniak", "product_id": ""},
        {"provider": "infomaniak", "product_id": "not-a-number"},
    ],
)
def test_invalid_settings_do_not_echo_secrets_or_replace_working_configuration(harness, changes):
    client, _, _, _ = harness
    accepted = client.patch("/api/settings/apertus", json=configuration()).json()
    invalid = client.patch(
        "/api/settings/apertus",
        json=configuration(key_action="replace", api_key="test-secret-never-echoed", **changes),
    )
    assert invalid.status_code == 422
    assert "test-secret-never-echoed" not in invalid.text
    assert client.get("/api/settings/apertus").json() == accepted


def test_empty_replacement_key_is_rejected_and_empty_endpoint_disconnects(harness):
    client, _, _, _ = harness
    empty_key = client.patch("/api/settings/apertus", json=configuration(key_action="replace"))
    assert empty_key.status_code == 422
    saved = client.patch("/api/settings/apertus", json=configuration(base_url=""))
    assert saved.status_code == 200 and not saved.json()["configured"]
    assert client.post("/api/settings/apertus/test", json=configuration(base_url="")).status_code == 503


def test_parameter_change_during_analysis_preserves_original_model_and_marks_result_stale(harness):
    client, _, service, model = harness
    client.patch("/api/settings/apertus", json=configuration(model="test-before-change"))
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]},
    ).json()
    original = model.complete

    async def change_configuration_during_request(system, user):
        service.save_model_settings(
            ApertusSettingsInput(**configuration(model="test-after-change", max_tokens=2000))
        )
        return await original(system, user)

    model.complete = change_configuration_during_request
    response = client.post("/api/comparisons/" + comparison["id"] + "/analyse")
    assert response.status_code == 200
    assert response.json()["model"] == "test-before-change"
    assert response.json()["status"] == "succeeded" and response.json()["stale"]
    assert client.get("/api/comparisons/" + comparison["id"]).json()["analysis"]["stale"]
