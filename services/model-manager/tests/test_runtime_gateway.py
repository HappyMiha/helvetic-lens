import asyncio
import importlib
import json
import sys

import httpx
import pytest
from helvetic_lens.analysis import (
    AnswerDigest,
    InferenceBudget,
    ModelClient,
    structured_completion,
)
from test_runtime_binding import runtime as runtime_fixture
from test_runtime_binding import start

runtime = runtime_fixture


@pytest.fixture
def gateway(runtime, monkeypatch, tmp_path):
    manager, _, _ = runtime
    snapshot = start(runtime)
    monkeypatch.setenv("MODEL_MANAGER_CATALOG", str(manager.catalog_path))
    monkeypatch.setenv("MODEL_MANAGER_LIBRARY", str(tmp_path / "gateway-import"))
    monkeypatch.setenv("MODEL_MANAGER_LLAMA_SERVER", str(manager.llama_server))
    sys.modules.pop("model_manager.app", None)
    module = importlib.import_module("model_manager.app")
    monkeypatch.setattr(module, "manager", manager)
    return module, manager, snapshot


def clients(module, monkeypatch, handler):
    real_client = httpx.AsyncClient
    async def route(request):
        metadata = runner_metadata(request)
        return metadata if metadata is not None else await handler(request)

    transport = httpx.MockTransport(route)
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs))
    return real_client(transport=httpx.ASGITransport(app=module.app), base_url="http://synthetic-manager")


def runner_metadata(request):
    if request.url.path == "/props":
        return httpx.Response(200, json={"default_generation_settings": {"n_ctx": 4096}, "total_slots": 1})
    if request.url.path.endswith("/input_tokens"):
        return httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": 32})
    return None


def assert_released(module, manager):
    assert not manager.inference_leases
    assert not module.admission.owners
    assert not module.admission.waiting


@pytest.mark.asyncio
async def test_runtime_endpoint_and_pinned_proxy_return_the_same_deployment(gateway, monkeypatch):
    module, manager, snapshot = gateway
    calls = []

    async def handler(request):
        calls.append(request)
        assert manager.inference_leases
        return httpx.Response(200, json={"choices": [{"message": {"content": "synthetic answer"}}]})

    async with clients(module, monkeypatch, handler) as client:
        observed = await client.get("/v1/runtime")
        assert observed.json() == snapshot
        payload = {"model": "local-apertus", "messages": [{"role": "user", "content": "synthetic question"}]}
        response = await client.post(
            "/openai/v1/chat/completions", json=payload,
            headers={"X-Helvetic-Runtime-Binding": snapshot["binding_fingerprint"]},
        )
        assert response.status_code == 200
        assert response.headers["x-helvetic-runtime-binding"] == snapshot["binding_fingerprint"]
        assert response.headers["x-helvetic-deployment-id"] == snapshot["deployment_id"]
        assert response.json()["choices"][0]["message"]["content"] == "synthetic answer"
        assert len(calls) == 1
        assert str(calls[0].url) == manager.inference_targets()[0]["url"] + "/v1/chat/completions"
        assert json.loads(calls[0].content) == payload
        assert "x-helvetic-runtime-binding" not in calls[0].headers
    assert_released(module, manager)


@pytest.mark.asyncio
@pytest.mark.parametrize("payload,binding,status,code", [
    ({"model": "local-apertus"}, "0" * 64, 409, "runtime_binding_changed"),
    ({"model": "local-apertus"}, "", 409, "runtime_binding_changed"),
    ({"model": "wrong-model"}, None, 409, "runtime_model_mismatch"),
    ({"model": " "}, None, 400, "invalid_model_request"),
    ({}, None, 400, "invalid_model_request"),
    ([], None, 400, "invalid_model_request"),
])
async def test_invalid_or_stale_request_is_not_forwarded(gateway, monkeypatch, payload, binding, status, code):
    module, manager, _ = gateway

    async def forbidden(_request):
        raise AssertionError("A rejected request must not spend an inference call")

    async with clients(module, monkeypatch, forbidden) as client:
        response = await client.post(
            "/openai/v1/chat/completions", json=payload,
            headers={"X-Helvetic-Runtime-Binding": binding} if binding is not None else {},
        )
        assert response.status_code == status
        assert response.json()["code"] == code
    assert_released(module, manager)


async def queued(module):
    for _ in range(100):
        if module.admission.waiting:
            return
        await asyncio.sleep(0.001)
    raise AssertionError("Request did not reach the admission queue")


@pytest.mark.asyncio
async def test_queued_pin_rejects_a_restart_of_the_same_model(gateway, runtime, monkeypatch):
    module, manager, snapshot = gateway
    held, _ = await module.admission.acquire("holder", "interactive")

    async def forbidden(_request):
        raise AssertionError("Old plan reached the new runner")

    async with clients(module, monkeypatch, forbidden) as client:
        request = asyncio.create_task(client.post(
            "/openai/v1/chat/completions", json={"model": "local-apertus"},
            headers={"X-Helvetic-Runtime-Binding": snapshot["binding_fingerprint"]},
        ))
        await queued(module)
        manager.stop_model("apertus-test")
        start(runtime)
        await module.admission.release(held, "holder")
        response = await asyncio.wait_for(request, 2)
        assert response.status_code == 409
        assert response.json()["code"] == "runtime_binding_changed"
    assert_released(module, manager)


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_block_next_organization(gateway, monkeypatch):
    module, manager, snapshot = gateway
    held, _ = await module.admission.acquire("holder", "interactive")
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"ok": True})

    async with clients(module, monkeypatch, handler) as client:
        request = asyncio.create_task(client.post(
            "/openai/v1/chat/completions", json={"model": "local-apertus"},
            headers={"X-Helvetic-Runtime-Binding": snapshot["binding_fingerprint"]},
        ))
        await queued(module)
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request
        assert not module.admission.waiting
        await module.admission.release(held, "holder")
        response = await asyncio.wait_for(client.post(
            "/openai/v1/chat/completions", json={"model": "local-apertus"},
            headers={"X-Helvetic-Organization": "next-organization"},
        ), 2)
        assert response.status_code == 200
        assert len(calls) == 1
    assert_released(module, manager)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["http_error", "transport_error", "cancel"])
async def test_proxy_releases_lease_and_slot_on_every_terminal_path(gateway, monkeypatch, failure):
    module, manager, snapshot = gateway
    entered = asyncio.Event()
    finish = asyncio.Event()

    async def handler(request):
        entered.set()
        await finish.wait()
        if failure == "transport_error":
            raise httpx.RemoteProtocolError("synthetic incomplete response")
        return httpx.Response(500, json={"error": "synthetic runner error"})

    async with clients(module, monkeypatch, handler) as client:
        request = asyncio.create_task(client.post(
            "/openai/v1/chat/completions", json={"model": "local-apertus"},
            headers={"X-Helvetic-Runtime-Binding": snapshot["binding_fingerprint"]},
        ))
        await asyncio.wait_for(entered.wait(), 2)
        stop = await client.post("/v1/models/apertus-test/stop")
        assert stop.status_code == 409
        assert stop.json()["code"] == "model_busy"
        if failure == "cancel":
            request.cancel()
            with pytest.raises(asyncio.CancelledError):
                await request
        else:
            finish.set()
            response = await asyncio.wait_for(request, 2)
            assert response.status_code == (500 if failure == "http_error" else 502)
        await asyncio.sleep(0)
        assert_released(module, manager)
        assert (await client.post("/v1/models/apertus-test/stop")).status_code == 200
        assert (await client.get("/v1/runtime")).json()["available"] is False


@pytest.mark.asyncio
async def test_admission_timeout_removes_waiter_before_next_request(gateway):
    module, manager, snapshot = gateway
    held, _ = await module.admission.acquire("holder", "interactive")
    with pytest.raises(TimeoutError):
        await module.admission.acquire(
            "timed-out", "interactive", timeout=0.01, expected_binding=snapshot["binding_fingerprint"],
        )
    assert not module.admission.waiting
    await module.admission.release(held, "holder")
    next_target, _ = await asyncio.wait_for(module.admission.acquire("next", "interactive"), 1)
    await module.admission.release(next_target, "next")
    assert_released(module, manager)


@pytest.mark.asyncio
async def test_real_assistant_client_uses_gateway_binding_end_to_end(gateway, monkeypatch):
    from helvetic_lens.ai_capabilities import RuntimeIdentity
    from helvetic_lens.config import Settings
    from helvetic_lens.model_manager_client import ModelManagerClient

    module, manager, snapshot = gateway
    # The manager's actual schema is consumable by the capability contract.
    assert RuntimeIdentity.model_validate(snapshot["identity"]).model_id == "apertus-test"
    real_client = httpx.AsyncClient
    asgi = httpx.ASGITransport(app=module.app)
    runner_calls = []

    async def route(request):
        if request.url.host == "synthetic-manager":
            return await asgi.handle_async_request(request)
        metadata = runner_metadata(request)
        if metadata is not None:
            return metadata
        runner_calls.append(request)
        assert manager.inference_leases
        return httpx.Response(200, json={"choices": [{"message": {"content": "synthetic end-to-end reply"}}]})

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(route), **kwargs),
    )
    client = ModelManagerClient(Settings(_env_file=None, model_manager_url="http://synthetic-manager"))
    result = await client.complete_profile("assistant-lite", "synthetic-org", [{"role": "user", "content": "test"}])
    assert result["content"] == "synthetic end-to-end reply"
    assert result["runtime_binding"] == snapshot["binding_fingerprint"]
    assert len(runner_calls) == 1
    assert json.loads(runner_calls[0].content)["model"] == snapshot["served_model_id"]
    assert_released(module, manager)


@pytest.mark.asyncio
async def test_real_analysis_client_carries_one_binding_through_gateway(gateway, monkeypatch):
    from helvetic_lens.config import DomainError, Settings
    from helvetic_lens.runtime_binding import RuntimeSnapshot

    module, manager, snapshot = gateway
    assert RuntimeSnapshot.model_validate(snapshot).identity.model_id == "apertus-test"
    real_client = httpx.AsyncClient
    asgi = httpx.ASGITransport(app=module.app)
    runner_calls, probes = [], []

    async def route(request):
        if request.url.host == "synthetic-manager":
            if request.url.path == "/v1/runtime":
                probes.append(request)
            return await asgi.handle_async_request(request)
        metadata = runner_metadata(request)
        if metadata is not None:
            return metadata
        runner_calls.append(request)
        assert manager.inference_leases
        assert json.loads(request.content)["model"] == snapshot["served_model_id"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "synthetic analysis reply"}}]})

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(route), **kwargs),
    )
    settings = Settings(_env_file=None, apertus_provider="docker", apertus_model=snapshot["served_model_id"])
    settings.apertus_base_url = "http://synthetic-manager/openai/v1"
    client = ModelClient(settings)
    token = client.begin_trace()
    budget = InferenceBudget(3)
    for wording in ("synthetic batch", "synthetic synthesis"):
        assert await client.complete("system", wording, budget=budget) == "synthetic analysis reply"
    manager.stop_model("apertus-test")
    with pytest.raises(DomainError) as error:
        await client.complete("system", "must not reach runner", budget=budget)
    trace = client.end_trace(token)
    assert error.value.code == "runtime_binding_changed"
    assert len(probes) == 1 and len(runner_calls) == 2
    capture = trace[0]["runtime_binding"]
    assert capture["binding_fingerprint"] == snapshot["binding_fingerprint"]
    assert capture["hardware"] == RuntimeSnapshot.model_validate(snapshot).hardware.model_dump()
    assert_released(module, manager)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["fit", "restart", "oversized_repair"])
async def test_measured_allocator_uses_real_gateway_and_rechecks_final_generation(gateway, runtime, monkeypatch, mode):
    from helvetic_lens.config import DomainError, Settings

    module, manager, snapshot = gateway
    assert snapshot["prompt_budget_schema"] == "local-prompt-budget-v1"
    real_client = httpx.AsyncClient
    asgi = httpx.ASGITransport(app=module.app)
    counts, generated = [], []
    evidence = [{
        "version_id": side, "passage_id": f"p{index}", "text": f"Synthetic {side} rule {index}.",
        "change_id": f"c{index}", "change_kind": "modified", "side": side,
    } for index in range(4) for side in ("old", "new")]
    columns = ["row_number", "change_id", "text"]
    payload = {"evidence": {"columns": columns, "rows": [[number, item["change_id"], item["text"]] for number, item in enumerate(evidence, 1)]}}

    async def route(request):
        if request.url.host == "synthetic-manager":
            if mode == "restart" and request.url.path == "/openai/v1/chat/completions":
                # Replacement between allocation and decoding; no lease is held
                # outside a gateway request. The previous pin must reject it.
                manager.stop_model("apertus-test")
                start(runtime)
            return await asgi.handle_async_request(request)
        if request.url.path == "/props":
            return runner_metadata(request)
        wire = json.loads(request.content)
        supplied = json.loads(wire["messages"][-1]["content"])
        assert manager.inference_leases
        if request.url.path.endswith("/input_tokens"):
            count = 5000 if "repair" in supplied else 350 + 600 * len(supplied["evidence"]["rows"])
            counts.append((wire, count))
            return httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": count})
        assert counts[-1][0] == wire
        assert counts[-1][1] + wire["max_tokens"] + 128 <= 4096
        generated.append(wire)
        content = {"supported": True, "citation_rows": [999 if mode == "oversized_repair" else 1]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}}]})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(route), **kwargs))
    configuration = Settings(_env_file=None, apertus_provider="docker", apertus_model=snapshot["served_model_id"], apertus_max_tokens=700)
    configuration.apertus_base_url = "http://synthetic-manager/openai/v1"
    client = ModelClient(configuration)
    token = client.begin_trace()
    budget = InferenceBudget(3)
    allocation = {}
    attempt = structured_completion(
        client, "Use only the synthetic supplied rows.", payload, AnswerDigest, evidence,
        validate_citations=False, numeric_reference_count=8, numeric_reference_evidence=evidence,
        budget=budget, allocation=allocation,
    )
    if mode == "fit":
        result = await attempt
        assert result["citation_rows"] == [1]
    else:
        with pytest.raises(DomainError) as error:
            await attempt
        assert error.value.code == ("runtime_binding_changed" if mode == "restart" else "model_context_exceeded")
    trace = client.end_trace(token)
    assert allocation["row_numbers"] == [1, 2, 3, 4]
    assert allocation["count_probes"] == 2
    assert len(generated) == (0 if mode == "restart" else 1)
    if mode == "oversized_repair":
        assert trace[-1].get("outcome") == "error"
        assert any(not event["prompt_token_measurement"]["fits"] for event in trace if event.get("prompt_token_measurement"))
    assert_released(module, manager)
