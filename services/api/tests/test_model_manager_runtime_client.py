import json

import httpx
import pytest

from helvetic_lens.config import DomainError, Settings
from helvetic_lens.model_manager_client import ModelManagerClient


@pytest.fixture
def setup(monkeypatch):
    profile = {
        "ready": True, "selected_model": {
            "served_model_id": "synthetic-model", "id": "synthetic-model-id",
            "immutable_revision": "c" * 40, "artifact_sha256": "d" * 64,
        },
        "generation": {"max_tokens": 128}, "policy": {"priority": "interactive"},
    }
    snapshot = {
        "schema_version": "local-runtime-binding-v1", "available": True,
        "binding_fingerprint": "a" * 64, "deployment_id": "b" * 32,
        "served_model_id": "synthetic-model", "identity": None,
        "model_id": "synthetic-model-id", "model_revision": "c" * 40, "artifact_sha256": "d" * 64,
    }
    returned_binding = [snapshot["binding_fingerprint"]]
    calls = []

    async def handler(request):
        calls.append(request)
        if request.url.path == "/v1/profiles/assistant-lite":
            return httpx.Response(200, json=profile)
        if request.url.path == "/v1/runtime":
            return httpx.Response(200, json=snapshot)
        assert request.url.path == "/openai/v1/chat/completions"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "synthetic answer"}}]},
            headers={"x-helvetic-runtime-binding": returned_binding[0]} if returned_binding[0] else {},
        )

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs))
    client = ModelManagerClient(Settings(_env_file=None, model_manager_url="http://synthetic-manager"))
    return client, profile, snapshot, returned_binding, calls


@pytest.mark.asyncio
async def test_assistant_binds_profile_and_checks_response_without_promoting_a_model(setup):
    client, _, snapshot, _, calls = setup
    result = await client.complete_profile(
        "assistant-lite", "organization-a", [{"role": "user", "content": "synthetic question"}],
    )
    assert [call.url.path for call in calls] == [
        "/v1/profiles/assistant-lite", "/v1/runtime", "/openai/v1/chat/completions",
    ]
    request = calls[-1]
    assert request.headers["x-helvetic-runtime-binding"] == snapshot["binding_fingerprint"]
    assert request.headers["x-helvetic-organization"] == "organization-a"
    assert "authorization" not in request.headers
    assert json.loads(request.content)["model"] == "synthetic-model"
    assert json.loads(request.content)["max_tokens"] == 128
    assert result["content"] == "synthetic answer"
    assert result["runtime_binding"] == snapshot["binding_fingerprint"]
    assert "generated_explanation" not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value,code", [
    ("available", False, "assistant_local_unavailable"),
    ("available", 1, "assistant_local_unavailable"),
    ("binding_fingerprint", None, "assistant_local_unavailable"),
    ("binding_fingerprint", "not-a-hash", "assistant_local_unavailable"),
    ("deployment_id", "old-process", "assistant_local_unavailable"),
    ("schema_version", "unknown-version", "assistant_local_unavailable"),
    ("served_model_id", "a-different-model", "runtime_binding_changed"),
    ("model_id", "a-different-catalog-entry", "runtime_binding_changed"),
    ("model_revision", "e" * 40, "runtime_binding_changed"),
    ("artifact_sha256", "e" * 64, "runtime_binding_changed"),
])
async def test_changed_or_unavailable_runtime_never_receives_a_chat_request(setup, field, value, code):
    client, _, snapshot, _, calls = setup
    snapshot[field] = value
    with pytest.raises(DomainError) as error:
        await client.complete_profile("assistant-lite", "organization-a", [])
    assert error.value.code == code
    assert len(calls) == 2
    assert all(call.method == "GET" for call in calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("binding", [None, "c" * 64])
async def test_unbound_or_different_response_is_discarded_without_retry(setup, binding):
    client, _, _, returned_binding, calls = setup
    returned_binding[0] = binding
    with pytest.raises(DomainError) as error:
        await client.complete_profile("assistant-lite", "organization-a", [])
    assert error.value.code == "runtime_binding_changed"
    assert len([call for call in calls if call.method == "POST"]) == 1


@pytest.mark.asyncio
async def test_unready_assistant_profile_does_not_probe_or_start_a_model(setup):
    client, profile, _, _, calls = setup
    profile["ready"] = False
    with pytest.raises(DomainError) as error:
        await client.complete_profile("assistant-lite", "organization-a", [])
    assert error.value.code == "assistant_local_unavailable"
    assert len(calls) == 1
    assert calls[0].method == "GET"
