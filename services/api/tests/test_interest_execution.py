"""Real local gateway and DB with synthetic runtime/review/HTTP, not model quality."""

import asyncio
import inspect
import json

import httpx
import pytest
from pydantic import ValidationError
from runtime_fixtures import local_runtime
from sqlalchemy import event, select
from test_ai_capabilities import artifacts as artifacts_fixture
from test_analysis_runtime_binding import transport
from test_interest_admission import setup
from test_prompt_token_measurements import measurement

from helvetic_lens.analysis import ModelClient
from helvetic_lens.config import DomainError
from helvetic_lens.interest_assessment import BriefExecution
from helvetic_lens.interest_execution import LocalBriefRunner
from helvetic_lens.models import InterestEventAssessment, RegulatoryDocumentVersion

artifacts = artifacts_fixture


def draft(data):
    source = next(row["id"] for row in data["evidence"] if row["source_kind"] == "event")
    claim = {"text": "Synthetic source provides a review lead.", "evidence_ids": [source]}
    facts = data["profile_facts"]
    return {"what_happened": dict(claim),
            "why_in_radar": [{**claim, "interest_id": row["id"]} for row in data["interests"]],
            "importance": {**claim, "level": "low" if facts else "undetermined",
                           "profile_fact_ids": [facts[0]["id"]] if facts else []},
            "affected_area_ids": [], "next_step": {**claim, "kind": "no_action_now", "interest_id": None},
            "uncertainty": "Synthetic fixture, not a legal conclusion."}


@pytest.fixture
def execution(harness, artifacts, monkeypatch):
    service, event_id, version_id, _ = setup(harness, topics=2, units=3)
    root, identity, review, registry, write = artifacts
    runtime = {**local_runtime(), "prompt_budget_schema": "local-prompt-budget-v1"}
    identity.clear()
    identity.update(runtime["identity"])
    review["task"] = registry["profiles"][0]["grants"][0]["task"] = "interest_brief"
    settings = service.settings
    settings.apertus_provider = "docker"
    settings.apertus_base_url = "http://synthetic-manager/openai/v1"
    settings.apertus_model = runtime["served_model_id"]
    settings.apertus_explanation_profile = "synthetic-explanations"
    settings.ai_capability_registry = write()
    settings.ai_capability_evidence_root = root
    settings.apertus_max_tokens = 1600
    settings.apertus_context_chars = 100000
    client = ModelClient(settings, service.integration_logger)
    state = {"requests": [], "generated": [], "counts": [], "tokens": 400,
             "runtime": runtime, "hook": None, "invalid": 0, "disconnect": False,
             "measurement_override": {}, "bad_citation": False}

    async def handler(request):
        state["requests"].append(request)
        if request.method == "GET":
            if state["hook"]:
                response = state["hook"]("runtime")
                if inspect.isawaitable(response):
                    await response
            return httpx.Response(200, json=state["runtime"])
        wire = json.loads(request.content)
        count = request.url.path.endswith("/input_tokens")
        if state["hook"]:
            response = state["hook"]("count" if count else "generate")
            if inspect.isawaitable(response):
                await response
        tokens = state["tokens"]
        measured = measurement(wire, input_tokens=tokens, fits=tokens + wire["max_tokens"] + 128 <= 4096)
        measured.update(state["measurement_override"])
        headers = {"x-helvetic-runtime-binding": runtime["binding_fingerprint"],
                   "x-helvetic-token-budget": json.dumps(measured)}
        if count:
            state["counts"].append(wire)
            return httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": tokens}, headers=headers)
        state["generated"].append(wire)
        if state["disconnect"]:
            raise httpx.RemoteProtocolError("synthetic closed connection")
        # Repairs carry a different payload. Reuse the first complete dossier.
        data = json.loads(state["generated"][0]["messages"][-1]["content"])
        answer = draft(data)
        if state["bad_citation"] and len(state["generated"]) == 1:
            answer["what_happened"]["evidence_ids"] = ["not-supplied"]
        content = "invalid JSON" if len(state["generated"]) <= state["invalid"] else json.dumps(answer)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]}, headers=headers)

    transport(monkeypatch, handler)
    return service, LocalBriefRunner(service.db, service.organization_id, client), event_id, version_id, state, review, registry, write


def run(execution, **kwargs):
    return asyncio.run(execution[1].run(execution[2], **kwargs))


def records(execution):
    service = execution[0]
    with service.db.session() as session:
        return list(session.scalars(select(InterestEventAssessment)))


def test_measured_complete_request_persisted_and_exact_reuse(execution):
    result = run(execution)
    assert result["status"] == "succeeded", result
    assert result["result"]["coverage"]["explained_interests"] == 2
    state = execution[4]
    assert len(state["generated"]) == 1 and len(state["counts"]) == 2
    assert state["counts"][0] == state["counts"][1] == state["generated"][0]
    assert state["generated"][0]["max_tokens"] == 700
    proof = result["provenance"]["execution"]
    assert proof["admission_measurement"] == proof["generation_measurements"][0]
    assert result["provenance"]["provider_calls"] == 1
    posts = [r for r in state["requests"] if r.method == "POST"]
    assert all(r.headers["x-helvetic-priority"] == "background" for r in posts)
    before = len(state["requests"])
    again = run(execution)
    assert again["cached"] and again["id"] == result["id"]
    assert len(state["requests"]) == before + 1  # current runtime observation only
    assert len(state["generated"]) == 1 and len(records(execution)) == 1


@pytest.mark.parametrize("change", ["ask", "locale", "revoked", "identity", "unmeasured", "cloud"])
def test_no_implicit_scope_or_provider_fallback(execution, change):
    service, _, _, _, state, review, registry, write = execution
    if change == "ask":
        review["task"] = registry["profiles"][0]["grants"][0]["task"] = "ask"
    elif change == "revoked":
        registry["profiles"][0]["status"] = "revoked"
    elif change == "identity":
        state["runtime"]["identity"]["chat_template_sha256"] = "9" * 64
    elif change == "unmeasured":
        state["runtime"].pop("prompt_budget_schema")
    elif change == "cloud":
        service.settings.apertus_provider = "infomaniak"
    write()
    with pytest.raises(DomainError):
        run(execution, locale="fr" if change == "locale" else "en")
    assert not state["generated"] and not state["counts"] and not records(execution)
    if change == "cloud":
        assert not state["requests"]


@pytest.mark.parametrize("tokens", [3001, 4096])
def test_complete_input_over_budget_creates_no_job_or_generation(execution, tokens):
    execution[4]["tokens"] = tokens
    with pytest.raises(DomainError) as error:
        run(execution)
    assert error.value.code == "capability_budget_exceeded"
    assert not execution[4]["generated"] and not records(execution)


@pytest.mark.parametrize("invalid", [1, 2])
def test_single_repair_shared_budget_and_failure_is_not_retried_on_read(execution, invalid):
    execution[4]["invalid"] = invalid
    if invalid == 1:
        result = run(execution)
        assert result["status"] == "succeeded"
        assert result["provenance"]["provider_calls"] == 2
        assert len(result["provenance"]["execution"]["generation_measurements"]) == 2
    else:
        with pytest.raises(DomainError):
            run(execution)
        assert records(execution)[0].status == "failed"
        assert run(execution)["status"] == "failed"
    assert len(execution[4]["generated"]) == 2


@pytest.mark.parametrize("during", ["count", "generate"])
def test_changed_saved_input_cannot_publish(execution, during):
    service, _, _, version_id, state, *_ = execution

    def mutate(phase):
        if phase != during:
            return
        state["hook"] = None
        with service.db.session() as session:
            version = session.get(RegulatoryDocumentVersion, version_id)
            version.passages = [{**row, "text": row["text"] + " Corrected source."} for row in version.passages]
            session.commit()

    state["hook"] = mutate
    if during == "count":
        with pytest.raises(DomainError) as error:
            run(execution)
        assert error.value.code == "interest_inputs_changed"
        assert not records(execution) and not state["generated"]
    else:
        result = run(execution)
        assert result["status"] == "superseded" and result["result"] is None


def test_missing_event_denied_before_runtime_contact(execution):
    with pytest.raises(DomainError) as error:
        asyncio.run(execution[1].run("missing-event"))
    assert error.value.code == "not_found"
    assert not execution[4]["requests"]


def test_transport_retries_share_two_generation_limit(execution):
    execution[4]["disconnect"] = True
    with pytest.raises(DomainError):
        run(execution)
    assert len(execution[4]["generated"]) == 2
    assert records(execution)[0].status == "failed"


def test_revocation_during_count_prevents_generation(execution):
    state, registry, write = execution[4], execution[6], execution[7]

    def revoke(phase):
        if phase == "count":
            registry["profiles"][0]["status"] = "revoked"
            write()

    state["hook"] = revoke
    with pytest.raises(DomainError) as error:
        run(execution)
    assert error.value.code == "capability_changed"
    assert not state["generated"] and not records(execution)


@pytest.mark.parametrize("field,value", [("request_sha256", "0" * 64), ("deployment_id", "0" * 32),
                                        ("input_tokens", True), ("binding_fingerprint", "0" * 64)])
def test_invalid_runtime_measurement_cannot_admit_work(execution, field, value):
    execution[4]["measurement_override"] = {field: value}
    with pytest.raises(DomainError) as error:
        run(execution)
    assert error.value.code == "token_budget_invalid"
    assert not execution[4]["generated"] and not records(execution)


def test_invalid_citation_repaired_against_same_full_dossier(execution):
    execution[4]["bad_citation"] = True
    result = run(execution)
    assert result["status"] == "succeeded" and result["provenance"]["provider_calls"] == 2
    assert "not-supplied" not in json.dumps(result["result"])
    assert len(execution[4]["counts"]) == 3  # initial admission + each generation


@pytest.mark.parametrize("change", ["runtime", "revoked", "configuration"])
def test_changed_model_or_approval_after_generation_does_not_publish(execution, change):
    service, _, _, _, state, _, registry, write = execution

    def mutate(phase):
        if phase != "runtime" or not state["generated"]:
            return
        if change == "runtime":
            state["runtime"]["identity"]["artifact_sha256"] = "9" * 64
            state["runtime"]["artifact_sha256"] = "9" * 64
        elif change == "revoked":
            registry["profiles"][0]["status"] = "revoked"
            write()
        else:
            service.settings.apertus_temperature = 0.5

    state["hook"] = mutate
    if change == "configuration":
        result = run(execution)
        assert result["status"] == "superseded" and result["result"] is None
    else:
        with pytest.raises(DomainError) as error:
            run(execution)
        assert error.value.code == "interest_capability_unavailable"
        assert records(execution)[0].status == "failed"
        assert records(execution)[0].error_code == "interest_capability_unavailable"
    assert records(execution)[0].result is None


@pytest.mark.parametrize("failure", ["cancelled", "timeout"])
def test_interruption_closes_attempt_and_restores_context(execution, failure):
    state = execution[4]

    def stop(phase):
        if phase == "generate":
            raise asyncio.CancelledError() if failure == "cancelled" else TimeoutError()

    state["hook"] = stop
    with pytest.raises(asyncio.CancelledError if failure == "cancelled" else DomainError):
        run(execution)
    row = records(execution)[0]
    assert row.status == "failed" and row.result is None and row.attempt_key is None
    assert row.error_code == ("cancelled" if failure == "cancelled" else "model_timeout")
    assert execution[1].client.active_capability is None
    assert execution[1].client.headers()["X-Helvetic-Priority"] == "interactive"


def test_database_connections_not_held_during_provider_calls(execution):
    engine = execution[0].db.engine
    checked_out = set()

    def checkout(connection, record, proxy):
        checked_out.add(id(record))

    def checkin(connection, record):
        checked_out.discard(id(record))

    event.listen(engine, "checkout", checkout)
    event.listen(engine, "checkin", checkin)
    execution[4]["hook"] = lambda phase: pytest.fail("DB connection held across HTTP") if checked_out else None
    try:
        assert run(execution)["status"] == "succeeded"
    finally:
        event.remove(engine, "checkout", checkout)
        event.remove(engine, "checkin", checkin)


@pytest.mark.parametrize("change", ["extra", "launch", "missing", "overflow"])
def test_execution_proof_rejects_unbounded_or_inconsistent_metadata(execution, change):
    proof = run(execution)["provenance"]["execution"]
    if change == "extra":
        proof["raw_provider_response"] = "must never be persisted"
    elif change == "launch":
        proof["generation_measurements"][0]["deployment_id"] = "f" * 32
    elif change == "missing":
        proof["generation_measurements"] = []
    else:
        proof["generation_measurements"] *= 3
    with pytest.raises(ValidationError):
        BriefExecution.model_validate(proof)


def test_concurrent_call_reuses_running_attempt_and_contexts_do_not_leak(execution):
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()

        async def hook(phase):
            if phase == "generate":
                started.set()
                await release.wait()

        execution[4]["hook"] = hook
        first = asyncio.create_task(execution[1].run(execution[2]))
        try:
            await asyncio.wait_for(started.wait(), timeout=5)
            second = await execution[1].run(execution[2])
            assert second["status"] == "running" and second["result"] is None
            assert execution[1].client.active_capability is None
        finally:
            release.set()
        completed = await first
        assert completed["status"] == "succeeded" and completed["id"] == second["id"]

    asyncio.run(scenario())
    assert len(execution[4]["generated"]) == 1 and len(records(execution)) == 1


def test_identical_runtime_restart_reuses_immutable_result(execution):
    first = run(execution)
    execution[4]["runtime"].update(deployment_id="b" * 32, binding_fingerprint="b" * 64)
    second = run(execution)
    assert second["cached"] and first["id"] == second["id"]
    assert len(execution[4]["generated"]) == 1
    assert second["provenance"] == first["provenance"]  # evidence of original execution retained
