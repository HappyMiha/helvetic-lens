"""Contract/HTTP regression fixtures, not independent semantic acceptance."""

import copy
import json

import pytest
from decision_fixtures import decision_draft
from pydantic import ValidationError
from test_ai_capabilities import artifacts as artifacts_fixture
from test_capability_execution import approved_app as approved_fixture
from test_capability_execution import history, request_analysis

from helvetic_lens.analysis import answer_from_impact_report
from helvetic_lens.config import DomainError
from helvetic_lens.decision_copy import COPY, decision_copy
from helvetic_lens.decision_report import (
    DecisionDraft,
    decision_catalogs,
    materialize_decision,
    validate_draft,
)
from helvetic_lens.models import Analysis

artifacts = artifacts_fixture
approved_app = approved_fixture


@pytest.fixture
def decision_case():
    rows = [
        {"version_id": side, "passage_id": f"p{number}", "change_id": f"c{number}", "side": side}
        for number in (1, 2)
        for side in ("old", "new")
    ]
    citations = [
        {
            **{key: row[key] for key in ("version_id", "passage_id")},
            "quote": f"Records are retained for {30 if row['version_id'] == 'old' else 60} days in {row['passage_id']}.",
            "url": "/evidence/synthetic",
        }
        for row in rows
    ]
    changes, activities = decision_catalogs(citations, rows, ["Record storage", "Payroll"])
    draft = decision_draft(
        {
            "citation_catalog": [{"number": i, **c} for i, c in enumerate(citations, 1)],
            "change_catalog": changes,
            "activity_catalog": activities,
        }
    )
    coverage = {"limited": False, "material_items": 2}
    return draft, citations, changes, activities, coverage


def validated(case):
    draft, citations, changes, activities, coverage = case
    return validate_draft(
        DecisionDraft.model_validate(draft).model_dump(), citations, changes, activities, coverage
    )


@pytest.mark.parametrize("locale", list(COPY))
def test_actions_deduplicate_by_source_obligation_activity_and_type_not_title(decision_case, locale):
    draft, citations, changes, activities, _ = decision_case
    original = draft["actions"][0]
    duplicate = {
        **original,
        "title": "Inspect records policy",
        "text": "Compare the applicable schedule before revising it.",
        "priority": "high",
    }
    draft["actions"] += [
        duplicate,
        {**original, "activity_number": 2},
        {**original, "action_type": "legal_review"},
    ]
    report = materialize_decision(
        validated(decision_case), citations, changes, activities, decision_copy(locale)
    )
    assert len(report["actions"]) == 3 and report["decision_review"]["merged_actions"] == 1
    assert report["actions"][0]["priority"] == "high"
    for action in report["actions"]:
        assert action["owner_role"] == decision_copy(locale)["unassigned"]
        assert action["due_date"] is None and action["due_basis"] == "not_reviewed"
        assert action["review_suggestion"] and action["evidence_grade"] == "possible"
        assert action["obligation_anchor"]["quote"] in action["obligation_anchor"]["citation"]["quote"]
    old_key = report["actions"][0]["action_key"]
    draft["actions"] = [duplicate]
    rerun = materialize_decision(
        validated(decision_case), citations, changes, activities, decision_copy(locale)
    )
    assert rerun["actions"][0]["action_key"] == old_key


@pytest.mark.parametrize(
    "fault",
    [
        "claim_ref",
        "wrong_change",
        "one_side",
        "activity",
        "invented_anchor",
        "anchor_ref",
        "status_ref",
        "owner",
        "due_date",
        "action_state",
    ],
)
def test_invalid_claims_do_not_become_valid_actions(decision_case, fault):
    draft = decision_case[0]
    if fault == "claim_ref":
        draft["changes"][0]["citation_numbers"] = [999]
    if fault == "wrong_change":
        draft["changes"][0]["citation_numbers"] = [3, 4]
    if fault == "one_side":
        draft["changes"][0]["citation_numbers"] = [1]
    if fault == "activity":
        draft["actions"][0]["activity_number"] = 999
    if fault == "invented_anchor":
        draft["actions"][0]["obligation_quote"] = "All employers must close the office."
    if fault == "anchor_ref":
        draft["actions"][0]["obligation_citation"] = 999
    if fault == "status_ref":
        draft["official_status"]["citation_numbers"] = [999]
    if fault in {"owner", "due_date"}:
        draft["actions"][0][fault] = "Invented"
    if fault == "action_state":
        draft["action_review"]["status"] = "no_action_now"
    with pytest.raises((DomainError, ValidationError)):
        validated(decision_case)


@pytest.mark.parametrize("incomplete", ["coverage", "unexplained", "applicability", "undercounted"])
def test_empty_actions_cannot_claim_no_action_for_incomplete_review(decision_case, incomplete):
    draft, _, changes, _, coverage = decision_case
    draft["actions"] = []
    draft["action_review"]["status"] = "no_action_now"
    draft["changes"].append(
        {
            "change_number": 2,
            "explanation": "Second change reviewed.",
            "citation_numbers": changes[1]["citation_numbers"],
        }
    )
    if incomplete == "coverage":
        coverage["limited"] = True
    if incomplete == "unexplained":
        draft["changes"].pop()
    if incomplete == "applicability":
        draft["applicability"]["status"] = "unknown"
    if incomplete == "undercounted":
        coverage["material_items"] = 1
        draft["changes"].pop()
    with pytest.raises((DomainError, ValidationError)):
        validated(decision_case)
    draft["action_review"]["status"] = "not_reviewed"
    assert validated(decision_case)["actions"] == []


def test_reviewed_no_action_and_proposal_remain_interpretations(decision_case):
    draft, citations, changes, activities, coverage = decision_case
    draft["changes"].append({"change_number": 2, "explanation": "Second change reviewed.", "citation_numbers": changes[1]["citation_numbers"]})
    draft["actions"] = []
    draft["action_review"]["status"] = "no_action_now"
    draft["official_status"] = {
        "status": "proposal",
        "explanation": "The cited heading calls this a proposal.",
        "citation_numbers": [1],
    }
    result = materialize_decision(
        validated(decision_case), citations, changes, activities, decision_copy("en-CH")
    )
    assert result["action_review"]["status"] == "no_action_now" and not result["actions"]
    assert result["official_status"]["status"] == "proposal"
    assert result["official_status"]["basis"] == "model_interpretation"


def with_activity(app):
    response = app[0].patch(
        "/api/profile",
        json={
            "name": "Synthetic records team",
            "description": "We store records.",
            "business_areas": ["Record storage"],
        },
    )
    assert response.status_code == 200, response.text


def test_real_approved_pipeline_persists_claims_conditions_actions_and_zero_call_reuse(approved_app):
    with_activity(approved_app)
    response = request_analysis(approved_app, "analyse")
    assert response.status_code == 200, response.text
    record = history(approved_app)[0]
    assert record["status"] == "succeeded", record
    report = record["result"]
    assert report["schema_version"] == "impact-report-v5"
    assert report["decision_review"]["basis"] == "model_interpretation"
    assert report["organization_applicability"]["conditions"]
    interpreted = [c for c in report["material_changes"] if c["explanation_basis"] == "model_interpretation"]
    assert interpreted[0]["explanation"] == "The selected wording changes the retention review."
    assert {ref["version_id"] for ref in interpreted[0]["citations"]} == {
        approved_app[2]["old_version_id"],
        approved_app[2]["new_version_id"],
    }
    assert report["actions"][0]["affected_area"] == "Record storage"
    assert report["actions"][0]["owner_role"] == "Not assigned"
    assert report["action_review"]["status"] == "review_actions"
    assert report["date_review"]["legal_meaning_status"] == "not_reviewed"
    assert len(approved_app[3]["generated"]) == 2
    again = request_analysis(approved_app, "analyse").json()
    assert again["cached"] and again["result"] == report
    assert len(approved_app[3]["generated"]) == 2
    for citation in report["actions"][0]["citations"]:
        version = approved_app[0].get(f"/api/versions/{citation['version_id']}").json()
        passage = next(p for p in version["passages"] if p["id"] == citation["passage_id"])
        assert citation["quote"] in passage["text"]
        assert citation["url"].startswith("/evidence/")


@pytest.mark.parametrize("repair_succeeds", [False, True])
@pytest.mark.parametrize("fault", ["citation", "anchor", "owner"])
def test_actual_api_repairs_draft_once_or_preserves_failure_without_template_fallback(
    approved_app, repair_succeeds, fault
):
    with_activity(approved_app)

    def transform(draft, payload):
        if not (repair_succeeds and payload.get("repair")):
            if fault == "citation":
                draft["changes"][0]["citation_numbers"] = [999]
            if fault == "anchor":
                draft["actions"][0]["obligation_quote"] = "Invented exact legal obligation."
            if fault == "owner":
                draft["actions"][0]["owner_role"] = "CEO"
        return draft

    approved_app[3]["draft_transform"] = transform
    request_analysis(approved_app, "analyse")
    record = history(approved_app)[0]
    assert record["status"] == ("succeeded" if repair_succeeds else "failed"), record
    assert (record["result"] is not None) == repair_succeeds
    generated = approved_app[3]["generated"]
    assert len(generated) == 3  # one batch + synthesis + one repair, no template fallback
    first, retry = [json.loads(wire["messages"][-1]["content"]) for wire in generated[-2:]]
    assert retry["citation_catalog"] == first["citation_catalog"]
    assert retry["change_catalog"] == first["change_catalog"]
    assert retry["repair"]["validation_error"]


def test_v4_history_remains_exact_and_only_explicit_reassessment_creates_v5(approved_app):
    first = request_analysis(approved_app, "analyse").json()
    client, service, comparison, state, *_ = approved_app
    legacy = copy.deepcopy(first["result"])
    legacy["schema_version"] = "impact-report-v4"
    for key in ("decision_review", "official_status", "action_review"):
        legacy.pop(key)
    with service.db.session() as session:
        row = session.get(Analysis, first["id"])
        row.result = legacy
        row.cache_key = "synthetic-v4-key"
        session.commit()
    count = len(state["generated"])
    route = f"/api/comparisons/{comparison['id']}"
    visible = client.get(route).json()["analysis"]
    assert visible["stale"] and visible["result"] == legacy
    assert history(approved_app)[0]["result"] == legacy
    assert answer_from_impact_report("actions", "en-CH", {"result": legacy}) is None
    assert len(state["generated"]) == count
    new = request_analysis(approved_app, "analyse").json()
    assert new["id"] != first["id"] and new["result"]["schema_version"] == "impact-report-v5"
    assert next(item for item in history(approved_app) if item["id"] == first["id"])["result"] == legacy


@pytest.mark.parametrize("locale", list(COPY))
def test_five_locale_reports_keep_source_words_and_reuse_conditions_and_actions(approved_app, locale):
    with_activity(approved_app)
    approved_app[4]["locale"] = locale
    approved_app[5]["profiles"][0]["grants"][0]["locale"] = locale
    first = request_analysis(approved_app, "analyse", locale).json()
    assert first["status"] == "succeeded", first
    report = first["result"]
    assert report["output_locale"] == locale
    assert report["actions"][0]["owner_role"] == decision_copy(locale)["unassigned"]
    for intent in ("organization_impact", "actions"):
        answer = answer_from_impact_report(intent, locale, first)
        assert decision_copy(locale)["interpretation"] in answer["answer"]
        condition = report["organization_applicability"]["conditions"][0] if intent == "organization_impact" else report["actions"][0]["applicability_condition"]
        assert condition in answer["answer"]
        assert answer["reused_impact_report_id"] == first["id"] and answer["citations"]
    assert len(approved_app[3]["generated"]) == 2
    payload = json.loads(approved_app[3]["generated"][-1]["messages"][-1]["content"])
    assert all(item["quote"] in next(row["quote"] for row in payload["citation_catalog"] if row["version_id"] == item["version_id"] and row["passage_id"] == item["passage_id"]) for item in report["citations"])
