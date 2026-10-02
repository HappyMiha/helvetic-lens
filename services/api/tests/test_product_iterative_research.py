"""Real coordinator, controlled external adapters: multi-hop evidence, not a live-provider evaluation."""
import hashlib
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from test_product_dossiers import ROOT, post
from test_product_dossiers import signed as signed
from test_product_investigations import tick

from helvetic_lens import decision_engines, decision_search, decision_sources, jobs, product_iterative_steps
from helvetic_lens.db import utcnow
from helvetic_lens.models import Job, OrganizationMembership
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch
from helvetic_lens.product_iterative_research import Limits

QUESTION = "Investigate Alpine Foundation funding, recipients, amounts, periods and documentary evidence."
IDENTITY = "The Registry of Switzerland identifies Alpine Foundation as CH-100, a foundation established in Switzerland."
GRANT = "Alpine Foundation, Registry of Switzerland CH-100, granted CHF 50,000 to River Trust, Registry of Switzerland CH-200, in 2024."
RECIPIENT = "River Trust, Registry of Switzerland CH-200, reports receiving CHF 40,000 from Alpine Foundation, Registry of Switzerland CH-100, in 2024."
STATEMENT = "Alpine Foundation granted CHF 50,000 to River Trust in 2024."


def start(client, limits=None, product="pharma", question=QUESTION):
    base = ROOT.replace("pharma", product)
    created = post(client, base, {"creation_key": str(uuid4()), "config": {"name": "Foundation evidence fixture", "goal": QUESTION}})
    assert created.status_code == 201, created.text
    doc = created.json()
    root = f"{base}/{doc['id']}/investigations"
    body = {"request_key": str(uuid4()), "question": question, "public_query_confirmed": True,
        "engine": "iterative-v1"}
    if limits:
        body["limits"] = limits
    response = post(client, root, body)
    assert response.status_code == 202, response.text
    return root, response.json(), body


def complete(client, service, root, run):
    for _ in range(180):
        value = client.get(root + "/" + run["id"]).json()
        if value["status"] not in {"queued", "running"}:
            return value
        tick(service, run["id"])
    raise AssertionError("Research did not stop: " + json.dumps(value))


def pipeline(monkeypatch, service, model, *, uncertain=False, jev_fails=False, invalid=False):
    service.settings.search1api_api_key = SecretStr("fixture")
    trace = {"queries": [], "reads": [], "models": [], "gates": []}

    async def retrieve(settings, query, index, depth, product, **kwargs):
        trace["queries"].append(query)
        name = "recipient" if "recipient disclosure" in query else "identity" if "legal identity" in query else "grant"
        def item(key, title):
            return {"id": hashlib.sha256(key.encode()).hexdigest()[:32], "title": title,
                "summary": "Public fixture candidate", "url": "https://example.org/" + key}
        return {"items": [item("road", "Vaud motorway deforestation in the canton"), item(name, "Alpine Foundation " + name)],
            "lanes": [{"status": "complete", "name": "Fixture search index"}], "search_requests": 3}

    class Engine:
        def __init__(self, name):
            self.name = name

        async def choose(self, state, instructions, criteria):
            trace["gates"].append({"engine": self.name, "state": state})
            if self.name == "jev" and jev_fails:
                raise decision_engines.DecisionUnavailable("quota")
            verdict = "unrelated" if "motorway" in state["title"] else "uncertain" if uncertain else "relevant"
            return decision_engines.Decision(self.name, "fixture-" + self.name, verdict,
                {k: float(k == verdict) for k in criteria}, 1, 1, 1, 12, 1)

    async def inspect(settings, query, item, mode, **kwargs):
        assert item["url"] != "https://example.org/road", "Unrelated candidate must never be fetched"
        trace["reads"].append(item["url"])
        text = {"identity": IDENTITY, "grant": GRANT, "recipient": RECIPIENT}[item["url"].rsplit("/", 1)[-1]]
        return {"status": "complete", "url": item["url"], "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "excerpts": [{"text": text, "passage": "p1"}], "scope": "Controlled fixture public evidence"}

    async def model_call(system, user, **kwargs):
        data = json.loads(user)
        title = kwargs["response_schema"]["title"]
        trace["models"].append({"phase": title, "input": data})
        if title == "ResearchPlan":
            return json.dumps({"objective": QUESTION, "completion_criteria": ["Trace recipient-side evidence for disclosed grants."],
                "branches": [{"question": "What is the foundation's legal identity?", "query": "Alpine Foundation legal identity", "purpose": "Establish the legal entity from registry evidence.", "priority": 5},
                    {"question": "Which grants does the foundation disclose?", "query": "Alpine Foundation grants report", "purpose": "Find documented grants and recipients.", "priority": 4}]})
        if title == "CandidateAssessment":
            return json.dumps({"verdict": "relevant", "reason": "The candidate names the foundation and requested record type."})
        if title == "Reflection":
            source = next((s for s in data["sources"] if s["excerpts"][0]["text"] == GRANT), None)
            gaps = [] if not source else [{"question": "Does River Trust disclose the same amount for 2024?",
                "query": "River Trust Alpine Foundation recipient disclosure 2024 grant amount",
                "purpose": "Test the reported amount against the recipient's own disclosure.", "priority": 5,
                "quote": "Invented evidence for a follow-up" if invalid else GRANT, "locator": "p1", "source_id": source["id"],
                "claim_id": data["claims"][0]["id"], "kind": "independent_verification"}]
            return json.dumps({"gaps": gaps, "outcome": "Captured cited public records; recipient amount still needs comparison."})
        source = data["source"]
        quote = source["excerpts"][0]["text"]
        if source["kind"] != "public_source":
            return json.dumps({"claims": [], "entities": [], "relationships": []})
        recipient = quote == RECIPIENT
        entities = [{"name": "Alpine Foundation", "kind": "foundation", "identifier": "CH-100",
            "identifier_issuer": "Registry of Switzerland", "jurisdiction": "Switzerland", "quote": quote, "locator": "p1"}]
        if quote != IDENTITY:
            entities.append({"name": "River Trust", "kind": "organisation", "identifier": "CH-200",
                "identifier_issuer": "Registry of Switzerland", "jurisdiction": "Switzerland", "quote": quote, "locator": "p1"})
        claims = [] if quote == IDENTITY else [{"statement": STATEMENT,
            "existing_claim_id": next((c["id"] for c in data["existing_claims"] if c["statement"] == STATEMENT), None),
            "relation": "CONTRADICTS" if recipient else "SUPPORTS", "quote": quote, "locator": "p1"}]
        edges = [{"subject": "Alpine Foundation", "object": "River Trust", "predicate": "FUNDS",
            "claim_statement": STATEMENT, "quote": quote, "locator": "p1", "amount_text": "CHF 50,000", "period_text": "2024"}] if quote == GRANT else []
        return json.dumps({"claims": claims, "entities": entities, "relationships": edges,
            "source_class": {"category": "primary", "quote": quote, "locator": "p1"}})

    monkeypatch.setattr(decision_search, "federated_retrieve", retrieve)
    monkeypatch.setattr(decision_engines, "engines", lambda settings: {v: Engine(v) for v in ("jev", "laya")})
    monkeypatch.setattr(decision_sources, "safe_inspect", inspect)
    monkeypatch.setattr(model, "complete", model_call)
    return trace


@pytest.mark.parametrize("product", ["pharma", "legal"])
def test_planner_followup_new_evidence_updates_same_claim_and_resolves_identifiers(signed, monkeypatch, tmp_path, product):
    client, service, _, model = signed
    trace = pipeline(monkeypatch, service, model)
    root, run, body = start(client, product=product)
    assert post(client, root, body).json()["id"] == run["id"]
    assert post(client, root, {**body, "engine": "bounded-v1"}).status_code == 409
    result = complete(client, service, root, run)
    assert result["status"] == "completed", result
    assert len(trace["queries"]) == 3 and "recipient disclosure" in trace["queries"][-1]
    assert len(result["sources"]) == 3
    assert len(result["claims"]) == 1
    claim = result["claims"][0]
    assert claim["status"] == "CONTESTED" and claim["revision"] == 2
    assert [h["to"] for h in claim["history"]] == ["SUPPORTED", "CONTESTED"]
    assert len(result["entities"]) == 2
    assert sorted(len(e["evidence"]["mentions"]) for e in result["entities"]) == [2, 3]
    assert result["relationships"][0]["evidence"]["claim_id"] == claim["id"]
    follow = next(q for q in result["research"]["questions"] if q["parent_branch_id"])
    assert follow["claim_id"] == claim["id"] and follow["claim_revision_before"] == 1
    assert follow["depth"] == 1 and follow["status"] == "evidence_found"
    assert len(follow["answer_evidence_ids"]) == 1
    assert any(e["id"] in follow["answer_evidence_ids"] and e["relation"] == "CONTRADICTS" for e in result["evidence"])
    assert len([a for a in result["activity"] if a["kind"] == "candidate_rejected"]) == 3
    assert len(result["plans"]) >= 3 and len(result["research"]["completion_criteria"]) == 1
    assert result["research"]["used"]["search_requests"] == 6
    assert result["research"]["used"]["source_fetches"] == 3
    exported = client.get(root.removesuffix("/investigations") + "/export").json()
    assert exported["investigations"][0]["research"] == result["research"]
    receipt = {"kind": "real_native_worker_with_controlled_external_adapters", "not_live_provider_validation": True,
        "trace": trace, "run": result}
    (tmp_path / "iterative-run.json").write_text(json.dumps(receipt, indent=2))


@pytest.mark.parametrize("options,expected", [({"jev_fails": True}, "laya"), ({"uncertain": True}, "workspace_model")])
def test_fallback_and_uncertainty_are_visible_before_fetch(signed, monkeypatch, options, expected):
    client, service, _, model = signed
    pipeline(monkeypatch, service, model, **options)
    root, run, _ = start(client)
    result = complete(client, service, root, run)
    assert result["claims"][0]["status"] == "CONTESTED"
    gates = [d for b in result["branches"] for d in b["decisions"]]
    assert any(d["engine"] == expected and d["verdict"] == "relevant" for d in gates)
    assert all(s["snapshot"]["relevance_gate"]["verdict"] == "relevant" for s in result["sources"])


@pytest.mark.parametrize("verdict", ["uncertain", "unavailable"])
def test_unresolved_candidate_remains_distinct_from_rejection_without_source_fetch(signed, monkeypatch, verdict):
    client, service, _, model = signed
    trace = pipeline(monkeypatch, service, model)
    original_model = model.complete

    async def unresolved(*args):
        return {"verdict": verdict, "engine": "laya" if verdict == "uncertain" else None,
            "basis": "Controlled unresolved candidate fixture"}

    async def assess(system, user, **kwargs):
        if kwargs["response_schema"]["title"] == "CandidateAssessment":
            return json.dumps({"verdict": "uncertain", "reason": "This snippet cannot establish the relationship."})
        return await original_model(system, user, **kwargs)

    monkeypatch.setattr(product_iterative_steps, "evaluate", unresolved)
    monkeypatch.setattr(model, "complete", assess)
    root, run, _ = start(client)
    result = complete(client, service, root, run)
    assert not result["sources"] and not result["claims"] and not trace["reads"]
    decisions = [d for b in result["branches"] for d in b["decisions"]]
    assert decisions and all(d["verdict"] == verdict for d in decisions)
    activity = [a for a in result["activity"] if a["detail"].get("verdict") == verdict]
    assert activity and all(a["kind"] == "candidate_" + verdict for a in activity)
    assert not any(a["kind"] in {"candidate_accepted", "candidate_rejected"} for a in result["activity"])
    assert result["research"]["used"].get("source_fetches", 0) == 0
    assert result["research"]["used"]["model_calls"] <= result["research"]["limits"]["model_calls"]


def test_admitted_research_does_not_stop_at_legacy_episode_allowance(signed, monkeypatch):
    client, service, _, model = signed
    trace = pipeline(monkeypatch, service, model)
    retrieval = decision_search.federated_retrieve
    providers = []
    async def capture(settings, *args, **kwargs):
        providers.append(settings.web_search_provider)
        return await retrieval(settings, *args, **kwargs)
    monkeypatch.setattr(decision_search, "federated_retrieve", capture)
    root, run, _ = start(client, Limits(search_requests=2).model_dump())
    result = complete(client, service, root, run)
    assert result["status"] == "completed"
    assert len(trace["queries"]) == 3 and result["claims"][0]["revision"] == 2
    assert providers == ["search1api"] * 3
    assert result["research"]["used"]["search_requests"] > 2
    assert "search_requests" not in result["research"]["stops"]
    assert len([m for m in trace["models"] if m["phase"] == "ResearchPlan"]) == 1


def test_invalid_gap_cannot_create_child_and_private_context_never_enters_public_planning(signed, monkeypatch):
    client, service, _, model = signed
    trace = pipeline(monkeypatch, service, model, invalid=True)
    root, run, _ = start(client)
    private = "Confidential acquisition CERULEAN-842"
    assert post(client, root.removesuffix("/investigations") + "/entries",
        {"request_key": str(uuid4()), "kind": "note", "body": private}).status_code == 201
    result = complete(client, service, root, run)
    assert len(trace["queries"]) == 2 and result["claims"][0]["revision"] == 1
    assert not any(q["parent_branch_id"] for q in result["research"]["questions"])
    assert any(private in json.dumps(m) for m in trace["models"] if m["phase"] == "ResearchExtraction")
    assert all(private not in json.dumps(m) for m in trace["models"] if m["phase"] != "ResearchExtraction")
    assert all(private not in q for q in trace["queries"])
    assert all(private not in json.dumps(g) for g in trace["gates"])


def test_pause_resume_and_interrupted_gate_do_not_repeat_paid_work(signed, monkeypatch):
    client, service, _, model = signed
    trace = pipeline(monkeypatch, service, model)
    root, run, _ = start(client)
    for _ in range(3):  # seed, planner, first search
        tick(service, run["id"])
    detail = root + "/" + run["id"]
    current = client.get(detail).json()
    paused = post(client, detail + "/control", {"action": "pause", "expected_revision": current["revision"]}).json()
    assert paused["status"] == "paused"
    resumed = post(client, detail + "/control", {"action": "resume", "expected_revision": paused["revision"]}).json()
    assert resumed["status"] == "queued"
    with service.db.session() as session:
        record = session.get(Investigation, run["id"])
        job = jobs.claim(session, record.job_id, "interrupted-gate")
        job.heartbeat_at = utcnow() - timedelta(hours=1)
        branch = session.scalar(select(InvestigationBranch).where(
            InvestigationBranch.investigation_id == run["id"], InvestigationBranch.phase == "gate"))
        state = dict(branch.checkpoint)
        state.update(inflight="reserved-before-crash", steps=[*state["steps"], {"id": "reserved-before-crash", "phase": "gate", "status": "running"}])
        branch.checkpoint = state
        session.commit()
    with service.db.session() as session:
        jobs.reconcile(session, 30)
        session.commit()
    result = complete(client, service, root, run)
    assert result["claims"][0]["revision"] == 2
    assert len(trace["queries"]) == 3
    assert len([m for m in trace["models"] if m["phase"] == "ResearchPlan"]) == 1
    assert len([g for g in trace["gates"] if "motorway" in g["state"]["title"]]) == 2
    assert any(s["status"] == "interrupted" for b in result["branches"] for s in b["steps"])
    with service.db.session() as session:
        assert session.get(Job, session.get(Investigation, run["id"]).job_id).state == "succeeded"


def test_revocation_during_new_gate_discards_result_before_fetch(signed, monkeypatch):
    client, service, identity, model = signed
    trace = pipeline(monkeypatch, service, model)
    async def revoked(*args):
        with service.db.session() as session:
            member = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"]))
            member.role = "viewer"
            session.commit()
        return {"verdict": "relevant", "engine": "jev", "reason": "MUST NOT RETAIN"}
    monkeypatch.setattr(product_iterative_steps, "evaluate", revoked)
    root, run, _ = start(client)
    for _ in range(4):
        tick(service, run["id"])
    response = client.get(root + "/" + run["id"])
    assert response.json()["status"] == "paused"
    assert "MUST NOT RETAIN" not in response.text and not trace["reads"]
    assert post(client, root + "/" + run["id"] + "/control", {"action": "resume", "expected_revision": response.json()["revision"]}).status_code == 403


def test_research_state_migration_preserves_legacy_evidence_and_refuses_destructive_downgrade(signed):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from test_account_deletion_migration import config

    from alembic import command
    from helvetic_lens.db import Base

    client, service, _, _ = signed
    root, run, _ = start(client)
    with service.db.engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"include_object":
            lambda obj, name, kind, reflected, other: kind != "table" or name == "product_investigations"})
        assert compare_metadata(context, Base.metadata) == []
        with pytest.raises(RuntimeError, match="Retain research checkpoints"):
            command.downgrade(config(connection), "08d495bef125")
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    assert client.get(root + "/" + run["id"]).json()["research"]["version"] == "iterative-v1"


def test_query_deduplication_preserves_relationship_direction():
    from pydantic import ValidationError

    from helvetic_lens.product_iterative_research import ResearchPlan, query_key

    assert query_key("Foundation A funds B") != query_key("B funds Foundation A")
    assert query_key("Foundation A, funds B!") == query_key("FOUNDATION A funds B")
    draft = {"question": "Which grants were made?", "query": "Foundation A grants", "purpose": "Check source records.", "priority": 3}
    with pytest.raises(ValidationError):
        ResearchPlan.model_validate({"objective": QUESTION, "completion_criteria": ["Check grants"], "branches": [draft, draft]})


def test_cantonal_health_rejects_motorway_candidate_before_source_fetch(signed, monkeypatch):
    client, service, _, model = signed
    trace = pipeline(monkeypatch, service, model)
    original_model = model.complete
    async def plan_health(system, user, **kwargs):
        if kwargs["response_schema"]["title"] == "ResearchPlan":
            return json.dumps({"objective": "Swiss cantonal health regulation", "completion_criteria": ["Identify applicable official health rules."],
                "branches": [{"question": "Which cantonal health laws apply?", "query": "Swiss cantonal health legislation", "purpose": "Find the applicable health law.", "priority": 5},
                    {"question": "Which official health guidance applies?", "query": "Swiss cantonal health authority guidance", "purpose": "Compare official regulatory guidance.", "priority": 4}]})
        return await original_model(system, user, **kwargs)
    async def only_road(*args, **kwargs):
        return {"items": [{"id": "road", "title": "Vaud motorway deforestation in the canton",
            "summary": "Approval to clear woodland for a motorway.", "url": "https://example.org/road"}], "search_requests": 3}
    monkeypatch.setattr(model, "complete", plan_health)
    monkeypatch.setattr(decision_search, "federated_retrieve", only_road)
    root, run, _ = start(client, question="Swiss cantonal health regulation")
    result = complete(client, service, root, run)
    assert not result["sources"] and not result["claims"] and not trace["reads"]
    decisions = [d for b in result["branches"] for d in b["decisions"]]
    assert len(decisions) == 2 and all(d["verdict"] == "unrelated" for d in decisions)
    assert all(g["state"]["question"] == "Swiss cantonal health regulation" for g in trace["gates"])


def test_explicit_retry_of_failed_planner_does_not_turn_into_empty_source_read(signed, monkeypatch):
    client, service, _, model = signed
    trace = pipeline(monkeypatch, service, model)
    original_model = model.complete
    attempts = []
    async def interrupted(system, user, **kwargs):
        if kwargs["response_schema"]["title"] == "ResearchPlan":
            attempts.append(1)
            if len(attempts) == 1:
                raise RuntimeError("private provider error must not be retained")
        return await original_model(system, user, **kwargs)
    monkeypatch.setattr(model, "complete", interrupted)
    root, run, _ = start(client)
    failed = complete(client, service, root, run)
    assert failed["status"] == "failed" and not trace["queries"]
    assert "private provider error" not in json.dumps(failed)
    response = post(client, root + "/" + run["id"] + "/control", {"action": "retry", "expected_revision": failed["revision"]})
    assert response.status_code == 200, response.text
    result = complete(client, service, root, run)
    assert result["claims"][0]["revision"] == 2 and len(attempts) == 2


def test_identical_document_at_new_url_does_not_strengthen_claim(signed, monkeypatch):
    client, service, _, model = signed
    pipeline(monkeypatch, service, model)
    original_reader = decision_sources.safe_inspect
    async def copied(settings, query, item, mode, **kwargs):
        result = await original_reader(settings, query, item, mode, **kwargs)
        if item["url"].endswith("recipient"):
            result.update(sha256=hashlib.sha256(GRANT.encode()).hexdigest(), excerpts=[{"text": GRANT, "passage": "p1"}])
        return result
    monkeypatch.setattr(decision_sources, "safe_inspect", copied)
    root, run, _ = start(client)
    result = complete(client, service, root, run)
    assert len(result["sources"]) == 3 and result["claims"][0]["revision"] == 1
    duplicate = next(s for s in result["sources"] if s["snapshot"].get("duplicate_of"))
    assert not any(e["source_id"] == duplicate["id"] for e in result["evidence"])
    question = next(q for q in result["research"]["questions"] if q["parent_branch_id"])
    assert question["status"] == "unresolved" and not question["answer_evidence_ids"]


def test_local_first_gate_and_total_provider_failure_are_explicit(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from helvetic_lens.product_research_gate import evaluate

    calls = []
    settings = SimpleNamespace(jev_input_usd_per_million=None, jev_output_usd_per_million=None)
    class Engine:
        def __init__(self, name, fail=False):
            self.name, self.fail = name, fail
        async def choose(self, state, instructions, criteria):
            calls.append(self.name)
            assert "overall research question" in instructions
            if self.fail:
                raise decision_engines.DecisionUnavailable("not_configured")
            return decision_engines.Decision(self.name, "fixture", "uncertain", {"relevant": 0.1, "uncertain": 0.8, "unrelated": 0.1}, 0.6, 0.8, 2, 3, 1)
    monkeypatch.setattr(decision_engines, "engines", lambda _: {name: Engine(name) for name in ("jev", "laya")})
    item = {"title": "A possibly related public record", "summary": "Limited detail"}
    result = asyncio.run(evaluate(settings, "Research funding", "Check recipient", item, "laya_first"))
    assert calls == ["laya"] and result["verdict"] == "uncertain"
    calls.clear()
    monkeypatch.setattr(decision_engines, "engines", lambda _: {name: Engine(name, True) for name in ("jev", "laya")})
    result = asyncio.run(evaluate(settings, "Research funding", "Check recipient", item))
    assert calls == ["jev", "laya"] and result["verdict"] == "unavailable"
    assert result["engine"] is None and len(result["fallback_errors"]) == 2


def test_incomplete_identity_namespace_does_not_merge_same_name_mentions(signed):
    from helvetic_lens import product_iterative_research as research
    from helvetic_lens.product_investigation_models import DossierEntity
    from helvetic_lens.product_investigations import rows, snapshot

    client, service, _, _ = signed
    _, run, _ = start(client)
    quote = "Orion Trust has Registry identifier 123. Its jurisdiction is not recorded here."
    data = research.ResearchExtraction.model_validate({"entities": [{"name": "Orion Trust", "kind": "organisation",
        "identifier": "123", "identifier_issuer": "Registry", "quote": quote, "locator": "p1"}]})
    with service.db.session() as session:
        record = session.get(Investigation, run["id"])
        for suffix in ("one", "two"):
            source, _ = snapshot(session, record, {"url": "https://example.org/" + suffix,
                "title": "Registry mention", "sha256": hashlib.sha256((quote + suffix).encode()).hexdigest(),
                "excerpts": [{"text": quote, "passage": "p1"}], "scope": "Fixture"}, public=True)
            research.extract(session, record, source, data)
        entities = rows(session, DossierEntity, record)
        assert len(entities) == 2
        assert all(e.evidence["identity"] == "unresolved_source_mention" for e in entities)


def test_distinct_witnessed_originals_for_one_question_get_separate_read_branches(signed):
    import asyncio

    from helvetic_lens import product_iterative_research as research
    from helvetic_lens.product_investigations import rows

    client, service, _, _ = signed
    _, run, _ = start(client)
    witness = {"source_id": str(uuid4()), "locator": "p1", "quote": "Compare the original annual series and the methods appendix."}
    question = "Verify the linked original for: what does the reported trend mean?"
    first_url, second_url = "https://example.org/annual-series", "https://example.org/methods-appendix"
    def draft(query, kind="independent_verification"):
        return research.Gap(question=question, query=query, purpose="Read the cited original before completing the answer.",
            priority=1, kind=kind, catalogues=[], **witness)

    with service.db.session() as session:
        record = session.get(Investigation, run["id"])
        first = research.add_question(session, record, draft(first_url), trigger=witness)
        research.schedule_questions(session, record)
        second = research.add_question(session, record, draft(second_url), trigger=witness)
        research.schedule_questions(session, record)
        assert first and second and first != second
        # Keep loop protection for an already scheduled original, a repeated
        # search question, and unwitnessed/non-verification requests.
        assert research.add_question(session, record, draft(first_url), trigger=witness) is None
        assert research.add_question(session, record, draft("annual trend original report"), trigger=witness) is None
        assert research.add_question(session, record, draft("https://example.org/third")) is None
        assert research.add_question(session, record, draft("https://example.org/third", "missing_evidence"), trigger=witness) is None
        branches = rows(session, InvestigationBranch, record)
        assert {branch.query for branch in branches} == {first_url, second_url}
        assert all(branch.checkpoint["trigger"] == witness for branch in branches)
        # The existing direct-reading route works without a broad search key.
        for branch in branches:
            result = asyncio.run(decision_search.federated_retrieve(service.settings, branch.query, "web", "quick", "pharma", selected_catalogues=[]))
            assert [item["url"] for item in result["items"]] == [branch.query]
            assert result["search_requests"] == 0
