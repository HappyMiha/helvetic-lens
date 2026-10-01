"""Shared native journeys with retained evidence and controlled provider failures."""
import asyncio
import hashlib
import json
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from test_product_claim_review import body, item, seed
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_exploration import adapters, start
from test_product_investigations import tick
from test_product_iterative_research import GRANT, complete

from helvetic_lens import decision_engines, decision_search, research_gateway, research_knowledge
from helvetic_lens.config import Settings
from helvetic_lens.db import utcnow
from helvetic_lens.domain_packs import REGISTRY
from helvetic_lens.product_domain_context import SCHEMAS
from helvetic_lens.product_investigation_models import (
    ClaimEvidence,
    DossierClaim,
    Investigation,
    InvestigationSource,
)
from helvetic_lens.product_investigations import scope
from helvetic_lens.research_contracts import SKILLS, SOURCES


def test_registered_packs_have_real_schemas_and_routable_tasks():
    assert set(REGISTRY) == {"GeneralPack", "LegalPack", "PharmaPack"}
    for pack in REGISTRY.values():
        value = pack.descriptor()
        assert value["context_schema_id"] in SCHEMAS
        assert value["review_policy"]["domain"] == pack.domain
        assert set(pack.skill_ids) <= set(SKILLS) and set(pack.source_ids) <= set(SOURCES)
        assert all(value["input_schema"] and value["output_schema"] for value in value["skills"])
    settings = Settings()
    work = {"phase": "compare", "product": "legal", "input": {"current": [], "previous": []}}
    assert research_gateway.route(settings, work)["provider"] == "deterministic"
    assert research_gateway.route(settings, {**work, "input": {"current": ["a"], "previous": ["b"]}})["model"] == settings.apertus_model


def test_source_discovery_survives_both_decision_engines_down(monkeypatch):
    class Down:
        async def choose(self, *args):
            raise decision_engines.DecisionUnavailable("unavailable")
    monkeypatch.setattr(decision_engines, "engines", lambda _: {"jev": Down(), "laya": Down()})
    calls = []
    async def retrieve(settings, query, index, depth, product, alternatives=()):
        calls.append(query)
        return {"items": [{"id": "source", "title": "Fictional source", "url": "https://example.org/source"}],
            "lanes": [{"name": "Direct source", "status": "complete", "count": 1}]}
    monkeypatch.setattr(decision_search, "federated_retrieve", retrieve)
    result = asyncio.run(decision_search.execute(Settings(), "reuse evidence", "auto", product="legal"))
    assert calls == ["reuse evidence"] and result["items"][0]["id"] == "source"
    assert result["selected_engine"] is None and result["error"]


@pytest.mark.parametrize("product", ["legal", "pharma"])
def test_complete_research_reuses_a_capture_and_retains_routes_and_coverage(signed, monkeypatch, product):
    client, service, identity, model = signed
    trace = adapters(monkeypatch, service, model)
    base = model.complete
    recalled = []
    async def response(system, user, **kwargs):
        value = json.loads(user)
        if value.get("saved_knowledge"):
            assert research_knowledge.SYSTEM in system
            recalled.append(value["saved_knowledge"])
        if kwargs["response_schema"]["title"] == "Reflection":
            return json.dumps({"gaps": [], "outcome": "The retained grant and newly read identity require later independent verification."})
        return await base(system, user, **kwargs)
    monkeypatch.setattr(model, "complete", response)
    root, run, _ = start(client, product)
    with service.db.session() as session:
        current = session.get(Investigation, run["id"])
        previous = Investigation(dossier_id=current.dossier_id, organization_id=identity["organization"]["id"],
            status="completed", request_key=str(uuid4()), question="Earlier public grant question",
            created_at=utcnow() - timedelta(days=2))
        session.add(previous)
        session.flush()
        source = InvestigationSource(**scope(previous), source_key="original-grant", kind="public_source",
            title="Original grant disclosure", url="https://example.org/grant", sha256=hashlib.sha256(GRANT.encode()).hexdigest(),
            snapshot={"status": "complete", "sha256": hashlib.sha256(GRANT.encode()).hexdigest(),
                "excerpts": [{"text": GRANT, "passage": "p1"}]})
        session.add(source)
        session.commit()
        source_id = source.id
    result = complete(client, service, root + "/investigations", run)
    assert result["exploration"]["status"] == "ready", result["stop_reason"]
    assert recalled and all(s["fresh_source_check"] is False for s in recalled)
    assert "https://example.org/grant" not in trace["reads"], "A retained source must not be fetched again by default"
    copied = next(s for s in result["sources"] if s["snapshot"].get("retained_origin"))
    assert copied["snapshot"]["retained_origin"]["source_id"] == source_id
    assert any(f["source_id"] == copied["id"] for f in result["exploration"]["briefing"]["findings"])
    manifest = result["coverage_manifest"]
    assert manifest["summary"]["reused_sources"] == 1 and manifest["exhaustive"] is False
    assert manifest["pack_id"] == ("LegalPack" if product == "legal" else "PharmaPack")
    assert manifest["executions"] and all(s["receipt"]["skill_version"] for s in manifest["executions"])
    gate = next(s["receipt"] for s in manifest["executions"] if s["phase"] == "gate")
    assert gate["decision"]["measurement"]["input_tokens"] == 12
    assert all(s["receipt"].get("output_fingerprint") for s in manifest["executions"] if s["status"] == "completed")
    assert client.get(root + "/coverage/research").json()["items"][0]["investigation_id"] == run["id"]
    with service.db.session() as session:
        original = session.get(InvestigationSource, source_id)
        original.snapshot = {**original.snapshot, "excerpts": [{"text": "Withdrawn old text", "passage": "p1"}]}
        session.commit()
    assert client.get(root + "/investigations/" + run["id"]).status_code == 404
    search = post(client, root + "/evidence-search", {"query": "Foundation", "mode": "literal"})
    assert search.status_code == 200 and all(s["source_id"] != copied["id"] for s in search.json()["items"])


@pytest.mark.parametrize("product", ["loyer", "pharma"])
def test_knowledge_unifies_reviews_conflicts_and_origin_without_promoting_ai(signed, product):
    client, service, _, root, ids, sources, runs, _, _ = seed(signed, product=product)
    response = client.get(root + "/knowledge")
    assert response.status_code == 200, response.text
    ledger = response.json()
    assert ledger["total"] == 2 and all(r["review_requirement"]["required"] for r in ledger["items"])
    conflicted = next(r for r in ledger["items"] if r["id"] == ids[0])
    assert "conflicting_evidence" in conflicted["review_requirement"]["reasons"]
    assert {e["relation"] for e in conflicted["citations"]} == {"SUPPORTS", "CONTRADICTS"}
    assert post(client, root + "/claim-reviews/review", body(item(client, root, ids[1]))).status_code == 200
    approved = next(r for r in client.get(root + "/knowledge").json()["items"] if r["id"] == ids[1])
    assert approved["review_requirement"]["accepted_for_use"] and approved["review_history"]
    assert approved["citations"][0]["source"]["sha256"]
    with service.db.session() as session:
        source = session.get(InvestigationSource, sources[1])
        source.snapshot = {**source.snapshot, "excerpts": []}
        session.commit()
    stale = next(r for r in client.get(root + "/knowledge").json()["items"] if r["id"] == ids[1])
    assert stale["review_requirement"]["required"] and not stale["review_requirement"]["accepted_for_use"]
    client.cookies.clear()
    assert client.get(root + "/knowledge").status_code == 401


def test_recall_never_promotes_private_or_mixed_source_claims(signed, monkeypatch):
    client, service, identity, model = signed
    root, run, _ = start(client)
    with service.db.session() as session:
        current = session.get(Investigation, run["id"])
        old = Investigation(dossier_id=current.dossier_id, organization_id=identity["organization"]["id"],
            status="completed", request_key=str(uuid4()), question="Old question")
        session.add(old)
        session.flush()
        values = []
        for kind, text in (("public_source", GRANT), ("team_contribution", "PRIVATE-MIXED-SOURCE-MARKER")):
            source = InvestigationSource(**scope(old), source_key=kind, kind=kind, title=kind,
                url="https://example.org/" + kind, sha256=hashlib.sha256(text.encode()).hexdigest(),
                snapshot={"excerpts": [{"text": text, "passage": "p1"}]})
            session.add(source)
            session.flush()
            values.append((source, text))
        claim = DossierClaim(**scope(old), statement="PRIVATE-MIXED-CLAIM-MARKER", status="SUPPORTED")
        session.add(claim)
        session.flush()
        for source, text in values:
            session.add(ClaimEvidence(**scope(old), claim_id=claim.id, source_id=source.id, relation="SUPPORTS", quote=text, locator="p1"))
        session.commit()
    tick(service, run["id"])
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        context = deepcopy(saved.research_state["core"]["recall"])
        assert context["claims"] == [] and len(context["sources"]) == 1
        assert "PRIVATE-MIXED" not in json.dumps(context)
        assert research_knowledge.current(session, saved)
    assert model.calls == []


def test_pack_discovery_uses_authenticated_product_scope(signed):
    client, _, _, _ = signed
    response = client.get("/api/products/pharma/research-capabilities")
    assert response.status_code == 200, response.text
    assert response.json()["selected"] == "PharmaPack"
    assert len(response.json()["packs"]) == 3
    client.cookies.clear()
    assert client.get("/api/products/pharma/research-capabilities").status_code == 401
