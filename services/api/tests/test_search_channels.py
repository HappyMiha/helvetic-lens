"""Real adapters and native research with controlled external failures."""
import asyncio

import httpx
import pytest
from pydantic import SecretStr
from test_product_decision_search import BASE, command, transport
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_iterative_research import complete, pipeline, start

from helvetic_lens import decision_engines, decision_search, search_channels
from helvetic_lens.config import Settings
from helvetic_lens.product_provenance import SourceRecord


def test_searxng_normalizes_partial_results_and_never_uses_paid_fallback(monkeypatch):
    calls = []
    def handle(request):
        calls.append(request)
        assert request.url.host == "local-search" and "authorization" not in request.headers
        assert request.url.params["engines"] == "google,bing,yahoo"
        return httpx.Response(200, json={"results": [
            {"url": "https://example.org/evidence#page", "title": "<b>Material reuse</b>", "content": "<p>Publication summary</p>"},
            {"url": "http://127.0.0.1/private", "title": "Local secret"},
            {"url": "https://example.org/invalid", "title": 12}],
            "unresponsive_engines": [["bing", "PRIVATE UPSTREAM BODY"]]})
    transport(monkeypatch, handle)
    settings = Settings(web_search_provider="searxng", searxng_base_url="http://local-search:8080", search1api_api_key="unused")
    result = asyncio.run(decision_search.retrieve(settings, "building reuse", "news"))
    assert len(calls) == 1 and len(result["items"]) == 1
    assert result["status"] == "partial" and result["unavailable_engines"] == ["bing"]
    assert "PRIVATE" not in str(result)
    assert SourceRecord.model_validate(result["items"][0]).provider == "SearXNG"
    assert result["items"][0]["url"] == "https://example.org/evidence"
    assert result["index"] == "web"  # We do not claim an unconfigured news engine.


@pytest.mark.parametrize("body", [b"not-json", b"x" * (search_channels.MAX_BYTES + 1), b'{"results":{},"unresponsive_engines":[]}'])
def test_searxng_refuses_malformed_or_oversized_responses(monkeypatch, body):
    transport(monkeypatch, lambda request: httpx.Response(200, content=body))
    with pytest.raises(decision_engines.DecisionUnavailable):
        asyncio.run(search_channels.searxng(Settings(searxng_base_url="http://local-search"), "reuse", "web"))


def test_direct_catalogue_survives_web_outage_and_records_empty_distinctly(monkeypatch):
    calls = []
    def handle(request):
        calls.append(request.url.host)
        if request.url.host == "local-search":
            return httpx.Response(503)
        assert request.url.host == "api.crossref.org"
        return httpx.Response(200, json={"message": {"items": [{"DOI": "10.123/test", "URL": "https://doi.org/10.123/test",
            "title": ["Building material reuse"], "abstract": "<jats:p>Publisher-supplied abstract.</jats:p>"}]}})
    transport(monkeypatch, handle)
    from helvetic_lens import product_research, research_catalogues
    async def empty(provider, query, *args, **kwargs):
        assert provider in {"fedlex", "finma_news", "federal_court"}
        return {"items": []}
    monkeypatch.setattr(product_research, "public_search", empty)
    monkeypatch.setattr(research_catalogues, "search", empty)
    settings = Settings(web_search_provider="searxng", searxng_base_url="http://local-search")
    result = asyncio.run(decision_search.federated_retrieve(settings, "building reuse", "web", "balanced", "legal"))
    assert calls == ["local-search", "api.crossref.org"]
    assert result["search_requests"] == search_channels.request_count(settings, product="legal") == 7
    assert [lane["status"] for lane in result["lanes"]] == ["unavailable", "complete", "complete", "complete", "complete"]
    assert result["lanes"][-1]["count"] == 0
    assert SourceRecord.model_validate(result["items"][0]).provider == "Crossref"


def test_submitted_url_survives_all_discovery_failures_and_none_skips_broad_search(monkeypatch):
    calls = []
    async def unavailable(provider, query):
        calls.append(provider)
        raise decision_engines.DecisionUnavailable("unavailable")
    monkeypatch.setattr(search_channels, "direct_search", unavailable)
    settings = Settings(web_search_provider="none")
    result = asyncio.run(decision_search.federated_retrieve(settings, "material reuse", "web", "balanced", "legal",
        public_sources=["https://example.org/report", "https://127.0.0.1/private"]))
    assert calls == ["crossref", "fedlex", "federal_court", "finma_news"]
    assert result["search_requests"] == 6
    assert [v["url"] for v in result["items"]] == ["https://example.org/report"]
    assert result["items"][0]["provider"] == "Submitted public source"


@pytest.mark.parametrize("product", ["legal", "pharma"])
def test_native_research_reads_and_analyses_direct_sources_when_web_is_down(signed, monkeypatch, product):
    client, service, _, model = signed
    native_federation = decision_search.federated_retrieve
    trace = pipeline(monkeypatch, service, model)
    fixture_retrieval = decision_search.federated_retrieve
    monkeypatch.setattr(decision_search, "federated_retrieve", native_federation)
    service.settings.decision_search_daily_limit = 0
    service.settings.web_search_provider = "searxng"
    service.settings.searxng_base_url = "http://local-search"
    service.settings.search1api_api_key = SecretStr("")
    async def unavailable(*args, **kwargs):
        raise decision_engines.DecisionUnavailable("unavailable")
    async def direct(provider, query):
        if provider != "crossref":
            return {"items": []}
        result = await fixture_retrieval(service.settings, query, "web", "balanced", product)
        for item in result["items"]:
            item.update(provider="Crossref", kind="literature", date=None)
        return result
    monkeypatch.setattr(decision_search, "retrieve", unavailable)
    monkeypatch.setattr(search_channels, "direct_search", direct)
    root, run, _ = start(client, product=product)
    result = complete(client, service, root, run)
    assert result["status"] == "completed", result
    assert len(result["sources"]) == 3 and len(trace["reads"]) == 3
    assert result["claims"][0]["status"] == "CONTESTED"
    assert result["research"]["used"]["search_requests"] == 0
    coverages = [b["coverage"] for b in result["branches"] if b.get("coverage")]
    assert coverages and all(c["retrieval"]["lanes"][0]["status"] == "unavailable" for c in coverages)


@pytest.mark.parametrize("provider", ["Crossref", "SearXNG"])
def test_new_provider_results_retain_signed_discovery_receipts(signed, monkeypatch, provider):
    client, _, _, _ = signed
    async def execute(*args):
        return {"items": [{"id": "a" * 32, "kind": "web_source", "provider": provider, "title": "Building reuse",
            "summary": "Public discovery metadata", "url": "https://example.org/reuse", "date": None}], "engines": []}
    monkeypatch.setattr(decision_search, "execute", execute)
    result = post(client, BASE + "/decision", command())
    assert result.status_code == 200, result.text
    assert result.json()["items"][0]["discovery_receipt"]


def test_free_search_rotates_same_day_history_without_consuming_paid_allowance(signed, monkeypatch):
    from uuid import uuid4

    from sqlalchemy import func, select

    from helvetic_lens.db import utcnow
    from helvetic_lens.product_models import DecisionSearchBudget, DecisionSearchRun
    client, service, person, _ = signed
    service.environment_settings.web_search_provider = "searxng"
    service.environment_settings.searxng_base_url = "http://local-search"
    service.environment_settings.decision_search_daily_limit = 0
    with service.db.session() as session:
        session.add(DecisionSearchBudget(day=utcnow().date(), used=1000))
        for _ in range(50):
            session.add(DecisionSearchRun(product="pharma", organization_id=person["organization"]["id"],
                owner_user_id=person["user"]["id"], request_key=str(uuid4()), fingerprint="a" * 64,
                query="Saved public search", mode="laya", status="complete"))
        session.commit()
    async def execute(settings, *args):
        assert settings.web_search_provider == "searxng"
        return {"items": [], "engines": []}
    monkeypatch.setattr(decision_search, "execute", execute)
    response = post(client, BASE + "/decision", command(mode="laya"))
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "complete"
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(DecisionSearchRun)) == 50
        assert session.get(DecisionSearchBudget, utcnow().date()).used == 1000
    assert client.get(BASE + "/engines").json()["free_search_query_limit"] is None
