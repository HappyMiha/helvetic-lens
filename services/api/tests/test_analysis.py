import json

import pytest
from conftest import LAW_URL, add_law, import_old, policy, run_scan

from regwatch.analysis import Answer, ModelClient, parse_response, select_evidence
from regwatch.config import DomainError
from regwatch.diffing import DIFF_SCHEMA_VERSION, compare_passages
from regwatch.models import Comparison, Version


def test_timeout_keeps_diff_retry_only_analysis_and_profile_invalidates_cache(harness):
    client, fetcher, service, model = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    fetcher.values[LAW_URL] = policy(60)
    model.fail = True
    scan = run_scan(client, [law["id"]])
    item = scan["items"][0]
    assert scan["status"] == "partial"
    assert item["result"] == "changed"
    assert item["analysis_status"] == "failed"
    assert item["stage"] == "complete"
    comparison_id = item["comparison_id"]
    assert client.get("/api/comparisons/" + comparison_id).json()["diff"]["changed"]
    fetch_count = len(fetcher.calls)
    model.fail = False
    route = "/api/comparisons/" + comparison_id + "/analyse"
    result = client.post(route).json()
    assert result["status"] == "succeeded" and result["cached"] is False
    assert len(fetcher.calls) == fetch_count
    assert len(client.get("/api/laws/" + law["id"]).json()["versions"]) == 2
    citation = result["result"]["actions"][0]["citations"][0]
    assert citation["url"].startswith("/evidence/" + citation["version_id"])
    evidence = client.get("/api/versions/" + citation["version_id"]).json()
    assert citation["quote"] in next(
        p["text"] for p in evidence["passages"] if p["id"] == citation["passage_id"]
    )
    previous_calls = len(model.calls)
    assert client.post(route).json()["cached"] is True
    assert len(model.calls) == previous_calls
    client.patch(
        "/api/profile",
        json={"name": "Different company", "description": "New profile", "business_areas": ["HR"]},
    )
    assert client.get("/api/comparisons/" + comparison_id).json()["analysis"]["stale"] is True
    assert client.post(route).json()["cached"] is False
    assert len(model.calls) == previous_calls + 1
    assert client.get("/api/comparisons/" + comparison_id).json()["analysis"]["stale"] is False


def test_invalid_citations_never_appear_as_success_and_retry_works(harness):
    client, fetcher, service, model = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    fetcher.values[LAW_URL] = policy(60)
    model.invalid = True
    item = run_scan(client, [law["id"]])["items"][0]
    comparison = client.get("/api/comparisons/" + item["comparison_id"]).json()
    assert comparison["analysis"]["status"] == "failed"
    assert comparison["analysis"]["result"] is None
    route = "/api/comparisons/" + item["comparison_id"] + "/ask"
    reply = client.post(route, json={"question": "What changed?"})
    assert reply.status_code == 502 and reply.json()["code"] == "invalid_citation"
    model.invalid = False
    assert (
        client.post("/api/comparisons/" + item["comparison_id"] + "/analyse").json()["status"] == "succeeded"
    )


def test_questions_use_selected_pair_and_explicit_unsupported_answer(harness):
    client, _, service, model = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons", json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]}
    ).json()
    route = "/api/comparisons/" + comparison["id"] + "/ask"
    reply = client.post(route, json={"question": "What changed?"})
    assert reply.status_code == 200 and reply.json()["supported"] is True
    prior_question = {"question": "What changed?"}
    assert (
        client.post(
            route, json={"question": "What did the older version say?", "history": [prior_question]}
        ).status_code
        == 200
    )
    model_input = json.loads(model.calls[-1][1])
    assert model_input["previous_questions"] == [prior_question]
    assert {p["version_id"] for p in model_input["evidence"]} == {old["id"], law["current_version_id"]}
    assert len(model_input["evidence"]) == 2
    assert model_input["coverage"]["complete"] is True
    assert model_input["coverage"]["limited"] is False
    assert model_input["deterministic_diff"]["complete"] is True
    assert len(model_input["deterministic_diff"]["items"]) == 1
    model.unsupported = True
    unsupported = client.post(route, json={"question": "Who signed the law?"}).json()
    assert unsupported["supported"] is False and unsupported["citations"] == []


@pytest.mark.parametrize(
    "citation",
    [
        {"version_id": "old", "passage_id": "missing", "quote": "30"},
        {"version_id": "new", "passage_id": "p1", "quote": "30"},
        {"version_id": "old", "passage_id": "p1", "quote": "invented deadline"},
        {"version_id": "old", "passage_id": "p1", "quote": "  "},
    ],
)
def test_exact_version_passage_and_nonempty_quote_required(citation):
    evidence = [
        {"version_id": "old", "passage_id": "p1", "text": "Retention is 30 days.", "page": 2},
        {"version_id": "new", "passage_id": "p1", "text": "Retention is 60 days.", "page": 3},
    ]
    with pytest.raises(DomainError) as error:
        parse_response(
            json.dumps({"supported": True, "answer": "A changed period.", "citations": [citation]}),
            Answer,
            evidence,
        )
    assert error.value.code == "invalid_citation"


def test_both_versions_cite_their_own_saved_page():
    evidence = [
        {"version_id": "old", "passage_id": "p1", "text": "Retention is 30 days.", "page": 2},
        {"version_id": "new", "passage_id": "p1", "text": "Retention is 60 days.", "page": 3},
    ]
    raw = json.dumps(
        {
            "supported": True,
            "answer": "30 became 60.",
            "citations": [
                {"version_id": "old", "passage_id": "p1", "quote": "30 days"},
                {"version_id": "new", "passage_id": "p1", "quote": "60 days"},
            ],
        }
    )
    result = parse_response(raw, Answer, evidence)
    assert result["citations"][0]["url"] == "/evidence/old?passage=p1"
    assert result["citations"][0]["page"] == 2
    assert result["citations"][1]["url"] == "/evidence/new?passage=p1"
    assert result["citations"][1]["page"] == 3
    with pytest.raises(DomainError):
        parse_response('{"supported":true,"answer":"Uncited","citations":[]}', Answer, evidence)
    with pytest.raises(DomainError):
        parse_response("A plain sentence is not the agreed structure.", Answer, evidence)


def test_complete_diff_aligns_articles_and_covers_every_saved_passage_once():
    old = [
        {"id": "old-1", "text": "Art. 1 Purpose", "page": 1},
        {"id": "old-2", "text": "Records must be retained for 30 days.", "page": 1},
        {"id": "old-3", "text": "Art. 2 Scope", "page": 2},
    ]
    new = [
        {"id": "new-1", "text": "Art. 1 Purpose", "page": 1},
        {"id": "new-2", "text": "A controller must appoint an owner.", "page": 1},
        {"id": "new-3", "text": "Records must be retained for 60 days.", "page": 1},
        {"id": "new-4", "text": "Art. 2 Scope", "page": 2},
    ]
    diff = compare_passages(old, new)
    assert diff["schema_version"] == DIFF_SCHEMA_VERSION and diff["complete"] is True
    assert diff["granularity"] == "article_or_passage"
    assert diff["counts"] == {"added": 1, "removed": 0, "modified": 1, "unchanged": 2}
    assert [item["old"]["id"] for item in diff["items"] if item["old"]] == [
        passage["id"] for passage in old
    ]
    assert [item["new"]["id"] for item in diff["items"] if item["new"]] == [
        passage["id"] for passage in new
    ]
    modified = next(item for item in diff["items"] if item["kind"] == "modified")
    assert modified["old"]["id"] == "old-2" and modified["new"]["id"] == "new-3"
    assert modified["old_position"] == 2 and modified["new_position"] == 3


def test_large_replacement_fallback_still_covers_both_saved_versions():
    old = [
        {"id": f"old-{index}", "text": f"Legacy clause {index} alpha requirement.", "page": index}
        for index in range(205)
    ]
    new = [
        {"id": f"new-{index}", "text": f"Replacement section {index} zeta obligation.", "page": index}
        for index in range(205)
    ]
    diff = compare_passages(old, new)
    assert diff["complete"] is True
    assert sum(item["old"] is not None for item in diff["items"]) == len(old)
    assert sum(item["new"] is not None for item in diff["items"]) == len(new)


def test_legacy_persisted_comparison_is_upgraded_before_it_is_returned(harness):
    client, _, service, _ = harness
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]},
    ).json()
    with service.db.session() as session:
        stored = session.get(Comparison, comparison["id"])
        stored.diff = {
            "items": [
                {
                    key: value
                    for key, value in item.items()
                    if key not in {"old_position", "new_position"}
                }
                for item in stored.diff["items"]
            ],
            "counts": stored.diff["counts"],
            "changed": stored.diff["changed"],
        }
        session.commit()

    upgraded = client.get("/api/comparisons/" + comparison["id"]).json()["diff"]
    assert upgraded["schema_version"] == DIFF_SCHEMA_VERSION and upgraded["complete"] is True
    with service.db.session() as session:
        assert session.get(Comparison, comparison["id"]).diff == upgraded


def test_changed_evidence_is_complete_and_ignores_retrieval_budget():
    old = Version(
        id="old",
        origin="uploaded",
        synthetic=True,
        passages=[
            {"id": "p1", "text": "Earlier wording " * 500, "page": 1},
            {"id": "p2", "text": "Shared unchanged article.", "page": 2},
        ],
    )
    new = Version(
        id="new",
        origin="live",
        synthetic=True,
        passages=[
            {"id": "p1", "text": "Current wording " * 500, "page": 1},
            {"id": "p2", "text": "Other section " * 500, "page": 2},
            {"id": "p3", "text": "Shared unchanged article.", "page": 3},
        ],
    )
    comparison = Comparison(diff=compare_passages(old.passages, new.passages))
    evidence, coverage = select_evidence(old, new, comparison, 1000, "Earlier wording")
    assert sum(len(p["text"]) for p in evidence) > 1000
    assert coverage["limited"] is False and coverage["complete"] is True
    assert coverage["exceeds_configured_context"] is True
    assert coverage["included_passages"] == coverage["available_passages"] == 3
    assert {(p["version_id"], p["passage_id"]) for p in evidence} == {
        ("old", "p1"),
        ("new", "p1"),
        ("new", "p2"),
    }
    assert all(p["synthetic"] is True for p in evidence)


def test_invalid_json_is_validated_and_repaired_once_for_impact_and_ask(harness):
    client, _, service, model = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]},
    ).json()

    model.invalid_json_responses = 1
    impact = client.post("/api/comparisons/" + comparison["id"] + "/analyse")
    assert impact.status_code == 200 and impact.json()["status"] == "succeeded"
    assert len(model.calls) == 2 and "repair" in json.loads(model.calls[1][1])

    model.calls.clear()
    model.invalid_json_responses = 1
    answer = client.post(
        "/api/comparisons/" + comparison["id"] + "/ask", json={"question": "What changed?"}
    )
    assert answer.status_code == 200 and answer.json()["supported"] is True
    assert len(model.calls) == 2 and "repair" in json.loads(model.calls[1][1])


def test_invalid_json_gets_only_one_repair_attempt(harness):
    client, _, service, model = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]},
    ).json()
    model.invalid_json_responses = 2
    answer = client.post(
        "/api/comparisons/" + comparison["id"] + "/ask", json={"question": "What changed?"}
    )
    assert answer.status_code == 502 and answer.json()["code"] == "invalid_model_output"
    assert len(model.calls) == 2


def test_change_question_cannot_return_insufficient_context_when_diff_is_complete(harness):
    client, _, service, model = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]},
    ).json()
    model.unsupported_responses = 1
    answer = client.post(
        "/api/comparisons/" + comparison["id"] + "/ask", json={"question": "What changed?"}
    )
    assert answer.status_code == 200 and answer.json()["supported"] is True
    assert len(model.calls) == 2 and "repair" in json.loads(model.calls[1][1])


def test_unchanged_saved_comparison_answers_change_question_deterministically(harness):
    client, _, _, model = harness
    law = add_law(client)
    comparison = client.post(
        "/api/comparisons",
        json={
            "old_version_id": law["current_version_id"],
            "new_version_id": law["current_version_id"],
        },
    ).json()
    answer = client.post(
        "/api/comparisons/" + comparison["id"] + "/ask", json={"question": "What changed?"}
    )
    assert answer.status_code == 200 and answer.json()["supported"] is True
    assert "no article- or passage-level text changes" in answer.json()["answer"]
    assert answer.json()["citations"] == [] and model.calls == []


@pytest.mark.asyncio
async def test_actual_adapter_reports_no_endpoint(harness):
    _, _, service, _ = harness
    with pytest.raises(DomainError) as error:
        await ModelClient(service.settings).complete("Test", "Test")
    assert error.value.code == "model_not_configured"
