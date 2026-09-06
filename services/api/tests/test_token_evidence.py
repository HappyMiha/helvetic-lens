import asyncio
import copy
import json
import time

import httpx
import pytest
from conftest import LAW_URL, add_law, import_old
from runtime_fixtures import local_runtime
from test_analysis_runtime_binding import settings, transport
from test_prompt_token_measurements import measurement

from helvetic_lens.analysis import (
    AnswerDigest,
    ImpactDigest,
    InferenceBudget,
    ModelClient,
    structured_completion,
)
from helvetic_lens.config import DomainError
from helvetic_lens.models import Comparison
from helvetic_lens.token_evidence import MAX_COUNT_PROBES, allocated_coverage


def dossier(groups=8, *, text=None):
    evidence = []
    items = []
    for index in range(groups):
        kind = "modified" if index >= groups // 2 else "added"
        # Synthetic two-sided units deliberately include IDs beyond a retained
        # prefix, so a wrong but in-range citation must not pass validation.
        for side in ("old", "new"):
            evidence.append({
                "version_id": side, "passage_id": f"p{index}", "position": index, "page": 1,
                "change_id": f"c{index}", "change_kind": kind, "side": side,
                "text": text[side] if text else f"Synthetic {side} text for unit {index}.",
            })
        items.append([f"c{index}", kind, index, index])
    columns = ["row_number", "change_id", "change_kind", "side", "position", "passage_id", "page", "text"]
    payload = {
        "task": "answer_batch", "company": {},
        "coverage": {"complete": True, "limited": False, "included_passages": len(evidence), "scope": "Synthetic complete dossier"},
        "deterministic_diff": {"complete": True, "change_items": items, "batch_counts": {"modified": groups // 2, "added": groups // 2}},
        "evidence": {"columns": columns, "version_ids": {"old": "old", "new": "new"}, "rows": [
            [number, *[item[key] for key in columns[1:]]] for number, item in enumerate(evidence, 1)
        ]},
    }
    return evidence, payload


def counted_transport(monkeypatch, counter, *, wrong_first=False, wrong_always=False, advertised=True, unmeasured_generation=False):
    calls = []
    generations = []

    async def handler(request):
        if request.method == "GET":
            state = local_runtime()
            if advertised:
                state["prompt_budget_schema"] = "local-prompt-budget-v1"
            return httpx.Response(200, json=state)
        wire = json.loads(request.content)
        data = json.loads(wire["messages"][-1]["content"])
        tokens = counter(wire, data)
        measured = measurement(wire, input_tokens=tokens, fits=tokens + wire["max_tokens"] + 128 <= 4096)
        headers = {"x-helvetic-runtime-binding": "a" * 64, "x-helvetic-token-budget": json.dumps(measured)}
        is_count = request.url.path.endswith("/input_tokens")
        calls.append({"count": is_count, "wire": wire, "data": data, "measurement": measured})
        if is_count:
            return httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": tokens, "token_budget": measured}, headers=headers)
        assert measured["fits"], "An oversized request reached generation"
        generations.append(data)
        allowed = wire["response_format"]["schema"]["properties"]["citation_rows"]["items"].get("enum", [1])
        selected = 1 if wrong_always or (wrong_first and len(generations) == 1) else allowed[0]
        content = {"citation_rows": [selected]}
        content["impact" if data.get("task") == "impact_batch" else "supported"] = "low" if data.get("task") == "impact_batch" else True
        if unmeasured_generation:
            headers.pop("x-helvetic-token-budget")
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}}]}, headers=headers)

    transport(monkeypatch, handler)
    return calls, generations


async def execute(evidence, payload, *, schema=AnswerDigest):
    model = ModelClient(settings(apertus_max_tokens=700))
    trace_token = model.begin_trace()
    budget = InferenceBudget(3)
    allocation = {}
    try:
        result = await structured_completion(
            model, "Synthetic system instructions with exact citation rules.", payload, schema, evidence,
            validate_citations=False, numeric_reference_count=len(evidence), numeric_reference_evidence=evidence,
            budget=budget, allocation=allocation,
        )
        return result, allocation, budget
    finally:
        model.end_trace(trace_token)


@pytest.mark.asyncio
@pytest.mark.parametrize("schema", [AnswerDigest, ImpactDigest])
async def test_measured_selection_keeps_whole_change_pairs_and_original_citation_numbers(monkeypatch, schema):
    evidence, payload = dossier()
    payload["task"] = "impact_batch" if schema is ImpactDigest else "answer_batch"
    saved = copy.deepcopy(evidence)
    calls, generations = counted_transport(monkeypatch, lambda _wire, data: 350 + len(data["evidence"]["rows"]) * 600)
    result, allocation, budget = await execute(evidence, payload, schema=schema)
    assert allocation["row_numbers"] == [9, 10, 11, 12]
    assert result["citation_rows"] == [9]
    assert allocation["limited"] and allocation["count_probes"] == 3
    assert len(generations) == budget.used == 1
    assert calls[-2]["wire"] == calls[-1]["wire"]
    sent = generations[0]
    assert sent["deterministic_diff"]["complete"] is False
    assert [item[0] for item in sent["deterministic_diff"]["change_items"]] == ["c4", "c5"]
    assert sent["deterministic_diff"]["batch_counts"]["modified"] == 2
    assert evidence == saved and len(payload["evidence"]["rows"]) == 16
    selected, coverage = allocated_coverage(evidence, payload["coverage"], [{"evidence": evidence, "token_allocation": allocation}])
    assert {(item["change_id"], item["side"]) for item in selected} == {(unit, side) for unit in ("c4", "c5") for side in ("old", "new")}
    assert coverage["included_passages"] == coverage["processed_passages"] == 4
    assert coverage["complete"] is False and "partial" in coverage["scope"]


@pytest.mark.asyncio
@pytest.mark.parametrize("wrong_always", [False, True])
async def test_omitted_but_in_range_row_requires_repair_and_cannot_be_accepted(monkeypatch, wrong_always):
    evidence, payload = dossier()
    calls, generations = counted_transport(monkeypatch, lambda _wire, data: 350 + len(data["evidence"]["rows"]) * 600, wrong_first=True, wrong_always=wrong_always)
    if wrong_always:
        with pytest.raises(DomainError) as error:
            await execute(evidence, payload)
        assert error.value.code == "invalid_citation"
    else:
        result, _, budget = await execute(evidence, payload)
        assert result["citation_rows"] == [9] and budget.used == 2
    assert len(generations) == 2
    assert generations[1]["repair"]["valid_row_numbers"] == [9, 10, 11, 12]
    assert generations[0]["evidence"] == generations[1]["evidence"]
    assert len([call for call in calls if call["count"]]) == 3


@pytest.mark.asyncio
async def test_long_pair_uses_exact_windows_around_changed_wording_without_editing_sources(monkeypatch):
    texts = {side: "Identical prefix. " * 100 + ending for side, ending in [("old", "Keep for five days."), ("new", "Keep for ten days.")]}
    evidence, payload = dossier(1, text=texts)
    calls, generations = counted_transport(monkeypatch, lambda _wire, data: 5000 if max(len(row[-1]) for row in data["evidence"]["rows"]) > 250 else 500)
    _, allocation, budget = await execute(evidence, payload)
    assert allocation["row_numbers"] == [1, 2] and not allocation["omitted_row_numbers"]
    assert allocation["limited"] and budget.used == 1
    assert len(generations[0]["evidence"]["rows"]) == 2
    for row, span, original in zip(generations[0]["evidence"]["rows"], allocation["windows"], evidence, strict=True):
        assert span["start"] > 0
        assert row[-1] == original["_model_text"] == texts[original["side"]][span["start"]:span["start"] + span["characters"]]
        assert original["text"] == texts[original["side"]]
        assert "five days" in row[-1] or "ten days" in row[-1]
    assert len(calls) <= MAX_COUNT_PROBES + 1


@pytest.mark.asyncio
async def test_fixed_prompt_overhead_fails_boundedly_without_generation(monkeypatch):
    evidence, payload = dossier(1, text={"old": "a" * 1000, "new": "b" * 1000})
    saved = copy.deepcopy(evidence)
    calls, generations = counted_transport(monkeypatch, lambda _wire, _data: 5000)
    with pytest.raises(DomainError) as error:
        await execute(evidence, payload)
    assert error.value.code == "model_context_exceeded"
    assert "complete saved comparison remains available" in error.value.message
    assert not generations and 1 <= len(calls) <= MAX_COUNT_PROBES
    assert evidence == saved


@pytest.mark.asyncio
@pytest.mark.parametrize("advertised", [True, False])
async def test_full_fitting_evidence_and_legacy_gateway_do_not_lose_rows(monkeypatch, advertised):
    evidence, payload = dossier()
    calls, generations = counted_transport(monkeypatch, lambda _wire, _data: 100, advertised=advertised)
    _, allocation, budget = await execute(evidence, payload)
    assert len(generations) == budget.used == 1
    assert generations[0]["evidence"] == payload["evidence"]
    if advertised:
        assert not allocation["limited"] and allocation["count_probes"] == 1
    else:
        assert not allocation and not any(call["count"] for call in calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,expected", [
    ("wrong_hash", "token_budget_invalid"), ("missing_header", "token_budget_invalid"),
    ("wrong_body", "token_budget_invalid"), ("restart", "runtime_binding_changed"),
    ("transport", "token_budget_unavailable"), ("deadline", "token_budget_unavailable"),
])
async def test_count_failure_never_falls_back_to_generation_or_retries(monkeypatch, failure, expected):
    count_calls = []

    async def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={**local_runtime(), "prompt_budget_schema": "local-prompt-budget-v1"})
        assert request.url.path.endswith("/input_tokens")
        count_calls.append(request)
        if failure == "transport":
            raise httpx.ReadError("synthetic interruption")
        if failure == "deadline":
            await asyncio.Event().wait()
        if failure == "restart":
            return httpx.Response(409)
        wire = json.loads(request.content)
        measured = measurement(wire, **({"request_sha256": "0" * 64} if failure == "wrong_hash" else {}))
        headers = {"x-helvetic-runtime-binding": "a" * 64}
        if failure != "missing_header":
            headers["x-helvetic-token-budget"] = json.dumps(measured)
        return httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": 999 if failure == "wrong_body" else 123}, headers=headers)

    transport(monkeypatch, handler)
    model = ModelClient(settings(apertus_max_tokens=700))
    token = model.begin_trace()
    budget = InferenceBudget(3)
    if failure == "deadline":
        # Bind first so the timeout is specifically the count-only request.
        await model.bound_runtime(budget)
        budget.deadline = time.monotonic() + 0.05
    evidence, payload = dossier()
    allocation = {}
    with pytest.raises(DomainError) as error:
        await structured_completion(model, "synthetic system", payload, AnswerDigest, evidence, budget=budget, allocation=allocation)
    trace = model.end_trace(token)
    assert error.value.code == expected
    assert len(count_calls) == 1 and budget.used == 0
    assert allocation["status"] == "failed"
    assert trace[-1]["evidence_allocation"] == allocation


@pytest.mark.asyncio
async def test_cancelled_count_is_not_converted_to_retry_or_generation(monkeypatch):
    entered = asyncio.Event()

    async def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={**local_runtime(), "prompt_budget_schema": "local-prompt-budget-v1"})
        assert request.url.path.endswith("/input_tokens")
        entered.set()
        await asyncio.Event().wait()

    transport(monkeypatch, handler)
    evidence, payload = dossier()
    task = asyncio.create_task(execute(evidence, payload))
    await asyncio.wait_for(entered.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_advertised_gateway_cannot_drop_measurement_after_allocation(monkeypatch):
    evidence, payload = dossier()
    calls, generations = counted_transport(monkeypatch, lambda _wire, _data: 100, unmeasured_generation=True)
    with pytest.raises(DomainError) as error:
        await execute(evidence, payload)
    assert error.value.code == "token_budget_invalid"
    assert len(generations) == 1 and len(calls) == 2


@pytest.mark.parametrize("kind,question", [("analyse", None), ("ask", "What changed in this document?"), ("ask", "Summarize the whole document")])
def test_real_http_analysis_persists_executed_coverage_and_reuses_it_without_new_generation(harness, monkeypatch, kind, question):
    client, fetcher, service, _ = harness

    def document(days):
        return ("<html><main><h1>Synthetic rules</h1>" + "".join(
            f"<h2>Art. {index + 1}</h2><p>Synthetic records for category {index} must be retained for {days} days.</p>"
            for index in range(8)
        ) + "</main></html>").encode()

    fetcher.values[LAW_URL] = document(30)
    law = add_law(client)
    previous = import_old(client, law["id"], body=document(10))["version"]
    compared = client.post("/api/comparisons", json={"old_version_id": previous["id"], "new_version_id": law["current_version_id"]}).json()
    with service.db.session() as session:
        original_diff = copy.deepcopy(session.get(Comparison, compared["id"]).diff)
    service.settings.apertus_provider = "docker"
    service.settings.apertus_base_url = "http://synthetic-manager/openai/v1"
    service.settings.apertus_model = "test-apertus"
    service.settings.apertus_max_tokens = 700
    service.settings.apertus_context_chars = 40000
    service.model_client = ModelClient(service.settings, service.integration_logger)
    calls, generations = counted_transport(monkeypatch, lambda _wire, data: 350 + len(data["evidence"]["rows"]) * 600)
    route = f"/api/comparisons/{compared['id']}"
    response = client.post(route + "/" + kind, json={"question": question} if question else {})
    assert response.status_code == 200, response.text
    record = client.get(route + "/ai-history").json()["items"][0]
    assert record["status"] == "succeeded", record
    allocation = record["analysis_plan"]["actual"]["evidence_allocation"]
    assert allocation and allocation["batches"][0]["limited"]
    assert record["provenance"]["evidence_allocations"] == allocation["batches"]
    coverage = record["coverage"]
    sent_rows = [row for data in generations for row in data["evidence"]["rows"]]
    assert coverage["processed_passages"] == coverage["included_passages"] == len(sent_rows)
    assert coverage["included_characters"] == sum(len(row[-1]) for row in sent_rows)
    assert coverage["limited"] and not coverage["complete"]
    assert record["analysis_plan"]["actual"]["selected_evidence_ids"] == coverage["selected_evidence_ids"]
    assert len(generations) <= (3 if kind == "analyse" else 1)
    before = len(generations)
    repeated = client.post(route + "/" + kind, json={"question": question} if question else {})
    assert repeated.status_code == 200 and len(generations) == before
    with service.db.session() as session:
        assert session.get(Comparison, compared["id"]).diff == original_diff
