"""Late context changes cannot persist an answer assessment or launch later work."""

import json
from copy import deepcopy

import pytest
from test_product_branch_assessment import configured
from test_product_dossiers import signed as signed
from test_product_episode_progress import extra_source
from test_product_iterative_research import complete

from helvetic_lens.product_investigation_models import DossierClaim, Investigation, InvestigationBranch


@pytest.mark.parametrize("changed", ["question", "branch_query", "claim"])
def test_exact_target_and_claim_context_are_rechecked_after_inference(signed, monkeypatch, changed):
    client, service, _, _ = signed

    def callback(data):
        target = data["branch_assessment_question"]
        with service.db.session() as session:
            branch = session.get(InvestigationBranch, target["branch_id"])
            run = session.get(Investigation, branch.investigation_id)
            if changed == "question":
                state = deepcopy(run.research_state)
                next(q for q in state["questions"] if q["id"] == target["question_id"])["question"] = (
                    "A different question injected during inference."
                )
                run.research_state = state
            elif changed == "branch_query":
                branch.query = "Different public query substituted while assessment was running"
            else:
                session.get(
                    DossierClaim, data["claims"][0]["id"]
                ).statement = "PRIVATE claim changed during inference"
            session.commit()

    root, run, _, _ = configured(signed, monkeypatch, callback=callback)
    final = complete(client, service, root + "/investigations", run)
    assessment = final["exploration"]["question_assessments"]
    assert assessment["status"] == "ready" and not assessment["assessments"]
    assert final["exploration"]["next_check"] is None
    assert final["sources"]
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        assert not any(q.get("branch_assessment") for q in saved.research_state["questions"])


def test_new_assessment_never_uses_unrelated_private_context(signed, monkeypatch):
    client, service, _, _ = signed
    root, run, _, requests = configured(signed, monkeypatch)
    with service.db.session() as session:
        extra_source(session, session.get(Investigation, run["id"]), private=True)
        session.commit()
    final = complete(client, service, root + "/investigations", run)
    assert final["exploration"]["question_assessments"]["assessments"]
    assert final["exploration"]["next_check"]
    assert "PRIVATE CANARY" not in json.dumps(requests)
    assert "PRIVATE CANARY" not in json.dumps(final["exploration"])


@pytest.mark.parametrize("change_during_brief", [False, True])
def test_final_brief_uses_current_question_checkpoints(signed, monkeypatch, change_during_brief):
    client, service, _, model = signed
    root, run, _, reflections = configured(signed, monkeypatch)
    base = model.complete
    observed = []

    async def respond(system, user, **kwargs):
        value = await base(system, user, **kwargs)
        if kwargs["response_schema"]["title"] == "Briefing":
            data = json.loads(user)
            checkpoint = data["question_assessments"]["assessments"][0]
            assert checkpoint["question"] == reflections[-1]["branch_assessment_question"]["question"]
            assert checkpoint["status"] == "partial" and checkpoint["points"][0]["evidence"]
            assert "branch_assessment" not in json.dumps(data["question_assessments"])
            observed.append(checkpoint)
            if change_during_brief:
                with service.db.session() as session:
                    session.get(
                        DossierClaim, reflections[-1]["claims"][0]["id"]
                    ).statement = "PRIVATE changed final context"
                    session.commit()
        return value

    monkeypatch.setattr(model, "complete", respond)
    final = complete(client, service, root + "/investigations", run)
    assert observed
    if change_during_brief:
        assert final["exploration"]["status"] == "evidence_changed"
        assert final["exploration"]["briefing"] is None and final["exploration"]["next_check"] is None
        assert final["exploration"]["question_assessments"]["status"] == "evidence_changed"
    else:
        assert final["exploration"]["status"] == "ready" and final["exploration"]["next_check"]


def test_later_public_counterevidence_keeps_work_running_but_retires_old_assessment(signed, monkeypatch):
    from test_product_exploration import adapters, start
    from test_product_iterative_research import GRANT

    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    base = model.complete
    observed = []

    async def respond(system, user, **kwargs):
        result = json.loads(await base(system, user, **kwargs))
        data = json.loads(user)
        if kwargs["response_schema"]["title"] == "Reflection" and data.get("branch_assessment_question"):
            target = data["branch_assessment_question"]
            source = next((s for s in data["sources"] if s["excerpts"][0]["text"] == GRANT), None)
            if source:
                result["assessment"] = {
                    "question_id": target["question_id"],
                    "status": "partial",
                    "points": [
                        {
                            "statement": "The grant statement still needs independent confirmation.",
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
        if kwargs["response_schema"]["title"] == "Briefing":
            observed.append(data)
        return json.dumps(result)

    monkeypatch.setattr(model, "complete", respond)
    root, run, _ = start(client)
    final = complete(client, service, root + "/investigations", run)
    assert final["status"] == "completed" and final["exploration"]["status"] == "ready", final["stop_reason"]
    assert len(trace["queries"]) == 3 and final["claims"][0]["status"] == "CONTESTED"
    value = final["exploration"]["question_assessments"]
    assert value["outdated"] == 1 and value["assessments"] == []
    assert observed[0]["question_assessments"]["outdated"] == 1
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        assert any(q.get("branch_assessment") for q in saved.research_state["questions"])
