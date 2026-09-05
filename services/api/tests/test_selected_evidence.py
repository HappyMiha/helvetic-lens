import copy
import json

import pytest
from conftest import add_law, import_old

from helvetic_lens.analysis import (
    ImpactDigest,
    InferenceBudget,
    answer_from_impact_report,
    finalize_impact_report,
    localized_cited_change_answer,
    structured_completion,
)
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.models import Analysis, Comparison
from helvetic_lens.selected_evidence import COPY, selected_evidence_copy


def comparison_for(client):
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]},
    )
    assert comparison.status_code == 201, comparison.text
    return law, comparison.json()


@pytest.mark.parametrize("locale", list(COPY))
def test_selection_cannot_establish_impact_applicability_actions_or_absent_dates(locale):
    comparison = Comparison(
        id="comparison",
        diff={
            "items": [
                {
                    "id": "c1",
                    "kind": "modified",
                    "significance": "substantive",
                    "old": {"id": "p1", "text": "Art. 1 Deadline: 30 days."},
                    "new": {"id": "p2", "text": "Art. 1 Deadline: 60 days."},
                }
            ]
        },
    )
    evidence = [
        {
            "change_id": "c1",
            "version_id": "old",
            "passage_id": "p1",
            "text": "Art. 1 Deadline: 30 days.",
            "side": "old",
            "page": 1,
        },
        {
            "change_id": "c1",
            "version_id": "new",
            "passage_id": "p2",
            "text": "Art. 1 Deadline: 60 days.",
            "side": "new",
            "page": 1,
        },
    ]
    citation = {"version_id": "new", "passage_id": "p2", "quote": evidence[1]["text"]}
    result = {
        "response_mode": "selected_evidence",
        "summary": "A fabricated high impact!",
        "reason": "Applies to all organizations.",
        "impact": "high",
        "business_areas": ["HR"],
        "actions": [{"text": "Update every policy immediately.", "citations": [citation]}],
        "citations": [citation],
    }
    report = finalize_impact_report(result, comparison, evidence, {}, output_locale=locale)
    assert report["schema_version"] == "impact-report-v4"
    assert report["response_mode"] == "selected_evidence"
    assert report["assessment_status"] == "not_assessed"
    assert report["impact"] == report["materiality"] == "unknown"
    assert report["actions"] == report["business_areas"] == []
    assert report["organization_applicability"]["status"] == "unknown"
    assert {item["status"] for item in report["important_dates"]} == {"uncertain"}
    assert report["date_review"]["legal_meaning_status"] == "not_reviewed"
    assert report["summary"] == selected_evidence_copy(locale)["summary"]
    assert report["reason"] == selected_evidence_copy(locale)["reason"]
    assert "30 days" in report["material_changes"][0]["explanation"]
    assert "60 days" in report["material_changes"][0]["explanation"]
    assert report["citations"][0]["quote"] == citation["quote"]
    wrapper = {"id": "saved-report", "result": report}
    for intent in ("actions", "organization_impact", "explain_changes"):
        answer = answer_from_impact_report(intent, locale, wrapper)
        assert answer["response_mode"] == "selected_evidence"
        assert answer["supported"] is (intent == "explain_changes")
        assert answer["reused_impact_report_id"] == "saved-report"
        assert answer["citations"]


@pytest.mark.parametrize("locale", list(COPY))
def test_selected_quotes_do_not_prove_removal_addition_or_pairing(locale):
    old = {"version_id": "old", "quote": "Art. 2 Unrelated old provision."}
    new = {"version_id": "new", "quote": "Art. 7 Different current provision."}
    copy = selected_evidence_copy(locale)
    assert localized_cited_change_answer([old], "old", "new", locale, "fallback") == (
        f"{copy['earlier']}: {old['quote']}"
    )
    assert localized_cited_change_answer([new], "old", "new", locale, "fallback") == (
        f"{copy['current']}: {new['quote']}"
    )
    assert localized_cited_change_answer([new, old], "old", "new", locale, "fallback") == (
        f"{copy['earlier']}: {old['quote']}\n\n{copy['current']}: {new['quote']}"
    )


def test_selected_mode_survives_cache_history_and_does_not_reinterpret_v2(harness):
    client, _, service, model = harness
    service.settings.apertus_provider = "docker"
    service.settings.apertus_base_url = "http://127.0.0.1:12435/v1"
    model.settings = service.settings
    law, comparison = comparison_for(client)
    route = f"/api/comparisons/{comparison['id']}"
    first = client.post(route + "/analyse").json()
    assert first["status"] == "succeeded", first
    assert first["result"]["response_mode"] == "selected_evidence"
    assert first["result"]["impact"] == "unknown"
    call_count = len(model.calls)
    repeated = client.post(route + "/analyse").json()
    assert repeated["id"] == first["id"] and repeated["cached"]
    answer = client.post(route + "/ask", json={"question": "What should we do?"}).json()
    assert answer["response_mode"] == "selected_evidence" and not answer["supported"]
    assert len(model.calls) == call_count  # Reuse does not spend tokens.
    history = client.get(route + "/ai-history").json()["items"]
    assert all(item["result"]["response_mode"] == "selected_evidence" for item in history)
    matrix = client.get("/api/impact-matrix").json()
    assert len(matrix["rows"]) == 1 and matrix["rows"][0]["cells"]
    assert all(
        cell["state"] == "unknown"
        for row in matrix["rows"]
        if row["law_id"] == law["id"]
        for cell in row["cells"]
    )

    # Emulate a pre-mode stored record without rewriting it on a read.
    legacy = copy.deepcopy(first["result"])
    legacy["schema_version"] = "impact-report-v2"
    legacy["impact"] = legacy["materiality"] = "high"
    del legacy["response_mode"], legacy["assessment_status"]
    with service.db.session() as session:
        record = session.get(Analysis, first["id"])
        record.result = legacy
        record.cache_key = "previous-code-cache-key"
        session.commit()
    visible = client.get(route).json()["analysis"]
    assert visible["stale"] and visible["result"] == legacy
    assert answer_from_impact_report("actions", "en-CH", {"result": legacy}) is None
    replacement = client.post(route + "/analyse").json()
    assert replacement["id"] != first["id"]
    assert replacement["result"]["impact"] == "unknown"
    with service.db.session() as session:
        assert session.get(Analysis, first["id"]).result == legacy


def test_local_ask_without_report_does_not_claim_an_impact_conclusion(harness):
    client, _, service, model = harness
    service.settings.apertus_provider = "docker"
    service.settings.apertus_base_url = "http://127.0.0.1:12435/v1"
    model.settings = service.settings
    _, comparison = comparison_for(client)
    response = client.post(
        f"/api/comparisons/{comparison['id']}/ask",
        json={"question": "What should we do?"},
    )
    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer["response_mode"] == "selected_evidence"
    assert not answer["supported"]
    assert answer["citations"]
    assert len(model.calls) <= 3


def test_generated_and_zero_call_answers_keep_their_actual_mode(harness):
    client, _, service, _ = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    _, comparison = comparison_for(client)
    route = f"/api/comparisons/{comparison['id']}"
    report = client.post(route + "/analyse").json()
    assert report["result"]["response_mode"] == "generated_explanation"
    assert report["result"]["impact"] == "medium"
    answer = client.post(route + "/ask", json={"question": "What changed?"}).json()
    assert answer["response_mode"] == "generated_explanation"
    assert answer["coverage"]["provider_calls"] == 0  # Origin survives report reuse.
    vague = client.post(route + "/ask", json={"question": "Help"}).json()
    assert vague["response_mode"] == "deterministic"
    assert vague["coverage"]["provider_calls"] == 0


def test_server_authored_unsupported_reply_does_not_claim_model_authorship(harness):
    client, _, service, model = harness
    service.settings.apertus_provider = "docker"
    service.settings.apertus_base_url = "http://127.0.0.1:12435/v1"
    model.settings = service.settings
    model.unsupported = True
    _, comparison = comparison_for(client)
    response = client.post(
        f"/api/comparisons/{comparison['id']}/ask", json={"question": "Who signed the law?"}
    )
    assert response.status_code == 200, response.text
    answer = response.json()
    assert not answer["supported"]
    assert answer["response_mode"] == answer["coverage"]["response_mode"] == "deterministic"
    assert 0 < answer["coverage"]["provider_calls"] == len(model.calls) <= 3
    assert not answer["citations"]


@pytest.mark.asyncio
@pytest.mark.parametrize("repair_valid", [True, False])
async def test_selection_still_validates_citations_with_only_one_repair(repair_valid):
    class Client:
        settings = Settings(_env_file=None, apertus_provider="docker")
        calls = 0

        async def complete(self, system, user, *, response_schema, budget):
            budget.claim()
            self.calls += 1
            return json.dumps(
                {"citation_rows": [1 if repair_valid and self.calls == 2 else 999], "impact": "high"}
            )

    client = Client()
    budget = InferenceBudget(3)
    payload = {"evidence": {"columns": ["row_number", "text"], "rows": [[1, "Saved wording"]]}}
    if repair_valid:
        result = await structured_completion(
            client,
            "Select evidence",
            payload,
            ImpactDigest,
            [],
            validate_citations=False,
            numeric_reference_count=1,
            budget=budget,
        )
        assert result["citation_rows"] == [1]
    else:
        with pytest.raises(DomainError, match="citation"):
            await structured_completion(
                client,
                "Select evidence",
                payload,
                ImpactDigest,
                [],
                validate_citations=False,
                numeric_reference_count=1,
                budget=budget,
            )
    assert client.calls == budget.used == 2
