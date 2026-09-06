"""Real API/cache/job paths with synthetic local HTTP, never a real model."""

import asyncio
import copy
import json

import httpx
import pytest
from conftest import add_law, import_old
from runtime_fixtures import local_runtime

from helvetic_lens.analysis import ModelClient
from helvetic_lens.models import Job
from helvetic_lens.runtime_binding import RuntimeSnapshot


@pytest.fixture
def bound_app(harness, monkeypatch):
    client, _, service, _ = harness
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post("/api/comparisons", json={
        "old_version_id": old["id"], "new_version_id": law["current_version_id"],
    }).json()
    service.settings.apertus_provider = "docker"
    service.settings.apertus_base_url = "http://synthetic-manager/openai/v1"
    service.settings.apertus_model = "test-apertus"
    service.model_client = ModelClient(service.settings, service.integration_logger)
    state = {"runtime": local_runtime(), "offline": False, "wrong_reply": False, "calls": []}
    real_client = httpx.AsyncClient

    async def handler(request):
        state["calls"].append(request)
        if request.method == "GET":
            if request.url.path == "/v1/inventory":
                return httpx.Response(200, json={"deployment": {"state": "ready"}})
            assert request.url.path == "/v1/runtime"
            return httpx.Response(503) if state["offline"] else httpx.Response(200, json=state["runtime"])
        assert request.headers["x-helvetic-runtime-binding"] == state["runtime"]["binding_fingerprint"]
        data = json.loads(request.content)
        properties = data["response_format"]["schema"]["properties"]
        answer = {"supported": True, "citation_rows": [1]} if "supported" in properties else {"impact": "low", "citation_rows": [1]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(answer)}}]}, headers={
            "x-helvetic-runtime-binding": "f" * 64 if state["wrong_reply"] else state["runtime"]["binding_fingerprint"],
        })

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    return client, service, law, comparison, state


def run(client, comparison, kind):
    return client.post(
        f"/api/comparisons/{comparison['id']}/{kind}",
        json={"question": "What is the retention period?", "output_locale": "en-CH"} if kind.startswith("ask") else {"output_locale": "en-CH"},
    )


def record_id(result):
    return result.get("record_id") or result["id"]


@pytest.mark.parametrize("field", [
    "model_id", "model_revision", "artifact_sha256", "tokenizer_sha256",
    "chat_template_sha256", "runtime_sha256", "hardware_profile",
    "context_window_tokens", "default_output_tokens", "served_model_id",
])
def test_reuse_identity_changes_for_each_execution_input(field):
    original = local_runtime()
    changed = copy.deepcopy(original)
    if field in changed["identity"]:
        previous = changed["identity"][field]
        changed["identity"][field] = ("5" * len(previous)) if field.endswith("sha256") or field == "model_revision" else "another-synthetic-value"
        if field in changed:
            changed[field] = changed["identity"][field]
    elif field == "served_model_id":
        changed[field] = "another-served-alias"
    else:
        changed[field] += 100
    assert RuntimeSnapshot.model_validate(original).cache_identity() != RuntimeSnapshot.model_validate(changed).cache_identity()


@pytest.mark.parametrize("kind", ["ask", "analyse"])
def test_exact_runtime_reuses_answer_across_restart_but_new_revision_does_not(bound_app, kind):
    client, _, law, comparison, state = bound_app
    first = run(client, comparison, kind)
    assert first.status_code == 200, first.text
    first = first.json()
    assert first["cached"] is False
    assert first["analysis_plan"]["runtime_cache_identity"] == RuntimeSnapshot.model_validate(state["runtime"]).cache_identity()
    state["runtime"] = local_runtime(generation="b")
    repeated = run(client, comparison, kind).json()
    assert repeated["cached"] is True and record_id(repeated) == record_id(first)
    assert [call.method for call in state["calls"]] == ["GET", "POST", "GET"]
    state["runtime"] = local_runtime(generation="c", revision="5")
    changed = run(client, comparison, kind).json()
    assert changed["cached"] is False and record_id(changed) != record_id(first)
    assert [call.method for call in state["calls"]] == ["GET", "POST", "GET", "GET", "POST"]
    before_history = len(state["calls"])
    history = client.get(f"/api/laws/{law['id']}/ai-history").json()["items"]
    assert len(state["calls"]) == before_history
    assert len(history) == 2
    assert {item["provenance"]["model_revision"] for item in history} == {"1" * 40, "5" * 40}
    original = next(item for item in history if item["id"] == record_id(first))
    assert original["provenance"]["runtime_binding"]["deployment_id"] == "a" * 32
    assert original["use_count"] == 2


@pytest.mark.parametrize("kind", ["ask", "analyse"])
def test_incomplete_identity_reuses_only_same_live_deployment(bound_app, kind):
    client, _, _, comparison, state = bound_app
    state["runtime"]["identity"] = None
    first = run(client, comparison, kind).json()
    repeated = run(client, comparison, kind).json()
    assert repeated["cached"] is True and record_id(repeated) == record_id(first)
    state["runtime"] = {**local_runtime(generation="b"), "identity": None}
    restarted = run(client, comparison, kind).json()
    assert restarted["cached"] is False and record_id(restarted) != record_id(first)


def test_views_and_report_reuse_agree_after_model_change_and_remain_readable_offline(bound_app):
    client, service, law, comparison, state = bound_app
    report = run(client, comparison, "analyse").json()
    path = f"/api/comparisons/{comparison['id']}"
    assert client.get(path).json()["analysis"]["stale"] is False
    assert client.get("/api/laws").json()[0]["analysis"]["stale"] is False
    assert client.get(f"/api/laws/{law['id']}").json()["analysis"]["stale"] is False
    assert client.get("/api/impact-matrix").json()["rows"][0]["report_state"] == "current"
    state["runtime"] = local_runtime(generation="b", revision="5")
    for route in (path, f"/api/laws/{law['id']}"):
        shown = client.get(route).json()["analysis"]
        assert shown["id"] == report["id"] and shown["stale"] is True
    assert client.get("/api/laws").json()[0]["analysis"]["stale"] is True
    assert client.get("/api/impact-matrix").json()["rows"][0]["report_state"] == "stale"

    async def selected_report():
        from helvetic_lens.models import Comparison, Profile
        async with service.runtime_cache_scope():
            with service.db.session() as session:
                return service.current_impact_report(
                    session, session.get(Comparison, comparison["id"]), session.get(Profile, service.tenant_record_id),
                    service.settings, service.prompt_settings, "en-CH",
                )

    assert asyncio.run(selected_report()) is None
    state["offline"] = True
    assert client.get(path).status_code == 200
    assert client.get(path).json()["analysis"]["stale"] is True
    before_history = len(state["calls"])
    history = client.get(path + "/ai-history").json()["items"]
    assert len(state["calls"]) == before_history
    assert history[0]["result"] == report["result"]
    assert sum(call.method == "POST" for call in state["calls"]) == 1


def test_rejected_answer_retry_preserves_failed_history(bound_app):
    client, _, _, comparison, state = bound_app
    state["wrong_reply"] = True
    assert run(client, comparison, "ask").status_code == 409
    path = f"/api/comparisons/{comparison['id']}/ai-history"
    failure = client.get(path).json()["items"][0]
    assert failure["status"] == "failed"
    state["wrong_reply"] = False
    recovered = run(client, comparison, "ask").json()
    assert recovered["cached"] is False and recovered["record_id"] != failure["id"]
    history = client.get(path).json()["items"]
    assert len(history) == 2
    assert next(item for item in history if item["id"] == failure["id"]) == failure


@pytest.mark.parametrize("kind", ["ask", "analyse"])
def test_new_count_protocol_cannot_reuse_unmeasured_answer_with_same_model_identity(bound_app, kind):
    client, _, _, comparison, state = bound_app
    first = run(client, comparison, kind)
    assert first.status_code == 200
    path = f"/api/comparisons/{comparison['id']}/ai-history"
    original = client.get(path).json()["items"][0]
    before = RuntimeSnapshot.model_validate(state["runtime"])
    state["runtime"]["prompt_budget_schema"] = "local-prompt-budget-v1"
    after = RuntimeSnapshot.model_validate(state["runtime"])
    assert before.identity_fingerprint() == after.identity_fingerprint()
    assert before.binding_fingerprint == after.binding_fingerprint
    assert before.cache_identity() != after.cache_identity()
    # This deliberately old transport cannot return a verified count despite
    # advertising it. The new attempt must fail, never relabel the old answer.
    attempted = run(client, comparison, kind)
    assert attempted.status_code == (422 if kind == "ask" else 200)
    history = client.get(path).json()["items"]
    assert len(history) == 2 and history[0]["status"] == "failed"
    assert "token measurement does not match this request" in history[0]["error"]
    assert history[0]["provenance"]["provider_calls"] == 0
    assert history[0]["provenance"]["evidence_allocations"][0]["status"] == "failed"
    assert next(item for item in history if item["id"] == original["id"]) == original
    assert state["calls"][-1].url.path.endswith("/input_tokens")


@pytest.mark.parametrize("kind", ["ask-jobs", "analyse-jobs"])
def test_completed_jobs_reuse_only_matching_runtime(bound_app, kind):
    client, _, _, comparison, state = bound_app
    first = run(client, comparison, kind)
    assert first.status_code == 202, first.text
    first = first.json()
    assert first["state"] == "succeeded", first
    repeated = run(client, comparison, kind).json()
    assert repeated["id"] == first["id"]
    assert repeated["result"]["data"]["cached"] is True
    state["runtime"] = local_runtime(generation="b", revision="5")
    changed = run(client, comparison, kind).json()
    assert changed["id"] != first["id"] and changed["state"] == "succeeded"
    assert changed["result"]["id"] != first["result"]["id"]
    assert sum(call.method == "POST" for call in state["calls"]) == 2


@pytest.mark.parametrize("kind", ["ask-jobs", "analyse-jobs"])
def test_model_change_while_queued_cannot_poison_original_job_cache_key(bound_app, kind):
    client, service, _, comparison, state = bound_app
    service.settings.job_execution_mode = "celery"
    queued = run(client, comparison, kind).json()
    assert queued["state"] == "queued"
    assert run(client, comparison, kind).json()["id"] == queued["id"]
    state["runtime"] = local_runtime(generation="b", revision="5")
    finished = asyncio.run(service.execute_job(queued["id"]))
    assert finished["state"] == "succeeded", finished
    historical = copy.deepcopy(finished["result"])
    state["runtime"] = local_runtime(generation="c")
    replacement = run(client, comparison, kind).json()
    assert replacement["id"] != queued["id"] and replacement["state"] == "queued"
    assert client.get(f"/api/jobs/{queued['id']}").json()["result"] == historical
    with service.db.session() as session:
        old_job = session.get(Job, queued["id"])
        assert old_job.idempotency_key == f"superseded:{old_job.id}"
        assert old_job.correlation["superseded_idempotency_key"].startswith("ask:" if kind.startswith("ask") else "impact:")
        assert old_job.payload["runtime_cache_identity"] == RuntimeSnapshot.model_validate(local_runtime()).cache_identity()
    # No duplicate generation occurs merely by queueing or inspecting old work.
    assert sum(call.method == "POST" for call in state["calls"]) == 1


@pytest.mark.parametrize("kind", ["ask-jobs", "analyse-jobs"])
def test_completed_work_queued_without_runtime_cannot_be_reused_as_current_offline(bound_app, kind):
    client, service, _, comparison, state = bound_app
    service.settings.job_execution_mode = "celery"
    state["offline"] = True
    queued = run(client, comparison, kind).json()
    assert queued["state"] == "queued"
    state["offline"] = False
    finished = asyncio.run(service.execute_job(queued["id"]))
    assert finished["state"] == "succeeded", finished
    state["offline"] = True
    later = run(client, comparison, kind).json()
    assert later["id"] != queued["id"] and later["state"] == "queued"
    assert client.get(f"/api/jobs/{queued['id']}").json()["result"] == finished["result"]
    assert sum(call.method == "POST" for call in state["calls"]) == 1


def test_runtime_observation_is_scoped_to_client_and_cleared_on_cancellation(bound_app):
    _, service, _, _, state = bound_app
    original = service.model_client

    async def scopes():
        with pytest.raises(asyncio.CancelledError):
            async with service.runtime_cache_scope():
                first = service.cache_runtime_identity()
                assert first is not None
                service.model_client = ModelClient(service.settings, service.integration_logger)
                assert service.cache_runtime_identity() is None
                state["runtime"] = local_runtime(generation="b", revision="5")
                async with service.runtime_cache_scope():
                    assert service.cache_runtime_identity() != first
                service.model_client = original
                assert service.cache_runtime_identity() == first
                raise asyncio.CancelledError()
        assert service.cache_runtime_identity() is None
        assert original._runtime_binding.get() is None

    asyncio.run(scopes())
    assert [call.method for call in state["calls"]] == ["GET", "GET"]
