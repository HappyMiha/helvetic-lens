"""Saved relation conclusions follow the observed gateway, not inventory labels.

Real ModelClient/API/queue/SQL paths; HTTP, model text and mail are synthetic.
"""

import asyncio
import copy
import json
from dataclasses import replace

import httpx
import pytest
from runtime_fixtures import local_runtime
from sqlalchemy import select
from test_digest_periods import recipient
from test_digest_resume import record_mail
from test_relation_analysis import relation_delivery

from helvetic_lens import digests
from helvetic_lens.analysis import ModelClient
from helvetic_lens.config import DomainError
from helvetic_lens.impact_inbox import ImpactInboxFilters, ImpactInboxReader
from helvetic_lens.model_settings import local_docker_base_url
from helvetic_lens.models import DigestPreference, Job, RelationImpactAnalysis
from helvetic_lens.relation_runtime import current_fingerprint


def configure_local_relation(harness, monkeypatch):
    client, _, service, model = harness
    delivery, _ = relation_delivery(harness)
    service.settings.apertus_provider = "docker"
    service.settings.apertus_base_url = local_docker_base_url()
    service.settings.apertus_model = "test-apertus"
    service.model_client = ModelClient(service.settings, service.integration_logger)
    state = {"runtime": local_runtime(), "calls": [], "offline": False, "wrong_reply": False, "probes": 0}
    real_client = httpx.AsyncClient

    async def handler(request):
        state["calls"].append(request)
        if request.method == "GET":
            if request.url.path == "/v1/inventory":
                # Deliberately unchanged/incomplete: this cannot attest inference.
                return httpx.Response(200, json={"deployment": {"state": "ready", "model_revision": "inventory-is-not-evidence"}})
            assert request.url.path == "/v1/runtime"
            state["probes"] += 1
            if state.get("change_at_probe") == state["probes"]:
                state["runtime"] = local_runtime(generation="c", revision="5")
            if state["offline"]:
                return httpx.Response(503)
            return httpx.Response(200, json=state["runtime"])
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["x-helvetic-runtime-binding"] == state["runtime"]["binding_fingerprint"]
        data = json.loads(request.content)
        content = await model.complete(data["messages"][0]["content"], data["messages"][1]["content"])
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]}, headers={
            "x-helvetic-runtime-binding": "f" * 64 if state["wrong_reply"] else state["runtime"]["binding_fingerprint"],
        })

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    return client, service, model, delivery, state


@pytest.fixture
def local_relation(harness, monkeypatch):
    return configure_local_relation(harness, monkeypatch)

def run(app):
    client, _, _, delivery, _ = app
    response = client.post(f"/api/relation-candidates/{delivery}/analyse-jobs")
    assert response.status_code == 202, response.text
    result = response.json()
    assert result["state"] == "succeeded", result
    return result


def observation(service):
    async def capture():
        async with service.runtime_cache_scope():
            return service.relation_runtime_observation()
    return asyncio.run(capture())


def history(app):
    client, _, _, delivery, _ = app
    response = client.get(f"/api/relation-candidates/{delivery}/analyses")
    assert response.status_code == 200, response.text
    return response.json()


def test_same_identity_restart_reuses_job_and_keeps_original_provenance(local_relation):
    client, service, model, delivery, state = local_relation
    first = run(local_relation)
    saved = first["result"]["data"]
    assert saved["provenance"]["runtime_binding"]["deployment_id"] == "a" * 32
    state["runtime"] = local_runtime(generation="b")
    repeated = run(local_relation)
    assert repeated["id"] == first["id"] and len(model.calls) == 1
    assert history(local_relation)["current"]["id"] == saved["id"]
    for route in ("/api/impact-inbox", "/api/impact-inbox/page"):
        before = state["probes"]
        item = client.get(route).json()["items"][0]["items"][0]
        assert item["current_analysis_id"] == saved["id"]
        assert state["probes"] == before + 1
    # The service entry point also reuses only this immutable identity.
    cached = asyncio.run(service.analyse_relation_candidate(delivery))
    assert cached["cached"] and cached["id"] == saved["id"]
    assert cached["provenance"] == saved["provenance"] and len(model.calls) == 1


@pytest.mark.parametrize("field", [
    "model_revision", "artifact_sha256", "tokenizer_sha256", "chat_template_sha256",
    "runtime_sha256", "hardware_profile", "context_window_tokens", "default_output_tokens",
    "prompt_budget_schema",
])
def test_same_name_different_runtime_hides_old_conclusion_without_new_inference(local_relation, field):
    client, service, model, _, state = local_relation
    saved = run(local_relation)["result"]["data"]
    changed = copy.deepcopy(state["runtime"])
    if field in changed["identity"]:
        previous = changed["identity"][field]
        changed["identity"][field] = "5" * len(previous) if field.endswith("sha256") or field == "model_revision" else "other-hardware"
        if field in changed:
            changed[field] = changed["identity"][field]
    elif field == "prompt_budget_schema":
        changed[field] = "local-prompt-budget-v1"
    else:
        changed[field] += 128
    state["runtime"] = changed
    shown = history(local_relation)
    assert shown["current"] is None and shown["items"][0]["stale"]
    assert shown["items"][0]["result"] == saved["result"]
    assert shown["items"][0]["provenance"] == saved["provenance"]
    for route in ("/api/impact-inbox", "/api/impact-inbox/page"):
        item = client.get(route).json()["items"][0]["items"][0]
        assert item["current_analysis_id"] is None and item["latest_attempt_id"] == saved["id"]
        assert item["severity"] == "unknown"
        assert client.get(route, params={"severity": "medium"}).json()["items"] == []
    with service.db.session() as session:
        before = len(state["calls"])
        row = session.get(RelationImpactAnalysis, saved["id"])
        assert row.result == saved["result"] and row.analysis_plan == saved["analysis_plan"]
        assert len(state["calls"]) == before and len(model.calls) == 1


def test_partial_identity_restart_and_new_revision_need_new_analysis(local_relation):
    _, _, model, _, state = local_relation
    state["runtime"]["identity"] = None
    first = run(local_relation)
    assert run(local_relation)["id"] == first["id"]
    state["runtime"] = {**local_runtime(generation="b"), "identity": None}
    assert history(local_relation)["current"] is None
    second = run(local_relation)
    assert second["id"] != first["id"]
    state["runtime"] = local_runtime(generation="c", revision="5")
    third = run(local_relation)
    assert third["id"] != second["id"] and len(model.calls) == 3
    assert len(history(local_relation)["items"]) == 3


def test_offline_reads_keep_history_and_citations_but_never_promote_or_reuse_finished_job(local_relation):
    client, _, model, delivery, state = local_relation
    saved = run(local_relation)["result"]["data"]
    state["offline"] = True
    assert history(local_relation)["current"] is None
    assert client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]["current_analysis_id"] is None
    before = state["probes"]
    citation = saved["result"]["citations"][0]
    assert client.get(citation["url"]).json()["text"] == citation["quote"]
    assert state["probes"] == before
    response = client.post(f"/api/relation-candidates/{delivery}/analyse-jobs")
    assert response.status_code == 202 and response.json()["state"] == "retrying"
    repeated = client.post(f"/api/relation-candidates/{delivery}/analyse-jobs").json()
    assert repeated["id"] == response.json()["id"] and repeated["state"] != "succeeded"
    assert len(model.calls) == 1


def test_queued_job_cannot_use_old_runtime_identity_after_model_swap(local_relation):
    _, service, model, delivery, state = local_relation
    job = asyncio.run(service.enqueue_relation_analysis(delivery))
    state["runtime"] = local_runtime(generation="b", revision="5")
    completed = asyncio.run(service.execute_job(job["id"]))
    assert completed["state"] in {"retrying", "failed"}
    assert model.calls == [] and history(local_relation)["items"] == []
    with service.db.session() as session:
        stored = session.get(Job, job["id"])
        assert stored.error_code == "runtime_binding_changed"
    assert run(local_relation)["id"] != job["id"] and len(model.calls) == 1


def test_response_from_another_runtime_is_retained_as_failure(local_relation):
    client, _, model, delivery, state = local_relation
    state["wrong_reply"] = True
    response = client.post(f"/api/relation-candidates/{delivery}/analyse-jobs")
    assert response.status_code == 202
    failed = history(local_relation)
    assert failed["current"] is None and failed["items"][0]["status"] == "failed"
    assert failed["items"][0]["result"] is None
    state["wrong_reply"] = False
    run(local_relation)
    assert len(history(local_relation)["items"]) == 2 and len(model.calls) == 2


def digest_job(app):
    _, service, _, _, _ = app
    saved = run(app)["result"]["data"]
    user_id = recipient(service)
    service.save_digest_preference(user_id, enabled=True, frequency="daily", sources=[], severities=["medium"])
    return service.enqueue_digest_now(user_id), saved


def test_digest_preparation_restarts_and_final_delivery_rejects_changed_runtime(local_relation, monkeypatch):
    _, service, model, _, state = local_relation
    job, saved = digest_job(local_relation)
    sent = record_mail(monkeypatch)
    captured = observation(service)
    with service.db.session() as session:
        selection = digests.prepare_batch(session, job["target_id"], settings=service.settings, runtime=captured)
    assert selection["complete"] and saved["event_id"] in selection["event_ids"]
    state["runtime"] = local_runtime(generation="b", revision="5")
    changed = observation(service)
    with pytest.raises(DomainError, match="preparation will restart"):
        digests.deliver(service.db, service.environment_settings, job["target_id"], selection=selection,
                        analysis_settings=service.settings, runtime=changed)
    with service.db.session() as session:
        restarted = digests.prepare_batch(session, job["target_id"], selection, settings=service.settings, runtime=changed)
    assert restarted["restarts"] == 1 and restarted["event_ids"] == []
    assert sent == [] and len(model.calls) == 1


@pytest.mark.parametrize("change", [False, True])
def test_digest_worker_observes_again_before_delivery(local_relation, monkeypatch, change):
    _, service, model, _, state = local_relation
    job, _ = digest_job(local_relation)
    sent = record_mail(monkeypatch)
    before = state["probes"]
    if change:
        state["change_at_probe"] = before + 2
    result = asyncio.run(service.execute_job(job["id"]))
    assert state["probes"] == before + 2
    assert result["state"] == ("retrying" if change else "succeeded")
    assert len(sent) == (0 if change else 1) and len(model.calls) == 1


def test_offline_digest_does_not_consume_recipient_period(local_relation, monkeypatch):
    _, service, model, _, state = local_relation
    job, _ = digest_job(local_relation)
    sent = record_mail(monkeypatch)
    state["offline"] = True
    result = asyncio.run(service.execute_job(job["id"]))
    assert result["state"] == "retrying" and not sent
    with service.db.session() as session:
        assert session.scalar(select(DigestPreference.last_sent_at)) is None
    assert len(model.calls) == 1


def test_runtime_observation_cannot_cross_organization_or_configuration(local_relation):
    _, service, _, _, _ = local_relation
    run(local_relation)
    captured = observation(service)
    for other in (replace(captured, organization_id="another-tenant"), replace(captured, configuration="old-configuration"), None):
        assert current_fingerprint(service.settings, service.organization_id, other) is None
        with service.db.session() as session:
            reader = ImpactInboxReader(service.organization_id, None, settings=service.settings, prompts=service.prompt_settings, runtime=other)
            assert reader.page(session, ImpactInboxFilters())["items"][0]["items"][0]["current_analysis_id"] is None


@pytest.mark.parametrize("legacy", [None, "old-inventory-fingerprint", 42, {"fingerprint": "old"}])
def test_missing_or_legacy_runtime_binding_remains_history_only(local_relation, legacy):
    client, service, model, _, _ = local_relation
    saved = run(local_relation)["result"]["data"]
    with service.db.session() as session:
        record = session.get(RelationImpactAnalysis, saved["id"])
        record.analysis_plan = {**record.analysis_plan, "runtime_fingerprint": legacy}
        session.commit()
    assert history(local_relation)["current"] is None
    assert client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]["current_analysis_id"] is None
    assert len(model.calls) == 1


def test_unverified_queue_wakes_using_actual_model_without_reviving_completed_job(local_relation, monkeypatch):
    _, service, model, delivery, state = local_relation
    state["offline"] = True
    queued = asyncio.run(service.enqueue_relation_analysis(delivery))
    with service.db.session() as session:
        assert session.get(Job, queued["id"]).payload["runtime_fingerprint"] is None
    async def starting():
        return {"deployment": {"state": "starting"}, "models": []}
    original_inventory = service.model_manager.inventory
    monkeypatch.setattr(service.model_manager, "inventory", starting)
    waiting = asyncio.run(service.execute_job(queued["id"]))
    assert waiting["state"] == "waiting_for_model" and not model.calls
    monkeypatch.setattr(service.model_manager, "inventory", original_inventory)
    state["offline"] = False
    completed = asyncio.run(service.execute_job(queued["id"]))
    assert completed["state"] == "succeeded" and len(model.calls) == 1
    saved = completed["result"]["data"]
    assert saved["provenance"]["runtime_binding"]["deployment_id"] == "a" * 32
    assert saved["analysis_plan"]["runtime_fingerprint"] is not None
    state["offline"] = True
    assert asyncio.run(service.enqueue_relation_analysis(delivery))["id"] != queued["id"]


def test_fanout_shares_one_bounded_probe_per_organization(local_relation):
    _, service, model, delivery, state = local_relation
    before = state["probes"]
    result = asyncio.run(service.enqueue_pending_relation_analyses([(service.organization_id, delivery)] * 3))
    assert result["queued"] == 3 and result["failed"] == 0
    assert state["probes"] == before + 1 and not model.calls


def test_concurrent_offline_requests_coalesce_across_worker_guards(local_relation):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, RLock

    _, service, model, delivery, state = local_relation
    if service.db.engine.dialect.name != "postgresql":
        pytest.skip("Cross-worker row locking is verified against isolated PostgreSQL")
    state["offline"] = True
    barrier = Barrier(2)
    workers = [copy.copy(service), copy.copy(service)]
    for worker in workers:
        worker.write_guard = RLock()
    def enqueue(worker):
        barrier.wait(timeout=10)
        return asyncio.run(worker.enqueue_relation_analysis(delivery))["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        requests = list(pool.map(enqueue, workers))
    assert requests[0] == requests[1] and not model.calls
    with service.db.session() as session:
        assert len(list(session.scalars(select(Job).where(Job.target_id == delivery)))) == 1
