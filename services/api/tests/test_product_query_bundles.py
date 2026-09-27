"""Query bundles retain explicit disclosure, spend bounds and exact provenance."""
import asyncio
import base64
import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_product_decision_search import BASE, ITEM, command, fake_result
from test_product_dossiers import ROOT, create, post
from test_product_dossiers import signed as signed

from helvetic_lens import decision_search, product_provenance, product_research
from helvetic_lens.config import Settings
from helvetic_lens.db import utcnow
from helvetic_lens.decision_engines import DecisionUnavailable
from helvetic_lens.models import OrganizationMembership, User, UserSession
from helvetic_lens.product_models import DecisionSearchBudget, DecisionSearchRun, DossierEntry

DRAFT = {"alternatives": [
    {"language": "de", "query": "Arzneimittelsicherheit Swissmedic", "reason": "Search official German terminology."},
    {"language": "fr", "query": "Swissmedic sécurité des médicaments", "reason": "Find the corresponding French source vocabulary."}]}


def expansion(**kwargs):
    return {"question": "Swissmedic medicine safety", "languages": ["de", "fr"],
        "public_question_confirmed": True, **kwargs}


@pytest.mark.parametrize("product", ["pharma", "loyer"])
def test_draft_uses_only_reviewed_question_and_languages_without_retrieval_or_writes(signed, monkeypatch, product):
    client, service, _, model = signed
    doc, _ = create(client)
    post(client, ROOT + "/" + doc["id"] + "/entries", {"request_key": str(uuid4()), "kind": "note", "body": "PRIVATE CLIENT CONTEXT"})
    async def forbidden(*args, **kwargs): pytest.fail("A draft must not retrieve sources")
    monkeypatch.setattr(decision_search, "retrieve", forbidden)
    with service.db.session() as session:
        before = session.scalar(select(func.count()).select_from(DossierEntry))
    model.responses = [json.dumps(DRAFT)]
    response = post(client, BASE.replace("pharma", product) + "/expand", expansion())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["alternatives"] == DRAFT["alternatives"] and body["searched"] is False
    assert body["question"] == expansion()["question"] and "no-store" in response.headers["cache-control"]
    assert len(model.calls) == 1 and "PRIVATE CLIENT CONTEXT" not in str(model.calls)
    assert json.loads(model.calls[0][1]) == {"product": product, "question": expansion()["question"], "languages": {"de": "German", "fr": "French"}}
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(DossierEntry)) == before
        assert session.scalar(select(func.count()).select_from(DecisionSearchRun)) == 0
        assert session.get(DecisionSearchBudget, utcnow().date()) is None


@pytest.mark.parametrize("draft", [
    "not JSON", {"alternatives": []},
    {"alternatives": [DRAFT["alternatives"][0]]},
    {"alternatives": [DRAFT["alternatives"][0], DRAFT["alternatives"][0]]},
    {"alternatives": [{**DRAFT["alternatives"][0], "language": "en"}, DRAFT["alternatives"][1]]},
    {"alternatives": [{**DRAFT["alternatives"][0], "query": expansion()["question"]}, DRAFT["alternatives"][1]]},
    {**DRAFT, "findings": ["Invented answer"]},
])
def test_invalid_language_or_finding_draft_is_not_partially_returned(signed, draft):
    client, _, _, model = signed
    model.responses = [json.dumps(draft) if isinstance(draft, dict) else draft]
    response = post(client, BASE + "/expand", expansion())
    assert response.status_code == 502 and "alternatives" not in response.json()
    assert "unchanged" in response.json()["detail"]


@pytest.mark.parametrize("change", [
    {"public_question_confirmed": 1}, {"public_question_confirmed": False},
    {"languages": ["de", "de"]}, {"languages": ["de", "fr", "it"]},
    {"languages": ["unknown"]}, {"question": "  "}, {"dossier_id": "private"},
])
def test_invalid_expansion_never_calls_model(signed, change):
    client, _, _, model = signed
    assert post(client, BASE + "/expand", expansion(**change)).status_code == 422
    assert not model.calls


def test_expand_requires_csrf_and_current_session_after_generation(signed):
    client, service, person, model = signed
    assert client.post(BASE + "/expand", json=expansion()).status_code == 403
    assert not model.calls
    async def revoked(*args, **kwargs):
        with service.db.session() as session:
            login = session.scalar(select(UserSession).where(UserSession.user_id == person["user"]["id"]))
            login.revoked_at = utcnow()
            session.commit()
        return json.dumps(DRAFT)
    model.complete = revoked
    response = post(client, BASE + "/expand", expansion())
    assert response.status_code == 401 and "alternatives" not in response.json()


def test_viewer_cannot_send_question_to_draft_provider(signed):
    client, service, person, model = signed
    with service.db.session() as session:
        membership = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == person["user"]["id"]))
        membership.role = "viewer"
        session.commit()
    assert post(client, BASE + "/expand", expansion()).status_code == 403
    assert not model.calls


def test_bundle_budget_replay_and_signed_exact_query_import(signed, monkeypatch):
    client, service, _, _ = signed
    calls = []
    alternatives = ["Arzneimittelsicherheit", "sécurité <script>médicaments</script>"]
    async def execute(settings, query, mode, depth, product, reviewed):
        with service.db.session() as session:
            running = session.scalar(select(DecisionSearchRun))
            assert running.status == "running" and running.result_json["queries"] == [data["query"], *alternatives]
        calls.append(list(reviewed))
        result = fake_result()
        result["items"][0]["retrieval_queries"] = list(reviewed)
        return result
    monkeypatch.setattr(decision_search, "execute", execute)
    data = command(alternatives=alternatives)
    service.environment_settings.decision_search_daily_limit = 2
    assert post(client, BASE + "/decision", data).status_code == 429 and not calls
    service.environment_settings.decision_search_daily_limit = 3
    response = post(client, BASE + "/decision", data)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["queries"] == [data["query"], *alternatives] and calls == [alternatives]
    assert post(client, BASE + "/decision", data).json()["id"] == result["id"] and len(calls) == 1
    assert post(client, BASE + "/decision", {**data, "alternatives": ["other wording"]}).status_code == 409
    with service.db.session() as session:
        assert session.get(DecisionSearchBudget, utcnow().date()).used == 3
    doc, _ = create(client)
    path = ROOT + "/" + doc["id"]
    imported = post(client, path + "/discovery-references", {"request_key": str(uuid4()), "receipt": result["items"][0]["discovery_receipt"]})
    assert imported.status_code == 201, imported.text
    assert imported.json()["data"]["discovery"]["record"]["retrieval_queries"] == alternatives
    brief = client.get(path + "/brief")
    assert alternatives[0] in brief.text and "&lt;script&gt;médicaments&lt;/script&gt;" in brief.text and "<script>" not in brief.text
    assert client.get(path + "/export").json()["entries"][0]["data"]["discovery"]["record"]["retrieval_queries"] == alternatives
    receipt = json.loads(base64.urlsafe_b64decode(result["items"][0]["discovery_receipt"]))
    receipt["record"]["retrieval_queries"] = ["forged"]
    altered = base64.urlsafe_b64encode(json.dumps(receipt).encode()).decode()
    assert post(client, path + "/discovery-references", {"request_key": str(uuid4()), "receipt": altered}).status_code == 409


def test_duplicate_and_overlong_queries_never_reach_provider(signed, monkeypatch):
    client, _, _, _ = signed
    async def forbidden(*args): pytest.fail("Invalid bundle reached a provider")
    monkeypatch.setattr(decision_search, "execute", forbidden)
    for values in [["one", "two", "three"], ["a"], ["x" * 301], ["same", "SAME"], ["Public safety evidence"]]:
        assert post(client, BASE + "/decision", command(alternatives=values)).status_code == 422


def test_each_alternative_has_attributable_partial_lane_and_one_deduplicated_pool(monkeypatch):
    calls = []
    async def retrieve(settings, query, index, **kwargs):
        calls.append((query, kwargs.get("service", "google")))
        if query == "français":
            raise DecisionUnavailable("unavailable")
        return {"items": [deepcopy(ITEM)], "omitted_records": 0}
    async def literature(*args): return {"items": [], "omitted_records": 0}
    monkeypatch.setattr(decision_search, "retrieve", retrieve)
    monkeypatch.setattr(product_research, "public_search", literature)
    result = asyncio.run(decision_search.federated_retrieve(Settings(), "English", "web", "deep", "pharma", ["Deutsch", "français"]))
    assert calls == [("English", "google"), ("English", "bing"), ("Deutsch", "google"), ("français", "google")]
    assert len(result["items"]) == 1 and result["candidate_limit"] == 36 and result["search_requests"] == 5
    assert result["items"][0]["retrieval_queries"] == ["English", "Deutsch"]
    assert result["lanes"][-1] == {"name": "Google alternative 2", "query": "français", "status": "unavailable", "count": 0}
    assert result["omitted_records"] == 2


def test_pre_bundle_history_retry_and_signed_receipt_remain_usable(signed, monkeypatch):
    client, service, person, _ = signed
    async def execute(*args): return fake_result()
    monkeypatch.setattr(decision_search, "execute", execute)
    data = command()
    result = post(client, BASE + "/decision", data).json()
    receipt = json.loads(base64.urlsafe_b64decode(result["items"][0]["discovery_receipt"]))
    receipt.pop("signature")
    receipt["record"].pop("retrieval_queries")
    with service.db.session() as session:
        row = session.get(DecisionSearchRun, result["id"])
        legacy = deepcopy(row.result_json)
        legacy.pop("queries")
        row.result_json = legacy
        user = session.get(User, person["user"]["id"])
        login = session.scalar(select(UserSession).where(UserSession.user_id == user.id))
        identity = SimpleNamespace(user_id=user.id, organization_id=login.organization_id, session_id=login.id)
        receipt["signature"] = product_provenance.signature(user, identity, receipt)
        session.commit()
    async def forbidden(*args): pytest.fail("Legacy retry must not repeat retrieval")
    monkeypatch.setattr(decision_search, "execute", forbidden)
    replay = post(client, BASE + "/decision", {**data, "alternatives": []})
    assert replay.status_code == 200 and replay.json()["queries"] == [data["query"]]
    doc, _ = create(client)
    imported = post(client, ROOT + "/" + doc["id"] + "/discovery-references", {
        "request_key": str(uuid4()), "receipt": base64.urlsafe_b64encode(product_provenance.canonical(receipt).encode()).decode()})
    assert imported.status_code == 201, imported.text
    assert "retrieval_queries" not in imported.json()["data"]["discovery"]["record"]
