"""Causal reinterpretation through real worker turns; fictional, not live quality."""
import hashlib
import json
from copy import deepcopy

import pytest
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude
from test_product_exploration import QUESTION, adapters, start
from test_product_investigations import tick
from test_product_iterative_research import GRANT, RECIPIENT, complete

from helvetic_lens import decision_search, decision_sources
from helvetic_lens import product_exploration as exploration
from helvetic_lens import product_iterative_research as research
from helvetic_lens.config import DomainError
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationSource

QUERY = "River Trust audited reconciliation 2024"
PASSAGE = "River Trust records a CHF 10,000 grant instalment carried into 2025; the total award was CHF 50,000."


def adaptive(monkeypatch, service, model, callback=None):
    trace = adapters(monkeypatch, service, model)
    base, retrieve, inspect = model.complete, decision_search.federated_retrieve, decision_sources.safe_inspect

    async def search(settings, query, *args):
        result = await retrieve(settings, query, *args)
        if query == QUERY:
            result["items"] = [{"id": "reconciliation", "title": "Alpine Foundation reconciliation",
                "url": "https://example.org/reconciliation", "summary": "Public fixture record"}]
        return result

    async def read(settings, query, item, *args, **kwargs):
        if item["url"].endswith("reconciliation"):
            trace["reads"].append(item["url"])
            return {"status": "complete", "url": item["url"], "sha256": hashlib.sha256(PASSAGE.encode()).hexdigest(),
                "excerpts": [{"text": PASSAGE, "passage": "p1"}], "scope": "Fictional public record"}
        return await inspect(settings, query, item, *args, **kwargs)

    async def respond(system, user, **kwargs):
        data = json.loads(user)
        title = kwargs["response_schema"]["title"]
        if title == "ResearchExtraction" and data["source"]["excerpts"][0]["text"] == PASSAGE:
            return json.dumps({"claims": [{"statement": PASSAGE, "relation": "CONTEXT", "quote": PASSAGE, "locator": "p1"}]})
        result = json.loads(await base(system, user, **kwargs))
        if title == "EarlyOrientation":
            source = next(s for s in data["sources"] if s["excerpts"][0]["text"] == GRANT)
            result["interpretations"][0].update(source_id=source["id"], quote=GRANT,
                meaning="The question may concern a single reported grant and its recipient.",
                why="This captured grant record identifies a possible recipient and an amount for the user's funding question.")
        if title == "Reflection" and any(s["excerpts"][0]["text"] == RECIPIENT for s in data["sources"]):
            source = next(s for s in data["sources"] if s["excerpts"][0]["text"] == RECIPIENT)
            early = data["early_orientation"]
            result["gaps"] = [{"question": "Do different payment periods explain the reported amounts?",
                "query": QUERY, "purpose": "Find a reconciliation distinguishing payment from the award.", "priority": 5,
                "source_id": source["id"], "quote": RECIPIENT, "locator": "p1", "kind": "contradiction",
                "reconsideration": {"orientation_revision": early["revision"], "interpretation_index": 0,
                    "signal": "questioned", "meaning": "The research may need to distinguish the award from payments received.",
                    "why": "The recipient reports a different amount for the same year; a single amount may conceal timing."}}]
            trace["reconsideration_input"] = data
            trace["reconsideration_result"] = deepcopy(result)
            if callback:
                callback(data, result)
        return json.dumps(result)

    monkeypatch.setattr(decision_search, "federated_retrieve", search)
    monkeypatch.setattr(decision_sources, "safe_inspect", read)
    monkeypatch.setattr(model, "complete", respond)
    return trace


def until_change(client, service, root, run):
    for _ in range(90):
        value = client.get(root + "/investigations/" + run["id"]).json()
        if value["exploration"].get("changes"):
            return value
        assert value["status"] in {"queued", "running"}, value
        tick(service, run["id"])
    raise AssertionError("No adaptive question created")


@pytest.mark.parametrize("product", ["legal", "pharma"])
def test_new_passage_changes_real_next_search_and_keeps_original_history(signed, monkeypatch, product):
    client, service, _, model = signed
    trace = adaptive(monkeypatch, service, model)
    root, run, _ = start(client, product)
    first = until_change(client, service, root, run)
    assert QUERY not in trace["queries"]
    change = first["exploration"]["changes"][0]
    assert change["searches_completed"] == change["reads_completed"] == 0
    assert change["branch_id"] and change["signal"] == "questioned"
    final = complete(client, service, root + "/investigations", run)
    assert final["question"] == QUESTION
    assert final["exploration"]["status"] == "ready"
    assert trace["queries"].count(QUERY) == 1
    assert len(trace["reads"]) == 4
    saved = final["exploration"]["changes"][0]
    assert saved["quote"] == RECIPIENT and saved["searches_completed"] == saved["reads_completed"] == 1
    assert saved["status"] == "evidence_found"
    assert first["exploration"]["orientation"] == final["exploration"]["orientation"]
    assert final["exploration"]["briefing"]["findings"][-1]["quote"] == PASSAGE
    assert trace["briefings"][0]["interpretation_changes"][0]["question_id"] == saved["question_id"]
    assert all(final["research"]["used"].get(k, 0) <= v for k, v in final["research"]["limits"].items())
    assert client.get(root + "/web-research").json()["policy"]["enabled"] is False


def test_invalid_changes_are_atomic_and_duplicate_has_no_second_action(signed, monkeypatch):
    client, service, _, model = signed
    trace = adaptive(monkeypatch, service, model)
    root, run, _ = start(client)
    value = until_change(client, service, root, run)
    supplied, result = trace["reconsideration_input"], trace["reconsideration_result"]
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        child = session.get(InvestigationBranch, value["exploration"]["changes"][0]["branch_id"])
        parent = session.get(InvestigationBranch, child.checkpoint["parent_branch_id"])
        before = deepcopy(saved.research_state)
        for mode in ("revision", "index", "old_source", "quote", "no_context"):
            invalid, context = deepcopy(result), deepcopy(supplied)
            gap = invalid["gaps"][0]
            if mode == "revision":
                gap["reconsideration"]["orientation_revision"] += 1
            elif mode == "index":
                gap["reconsideration"]["interpretation_index"] = 2
            elif mode == "old_source":
                gap["source_id"] = supplied["early_orientation"]["briefing"]["source_dependencies"][0]["source_id"]
            elif mode == "quote":
                gap["quote"] = "Invented later evidence"
            else:
                context.pop("early_orientation")
            # A valid first draft cannot mutate before an invalid second draft.
            invalid["gaps"].insert(0, {**deepcopy(result["gaps"][0]), "query": "A different valid query"})
            with pytest.raises(DomainError):
                research.apply_reflection(session, saved, parent, context, research.Reflection.model_validate(invalid))
            assert saved.research_state == before
        research.apply_reflection(session, saved, parent, supplied, research.Reflection.model_validate(result))
        assert len(saved.research_state["questions"]) == len(before["questions"])
        assert len(exploration.projection(session, saved)["changes"]) == 1


@pytest.mark.parametrize("constraint", ["depth", "branches"])
def test_budget_pending_change_does_not_claim_executed_research(signed, monkeypatch, constraint):
    client, service, _, model = signed
    trace = adaptive(monkeypatch, service, model)
    root, run, _ = start(client)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        state = deepcopy(saved.research_state)
        state["limits"][constraint] = 1 if constraint == "depth" else 3
        saved.research_state = state
        session.commit()
    final = complete(client, service, root + "/investigations", run)
    change = final["exploration"]["changes"][0]
    assert change["waiting_reason"] == ("depth_budget" if constraint == "depth" else "branch_budget")
    assert change["branch_id"] is None and change["status"] == "open"
    assert change["searches_completed"] == change["reads_completed"] == 0
    assert QUERY not in trace["queries"]


@pytest.mark.parametrize("when", ["during_reflection", "before_search", "after_completion"])
def test_all_input_dependencies_fence_new_work_and_derived_projection(signed, monkeypatch, when):
    client, service, identity, model = signed
    def callback(data, result):
        if when == "during_reflection":
            exclude(service, identity, data["early_orientation"]["briefing"]["source_dependencies"][0]["source_id"])
    trace = adaptive(monkeypatch, service, model, callback)
    root, run, _ = start(client)
    if when != "during_reflection":
        value = until_change(client, service, root, run)
        if when == "after_completion":
            value = complete(client, service, root + "/investigations", run)
        exclude(service, identity, value["exploration"]["orientation"]["briefing"]["source_dependencies"][0]["source_id"])
    value = complete(client, service, root + "/investigations", run)
    assert value["exploration"]["changes"] == []
    if when != "during_reflection":
        assert value["exploration"]["changes_unavailable"]
        assert value["research"] is None and value["branches"] == value["plans"] == []
        assert value["exploration"]["briefing"] is None
    if when == "before_search":
        assert value["status"] == "paused"
    if when != "after_completion":
        assert QUERY not in trace["queries"]
    assert "PRIVATE EXCLUSION" not in json.dumps(value["exploration"])


@pytest.mark.parametrize("kind", ["hash", "rights"])
def test_changed_capture_or_discovery_rights_stops_derived_search_and_private_input_stays_out(signed, monkeypatch, kind):
    client, service, _, model = signed
    trace = adaptive(monkeypatch, service, model)
    root, run, _ = start(client)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        session.add(InvestigationSource(dossier_id=saved.dossier_id, organization_id=saved.organization_id,
            investigation_id=saved.id, source_key="private", kind="uploaded_file", title="PRIVATE SENTINEL",
            url="", sha256="f" * 64, snapshot={"excerpts": [{"passage": "p1", "text": "PRIVATE SENTINEL"}]}))
        session.commit()
    value = until_change(client, service, root, run)
    assert "PRIVATE SENTINEL" not in json.dumps(trace)
    with service.db.session() as session:
        source = session.get(InvestigationSource, value["exploration"]["changes"][0]["source_id"])
        if kind == "hash":
            source.sha256 = "e" * 64
        else:
            source.snapshot = {**source.snapshot, "allow_discovery": False}
        session.commit()
    paused = complete(client, service, root + "/investigations", run)
    assert paused["status"] == "paused" and QUERY not in trace["queries"]
    assert paused["exploration"]["changes_unavailable"]
    assert paused["exploration"]["changes"] == []
    assert paused["research"] is None and paused["branches"] == paused["plans"] == []
