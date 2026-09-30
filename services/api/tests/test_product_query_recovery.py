"""Durable recovery fixtures exercise mechanics, not live semantic accuracy."""

import json
from copy import deepcopy
from uuid import uuid4

import pytest
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude
from test_product_exploration import QUESTION, adapters, start
from test_product_investigations import tick
from test_product_iterative_research import complete
from test_product_source_recovery import projection

from helvetic_lens import decision_search, product_iterative_steps
from helvetic_lens.models import Job
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from helvetic_lens.product_investigations import rows
from helvetic_lens.product_models import DossierEntry

ORIGINAL = "Alpine Foundation legal identity"
ALTERNATIVE = "Alpine Foundation registry legal identity"


def setup(monkeypatch, service, model, mode="empty"):
    trace = adapters(monkeypatch, service, model)
    retrieve, model_call, gate = (
        decision_search.federated_retrieve,
        model.complete,
        product_iterative_steps.evaluate,
    )
    trace["reformulations"] = []

    async def search(*args):
        result = await retrieve(*args)
        if args[1] == ORIGINAL or mode == "all_empty":
            if mode == "outage":
                raise RuntimeError("PRIVATE PROVIDER CANARY")
            if mode in {"unrelated", "gate_unavailable", "cap"}:
                road = result["items"][0]
                result["items"] = (
                    [road]
                    if mode != "cap"
                    else [{**road, "id": str(n), "url": f"https://example.org/road{n}"} for n in range(10)]
                )
            elif mode != "excluded":
                result["items"] = []
            if mode == "partial":
                result["lanes"].append({"status": "unavailable", "name": "missing"})
            if mode == "unknown":
                result.pop("lanes")
            if mode == "omitted":
                result["omitted_records"] = 1
        return result

    async def evaluate(*args):
        if mode == "gate_unavailable" and args[2] == ORIGINAL:
            return {"verdict": "unavailable", "engine": "fixture", "basis": "unavailable"}
        return await gate(*args)

    async def call(system, user, **kwargs):
        if kwargs["response_schema"]["title"] != "QueryReformulation":
            return await model_call(system, user, **kwargs)
        data = json.loads(user)
        trace["reformulations"].append(data)
        if mode == "model_failure":
            raise RuntimeError("PRIVATE MODEL CANARY")
        return json.dumps(
            {
                "query": ORIGINAL.upper() + " !!!"
                if mode == "duplicate"
                else None
                if mode == "null"
                else ALTERNATIVE
            }
        )

    monkeypatch.setattr(decision_search, "federated_retrieve", search)
    monkeypatch.setattr(product_iterative_steps, "evaluate", evaluate)
    monkeypatch.setattr(model, "complete", call)
    return trace


def recovery(value):
    return value["exploration"]["research_scope"]["query_recovery"]


def until_reformulation(service, run):
    for _ in range(15):
        tick(service, run["id"])
        with service.db.session() as session:
            saved = session.get(Investigation, run["id"])
            branch = next(
                (b for b in rows(session, InvestigationBranch, saved) if b.phase == "reformulate"), None
            )
            if branch:
                return branch.id
    raise AssertionError("No reformulation checkpoint")


@pytest.mark.parametrize("product,mode", [("legal", "empty"), ("pharma", "unrelated")])
def test_unproductive_query_recovers_exact_evidence_and_keeps_intent(signed, monkeypatch, product, mode):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model, mode)
    root, run, _ = start(client, product)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        session.add(
            InvestigationSource(
                dossier_id=saved.dossier_id,
                organization_id=saved.organization_id,
                investigation_id=saved.id,
                source_key="private",
                kind="uploaded_file",
                title="PRIVATE TITLE CANARY",
                url="",
                sha256="a" * 64,
                snapshot={"excerpts": [{"passage": "p1", "text": "PRIVATE TEXT CANARY"}]},
            )
        )
        session.commit()
    original_call = model.complete
    activities = []

    async def inspect(system, user, **kwargs):
        if kwargs["response_schema"]["title"] == "QueryReformulation":
            activities.append(projection(service, run)["current_activity"])
        return await original_call(system, user, **kwargs)

    monkeypatch.setattr(model, "complete", inspect)
    value = complete(client, service, root + "/investigations", run)
    result = recovery(value)
    assert value["question"] == QUESTION and value["exploration"]["status"] == "ready"
    assert result["query"] == ALTERNATIVE and result["original_query"] == ORIGINAL
    assert result["searches_completed"] == 1 and result["captures"] == 1 and not result["unfinished"]
    assert activities[0]["phase"] == "reformulate" and activities[0]["status"] == "working"
    assert len(trace["reformulations"]) == 1 and trace["queries"].count(ALTERNATIVE) == 1
    assert "PRIVATE" not in json.dumps(trace["reformulations"])
    assert value["exploration"]["research_scope"]["searches"]["completed"] == len(trace["queries"]) == 4
    assert value["exploration"]["research_scope"]["indexes"]["completed"] == 4
    assert value["exploration"]["research_scope"]["candidates"]["retrieved"] == (
        7 if mode == "unrelated" else 6
    )
    assert trace["briefings"][-1]["research_scope"]["query_recovery"] == result
    assert any(s["url"].endswith("/identity") for s in value["exploration"]["sources"])
    assert all(
        f["source_id"] in {s["id"] for s in value["exploration"]["sources"]}
        for f in value["exploration"]["briefing"]["findings"]
    )
    assert client.get(root + "/web-research").json()["policy"]["enabled"] is False
    assert client.get(root + "/investigations").json()["total"] == 1
    with service.db.session() as session:
        b = session.get(InvestigationBranch, until_id(value))
        assert b.query == ORIGINAL and b.checkpoint["query_recovery"]["prior"]["coverage"]


def until_id(value):
    return next(b["id"] for b in value["branches"] if b["query"] == ORIGINAL)


@pytest.mark.parametrize(
    "mode",
    [
        "all_empty",
        "duplicate",
        "null",
        "model_failure",
        "outage",
        "partial",
        "unknown",
        "omitted",
        "cap",
        "gate_unavailable",
        "legacy",
        "excluded",
    ],
)
def test_empty_failure_access_and_duplicate_results_do_not_loop(signed, monkeypatch, mode):
    client, service, identity, model = signed
    trace = setup(monkeypatch, service, model, mode)
    root, run, _ = start(client)
    if mode in {"legacy", "excluded"}:
        with service.db.session() as session:
            saved = session.get(Investigation, run["id"])
            if mode == "legacy":
                data = deepcopy(saved.research_state)
                data["exploration"].pop("query_recovery_contract")
                saved.research_state = data
            else:
                session.add(
                    DossierEntry(
                        dossier_id=saved.dossier_id,
                        organization_id=saved.organization_id,
                        request_key=str(uuid4()),
                        kind="source_review",
                        actor_user_id=identity["user"]["id"],
                        url="https://example.org/identity",
                        body="PRIVATE REVIEW CANARY",
                        data_json={"decision": "exclude", "revision": 1},
                    )
                )
            session.commit()
    value = complete(client, service, root + "/investigations", run)
    expected = mode in {"all_empty", "duplicate", "null", "model_failure"}
    assert len(trace["reformulations"]) == int(expected)
    assert trace["queries"].count(ALTERNATIVE) == int(mode == "all_empty")
    if mode == "all_empty":
        assert value["exploration"]["briefing"] is None and recovery(value)["captures"] == 0
    if mode in {"duplicate", "null"}:
        assert recovery(value)["outcome"] == "no_alternative"
    if mode == "model_failure":
        assert recovery(value)["proposal_unavailable"]
    if mode == "legacy":
        assert recovery(value)["status"] == "unknown"
    assert "PRIVATE MODEL CANARY" not in json.dumps(value)
    assert "PRIVATE PROVIDER CANARY" not in json.dumps(value)


@pytest.mark.parametrize("resource", ["model_calls", "search_requests", "active_seconds"])
def test_reformulation_keeps_existing_budget(signed, monkeypatch, resource):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client)
    until_reformulation(service, run)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        data = deepcopy(saved.research_state)
        data["used"][resource] = data["limits"][resource] - int(resource == "model_calls")
        saved.research_state = data
        session.commit()
    value = complete(client, service, root + "/investigations", run)
    assert resource in value["research"]["stops"] and ALTERNATIVE not in trace["queries"]
    assert recovery(value)["unfinished"] and not recovery(value)["captures"]


@pytest.mark.parametrize("action", ["pause", "cancel"])
def test_control_before_reformulation(signed, monkeypatch, action):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client)
    until_reformulation(service, run)
    url = root + "/investigations/" + run["id"]
    value = client.get(url).json()
    stopped = post(client, url + "/control", {"action": action, "expected_revision": value["revision"]})
    assert stopped.status_code == 200
    tick(service, run["id"])
    assert not trace["reformulations"]
    if action == "pause":
        assert (
            post(
                client,
                url + "/control",
                {"action": "resume", "expected_revision": stopped.json()["revision"]},
            ).status_code
            == 200
        )
        value = complete(client, service, root + "/investigations", run)
        assert recovery(value)["captures"] == 1


def test_interrupted_reformulation_is_not_replayed(signed, monkeypatch):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client)
    base = model.complete

    async def interrupted(system, user, **kwargs):
        result = await base(system, user, **kwargs)
        if kwargs["response_schema"]["title"] == "QueryReformulation":
            with service.db.session() as session:
                job = session.get(Job, session.get(Investigation, run["id"]).job_id)
                job.state, job.lease_owner = "queued", None
                session.commit()
        return result

    monkeypatch.setattr(model, "complete", interrupted)
    value = complete(client, service, root + "/investigations", run)
    assert len(trace["reformulations"]) == 1 and ALTERNATIVE not in trace["queries"]
    assert recovery(value)["proposal_unavailable"]


def test_revoked_alternate_capture_hides_recovery(signed, monkeypatch):
    client, service, identity, model = signed
    setup(monkeypatch, service, model)
    root, run, _ = start(client)
    value = complete(client, service, root + "/investigations", run)
    source = next(s for s in value["exploration"]["sources"] if s["url"].endswith("/identity"))
    exclude(service, identity, source["id"])
    value = client.get(root + "/investigations/" + run["id"]).json()
    assert value["exploration"]["research_scope"]["status"] == "evidence_changed"
    assert "query_recovery" not in value["exploration"]["research_scope"]
