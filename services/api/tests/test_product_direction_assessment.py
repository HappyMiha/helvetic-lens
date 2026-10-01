"""Actual early choice and durable final request; fictional evidence, not quality scores."""
import json
from copy import deepcopy
from datetime import timedelta

import pytest
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_clarification import setup as early_setup
from test_product_exploration import QUESTION, start
from test_product_iterative_research import GRANT, RECIPIENT, complete
from test_product_selected_direction import choose

from helvetic_lens import decision_sources
from helvetic_lens import product_direction_assessment as assessment
from helvetic_lens.product_investigation_models import ClaimEvidence, Investigation, InvestigationSource
from helvetic_lens.product_investigations import scope

CANARY = "INVALID OPTIONAL PRIVATE CANARY"


def setup(monkeypatch, service, model, *, outcome="partial", invalid=None, callback=None):
    trace = early_setup(monkeypatch, service, model)
    trace["final_requests"] = []
    base = model.complete

    def evidence(source, role="support"):
        return {"source_id": source["id"], "quote": source["excerpts"][0]["text"],
            "locator": "p1", "role": role}

    def points(sources, status):
        source = next((s for s in sources if s["excerpts"][0]["text"] == GRANT), sources[0])
        values = [source]
        roles = ["context" if status == "not_found" else "support"]
        if status == "conflicting":
            values.append(next(s for s in sources if s["excerpts"][0]["text"] == RECIPIENT))
            roles.append("counterevidence")
        return [{"statement": s["excerpts"][0]["text"], "evidence": [evidence(s, r)]}
            for s, r in zip(values, roles)]

    async def response(system, user, **kwargs):
        data = json.loads(user)
        title = kwargs["response_schema"]["title"]
        result = json.loads(await base(system, user, **kwargs))
        if title == "ResearchPlan" and data.get("selected_direction"):
            # Actually read both sides of the fictional transaction after the choice.
            for b in result["branches"]:
                b["query"] = "chosen goal " + b["query"].removeprefix("focused recipient disclosure ")
        if title == "Reflection" and data.get("branch_assessment_question"):
            result["assessment"] = {"question_id": data["branch_assessment_question"]["question_id"],
                "status": "partial", "points": points(data["sources"], "partial"),
                "limitations": ["Other periods and independent records remain unchecked."]}
        if title != "Briefing" or not data.get("direction_assessment_target"):
            return json.dumps(result)
        trace["final_requests"].append({"input": deepcopy(data), "system": system,
            "schema": kwargs["response_schema"]})
        result["direction_assessment"] = {"selection": data["direction_assessment_target"]["selection"],
            "status": outcome, "points": points(data["sources"], outcome),
            "limitations": ["These fictional records do not establish complete coverage or user intent."]}
        result["question_renewals"] = [{"question_id": q["question_id"], "status": "partial",
            "points": points(data["sources"], "partial"), "limitations": ["Other records remain unchecked."]}
            for q in data.get("question_renewal_targets", [])]
        if not data.get("question_renewal_targets"):
            result.pop("question_renewals")
        a = result["direction_assessment"]
        if invalid == "target":
            a["selection"]["direction_index"] = 2
        elif invalid == "old_source":
            a["points"][0]["evidence"][0]["source_id"] = data["direction_assessment_target"]["earlier_context"]["source"]["id"]
        elif invalid == "quote":
            a["points"][0]["evidence"][0]["quote"] = CANARY
        elif invalid == "uncited":
            a["points"][0]["evidence"] = []
        elif invalid == "conflict":
            a["status"] = "conflicting"
        elif invalid == "shape":
            result["direction_assessment"] = CANARY
        elif invalid == "missing":
            result.pop("direction_assessment")
        elif invalid == "renewal_shape":
            assert data.get("question_renewal_targets")
            result["question_renewals"] = CANARY
        elif invalid == "both_shape":
            assert data.get("question_renewal_targets")
            result.update(direction_assessment=CANARY, question_renewals=CANARY)
        elif invalid == "base":
            result["direction_assessment"] = CANARY
            result["findings"][0]["quote"] = CANARY
        if callback:
            callback(data)
        return json.dumps(result)

    monkeypatch.setattr(model, "complete", response)
    return trace


@pytest.mark.parametrize("product", ["legal", "pharma"])
@pytest.mark.parametrize("outcome", ["possible_answer", "partial", "conflicting", "not_found"])
def test_chosen_direction_receives_current_cited_answer_in_one_final_request(signed, monkeypatch, product, outcome):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model, outcome=outcome)
    root, old, _ = start(client, product)
    early, direction, child, body = choose(client, service, root, old, index=int(outcome == "conflicting"))
    final = complete(client, service, root + "/investigations", child)
    assert final["exploration"]["status"] == "ready", final["stop_reason"]
    answer = final["exploration"]["briefing"]["assessment"]
    assert answer["contract"] == assessment.CONTRACT and answer["status"] == outcome
    assert answer["question"] == direction["question"] and "question_id" not in answer
    assert answer["selection"] == {"investigation_id": old["id"],
        "orientation_revision": body["orientation_revision"], "direction_index": body["direction"]}
    assert answer["investigation_id"] == child["id"]
    assert len(trace["final_requests"]) == 1
    request = trace["final_requests"][0]
    assert assessment.SYSTEM in request["system"]
    assert request["input"]["direction_assessment_target"]["earlier_context"]["original_question"] == QUESTION
    assert not request["input"].get("assessment_question") and not request["input"].get("selected_public_check")
    supplied = {s["id"]: s for s in request["input"]["sources"]}
    assert direction["source_id"] not in supplied
    for point in answer["points"]:
        for ref in point["evidence"]:
            assert ref["sha256"] == supplied[ref["source_id"]]["sha256"]
            assert ref["quote"] in [p["text"] for p in supplied[ref["source_id"]]["excerpts"]]
    assert any(q.startswith("chosen goal") for q in trace["queries"])
    assert client.get(root + "/investigations/" + old["id"]).json()["exploration"]["orientation"] == early["exploration"]["orientation"]
    url = root + "/investigations/" + old["id"] + "/exploration/reply"
    assert post(client, url, body).json()["id"] == child["id"]
    with service.db.session() as session:
        run = session.get(Investigation, child["id"])
        before = deepcopy(run.research_state), run.event_sequence
    assert client.get(root + "/investigations/" + child["id"]).json()["exploration"]["briefing"]["assessment"] == answer
    with service.db.session() as session:
        run = session.get(Investigation, child["id"])
        assert (run.research_state, run.event_sequence) == before
        assert run.research_state["exploration"].get("direction_assessment_context")
        assert "assessment_contract" not in run.research_state["exploration"]
    assert "direction_assessment_context" not in json.dumps(final)
    assert client.get(root + "/web-research").json()["policy"]["enabled"] is False


@pytest.mark.parametrize("invalid", ["target", "old_source", "quote", "uncited", "conflict", "shape", "missing", "renewal_shape", "both_shape"])
def test_optional_outputs_recover_independently_without_extra_requests(signed, monkeypatch, invalid):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model, invalid=invalid)
    root, old, _ = start(client)
    _, _, child, _ = choose(client, service, root, old)
    final = complete(client, service, root + "/investigations", child)
    brief = final["exploration"]["briefing"]
    assert final["exploration"]["status"] == "ready" and brief["findings"], final["stop_reason"]
    assert len(trace["final_requests"]) == 1 and CANARY not in json.dumps(final)
    if invalid != "renewal_shape":
        assert "assessment" not in brief and brief["selected_direction_assessment"] == {"status": "unavailable"}
    else:
        assert brief["assessment"]["contract"] == assessment.CONTRACT
    if invalid in {"renewal_shape", "both_shape"}:
        assert brief["question_updates"] == {"status": "unavailable"}
    else:
        assert "question_updates" not in brief
        assert trace["final_requests"][0]["input"].get("question_renewal_targets")
        assert any(q.get("stage") == "final_briefing" for q in final["exploration"]["question_assessments"]["assessments"])
    with service.db.session() as session:
        saved = session.get(Investigation, child["id"])
        assert CANARY not in json.dumps(saved.research_state)


def mutate(service, child, data, change):
    with service.db.session() as session:
        run = session.get(Investigation, child["id"])
        source = session.get(InvestigationSource, data["sources"][-1]["id"])
        state = deepcopy(run.research_state)
        if change == "source_metadata":
            source.title = "CHANGED SOURCE TITLE"
        elif change == "rights":
            source.snapshot = {**source.snapshot, "allow_discovery": False}
        elif change == "contract":
            state["exploration"].pop("direction_assessment_contract")
            run.research_state = state
        elif change == "ancestor_time":
            old = session.get(InvestigationSource, data["direction_assessment_target"]["earlier_context"]["source"]["id"])
            old.created_at += timedelta(days=1)
        elif change == "private_claim":
            claim_id = data["claims"][0]["id"]
            private = InvestigationSource(**scope(run), kind="uploaded_file", title="PRIVATE FILE", url="",
                source_key="private", sha256="private", snapshot={"excerpts": [{"text": "PRIVATE CANARY", "passage": "p1"}]})
            session.add(private)
            session.flush()
            session.add(ClaimEvidence(**scope(run), claim_id=claim_id, source_id=private.id,
                relation="CONTEXT", quote="PRIVATE CANARY", locator="p1"))
        else:
            raise AssertionError(change)
        session.commit()


@pytest.mark.parametrize("change", ["source_metadata", "rights", "contract", "ancestor_time", "private_claim"])
@pytest.mark.parametrize("when", ["during", "after"])
def test_changed_complete_inputs_cannot_be_rescued_as_optional_output(signed, monkeypatch, change, when):
    client, service, _, model = signed
    child = None
    def callback(data):
        if when == "during":
            mutate(service, child, data, change)
    trace = setup(monkeypatch, service, model, callback=callback)
    root, old, _ = start(client)
    _, _, child, _ = choose(client, service, root, old)
    final = complete(client, service, root + "/investigations", child)
    assert len(trace["final_requests"]) == 1
    if when == "after":
        assert final["exploration"]["briefing"]["assessment"]
        mutate(service, child, trace["final_requests"][0]["input"], change)
        final = client.get(root + "/investigations/" + child["id"]).json()
    else:
        assert final["status"] == "paused"
    assert final["exploration"]["briefing"] is None
    assert "PRIVATE CANARY" not in json.dumps(final["exploration"])
    if change == "private_claim":
        assert any(
            source["kind"] == "uploaded_file" and "PRIVATE CANARY" in json.dumps(source["snapshot"])
            for source in final["sources"]
        )
    assert "PRIVATE CANARY" not in json.dumps(trace["final_requests"])
    client.cookies.clear()
    assert client.get(root + "/investigations/" + child["id"]).status_code == 401


@pytest.mark.parametrize("mode", ["free_text", "legacy", "no_read", "bad_base"])
def test_legacy_no_read_and_required_output_keep_their_boundaries(signed, monkeypatch, mode):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model, invalid="base" if mode == "bad_base" else None)
    root, old, _ = start(client)
    _, _, child, _ = choose(client, service, root, old, free_text=mode == "free_text")
    if mode in {"legacy", "free_text"}:
        with service.db.session() as session:
            run = session.get(Investigation, child["id"])
            state = deepcopy(run.research_state)
            if mode == "legacy":
                state["exploration"].pop("direction_assessment_contract")
            else:
                # A saved free-text episode from before ordinary-question answers.
                state["exploration"]["direction_assessment_contract"] = assessment.CONTRACT
            run.research_state = state
            session.commit()
    if mode == "no_read":
        async def unavailable(*args, **kwargs):
            return {"status": "unavailable"}
        monkeypatch.setattr(decision_sources, "safe_inspect", unavailable)
    final = complete(client, service, root + "/investigations", child)
    if mode in {"free_text", "legacy"}:
        assert final["exploration"]["status"] == "ready" and not trace["final_requests"]
        assert "assessment" not in final["exploration"]["briefing"]
        assert "selected_direction_assessment" not in final["exploration"]["briefing"]
    else:
        assert final["exploration"]["briefing"] is None
        assert final["exploration"]["status"] == ("no_evidence" if mode == "no_read" else "unavailable")
        assert len(trace["final_requests"]) == int(mode == "bad_base")
        assert CANARY not in json.dumps(final)
