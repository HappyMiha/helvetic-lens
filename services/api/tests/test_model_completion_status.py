"""Explicitly unfinished provider text cannot become a draft or format-repair input."""
import json
from types import SimpleNamespace

import httpx
import pytest
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_investigations import complete, pipeline, start, tick
from test_settings import transport

from helvetic_lens import research_gateway
from helvetic_lens.analysis import InferenceBudget, ModelClient
from helvetic_lens.config import OPENAI_BASE_URL, SWISSCOM_WEEKS_BASE_URL, DomainError, Settings
from helvetic_lens.product_investigation_models import InvestigationBranch
from helvetic_lens.product_investigations import Extraction
from helvetic_lens.product_iterative_research import ResearchPlan


def settings(tmp_path, provider="custom"):
    base = {"openai": OPENAI_BASE_URL, "swisscom": SWISSCOM_WEEKS_BASE_URL}.get(provider, "https://inference.example/v1")
    return Settings(_env_file=None, data_dir=tmp_path, apertus_provider=provider,
        apertus_base_url=base, apertus_model="synthetic-model",
        apertus_api_key="test-only-key", apertus_request_retries=2)


@pytest.mark.asyncio
@pytest.mark.parametrize("choice", [
    {"finish_reason": reason, "message": {"content": '{"syntactically":"complete"}'}}
    for reason in ("length", "content_filter", "tool_calls", "function_call", None)
] + [
    {"finish_reason": "stop", "message": {"content": "partial private text", "refusal": "private refusal"}},
    {"finish_reason": "stop", "message": {"content": [
        {"type": "text", "text": "partial private text"}, {"type": "refusal", "refusal": "private refusal"}]}},
    {"message": {"content": "partial private text", "tool_calls": [{"id": "synthetic-call"}]}},
])
async def test_explicit_nonterminal_or_refused_output_is_never_success_or_blind_retry(tmp_path, monkeypatch, choice):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"choices": [choice]})

    transport(monkeypatch, respond)
    client, budget = ModelClient(settings(tmp_path)), InferenceBudget(3)
    token = client.begin_trace()
    with pytest.raises(DomainError) as error:
        await client.complete("Use the supplied evidence.", "Private source text.", budget=budget)
    events = client.end_trace(token)
    assert error.value.code == "model_incomplete" and error.value.status == 502
    assert "private" not in error.value.message.lower()
    assert len(calls) == budget.used == 1
    assert [event["outcome"] for event in events if "outcome" in event] == ["error"]
    assert events[-1]["error_code"] == "model_incomplete"


@pytest.mark.asyncio
@pytest.mark.parametrize("choice,expected", [
    ({"finish_reason": "stop", "message": {"content": '{"status":"ok"}', "refusal": None}}, '{"status":"ok"}'),
    ({"message": {"content": "Legacy complete text."}}, "Legacy complete text."),
    ({"finish_reason": "stop", "message": {"content": [{"type": "text", "text": "Complete text block."}]}}, "Complete text block."),
])
async def test_complete_and_legacy_envelopes_keep_existing_content_contract(tmp_path, monkeypatch, choice, expected):
    transport(monkeypatch, lambda request: httpx.Response(200, json={"choices": [choice]}))
    assert await ModelClient(settings(tmp_path)).complete("system", "input") == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["custom", "openai", "swisscom"])
async def test_interrupted_operational_plan_does_not_enter_same_schema_format_repair(tmp_path, monkeypatch, provider):
    calls = []

    def respond(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"finish_reason": "length", "message": {
            "content": '{"objective":"PRIVATE INTERRUPTED PLAN", "branches":['}}]})

    transport(monkeypatch, respond)
    configured = settings(tmp_path, provider)
    service = SimpleNamespace(settings=configured, model_client=ModelClient(configured))
    work = {"phase": "plan", "unmetered_research": True,
        "input": {"question": "Find the relevant source records.", "sources": []}}
    with pytest.raises(DomainError) as error:
        await research_gateway.complete(service, work, "Return an operational plan.", ResearchPlan, 30)
    assert error.value.code == "model_incomplete"
    assert len(calls) == work["model_route"]["model_requests"] == 1
    assert not work["model_route"].get("format_repair")
    assert "PRIVATE INTERRUPTED PLAN" not in json.dumps(work)


def test_interrupted_analysis_keeps_captured_reading_and_explicit_native_retry(signed, monkeypatch, tmp_path):
    client, service, _, scripted = signed
    pipeline(monkeypatch, service, scripted)
    root, run, _ = start(client)
    configured = settings(tmp_path)
    remote = SimpleNamespace(settings=configured, model_client=ModelClient(configured))
    calls, dispatched = [], []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"choices": [{"finish_reason": "length", "message": {
            "content": '{"claims":[{"statement":"PRIVATE INTERRUPTED CLAIM"'}}]})

    transport(monkeypatch, respond)
    original = research_gateway.execute

    async def interrupted(service, work, seconds):
        if work["phase"] == "extract" and not dispatched:
            dispatched.append((work["branch_id"], work["source_id"]))
            return await research_gateway.complete(remote, work, "Extract source claims.", Extraction, seconds)
        return await original(service, work, seconds)

    monkeypatch.setattr(research_gateway, "execute", interrupted)
    failed = complete(client, service, root, run)
    assert failed["status"] == "failed" and failed["retry"]["available"]
    assert not failed["claims"] and len(failed["sources"]) == len(calls) == 1
    assert "PRIVATE INTERRUPTED CLAIM" not in json.dumps(failed)
    captured = failed["sources"][0]
    with service.db.session() as session:
        state = session.get(InvestigationBranch, dispatched[0][0]).checkpoint
        assert state["source_ids"] == [dispatched[0][1]]
        assert state.get("failed_extract_indices") and not state.get("provider_retries")
        assert not state["steps"][-1]["execution"].get("format_repair")
    tick(service, run["id"])
    assert len(calls) == 1, "Job redelivery must not retry the same exhausted output allowance"
    retry = post(client, root + "/" + run["id"] + "/control",
        {"action": "retry", "expected_revision": failed["revision"]})
    assert retry.status_code == 200, retry.text
    tick(service, run["id"])
    resumed = client.get(root + "/" + run["id"]).json()
    assert resumed["claims"] and resumed["sources"][0] == captured
    with service.db.session() as session:
        state = session.get(InvestigationBranch, dispatched[0][0]).checkpoint
        assert state["source_ids"] == [dispatched[0][1]]
        assert sum(step["phase"] == "read" for step in state["steps"]) == 1
