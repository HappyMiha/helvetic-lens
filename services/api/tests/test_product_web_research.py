"""Recurring queries through real native scheduling, jobs, capture and comparison."""
import hashlib
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from test_auth import _register
from test_legal_profiles import config
from test_private_dossier_monitoring import private
from test_product_dossiers import active, post
from test_product_dossiers import signed as signed
from test_product_investigations import complete, tick

from helvetic_lens import decision_search, decision_sources, jobs
from helvetic_lens.db import utcnow
from helvetic_lens.models import OrganizationMembership, User
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch
from helvetic_lens.product_investigation_models import WebResearchPolicy as Policy
from helvetic_lens.product_investigation_models import WebResearchTrigger as Trigger
from helvetic_lens.product_models import DecisionSearchBudget, DossierEntry, ProductDossier
from helvetic_lens.product_web_research import enqueue_due

QUESTION = "Public research about Alpine Therapeutics"
URL = "https://example.org/registry"
FIRST = "Alpine Therapeutics owns Helvetic Molecule AG, according to the current registry."
SECOND = "Alpine Therapeutics sold Helvetic Molecule AG, according to the later registry."


def setup(client, product="pharma", audience="draft"):
    if audience == "team":
        doc, root, _ = private(client, product)
        return doc, root
    root = f"/api/products/{product}/dossiers"
    response = post(client, root, {"creation_key": str(uuid4()), "config": config(name="Private secret dossier name")})
    assert response.status_code == 201, response.text
    doc = response.json()
    if audience == "workspace":
        active(client, doc)
    return doc, root + "/" + doc["id"]


def enable(client, root, **values):
    previous = client.get(root + "/web-research")
    assert previous.status_code == 200, previous.text
    data = {"request_key": str(uuid4()), "expected_revision": previous.json()["policy"]["revision"],
        "enabled": True, "question": QUESTION, "cadence_hours": 24, "standing_public_query_confirmed": True, **values}
    result = post(client, root + "/web-research", data)
    assert result.status_code == 200, result.text
    return result.json(), data


def due(service, *, next_day=False):
    with service.db.session() as session:
        for row in session.scalars(select(Policy)):
            row.next_check_at = row.next_run_at = utcnow() - timedelta(seconds=1)
            if next_day:
                row.budget_day = "2000-01-01"
        session.commit()
    return enqueue_due(service.db, service.settings)


def newest(client, root):
    return client.get(root + "/web-research").json()["items"][0]["investigation"]


def pipeline(monkeypatch, service, target, *, during=None):
    service.settings.search1api_api_key = SecretStr("fixture")
    service.settings.typesafe_api_key = SecretStr("fixture")
    service.settings.apertus_base_url = "http://127.0.0.1:8181/v1"
    service.settings.apertus_model = "fixture"
    state = {"text": FIRST, "queries": [], "reads": [], "analysis": [], "empty": False, "failure": False}
    def hook(phase):
        if during:
            during(phase)
    async def search(settings, query, mode, depth, product):
        state["queries"].append((query, mode, depth, product))
        hook("search")
        if state["failure"]:
            raise RuntimeError("PRIVATE PROVIDER FAILURE BODY")
        return {"items": [] if state["empty"] else [{"id": "a", "title": "Public registry", "url": URL}],
            "selected_engine": "laya", "latency_ms": 17, "error": None,
            "retrieval": {"lanes": [{"name": "Google web", "query": query, "status": "complete", "count": 0 if state["empty"] else 1}],
                          "cost_usd": None, "search_requests": 2},
            "engines": [{"engine": "jev", "error": "quota", "estimated_cost_usd": None},
                {"engine": "laya", "latency_ms": 12, "estimated_cost_usd": None,
                 "mean_confidence": 0.9, "confidence_definition": "Not measured accuracy.", "cost_scope": "Inference only."}]}
    async def inspect(settings, query, item, mode, **kwargs):
        state["reads"].append((query, item["url"]))
        hook("read")
        return {"status": "complete", "url": item["url"], "sha256": hashlib.sha256(state["text"].encode()).hexdigest(),
            "excerpts": [{"text": state["text"], "passage": "p1"}]}
    async def model(system, user, **kwargs):
        data = json.loads(user)
        state["analysis"].append(data)
        hook("compare" if "current" in data else "extract")
        if "current" in data:
            return json.dumps({"changes": [{"current_claim_id": data["current"][0]["id"],
                "previous_claim_id": data["previous"][0]["id"], "kind": "UPDATES"}]})
        assert data["existing_claims"] == []
        quote = data["source"]["excerpts"][0]["text"]
        return json.dumps({"claims": [{"statement": quote, "quote": quote, "locator": "p1", "relation": "SUPPORTS"}],
            "entities": [{"name": "Alpine Therapeutics", "kind": "company", "quote": quote, "locator": "p1", "investigate": True}]})
    monkeypatch.setattr(decision_search, "execute", search)
    monkeypatch.setattr(decision_sources, "safe_inspect", inspect)
    monkeypatch.setattr(target, "complete", model)
    return state


@pytest.mark.parametrize("product,audience", [(p,a) for p in ("pharma", "loyer") for a in ("draft", "team", "workspace")])
def test_recurring_evidence_deduplicates_then_updates_and_keeps_query_private(signed, monkeypatch, product, audience):
    client, service, _, target = signed
    _, root = setup(client, product, audience)
    state = pipeline(monkeypatch, service, target)
    secret = "PRIVATE NOTE NEVER USED FOR PUBLIC DISCOVERY"
    assert post(client, root + "/entries", {"request_key": str(uuid4()), "kind": "note", "body": secret}).status_code == 201
    saved, command = enable(client, root)
    assert post(client, root + "/web-research", command).json() == saved
    assert enqueue_due(service.db, service.settings) == {"checked": 1, "started": 1}, client.get(root + "/web-research").json()
    first = complete(client, service, root + "/investigations", newest(client, root))
    assert first["status"] == "completed" and len(first["claims"]) == 1, first
    assert first["web_research_trigger"] and len(first["branches"]) == 1
    assert first["plans"][0]["document"]["budgets"]["public_branches"] == 1
    assert enqueue_due(service.db, service.settings) == {"checked": 0, "started": 0}
    assert due(service, next_day=True)["started"] == 1
    same = complete(client, service, root + "/investigations", newest(client, root))
    assert same["status"] == "completed" and not same["claims"]
    assert same["sources"][0]["snapshot"]["unchanged_from"] == first["sources"][0]["id"]
    assert len(state["analysis"]) == 1  # Read/rank again, no repeated extraction.
    state["text"] = SECOND
    assert due(service, next_day=True)["started"] == 1
    changed = complete(client, service, root + "/investigations", newest(client, root))
    assert changed["claims"] and changed["claims"][0]["statement"] == SECOND
    assert client.get(root + "/evidence-changes").json()["total"] == 1
    assert len(state["analysis"]) == 3
    assert state["queries"] == [(QUESTION, "auto", "balanced", product)] * 3
    assert secret not in json.dumps(state) and "Private secret dossier name" not in json.dumps(state)
    detail = client.get(root + "/web-research").json()
    assert detail["total"] == 3 and detail["items"][1]["unchanged_sources"] == 1
    measurements = detail["items"][0]["coverage"][0]["engines"]
    assert measurements[1]["mean_confidence"] == .9 and measurements[1]["estimated_cost_usd"] is None
    exported = client.get(root + "/export").json()
    assert exported["web_research"]["total"] == 3
    assert client.get(root.split('/dossiers/')[0] + "/public-dossiers").json()["total"] == 0
    with service.db.session() as session:
        assert all(r.session_id is None and r.publication_id is None for r in session.scalars(select(Investigation)))
        assert session.get(DecisionSearchBudget, utcnow().date()).used == 6


def test_reappearing_content_and_changed_question_are_new_analysis(signed, monkeypatch):
    client, service, _, target = signed
    _, root = setup(client)
    state = pipeline(monkeypatch, service, target)
    enable(client, root)
    for text in (FIRST, SECOND, FIRST):
        state["text"] = text
        due(service, next_day=True)
        result = complete(client, service, root + "/investigations", newest(client, root))
        assert result["claims"] and not result["sources"][0]["snapshot"]["unchanged_from"]
    enable(client, root, question="New public question about Alpine Therapeutics")
    due(service, next_day=True)
    result = complete(client, service, root + "/investigations", newest(client, root))
    assert result["claims"] and not result["sources"][0]["snapshot"]["unchanged_from"]


@pytest.mark.parametrize("empty,failure", [(True, False), (False, True)])
def test_empty_search_is_complete_but_unavailable_is_not(signed, monkeypatch, empty, failure):
    client, service, _, target = signed
    _, root = setup(client)
    state = pipeline(monkeypatch, service, target)
    state.update(empty=empty, failure=failure)
    enable(client, root)
    due(service)
    result = complete(client, service, root + "/investigations", newest(client, root))
    assert result["status"] == ("completed" if empty else "failed")
    assert not result["sources"] and not state["reads"] and not state["analysis"]
    assert "PRIVATE PROVIDER" not in json.dumps(result)
    assert enqueue_due(service.db, service.settings)["started"] == 0


@pytest.mark.parametrize("race,phase", [("question","search"), ("disable","read"), ("audience","extract"),
    ("member","search"), ("account","read"), ("source","read"), ("source","extract")])
def test_late_results_are_fenced_by_current_scope_and_source(signed, monkeypatch, race, phase):
    client, service, identity, target = signed
    doc, root = setup(client)
    changed = []
    def mutate(current):
        if current != phase or changed:
            return
        if race in {"question", "disable"}:
            enable(client, root, enabled=race != "disable", question="Changed explicit public question")
        else:
            with service.db.session() as session:
                if race == "audience":
                    session.get(ProductDossier, doc["id"]).team_managed = True
                elif race == "member":
                    session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"])).role = "viewer"
                elif race == "account":
                    session.get(User, identity["user"]["id"]).active = False
                else:
                    session.add(DossierEntry(dossier_id=doc["id"], request_key=str(uuid4()), kind="source_review",
                        url=URL, data_json={"decision": "exclude", "revision": 1}))
                session.commit()
        changed.append(True)
    pipeline(monkeypatch, service, target, during=mutate)
    enable(client, root)
    due(service)
    run = newest(client, root)
    for _ in range(5):
        tick(service, run["id"])
    assert changed == [True]
    from helvetic_lens.product_investigation_models import DossierClaim
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(DossierClaim)) == 0
        assert session.get(Investigation, run["id"]).status in {"failed", "paused", "cancelled"}


def test_limits_replay_consent_cadence_and_readiness(signed, monkeypatch):
    client, service, _, target = signed
    _, root = setup(client)
    state = pipeline(monkeypatch, service, target)
    page, command = enable(client, root, cadence_hours=168)
    assert page["policy"]["cadence_hours"] == 168
    assert post(client, root + "/web-research", {**command, "question": "Changed public question"}).status_code == 409
    newer = {**command, "request_key": str(uuid4()), "expected_revision": 1}
    for bad in ({"standing_public_query_confirmed": False}, {"standing_public_query_confirmed": "true"},
                {"question": "  "}, {"cadence_hours": 1}, {"cadence_hours": "24"}, {"expected_revision": 0}):
        assert post(client, root + "/web-research", {**newer, **bad}).status_code in {409, 422}
    service.settings.search1api_api_key = SecretStr("")
    service.settings.typesafe_api_key = SecretStr("")
    assert due(service)["started"] == 0 and state["queries"] == []
    assert "waiting" in client.get(root + "/web-research").json()["policy"]["reason"]
    # A decision engine is required; a paid broad-search key is not.
    service.settings.typesafe_api_key = SecretStr("fixture")
    service.settings.decision_search_daily_limit = 0
    assert due(service)["started"] == 1
    run = newest(client, root)
    result = complete(client, service, root + "/investigations", run)
    assert result["status"] == "completed" and state["queries"]
    enable(client, root, enabled=False)
    enable(client, root)
    assert due(service)["started"] == 1
    complete(client, service, root + "/investigations", newest(client, root))
    enable(client, root)
    assert due(service)["started"] == 0
    assert client.get(root + "/web-research").json()["policy"]["used_today"] == 2
    assert len(state["queries"]) >= 2


def test_interrupted_search_is_not_repeated_and_explicit_retry_is_bounded(signed, monkeypatch):
    client, service, _, target = signed
    _, root = setup(client)
    state = pipeline(monkeypatch, service, target)
    enable(client, root)
    due(service)
    run = newest(client, root)
    tick(service, run["id"])
    with service.db.session() as session:
        record = session.get(Investigation, run["id"])
        job = jobs.claim(session, record.job_id, "crashed-worker")
        job.heartbeat_at = utcnow() - timedelta(hours=1)
        branch = session.scalar(select(InvestigationBranch).where(InvestigationBranch.investigation_id == run["id"]))
        branch.checkpoint = {**branch.checkpoint, "inflight": "paid-request-receipt", "steps": [{"phase": "search", "status": "running"}]}
        session.commit()
    with service.db.session() as session:
        jobs.reconcile(session, 30)
        session.commit()
    result = complete(client, service, root + "/investigations", run)
    assert result["status"] == "failed" and not state["queries"]
    retry = post(client, root + f"/investigations/{run['id']}/control", {"action": "retry", "expected_revision": result["revision"]})
    assert retry.status_code == 200, retry.text
    result = complete(client, service, root + "/investigations", run)
    assert result["status"] == "completed" and len(state["queries"]) == 1
    assert due(service)["started"] == 0
    assert client.get(root + "/web-research").json()["policy"]["used_today"] == 2


def test_signout_does_not_manufacture_a_session_or_publish(signed, monkeypatch):
    client, service, _, target = signed
    _, root = setup(client)
    state = pipeline(monkeypatch, service, target)
    enable(client, root)
    assert post(client, "/api/auth/logout", {}).status_code == 200
    assert due(service)["started"] == 1
    with service.db.session() as session:
        identifier = session.scalar(select(Investigation.id))
    for _ in range(5):
        tick(service, identifier)
    with service.db.session() as session:
        run = session.get(Investigation, identifier)
        assert run.session_id is None and run.publication_id is None and run.status == "completed"
    assert len(state["analysis"]) == 1
    assert client.get(root + "/web-research").status_code == 401


def test_no_implicit_authority_and_tenant_vertical_boundaries(signed, monkeypatch):
    client, service, _, target = signed
    doc, root = setup(client)
    state = pipeline(monkeypatch, service, target)
    assert post(client, root + "/searches", {"request_key": str(uuid4()), "query": QUESTION, "provider": "workspace", "match_mode": "all", "purpose": "saved recipe"}).status_code == 201
    assert enqueue_due(service.db, service.settings) == {"checked": 0, "started": 0}
    assert not state["queries"]
    page, command = enable(client, root)
    assert client.post(root + "/web-research", json=command).status_code == 403
    assert client.get(root.replace("pharma", "loyer") + "/web-research").status_code == 404
    assert _register(client, "outsider@example.ch", "Different organization").status_code == 201
    assert client.get(root + "/web-research").status_code == 404
    assert post(client, root + "/web-research", command).status_code == 404


def test_migration_equivalence_retained_receipts_and_containment(signed, monkeypatch):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from sqlalchemy.exc import IntegrityError
    from test_account_deletion_migration import config as migration_config

    from alembic import command as migrate
    from helvetic_lens.db import Base

    client, service, _, target = signed
    _, root = setup(client)
    with service.db.engine.connect() as connection:
        migrate.downgrade(migration_config(connection), "03d495bef125")
        migrate.upgrade(migration_config(connection), "head")
        context = MigrationContext.configure(connection, opts={"include_object": lambda obj, name, kind, reflected, other:
            kind != "table" or name in {Policy.__tablename__, Trigger.__tablename__}})
        assert compare_metadata(context, Base.metadata) == []
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    pipeline(monkeypatch, service, target)
    enable(client, root)
    due(service)
    other, _ = setup(client)
    with service.db.session() as session:
        trigger = session.scalar(select(Trigger))
        session.add(Trigger(dossier_id=other["id"], organization_id=service.organization_id, policy_id=trigger.policy_id,
            policy_revision=1, investigation_id=trigger.investigation_id, question=QUESTION, scheduled_for=utcnow()))
        with pytest.raises(IntegrityError):
            session.commit()
    with service.db.engine.connect() as connection, pytest.raises(RuntimeError, match="Retained public-search"):
        migrate.downgrade(migration_config(connection), "03d495bef125")


@pytest.mark.parametrize("role", ["VIEWER", "CONTRIBUTOR", "EDITOR"])
def test_team_editors_can_authorize_without_workspace_admin_rights(signed, monkeypatch, role):
    from test_product_teams import accept, colleague, invite, managed, switch

    client, service, identity, target = signed
    user_id, cookies = colleague(client, service, identity)
    _, root = managed(client)
    invitation = invite(client, root, user_id, role)
    switch(client, cookies)
    accept(client, invitation)
    pipeline(monkeypatch, service, target)
    result = client.get(root + "/web-research").json()
    assert result["can_manage"] is (role == "EDITOR")
    request = {"request_key": str(uuid4()), "expected_revision": 0, "enabled": True, "question": QUESTION,
        "cadence_hours": 24, "standing_public_query_confirmed": True}
    result = post(client, root + "/web-research", request)
    assert result.status_code == (200 if role == "EDITOR" else 403), result.text
    assert due(service)["started"] == (1 if role == "EDITOR" else 0)
    if role == "EDITOR":
        assert complete(client, service, root + "/investigations", newest(client, root))["claims"]


def test_scheduler_reads_saved_model_configuration_and_failed_extraction_is_not_a_duplicate(signed, monkeypatch):
    from helvetic_lens.models import ApertusConfiguration

    client, service, _, target = signed
    _, root = setup(client)
    state = pipeline(monkeypatch, service, target)
    enable(client, root)
    with service.db.session() as session:
        record = ApertusConfiguration(id=service.tenant_record_id, values={"provider": "custom", "base_url": "", "model": "fixture"})
        session.add(record)
        session.commit()
    assert due(service)["started"] == 0  # A saved disconnect overrides environment availability.
    with service.db.session() as session:
        session.get(ApertusConfiguration, service.tenant_record_id).values = {"provider": "custom", "base_url": "https://example.org/v1", "model": "fixture"}
        session.commit()
    # A beat process sees its environment, while the workspace uses a saved model.
    service.settings.apertus_base_url = ""
    assert due(service)["started"] == 1
    healthy_model = target.complete
    async def invalid(*args, **kwargs):
        return '{"claims":[{"statement":"Invented statement", "quote":"This quotation is not in the source", "locator":"p1", "relation":"SUPPORTS"}]}'
    monkeypatch.setattr(target, "complete", invalid)
    first = complete(client, service, root + "/investigations", newest(client, root))
    assert first["status"] == "failed" and first["sources"] and not first["claims"]
    monkeypatch.setattr(target, "complete", healthy_model)
    assert due(service, next_day=True)["started"] == 1
    later = complete(client, service, root + "/investigations", newest(client, root))
    assert later["claims"] and not later["sources"][0]["snapshot"]["unchanged_from"]
    assert len(state["analysis"]) == 1
