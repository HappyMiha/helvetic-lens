"""A specific legal provision cannot be answered with unrelated report excerpts."""

import json

import pytest
from conftest import ScriptedModel

from helvetic_lens import analysis
from helvetic_lens.analysis import (
    answer_question,
    ask_cache_key,
    build_ask_plan,
    local_answer_synthesis,
    materialize_digest_citations,
    targeted_version_evidence,
)
from helvetic_lens.config import Settings
from helvetic_lens.diffing import compare_passages
from helvetic_lens.models import Comparison, Profile, Version
from helvetic_lens.prompt_settings import default_prompt_settings


def provision_case(number="39"):
    def version(side):
        texts = [
            "Unrelated preamble about saved wording and remuneration.",
            f"§ {number}",
            "Leitung",
            "Die Aufsichtsstelle wird von einer Fachperson geleitet."
            + (" Die Besoldung erfolgt analog den Zivilgerichtspräsidenten." if side == "new" else ""),
            "§ 40",
            "An unrelated provision about saved wording.",
            f"§ {number} Abs. 1",
            "Änderungstabelle",
        ]
        return Version(id=side, origin="live", synthetic=False, passages=[
            {"id": f"p{i}", "text": text, "page": 13} for i, text in enumerate(texts)
        ])
    old, new = version("old"), version("new")
    comparison = Comparison(id="comparison", mode="saved_versions", diff=compare_passages(old.passages, new.passages))
    profile = Profile(id="profile", name="Pilot", description="Pilot review", revision=1, business_areas=[])
    report = {
        "id": "partial-report",
        "result": {
            "schema_version": "impact-report-v5", "output_locale": "en-CH",
            "response_mode": "selected_evidence",
            "material_changes": [{"change_id": "cover", "explanation": "Unrelated cover date changed."}],
            "citations": [{"version_id": "new", "passage_id": "p0", "quote": new.passages[0]["text"]}],
        },
        "coverage": {"limited": True, "complete": False, "available_passages": 16,
                     "material_items": 5, "reviewed_material_items": 1, "scope": "Only one selected change was reviewed."},
    }
    return old, new, comparison, profile, report


@pytest.mark.asyncio
@pytest.mark.parametrize("number", ["39", "39a"])
async def test_specific_paragraph_ignores_general_report_and_supplies_its_body(number):
    old, new, comparison, profile, report = provision_case(number)
    settings = Settings(apertus_base_url="https://model.example/v1", apertus_context_chars=4000)
    question = f"Which exact wording changed about Besoldung in § {number}? Quote both saved passages."
    prompts = default_prompt_settings()
    plan = build_ask_plan(settings, comparison, old, new, question, prompts, profile, impact_report=report, output_locale="en-CH")
    assert plan["intent"] == "specific_unit"
    assert plan["execution"]["reused_impact_report_id"] is None
    assert set(plan["selected_evidence_ids"]) == {f"{side}:p{i}" for side in ("old", "new") for i in (1, 2, 3)}
    model = ScriptedModel()
    answer = await answer_question(model, settings, comparison, old, new, profile, question, [], impact_report=report, output_locale="en-CH")
    assert answer["context_mode"] == "targeted_passages"
    assert answer["reused_impact_report_id"] is None
    assert answer["coverage"]["limited"] and not answer["coverage"]["complete"]
    assert answer["coverage"]["provider_calls"] > 0
    assert "Unrelated cover" not in answer["answer"]
    supplied = json.dumps([json.loads(call[1])["evidence"] for call in model.calls], ensure_ascii=False)
    assert old.passages[3]["text"] in supplied
    assert new.passages[3]["text"] in supplied
    assert "Unrelated" not in supplied and "Änderungstabelle" not in supplied


@pytest.mark.asyncio
async def test_missing_or_different_suffix_never_substitutes_an_ordinal_passage():
    old, new, comparison, profile, report = provision_case("39a")
    for version in (old, new):
        version.passages += [{"id": f"f{i}", "text": "Unrelated Besoldung wording.", "page": 14} for i in range(50)]
    settings = Settings(apertus_base_url="https://model.example/v1", apertus_context_chars=4000)
    model = ScriptedModel()
    answer = await answer_question(model, settings, comparison, old, new, profile,
                                  "What changed about Besoldung in § 39?", [], impact_report=report, output_locale="en-CH")
    assert answer["supported"] is False and answer["citations"] == []
    assert answer["coverage"]["included_passages"] == 0
    assert answer["coverage"]["provider_calls"] == 0 and model.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("coverage", [None, {"limited": True, "complete": False, "available_passages": 16,
                                           "material_items": 5, "reviewed_material_items": 1}])
async def test_reused_partial_or_unknown_report_never_claims_complete_coverage(coverage):
    old, new, comparison, profile, report = provision_case()
    report["coverage"] = coverage
    settings, prompts = Settings(), default_prompt_settings()
    question = "Explain the material changes simply"
    model = ScriptedModel()
    plan = build_ask_plan(settings, comparison, old, new, question, prompts, profile, impact_report=report, output_locale="en-CH")
    answer = await answer_question(model, settings, comparison, old, new, profile, question, [], impact_report=report, output_locale="en-CH")
    assert answer["reused_impact_report_id"] == report["id"]
    for item in (plan["coverage"], answer["coverage"]):
        assert item["limited"] is True and item["complete"] is False
        assert item["included_passages"] == 1
        assert "does not establish complete" in item["scope"]
    if coverage:
        assert answer["coverage"]["available_passages"] == 16
        assert answer["coverage"]["reviewed_material_items"] == 1
    assert answer["coverage"]["provider_calls"] == 0 and model.calls == []


def test_updated_router_invalidates_an_existing_question_cache(monkeypatch):
    old, new, comparison, profile, report = provision_case()
    settings, prompts = Settings(), default_prompt_settings()
    current = ask_cache_key(comparison, profile, settings, prompts, "What changed?", [], report)
    monkeypatch.setattr(analysis, "ASK_ROUTER_VERSION", "ask-intent-v1")
    assert current != ask_cache_key(comparison, profile, settings, prompts, "What changed?", [], report)


def test_explicit_unit_does_not_consume_next_section():
    old, new, *_ = provision_case()
    evidence, _, _, _ = targeted_version_evidence(old, new, "Explain §39", 4000, force_targeted=True)
    assert {item["passage_id"] for item in evidence} == {"p1", "p2", "p3"}


def test_selected_body_citations_survive_headers_and_local_synthesis():
    old, new, *_ = provision_case()
    evidence, _, _, _ = targeted_version_evidence(old, new, "Explain §39", 4000, force_targeted=True)
    # The real local model selected all six rows; rows five and six are the bodies.
    selected = materialize_digest_citations({
        "supported": True, "answer": "Selected saved provision wording.",
        "citation_rows": [1, 2, 3, 4, 5, 6, 6],
    }, evidence)
    result = local_answer_synthesis([selected])
    assert len(result["citations"]) == 6
    by_reference = {(item["version_id"], item["passage_id"]): item for item in result["citations"]}
    for version in (old, new):
        citation = by_reference[(version.id, "p3")]
        assert citation["quote"] in version.passages[3]["text"]
        assert citation["url"] == f"/evidence/{version.id}?passage=p3"
    assert "Besoldung" in by_reference[("new", "p3")]["quote"]


def test_materialized_citations_keep_the_existing_ten_row_bound():
    evidence = [{"version_id": "new", "passage_id": f"p{i}", "text": f"Saved evidence {i}.",
                 "side": "new", "page": 1} for i in range(12)]
    selected = materialize_digest_citations({"supported": True, "citation_rows": list(range(1, 13))}, evidence)
    assert len(selected["citations"]) == 10
