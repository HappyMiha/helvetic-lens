"""Actual check receipts through native workers and authorized readers; fictional only."""
import json
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_investigations import complete, tick
from test_product_monitoring_outcomes import check, result
from test_product_web_research import QUESTION, SECOND, URL, due, enable, newest, pipeline, setup

from helvetic_lens import decision_search, decision_sources
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from helvetic_lens.product_models import DossierEntry


def coverage(client, root):
    return result(client, root)["source_coverage"]


@pytest.mark.parametrize("product", ["legal", "pharma"])
def test_check_identifies_first_unchanged_changed_and_unchecked_sources(signed, monkeypatch, product):
    client, service, _, model = signed
    _, root = setup(client, product)
    trace = pipeline(monkeypatch, service, model)
    enable(client, root)
    first = check(client, service, root)
    one = coverage(client, root)
    item = one["sources"][0]
    assert item["capture_state"] == "first_capture" and item["analysis_status"] == "analysed"
    assert item["attempt"]["started_at"] <= item["attempt"]["finished_at"] <= item["last_success_at"]
    assert item["source_id"] == first["sources"][0]["id"] and item["url"] == URL
    check(client, service, root)
    same = coverage(client, root)["sources"][0]
    assert same["capture_state"] == "unchanged" and same["analysis_status"] == "not_needed"
    assert same["last_success_at"] == item["last_success_at"]
    trace["text"] = SECOND
    check(client, service, root)
    changed = coverage(client, root)["sources"][0]
    assert changed["capture_state"] == "changed" and changed["analysis_status"] == "analysed"
    assert changed["last_success_at"] > item["last_success_at"]
    trace["empty"] = True
    last = check(client, service, root)
    missing = coverage(client, root)
    assert missing["search"]["status"] == "completed"
    assert missing["sources"][0]["read_status"] == "not_checked"
    assert missing["sources"][0]["attempt"] is None
    assert missing["sources"][0]["source_id"] == changed["source_id"]
    assert len(trace["queries"]) == 4 and len(trace["reads"]) == len(trace["analysis"]) == 3
    assert all(q[0] == QUESTION for q in trace["queries"])
    before = json.dumps(trace)
    exported = client.get(root + "/export").json()["web_research"]["items"]
    assert next(i for i in exported if i["investigation"]["id"] == last["id"])["outcome"]["source_coverage"] == missing
    assert coverage(client, root) == missing and json.dumps(trace) == before
    old = client.get(root + "/web-research").json()["items"][-1]["outcome"]["source_coverage"]
    assert old == one  # Later checks cannot extend the earlier receipt.


@pytest.mark.parametrize("failure", ["search", "read", "extract", "partial_read"])
def test_source_failures_do_not_invent_success_or_raw_errors(signed, monkeypatch, failure):
    client, service, _, model = signed
    _, root = setup(client)
    trace = pipeline(monkeypatch, service, model)
    search, inspect = decision_search.execute, decision_sources.safe_inspect
    if failure == "search":
        trace["failure"] = True
    elif failure == "extract":
        async def broken(*args, **kwargs):
            raise RuntimeError("SECRET PROVIDER ERROR")
        monkeypatch.setattr(model, "complete", broken)
    else:
        async def candidates(*args, **kwargs):
            value = await search(*args, **kwargs)
            value["items"].append({"url": URL + "/failed", "title": "Failed page"})
            return value
        async def read(settings, query, item, mode):
            if failure == "read" or item["url"].endswith("/failed"):
                return {"status": "unavailable", "error": "SECRET PROVIDER ERROR"}
            return await inspect(settings, query, item, mode)
        monkeypatch.setattr(decision_sources, "safe_inspect", read)
        if failure == "partial_read":
            monkeypatch.setattr(decision_search, "execute", candidates)
    enable(client, root)
    check(client, service, root)
    value = coverage(client, root)
    assert "SECRET" not in json.dumps(value)
    if failure == "search":
        assert value["search"]["status"] == "unavailable" and not value["sources"]
    elif failure == "extract":
        item = value["sources"][0]
        assert item["read_status"] == "read" and item["analysis_status"] == "failed"
        assert item["last_success_at"] is None
        assert item["analysis_attempt"]["finished_at"]
    else:
        bad = value["sources"][-1]
        assert bad["read_status"] == "failed" and bad["attempt"]["finished_at"]
        assert bad["last_success_at"] is None and bad["source_id"] is None
        if failure == "partial_read":
            assert value["sources"][0]["analysis_status"] == "analysed"
            assert result(client, root)["state"] == "partial"


@pytest.mark.parametrize("mutation", ["exclude", "remove", "earlier_question", "different_question", "legacy"])
def test_receipts_respect_current_source_scope_and_legacy(signed, monkeypatch, mutation):
    client, service, _, model = signed
    doc, root = setup(client)
    trace = pipeline(monkeypatch, service, model)
    enable(client, root)
    first = check(client, service, root)
    trace["empty"] = True
    if mutation == "different_question":
        enable(client, root, question="Different public question")
    later = check(client, service, root)
    with service.db.session() as session:
        if mutation == "exclude":
            session.add(DossierEntry(dossier_id=doc["id"], request_key=str(uuid4()), kind="source_review",
                url=URL, body="SECRET EXCLUSION", data_json={"decision": "exclude", "revision": 1}))
        elif mutation == "remove":
            session.delete(session.get(InvestigationSource, first["sources"][0]["id"]))
        elif mutation == "earlier_question":
            session.get(Investigation, first["id"]).question = "Replacement earlier question"
        elif mutation == "legacy":
            branch = session.scalar(select(InvestigationBranch).where(InvestigationBranch.investigation_id == later["id"]))
            branch.checkpoint = {k: v for k, v in branch.checkpoint.items() if k != "source_coverage"}
        session.commit()
    value = coverage(client, root)
    assert not value["sources"] and URL not in json.dumps(value) and "SECRET" not in json.dumps(value)
    if mutation == "legacy":
        assert not value["recorded"] and "not recorded" in value["scope"]
    elif mutation != "different_question":
        assert value["prior_hidden"] == 1
    client.cookies.clear()
    assert client.get(root + "/web-research").status_code == 401


def test_excluded_failed_candidate_is_redacted_even_without_a_capture(signed, monkeypatch):
    client, service, _, model = signed
    doc, root = setup(client)
    pipeline(monkeypatch, service, model)
    async def fail(*args, **kwargs):
        return {"status": "unavailable"}
    monkeypatch.setattr(decision_sources, "safe_inspect", fail)
    enable(client, root)
    check(client, service, root)
    with service.db.session() as session:
        session.add(DossierEntry(dossier_id=doc["id"], request_key=str(uuid4()), kind="source_review",
            url=URL, data_json={"decision": "exclude", "revision": 1}))
        session.commit()
    value = coverage(client, root)
    assert value["sources"][0]["read_status"] == "unavailable"
    assert URL not in json.dumps(value) and "Public registry" not in json.dumps(value)


def test_interrupted_read_is_not_checked_successfully_and_retry_keeps_attempt_count(signed, monkeypatch):
    client, service, _, model = signed
    _, root = setup(client)
    trace = pipeline(monkeypatch, service, model)
    enable(client, root)
    due(service)
    run = newest(client, root)
    assert "source_coverage" not in result(client, root)
    tick(service, run["id"])  # Seed.
    tick(service, run["id"])  # Search.
    assert coverage(client, root)["sources"][0]["read_status"] == "not_checked"
    with service.db.session() as session:
        branch = session.scalar(select(InvestigationBranch).where(InvestigationBranch.investigation_id == run["id"]))
        state = dict(branch.checkpoint)
        state["inflight"] = "lost-worker"
        state["steps"] = [*state["steps"], {"id": "lost-worker", "phase": "read", "status": "running",
            "source_url": URL, "started_at": "2026-09-30T00:00:00+00:00"}]
        branch.checkpoint = state
        session.commit()
    finished = complete(client, service, root + "/investigations", run)
    value = coverage(client, root)["sources"][0]
    assert value["read_status"] == "interrupted" and value["attempt"]["finished_at"]
    assert not trace["reads"] and not trace["analysis"]
    # The existing retry implementation owns retry selection; keep receipt history.
    with service.db.session() as session:
        branch = session.scalar(select(InvestigationBranch).where(InvestigationBranch.investigation_id == run["id"]))
        assert branch.checkpoint["steps"][-1]["status"] == "interrupted"
    assert value["attempt_count"] == 1
    response = post(client, root + f"/investigations/{run['id']}/control",
        {"action": "retry", "expected_revision": finished["revision"]})
    assert response.status_code == 200, response.text
    complete(client, service, root + "/investigations", run)
    retried = coverage(client, root)["sources"][0]
    assert retried["read_status"] == "read" and retried["attempt_count"] == 2
    assert len(trace["queries"]) == 1 and len(trace["reads"]) == 1


def test_lookback_is_bounded_and_pinned_before_later_sources_exist(signed, monkeypatch):
    client, service, _, model = signed
    _, root = setup(client)
    trace = pipeline(monkeypatch, service, model)
    enable(client, root)
    first = check(client, service, root)
    with service.db.session() as session:
        original = session.get(InvestigationSource, first["sources"][0]["id"])
        for index in range(15):
            session.add(InvestigationSource(dossier_id=original.dossier_id, investigation_id=original.investigation_id,
                organization_id=original.organization_id, kind="public_source", source_key=f"extra-{index}",
                title=f"Earlier fictional page {index}", url=f"https://example.org/prior/{index}",
                sha256=original.sha256, snapshot=dict(original.snapshot)))
        session.commit()
    trace["empty"] = True
    check(client, service, root)
    value = coverage(client, root)
    assert value["prior_truncated"] and len(value["sources"]) == value["prior_limit"] == 12
    assert all(s["read_status"] == "not_checked" and s["attempt"] is None for s in value["sources"])
    assert len(trace["reads"]) == len(trace["analysis"]) == 1
