"""Current read assessments guide durable work; fixtures are not semantic validation."""

import hashlib
import json
from copy import deepcopy

import pytest
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude, until
from test_product_exploration import QUESTION, adapters, start
from test_product_investigations import tick
from test_product_iterative_research import GRANT, IDENTITY, complete

from helvetic_lens import product_exploration as exploration
from helvetic_lens import product_informed_research as informed
from helvetic_lens import product_iterative_research as research
from helvetic_lens.config import DomainError
from helvetic_lens.product_investigation_models import (
    ClaimEvidence,
    DossierClaim,
    Investigation,
    InvestigationBranch,
    InvestigationSource,
)
from helvetic_lens.product_investigations import rows, scope

QUERY = "River Trust recipient disclosure 2024 reported amount verification"


def setup(monkeypatch, service, model, *, category="counterevidence", during=None):
    trace = adapters(monkeypatch, service, model)
    base = model.complete
    trace.update(reflection_inputs=[], early_inputs=[])

    async def response(system, user, **kwargs):
        data = json.loads(user)
        title = kwargs["response_schema"]["title"]
        if title == "Reflection":
            trace["reflection_inputs"].append(deepcopy(data))
            if during:
                during(data)
        result = json.loads(await base(system, user, **kwargs))
        if title == "ResearchExtraction" and data.get("read_question") and category != "missing":
            source = data["source"]
            result["read_relevance"] = {
                "source_id": source["id"],
                "question_id": data["read_question"]["question_id"],
                "category": category if source["excerpts"][0]["text"] == GRANT else "context",
                "quote": source["excerpts"][0]["text"],
                "locator": "p1",
                "reason": "This passage motivates checking what the recipient actually reports.",
                "limitations": ["date"],
            }
        if title == "EarlyOrientation":
            trace["early_inputs"].append(deepcopy(data))
            context = data.get("read_context")
            if context and context["assessments"]:
                result["interpretations"][0]["meaning"] = (
                    "The registry gives context, but the intended identity remains unconfirmed."
                )
        if title == "Reflection":
            values = data.get("read_context", {}).get("assessments", [])
            if any(a["category"] == "counterevidence" and a["quote"] == GRANT for a in values):
                assert informed.SYSTEM in system
                assert result["gaps"]
                result["gaps"][0]["query"] = QUERY
                result["gaps"][0]["purpose"] = (
                    "The read assessment leaves the recipient's own account to check."
                )
        return json.dumps(result)

    monkeypatch.setattr(model, "complete", response)
    return trace


@pytest.mark.parametrize("product", ["legal", "pharma"])
def test_assessments_change_actual_next_search_and_early_snapshot_survives_history(
    signed, monkeypatch, product
):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client, product)
    early = until(client, service, root, run)
    view = deepcopy(early["exploration"]["orientation"])
    assert len(trace["reads"]) == 2 and len(trace["early_inputs"]) == 1
    assert view["briefing"]["read_preparation"] == {
        "contract": informed.CONTRACT,
        "assessed_sources": 1,
        "unassessed_sources": 1,
    }
    assert "registry gives context" in view["briefing"]["interpretations"][0]["meaning"]
    assert "read_context_at_orientation" not in view["briefing"]
    final = complete(client, service, root + "/investigations", run)
    assert final["exploration"]["status"] == "ready" and final["question"] == QUESTION
    assert trace["queries"].count(QUERY) == 1 and len(trace["queries"]) == 3
    assert len(trace["reads"]) == 3 and len(trace["early_inputs"]) == 1
    assert final["exploration"]["orientation"] == view
    assert any(
        q["query"] == QUERY and q["status"] == "evidence_found" for q in final["research"]["questions"]
    )
    assert client.get(root + "/web-research").json()["policy"]["enabled"] is False
    assert all(final["research"]["used"].get(k, 0) <= v for k, v in final["research"]["limits"].items())
    assert client.get(root + "/investigations/" + run["id"]).json()["exploration"]["orientation"] == view


@pytest.mark.parametrize("category", ["context", "uncertain", "missing"])
def test_unknown_or_context_is_not_discarded_or_promoted_to_counterevidence(signed, monkeypatch, category):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model, category=category)
    root, run, _ = start(client)
    final = complete(client, service, root + "/investigations", run)
    assert final["exploration"]["status"] == "ready" and QUERY not in trace["queries"]
    assert len(trace["reads"]) == 3
    contexts = [d["read_context"] for d in trace["reflection_inputs"]]
    assert contexts
    if category == "missing":
        assert all(not c["assessments"] and c["unassessed_source_ids"] for c in contexts)
    else:
        assert any(
            a["category"] == category and a["limitations"] == ["date"]
            for c in contexts
            for a in c["assessments"]
        )


def captured(service, client, monkeypatch, model):
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client)
    early = until(client, service, root, run)
    return trace, root, run, early


def test_question_specific_context_keeps_two_different_assessments_of_one_source(signed, monkeypatch):
    client, service, _, model = signed
    _, _, run, _ = captured(service, client, monkeypatch, model)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        branches = [b for b in rows(session, InvestigationBranch, saved) if b.checkpoint.get("question_id")]
        first = next(b for b in branches if b.checkpoint.get("read_relevance", {}).get("assessments"))
        other = next(b for b in branches if b.id != first.id)
        assessment = deepcopy(first.checkpoint["read_relevance"]["assessments"][0])
        question = next(
            q for q in saved.research_state["questions"] if q["id"] == other.checkpoint["question_id"]
        )
        assessment.update(question_id=question["id"], question=question["question"], category="unrelated")
        other.checkpoint = {
            **other.checkpoint,
            "read_relevance": {"contract": "read-relevance/v1", "assessments": [assessment]},
        }
        session.flush()
        value = exploration.prepare(session, saved, early=True)["read_context"]
        values = [a for a in value["assessments"] if a["source_id"] == assessment["source_id"]]
        assert {v["category"] for v in values} == {"context", "unrelated"}
        assert len({v["question_id"] for v in values}) == 2


@pytest.mark.parametrize("mode", ["source_hash", "rights", "assessment", "claim", "mixed_claim"])
def test_changed_model_inputs_reject_reflection_before_creating_any_followup(signed, monkeypatch, mode):
    client, service, _, model = signed
    _, _, run, _ = captured(service, client, monkeypatch, model)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        branch = next(
            b
            for b in rows(session, InvestigationBranch, saved)
            if b.checkpoint.get("read_relevance", {}).get("assessments")
        )
        source = session.get(InvestigationSource, branch.checkpoint["source_ids"][0])
        claim = DossierClaim(
            **scope(saved), statement="A public fixture claim.", status="UNVERIFIED", revision=0, history=[]
        )
        session.add(claim)
        session.flush()
        session.add(
            ClaimEvidence(
                **scope(saved),
                source_id=source.id,
                claim_id=claim.id,
                relation="CONTEXT",
                quote=IDENTITY,
                locator="p1",
            )
        )
        session.flush()
        supplied = research.prepare_reflection(session, saved, branch)
        assert claim.id in {c["id"] for c in supplied["claims"]}
        if mode == "source_hash":
            source.sha256 = hashlib.sha256(b"changed").hexdigest()
        elif mode == "rights":
            source.snapshot = {**source.snapshot, "allow_discovery": False}
        elif mode == "assessment":
            state = deepcopy(branch.checkpoint)
            state["read_relevance"]["assessments"][0]["category"] = "uncertain"
            branch.checkpoint = state
        elif mode == "claim":
            claim.statement = "PRIVATE CHANGED CLAIM"
        else:
            private = InvestigationSource(
                **scope(saved),
                kind="uploaded_file",
                title="PRIVATE FILE",
                url="",
                source_key="private",
                sha256="private",
                snapshot={"excerpts": [{"text": "PRIVATE FILE", "passage": "p1"}]},
            )
            session.add(private)
            session.flush()
            session.add(
                ClaimEvidence(
                    **scope(saved),
                    source_id=private.id,
                    claim_id=claim.id,
                    relation="CONTEXT",
                    quote="PRIVATE FILE",
                    locator="p1",
                )
            )
        session.flush()
        before = deepcopy(saved.research_state)
        result = research.Reflection(gaps=[], outcome="No new search has been established.")
        with pytest.raises(DomainError):
            research.apply_reflection(session, saved, branch, supplied, result)
        assert saved.research_state == before
        if mode == "mixed_claim":
            clean = research.prepare_reflection(session, saved, branch)
            assert claim.id not in {c["id"] for c in clean["claims"]}
            assert "PRIVATE" not in json.dumps(clean)


def test_reflection_without_early_view_retains_every_input_for_future_access_fences(signed, monkeypatch):
    client, service, identity, model = signed
    _, _, run, _ = captured(service, client, monkeypatch, model)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        exploration.update(saved, orientation=None, adaptive_dependencies=[], read_dependencies=[])
        branch = next(
            b
            for b in rows(session, InvestigationBranch, saved)
            if b.checkpoint.get("read_relevance", {}).get("assessments")
        )
        supplied = research.prepare_reflection(session, saved, branch)
        assert "early_orientation" not in supplied
        research.apply_reflection(
            session,
            saved,
            branch,
            supplied,
            research.Reflection(gaps=[], outcome="No extra search is currently justified."),
        )
        deps = saved.research_state["exploration"]["adaptive_dependencies"]
        assert {d["source_id"] for d in deps} == {s["id"] for s in supplied["sources"]}
        session.commit()
    exclude(service, identity, deps[0]["source_id"])
    tick(service, run["id"])
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        assert saved.status == "paused" and not exploration.adaptive_current(session, saved)


def test_legacy_episode_keeps_its_existing_context_and_snapshot_contract(signed, monkeypatch):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        state = deepcopy(saved.research_state)
        state["exploration"].pop("informed_contract")
        saved.research_state = state
        session.commit()
    final = complete(client, service, root + "/investigations", run)
    assert final["exploration"]["status"] == "ready" and QUERY not in trace["queries"]
    assert all("read_context" not in d for d in trace["reflection_inputs"] + trace["early_inputs"])
    assert "read_preparation" not in final["exploration"]["orientation"]["briefing"]


@pytest.mark.parametrize("mode", ["assessment", "rights"])
def test_inflight_reflection_change_cannot_launch_its_search(signed, monkeypatch, mode):
    client, service, identity, model = signed
    touched = []

    def during(data):
        assessed = data.get("read_context", {}).get("assessments", [])
        target = next((a for a in assessed if a["quote"] == GRANT), None)
        if not target or touched:
            return
        touched.append(target["source_id"])
        if mode == "rights":
            exclude(service, identity, target["source_id"])
        else:
            with service.db.session() as session:
                source = session.get(InvestigationSource, target["source_id"])
                saved = session.get(Investigation, source.investigation_id)
                branch = next(
                    b
                    for b in rows(session, InvestigationBranch, saved)
                    if target["source_id"] in b.checkpoint.get("source_ids", [])
                )
                state = deepcopy(branch.checkpoint)
                state["read_relevance"]["assessments"][0]["category"] = "uncertain"
                branch.checkpoint = state
                session.commit()

    trace = setup(monkeypatch, service, model, during=during)
    root, run, _ = start(client)
    final = complete(client, service, root + "/investigations", run)
    assert touched and QUERY not in trace["queries"]
    assert final["research"] is None or not any(q["query"] == QUERY for q in final["research"]["questions"])
