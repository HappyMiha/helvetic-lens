"""Ordinary cited questions through durable episodes; not live semantic evaluation."""

import json
from copy import deepcopy
from uuid import uuid4

import pytest
from test_product_adaptive_orientation import QUERY
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude
from test_product_episode_progress import extra_source
from test_product_exploration import QUESTION, adapters, start
from test_product_investigations import tick
from test_product_iterative_research import complete
from test_product_question_assessment import assessment_adapters
from test_product_saved_check import command, url

from helvetic_lens import decision_search
from helvetic_lens.product_investigation_models import (
    ClaimEvidence,
    DossierClaim,
    Investigation,
    InvestigationSource,
)
from helvetic_lens.product_investigations import scope


def prepared(client, service, model, monkeypatch, product="legal", *, early=True, legacy=False):
    trace = adapters(monkeypatch, service, model)
    base = model.complete

    async def respond(system, user, **kwargs):
        phase = kwargs["response_schema"]["title"]
        if phase == "EarlyOrientation" and not early:
            return "{}"  # Optional failed orientation must not prevent an ordinary check.
        value = json.loads(await base(system, user, **kwargs))
        if phase == "Reflection":
            for gap in value["gaps"]:
                assert not gap.get("reconsideration")
                gap["query"] = QUERY
        return json.dumps(value)

    monkeypatch.setattr(model, "complete", respond)
    root, run, _ = start(client, product)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        state = deepcopy(saved.research_state)
        state["limits"]["depth"] = 0
        if legacy:
            state["exploration"].pop("open_check_contract")
        saved.research_state = state
        session.commit()
    value = complete(client, service, root + "/investigations", run)
    assert value["exploration"]["status"] == "ready"
    assert not value["exploration"]["changes"] and QUERY not in trace["queries"]
    if not legacy:
        check = value["exploration"]["next_check"]
        assert check and check["basis"] == "open_question" and check["why"] == check["purpose"]
    assert "open_check_context" not in json.dumps(value)
    return root, value, trace


@pytest.mark.parametrize("product", ["legal", "pharma"])
@pytest.mark.parametrize("early", [True, False])
def test_ordinary_question_executes_saved_query_once_and_gets_cited_assessment(
    signed, monkeypatch, product, early
):
    client, service, _, model = signed
    root, old, trace = prepared(client, service, model, monkeypatch, product, early=early)
    before = deepcopy(old["exploration"]["briefing"])
    requests = assessment_adapters(monkeypatch, model, trace, old, "partial")
    body = command(old)
    child = post(client, url(root, old), body).json()
    assert post(client, url(root, old), body).json()["id"] == child["id"]
    final = complete(client, service, root + "/investigations", child)
    assert final["exploration"]["status"] == "ready", final["stop_reason"]
    assert trace["queries"].count(QUERY) == 1
    assert not any(r["phase"] == "ResearchPlan" for r in requests)
    context = final["exploration"]["continuation"]
    assert context["basis"] == "open_question" and context["original_question"] == QUESTION
    assert context["quote"] == old["exploration"]["next_check"]["quote"]
    assert final["sources"] and final["exploration"]["capture_progress"]["status"] == "ready"
    assessment = final["exploration"]["briefing"]["assessment"]
    assert assessment["question_id"] == body["follow_up_id"] and assessment["question"] == body["question"]
    assert assessment["points"][0]["evidence"] and assessment["status"] == "partial"
    prior = client.get(root + "/investigations/" + old["id"]).json()
    assert prior["exploration"]["briefing"] == before and prior["sources"] == old["sources"]
    assert prior["exploration"]["next_check"] is None
    assert post(client, url(root, old), body).json()["id"] == child["id"]
    assert post(client, url(root, old), {**body, "request_key": str(uuid4())}).status_code == 409
    assert client.get(root + "/investigations").json()["total"] == 2
    assert client.get(root + "/web-research").json()["policy"]["enabled"] is False
    assert "open_check_context" not in json.dumps(final) and "context_fingerprint" not in json.dumps(requests)


@pytest.mark.parametrize(
    "change",
    [
        "missing_receipt",
        "incomplete_receipt",
        "dependencies",
        "query",
        "purpose",
        "claim",
        "mixed_claim",
        "hash",
        "rights",
        "finished",
    ],
)
def test_incomplete_or_changed_context_cannot_start_a_saved_check(signed, monkeypatch, change):
    client, service, _, model = signed
    root, old, _ = prepared(client, service, model, monkeypatch)
    body = command(old)
    with service.db.session() as session:
        run = session.get(Investigation, old["id"])
        state = deepcopy(run.research_state)
        question = next(q for q in state["questions"] if q["id"] == body["follow_up_id"])
        if change == "missing_receipt":
            question.pop("open_check_context")
        elif change == "incomplete_receipt":
            question["open_check_context"]["claims"] = []
        elif change == "dependencies":
            state["exploration"]["adaptive_dependencies"] = [
                d
                for d in state["exploration"]["adaptive_dependencies"]
                if d["source_id"] == question["trigger"]["source_id"]
            ]
        elif change in {"query", "purpose"}:
            question[change] = "A changed public topic without the original recorded context."
        elif change == "finished":
            question["status"] = "evidence_found"
        elif change in {"hash", "rights"}:
            source = session.get(InvestigationSource, question["trigger"]["source_id"])
            if change == "hash":
                source.sha256 = "b" * 64
            else:
                source.snapshot = {**source.snapshot, "allow_discovery": False}
        else:
            claim = session.get(DossierClaim, question["open_check_context"]["claims"][0]["id"])
            if change == "claim":
                claim.statement = "PRIVATE CHANGED CLAIM CANARY"
            else:
                private = extra_source(session, run, private=True)
                session.add(
                    ClaimEvidence(
                        **scope(run),
                        source_id=private.id,
                        claim_id=claim.id,
                        relation="CONTEXT",
                        quote="PRIVATE CANARY",
                        locator="p1",
                    )
                )
        run.research_state = state
        session.commit()
    response = client.get(root + "/investigations/" + old["id"]).json()
    assert response["exploration"]["next_check"] is None
    assert post(client, url(root, old), body).status_code == 409
    assert client.get(root + "/investigations").json()["total"] == 1


@pytest.mark.parametrize("when", ["before_selection", "queued", "during_search", "after_completion"])
def test_unquoted_source_dependency_fences_the_ordinary_descendant(signed, monkeypatch, when):
    client, service, identity, model = signed
    root, old, trace = prepared(client, service, model, monkeypatch)
    with service.db.session() as session:
        run = session.get(Investigation, old["id"])
        question = next(q for q in run.research_state["questions"] if q.get("open_check_context"))
        unquoted = next(
            d["source_id"]
            for d in question["open_check_context"]["source_dependencies"]
            if d["source_id"] != question["trigger"]["source_id"]
        )
    body = command(old)
    if when == "before_selection":
        exclude(service, identity, unquoted)
        assert post(client, url(root, old), body).status_code == 409
        return
    assessment_adapters(monkeypatch, model, trace, old, "partial")
    child = post(client, url(root, old), body).json()
    if when == "during_search":
        base = decision_search.federated_retrieve

        async def retrieve(*args, **kwargs):
            result = await base(*args, **kwargs)
            exclude(service, identity, unquoted)
            return result

        monkeypatch.setattr(decision_search, "federated_retrieve", retrieve)
    else:
        if when == "after_completion":
            complete(client, service, root + "/investigations", child)
        exclude(service, identity, unquoted)
    final = complete(client, service, root + "/investigations", child)
    assert final["exploration"]["continuation"] == {"status": "evidence_changed"}
    assert final["exploration"]["briefing"] is None and final["research"] is None
    assert final["branches"] == final["plans"] == []
    if when != "after_completion":
        assert final["status"] == "paused" and not final["sources"]
    if when == "queued":
        assert QUERY not in trace["queries"]
    assert post(client, url(root, old), body).json()["id"] == child["id"]


def test_legacy_gap_does_not_gain_guessed_provenance(signed, monkeypatch):
    client, service, _, model = signed
    _, old, _ = prepared(client, service, model, monkeypatch, legacy=True)
    assert old["exploration"]["next_check"] is None


def test_unrelated_private_source_does_not_enter_the_ordinary_continuation(signed, monkeypatch):
    client, service, _, model = signed
    root, old, trace = prepared(client, service, model, monkeypatch)
    body = command(old)
    with service.db.session() as session:
        run = session.get(Investigation, old["id"])
        extra_source(session, run, private=True)
        session.commit()
    requests = assessment_adapters(monkeypatch, model, trace, old, "partial")
    child = post(client, url(root, old), body).json()
    tick(service, child["id"])
    final = complete(client, service, root + "/investigations", child)
    assert final["exploration"]["status"] == "ready" and "PRIVATE CANARY" not in json.dumps(requests)
    assert "PRIVATE CANARY" not in json.dumps(final["exploration"])


@pytest.mark.parametrize("when", ["queued", "during_search"])
def test_changed_claim_context_fences_an_already_selected_ordinary_check(signed, monkeypatch, when):
    client, service, _, model = signed
    root, old, trace = prepared(client, service, model, monkeypatch)
    assessment_adapters(monkeypatch, model, trace, old, "partial")
    child = post(client, url(root, old), command(old)).json()

    def change_claim():
        with service.db.session() as session:
            parent = session.get(Investigation, old["id"])
            question = next(q for q in parent.research_state["questions"] if q.get("open_check_context"))
            claim = session.get(DossierClaim, question["open_check_context"]["claims"][0]["id"])
            claim.statement = "PRIVATE CHANGED CONTEXT CANARY"
            session.commit()

    if when == "queued":
        change_claim()
    else:
        base = decision_search.federated_retrieve

        async def search(*args, **kwargs):
            value = await base(*args, **kwargs)
            change_claim()
            return value

        monkeypatch.setattr(decision_search, "federated_retrieve", search)
    final = complete(client, service, root + "/investigations", child)
    assert final["status"] == "paused" and not final["sources"]
    assert final["exploration"]["continuation"] == {"status": "evidence_changed"}
    assert final["research"] is None and final["plans"] == []
    if when == "queued":
        assert QUERY not in trace["queries"]
