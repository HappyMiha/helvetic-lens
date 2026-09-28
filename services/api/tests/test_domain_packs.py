"""Pack selection is server-owned across old and product-prefixed workflows."""
import asyncio
import json
from uuid import uuid4

import pytest
from test_auth import _csrf, _register
from test_legal_profiles import config
from test_product_dossiers import active, create, post
from test_product_dossiers import signed as signed
from test_product_teams import accept, colleague, invite, managed, switch

from helvetic_lens import decision_search, domain_packs, product_investigations, product_research
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.legal_profile_models import LegalMonitoringProfile
from helvetic_lens.product_models import DossierEntry, DossierMember

TOPICS = json.dumps({"topics": [{"name": "Safety evidence", "description": "Review new evidence",
                                 "keywords": ["safety", "evidence"]}]})


@pytest.mark.parametrize("product,pack_id,topic_word", [
    (None, "LegalPack", "legal"), ("legal", "LegalPack", "legal"),
    ("loyer", "LegalPack", "legal"), ("pharma", "PharmaPack", "pharmaceutical"),
])
def test_common_profile_setup_resolves_saved_product_and_preserves_proposal_provenance(signed, product, pack_id, topic_word):
    client, service, _, model = signed
    # Even conflicting free text must not select a different domain policy.
    path = f"/api/products/{product}/dossiers" if product else "/api/monitoring-profiles"
    result = post(client, path, {"creation_key": str(uuid4()), "config": config(goal="PHARMA LEGAL: monitor my question")})
    assert result.status_code == 201, result.text
    profile = result.json()["profile"] if product else result.json()
    route = "/api/monitoring-profiles/" + profile["id"]
    pack = profile["domain_pack"]
    assert pack["id"] == pack_id and pack["version"] == "1.1.0"
    assert client.get(route).json()["domain_pack"] == pack
    model.responses = [TOPICS]
    response = post(client, route + "/suggest", {"expected_revision": 1})
    assert response.status_code == 200, response.text
    body = response.json()
    system, user = model.calls[-1]
    assert f"distinct {topic_word} monitoring topics" in system
    assert json.loads(user)["domain_pack"] == pack
    assert body["profile"]["config"]["topics"][0]["name"] == "Naturalisation"
    with service.db.session() as session:
        row = session.get(LegalMonitoringProfile, profile["id"])
        assert row.proposals_json[body["suggestions"][0]["id"]]["domain_pack"] == pack
    # Round-trip the selected proposal and retain it when actual monitoring starts.
    saved = client.put(route, headers=_csrf(client), json={"expected_revision": 2, "step": 2,
        "config": {**body["profile"]["config"], "topics": body["suggestions"]}})
    assert saved.status_code == 200, saved.text
    activated = post(client, route + "/activate", {"expected_revision": saved.json()["revision"]})
    assert activated.status_code == 200, activated.text
    assert activated.json()["domain_pack"] == pack
    assert activated.json()["topics"][0]["plan"]["ai_assisted"] is True


@pytest.mark.parametrize("product,pack_id", [("pharma", "PharmaPack"), ("legal", "LegalPack")])
def test_source_advice_and_active_refinement_share_the_saved_pack(signed, product, pack_id):
    client, service, _, model = signed
    result = post(client, f"/api/products/{product}/dossiers", {"creation_key": str(uuid4()), "config": config()})
    doc = result.json()
    root = f"/api/products/{product}/dossiers/{doc['id']}"
    model.responses = [json.dumps({"recommendations": [{"source_id": "fedlex-legislation", "reason": "Supplied catalogue"}]})]
    advice = post(client, root + "/source-advice", {"expected_revision": 1})
    assert advice.status_code == 200, advice.text
    assert advice.json()["domain_pack"]["id"] == pack_id
    assert json.loads(model.calls[-1][1])["domain_pack"] == doc["profile"]["domain_pack"]
    profile = active(client, doc)
    model.responses = [TOPICS]
    proposal = post(client, root + "/improve", {"expected_revision": profile["revision"], "feedback": "Focus on evidence"})
    assert proposal.status_code == 200, proposal.text
    assert json.loads(model.calls[-1][1])["domain_pack"]["id"] == pack_id
    with service.db.session() as session:
        saved = session.get(DossierEntry, proposal.json()["id"])
        assert saved.data_json["domain_pack"] == doc["profile"]["domain_pack"]
    assert client.get(root).json()["profile"]["topics"][0]["current_revision"] == 1


def test_client_cannot_override_pack_or_invoke_model_for_stale_or_foreign_profile(signed):
    client, _, _, model = signed
    doc, _ = create(client)
    route = "/api/monitoring-profiles/" + doc["profile"]["id"]
    assert post(client, route + "/suggest", {"expected_revision": 1, "domain_pack": "LegalPack"}).status_code == 422
    assert client.put(route, headers=_csrf(client), json={"expected_revision": 1, "step": 1,
        "config": {**doc["profile"]["config"], "domain_pack": "LegalPack"}}).status_code == 422
    assert post(client, route + "/suggest", {"expected_revision": 2}).status_code == 409
    assert _register(client, "other@example.ch", "Other workspace").status_code == 201
    assert client.get(route).status_code == 404
    assert post(client, route + "/suggest", {"expected_revision": 1}).status_code == 404
    assert model.calls == []


@pytest.mark.parametrize("change", ["revision", "role"])
def test_draft_changed_during_inference_discards_pack_proposals(signed, monkeypatch, change):
    client, service, identity, model = signed
    user_id, cookies = colleague(client, service, identity)
    doc, root = managed(client)
    invitation = invite(client, root, user_id, role="EDITOR")
    switch(client, cookies)
    accept(client, invitation)
    route = "/api/monitoring-profiles/" + doc["profile"]["id"]

    async def changed(*args, **kwargs):
        with service.db.session() as session:
            if change == "role":
                session.get(DossierMember, (doc["id"], user_id)).role = "VIEWER"
            else:
                session.get(LegalMonitoringProfile, doc["profile"]["id"]).revision += 1
            session.commit()
        return TOPICS

    monkeypatch.setattr(model, "complete", changed)
    response = post(client, route + "/suggest", {"expected_revision": 1})
    assert response.status_code == (403 if change == "role" else 409), response.text
    with service.db.session() as session:
        assert session.get(LegalMonitoringProfile, doc["profile"]["id"]).proposals_json == {}


@pytest.mark.parametrize("product,literature", [("pharma", True), ("legal", False), ("loyer", False)])
def test_pack_capabilities_and_real_federation_lanes_agree(monkeypatch, product, literature):
    calls = []

    async def web(*args, **kwargs):
        return {"items": []}

    async def public(provider, query):
        calls.append(provider)
        return {"items": []}

    monkeypatch.setattr(decision_search, "retrieve", web)
    monkeypatch.setattr(product_research, "public_search", public)
    capabilities = product_investigations.capabilities(Settings(), product)
    assert next(x for x in capabilities if x["id"] == "scientific_literature")["available"] is literature
    asyncio.run(decision_search.federated_retrieve(Settings(), "evidence", "web", "deep", product))
    assert calls == (["europepmc"] if literature else [])
    calls.clear()
    asyncio.run(decision_search.federated_retrieve(Settings(), "evidence", "web", "quick", product))
    assert calls == []


def test_unknown_product_is_rejected_before_any_retrieval():
    with pytest.raises(DomainError, match="not supported"):
        domain_packs.for_product("GENERAL")
    with pytest.raises(DomainError, match="not supported"):
        asyncio.run(decision_search.federated_retrieve(Settings(), "evidence", "web", "quick", "unknown"))
