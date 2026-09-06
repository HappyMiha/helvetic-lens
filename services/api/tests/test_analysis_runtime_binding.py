import asyncio
import copy
import json
from contextvars import ContextVar

import httpx
import pytest
from conftest import add_law, import_old
from runtime_fixtures import local_runtime

from helvetic_lens.analysis import AnswerDigest, InferenceBudget, ModelClient, structured_completion
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.runtime_binding import RuntimeSnapshot


def settings(**overrides):
    configured = Settings(
        _env_file=None,
        **{
            "apertus_provider": "docker", "apertus_model": "test-apertus",
            "apertus_base_url": "http://synthetic-manager/openai/v1",
            "apertus_request_retries": 2, "apertus_timeout_seconds": 5,
            **overrides,
        },
    )
    # Settings derives Docker URLs from the deployment environment. Keep the
    # intercepted test gateway explicit, including tests of endpoint changes.
    configured.apertus_base_url = overrides.get("apertus_base_url", "http://synthetic-manager/openai/v1")
    return configured


def transport(monkeypatch, handler):
    real_client = httpx.AsyncClient
    mock = httpx.MockTransport(handler)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client(transport=mock, **kwargs))


def reply(content="synthetic reply", binding="a" * 64):
    return httpx.Response(
        200, json={"choices": [{"message": {"content": content}}]},
        headers={"x-helvetic-runtime-binding": binding} if binding is not None else {},
    )


@pytest.mark.asyncio
async def test_concurrent_batches_share_one_probe_and_one_execution_pin(monkeypatch):
    calls = []

    async def handler(request):
        calls.append(request)
        if request.method == "GET":
            await asyncio.sleep(0.01)
            assert str(request.url) == "http://synthetic-manager/v1/runtime"
            return httpx.Response(200, json=local_runtime())
        assert request.headers["x-helvetic-runtime-binding"] == "a" * 64
        return reply()

    transport(monkeypatch, handler)
    model = ModelClient(settings())
    token = model.begin_trace()
    budget = InferenceBudget(3)
    result = await asyncio.gather(*(model.complete("system", f"batch {index}", budget=budget) for index in range(3)))
    trace = model.end_trace(token)
    assert result == ["synthetic reply"] * 3
    assert [call.method for call in calls].count("GET") == 1
    assert [call.method for call in calls].count("POST") == budget.used == 3
    assert len([event for event in trace if isinstance(event.get("runtime_binding"), dict)]) == 1
    assert all(event["runtime_binding"] == "a" * 64 for event in trace if event.get("outcome") == "success")
    assert model._runtime_binding.get() is None


@pytest.mark.asyncio
async def test_transient_retry_keeps_pin_but_deployment_change_never_retries(monkeypatch):
    calls = []

    async def handler(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=local_runtime())
        assert request.headers["x-helvetic-runtime-binding"] == "a" * 64
        if len(calls) == 2:
            return httpx.Response(503, json={"error": "synthetic transient failure"})
        return httpx.Response(409, json={"code": "runtime_binding_changed"})

    async def no_delay(_seconds):
        pass

    transport(monkeypatch, handler)
    monkeypatch.setattr("helvetic_lens.analysis.asyncio.sleep", no_delay)
    model = ModelClient(settings(apertus_request_retries=5))
    token = model.begin_trace()
    budget = InferenceBudget(3)
    with pytest.raises(DomainError) as error:
        await model.complete("system", "user", budget=budget)
    trace = model.end_trace(token)
    assert error.value.code == "runtime_binding_changed"
    assert [call.method for call in calls] == ["GET", "POST", "POST"]
    assert budget.used == 2
    assert trace[-1]["error_code"] == "runtime_binding_changed"


@pytest.mark.asyncio
@pytest.mark.parametrize("binding", [None, "b" * 64])
async def test_successful_http_with_missing_or_wrong_pin_is_not_an_accepted_answer(monkeypatch, binding):
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(200, json=local_runtime()) if request.method == "GET" else reply(binding=binding)

    transport(monkeypatch, handler)
    model = ModelClient(settings())
    with pytest.raises(DomainError) as error:
        await model.complete("system", "user")
    assert error.value.code == "runtime_binding_changed"
    assert [call.method for call in calls] == ["GET", "POST"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["unavailable", "invalid", "wrong_model", "transport", "floating_endpoint"])
async def test_unverifiable_runtime_sends_no_document_or_generation_request(monkeypatch, failure):
    calls = []

    async def handler(request):
        calls.append(request)
        assert request.method == "GET"
        assert not request.content
        if failure == "transport":
            raise httpx.ConnectError("Synthetic runtime unavailable")
        if failure == "unavailable":
            return httpx.Response(503)
        if failure == "invalid":
            return httpx.Response(200, json={"available": True})
        return httpx.Response(200, json=local_runtime(model="another-model"))

    transport(monkeypatch, handler)
    configured = settings()
    if failure == "floating_endpoint":
        configured.apertus_base_url = "http://unmanaged-runner/v1"
    model = ModelClient(configured)
    token = model.begin_trace()
    budget = InferenceBudget(3)
    for _ in range(2):
        with pytest.raises(DomainError):
            await model.complete("system", "PRIVATE_SYNTHETIC_DOCUMENT_SENTINEL", budget=budget)
    trace = model.end_trace(token)
    assert len(calls) == (0 if failure == "floating_endpoint" else 1)
    assert budget.used == 0
    assert not any(event.get("outcome") for event in trace)
    assert "PRIVATE_SYNTHETIC_DOCUMENT_SENTINEL" not in json.dumps(trace)


@pytest.mark.asyncio
async def test_model_connection_cannot_change_inside_an_analysis_scope(monkeypatch):
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(200, json=local_runtime()) if request.method == "GET" else reply()

    transport(monkeypatch, handler)
    model = ModelClient(settings())
    token = model.begin_trace()
    assert await model.complete("system", "first") == "synthetic reply"
    model.settings.apertus_provider = "custom"
    with pytest.raises(DomainError) as error:
        await model.complete("system", "second")
    assert error.value.code == "runtime_binding_changed"
    model.end_trace(token)
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_independent_scopes_do_not_share_runtime_state(monkeypatch):
    generation = ContextVar("synthetic_test_generation")
    calls = []

    async def handler(request):
        current = generation.get()
        calls.append((current, request.method))
        await asyncio.sleep(0)
        if request.method == "GET":
            return httpx.Response(200, json=local_runtime(generation=current))
        assert request.headers["x-helvetic-runtime-binding"] == current * 64
        return reply(binding=current * 64)

    transport(monkeypatch, handler)
    model = ModelClient(settings())

    async def run(current):
        context = generation.set(current)
        token = model.begin_trace()
        try:
            await model.complete("system", current)
            await model.complete("system", current)
        finally:
            trace = model.end_trace(token)
            generation.reset(context)
        return trace

    traces = await asyncio.gather(run("a"), run("b"))
    for current, trace in zip(("a", "b"), traces, strict=True):
        assert trace[0]["runtime_binding"]["deployment_id"] == current * 32
        assert calls.count((current, "GET")) == 1
        assert calls.count((current, "POST")) == 2
    assert model._runtime_binding.get() is None


@pytest.mark.asyncio
async def test_connection_changed_during_probe_never_receives_document(monkeypatch):
    model = ModelClient(settings())
    calls = []

    async def handler(request):
        calls.append(request)
        assert request.method == "GET"
        model.settings.apertus_base_url = "http://another-manager/openai/v1"
        return httpx.Response(200, json=local_runtime())

    transport(monkeypatch, handler)
    token = model.begin_trace()
    budget = InferenceBudget(3)
    with pytest.raises(DomainError) as error:
        await model.complete("system", "saved document", budget=budget)
    trace = model.end_trace(token)
    assert error.value.code == "runtime_binding_changed"
    assert budget.used == 0 and len(calls) == 1
    assert trace == [{"runtime_resolution_error": "runtime_binding_changed"}]


@pytest.mark.asyncio
async def test_cancelled_probe_releases_lock_for_remaining_batch(monkeypatch):
    entered = asyncio.Event()
    calls = []

    async def handler(request):
        calls.append(request)
        if len(calls) == 1:
            entered.set()
            await asyncio.Future()
        return httpx.Response(200, json=local_runtime()) if request.method == "GET" else reply()

    transport(monkeypatch, handler)
    model = ModelClient(settings())
    token = model.begin_trace()
    first = asyncio.create_task(model.complete("system", "cancelled"))
    await asyncio.wait_for(entered.wait(), 1)
    second = asyncio.create_task(model.complete("system", "remaining"))
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    assert await asyncio.wait_for(second, 1) == "synthetic reply"
    trace = model.end_trace(token)
    assert [call.method for call in calls] == ["GET", "GET", "POST"]
    assert len([event for event in trace if isinstance(event.get("runtime_binding"), dict)]) == 1


@pytest.mark.asyncio
async def test_slow_runtime_probe_has_wall_clock_deadline_and_does_not_retry(monkeypatch):
    calls = []

    async def handler(request):
        calls.append(request)
        await asyncio.Future()

    transport(monkeypatch, handler)
    model = ModelClient(settings())
    with model.runtime_scope():
        with pytest.raises(DomainError) as error:
            await asyncio.wait_for(model.bound_runtime(probe_timeout=0.01), 1)
        assert error.value.code == "model_runtime_unavailable"
        with pytest.raises(DomainError):
            await model.complete("system", "must not be transmitted")
    assert [call.method for call in calls] == ["GET"]


def test_runtime_provenance_whitelists_metadata_and_rejects_inconsistent_identity():
    snapshot = local_runtime()
    snapshot["unknown_provider_metadata"] = "must not persist"
    snapshot["hardware"]["unknown_provider_metadata"] = "must not persist"
    snapshot["hardware"]["cuda_devices"][0]["unknown_provider_metadata"] = "must not persist"
    assert "must not persist" not in RuntimeSnapshot.model_validate(snapshot).model_dump_json()
    snapshot["identity"]["model_revision"] = "5" * 40
    with pytest.raises(ValueError, match="disagrees"):
        RuntimeSnapshot.model_validate(snapshot)


@pytest.mark.asyncio
async def test_structured_repair_uses_the_original_pin_and_budget(monkeypatch):
    calls = []

    async def handler(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=local_runtime())
        assert request.headers["x-helvetic-runtime-binding"] == "a" * 64
        return reply("{broken JSON" if len(calls) == 2 else '{"supported":true,"citation_rows":[1]}')

    transport(monkeypatch, handler)
    model = ModelClient(settings())
    token = model.begin_trace()
    budget = InferenceBudget(3)
    evidence = [{"version_id": "v1", "passage_id": "p1", "text": "Synthetic saved wording."}]
    result = await structured_completion(
        model, "system", {"evidence": {"columns": ["row_number", "text"], "rows": [[1, evidence[0]["text"]]]}},
        AnswerDigest, evidence, validate_citations=False, require_supported=True,
        numeric_reference_count=1, numeric_reference_evidence=evidence, budget=budget,
    )
    trace = model.end_trace(token)
    assert result["citation_rows"] == [1]
    assert budget.used == 2
    assert [call.method for call in calls] == ["GET", "POST", "POST"]
    assert trace[-1]["validation"] == "accepted" and trace[-1]["repair"] is True


def test_restart_changes_execution_pin_but_not_reusable_identity():
    first = RuntimeSnapshot.model_validate(local_runtime())
    restarted = RuntimeSnapshot.model_validate(local_runtime(generation="b"))
    upgraded = RuntimeSnapshot.model_validate(local_runtime(revision="5"))
    assert first.binding_fingerprint != restarted.binding_fingerprint
    assert first.identity_fingerprint() == restarted.identity_fingerprint()
    assert first.identity_fingerprint() != upgraded.identity_fingerprint()
    unknown = RuntimeSnapshot.model_validate({**local_runtime(), "identity": None})
    assert unknown.identity_fingerprint() is None


@pytest.mark.parametrize("kind", ["analyse", "ask"])
@pytest.mark.parametrize("wrong_reply", [False, True])
def test_saved_analysis_uses_request_binding_not_post_run_inventory(harness, monkeypatch, kind, wrong_reply):
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
    original = local_runtime()
    runtime = copy.deepcopy(original)
    calls = []

    async def forbidden_inventory():
        raise AssertionError("A later inventory must never relabel the model that served this answer")

    monkeypatch.setattr(service.model_manager, "inventory", forbidden_inventory)

    async def handler(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=runtime)
        assert request.headers["x-helvetic-runtime-binding"] == original["binding_fingerprint"]
        runtime.update(local_runtime(generation="b", revision="5"))
        content = '{"impact":"low","citation_rows":[1]}' if kind == "analyse" else '{"supported":true,"citation_rows":[1]}'
        return reply(content, binding="b" * 64 if wrong_reply else original["binding_fingerprint"])

    transport(monkeypatch, handler)
    route = f"/api/comparisons/{comparison['id']}"
    response = client.post(route + "/" + kind, json={"question": "What is the retention period?"} if kind == "ask" else {})
    assert response.status_code == (409 if kind == "ask" and wrong_reply else 200), response.text
    history = client.get(route + "/ai-history").json()["items"]
    assert len(history) == 1
    record = history[0]
    assert record["status"] == ("failed" if wrong_reply else "succeeded")
    provenance = record["provenance"]
    assert provenance["model_revision"] == original["model_revision"]
    assert provenance["artifact_sha256"] == original["artifact_sha256"]
    assert provenance["runtime_binding"]["deployment_id"] == original["deployment_id"]
    assert provenance["runtime_identity_fingerprint"] == RuntimeSnapshot.model_validate(original).identity_fingerprint()
    assert provenance["runtime_binding_state"] == ("changed" if wrong_reply else "verified_responses")
    assert provenance["provider_calls"] == 1
    assert record["analysis_plan"]["actual"]["runtime_binding"]["binding_fingerprint"] == original["binding_fingerprint"]
    assert [call.method for call in calls] == ["GET", "POST"]
    if wrong_reply:
        assert not record["result"]
    else:
        assert record["result"]["citations"]
