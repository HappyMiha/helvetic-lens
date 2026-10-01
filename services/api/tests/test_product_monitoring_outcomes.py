"""Scheduled results through the real worker and authorized reader; fictional sources."""
import json
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_exploration import adapters, start
from test_product_investigations import complete
from test_product_iterative_research import complete as finish_exploration
from test_product_web_research import FIRST, QUESTION, SECOND, URL, due, enable, newest, pipeline, setup

from helvetic_lens import decision_search, decision_sources
from helvetic_lens.product_investigation_models import (
    ClaimChange,
    DossierClaim,
    Investigation,
    InvestigationSource,
)
from helvetic_lens.product_models import DossierEntry


def result(client, root):
    response = client.get(root + "/web-research")
    assert response.status_code == 200, response.text
    assert "no-store" in response.headers["cache-control"]
    return response.json()["items"][0]["outcome"]


def check(client, service, root):
    assert due(service, next_day=True)["started"] == 1
    return complete(client, service, root + "/investigations", newest(client, root))


@pytest.mark.parametrize("product", ["legal", "pharma"])
def test_understood_question_to_consent_and_cited_monitoring_result(signed, monkeypatch, product):
    client, service, _, model = signed
    service.settings.decision_search_daily_limit = 100
    adapters(monkeypatch, service, model)
    root, run, _ = start(client, product)
    brief = finish_exploration(client, service, root + "/investigations", run)
    assert brief["exploration"]["status"] == "ready"
    assert not client.get(root + "/web-research").json()["policy"]["enabled"]
    trace = pipeline(monkeypatch, service, model)
    # The user's chosen public wording remains the complete search authority.
    _, command = enable(client, root, question=QUESTION)
    assert post(client, root + "/web-research", command).status_code == 200
    first = check(client, service, root)
    one = result(client, root)
    assert one["state"] == "completed" and one["finding_state"] == "findings"
    assert one["findings"][0]["evidence"]["quote"] == FIRST
    same = check(client, service, root)
    unchanged = result(client, root)
    assert unchanged["finding_state"] == "unchanged" and not unchanged["findings"]
    assert same["sources"][0]["snapshot"]["unchanged_from"] == first["sources"][0]["id"]
    trace["text"] = SECOND
    changed = check(client, service, root)
    outcome = result(client, root)
    assert outcome["state"] == "completed" and outcome["finding_state"] == "changes"
    pair = outcome["comparisons"][0]
    assert pair["previous"]["evidence"]["quote"] == FIRST
    assert pair["current"]["evidence"]["quote"] == SECOND
    assert pair["current"]["investigation_id"] == changed["id"]
    assert len(trace["queries"]) == len(trace["reads"]) == 3
    assert len(trace["analysis"]) == 4  # Two extractions and existing comparisons with earlier research.
    assert all(q[0] == QUESTION for q in trace["queries"])
    before = json.dumps(trace)
    exported = client.get(root + "/export").json()["web_research"]["items"]
    assert next(item for item in exported if item["investigation"]["id"] == changed["id"])["outcome"] == outcome
    assert result(client, root) == outcome and json.dumps(trace) == before
    client.cookies.clear()
    assert client.get(root + "/web-research").status_code == 401


@pytest.mark.parametrize("failure", ["empty", "search", "read", "extract", "partial_read"])
def test_no_evidence_and_failures_have_distinct_results(signed, monkeypatch, failure):
    client, service, _, model = signed
    _, root = setup(client)
    trace = pipeline(monkeypatch, service, model)
    if failure == "empty":
        trace["empty"] = True
    elif failure == "search":
        trace["failure"] = True
    elif failure == "extract":
        async def broken(*args, **kwargs):
            raise RuntimeError("PRIVATE ERROR DETAIL")
        monkeypatch.setattr(model, "complete", broken)
    else:
        search, inspect = decision_search.execute, decision_sources.safe_inspect
        async def two_sources(*args, **kwargs):
            value = await search(*args, **kwargs)
            value["items"].append({"id": "b", "title": "Unavailable source", "url": URL + "/unavailable"})
            return value
        async def broken_read(settings, query, item, mode, **kwargs):
            if failure == "read" or item["url"].endswith("/unavailable"):
                return {"status": "unavailable", "error": "PRIVATE ERROR DETAIL"}
            return await inspect(settings, query, item, mode)
        monkeypatch.setattr(decision_sources, "safe_inspect", broken_read)
        if failure == "partial_read":
            monkeypatch.setattr(decision_search, "execute", two_sources)
    enable(client, root)
    check(client, service, root)
    outcome = result(client, root)
    assert "PRIVATE" not in json.dumps(outcome)
    if failure == "empty":
        assert outcome["state"] == "completed" and outcome["finding_state"] == "no_matches"
        assert not outcome["limitations"]
    else:
        assert outcome["state"] == ("partial" if failure == "partial_read" else "failed")
        assert outcome["limitations"] and outcome["finding_state"] != "unchanged"
        assert bool(outcome["findings"]) == (failure == "partial_read")


@pytest.mark.parametrize("mutation", ["exclude", "quote", "earlier_quote", "question", "revision", "dismiss", "claim"])
def test_result_rechecks_source_claim_question_and_relationship(signed, monkeypatch, mutation):
    client, service, _, model = signed
    doc, root = setup(client)
    trace = pipeline(monkeypatch, service, model)
    enable(client, root)
    first = check(client, service, root)
    trace["text"] = SECOND
    second = check(client, service, root)
    assert result(client, root)["comparisons"]
    with service.db.session() as session:
        if mutation == "exclude":
            session.add(DossierEntry(dossier_id=doc["id"], request_key=str(uuid4()), kind="source_review",
                url=URL, body="PRIVATE REASON", data_json={"decision": "exclude", "revision": 1}))
        elif mutation in {"quote", "earlier_quote"}:
            run = second if mutation == "quote" else first
            source = session.get(InvestigationSource, run["sources"][0]["id"])
            source.snapshot = {**source.snapshot, "excerpts": [{"passage": "p1", "text": "Replacement capture"}]}
        elif mutation == "question":
            session.get(Investigation, first["id"]).question = "Different earlier question"
        elif mutation == "revision":
            session.get(DossierClaim, first["claims"][0]["id"]).revision += 1
        elif mutation == "claim":
            session.get(DossierClaim, second["claims"][0]["id"]).status = "DISPROVED"
        else:
            session.scalar(select(ClaimChange)).status = "dismissed"
        session.commit()
    outcome = result(client, root)
    assert not outcome["comparisons"]
    if mutation in {"exclude", "quote", "claim"}:
        assert not outcome["findings"]
    if mutation == "exclude":
        assert outcome["state"] == "unavailable" and "PRIVATE REASON" not in json.dumps(outcome)
        assert FIRST not in json.dumps(outcome) and SECOND not in json.dumps(outcome)


@pytest.mark.parametrize("status", ["queued", "running", "paused", "cancelled"])
def test_unfinished_check_never_projects_a_completed_result(signed, monkeypatch, status):
    client, service, _, model = signed
    _, root = setup(client)
    pipeline(monkeypatch, service, model)
    enable(client, root)
    run = check(client, service, root)
    with service.db.session() as session:
        session.get(Investigation, run["id"]).status = status
        session.commit()
    outcome = result(client, root)
    assert outcome["state"] == status and outcome["finding_state"] == "pending"
    assert not outcome["findings"] and not outcome["comparisons"]


def test_failed_comparison_keeps_new_evidence_and_marks_the_check_incomplete(signed, monkeypatch):
    client, service, _, model = signed
    _, root = setup(client)
    trace = pipeline(monkeypatch, service, model)
    enable(client, root)
    check(client, service, root)
    base = model.complete
    async def compare_unavailable(system, user, **kwargs):
        if "current" in json.loads(user):
            raise RuntimeError("PRIVATE COMPARISON ERROR")
        return await base(system, user, **kwargs)
    monkeypatch.setattr(model, "complete", compare_unavailable)
    trace["text"] = SECOND
    check(client, service, root)
    outcome = result(client, root)
    assert outcome["state"] == "partial" and outcome["finding_state"] == "findings"
    assert outcome["findings"][0]["evidence"]["quote"] == SECOND
    assert "Comparison with earlier findings was not completed." in outcome["limitations"]
    assert not outcome["comparisons"] and "PRIVATE COMPARISON" not in json.dumps(outcome)
