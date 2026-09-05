from conftest import add_law, import_old
from fastapi.testclient import TestClient
from sqlalchemy import select

from helvetic_lens.main import create_app
from helvetic_lens.models import Analysis


def saved_comparison(client, law):
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons",
        json={
            "old_version_id": old["id"],
            "new_version_id": law["current_version_id"],
        },
    )
    assert comparison.status_code == 201, comparison.text
    return old, comparison.json()


def editable_prompts(settings):
    keys = {
        "impact_instructions",
        "impact_synthesis_instructions",
        "ask_instructions",
        "answer_synthesis_instructions",
        "repair_instructions",
        "ask_context_mode",
    }
    return {key: settings[key] for key in keys}


def test_saved_questions_and_impact_are_reused_and_attached_to_exact_comparison(harness):
    client, _, service, model = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    old, comparison = saved_comparison(client, law)
    ask_url = f"/api/comparisons/{comparison['id']}/ask"

    first = client.post(ask_url, json={"question": "What changed?", "history": []})
    assert first.status_code == 200 and first.json()["cached"] is False
    calls_after_first = len(model.calls)
    repeated = client.post(ask_url, json={"question": "What changed?", "history": []})
    assert repeated.status_code == 200 and repeated.json()["cached"] is True
    assert repeated.json()["record_id"] == first.json()["record_id"]
    assert repeated.json()["use_count"] == 2 and len(model.calls) == calls_after_first
    assert first.json()["analysis_plan"]["state"] == "completed"
    assert first.json()["analysis_plan"]["limits"]["provider_call_budget"] == 3
    assert first.json()["analysis_plan"]["actual"]["provider_calls"] <= 3

    impact_url = f"/api/comparisons/{comparison['id']}/analyse"
    impact = client.post(impact_url)
    assert impact.status_code == 200 and impact.json()["cached"] is False
    calls_after_impact = len(model.calls)
    repeated_impact = client.post(impact_url)
    assert repeated_impact.status_code == 200 and repeated_impact.json()["cached"] is True
    assert repeated_impact.json()["use_count"] == 2 and len(model.calls) == calls_after_impact
    assert impact.json()["analysis_plan"]["state"] == "completed"
    assert impact.json()["analysis_plan"]["limits"]["provider_call_budget"] == 5
    assert impact.json()["analysis_plan"]["actual"]["provider_calls"] <= 5

    history = client.get(f"/api/comparisons/{comparison['id']}/ai-history")
    assert history.status_code == 200 and history.json()["total"] == 2
    question = next(item for item in history.json()["items"] if item["type"] == "question")
    analysis = next(item for item in history.json()["items"] if item["type"] == "impact")
    assert question["question"] == "What changed?" and question["status"] == "succeeded"
    assert question["result"]["answer"] == "Test-only answer." and question["use_count"] == 2
    assert question["context_mode"] == "deterministic_diff"
    assert question["analysis_plan"]["actual"]["result_url"] == f"/compare/{comparison['id']}"
    assert analysis["analysis_plan"]["context_fingerprint"]
    assert analysis["result"]["summary"] == "Test-only summary." and analysis["use_count"] == 2
    assert question["comparison"] == analysis["comparison"]
    assert question["comparison"]["before"]["id"] == old["id"]
    assert question["comparison"]["after"]["id"] == law["current_version_id"]
    assert question["comparison"]["before"]["artifact_url"].endswith("/artifact")
    assert question["comparison"]["after"]["artifact_url"].endswith("/artifact")

    document_history = client.get(f"/api/laws/{law['id']}/ai-history")
    assert document_history.status_code == 200 and document_history.json()["total"] == 2


def test_impact_plan_is_committed_before_the_first_model_call(harness):
    client, _, service, model = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    _, comparison = saved_comparison(client, law)
    original_complete = model.complete
    observed = []

    async def inspect_plan(system, user, **kwargs):
        with service.db.session() as session:
            record = session.scalar(
                select(Analysis)
                .where(Analysis.comparison_id == comparison["id"])
                .order_by(Analysis.created_at.desc())
                .limit(1)
            )
            assert record is not None
            observed.append(record.analysis_plan)
            assert record.status == "pending"
            assert record.analysis_plan["state"] == "planned"
            assert record.analysis_plan["limits"]["provider_call_budget"] == 5
        return await original_complete(system, user, **kwargs)

    model.complete = inspect_plan
    response = client.post(f"/api/comparisons/{comparison['id']}/analyse")

    assert response.status_code == 200 and response.json()["status"] == "succeeded"
    assert observed and observed[0]["selected_change_ids"]


def test_general_questions_use_all_saved_passages_and_failed_attempts_remain_visible(harness):
    client, _, service, model = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    old, comparison = saved_comparison(client, law)
    route = f"/api/comparisons/{comparison['id']}/ask"

    answer = client.post(route, json={"question": "What did the older version say?"})
    assert answer.status_code == 200
    assert answer.json()["context_mode"] == "full_saved_versions"
    assert answer.json()["coverage"]["included_passages"] == 6
    assert answer.json()["coverage"]["available_passages"] == 6
    assert answer.json()["coverage"]["complete"] is True
    assert {citation["version_id"] for citation in answer.json()["citations"]}.issubset(
        {old["id"], law["current_version_id"]}
    )

    model.fail = True
    failed = client.post(route, json={"question": "Who approved this document?"})
    assert failed.status_code == 504
    history = client.get(f"/api/comparisons/{comparison['id']}/ai-history").json()
    failed_record = next(item for item in history["items"] if item.get("question") == "Who approved this document?")
    assert failed_record["status"] == "failed" and failed_record["result"] is None
    assert failed_record["error"] == "Test model timed out."


def test_failed_impact_rerun_keeps_last_valid_report_current(harness):
    client, _, service, model = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    _, comparison = saved_comparison(client, law)
    route = f"/api/comparisons/{comparison['id']}/analyse"
    first = client.post(route).json()
    assert first["status"] == "succeeded"

    current = client.get("/api/settings/prompts").json()
    changed = editable_prompts(current)
    changed["impact_instructions"] += " Use a fresh report revision."
    assert client.patch("/api/settings/prompts", json=changed).status_code == 200
    model.fail = True
    failed = client.post(route).json()
    assert failed["status"] == "failed"

    visible = client.get(f"/api/comparisons/{comparison['id']}").json()["analysis"]
    assert visible["id"] == first["id"]
    assert visible["result"]["schema_version"] == "impact-report-v4"
    assert visible["latest_attempt"]["id"] == failed["id"]
    assert visible["latest_attempt"]["status"] == "failed"
    history = client.get(f"/api/comparisons/{comparison['id']}/ai-history").json()
    assert len([item for item in history["items"] if item["type"] == "impact"]) == 2


def test_prompt_revisions_change_cache_boundary_without_deleting_old_history(harness):
    client, _, service, model = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    _, comparison = saved_comparison(client, law)
    route = f"/api/comparisons/{comparison['id']}/ask"
    impact_route = f"/api/comparisons/{comparison['id']}/analyse"
    payload = {"question": "What changed?", "history": []}

    initial_prompts = client.get("/api/settings/prompts")
    assert initial_prompts.status_code == 200 and initial_prompts.json()["source"] == "defaults"
    first = client.post(route, json=payload)
    assert first.status_code == 200 and first.json()["prompt_revision"] == 1
    first_impact = client.post(impact_route)
    assert first_impact.status_code == 200 and first_impact.json()["cached"] is False
    calls_before_revision = len(model.calls)

    changed = editable_prompts(initial_prompts.json())
    changed["ask_instructions"] += " Prefer a short first sentence."
    changed["impact_instructions"] += " Prefer a short first sentence."
    saved = client.patch("/api/settings/prompts", json=changed)
    assert saved.status_code == 200 and saved.json()["source"] == "workspace"
    assert saved.json()["revision"] == 1
    assert saved.json()["fingerprint"] != initial_prompts.json()["fingerprint"]
    after_revision = client.post(route, json=payload)
    assert after_revision.status_code == 200 and after_revision.json()["cached"] is False
    revised_impact = client.post(impact_route)
    assert revised_impact.status_code == 200 and revised_impact.json()["cached"] is False
    assert len(model.calls) == calls_before_revision + 2

    history = client.get(f"/api/comparisons/{comparison['id']}/ai-history").json()
    questions = [item for item in history["items"] if item["type"] == "question"]
    assert len(questions) == 2
    assert {item["result"]["answer"] for item in questions} == {"Test-only answer."}

    reset = client.post("/api/settings/prompts/reset")
    assert reset.status_code == 200 and reset.json()["source"] == "defaults"
    calls_before_cache = len(model.calls)
    reused_default = client.post(route, json=payload)
    assert reused_default.status_code == 200 and reused_default.json()["cached"] is False
    assert reused_default.json()["context_mode"] == "impact_report"
    assert reused_default.json()["coverage"]["provider_calls"] == 0
    assert len(model.calls) == calls_before_cache
    repeated_default = client.post(route, json=payload)
    assert repeated_default.json()["cached"] is True
    assert repeated_default.json()["record_id"] == reused_default.json()["record_id"]
    reused_impact = client.post(impact_route)
    assert reused_impact.status_code == 200 and reused_impact.json()["cached"] is True
    assert reused_impact.json()["id"] == first_impact.json()["id"]
    assert len(model.calls) == calls_before_cache
    visible = client.get(f"/api/comparisons/{comparison['id']}").json()["analysis"]
    assert visible["id"] == first_impact.json()["id"] and visible["stale"] is False


def test_deleting_document_removes_its_saved_ai_history(harness):
    client, _, service, _ = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    _, comparison = saved_comparison(client, law)
    assert client.post(
        f"/api/comparisons/{comparison['id']}/ask", json={"question": "What changed?"}
    ).status_code == 200
    assert client.delete(f"/api/laws/{law['id']}").status_code == 200
    assert client.get(f"/api/laws/{law['id']}/ai-history").status_code == 404
    assert client.get(f"/api/comparisons/{comparison['id']}/ai-history").status_code == 404


def test_prompt_settings_survive_an_api_restart(harness):
    client, fetcher, service, _ = harness
    current = client.get("/api/settings/prompts").json()
    changed = editable_prompts(current)
    changed["answer_synthesis_instructions"] += " Start with the direct answer."
    saved = client.patch("/api/settings/prompts", json=changed)
    assert saved.status_code == 200 and saved.json()["source"] == "workspace"

    restarted = create_app(service.environment_settings, fetcher=fetcher)
    with TestClient(restarted) as restored:
        loaded = restored.get("/api/settings/prompts")
        assert loaded.status_code == 200
        assert loaded.json()["answer_synthesis_instructions"] == changed[
            "answer_synthesis_instructions"
        ]
        assert loaded.json()["fingerprint"] == saved.json()["fingerprint"]
        assert loaded.json()["revision"] == saved.json()["revision"]
