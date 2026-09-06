"""Real API execution with synthetic approvals and synthetic provider replies."""

import asyncio
import copy
import json

import httpx
import pytest
from conftest import add_law, import_old
from decision_fixtures import decision_draft
from runtime_fixtures import local_runtime
from test_ai_capabilities import artifacts as artifacts_fixture
from test_analysis_runtime_binding import transport
from test_prompt_token_measurements import measurement

from helvetic_lens.analysis import ModelClient

artifacts = artifacts_fixture


@pytest.fixture
def approved_app(harness, artifacts, monkeypatch):
    client, _, service, _ = harness
    root, identity, review, registry, write = artifacts
    observed = {**local_runtime(), "prompt_budget_schema": "local-prompt-budget-v1"}
    identity.clear()
    identity.update(observed["identity"])
    settings = service.settings
    settings.apertus_provider = "docker"
    settings.apertus_base_url = "http://synthetic-manager/openai/v1"
    settings.apertus_model = observed["served_model_id"]
    settings.apertus_explanation_profile = "synthetic-explanations"
    settings.ai_capability_registry = write()
    settings.ai_capability_evidence_root = root
    settings.apertus_max_tokens = 1600
    service.model_client = ModelClient(settings, service.integration_logger)
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post("/api/comparisons", json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]}).json()
    state = {"runtime": observed, "rich": True, "requests": [], "generated": [], "mutate": None, "tokens": 400, "wrong_first": False}

    async def handler(request):
        state["requests"].append(request)
        if request.method == "GET":
            if request.url.path == "/v1/inventory":
                return httpx.Response(200, json={"deployment": {"state": "ready"}})
            return httpx.Response(200, json=state["runtime"])
        wire = json.loads(request.content)
        data = json.loads(wire["messages"][-1]["content"])
        count = request.url.path.endswith("/input_tokens")
        if state["mutate"]:
            state["mutate"](data, count)
        tokens = state["tokens"](data) if callable(state["tokens"]) else state["tokens"]
        headers = {}
        measured = None
        if settings.apertus_provider == "docker":
            measured = measurement(wire, input_tokens=tokens, fits=tokens + wire["max_tokens"] + 128 <= 4096)
            headers = {"x-helvetic-runtime-binding": observed["binding_fingerprint"], "x-helvetic-token-budget": json.dumps(measured)}
        if count:
            return httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": tokens}, headers=headers)
        state["generated"].append(wire)
        rows = data.get("evidence", {}).get("rows", [])
        number = rows[0][0] if rows else 1
        if state["wrong_first"] and len(state["generated"]) == 1:
            number = 999
        if data["task"] == "impact_synthesis":
            result = decision_draft(data)
            if state.get("draft_transform"):
                result = state["draft_transform"](result, data)
        elif data["task"] == "impact_batch":
            result = {"impact": "low", "citation_rows": [number]}
            if state["rich"]:
                result.update(summary="Synthetic explanation of changed retention wording.", reason="The cited period changed.", business_areas=[])
        else:
            result = {"supported": True, "citation_rows": [number]}
            if state["rich"]:
                result["answer"] = "Synthetic explanation: compare the revised retention period with your current schedule."
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(result)}}]}, headers=headers)

    transport(monkeypatch, handler)
    return client, service, comparison, state, review, registry, write


def request_analysis(app, kind="ask", locale="en-CH"):
    client, _, comparison, _, review, registry, write = app
    task = "impact_report" if kind.startswith("analyse") else "ask"
    review["task"] = task
    registry["profiles"][0]["grants"][0]["task"] = task
    write()
    return client.post(
        f"/api/comparisons/{comparison['id']}/{kind}",
        json={"output_locale": locale, **({"question": "What changed in this document?"} if task == "ask" else {})},
    )


def history(app):
    return app[0].get(f"/api/comparisons/{app[2]['id']}/ai-history").json()["items"]


@pytest.mark.parametrize("kind", ["ask", "analyse"])
def test_approved_exact_scope_generates_explanation_with_verified_citations_and_budget(approved_app, kind):
    response = request_analysis(approved_app, kind)
    assert response.status_code == 200, response.text
    record = history(approved_app)[0]
    assert record["status"] == "succeeded", record
    assert record["result"]["response_mode"] == "generated_explanation"
    text = record["result"].get("answer") or record["result"].get("summary")
    assert "Synthetic explanation" in text
    assert record["result"]["citations"] and record["result"]["citations"][0]["quote"]
    decision = record["provenance"]["capability_decision"]
    assert decision["mode"] == "generated_explanation" and decision["reason"] == "reviewed_scope"
    assert record["analysis_plan"]["capability_decision"] == record["analysis_plan"]["actual"]["capability_decision"] == decision
    generated = approved_app[3]["generated"]
    assert len(generated) == (1 if kind == "ask" else 2)
    assert all(wire["max_tokens"] == 700 for wire in generated)
    assert record["analysis_plan"]["limits"]["reserved_output_tokens_per_call"] == 700
    assert record["analysis_plan"]["estimates"]["output_tokens"] == len(generated) * 700
    assert all(item["fits"] for item in record["provenance"]["reviewed_prompt_budgets"])
    assert record["coverage"]["token_allocation"]["batches"][0]["reviewed_budget"] == decision["budget"]
    before = len(approved_app[3]["requests"])
    reused = request_analysis(approved_app, kind)
    assert reused.json()["cached"] is True
    assert len(approved_app[3]["requests"]) == before + 1  # runtime lookup only


@pytest.mark.parametrize("failure,reason", [
    ("locale", "scope_not_reviewed"), ("revoked", "profile_not_approved"),
    ("identity", "runtime_identity_mismatch"), ("measurement", "measurement_unavailable"),
    ("custom", "runtime_identity_unavailable"), ("infomaniak", "runtime_identity_unavailable"),
])
def test_transport_or_unreviewed_scope_cannot_authorize_explanation(approved_app, failure, reason):
    _, service, _, state, _, registry, _ = approved_app
    state["rich"] = False
    locale = "de-CH" if failure == "locale" else "en-CH"
    if failure == "revoked":
        registry["profiles"][0]["status"] = "revoked"
    if failure == "identity":
        state["runtime"]["identity"]["chat_template_sha256"] = "9" * 64
    if failure == "measurement":
        state["runtime"].pop("prompt_budget_schema")
    if failure in {"custom", "infomaniak"}:
        service.settings.apertus_provider = failure
        service.settings.apertus_base_url = "http://synthetic-provider/v1"
    response = request_analysis(approved_app, locale=locale)
    assert response.status_code == 200, response.text
    record = history(approved_app)[0]
    assert record["result"]["response_mode"] == "selected_evidence"
    assert record["provenance"]["capability_decision"]["reason"] == reason
    assert not record["provenance"]["reviewed_prompt_budgets"]
    assert "Synthetic explanation" not in record["result"]["answer"]


@pytest.mark.parametrize("kind", ["ask", "analyse"])
@pytest.mark.parametrize("change", ["revoked", "profile", "invalid_review"])
def test_approval_changes_invalidate_reuse_but_preserve_history(approved_app, kind, change):
    client, service, comparison, state, _, registry, write = approved_app
    first = request_analysis(approved_app, kind)
    assert first.status_code == 200, first.text
    original = copy.deepcopy(history(approved_app)[0])
    if change == "revoked":
        registry["profiles"][0]["status"] = "revoked"
        write()
    elif change == "profile":
        service.settings.apertus_explanation_profile = ""
    else:
        (service.settings.ai_capability_evidence_root / "review.json").write_text("broken", encoding="utf-8")
    before = len(state["generated"])
    if kind == "analyse":
        shown = client.get(f"/api/comparisons/{comparison['id']}").json()["analysis"]
        assert shown["stale"] is True and shown["id"] == first.json()["id"]
        assert client.get("/api/impact-matrix").json()["rows"][0]["report_state"] == "stale"
    assert history(approved_app)[0] == original
    assert len(state["generated"]) == before  # reading never regenerates
    state["rich"] = False
    # Do not use request_analysis: it deliberately rewrites the fixture review.
    response = client.post(f"/api/comparisons/{comparison['id']}/{kind}", json={
        "output_locale": "en-CH", **({"question": "What changed in this document?"} if kind == "ask" else {}),
    })
    assert response.status_code == 200, response.text
    assert response.json()["cached"] is False
    records = history(approved_app)
    assert len(records) == 2
    assert next(item for item in records if item["id"] == original["id"]) == original
    assert records[0]["result"]["response_mode"] == "selected_evidence"
    if change == "invalid_review":
        assert records[0]["provenance"]["capability_decision"]["reason"] == "registry_invalid"


@pytest.mark.parametrize("phase", ["count", "generation", "synthesis"])
def test_revocation_during_execution_aborts_without_accepting_explanation(approved_app, phase):
    _, _, _, state, _, registry, write = approved_app
    def revoke(data, count):
        if (phase == "count" and count) or (phase == "generation" and not count) or (phase == "synthesis" and data["task"] == "impact_synthesis"):
            registry["profiles"][0]["status"] = "revoked"
            write()
            state["mutate"] = None
    state["mutate"] = revoke
    response = request_analysis(approved_app, "analyse" if phase == "synthesis" else "ask")
    record = history(approved_app)[0]
    assert record["status"] == "failed", (response.text, record)
    assert not record.get("result")
    assert record["provenance"]["capability_error"] == "capability_changed"
    assert "approval changed" in record["error"]
    assert len(state["generated"]) == (0 if phase == "count" else 1)


@pytest.mark.parametrize("budget_failure", ["input", "combined", "synthesis"])
def test_reviewed_limits_reject_native_fitting_request_before_decoding(approved_app, budget_failure):
    _, _, _, state, review, _, _ = approved_app
    if budget_failure == "input":
        review["budget"]["input_tokens"] = 300
    elif budget_failure == "combined":
        # Each individual limit fits. Larger reviewed safety reserve is binding.
        review["budget"]["context_window_tokens"] = 8192
        review["budget"]["safety_tokens"] = 1600
        state["tokens"] = 2500  # native 4096 fits with 128 safety, not reviewed 1600
    else:
        state["tokens"] = lambda data: 3100 if data["task"] == "impact_synthesis" else 400
    response = request_analysis(approved_app, "analyse" if budget_failure == "synthesis" else "ask")
    record = history(approved_app)[0]
    assert record["status"] == "failed", (response.text, record)
    assert "reviewed task budget" in record["error"]
    assert len(state["generated"]) == (1 if budget_failure == "synthesis" else 0)
    assert all(item["fits"] for item in record["provenance"]["prompt_token_measurements"])
    assert state["requests"] and len(state["requests"]) <= 12


def test_reviewed_answer_repairs_invalid_citation_once_with_same_evidence(approved_app):
    approved_app[3]["wrong_first"] = True
    response = request_analysis(approved_app)
    assert response.status_code == 200, response.text
    record = history(approved_app)[0]
    assert record["status"] == "succeeded"
    generated = approved_app[3]["generated"]
    assert len(generated) == 2
    assert all(item["max_tokens"] == 700 for item in generated)
    payloads = [json.loads(item["messages"][-1]["content"]) for item in generated]
    assert payloads[0]["evidence"] == payloads[1]["evidence"]
    assert record["result"]["citations"]


@pytest.mark.parametrize("kind", ["ask-jobs", "analyse-jobs"])
def test_queued_approval_is_rechecked_and_old_job_key_is_not_reused(approved_app, kind):
    client, service, _, state, _, registry, write = approved_app
    service.settings.job_execution_mode = "celery"
    queued = request_analysis(approved_app, kind).json()
    assert queued["state"] == "queued", queued
    registry["profiles"][0]["status"] = "revoked"
    write()
    state["rich"] = False
    finished = asyncio.run(service.execute_job(queued["id"]))
    assert finished["state"] == "succeeded", finished
    assert history(approved_app)[0]["result"]["response_mode"] == "selected_evidence"
    saved_result = copy.deepcopy(finished["result"])
    registry["profiles"][0]["status"] = "approved"
    write()
    replacement = request_analysis(approved_app, kind).json()
    assert replacement["state"] == "queued" and replacement["id"] != queued["id"]
    assert client.get(f"/api/jobs/{queued['id']}").json()["result"] == saved_result
    assert len(state["generated"]) == 1


def test_settings_expose_only_verified_profile_metadata_and_persist_selection(approved_app):
    from test_settings import configuration
    client, service, _, state, _, _, _ = approved_app
    # Match server defaults too: saving a form resolves a new Settings instance.
    service.environment_settings.ai_capability_registry = service.settings.ai_capability_registry
    service.environment_settings.ai_capability_evidence_root = service.settings.ai_capability_evidence_root
    response = client.get("/api/settings/apertus")
    assert response.status_code == 200
    data = response.json()
    assert data["explanation_profiles"][0]["scopes"] == [{"task": "ask", "locale": "en-CH"}]
    assert "review.json" not in response.text and "Synthetic test reviewer" not in response.text
    saved = client.patch("/api/settings/apertus", json=configuration(explanation_profile="synthetic-explanations"))
    assert saved.status_code == 200, saved.text
    assert client.get("/api/settings/apertus").json()["explanation_profile"] == "synthetic-explanations"
    assert service.settings.apertus_explanation_profile == "synthetic-explanations"
    forbidden = client.patch("/api/settings/apertus", json=configuration(ai_capability_registry="/tmp/fake"))
    assert forbidden.status_code == 422
    assert not state["generated"]


def test_task_scope_is_exact_and_cancellation_restores_parent_decision(approved_app):
    _, service, _, _, _, _, _ = approved_app
    model = service.model_client
    async def run():
        with model.runtime_scope():
            await model.bound_runtime()
            with model.capability_scope("ask", "en-CH"):
                parent = model.active_capability
                async def child(task, locale, cancel=False):
                    with model.capability_scope(task, locale):
                        await asyncio.sleep(0)
                        assert model.active_capability.task == task
                        assert model.active_capability.locale == locale
                        if cancel:
                            raise asyncio.CancelledError()
                        return model.active_capability.reason
                results = await asyncio.gather(
                    child("impact_report", "en-CH"), child("ask", "de-CH"),
                    child("ask", "en-CH"), child("ask", "fr-CH", True), return_exceptions=True,
                )
                assert results[:3] == ["scope_not_reviewed", "scope_not_reviewed", "reviewed_scope"]
                assert isinstance(results[3], asyncio.CancelledError)
                assert model.active_capability == parent
            assert model.active_capability is None
    asyncio.run(run())


def test_current_report_reuse_is_cited_no_call_reuse_not_new_ask_approval(approved_app):
    client, _, comparison, state, _, _, _ = approved_app
    assert request_analysis(approved_app, "analyse").status_code == 200
    before = len(state["generated"])
    report = history(approved_app)[0]
    response = client.post(f"/api/comparisons/{comparison['id']}/ask", json={
        "question": "What changed in this document?", "output_locale": "en-CH",
    })
    assert response.status_code == 200, response.text
    answer = history(approved_app)[0]
    assert answer["result"]["reused_impact_report_id"] == report["id"]
    assert answer["result"]["response_mode"] == report["result"]["response_mode"]
    assert answer["provenance"]["capability_decision"]["reason"] == "scope_not_reviewed"
    assert answer["result"]["citations"]
    assert len(state["generated"]) == before
