"""A real selected answer, optional next check and explicit durable continuation."""
import json
from copy import deepcopy
from uuid import uuid4

import pytest
from test_product_direction_assessment import mutate as mutate_shared
from test_product_direction_assessment import setup as direction_setup
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_exploration import start
from test_product_investigations import tick
from test_product_iterative_research import complete
from test_product_saved_check import command, url
from test_product_selected_direction import choose

from helvetic_lens import product_direction_assessment as direction
from helvetic_lens.product_investigation_models import Investigation

LIMIT = "Independent recipient records for other reporting periods remain unchecked."
CANARY = "INVALID OPTIONAL PRIVATE NEXT CHECK"


def setup(monkeypatch, service, model, *, mode="current", invalid=None, callback=None):
    trace = direction_setup(monkeypatch, service, model)
    trace["choices"] = []
    base = model.complete

    def proposal(data, question_id, prefix):
        source = data["sources"][-1]
        return {"source_id": source["id"], "quote": source["excerpts"][0]["text"],
            "locator": "p1", "query": f"River Trust independent recipient disclosure {prefix} {question_id}",
            "purpose": "Check independent recipient records for other reporting periods."}

    async def response(system, user, **kwargs):
        data = json.loads(user)
        result = json.loads(await base(system, user, **kwargs))
        if kwargs["response_schema"]["title"] == "Reflection" and result.get("assessment"):
            result["assessment"]["further_check"] = proposal(data, result["assessment"]["question_id"], "saved")
        if "next_check_candidates" not in data:
            return json.dumps(result)
        candidates = data["next_check_candidates"]["items"]
        assert 0 < len(candidates) <= 6
        assert direction.NEXT_CHECK_SYSTEM in system
        options = [c for c in candidates if c["may_renew"]] if mode == "renewed" else [c for c in candidates if c["current_check"]]
        assert options, candidates
        selected = options[-1]
        if mode == "renewed":
            renewal = next(q for q in result["question_renewals"] if q["question_id"] == selected["question_id"])
            renewal["further_check"] = proposal(data, selected["question_id"], "renewed")
            query = renewal["further_check"]["query"]
        else:
            result["question_renewals"] = []
            query = selected["current_check"]["query"]
        result["direction_assessment"]["limitations"] = ["Only the retained public passages were read.", LIMIT]
        result["next_check_choice"] = {"question_id": selected["question_id"], "query": query, "limitation_index": 1}
        trace["choices"].append({"selected": deepcopy(selected), "query": query, "input": deepcopy(data)})
        if invalid == "missing":
            result.pop("next_check_choice")
        elif invalid in {"shape", "both_shape"}:
            result["next_check_choice"] = CANARY
        elif invalid == "id":
            result["next_check_choice"]["question_id"] = str(uuid4())
        elif invalid == "query":
            result["next_check_choice"]["query"] = "Unproposed unrelated replacement query"
        elif invalid == "index":
            result["next_check_choice"]["limitation_index"] = 3
        elif invalid == "bool_index":
            result["next_check_choice"]["limitation_index"] = True
        elif invalid == "answered":
            result["direction_assessment"]["status"] = "possible_answer"
        elif invalid == "bad_answer":
            result["direction_assessment"] = CANARY
        elif invalid == "no_proposal":
            renewal.pop("further_check")
        if invalid in {"bad_renewal", "both_shape"}:
            result["question_renewals"] = CANARY
        if callback:
            callback(data)
        return json.dumps(result)

    monkeypatch.setattr(model, "complete", response)
    return trace


def episode(signed, monkeypatch, *, product="legal", mode="current", invalid=None, callback=None, legacy=False, free_text=False):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model, mode=mode, invalid=invalid, callback=callback)
    root, old, _ = start(client, product)
    _, _, child, _ = choose(client, service, root, old, free_text=free_text)
    if legacy or free_text:
        with service.db.session() as session:
            run = session.get(Investigation, child["id"])
            state = deepcopy(run.research_state)
            if legacy:
                state["exploration"].pop("next_check_contract")
            if free_text:
                # Keep this older-context fixture at its original generation.
                state["exploration"]["direction_assessment_contract"] = direction.CONTRACT
            run.research_state = state
            session.commit()
    final = complete(client, service, root + "/investigations", child)
    return root, final, trace


@pytest.mark.parametrize("product", ["legal", "pharma"])
@pytest.mark.parametrize("mode", ["current", "renewed"])
def test_answer_links_existing_check_and_exact_user_choice_reaches_search(signed, monkeypatch, product, mode):
    client, service, _, _ = signed
    root, final, trace = episode(signed, monkeypatch, product=product, mode=mode)
    assert final["exploration"]["status"] == "ready", final["stop_reason"]
    assert len(trace["choices"]) == len(trace["final_requests"]) == 1
    chosen = trace["choices"][0]
    check = final["exploration"]["next_check"]
    assert check["question_id"] == chosen["selected"]["question_id"]
    assert check["answer_link"] == {"contract": direction.NEXT_CHECK_CONTRACT,
        "question": final["question"], "limitation_index": 1, "limitation": LIMIT}
    if mode == "renewed":
        assert len(chosen["input"]["next_check_candidates"]["items"]) >= 2
        assert check["question_id"] != chosen["input"]["next_check_candidates"]["items"][0]["question_id"]
    assert chosen["query"] not in trace["queries"]
    assert "next_check_receipt" not in json.dumps(final)
    assert "next_check_choice" not in json.dumps(final)
    with service.db.session() as session:
        run = session.get(Investigation, final["id"])
        before = deepcopy(run.research_state), run.revision, run.event_sequence
    assert client.get(root + "/investigations/" + final["id"]).json()["exploration"]["next_check"] == check
    with service.db.session() as session:
        run = session.get(Investigation, final["id"])
        assert (run.research_state, run.revision, run.event_sequence) == before
    body = command(final)
    response = post(client, url(root, final), body)
    assert response.status_code == 202, response.text
    child = response.json()
    assert post(client, url(root, final), body).json()["id"] == child["id"]
    for _ in range(6):
        if chosen["query"] in trace["queries"]:
            break
        tick(service, child["id"])
    assert trace["queries"].count(chosen["query"]) == 1
    assert child["exploration"]["continuation"]["question_id"] == check["question_id"]
    old = client.get(root + "/investigations/" + final["id"]).json()
    assert old["exploration"]["briefing"] == final["exploration"]["briefing"]
    assert old["exploration"]["next_check"] is None
    assert client.get(root + "/investigations").json()["total"] == 3
    assert not client.get(root + "/web-research").json()["policy"]["enabled"]


@pytest.mark.parametrize("invalid", ["missing", "shape", "id", "query", "index", "bool_index", "answered", "bad_answer", "bad_renewal", "both_shape", "no_proposal"])
def test_invalid_optional_link_preserves_independent_answer_and_renewals(signed, monkeypatch, invalid):
    mode = "renewed" if invalid in {"shape", "bad_answer", "no_proposal"} else "current"
    root, final, trace = episode(signed, monkeypatch, mode=mode, invalid=invalid)
    brief = final["exploration"]["briefing"]
    assert brief and brief["findings"] and final["exploration"]["status"] == "ready", final["stop_reason"]
    assert len(trace["final_requests"]) == 1
    assert CANARY not in json.dumps(final)
    check = final["exploration"]["next_check"]
    if invalid == "bad_renewal":
        assert check["answer_link"]["limitation"] == LIMIT
        assert brief["question_updates"]["status"] == "unavailable"
    else:
        assert not check or "answer_link" not in check
    if invalid == "bad_answer":
        assert not brief.get("assessment") and brief["selected_direction_assessment"]["status"] == "unavailable"
    else:
        assert brief["assessment"]
    if mode == "renewed":
        assert any(q.get("stage") == "final_briefing" for q in final["exploration"]["question_assessments"]["assessments"])
    assert signed[0].get(root + "/investigations").json()["total"] == 2


@pytest.mark.parametrize("change", ["candidate", "contract", "source_metadata", "rights", "private_claim"])
@pytest.mark.parametrize("when", ["during", "after"])
def test_changed_candidates_or_complete_evidence_hide_the_link_and_reject_stale_choice(signed, monkeypatch, change, when):
    client, service, _, _ = signed
    def mutate(data, run_id):
        if change not in {"candidate", "contract"}:
            mutate_shared(service, {"id": run_id}, data, change)
            return
        with service.db.session() as session:
            run = session.get(Investigation, run_id)
            state = deepcopy(run.research_state)
            if change == "contract":
                state["exploration"].pop("next_check_contract")
            else:
                selected = data["next_check_candidates"]["items"][-1]["question_id"]
                next(q for q in state["questions"] if q["id"] == selected)["waiting_reason"] = "Changed candidate research state"
            run.research_state = state
            session.commit()
    def callback(data):
        if when == "during":
            # Each serialized candidate resolves to this final episode, not its parent.
            from sqlalchemy import select
            with service.db.session() as session:
                run_id = session.scalar(select(Investigation.id).where(Investigation.question == data["original_question"]))
            mutate(data, run_id)
    root, final, trace = episode(signed, monkeypatch, callback=callback)
    if when == "after":
        assert final["exploration"]["next_check"]["answer_link"]
        body = command(final)
        mutate(trace["choices"][0]["input"], final["id"])
        final = client.get(root + "/investigations/" + final["id"]).json()
        assert post(client, url(root, final), body).status_code == 409
    else:
        assert final["status"] == "paused"
    assert final["exploration"]["briefing"] is None
    assert final["exploration"]["next_check"] is None
    assert final["exploration"]["status"] == "evidence_changed"
    assert "next_check_inputs_invalid" not in json.dumps(final["exploration"])
    assert "PRIVATE CANARY" not in json.dumps(final["exploration"])
    assert "PRIVATE CANARY" not in json.dumps(trace["final_requests"])
    client.cookies.clear()
    assert client.get(root + "/investigations/" + final["id"]).status_code == 401


@pytest.mark.parametrize("mode", ["legacy", "free_text", "changed_answer"])
def test_older_context_and_later_answer_changes_do_not_invent_a_connection(signed, monkeypatch, mode):
    client, service, _, _ = signed
    root, final, trace = episode(signed, monkeypatch, legacy=mode == "legacy", free_text=mode == "free_text")
    if mode == "changed_answer":
        assert final["exploration"]["next_check"]["answer_link"]
        with service.db.session() as session:
            run = session.get(Investigation, final["id"])
            state = deepcopy(run.research_state)
            state["exploration"]["briefing"]["assessment"]["limitations"][1] = "Changed answer uncertainty"
            run.research_state = state
            session.commit()
        final = client.get(root + "/investigations/" + final["id"]).json()
        assert final["exploration"]["briefing"] is None and final["exploration"]["next_check"] is None
    else:
        assert not trace["choices"] and final["exploration"]["briefing"]
        assert not final["exploration"]["next_check"] or "answer_link" not in final["exploration"]["next_check"]
