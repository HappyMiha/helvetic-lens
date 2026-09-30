"""Additional boundaries of the recorded reformulation, using durable fixtures."""

import json
from copy import deepcopy
from uuid import uuid4

import pytest
from test_product_dossiers import signed as signed
from test_product_exploration import start
from test_product_investigations import tick
from test_product_iterative_research import complete
from test_product_query_recovery import ALTERNATIVE, recovery, setup, until_reformulation

from helvetic_lens import decision_search
from helvetic_lens import product_iterative_research as research
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch
from helvetic_lens.product_investigations import rows
from helvetic_lens.product_models import DossierEntry


@pytest.mark.parametrize("resource", ["search_requests", "source_fetches", "decision_calls"])
def test_no_reformulation_model_spend_without_remaining_retrieval_budget(signed, monkeypatch, resource):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client)
    until_reformulation(service, run)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        data = deepcopy(saved.research_state)
        data["used"][resource] = data["limits"][resource]
        saved.research_state = data
        session.commit()
    tick(service, run["id"])
    assert not trace["reformulations"] and ALTERNATIVE not in trace["queries"]
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        assert resource in saved.research_state["stops"]
        assert any(
            b.status == "blocked" and b.phase == "reformulate"
            for b in rows(session, InvestigationBranch, saved)
        )


@pytest.mark.parametrize("mode", ["excluded_during_model", "alternate_outage"])
def test_current_exclusion_or_failed_alternate_search_does_not_retry(signed, monkeypatch, mode):
    client, service, identity, model = signed
    trace = setup(monkeypatch, service, model, "unrelated")
    root, run, _ = start(client)
    base_model, base_search = model.complete, decision_search.federated_retrieve

    async def model_call(system, user, **kwargs):
        result = await base_model(system, user, **kwargs)
        if mode == "excluded_during_model" and kwargs["response_schema"]["title"] == "QueryReformulation":
            with service.db.session() as session:
                saved = session.get(Investigation, run["id"])
                session.add(
                    DossierEntry(
                        dossier_id=saved.dossier_id,
                        organization_id=saved.organization_id,
                        request_key=str(uuid4()),
                        kind="source_review",
                        actor_user_id=identity["user"]["id"],
                        url="https://example.org/road",
                        body="PRIVATE EXCLUSION CANARY",
                        data_json={"decision": "exclude", "revision": 1},
                    )
                )
                session.commit()
        return result

    async def search(*args):
        if mode == "alternate_outage" and args[1] == ALTERNATIVE:
            trace["queries"].append(args[1])
            raise RuntimeError("PRIVATE OUTAGE CANARY")
        return await base_search(*args)

    monkeypatch.setattr(model, "complete", model_call)
    monkeypatch.setattr(decision_search, "federated_retrieve", search)
    value = complete(client, service, root + "/investigations", run)
    assert len(trace["reformulations"]) == 1
    assert trace["queries"].count(ALTERNATIVE) == int(mode == "alternate_outage")
    assert recovery(value)["captures"] == 0
    assert recovery(value)["searches_unavailable"] == int(mode == "alternate_outage")
    assert "PRIVATE" not in json.dumps(trace["reformulations"])
    assert "PRIVATE OUTAGE CANARY" not in json.dumps(value)


def test_later_followup_cannot_repeat_the_alternative_query(signed, monkeypatch):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    _, run, _ = start(client)
    until_reformulation(service, run)
    tick(service, run["id"])
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        before = len(saved.research_state["questions"])
        added = research.add_question(
            session,
            saved,
            research.BranchDraft(
                question="Should the same query be repeated?",
                query=ALTERNATIVE.upper() + " !!!",
                purpose="Attempt a repeated query after reformulation.",
                priority=3,
            ),
        )
        assert added is None and len(saved.research_state["questions"]) == before
    assert len(trace["reformulations"]) == 1
