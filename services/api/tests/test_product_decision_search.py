"""Behavior, provenance, disclosure and failure contracts for both engines."""
import asyncio
import base64
import json
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import delete
from test_auth import _register
from test_product_dossiers import ROOT, create, post
from test_product_dossiers import signed as signed

from helvetic_lens import decision_engines, decision_search, decision_sources
from helvetic_lens.config import Settings
from helvetic_lens.db import utcnow
from helvetic_lens.decision_engines import Decision, DecisionUnavailable
from helvetic_lens.product_decision_search import evaluate
from helvetic_lens.product_models import DecisionSearchBudget, DecisionSearchRun

BASE = "/api/products/pharma/discover"
ITEM = {"id": "a" * 32, "title": "Official medicine evidence", "summary": "A public safety assessment.",
        "url": "https://example.org/evidence", "kind": "web_source", "provider": "Search1API", "date": None}


def command(**kwargs):
    return {"request_key": str(uuid4()), "query": "Public safety evidence", "mode": "compare",
            "public_query_confirmed": True, **kwargs}


def fake_result():
    return {"items": [deepcopy(ITEM)], "selected_engine": "jev", "engines": [
        {"engine": engine, "models": [engine + "-test"], "scores": {ITEM["id"]: {"relevance": score}},
         "latency_ms": 10, "estimated_cost_usd": None} for engine, score in (("jev", .8), ("laya", .2))]}


def mock_pipeline(monkeypatch):
    calls = []
    async def execute(settings, query, mode, depth, product, alternatives=()):
        calls.append((query, mode, depth, product))
        return fake_result()
    monkeypatch.setattr(decision_search, "execute", execute)
    return calls


def transport(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(decision_engines.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw))


@pytest.mark.parametrize("corruption", ["extra_question", "wrong_type", "unknown_choice", "negative", "nan", "wrong_total", "not_argmax", "missing_choice"])
def test_contract_refuses_malformed_probabilities_and_answers(monkeypatch, corruption):
    body = {"model": "test", "answers": {"decision": {"type": "choice", "choice": "A", "probabilities": {"A": .8, "B": .2}, "confidence": .6}}}
    answer = body["answers"]["decision"]
    if corruption == "extra_question":
        body["answers"]["extra"] = answer
    if corruption == "wrong_type":
        answer["type"] = "noul"
    if corruption == "unknown_choice":
        answer["choice"] = "C"
    if corruption == "negative":
        answer["probabilities"] = {"A": 1.2, "B": -.2}
    if corruption == "nan":
        answer["confidence"] = "NaN"
    if corruption == "wrong_total":
        answer["probabilities"] = {"A": .9, "B": .9}
    if corruption == "not_argmax":
        answer["choice"] = "B"
    if corruption == "missing_choice":
        answer["probabilities"] = {"A": 1}
    transport(monkeypatch, lambda request: httpx.Response(200, json=body))
    with pytest.raises(DecisionUnavailable, match="invalid_response"):
        asyncio.run(decision_engines.JevEngine(Settings(typesafe_api_key="test")).choose({"query": "public"}, "Relevant?", {"A": "Yes", "B": "No"}))


def test_unknown_usage_stays_unknown_and_provider_failure_never_echoes_payload(monkeypatch):
    transport(monkeypatch, lambda request: httpx.Response(200, json={"model": "test", "answers": {
        "decision": {"type": "choice", "choice": "A", "probabilities": {"A": .8, "B": .2}, "confidence": .6}}}))
    engine = decision_engines.JevEngine(Settings(typesafe_api_key="do-not-expose"))
    decision = asyncio.run(engine.choose({}, "Relevant?", {"A": "Yes", "B": "No"}))
    assert decision.input_tokens is None and decision.output_tokens is None and decision.selected_probability == .8
    assert decision_engines.measurement("jev", [decision], Settings())["estimated_cost_usd"] is None
    # The actual HTTP status path discards its body, including secrets and query text.
    monkeypatch.undo()
    transport(monkeypatch, lambda request: httpx.Response(401, text="do-not-expose private payload"))
    with pytest.raises(DecisionUnavailable, match="^credentials$"):
        asyncio.run(engine.choose({}, "Relevant?", {"A": "Yes", "B": "No"}))


def test_receipts_history_labels_and_replay_use_real_private_storage(signed, monkeypatch):
    client, service, _, model = signed
    calls = mock_pipeline(monkeypatch)
    doc, _ = create(client)
    data = command()
    assert client.post(BASE + "/decision", json=data).status_code == 403
    assert post(client, BASE + "/decision", {**data, "public_query_confirmed": False}).status_code == 422
    found = post(client, BASE + "/decision", data)
    assert found.status_code == 200, found.text
    result = found.json()
    path = BASE + "/runs/" + result["id"]
    assert len(calls) == 1 and not model.calls and not service.fetcher.calls
    assert post(client, BASE + "/decision", data).json()["id"] == result["id"] and len(calls) == 1
    assert post(client, BASE + "/decision", {**data, "depth": "deep"}).status_code == 409
    assert client.get(BASE + "/runs").json()["items"][0]["id"] == result["id"]
    assert all(v["evaluation"]["accuracy"] is None for v in result["engines"])
    labelled = post(client, path + "/labels", {"expected_revision": 1, "source_id": ITEM["id"], "relevant": True}).json()
    assert [v["evaluation"]["accuracy"] for v in labelled["engines"]] == [1, 0]
    assert post(client, path + "/labels", {"expected_revision": 1, "source_id": ITEM["id"], "relevant": False}).status_code == 409
    assert post(client, path + "/labels", {"expected_revision": 2, "source_id": "b" * 32, "relevant": True}).status_code == 409
    imported = post(client, ROOT + "/" + doc["id"] + "/discovery-references",
        {"request_key": str(uuid4()), "receipt": result["items"][0]["discovery_receipt"]})
    assert imported.status_code == 201 and imported.json()["data"]["discovery"]["provider"] == "web"
    assert client.get(path.replace("pharma", "loyer")).status_code == 404
    assert _register(client, "other-search@example.ch").status_code == 201
    assert client.get(path).status_code == 404 and client.get(BASE + "/runs").json()["items"] == []
    client.cookies.clear()
    assert client.get(path).status_code == 401 and client.get(BASE + "/engines").status_code == 401


def test_history_does_not_renew_old_source_receipts_and_quota_survives_erasure(signed, monkeypatch):
    client, service, _, _ = signed
    mock_pipeline(monkeypatch)
    service.environment_settings.search1api_api_key = SecretStr("fixture")
    service.environment_settings.decision_search_daily_limit = 2
    data = command()
    found = post(client, BASE + "/decision", data).json()
    with service.db.session() as session:
        row = session.get(DecisionSearchRun, found["id"])
        row.created_at = utcnow() - timedelta(minutes=31)
        session.commit()
    old = client.get(BASE + "/runs/" + found["id"]).json()
    receipt = json.loads(base64.urlsafe_b64decode(old["items"][0]["discovery_receipt"]))
    assert receipt["retrieved_at"] == old["checked_at"]
    doc, _ = create(client)
    assert post(client, ROOT + "/" + doc["id"] + "/discovery-references",
        {"request_key": str(uuid4()), "receipt": old["items"][0]["discovery_receipt"]}).status_code == 409
    with service.db.session() as session:
        session.execute(delete(DecisionSearchRun))
        session.commit()
        assert session.get(DecisionSearchBudget, utcnow().date()).used == 2
    fallback = post(client, BASE + "/decision", command())
    assert fallback.status_code == 200
    assert fallback.json()["retrieval"]["skipped_channels"][0]["name"] == "Search1API"


def test_finished_network_failure_is_saved_and_not_repeated_by_retry(signed, monkeypatch):
    client, service, _, _ = signed
    calls = []
    async def failed(*args):
        calls.append(1)
        raise DecisionUnavailable("quota")
    monkeypatch.setattr(decision_search, "execute", failed)
    service.environment_settings.search1api_api_key = SecretStr("never-visible")
    data = command()
    result = post(client, BASE + "/decision", data).json()
    assert result["status"] == "failed" and result["error_code"] == "quota"
    assert post(client, BASE + "/decision", data).json()["id"] == result["id"] and len(calls) == 1
    assert "never-visible" not in client.get(BASE + "/engines").text


def test_same_candidates_compare_and_primary_failure_falls_back_without_new_retrieval(monkeypatch):
    calls = []
    class Engine:
        def __init__(self, name): self.name = name
        async def choose(self, state, instructions, criteria):
            calls.append((self.name, deepcopy(state)))
            if self.name == "jev" and "snippet" in state:
                raise DecisionUnavailable("quota")
            choice = next(iter(criteria))
            probs = {key: .8 if key == choice else .2 for key in criteria}
            return Decision(self.name, "tested-" + self.name, choice, probs, .6, .8, 10, 100, 0)
    monkeypatch.setattr(decision_engines, "engines", lambda s: {name: Engine(name) for name in ("jev", "laya")})
    retrievals = []
    async def retrieve(*args):
        retrievals.append(args[1])
        return {"items": [deepcopy(ITEM)], "candidate_limit": 24}
    monkeypatch.setattr(decision_search, "federated_retrieve", retrieve)
    result = asyncio.run(decision_search.execute(Settings(), "Public query", "auto"))
    assert result["selected_engine"] == "laya" and retrievals == ["Public query"]
    states = [value for _, value in calls if "snippet" in value]
    assert states[0] == states[1] and set(states[0]) == {"query", "title", "snippet"}
    assert result["engines"][0]["error"] == "quota" and result["engines"][0]["estimated_cost_usd"] is None
    calls.clear()
    result = asyncio.run(decision_search.execute(Settings(), "Public query", "laya"))
    assert {name for name, _ in calls} == {"laya"}


@pytest.mark.parametrize("url", ["http://example.org/", "https://127.0.0.1/", "https://192.168.1.2/", "https://name.local/", "https://user:pass@example.org/", "javascript:alert(1)", "https://example.org:8080/a", "https://example.org/\\bad"])
def test_unsafe_links_cannot_become_discovery_candidates(url):
    assert decision_search.public_url(url) is None


def test_federation_deduplicates_and_reports_partial_source_failure(monkeypatch):
    async def retrieve(settings, query, index, **kwargs):
        if kwargs.get("service") == "bing":
            raise DecisionUnavailable("quota")
        return {"items": [deepcopy(ITEM), {**ITEM, "url": ITEM["url"] + "#fragment"}], "omitted_records": 0}
    from helvetic_lens import search_channels
    async def catalogue(*args): return {"items": [], "omitted_records": 0}
    monkeypatch.setattr(decision_search, "retrieve", retrieve)
    monkeypatch.setattr(search_channels, "direct_search", catalogue)
    result = asyncio.run(decision_search.federated_retrieve(Settings(), "public", "web", "deep", "pharma"))
    assert len(result["items"]) == 1 and result["candidate_limit"] == 36
    assert result["lanes"][1]["status"] == "unavailable" and result["lanes"][2]["status"] == "complete"


def test_inspection_is_explicit_cached_and_does_not_create_monitoring(signed, monkeypatch):
    client, service, _, _ = signed
    mock_pipeline(monkeypatch)
    service.environment_settings.search1api_api_key = SecretStr("fixture")
    found = post(client, BASE + "/decision", command()).json()
    with service.db.session() as session:
        saved = session.get(DecisionSearchRun, found["id"])
        saved.result_json = {**saved.result_json, "inspections": {
            character * 32: {"status": "complete"} for character in "bcd"}}
        session.commit()
    calls = []
    async def inspect(*args):
        calls.append(args[1:])
        return {"status": "complete", "url": ITEM["url"], "links": []}
    monkeypatch.setattr(decision_sources, "safe_inspect", inspect)
    path = BASE + "/runs/" + found["id"] + "/inspect"
    body = {"source_id": ITEM["id"], "public_fetch_confirmed": True}
    assert client.post(path, json=body).status_code == 403
    assert post(client, path, {**body, "public_fetch_confirmed": False}).status_code == 422
    assert post(client, path, body).json()["inspections"][ITEM["id"]]["status"] == "complete"
    assert post(client, path, body).status_code == 200 and len(calls) == 1
    assert not service.fetcher.calls and client.get(ROOT).json()["total"] == 0


def test_robots_denial_makes_no_document_or_model_request(monkeypatch):
    calls = []
    async def read(client, url, limit):
        calls.append(url)
        return 200, "text/plain", b"User-agent: *\nDisallow: /"
    monkeypatch.setattr(decision_sources, "read_bytes", read)
    result = asyncio.run(decision_sources.safe_inspect(Settings(), "public", ITEM, "auto"))
    assert result["status"] == "unavailable" and calls == ["https://example.org/robots.txt"]


def test_label_metrics_are_not_model_confidence():
    scores = {"one": {"relevance": .9}, "two": {"relevance": .3}}
    assert evaluate(scores, {})["accuracy"] is None
    metric = evaluate(scores, {"one": False, "two": False})
    assert metric["accuracy"] == .5 and metric["labelled_count"] == 2
    assert metric["brier_score"] == pytest.approx(.45)


def test_comparison_uses_identical_candidates_and_keeps_estimate_separate(monkeypatch):
    calls = []
    class Engine:
        def __init__(self, name): self.name = name
        async def choose(self, state, instructions, criteria):
            calls.append((self.name, deepcopy(state)))
            choice = next(iter(criteria))
            probabilities = {key: .8 if key == choice else .2 for key in criteria}
            return Decision(self.name, "tested-" + self.name, choice, probabilities, .6, .8, 10, 100, 0)
    monkeypatch.setattr(decision_engines, "engines", lambda s: {name: Engine(name) for name in ("jev", "laya")})
    retrievals = []
    async def retrieve(*args):
        retrievals.append(args[1])
        return {"items": [deepcopy(ITEM)], "candidate_limit": 24}
    monkeypatch.setattr(decision_search, "federated_retrieve", retrieve)
    settings = Settings(jev_input_usd_per_million=.042, jev_output_usd_per_million=0)
    result = asyncio.run(decision_search.execute(settings, "public query", "compare"))
    assert result["selected_engine"] == "jev" and retrievals == ["public query"]
    assert [state for name, state in calls if name == "jev"] == [state for name, state in calls if name == "laya"]
    assert len(result["candidates_sha256"]) == 64
    assert result["engines"][0]["estimated_cost_usd"] == pytest.approx(.0000084)
    assert result["engines"][1]["estimated_cost_usd"] is None
    assert "accuracy" not in result["engines"][0]


def test_inspection_extracts_original_text_hash_and_safe_links_without_following_them(monkeypatch):
    import hashlib
    body = (b'<html><main><p>Medicine safety is reviewed against primary evidence.</p>'
            b'<a href="/paper">Primary paper</a><a href="http://example.org/unsafe">Insecure</a>'
            b'<a href="https://127.0.0.1/private">Private</a></main></html>')
    calls, model_calls = [], []
    async def read(client, url, limit):
        calls.append(url)
        return (404, "text/plain", b"") if url.endswith("robots.txt") else (200, "text/html", body)
    async def rank(engine, query, items):
        model_calls.extend(items)
        return [(v["id"], Decision("laya", "test", "A", {"A": .9, "B": .1}, .7, .9, 1, 20, 0)) for v in items]
    monkeypatch.setattr(decision_sources, "read_bytes", read)
    monkeypatch.setattr(decision_sources, "rank", rank)
    result = asyncio.run(decision_sources.safe_inspect(Settings(), "medicine safety", ITEM, "laya"))
    assert result["status"] == "complete" and result["engine"] == "laya"
    assert result["sha256"] == hashlib.sha256(body).hexdigest()
    assert result["links"] == [{"title": "Primary paper", "url": "https://example.org/paper"}]
    assert "Medicine safety is reviewed" in result["excerpts"][0]["text"]
    assert len(model_calls) <= 8 and calls == ["https://example.org/robots.txt", ITEM["url"]]


def test_explicit_booleans_viewer_denial_and_interrupted_inspection(signed, monkeypatch):
    from sqlalchemy import select

    from helvetic_lens.models import OrganizationMembership
    client, service, person, _ = signed
    calls = mock_pipeline(monkeypatch)
    assert post(client, BASE + "/decision", command(public_query_confirmed=1)).status_code == 422
    found = post(client, BASE + "/decision", command()).json()
    path = BASE + "/runs/" + found["id"]
    assert post(client, path + "/inspect", {"source_id": ITEM["id"], "public_fetch_confirmed": 1}).status_code == 422
    with service.db.session() as session:
        row = session.get(DecisionSearchRun, found["id"])
        row.result_json = {**row.result_json, "inspections": {ITEM["id"]: {
            "status": "running", "url": ITEM["url"], "started_at": (utcnow() - timedelta(minutes=3)).isoformat()}}}
        member = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == person["user"]["id"]))
        member.role = "viewer"
        session.commit()
    assert client.get(path).json()["inspections"][ITEM["id"]]["status"] == "interrupted"
    assert post(client, BASE + "/decision", command()).status_code == 403
    assert post(client, path + "/labels", {"source_id": ITEM["id"], "expected_revision": 1, "relevant": True}).status_code == 403
    assert post(client, path + "/inspect", {"source_id": ITEM["id"], "public_fetch_confirmed": True}).status_code == 403
    assert len(calls) == 1


def test_invalid_local_configuration_does_not_disable_hosted_adapter(monkeypatch):
    configured = decision_engines.engines(Settings(typesafe_api_key="test", laya_base_url="https://untrusted.example/v1/systemone"))
    assert configured["jev"].url == decision_engines.JEV_URL
    with pytest.raises(DecisionUnavailable, match="invalid_configuration"):
        asyncio.run(configured["laya"].choose({}, "Question", {"A": "Yes", "B": "No"}))


def test_real_native_erasure_removes_private_search_but_preserves_aggregate_budget(signed, monkeypatch):
    from helvetic_lens.account_erasure_store import erase_selected, select_private_rows
    from helvetic_lens.models import User
    client, service, person, _ = signed
    mock_pipeline(monkeypatch)
    service.environment_settings.search1api_api_key = SecretStr("fixture")
    found = post(client, BASE + "/decision", command()).json()
    with service.db.session(include_all_organizations=True) as session:
        user = session.get(User, person["user"]["id"])
        selection = select_private_rows(session, user, [person["organization"]["id"]])
        assert selection.counts["product_decision_search_runs"] == 1
        assert "product_decision_search_budgets" not in selection.counts
        erase_selected(session, user, selection)
        session.commit()
        assert session.get(DecisionSearchRun, found["id"]) is None
        assert session.get(DecisionSearchBudget, utcnow().date()).used == 2
        assert session.connection().exec_driver_sql("PRAGMA foreign_key_check").all() == []
