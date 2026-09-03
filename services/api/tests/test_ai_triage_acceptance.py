import json
import time
from pathlib import Path

import pytest
from conftest import add_law, import_old

from helvetic_lens.analysis import answer_question, impact_analysis
from helvetic_lens.diffing import compare_passages
from helvetic_lens.models import Comparison, Profile, Version
from helvetic_lens.triage_regression import load_corpus

CORPUS = Path(__file__).resolve().parents[3] / "demo" / "ai-triage-regression.json"


def _full_rewrite_pair():
    corpus = load_corpus(CORPUS)
    case = next(item for item in corpus["cases"] if item["id"] == "large-complete-rewrite")
    generator = case["generator"]
    count = generator["full_passages_per_side"]

    def side(template, prefix):
        return [
            {
                "id": f"{prefix}-{number}",
                "page": (number // 40) + 1,
                "text": template.format(number=number),
            }
            for number in range(1, count + 1)
        ]

    return side(generator["before_template"], "before"), side(
        generator["after_template"], "after"
    )


@pytest.mark.asyncio
async def test_1401_passage_rewrite_respects_ask_and_impact_provider_budgets(harness):
    _, _, service, model = harness
    settings = service.settings.model_copy(
        update={"apertus_base_url": "https://model.example/v1", "apertus_context_chars": 2400}
    )
    before, after = _full_rewrite_pair()
    diff = compare_passages(before, after)
    old = Version(id="hl064-old", origin="uploaded", synthetic=True, passages=before)
    new = Version(id="hl064-new", origin="live", synthetic=True, passages=after)
    comparison = Comparison(id="hl064-large", mode="saved_versions", diff=diff)
    profile = Profile(
        id="hl064-profile",
        name="Regression organization",
        description="Exercises bounded local-first inference.",
        business_areas=["Legal", "Operations"],
        revision=1,
    )

    assert diff["complete"] is True
    assert max(len(before), len(after)) >= 1400

    model.calls.clear()
    answer = await answer_question(
        model,
        settings,
        comparison,
        old,
        new,
        profile,
        "What changed?",
        [],
    )
    answer_call_count = len(model.calls)
    assert answer["supported"] is True
    assert answer["coverage"]["provider_calls"] == answer_call_count <= 3
    assert answer_call_count < len(diff["items"])
    assert answer["coverage"]["limited"] is True

    model.calls.clear()
    report, coverage = await impact_analysis(model, settings, comparison, old, new, profile)
    impact_call_count = len(model.calls)
    assert report["impact"] in {"high", "medium", "low"}
    assert coverage["provider_calls"] == impact_call_count <= 5
    assert impact_call_count < len(diff["items"])
    assert coverage["limited"] is True
    tasks = [json.loads(user).get("task") for _, user in model.calls]
    assert tasks.count("impact_synthesis") <= 1


def test_cached_outputs_citations_and_last_valid_report_are_guarded_together(harness):
    client, _, service, model = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]},
    ).json()
    ask_url = f"/api/comparisons/{comparison['id']}/ask"
    impact_url = f"/api/comparisons/{comparison['id']}/analyse"

    first_answer = client.post(ask_url, json={"question": "What changed?"})
    assert first_answer.status_code == 200 and first_answer.json()["cached"] is False
    calls_after_first = len(model.calls)
    repeated_answer = client.post(ask_url, json={"question": "What changed?"})
    assert repeated_answer.status_code == 200 and repeated_answer.json()["cached"] is True
    assert repeated_answer.json()["record_id"] == first_answer.json()["record_id"]
    assert len(model.calls) == calls_after_first

    first_report = client.post(impact_url)
    assert first_report.status_code == 200 and first_report.json()["status"] == "succeeded"
    report = first_report.json()["result"]
    assert len({action["action_key"] for action in report["actions"]}) == len(report["actions"])
    for citation in report["citations"]:
        evidence = client.get(f"/api/versions/{citation['version_id']}").json()
        passage = next(item for item in evidence["passages"] if item["id"] == citation["passage_id"])
        assert citation["quote"] in passage["text"]

    prompts = client.get("/api/settings/prompts").json()
    editable = {
        key: prompts[key]
        for key in {
            "impact_instructions",
            "impact_synthesis_instructions",
            "ask_instructions",
            "answer_synthesis_instructions",
            "repair_instructions",
            "ask_context_mode",
        }
    }
    editable["impact_instructions"] += " Force a distinct regression revision."
    assert client.patch("/api/settings/prompts", json=editable).status_code == 200
    model.fail = True
    failed_report = client.post(impact_url)
    assert failed_report.status_code == 200 and failed_report.json()["status"] == "failed"
    visible = client.get(f"/api/comparisons/{comparison['id']}").json()["analysis"]
    assert visible["id"] == first_report.json()["id"]
    assert visible["latest_attempt"]["id"] == failed_report.json()["id"]
    assert visible["latest_attempt"]["status"] == "failed"

    model.fail = False
    model.invalid = True
    invalid_answer = client.post(ask_url, json={"question": "Explain Article 2"})
    assert invalid_answer.status_code == 502
    assert invalid_answer.json()["code"] == "invalid_citation"
    history = client.get(f"/api/comparisons/{comparison['id']}/ai-history").json()["items"]
    rejected = next(item for item in history if item.get("question") == "Explain Article 2")
    assert rejected["status"] == "failed" and rejected["result"] is None


def test_vague_question_returns_choices_without_document_inference(harness):
    client, _, _, model = harness
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]},
    ).json()
    model.calls.clear()

    started = time.perf_counter()
    response = client.post(
        f"/api/comparisons/{comparison['id']}/ask",
        json={"question": "Ничего не понятно но очень интересно"},
    )
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert response.json()["context_mode"] == "clarification"
    assert response.json()["coverage"]["provider_calls"] == 0
    assert len(response.json()["suggestions"]) == 4
    assert elapsed < 1
    assert model.calls == []


@pytest.mark.asyncio
async def test_formatting_only_change_accepts_zero_actions_and_zero_provider_calls(harness):
    _, _, service, model = harness
    old = Version(
        id="hl064-format-old",
        origin="uploaded",
        synthetic=True,
        passages=[{"id": "old-wrap", "page": 1, "text": "L’obliga-\ntion reste applicable."}],
    )
    new = Version(
        id="hl064-format-new",
        origin="live",
        synthetic=True,
        passages=[{"id": "new-wrap", "page": 1, "text": "L’obligation reste applicable."}],
    )
    comparison = Comparison(
        id="hl064-formatting", mode="saved_versions", diff=compare_passages(old.passages, new.passages)
    )
    profile = Profile(
        id="hl064-format-profile",
        name="Regression organization",
        description="Formatting-only acceptance case.",
        business_areas=["Legal"],
        revision=1,
    )
    model.calls.clear()

    report, coverage = await impact_analysis(
        model, service.settings, comparison, old, new, profile
    )

    assert comparison.diff["material_count"] == 0
    assert report["actions"] == []
    assert coverage["provider_calls"] == 0
    assert model.calls == []
