import json

import pytest
from conftest import LAW_URL, add_law, import_old, policy, run_scan

from regwatch.analysis import Answer, ModelClient, parse_response, select_evidence
from regwatch.config import DomainError
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


def test_context_is_bounded_and_reports_truncated_scope():
    old = Version(
        id="old",
        origin="uploaded",
        synthetic=True,
        passages=[
            {"id": "p1", "text": "Earlier wording " * 500, "page": 1},
        ],
    )
    new = Version(
        id="new",
        origin="live",
        synthetic=True,
        passages=[
            {"id": "p1", "text": "Current wording " * 500, "page": 1},
            {"id": "p2", "text": "Other section " * 500, "page": 2},
        ],
    )
    comparison = Comparison(
        diff={"items": [{"kind": "modified", "old": old.passages[0], "new": new.passages[0]}]}
    )
    evidence, coverage = select_evidence(old, new, comparison, 1000, "Earlier wording")
    assert sum(len(p["text"]) for p in evidence) <= 1000
    assert coverage["limited"] is True and coverage["available_passages"] == 3
    assert evidence[0]["version_id"] == "old"
    assert evidence[0]["synthetic"] is True


@pytest.mark.asyncio
async def test_actual_adapter_reports_no_endpoint(harness):
    _, _, service, _ = harness
    with pytest.raises(DomainError) as error:
        await ModelClient(service.settings).complete("Test", "Test")
    assert error.value.code == "model_not_configured"
