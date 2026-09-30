"""Exact question outcomes through durable workers; fictional sources, not semantic evaluation."""

import json
from copy import deepcopy
from uuid import uuid4

import pytest
from test_product_adaptive_orientation import QUERY
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude
from test_product_episode_progress import extra_source
from test_product_exploration import adapters, start
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


def configured(
    signed, monkeypatch, product="legal", status="partial", invalid=None, callback=None, legacy=False
):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    base, search = model.complete, decision_search.federated_retrieve
    requests = []

    async def retrieve(*args):
        value = await search(*args)
        if "grants report" in args[1]:
            value["items"].append(
                {
                    "id": "counter",
                    "url": "https://example.org/recipient",
                    "title": "Recipient disclosure",
                    "summary": "Fictional public counter record",
                }
            )
        return value

    async def respond(system, user, **kwargs):
        result = json.loads(await base(system, user, **kwargs))
        data = json.loads(user)
        if kwargs["response_schema"]["title"] != "Reflection":
            return json.dumps(result)
        requests.append(data)
        result["gaps"] = []
        if "grants report" not in data["branch"] or not data.get("branch_assessment_question"):
            return json.dumps(result)
        target, sources = data["branch_assessment_question"], data["sources"]
        assert target["question"] == "Which grants does the foundation disclose?"

        def ref(source, role):
            return {
                "source_id": source["id"],
                "quote": source["excerpts"][0]["text"],
                "locator": "p1",
                "role": role,
            }

        evidence = [ref(sources[0], "context" if status == "not_found" else "support")]
        if status == "conflicting":
            evidence.append(ref(sources[1], "counterevidence"))
        a = {
            "question_id": target["question_id"],
            "status": status,
            "points": [
                {
                    "statement": "The fictional read records leave the requested scope uncertain.",
                    "evidence": evidence,
                }
            ],
            "limitations": ["Only retained passages were assessed; no exhaustive answer or human review."],
            "further_check": None
            if status == "possible_answer"
            else {
                **{k: v for k, v in evidence[0].items() if k != "role"},
                "query": QUERY,
                "purpose": "Look for a separate reconciliation record to clarify the incomplete grant account.",
            },
        }
        result["assessment"] = a
        if invalid == "missing":
            result.pop("assessment")
        elif invalid == "question":
            a["question_id"] = str(uuid4())
        elif invalid == "source":
            a["points"][0]["evidence"][0]["source_id"] = str(uuid4())
        elif invalid == "quote":
            a["points"][0]["evidence"][0]["quote"] = "A fabricated quote that was never supplied."
        elif invalid == "uncited":
            a["points"][0]["evidence"] = []
        elif invalid == "conflict":
            a["status"] = "conflicting"
        elif invalid == "repeated":
            a["further_check"]["query"] = data["previous_public_queries"][0]
        elif invalid == "proposal_quote":
            a["further_check"]["quote"] = "A nonexistent reason in the source."
        elif invalid == "resolved_proposal":
            a["status"] = "possible_answer"
        if callback:
            callback(data)
        return json.dumps(result)

    monkeypatch.setattr(decision_search, "federated_retrieve", retrieve)
    monkeypatch.setattr(model, "complete", respond)
    root, run, _ = start(client, product)
    if legacy:
        with service.db.session() as session:
            saved = session.get(Investigation, run["id"])
            state = deepcopy(saved.research_state)
            state["exploration"].pop("branch_assessment_contract")
            saved.research_state = state
            session.commit()
    return root, run, trace, requests


@pytest.mark.parametrize("product", ["legal", "pharma"])
@pytest.mark.parametrize("status", ["possible_answer", "partial", "conflicting", "not_found"])
def test_capture_does_not_settle_question_and_explicit_different_query_continues(
    signed, monkeypatch, product, status
):
    client, service, _, model = signed
    root, run, trace, requests = configured(signed, monkeypatch, product, status)
    old = complete(client, service, root + "/investigations", run)
    assert old["exploration"]["status"] == "ready", old
    a = old["exploration"]["question_assessments"]["assessments"][0]
    question = next(q for q in old["research"]["questions"] if q["id"] == a["question_id"])
    assert question["status"] == "evidence_found" and a["status"] == status
    assert a["question"] == question["question"] and a["points"][0]["evidence"]
    assert "branch_assessment" not in json.dumps(old["plans"])
    assert "branch_assessment" not in json.dumps(old["research"])
    assert len(requests) == 2 and len(trace["queries"]) == 2 and QUERY not in trace["queries"]
    assert client.get(root + "/investigations").json()["total"] == 1
    assert not client.get(root + "/web-research").json()["policy"]["enabled"]
    if status == "possible_answer":
        assert old["exploration"]["next_check"] is None
        return
    check = old["exploration"]["next_check"]
    assert check["basis"] == "further_question" and check["question_id"] == a["question_id"]
    assert check["question"] == question["question"]
    assessment_adapters(monkeypatch, model, trace, old, "partial")
    body = command(old)
    response = post(client, url(root, old), body)
    assert response.status_code == 202, response.text
    child = response.json()
    assert post(client, url(root, old), body).json()["id"] == child["id"]
    final = complete(client, service, root + "/investigations", child)
    assert trace["queries"].count(QUERY) == 1 and final["exploration"]["status"] == "ready"
    assert final["exploration"]["briefing"]["assessment"]["question"] == a["question"]
    prior = client.get(root + "/investigations/" + old["id"]).json()
    assert prior["exploration"]["question_assessments"] == old["exploration"]["question_assessments"]
    assert prior["sources"] == old["sources"] and prior["exploration"]["next_check"] is None
    assert post(client, url(root, old), {**body, "request_key": str(uuid4())}).status_code == 409
    assert not client.get(root + "/web-research").json()["policy"]["enabled"]


@pytest.mark.parametrize(
    "invalid",
    [
        "missing",
        "question",
        "source",
        "quote",
        "uncited",
        "conflict",
        "repeated",
        "proposal_quote",
        "resolved_proposal",
    ],
)
def test_unvalidated_assessment_is_unknown_and_never_repeats_query(signed, monkeypatch, invalid):
    client, service, _, _ = signed
    root, run, trace, _ = configured(signed, monkeypatch, invalid=invalid)
    final = complete(client, service, root + "/investigations", run)
    value = final["exploration"]["question_assessments"]
    assert value["status"] == "ready" and value["assessments"] == [] and value["unassessed"] > 0
    assert final["exploration"]["next_check"] is None and QUERY not in trace["queries"]
    assert final["sources"]


@pytest.mark.parametrize(
    "when", ["during", "after", "queued", "during_search", "hash", "claim", "mixed_claim"]
)
def test_complete_context_fences_assessment_and_descendant(signed, monkeypatch, when):
    client, service, identity, model = signed
    recorded = {}

    def callback(data):
        recorded.update(data)
        if when == "during":
            exclude(service, identity, data["sources"][-1]["id"])

    root, run, trace, _ = configured(signed, monkeypatch, callback=callback)
    old = complete(client, service, root + "/investigations", run)
    if when == "during":
        assert not old["exploration"]["question_assessments"].get("assessments")
        assert old["exploration"]["next_check"] is None
        return
    assert old["exploration"]["next_check"]
    body = command(old)
    unquoted = recorded["sources"][-1]["id"]

    def revoke():
        if when in {"claim", "mixed_claim", "hash"}:
            with service.db.session() as session:
                if when == "hash":
                    session.get(InvestigationSource, unquoted).sha256 = "b" * 64
                else:
                    claim = session.get(DossierClaim, recorded["claims"][0]["id"])
                    if when == "claim":
                        claim.statement = "PRIVATE changed claim canary"
                    else:
                        saved = session.get(Investigation, run["id"])
                        private = extra_source(session, saved, private=True)
                        session.add(
                            ClaimEvidence(
                                **scope(saved),
                                source_id=private.id,
                                claim_id=claim.id,
                                relation="CONTEXT",
                                quote="PRIVATE CANARY",
                                locator="p1",
                            )
                        )
                session.commit()
        else:
            exclude(service, identity, unquoted)

    if when in {"queued", "during_search"}:
        assessment_adapters(monkeypatch, model, trace, old, "partial")
        child = post(client, url(root, old), body).json()
        if when == "queued":
            revoke()
        else:
            base = decision_search.federated_retrieve

            async def search(*args, **kwargs):
                value = await base(*args, **kwargs)
                revoke()
                return value

            monkeypatch.setattr(decision_search, "federated_retrieve", search)
        final = complete(client, service, root + "/investigations", child)
        assert (
            final["status"] == "paused"
            and final["exploration"]["continuation"]["status"] == "evidence_changed"
        )
        assert not final["sources"] and final["research"] is None
        assert post(client, url(root, old), body).json()["id"] == child["id"]
    else:
        revoke()
        final = client.get(root + "/investigations/" + old["id"]).json()
        assert final["exploration"]["question_assessments"]["status"] == "evidence_changed"
        assert final["exploration"]["next_check"] is None and final["research"] is None
        assert post(client, url(root, old), body).status_code == 409
        assert "PRIVATE" not in json.dumps(final["exploration"])


def test_legacy_stays_unknown_and_private_material_never_enters_reflection(signed, monkeypatch):
    client, service, _, _ = signed
    root, run, _, requests = configured(signed, monkeypatch, legacy=True)
    tick(service, run["id"])
    with service.db.session() as session:
        extra_source(session, session.get(Investigation, run["id"]), private=True)
        session.commit()
    final = complete(client, service, root + "/investigations", run)
    assert final["exploration"]["question_assessments"]["status"] == "unknown"
    assert "PRIVATE CANARY" not in json.dumps(requests)
