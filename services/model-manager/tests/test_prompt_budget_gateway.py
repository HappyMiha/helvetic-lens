import asyncio
import json

import httpx
import pytest
from test_runtime_binding import runtime as runtime_fixture
from test_runtime_gateway import assert_released
from test_runtime_gateway import gateway as gateway_fixture

runtime = runtime_fixture
gateway = gateway_fixture


def connect(module, monkeypatch, handler):
    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real(transport=httpx.MockTransport(handler), **kwargs))
    return real(transport=httpx.ASGITransport(app=module.app), base_url="http://synthetic-manager")


def request_body(**extra):
    return {
        "model": "local-apertus", "max_tokens": 700,
        "messages": [
            {"role": "system", "content": "Synthetic system with schema and citation rules"},
            {"role": "user", "content": "Gesetz / loi / legge / lescha / law: synthetic evidence 🧪"},
        ],
        "response_format": {"type": "json_object", "schema": {"type": "object", "properties": {"answer": {"type": "string"}}}},
        **extra,
    }


def runner_response(request, *, tokens=3268, context=4096):
    if request.url.path == "/props":
        return httpx.Response(200, json={"total_slots": 1, "default_generation_settings": {"n_ctx": context}})
    if request.url.path.endswith("/input_tokens"):
        return httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": tokens})
    assert request.url.path == "/v1/chat/completions"
    return httpx.Response(200, json={"choices": [{"message": {"content": "synthetic reply"}}]})


@pytest.mark.asyncio
@pytest.mark.parametrize("tokens,status,generations", [(3268, 200, 1), (3269, 422, 0)])
async def test_full_request_with_template_count_and_output_reserve_is_checked_before_generation(gateway, monkeypatch, tokens, status, generations):
    module, manager, snapshot = gateway
    calls = []

    async def handler(request):
        calls.append(request)
        assert manager.inference_leases and module.admission.owners
        return runner_response(request, tokens=tokens)

    async with connect(module, monkeypatch, handler) as client:
        response = await client.post("/openai/v1/chat/completions", json=request_body())
        assert response.status_code == status
        measured = json.loads(response.headers["x-helvetic-token-budget"])
        assert measured["input_tokens"] == tokens
        assert measured["reserved_output_tokens"] == 700
        assert measured["safety_tokens"] == 128
        assert measured["binding_fingerprint"] == snapshot["binding_fingerprint"]
        assert measured["fits"] is (status == 200)
        assert [request.url.path for request in calls] == ["/props", "/v1/chat/completions/input_tokens"] + ["/v1/chat/completions"] * generations
        assert json.loads(calls[1].content) == request_body()
        if generations:
            assert calls[1].content == calls[2].content
        else:
            assert response.json()["error"]["code"] == "context_length_exceeded"
            assert response.json()["code"] == "context_length_exceeded"
            assert "3269 input tokens" in response.json()["detail"]
            assert "context window holds 4096" in response.json()["detail"]
    assert_released(module, manager)


@pytest.mark.asyncio
@pytest.mark.parametrize("context,tokens,fits", [(2048, 1300, False), (8192, 3300, False), (2048, 1200, True)])
async def test_count_only_uses_actual_slot_context_capped_by_launch_and_never_generates(gateway, monkeypatch, context, tokens, fits):
    module, manager, _ = gateway
    calls = []

    async def handler(request):
        calls.append(request.url.path)
        return runner_response(request, tokens=tokens, context=context)

    async with connect(module, monkeypatch, handler) as client:
        response = await client.post("/openai/v1/chat/completions/input_tokens", json=request_body())
        assert response.status_code == 200
        measured = response.json()["token_budget"]
        assert response.json()["input_tokens"] == tokens
        assert measured["fits"] is fits
        assert measured["runner_context_tokens"] == context
        assert measured["context_window_tokens"] == min(context, 4096)
        assert calls == ["/props", "/v1/chat/completions/input_tokens"]
    assert_released(module, manager)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing_endpoint", "bad_json", "wrong_object", "boolean", "string", "zero", "negative", "missing_count", "transport", "timeout", "bad_props", "multi_slots"])
async def test_unverifiable_budget_fails_once_without_generation_or_raw_provider_leak(gateway, monkeypatch, failure):
    module, manager, _ = gateway
    calls = []
    monkeypatch.setattr("model_manager.prompt_budget.PREFLIGHT_SECONDS", 0.01)

    async def handler(request):
        calls.append(request.url.path)
        assert request.url.path != "/v1/chat/completions"
        if request.url.path == "/props":
            if failure in {"bad_props", "multi_slots"}:
                return httpx.Response(200, json={"total_slots": 2 if failure == "multi_slots" else 1, "default_generation_settings": {"n_ctx": 4096 if failure == "multi_slots" else True}})
            return runner_response(request)
        if failure == "missing_endpoint":
            return httpx.Response(404, text="private upstream detail")
        if failure == "bad_json":
            return httpx.Response(200, text="private upstream detail")
        if failure == "transport":
            raise httpx.RemoteProtocolError("private upstream detail")
        if failure == "timeout":
            await asyncio.sleep(60)
        data = {"object": "response.input_tokens", "input_tokens": 32}
        if failure == "wrong_object":
            data["object"] = "chat.completion"
        elif failure == "missing_count":
            del data["input_tokens"]
        else:
            data["input_tokens"] = {"boolean": True, "string": "32", "zero": 0, "negative": -1}.get(failure, 32)
        return httpx.Response(200, json=data)

    async with connect(module, monkeypatch, handler) as client:
        response = await asyncio.wait_for(client.post("/openai/v1/chat/completions", json=request_body()), 1)
        assert response.status_code == 422
        assert response.json()["code"] == "token_budget_unavailable"
        assert "private upstream detail" not in response.text
        assert len(calls) <= 2
    assert_released(module, manager)


@pytest.mark.asyncio
@pytest.mark.parametrize("extra", [{"max_tokens": 0}, {"max_tokens": -1}, {"max_tokens": True}, {"max_tokens": "700"}, {"max_tokens": None}, {"max_completion_tokens": 900}, {"n_predict": 900}, {"n": 2}, {"n": True}])
async def test_invalid_or_conflicting_output_limits_never_reach_runner(gateway, monkeypatch, extra):
    module, manager, _ = gateway

    async def forbidden(_request):
        raise AssertionError("Invalid limits must fail before accessing the runner")

    async with connect(module, monkeypatch, forbidden) as client:
        response = await client.post("/openai/v1/chat/completions", json=request_body(**extra))
        assert response.status_code == 422
        assert response.json()["code"] in {"invalid_output_token_limit", "invalid_response_count"}
    assert_released(module, manager)


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_lease_covers_counting_and_cancellation_releases_next_request(gateway, monkeypatch, cancel):
    module, manager, _ = gateway
    counting, release = asyncio.Event(), asyncio.Event()

    async def handler(request):
        if request.url.path.endswith("/input_tokens"):
            counting.set()
            await release.wait()
        return runner_response(request)

    async with connect(module, monkeypatch, handler) as client:
        pending = asyncio.create_task(client.post("/openai/v1/chat/completions", json=request_body()))
        await asyncio.wait_for(counting.wait(), 1)
        stop = await client.post("/v1/models/apertus-test/stop")
        assert stop.status_code == 409 and stop.json()["code"] == "model_busy"
        if cancel:
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
        else:
            release.set()
            assert (await pending).status_code == 200
        await asyncio.sleep(0)
        assert_released(module, manager)
        release.set()
        assert (await client.post("/openai/v1/chat/completions", json=request_body())).status_code == 200
    assert_released(module, manager)
