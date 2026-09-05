import json
import time

import pytest
from conftest import LAW_URL, add_law, import_old, policy, run_scan

from helvetic_lens.analysis import (
    Answer,
    AnswerDigest,
    Impact,
    ModelClient,
    answer_question,
    batch_diff_evidence,
    build_impact_plan,
    classify_question_intent,
    diff_evidence,
    finalize_impact_report,
    impact_analysis,
    local_answer_synthesis,
    local_impact_synthesis,
    localized_cited_change_answer,
    materialize_digest_citations,
    no_change_answer,
    numbered_selection,
    parse_response,
    planned_diff_evidence,
    select_evidence,
    structured_completion,
    targeted_version_evidence,
)
from helvetic_lens.config import DomainError
from helvetic_lens.diffing import DIFF_SCHEMA_VERSION, compare_passages
from helvetic_lens.models import Comparison, Profile, Version


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
    report = result["result"]
    assert report["schema_version"] == "impact-report-v3"
    assert report["headline"] and report["materiality"] == report["impact"]
    assert report["material_changes"][0]["old_unit"]["passage_id"]
    assert report["material_changes"][0]["new_unit"]["passage_id"]
    assert report["material_changes"][0]["evidence_grade"] in {
        "confirmed",
        "needs_review",
    }
    assert {item["status"] for item in report["important_dates"]} == {"not_found"}
    assert len({action["action_key"] for action in report["actions"]}) == len(report["actions"])
    assert result["provenance"]["backend"] == "custom"
    assert result["provenance"]["generation"]["max_tokens"] == service.settings.apertus_max_tokens
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
    service.settings.apertus_temperature += 0.1
    assert client.post(route).json()["cached"] is False
    assert len(model.calls) == previous_calls + 2


def test_review_action_decisions_are_append_only_and_scoped_to_saved_report(harness):
    client, _, service, _ = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]},
    ).json()
    report = client.post(f"/api/comparisons/{comparison['id']}/analyse").json()
    analysis_id = report["id"]
    action_key = report["result"]["actions"][0]["action_key"]
    route = (
        f"/api/comparisons/{comparison['id']}/analyses/{analysis_id}"
        f"/actions/{action_key}/decisions"
    )

    accepted = client.post(route, json={"decision": "accepted"})
    assert accepted.status_code == 200
    assert accepted.json()["current"][action_key]["decision"] == "accepted"
    assigned = client.post(
        route,
        json={"decision": "assigned", "assigned_to": "Legal operations"},
    )
    assert assigned.status_code == 200
    assert assigned.json()["current"][action_key]["assigned_to"] == "Legal operations"
    scheduled = client.post(
        route,
        json={"decision": "scheduled", "scheduled_for": "2027-02-01T09:00:00+01:00"},
    )
    assert scheduled.status_code == 200
    assert len(scheduled.json()["history"]) == 3
    rejected = client.post(route, json={"decision": "not_applicable"})
    assert rejected.status_code == 422 and rejected.json()["code"] == "rationale_required"
    dismissed = client.post(
        route,
        json={"decision": "not_applicable", "rationale": "No covered activity in this workspace."},
    )
    assert dismissed.status_code == 200
    current = client.get(f"/api/comparisons/{comparison['id']}").json()["analysis"]
    assert current["action_decisions"]["current"][action_key]["decision"] == "not_applicable"
    assert len(current["action_decisions"]["history"]) == 4
    assert current["result"]["actions"][0]["action_key"] == action_key


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


def test_local_docker_finishes_with_validated_batch_results_without_synthesis_call(harness):
    client, _, service, model = harness
    service.settings.apertus_provider = "docker"
    service.settings.apertus_base_url = "http://127.0.0.1:12435/v1"
    model.settings = service.settings
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]},
    ).json()

    model.calls.clear()
    impact = client.post(f"/api/comparisons/{comparison['id']}/analyse").json()
    impact_tasks = [json.loads(user).get("task") for _, user in model.calls]
    assert impact["status"] == "succeeded"
    assert impact_tasks == ["impact_batch"]
    assert impact["result"]["citations"][0]["url"].startswith("/evidence/")

    model.calls.clear()
    answer = client.post(
        f"/api/comparisons/{comparison['id']}/ask",
        json={"question": "Що змінилося?"},
    ).json()
    answer_tasks = [json.loads(user).get("task") for _, user in model.calls]
    assert answer["supported"] is True
    # The selected product locale is en-CH, so the matching validated impact report is reused.
    assert answer_tasks == []
    assert answer["citations"][0]["url"].startswith("/evidence/")


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
    first_answer = reply.json()
    prior_question = {
        "question": "What changed?",
        "answer": first_answer["answer"],
        "citations": first_answer["citations"],
    }
    older_reply = client.post(
        route, json={"question": "What did the older version say?", "history": [prior_question]}
    )
    assert older_reply.status_code == 200
    assert older_reply.json()["context_mode"] == "full_saved_versions"
    model_input = json.loads(model.calls[-1][1])
    assert model_input["previous_questions"] == [prior_question]
    assert {p["version_id"] for p in model_input["evidence"]} == {old["id"], law["current_version_id"]}
    assert len(model_input["evidence"]) == 6
    assert model_input["coverage"]["complete"] is True
    assert model_input["coverage"]["limited"] is False
    assert model_input["document_context"]["complete"] is True
    assert model_input["document_context"]["kind"] == "complete_saved_version_text"
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


def test_validated_json_object_survives_schema_echo_and_trailing_noise_without_a_repair():
    evidence = [
        {"version_id": "new", "passage_id": "p1", "text": "Retention is 60 days.", "page": 3}
    ]
    raw = json.dumps(
        {
            "supported": True,
            "answer": "The period is 60 days.",
            "citations": [
                {"version_id": "new", "passage_id": "p1", "quote": "Retention is 60 days."}
            ],
        }
    )
    result = parse_response(
        json.dumps(Answer.model_json_schema()) + "\n" + raw + "}\nExplanation omitted.",
        Answer,
        evidence,
    )
    assert result["supported"] is True
    assert result["citations"][0]["url"] == "/evidence/new?passage=p1"


def test_validated_json_object_is_found_inside_provider_wrappers_and_encoded_strings():
    evidence = [
        {"version_id": "new", "passage_id": "p1", "text": "Retention is 60 days.", "page": 3}
    ]
    answer = {
        "supported": True,
        "answer": "The period is 60 days.",
        "citations": [
            {"version_id": "new", "passage_id": "p1", "quote": "Retention is 60 days."}
        ],
    }
    wrapped = json.dumps({"answerResult": json.dumps(answer)})
    result = parse_response(wrapped, Answer, evidence)
    assert result["answer"] == "The period is 60 days."
    assert result["citations"][0]["url"] == "/evidence/new?passage=p1"


def test_impact_overflow_is_clamped_before_retained_citations_are_validated():
    evidence = [
        {"version_id": "new", "passage_id": "p1", "text": "Retention is 60 days.", "page": 3}
    ]
    citation = {"version_id": "new", "passage_id": "p1", "quote": "Retention is 60 days."}
    raw = json.dumps(
        {
            "summary": "The retention rule changed.",
            "impact": "medium",
            "reason": "The operating procedure may need review.",
            "business_areas": [f"Area {index}" for index in range(15)],
            "actions": [
                {"text": f"Review action {index}.", "citations": [citation]}
                for index in range(7)
            ],
            "citations": [citation] * 12,
        }
    )
    result = parse_response(raw, Impact, evidence)
    assert len(result["actions"]) == 5
    assert len(result["business_areas"]) == 12
    assert len(result["citations"]) == 10
    assert all(action["citations"][0]["url"] == "/evidence/new?passage=p1" for action in result["actions"])


def test_batch_digest_text_and_citations_are_bounded_before_validation():
    evidence = [
        {
            "version_id": "new",
            "passage_id": f"p{index}",
            "position": index,
            "text": f"Changed passage {index}.",
            "page": 1,
        }
        for index in range(1, 31)
    ]
    result = parse_response(
        json.dumps(
            {
                "supported": True,
                "answer": "A" * 1364,
                "citation_rows": list(range(1, 31)),
            }
        ),
        AnswerDigest,
        evidence,
        validate_citations=False,
        numeric_reference_count=len(evidence),
        numeric_reference_evidence=evidence,
    )
    assert len(result["answer"]) == 1000
    assert result["citation_rows"] == list(range(1, 11))


def test_compact_batch_side_alias_is_resolved_to_the_exact_saved_version():
    evidence = [
        {
            "version_id": "saved-old-version",
            "passage_id": "p1",
            "side": "old",
            "text": "The earlier requirement was removed.",
            "page": 2,
        }
    ]
    raw = json.dumps(
        {
            "supported": True,
            "answer": "The requirement was removed.",
            "citations": [
                {
                    "version_id": "old",
                    "passage_id": "p1",
                    "quote": "The earlier requirement was removed.",
                }
            ],
        }
    )
    result = parse_response(raw, Answer, evidence)
    assert result["citations"][0]["version_id"] == "saved-old-version"
    assert result["citations"][0]["url"] == "/evidence/saved-old-version?passage=p1"


def test_numeric_model_references_are_range_checked_and_materialized_by_the_server():
    evidence = [
        {
            "version_id": "saved-old-version",
            "passage_id": "old-1",
            "text": "The earlier requirement was removed.",
            "page": 2,
        },
        {
            "version_id": "saved-new-version",
            "passage_id": "new-1",
            "text": "A replacement requirement was added.",
            "page": 3,
        },
    ]
    digest = AnswerDigest.model_validate(
        {
            "supported": True,
            "answer": "A replacement requirement was added.",
            "citation_rows": [2, *range(1, 55), 999, 2],
        }
    ).model_dump()
    result = materialize_digest_citations(
        digest,
        evidence,
    )
    assert result["citations"] == [
        {
            "version_id": "saved-new-version",
            "passage_id": "new-1",
            "quote": "A replacement requirement was added.",
            "url": "/evidence/saved-new-version?passage=new-1",
            "page": 3,
        },
        {
            "version_id": "saved-old-version",
            "passage_id": "old-1",
            "quote": "The earlier requirement was removed.",
            "url": "/evidence/saved-old-version?passage=old-1",
            "page": 2,
        },
    ]
    with pytest.raises(DomainError) as error:
        numbered_selection([999], result["citations"], 10, required=True)
    assert error.value.code == "invalid_citation"


def test_numeric_citations_accept_explicit_rows_and_legacy_passage_positions():
    evidence = [
        {
            "version_id": "saved-old-version",
            "passage_id": "p01126",
            "position": 1126,
            "text": "The earlier requirement applied.",
            "page": 28,
        },
        {
            "version_id": "saved-new-version",
            "passage_id": "p01127",
            "position": 1127,
            "text": "The replacement requirement applies.",
            "page": 29,
        },
    ]
    result = parse_response(
        json.dumps(
            {
                "supported": True,
                "answer": "The requirement changed.",
                # Some providers copy the visible passage position instead of the batch row.
                "citation_rows": [1126, 1127],
            }
        ),
        AnswerDigest,
        evidence,
        validate_citations=False,
        numeric_reference_count=len(evidence),
        numeric_reference_evidence=evidence,
    )
    assert result["citation_rows"] == [1, 2]


@pytest.mark.asyncio
async def test_out_of_range_numeric_citation_gets_one_repair_attempt():
    class NumericRepairModel:
        def __init__(self):
            self.calls = 0
            self.response_schemas = []

        async def complete(self, system, user, **kwargs):
            self.calls += 1
            self.response_schemas.append(kwargs.get("response_schema"))
            return json.dumps(
                {
                    "supported": True,
                    "answer": "The requirement changed.",
                    "citation_rows": [999 if self.calls == 1 else 1],
                }
            )

    model = NumericRepairModel()
    result = await structured_completion(
        model,
        "Return the requested JSON.",
        {"evidence": [["saved passage"]]},
        AnswerDigest,
        [],
        require_supported=True,
        validate_citations=False,
        numeric_reference_count=1,
    )
    assert result["citation_rows"] == [1]
    assert model.calls == 2
    assert all(
        response_schema["properties"]["citation_rows"]["items"]["maximum"] == 1
        for response_schema in model.response_schemas
    )
    assert all(
        response_schema["properties"]["citation_rows"]["maxItems"] == 1
        for response_schema in model.response_schemas
    )
def test_local_synthesis_uses_only_validated_batch_text_and_citations():
    citation = {
        "version_id": "version-1",
        "passage_id": "p00001",
        "quote": "Records must be retained for 60 days.",
    }
    reviews = [
        {
            "batch_index": 1,
            "summary": "The retention period increased.",
            "impact": "medium",
            "reason": "The operating schedule may need review.",
            "business_areas": ["Legal", "IT"],
            "citations": [citation],
        },
        {
            "batch_index": 2,
            "summary": "A new reporting duty was added.",
            "impact": "high",
            "reason": "A new filing workflow may be required.",
            "business_areas": ["Legal", "Operations"],
            "citations": [{**citation, "passage_id": "p00002"}],
        },
    ]
    impact = local_impact_synthesis(reviews)
    answer = local_answer_synthesis(
        [
            {"answer": review["summary"], "citations": review["citations"]}
            for review in reviews
        ]
    )
    assert impact["impact"] == "high" and impact["actions"] == []
    assert impact["citations"][0]["url"].startswith("/evidence/version-1")
    assert "reporting duty" in answer["answer"]
    assert answer["supported"] is True and len(answer["citations"]) == 2


def test_impact_report_merges_duplicate_actions_and_combines_exact_changes():
    old = Version(
        id="old",
        origin="uploaded",
        synthetic=True,
        passages=[
            {"id": "p1", "text": "Art. 1 Retain records for 30 days.", "page": 1},
            {"id": "p2", "text": "Art. 2 Notify within 10 days.", "page": 2},
        ],
    )
    new = Version(
        id="new",
        origin="live",
        synthetic=True,
        passages=[
            {"id": "p1", "text": "Art. 1 Retain records for 60 days.", "page": 1},
            {"id": "p2", "text": "Art. 2 Notify within 5 days.", "page": 2},
        ],
    )
    comparison = Comparison(
        id="comparison",
        mode="saved_versions",
        diff=compare_passages(old.passages, new.passages),
    )
    evidence, _, coverage = diff_evidence(old, new, comparison)
    citations = [
        {
            "version_id": row["version_id"],
            "passage_id": row["passage_id"],
            "quote": row["text"],
            "url": f"/evidence/{row['version_id']}?passage={row['passage_id']}",
            "page": row["page"],
        }
        for row in evidence
        if row["side"] == "new"
    ]
    result = {
        "summary": "Two deadlines changed.",
        "impact": "high",
        "reason": "Operating timelines may need review.",
        "business_areas": ["Operations"],
        "actions": [
            {"text": "Review the operating timetable.", "citations": [citation]}
            for citation in citations
        ],
        "citations": citations,
    }

    report = finalize_impact_report(result, comparison, evidence, coverage)

    assert len(report["material_changes"]) == 2
    assert len(report["actions"]) == 1
    assert len(report["actions"][0]["related_change_ids"]) == 2
    assert len(report["actions"][0]["citations"]) == 2
    assert report["actions"][0]["due_basis"] == "not_found"
    assert report["actions"][0]["due_date"] is None
    assert report["actions"][0]["review_suggestion"] is True
    assert report["organization_applicability"]["evidence_grade"] == "possible"
    assert report["evidence_grade"] in {"supported", "needs_review"}


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
    assert diff["granularity"] == "legal_unit"
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


def test_1406_changed_passages_are_partitioned_without_omission_or_truncation():
    old = Version(
        id="old",
        origin="live",
        synthetic=False,
        passages=[
            {"id": f"p{index:05d}", "text": f"Repealed provision {index}.", "page": index // 40 + 1}
            for index in range(1406)
        ],
    )
    new = Version(id="new", origin="live", synthetic=False, passages=[])
    comparison = Comparison(diff=compare_passages(old.passages, new.passages))
    evidence, deterministic_diff, _ = diff_evidence(old, new, comparison)
    batches = batch_diff_evidence(evidence, deterministic_diff, 24000)
    assert all(batch["model_evidence"]["columns"][0] == "row_number" for batch in batches)
    assert all(
        [row[0] for row in batch["model_evidence"]["rows"]]
        == list(range(1, len(batch["model_evidence"]["rows"]) + 1))
        for batch in batches
    )
    processed = [
        (passage["version_id"], passage["passage_id"])
        for batch in batches
        for passage in batch["evidence"]
    ]
    assert len(batches) > 1 and len(processed) == 1406
    assert len(processed) == len(set(processed))
    assert max(batch["estimated_input_characters"] for batch in batches) <= 24000


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


def test_complete_versions_require_serialized_prompt_and_output_reservation_to_fit():
    old = Version(
        id="fit-old",
        origin="uploaded",
        synthetic=True,
        passages=[{"id": "p1", "text": "Retention obligation was 30 days. " * 8, "page": 1}],
    )
    new = Version(
        id="fit-new",
        origin="live",
        synthetic=True,
        passages=[{"id": "p1", "text": "Retention obligation is 60 days. " * 8, "page": 1}],
    )

    evidence, _, coverage, mode = targeted_version_evidence(
        old,
        new,
        "What is the retention obligation?",
        2600,
        system_prompt="Follow the evidence. " * 20,
        request_fields={"question": "What is the retention obligation?"},
        reserved_output_tokens=500,
    )

    assert mode == "targeted_passages"
    assert evidence
    assert coverage["serialized_request_characters"] + coverage[
        "reserved_output_characters"
    ] + 512 > 2600
    assert coverage["limited"] is True


@pytest.mark.asyncio
async def test_large_diff_uses_a_bounded_ai_dossier_for_ask_and_impact(harness):
    _, _, service, model = harness
    settings = service.settings.model_copy(
        update={
            "apertus_base_url": "https://model.example/v1",
            "apertus_context_chars": 2000,
        }
    )
    old = Version(
        id="large-old",
        origin="uploaded",
        synthetic=True,
        passages=[
            {
                "id": f"old-{index:04d}",
                "text": (
                    f"Article {index}. Records must be retained for 30 days. "
                    "The operations team documents every review decision."
                ),
                "page": index + 1,
            }
            for index in range(80)
        ],
    )
    new = Version(
        id="large-new",
        origin="live",
        synthetic=True,
        passages=[
            {
                "id": f"new-{index:04d}",
                "text": (
                    f"Article {index}. Records must be retained for 60 days. "
                    "The data protection lead documents every review decision."
                ),
                "page": index + 1,
            }
            for index in range(80)
        ],
    )
    comparison = Comparison(
        id="large-comparison",
        mode="saved_versions",
        diff=compare_passages(old.passages, new.passages),
    )
    profile = Profile(
        id="default",
        name="Test company",
        description="Synthetic test profile",
        business_areas=["Operations"],
        revision=1,
    )
    complete_evidence, _, _ = diff_evidence(old, new, comparison)
    expected_references = {
        (passage["version_id"], passage["passage_id"]) for passage in complete_evidence
    }

    def supplied_references(payload):
        supplied = payload["evidence"]
        columns = supplied["columns"]
        side_index, passage_index = columns.index("side"), columns.index("passage_id")
        return [
            (supplied["version_ids"][row[side_index]], row[passage_index])
            for row in supplied["rows"]
        ]

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
    answer_payloads = [json.loads(call[1]) for call in model.calls]
    answer_batches = [payload for payload in answer_payloads if payload.get("task") == "answer_batch"]
    processed_answer_references = {
        (passage["version_id"], passage["passage_id"])
        for passage in answer_payloads[0]["evidence"]
    }
    assert answer["supported"] is True and answer["coverage"]["complete"] is False
    assert answer["coverage"]["batch_count"] == 1
    assert len(processed_answer_references) == len(set(processed_answer_references))
    assert set(processed_answer_references) < expected_references
    assert answer["coverage"]["limited"] is True
    assert answer["coverage"]["provider_calls"] <= 3
    assert answer_batches == []

    model.calls.clear()
    result, coverage = await impact_analysis(model, settings, comparison, old, new, profile)
    impact_payloads = [json.loads(call[1]) for call in model.calls]
    impact_batches = [payload for payload in impact_payloads if payload.get("task") == "impact_batch"]
    processed_impact_references = [
        reference for payload in impact_batches for reference in supplied_references(payload)
    ]
    assert result["impact"] == "medium" and coverage["complete"] is False
    assert coverage["batch_count"] == len(impact_batches) > 1
    assert len(processed_impact_references) == len(set(processed_impact_references))
    assert set(processed_impact_references) < expected_references
    assert coverage["limited"] is True
    assert coverage["provider_calls"] <= 5
    assert impact_payloads[-1]["task"] == "impact_synthesis"
    assert all(
        set(citation) == {"version_id", "passage_id", "quote"}
        for batch in impact_payloads[-1]["batch_reviews"]
        for citation in batch["citations"]
    )

    plan, _ = build_impact_plan(settings, comparison, old, new, profile)
    assert plan["state"] == "planned"
    assert plan["limits"]["provider_call_budget"] == 5
    assert plan["estimates"]["planned_generation_calls"] <= 4
    assert plan["execution"]["profile_revision"] == profile.revision
    assert plan["coverage"]["limited"] is True
    assert plan["shared_general_change"]["fingerprint"]
    assert "material or uncertain legal units" in plan["shared_general_change"]["summary"]


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
        "/api/comparisons/" + comparison["id"] + "/ask",
        json={"question": "Explain Article 2"},
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


def test_no_change_answer_distinguishes_german_and_italian():
    assert no_change_answer("Was ist die Differenz?").startswith("Der vollständige Vergleich")
    assert no_change_answer("Quali sono le differenze?").startswith("Il confronto completo")


def test_small_local_model_change_evidence_is_rendered_in_the_selected_language():
    citations = [
        {"version_id": "old", "quote": "Die Frist beträgt 30 Tage."},
        {"version_id": "new", "quote": "Die Frist beträgt 60 Tage."},
    ]

    assert localized_cited_change_answer(citations, "old", "new", "de-CH", "fallback").startswith(
        "Früherer gespeicherter Wortlaut"
    )
    assert localized_cited_change_answer(citations, "old", "new", "fr-CH", "fallback").startswith(
        "Texte antérieur enregistré"
    )
    assert localized_cited_change_answer(citations, "old", "new", "it-CH", "fallback").startswith(
        "Testo precedente salvato"
    )
    assert localized_cited_change_answer(citations, "old", "new", "rm-CH", "fallback").startswith(
        "Text precedent memorisà"
    )
    assert localized_cited_change_answer(citations, "old", "new", "en-CH", "fallback").startswith(
        "Earlier saved wording"
    )


def test_oversized_single_change_uses_exact_bounded_windows():
    common = "Stable legal wording " * 500
    old = Version(
        id="window-old",
        origin="uploaded",
        synthetic=False,
        passages=[{"id": "old-1", "text": common + "30 days", "page": 1}],
    )
    new = Version(
        id="window-new",
        origin="live",
        synthetic=False,
        passages=[{"id": "new-1", "text": common + "60 days", "page": 1}],
    )
    comparison = Comparison(
        id="window-comparison",
        mode="saved_versions",
        diff=compare_passages(old.passages, new.passages),
    )

    _, dossier, coverage, batches = planned_diff_evidence(
        old, new, comparison, max_chars=3000, max_batches=1
    )

    assert len(batches) == 1
    assert batches[0]["estimated_input_characters"] <= 3000
    assert batches[0]["excerpted_passages"] == 2
    assert coverage["limited"] is True and coverage["complete"] is False
    assert dossier["audit_complete"] is True and dossier["complete"] is False


@pytest.mark.asyncio
async def test_formatting_only_plan_and_impact_use_zero_model_calls(harness):
    _, _, service, model = harness
    settings = service.settings.model_copy(
        update={"apertus_base_url": "https://model.example/v1"}
    )
    old = Version(
        id="format-old",
        origin="uploaded",
        synthetic=True,
        passages=[{"id": "p1", "text": "word-\nwrapped text", "page": 1}],
    )
    new = Version(
        id="format-new",
        origin="live",
        synthetic=True,
        passages=[{"id": "p1", "text": "wordwrapped text", "page": 1}],
    )
    comparison = Comparison(
        id="format-comparison",
        mode="saved_versions",
        diff=compare_passages(old.passages, new.passages),
    )
    profile = Profile(
        id="default",
        name="Test company",
        description="Synthetic test profile",
        business_areas=["Operations"],
        revision=1,
    )

    plan, prepared = build_impact_plan(settings, comparison, old, new, profile)
    result, coverage = await impact_analysis(
        model, settings, comparison, old, new, profile, prepared=prepared
    )

    assert plan["estimates"]["planned_generation_calls"] == 0
    assert plan["execution"]["strategy"] == "deterministic_no_substantive_change"
    assert result["impact"] == "low" and result["actions"] == []
    assert coverage["provider_calls"] == 0 and model.calls == []


@pytest.mark.asyncio
async def test_actual_adapter_reports_no_endpoint(harness):
    _, _, service, _ = harness
    with pytest.raises(DomainError) as error:
        await ModelClient(service.settings).complete("Test", "Test")
    assert error.value.code == "model_not_configured"


def test_vague_comment_and_numeric_gibberish_do_not_call_the_model(harness):
    client, _, _, model = harness
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]},
    ).json()
    route = f"/api/comparisons/{comparison['id']}/ask"
    model.calls.clear()

    started = time.perf_counter()
    vague = client.post(route, json={"question": "Ничего не понятно но очень интересно"})
    vague_elapsed = time.perf_counter() - started
    numeric = client.post(route, json={"question": "111"})
    off_topic = client.post(route, json={"question": "Tell me a joke about the weather"})

    assert vague.status_code == numeric.status_code == off_topic.status_code == 200
    assert vague.json()["context_mode"] == numeric.json()["context_mode"] == "clarification"
    assert vague.json()["coverage"]["provider_calls"] == 0
    assert vague_elapsed < 1
    assert len(vague.json()["suggestions"]) == 4
    assert off_topic.json()["intent"] == off_topic.json()["context_mode"] == "off_topic"
    assert off_topic.json()["supported"] is False
    assert off_topic.json()["coverage"]["provider_calls"] == 0
    assert model.calls == []


@pytest.mark.parametrize(
    ("question", "intent"),
    [
        ("What changed in this document?", "explain_changes"),
        ("Was hat sich inhaltlich in den Fassungen geändert?", "explain_changes"),
        ("Quale modifica sostanziale esiste tra queste versioni?", "explain_changes"),
        ("Does this affect our organization?", "organization_impact"),
        ("Create a review checklist", "actions"),
        ("Explain Article 5", "specific_unit"),
        ("Summarize the whole document", "whole_document"),
        ("Ничего не понятно но очень интересно", "vague"),
        ("Tell me a joke about the weather", "off_topic"),
    ],
)
def test_question_router_uses_no_document_body_or_model(question, intent):
    route = classify_question_intent(question)

    assert route["intent"] == intent
    assert route["document_characters_seen"] == 0
    assert route["provider_calls"] == 0


def test_canonical_ask_reuses_current_validated_impact_report(harness):
    client, _, service, model = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]},
    ).json()
    impact = client.post(f"/api/comparisons/{comparison['id']}/analyse").json()
    calls_after_impact = len(model.calls)

    answer = client.post(
        f"/api/comparisons/{comparison['id']}/ask",
        json={"question": "Explain the material changes simply"},
    ).json()

    assert answer["intent"] == "explain_changes"
    assert answer["context_mode"] == "impact_report"
    assert answer["reused_impact_report_id"] == impact["id"]
    assert answer["coverage"]["provider_calls"] == 0
    assert answer["citations"] and answer["selected_change_ids"]
    assert answer["analysis_plan"]["router"]["document_characters_seen"] == 0
    assert answer["analysis_plan"]["limits"]["router_call_budget"] == 0
    assert len(model.calls) == calls_after_impact
    saved = client.get(f"/api/comparisons/{comparison['id']}/ai-history").json()
    saved_answer = next(item for item in saved["items"] if item["type"] == "question")
    assert saved_answer["result"]["intent"] == "explain_changes"
    assert saved_answer["result"]["output_locale"] == "en-CH"
    assert saved_answer["result"]["selected_change_ids"]


def test_specific_unit_ask_uses_only_target_and_neighbours(harness):
    client, _, service, model = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]},
    ).json()
    model.calls.clear()

    answer = client.post(
        f"/api/comparisons/{comparison['id']}/ask",
        json={"question": "Explain Article 2"},
    ).json()

    assert answer["intent"] == "specific_unit"
    assert answer["context_mode"] == "targeted_passages"
    assert answer["coverage"]["limited"] is True
    assert "neighbours" in answer["scope"]
    supplied = json.loads(model.calls[0][1])
    assert supplied["intent"] == "specific_unit"
    assert supplied["output_locale"] == "en-CH"
