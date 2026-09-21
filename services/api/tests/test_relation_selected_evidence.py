"""Unreviewed relation inference may select evidence but cannot assess impact."""

import asyncio
import json

import pytest
from test_relation_evidence_gate import dossier
from test_relation_runtime import (
    approved_local_relation as approved_fixture,
)
from test_relation_runtime import (
    artifacts as artifacts_fixture,
)
from test_relation_runtime import (
    history,
    run,
)
from test_relation_runtime import (
    local_relation as local_fixture,
)

from helvetic_lens.config import DomainError
from helvetic_lens.models import RegulatoryEvent, RelationImpactAnalysis
from helvetic_lens.prompt_settings import default_prompt_settings
from helvetic_lens.relation_analysis import select_evidence, select_relation_evidence

artifacts = artifacts_fixture
local_relation = local_fixture
approved_local_relation = approved_fixture


def test_unreviewed_relation_uses_saved_quotes_without_impact_severity_or_actions(local_relation):
    client, _, model, _, _ = local_relation
    saved = run(local_relation)["result"]["data"]
    report = saved["result"]
    assert report["response_mode"] == "selected_evidence"
    assert report["assessment_status"] == "not_assessed"
    assert not report["supported"] and report["proposed_relation_type"] is None
    assert report["actions"] == [] and report["business_areas"] == []
    assert "does not mean that no action is needed" in report["explanation"]
    assert report["citations"]
    for citation in report["citations"]:
        assert citation["quote"] in client.get(citation["url"]).json()["text"]
    assert saved["provenance"]["capability_decision"]["task"] == "relation_impact"
    assert saved["analysis_plan"]["capability_decision"]["mode"] == "selected_evidence"
    for route in ("/api/impact-inbox", "/api/impact-inbox/page"):
        item = client.get(route).json()["items"][0]["items"][0]
        assert item["status"] == "evidence_only" and item["severity"] == "unknown"
        assert client.get(route, params={"severity": "none"}).json()["items"] == []
    repeated = run(local_relation)["result"]["data"]
    assert repeated["id"] == saved["id"] and len(model.calls) == 1


def test_unassessed_relation_preserves_independent_source_urgency(local_relation):
    client, service, _, _, _ = local_relation
    saved = run(local_relation)["result"]["data"]
    with service.db.session() as session:
        event = session.get(RegulatoryEvent, saved["event_id"])
        event.impact = "high"
        session.commit()
    item = client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]
    assert item["severity"] == "high"


def test_invalid_selected_row_retains_failure_without_fabricating_success(local_relation):
    client, _, model, delivery, _ = local_relation
    model.invalid = True
    response = client.post(f"/api/relation-candidates/{delivery}/analyse-jobs")
    assert response.status_code == 202
    saved = history(local_relation)
    assert saved["current"] is None and len(saved["items"]) == 1
    assert saved["items"][0]["status"] == "failed" and saved["items"][0]["result"] is None
    assert len(model.calls) == 2


def test_empty_selection_is_explicit_and_never_a_no_impact_finding(local_relation):
    client, _, model, _, _ = local_relation
    model.unsupported = True
    report = run(local_relation)["result"]["data"]["result"]
    assert report["citations"] == [] and report["actions"] == []
    assert "No saved passage was selected" in report["explanation"]
    assert "require human review" in report["explanation"]
    assert "Open the citations" not in report["explanation"]
    item = client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]
    assert item["status"] == "evidence_only" and item["severity"] == "unknown"


def test_revoked_relation_approval_invalidates_current_assessment_and_replay(approved_local_relation, artifacts):
    client, service, model, _, _ = approved_local_relation
    old = run(approved_local_relation)["result"]["data"]
    assert old["result"]["response_mode"] == "generated_explanation"
    assert old["result"]["supported"]
    _, _, _, registry, write = artifacts
    registry["profiles"][0]["status"] = "revoked"
    write()
    assert history(approved_local_relation)["current"] is None
    fresh = run(approved_local_relation)["result"]["data"]
    assert fresh["id"] != old["id"] and len(model.calls) == 2
    assert fresh["result"]["assessment_status"] == "not_assessed"
    assert fresh["provenance"]["capability_decision"]["reason"] == "profile_not_approved"
    with service.db.session() as session:
        assert session.get(RelationImpactAnalysis, old["id"]).result == old["result"]
    assert client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]["severity"] == "unknown"


def test_report_approval_does_not_authorize_relation_interpretation(approved_local_relation, artifacts):
    _, _, _, _, _ = approved_local_relation
    _, _, review, registry, write = artifacts
    review["task"] = registry["profiles"][0]["grants"][0]["task"] = "impact_report"
    write()
    saved = run(approved_local_relation)["result"]["data"]
    assert saved["provenance"]["capability_decision"]["reason"] == "scope_not_reviewed"
    assert saved["result"]["response_mode"] == "selected_evidence"


def select_with_model(app, rows, locale="en-CH", official=None):
    _, service, _, _, state = app
    state["runtime"]["prompt_budget_schema"] = "local-prompt-budget-v1"
    async def select():
        async with service.runtime_cache_scope():
            with service.model_capability_scope("relation_impact", locale):
                return await select_relation_evidence(
                    service.model_client, default_prompt_settings(), analysis_id="selection",
                    evidence=rows, coverage={"complete": True, "limited": False},
                    source_work={"id": "source", "title": "New proposal"},
                    target_work={"id": "target", "title": "Monitored act"},
                    candidate={"why": ["Shared subject terms"]}, official_relation=official,
                    output_locale=locale,
                )
    return asyncio.run(select())


def test_measured_dossier_keeps_both_sides_and_cites_only_original_windows(local_relation):
    _, _, model, _, state = local_relation
    rows = [{**row, "text": row["text"] * 100} for row in dossier()]
    state["tokens"] = lambda payload: 600 + sum(len(row[-1]) for row in payload["evidence"]["rows"])
    report, coverage = select_with_model(local_relation, rows)
    assert coverage["limited"] and not coverage["complete"]
    allocation = coverage["token_allocation"]
    assert 1 < allocation["count_probes"] <= 8
    assert allocation["row_numbers"] == list(range(1, len(rows) + 1))
    assert allocation["omitted_row_numbers"] == [] and len(model.calls) == 1
    supplied = json.loads(model.calls[0][1])["evidence"]["rows"]
    assert {row[1] for row in supplied} >= {"event_source_passage", "monitored_work_passage"}
    originals = {row["evidence_id"]: row["text"] for row in rows}
    for citation in report["citations"]:
        assert citation["quote"] in originals[citation["evidence_id"]]
        assert len(citation["quote"]) < len(originals[citation["evidence_id"]])


def test_unfit_minimal_dossier_fails_before_generation(local_relation):
    _, _, model, _, state = local_relation
    state["tokens"] = 10000
    with pytest.raises(DomainError) as error:
        select_with_model(local_relation, dossier())
    assert error.value.code == "model_context_exceeded" and model.calls == []


@pytest.mark.parametrize("locale", ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"])
def test_selected_evidence_is_localized_and_keeps_confirmed_official_fact(local_relation, locale):
    official = {"id": "official-1", "state": "confirmed", "type": "amends",
                "subject_work_id": "source", "object_work_id": "target"}
    report, _ = select_with_model(local_relation, dossier(), locale, official)
    assert report["official_relation"] == official
    assert report["output_locale"] == locale and report["assessment_status"] == "not_assessed"
    assert not report["supported"] and report["actions"] == []


def test_all_rows_but_truncated_text_never_claims_complete_evidence():
    rows = [{**row, "text": row["text"] * 100} for row in dossier()]
    selected, coverage = select_evidence(rows, 4000)
    assert len(selected) == len(rows)
    assert coverage["limited"] and not coverage["complete"]
