"""Later fictional evidence renews exact questions through the real durable worker."""

import json
from copy import deepcopy
from uuid import uuid4

import pytest
from test_product_adaptive_orientation import QUERY
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_exploration import adapters, start
from test_product_iterative_research import GRANT, RECIPIENT, complete
from test_product_question_assessment import assessment_adapters
from test_product_saved_check import command, url

from helvetic_lens.product_investigation_models import Investigation


def configured(signed, monkeypatch, product="legal", invalid=None, callback=None, legacy=False):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    base = model.complete
    observed, before = [], []

    async def respond(system, user, **kwargs):
        result = json.loads(await base(system, user, **kwargs))
        data = json.loads(user)
        title = kwargs["response_schema"]["title"]
        if title == "Reflection" and data.get("branch_assessment_question"):
            source = next((s for s in data["sources"] if s["excerpts"][0]["text"] == GRANT), None)
            if source:
                result["assessment"] = {
                    "question_id": data["branch_assessment_question"]["question_id"],
                    "status": "partial",
                    "points": [
                        {
                            "statement": "The foundation reports one amount; the recipient is unchecked.",
                            "evidence": [
                                {
                                    "source_id": source["id"],
                                    "quote": GRANT,
                                    "locator": "p1",
                                    "role": "support",
                                }
                            ],
                        }
                    ],
                    "limitations": ["The recipient account has not yet been read."],
                }
        if title == "Briefing":
            observed.append(deepcopy(data))
            if data.get("question_renewal_targets"):
                target = data["question_renewal_targets"][0]
                sources = {s["excerpts"][0]["text"]: s for s in data["sources"]}

                def ref(text, role):
                    return {"source_id": sources[text]["id"], "quote": text, "locator": "p1", "role": role}

                a = {
                    "question_id": target["question_id"],
                    "status": "conflicting",
                    "points": [
                        {
                            "statement": "The two read disclosures report different grant amounts.",
                            "evidence": [ref(GRANT, "support"), ref(RECIPIENT, "counterevidence")],
                        }
                    ],
                    "limitations": ["A reconciliation has not been found in the material read."],
                    "further_check": {k: v for k, v in ref(RECIPIENT, "context").items() if k != "role"}
                    | {
                        "query": QUERY,
                        "purpose": "Find a reconciliation of the different reported grant amounts.",
                    },
                }
                result["question_renewals"] = [a]
                if invalid == "missing":
                    result.pop("question_renewals")
                elif invalid == "target":
                    a["question_id"] = str(uuid4())
                elif invalid == "duplicate":
                    result["question_renewals"].append(deepcopy(a))
                elif invalid == "quote":
                    a["points"][0]["evidence"][1]["quote"] = "Invented absent passage"
                elif invalid == "source":
                    a["points"][0]["evidence"][1]["source_id"] = str(uuid4())
                elif invalid == "conflict":
                    a["points"][0]["evidence"] = [ref(GRANT, "support")]
                elif invalid == "query":
                    a["further_check"]["query"] = data["previous_public_queries"][0]
                elif invalid == "proposal_quote":
                    a["further_check"]["quote"] = "Invented absent proposal basis"
                elif invalid == "resolved_proposal":
                    a["status"] = "possible_answer"
                elif invalid == "bound":
                    result["question_renewals"] = [deepcopy(a) for _ in range(4)]
                with service.db.session() as session:
                    from helvetic_lens.product_investigation_models import InvestigationBranch

                    branch = session.get(InvestigationBranch, target["branch_id"])
                    saved = session.get(Investigation, branch.investigation_id)
                    before.append(
                        deepcopy(
                            next(
                                q["branch_assessment"]
                                for q in saved.research_state["questions"]
                                if q["id"] == target["question_id"]
                            )
                        )
                    )
                if callback:
                    callback(data)
        return json.dumps(result)

    monkeypatch.setattr(model, "complete", respond)
    root, run, _ = start(client, product)
    if legacy:
        with service.db.session() as session:
            saved = session.get(Investigation, run["id"])
            state = deepcopy(saved.research_state)
            state["exploration"].pop("renewal_contract")
            saved.research_state = state
            session.commit()
    return root, run, trace, observed, before


@pytest.mark.parametrize("product", ["legal", "pharma"])
def test_later_evidence_renews_question_preserves_history_and_continues_once(signed, monkeypatch, product):
    client, service, _, model = signed
    root, run, trace, observed, before = configured(signed, monkeypatch, product)
    old = complete(client, service, root + "/investigations", run)
    assert old["status"] == "completed" and old["exploration"]["status"] == "ready", old["stop_reason"]
    value = old["exploration"]["question_assessments"]
    a = value["assessments"][0]
    assert a["status"] == "conflicting" and a["stage"] == "final_briefing" and value["outdated"] == 0
    assert a["earlier"][0]["status"] == "partial" and "unchecked" in a["earlier"][0]["points"][0]["statement"]
    assert (
        len(observed) == 1
        and observed[0]["question_renewal_targets"][0]["reason"] == "earlier_context_changed"
    )
    assert len(trace["queries"]) == 3 and QUERY not in trace["queries"]
    for key in ["branch_assessment_history", "renewal_context", "question_renewals"]:
        assert key not in json.dumps(old["exploration"])
        assert key not in json.dumps(old["plans"]) and key not in json.dumps(old["research"])
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        question = next(q for q in saved.research_state["questions"] if q["id"] == a["question_id"])
        assert question["branch_assessment_history"] == before
        assert question["branch_assessment"]["revision"] == 2
        assert question["branch_assessment"]["assessment"]["further_check"]["query"] == QUERY
    assert old["exploration"]["next_check"]["question_id"] == a["question_id"]
    assessment_adapters(monkeypatch, model, trace, old, "partial")
    body = command(old)
    response = post(client, url(root, old), body)
    assert response.status_code == 202, response.text
    child = response.json()
    assert post(client, url(root, old), body).json()["id"] == child["id"]
    final = complete(client, service, root + "/investigations", child)
    assert final["exploration"]["briefing"]["assessment"]["question"] == a["question"]
    assert trace["queries"].count(QUERY) == 1
    prior = client.get(root + "/investigations/" + run["id"]).json()
    assert prior["exploration"]["question_assessments"] == value
    assert not client.get(root + "/web-research").json()["policy"]["enabled"]


@pytest.mark.parametrize(
    "invalid",
    [
        "missing",
        "target",
        "duplicate",
        "quote",
        "source",
        "conflict",
        "query",
        "proposal_quote",
        "resolved_proposal",
        "bound",
    ],
)
def test_missing_or_invalid_renewal_never_rewrites_earlier_checkpoint(signed, monkeypatch, invalid):
    client, service, _, _ = signed
    root, run, trace, observed, before = configured(signed, monkeypatch, invalid=invalid)
    final = complete(client, service, root + "/investigations", run)
    assert observed and before
    assert final["exploration"]["status"] == ("ready" if invalid == "missing" else "unavailable")
    assert final["exploration"]["next_check"] is None and QUERY not in trace["queries"]
    assert final["exploration"]["question_assessments"]["outdated"] == 1
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        old = [q for q in saved.research_state["questions"] if q.get("branch_assessment")]
        assert [q["branch_assessment"] for q in old] == before
        assert not any(q.get("branch_assessment_history") for q in old)


def test_legacy_episode_does_not_acquire_renewal_context(signed, monkeypatch):
    client, service, _, _ = signed
    root, run, _, observed, before = configured(signed, monkeypatch, legacy=True)
    final = complete(client, service, root + "/investigations", run)
    assert (
        final["exploration"]["status"] == "ready"
        and final["exploration"]["question_assessments"]["outdated"] == 1
    )
    assert before == [] and "question_renewal_targets" not in observed[0]
