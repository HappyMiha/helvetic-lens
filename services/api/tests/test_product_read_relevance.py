"""Scripted passages exercise durable behavior, not live semantic accuracy."""

import hashlib
import json
from copy import deepcopy
from uuid import uuid4

import pytest
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude
from test_product_exploration import QUESTION, adapters, start
from test_product_investigations import tick
from test_product_iterative_research import RECIPIENT, complete
from test_product_source_recovery import projection

from helvetic_lens import decision_search, decision_sources
from helvetic_lens.models import Job
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from helvetic_lens.product_investigations import rows, scope


def setup(monkeypatch, service, model, mode="unrelated", during=None):
    trace = adapters(monkeypatch, service, model)
    search, read, call = decision_search.federated_retrieve, decision_sources.safe_inspect, model.complete
    trace.update(attempts=[], assessed_inputs=[])

    async def retrieve(*args):
        value = await search(*args)
        if args[1] == "Alpine Foundation legal identity":
            road, good = value["items"]
            value["items"] = [
                {**good, "id": f"misleading-{n}", "url": f"https://example.org/misleading-{n}"}
                for n in (1, 2)
            ] + [good, road]
        return value

    async def inspect(*args, **kwargs):
        url = args[2]["url"]
        trace["attempts"].append(url)
        if "misleading" not in url:
            return await read(*args, **kwargs)
        text = {
            "direct": "The registry identifies Alpine Foundation as a foundation in Switzerland.",
            "context": "The registry explains how legal identities of foundations are recorded.",
            "counterevidence": "The registry warns that Alpine Foundation is not the registered name of this entity.",
            "uncertain": "The extracted registry page omits the entity identification section.",
        }.get(
            mode,
            "This register entry identifies Alpine Paint, a paint manufacturer, rather than Alpine Foundation.",
        )
        text += " Record " + url.rsplit("-", 1)[-1] + "."
        return {
            "status": "complete",
            "url": url,
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "excerpts": [{"text": text, "passage": "p1"}],
            "text_truncated": False,
        }

    async def model_call(system, user, **kwargs):
        data = json.loads(user)
        if kwargs["response_schema"]["title"] != "ResearchExtraction":
            return await call(system, user, **kwargs)
        source = data["source"]
        fake = "Record " in source["excerpts"][0]["text"]
        value = (
            {"claims": [], "entities": [], "relationships": []}
            if fake
            else json.loads(await call(system, user, **kwargs))
        )
        if data.get("read_question"):
            trace["assessed_inputs"].append(data)
            if during:
                during(data)
            if fake and mode == "failure":
                raise RuntimeError("PRIVATE MODEL ERROR CANARY")
            if fake and mode == "missing":
                return json.dumps(value)
            category = mode if mode in {"direct", "context", "counterevidence", "uncertain"} else "unrelated"
            if not fake:
                category = "counterevidence" if source["excerpts"][0]["text"] == RECIPIENT else "direct"
            value["read_relevance"] = {
                "source_id": str(uuid4()) if fake and mode == "invalid_source" else source["id"],
                "question_id": str(uuid4())
                if fake and mode == "invalid_question"
                else data["read_question"]["question_id"],
                "category": category,
                "quote": "INVENTED UNSUPPLIED PASSAGE"
                if fake and mode == "invalid_quote"
                else source["excerpts"][0]["text"],
                "locator": "p1",
                "reason": "The cited passage concerns the selected question with the indicated limits.",
                "limitations": ["incomplete"]
                if fake and mode == "incomplete"
                else ["entity"]
                if category == "unrelated"
                else [],
            }
        return json.dumps(value)

    monkeypatch.setattr(decision_search, "federated_retrieve", retrieve)
    monkeypatch.setattr(decision_sources, "safe_inspect", inspect)
    monkeypatch.setattr(model, "complete", model_call)
    return trace


def relevance(value):
    return value["exploration"]["research_scope"]["read_relevance"]


def until_next_candidate(service, run):
    for _ in range(25):
        tick(service, run["id"])
        with service.db.session() as session:
            saved = session.get(Investigation, run["id"])
            branch = next(
                (
                    b
                    for b in rows(session, InvestigationBranch, saved)
                    if "first_alternative_step" in b.checkpoint.get("read_relevance", {})
                ),
                None,
            )
            if branch:
                return branch.id
    raise AssertionError("No assessment-directed candidate checkpoint")


@pytest.mark.parametrize("product", ["legal", "pharma"])
def test_read_passages_change_actual_work_and_remain_auditable(signed, monkeypatch, product):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client, product)
    value = complete(client, service, root + "/investigations", run)
    assessed = relevance(value)
    assert value["exploration"]["status"] == "ready" and value["question"] == QUESTION
    assert len(trace["queries"]) == 3  # only existing planned/reflected searches
    assert len(trace["attempts"]) == len(set(trace["attempts"])) == 5
    assert "https://example.org/identity" in trace["attempts"]
    assert assessed["alternative_reads"] == 1 and assessed["unfinished"] == 0
    assert len(assessed["assessments"]) == 5 and assessed["unassessed"] == 0
    assert sum(a["category"] == "unrelated" for a in assessed["assessments"]) == 2
    assert any(a["category"] == "counterevidence" for a in assessed["assessments"])
    assert value["exploration"]["research_scope"]["source_recovery"]["failed_reads"] == 0
    assert trace["briefings"][-1]["research_scope"]["read_relevance"] == assessed
    assert {a["source_id"] for a in assessed["assessments"]} <= {
        s["id"] for s in value["exploration"]["sources"]
    }
    assert value["claims"][0]["status"] == "CONTESTED"
    assert client.get(root + "/web-research").json()["policy"]["enabled"] is False
    assert client.get(root + "/investigations").json()["total"] == 1


@pytest.mark.parametrize(
    "mode",
    [
        "direct",
        "context",
        "counterevidence",
        "uncertain",
        "missing",
        "incomplete",
        "failure",
        "invalid_source",
        "invalid_question",
        "invalid_quote",
        "legacy",
    ],
)
def test_no_claims_or_missing_invalid_uncertain_assessment_never_means_unrelated(signed, monkeypatch, mode):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model, mode)
    root, run, _ = start(client)
    if mode == "legacy":
        with service.db.session() as session:
            saved = session.get(Investigation, run["id"])
            data = deepcopy(saved.research_state)
            data["exploration"].pop("read_relevance_contract")
            saved.research_state = data
            session.commit()
    value = complete(client, service, root + "/investigations", run)
    assert "https://example.org/identity" not in trace["attempts"]
    assert sum("misleading" in s["url"] for s in value["exploration"]["sources"]) == 2
    assessed = relevance(value)
    if mode == "legacy":
        assert assessed["status"] == "unknown" and not trace["assessed_inputs"]
    else:
        assert assessed["alternative_reads"] == 0
        if mode in {"missing", "failure", "invalid_source", "invalid_question", "invalid_quote"}:
            assert assessed["unassessed"] == 2
        else:
            assert assessed["unassessed"] == 0
    assert "INVENTED UNSUPPLIED" not in json.dumps(value)
    assert "PRIVATE MODEL ERROR" not in json.dumps(value)


@pytest.mark.parametrize("resource", ["source_fetches", "decision_calls", "model_calls", "active_seconds"])
def test_assessment_cannot_expand_existing_budgets(signed, monkeypatch, resource):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client)
    until_next_candidate(service, run)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        data = deepcopy(saved.research_state)
        data["used"][resource] = data["limits"][resource] - int(resource == "model_calls")
        saved.research_state = data
        session.commit()
    if resource == "model_calls":
        from helvetic_lens import product_iterative_steps

        async def uncertain(*args):
            return {"verdict": "uncertain", "engine": "fixture", "basis": "Needs existing model escalation"}

        monkeypatch.setattr(product_iterative_steps, "evaluate", uncertain)
    value = complete(client, service, root + "/investigations", run)
    assert "https://example.org/identity" not in trace["attempts"]
    assert resource in value["research"]["stops"]
    assert relevance(value)["unfinished"] > 0


@pytest.mark.parametrize("action", ["pause", "cancel"])
def test_control_fences_new_reading(signed, monkeypatch, action):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client)
    until_next_candidate(service, run)
    url = root + "/investigations/" + run["id"]
    value = client.get(url).json()
    stopped = post(client, url + "/control", {"action": action, "expected_revision": value["revision"]})
    assert stopped.status_code == 200
    count = len(trace["attempts"])
    tick(service, run["id"])
    assert len(trace["attempts"]) == count
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
        assert relevance(value)["alternative_reads"] == 1


@pytest.mark.parametrize("mode", ["excluded", "changed"])
def test_revoked_assessment_input_hides_output_and_stops_dependent_work(signed, monkeypatch, mode):
    client, service, identity, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client)
    until_next_candidate(service, run)
    view = projection(service, run)
    source_id = view["research_scope"]["read_relevance"]["assessments"][0]["source_id"]
    if mode == "excluded":
        exclude(service, identity, source_id)
    else:
        with service.db.session() as session:
            session.get(InvestigationSource, source_id).sha256 = "changed-version"
            session.commit()
    tick(service, run["id"])
    value = client.get(root + "/investigations/" + run["id"]).json()
    assert value["status"] == "paused"
    assert value["exploration"]["research_scope"]["status"] == "evidence_changed"
    assert "read_relevance" not in value["exploration"]["research_scope"]
    assert "https://example.org/identity" not in trace["attempts"]


def test_interrupted_assessment_is_not_replayed(signed, monkeypatch):
    client, service, _, model = signed
    seen = []

    def interrupt(data):
        if seen:
            return
        seen.append(data["source"]["id"])
        with service.db.session() as session:
            source = session.get(InvestigationSource, seen[0])
            job = session.get(Job, session.get(Investigation, source.investigation_id).job_id)
            job.state, job.lease_owner = "queued", None
            session.commit()

    trace = setup(monkeypatch, service, model, during=interrupt)
    root, run, _ = start(client)
    value = complete(client, service, root + "/investigations", run)
    assert sum(d["source"]["id"] == seen[0] for d in trace["assessed_inputs"]) == 1
    assert seen[0] not in {a["source_id"] for a in relevance(value)["assessments"]}
    assert relevance(value)["unassessed"] == 1


def test_private_saved_material_never_enters_read_assessment(signed, monkeypatch):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        session.add(
            InvestigationSource(
                **scope(saved),
                kind="uploaded_file",
                title="PRIVATE READ CANARY",
                url="",
                source_key=str(uuid4()),
                sha256="private",
                snapshot={
                    "allow_discovery": False,
                    "excerpts": [{"passage": "private", "text": "PRIVATE READ CANARY"}],
                },
            )
        )
        session.commit()
    value = complete(client, service, root + "/investigations", run)
    assert trace["assessed_inputs"] and "PRIVATE READ CANARY" not in json.dumps(trace)
    assert "PRIVATE READ CANARY" not in json.dumps(relevance(value))
