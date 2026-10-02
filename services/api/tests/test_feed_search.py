"""Machine discovery cannot authorize user data or silently spend paid credits."""
import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from test_auth import _settings

from helvetic_lens import feed_search
from helvetic_lens.decision_engines import DecisionUnavailable
from helvetic_lens.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    async def search(settings, query, index, limit):
        assert settings.searxng_base_url == "http://local-search"
        assert index == "web" and limit == 12
        return {"status": "partial", "items": [{"title": "Public decision", "url": "https://bger.ch/decision", "summary": query}]}
    monkeypatch.setattr(feed_search, "searxng", search)
    settings = _settings(tmp_path, legal_feed_search_token="test-service-key", searxng_base_url="http://local-search")
    with TestClient(create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())) as result:
        result.app.state.feed_test_settings = settings
        yield result


AUTH = {"Authorization": "Bearer test-service-key"}


def test_bridge_auth_is_exact_and_does_not_authorize_private_routes(client):
    for headers in ({}, {"Authorization": "Bearer wrong"}):
        assert client.post(feed_search.PATH, json={"query": "Ozempic"}, headers=headers).status_code == 401
    assert client.get("/api/products/legal/dossiers", headers=AUTH).status_code == 401
    result = client.post(feed_search.PATH, json={"query": "site:bger.ch Ozempic"}, headers=AUTH)
    assert result.status_code == 200
    assert result.json() == {"provider": "SearXNG", "partial": True, "results": [
        {"title": "Public decision", "link": "https://bger.ch/decision", "snippet": "site:bger.ch Ozempic"}]}
    assert result.headers["cache-control"] == "no-store"


def test_bridge_bounds_input_and_rate_without_echoing_private_requests(client):
    assert client.get(feed_search.PATH, headers=AUTH).status_code == 405
    for body in ({"query": "ok"}, {"query": "x" * 4001}, {"query": "Ozempic", "url": "http://private"}):
        result = client.post(feed_search.PATH, json=body, headers=AUTH)
        assert result.status_code == 422 and "private" not in result.text
    assert client.post(feed_search.PATH, content=b"x" * 24001, headers=AUTH).status_code == 413
    for _ in range(26):
        assert client.post(feed_search.PATH, json={"query": "Ozempic"}, headers=AUTH).status_code == 200
    assert client.post(feed_search.PATH, json={"query": "Ozempic"}, headers=AUTH).status_code == 429


def test_bridge_reports_upstream_outage_and_is_disabled_without_key(client, monkeypatch):
    async def fail(*args, **kwargs):
        raise DecisionUnavailable("private upstream detail")
    monkeypatch.setattr(feed_search, "searxng", fail)
    result = client.post(feed_search.PATH, json={"query": "Ozempic"}, headers=AUTH)
    assert result.status_code == 503 and "private" not in result.text
    from pydantic import SecretStr
    client.app.state.feed_test_settings.legal_feed_search_token = SecretStr("")
    assert client.post(feed_search.PATH, json={"query": "Ozempic"}, headers=AUTH).status_code == 401


def test_discarded_results_are_not_a_successful_empty_search(client, monkeypatch):
    async def invalid(*args, **kwargs):
        return {"items": [], "omitted_records": 2, "status": "complete"}
    monkeypatch.setattr(feed_search, "searxng", invalid)
    assert client.post(feed_search.PATH, json={"query": "Ozempic"}, headers=AUTH).status_code == 503
    async def empty(*args, **kwargs):
        return {"items": [], "omitted_records": 0, "status": "complete"}
    monkeypatch.setattr(feed_search, "searxng", empty)
    result = client.post(feed_search.PATH, json={"query": "Ozempic"}, headers=AUTH)
    assert result.status_code == 200 and result.json()["results"] == []
