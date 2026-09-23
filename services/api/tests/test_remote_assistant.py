"""Real adapter, synthetic HTTP only: remote routing must retain personal isolation."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import httpx
import pytest
from conftest import FakeFetcher
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select
from test_auth import _csrf, _register, _settings
from test_settings import configuration, transport

from helvetic_lens.config import SWISSCOM_WEEKS_BASE_URL, SWISSCOM_WEEKS_MODEL
from helvetic_lens.main import create_app
from helvetic_lens.models import IntegrationLog


class NoLocalInference:
    def __getattr__(self, name):
        raise AssertionError(f"Remote selection must not call the local manager: {name}")


@pytest.fixture
def remote(tmp_path):
    settings = _settings(tmp_path).model_copy(update={
        "apertus_provider": "swisscom", "apertus_base_url": SWISSCOM_WEEKS_BASE_URL,
        "apertus_model": SWISSCOM_WEEKS_MODEL, "apertus_api_key": SecretStr("synthetic-shared-key"),
        "apertus_request_retries": 0, "apertus_json_mode": False,
    })
    app = create_app(settings, fetcher=FakeFetcher())
    with TestClient(app) as client:
        identity = _register(client).json()
        app.state.service.model_manager = NoLocalInference()
        yield app, client, identity


def conversation(client):
    response = client.post("/api/assistant/conversations", headers=_csrf(client),
        json={"route": "/sources", "locale": "en-CH"})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def message(client, key, text):
    return client.post(f"/api/assistant/conversations/{key}/messages", headers=_csrf(client),
        json={"message": text, "tone": "dry"})


def test_remote_chat_and_remarks_use_default_provider_without_shared_prompt_logs(remote, monkeypatch):
    app, client, _ = remote
    active = client.get("/api/settings/apertus").json()
    assert active["source"] == "environment" and active["provider"] == "swisscom"
    assert "synthetic-shared-key" not in json.dumps(active)
    runtime = client.get("/api/assistant/runtime").json()
    assert runtime["execution"] == "remote" and runtime["ready"]
    assert runtime["selected_model"]["served_model_id"] == SWISSCOM_WEEKS_MODEL
    calls = []

    def respond(request):
        payload = json.loads(request.content)
        calls.append(payload)
        assert request.url == SWISSCOM_WEEKS_BASE_URL + "/chat/completions"
        assert request.headers["authorization"] == "Bearer synthetic-shared-key"
        assert payload["model"] == SWISSCOM_WEEKS_MODEL
        assert '"additionalProperties": false' in payload["messages"][0]["content"]
        assert payload["max_tokens"] <= 260 and "response_format" not in payload
        content = ({"angle": "queue"} if '"angle"' in payload["messages"][0]["content"] else
            {"reply": "Hello. I can help you navigate this workspace.", "requires_cited_ask": False})
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}}]})

    transport(monkeypatch, respond)
    key = conversation(client)
    reply = message(client, key, "Hello from my private conversation")
    assert reply.status_code == 200, reply.text
    provenance = reply.json()["messages"][-1]["provenance"]
    assert provenance["local"] is False and provenance["provider"] == "swisscom"
    assert provenance["cloud_fallback"] is False
    remark = client.post("/api/assistant/remark", headers=_csrf(client),
        json={"route": "/sources", "trigger": "arrival", "locale": "en-CH", "tone": "dry"})
    assert remark.status_code == 200, remark.text
    assert remark.json()["provenance"]["local"] is False
    assert len(calls) == 2
    with app.state.service.db.session(include_all_organizations=True) as session:
        assert session.scalar(select(func.count()).select_from(IntegrationLog)) == 0


@pytest.mark.parametrize("failure", [401, 429, 502, "invalid"])
def test_remote_failures_never_fall_back_or_save_invalid_chat(remote, monkeypatch, failure):
    app, client, _ = remote
    calls = []

    def respond(request):
        calls.append(request)
        if failure == "invalid":
            return httpx.Response(200, json={"choices": [{"message": {"content": "not valid JSON"}}]})
        return httpx.Response(failure, json={"error": "synthetic-private-provider-error"})

    transport(monkeypatch, respond)
    key = conversation(client)
    response = message(client, key, "Private test message")
    assert response.status_code == (503 if failure == 429 else 502)
    assert len(calls) == (2 if failure == "invalid" else 1)
    assert "synthetic-private-provider-error" not in response.text
    assert "synthetic-shared-key" not in response.text
    assert client.get(f"/api/assistant/conversations/{key}").json()["messages"] == []
    with app.state.service.db.session(include_all_organizations=True) as session:
        assert session.scalar(select(func.count()).select_from(IntegrationLog)) == 0


def test_concurrent_users_keep_organization_credentials_context_and_history_separate(remote, monkeypatch):
    app, first, _ = remote
    with TestClient(app) as second:
        _register(second, email="second@example.ch", organization="Second organization")
        # A new organization inherits the remote default, then uses its own
        # credential override to prove that concurrent requests cannot mix it.
        assert second.get("/api/settings/apertus").json()["provider"] == "swisscom"
        saved = second.patch("/api/settings/apertus", headers=_csrf(second), json=configuration(
            provider="swisscom", base_url=SWISSCOM_WEEKS_BASE_URL, model=SWISSCOM_WEEKS_MODEL,
            key_action="replace", api_key="synthetic-second-key", request_retries=0, json_mode=False))
        assert saved.status_code == 200, saved.text
        keys = [conversation(first), conversation(second)]
        barrier = Barrier(2)

        def respond(request):
            payload = json.loads(request.content)
            turns = json.loads(payload["messages"][1]["content"])
            text = turns[-1]["content"]
            owner = "first" if text == "Hello from first" else "second"
            assert request.headers["authorization"] == (
                "Bearer synthetic-shared-key" if owner == "first" else "Bearer synthetic-second-key")
            assert all(("second" if owner == "first" else "first") not in t["content"] for t in turns)
            barrier.wait(timeout=10)
            content = json.dumps({"reply": f"Hello, {owner} user.", "requires_cited_ask": False})
            return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

        transport(monkeypatch, respond)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(message, client, key, f"Hello from {owner}")
                for client, key, owner in zip((first, second), keys, ("first", "second"), strict=True)]
            results = [future.result(timeout=20) for future in futures]
        for result, owner in zip(results, ("first", "second"), strict=True):
            assert result.status_code == 200, result.text
            assert result.json()["messages"][-1]["content"] == f"Hello, {owner} user."
        assert first.get(f"/api/assistant/conversations/{keys[1]}").status_code == 404
        assert second.get(f"/api/assistant/conversations/{keys[0]}").status_code == 404
