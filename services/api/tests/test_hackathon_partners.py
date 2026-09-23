"""Provider protocol, private workspace and failure tests. All credentials are synthetic."""

import base64
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_auth import _csrf, _register, _settings
from test_settings import configuration, transport

from helvetic_lens.analysis import Answer, InferenceBudget, ModelClient, parse_response
from helvetic_lens.config import (
    ANTHROPIC_BASE_URL,
    OPENAI_BASE_URL,
    SWISSCOM_WEEKS_BASE_URL,
    DomainError,
    Settings,
)
from helvetic_lens.main import create_app
from helvetic_lens.models import IntegrationLog, OrganizationMembership, PartnerConfiguration
from helvetic_lens.partner_tools import MAX_RESPONSE_BYTES, PartnerClient


def partner_settings(**changes):
    return {"revision": 0, "enabled": True, "key_action": "replace", "api_key": "test-only-partner-secret",
        "voice_id": "test-voice", "model_id": "eleven_multilingual_v2", **changes}


def briefing(**changes):
    return {"text": "Synthetic policy: retain records for 60 days.", "consent": True, "revision": 1, **changes}


def claude_settings(tmp_path, **changes):
    return Settings(_env_file=None, data_dir=tmp_path, apertus_provider="anthropic",
        apertus_model="test-claude", apertus_api_key="test-only-claude-key", apertus_request_retries=0, **changes)


@pytest.mark.asyncio
async def test_claude_uses_messages_and_preserves_call_budget(tmp_path, monkeypatch):
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"content": [{"type": "thinking", "thinking": "private reasoning"},
            {"type": "text", "text": '{"status":"ok"}'}], "stop_reason": "end_turn"})
    transport(monkeypatch, respond)
    budget = InferenceBudget(1)
    client = ModelClient(claude_settings(tmp_path))
    assert await client.complete("system", "evidence", response_schema={"type": "object"}, budget=budget) == '{"status":"ok"}'
    assert str(calls[0].url) == ANTHROPIC_BASE_URL + "/messages"
    assert calls[0].headers["authorization"] == "Bearer test-only-claude-key"
    assert calls[0].headers["anthropic-version"] == "2023-06-01"
    payload = json.loads(calls[0].content)
    assert payload["messages"] == [{"role": "user", "content": "evidence"}]
    assert payload["system"].startswith("system")
    assert not {"n", "response_format", "presence_penalty", "top_p", "temperature", "reasoning_effort"} & payload.keys()
    with pytest.raises(DomainError, match="budget"):
        await client.complete("system", "more evidence", budget=budget)
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("stop", ["max_tokens", "refusal", "tool_use", None])
async def test_claude_rejects_partial_or_refused_answers(tmp_path, monkeypatch, stop):
    transport(monkeypatch, lambda request: httpx.Response(200, json={"content": [{"type": "text", "text": "partial"}], "stop_reason": stop}))
    with pytest.raises(DomainError) as error:
        await ModelClient(claude_settings(tmp_path)).complete("system", "evidence")
    assert error.value.code == "model_incomplete"


@pytest.mark.asyncio
async def test_claude_malformed_envelope_is_an_actionable_failure(tmp_path, monkeypatch):
    transport(monkeypatch, lambda request: httpx.Response(200, json=[]))
    with pytest.raises(DomainError) as error:
        await ModelClient(claude_settings(tmp_path)).complete("system", "evidence")
    assert error.value.code == "model_error"


@pytest.mark.asyncio
@pytest.mark.parametrize("quote", ["60 days", "invented deadline"])
async def test_claude_answers_retain_saved_evidence_validation(tmp_path, monkeypatch, quote):
    answer = {"supported": True, "answer": "The period changed.", "citations": [
        {"version_id": "saved-new", "passage_id": "p1", "quote": quote}]}
    transport(monkeypatch, lambda request: httpx.Response(200, json={
        "stop_reason": "end_turn", "content": [{"type": "text", "text": json.dumps(answer)}]}))
    evidence = [{"version_id": "saved-new", "passage_id": "p1", "text": "Retention is 60 days.", "page": 3}]
    raw = await ModelClient(claude_settings(tmp_path)).complete("Use the supplied evidence.", json.dumps(evidence))
    if quote == "invented deadline":
        with pytest.raises(DomainError) as error:
            parse_response(raw, Answer, evidence)
        assert error.value.code == "invalid_citation"
    else:
        result = parse_response(raw, Answer, evidence)
        assert result["citations"][0]["url"] == "/evidence/saved-new?passage=p1"
        assert result["citations"][0]["page"] == 3


@pytest.mark.parametrize("provider,base", [
    ("anthropic", ANTHROPIC_BASE_URL),
    ("swisscom", "https://api.swisscom.com/layer/swiss-ai-platform/test-model/v1"),
])
def test_partner_model_discovery_precedes_model_selection(harness, monkeypatch, provider, base):
    client, _, _, _ = harness
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"data": [{"id": "granted-model"}]})
    transport(monkeypatch, respond)
    draft = configuration(provider=provider, base_url=base, model="", key_action="replace", api_key="test-key")
    result = client.post("/api/settings/apertus/models", json=draft)
    assert result.status_code == 200, result.text
    assert result.json()["models"][0]["id"] == "granted-model"
    assert len(calls) == 1 and calls[0].method == "GET" and str(calls[0].url) == base + "/models"
    assert "test-key" not in result.text
    assert client.patch("/api/settings/apertus", json=draft).status_code == 422


@pytest.mark.asyncio
async def test_swisscom_uses_issued_route_and_bearer_token(tmp_path, monkeypatch):
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "valid"}}]})
    transport(monkeypatch, respond)
    settings = Settings(_env_file=None, data_dir=tmp_path, apertus_provider="swisscom",
        apertus_base_url="https://api.swisscom.com/layer/swiss-ai-platform/test-model/v1",
        apertus_model="issued-model-id", apertus_api_key="test-only-swisscom")
    assert await ModelClient(settings).complete("system", "evidence") == "valid"
    assert str(calls[0].url) == settings.apertus_base_url + "/chat/completions"
    assert json.loads(calls[0].content)["model"] == "issued-model-id"
    assert calls[0].headers["authorization"] == "Bearer test-only-swisscom"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["swisscom", "custom", "infomaniak", "openai", "anthropic"])
@pytest.mark.parametrize("json_mode", [False, True])
async def test_remote_generation_receives_the_output_contract(tmp_path, monkeypatch, provider, json_mode):
    """JSON mode alone cannot tell a remote model which fields to generate."""
    schema = {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]}
    calls = []

    def respond(request):
        payload = json.loads(request.content)
        calls.append(payload)
        system = payload["system"] if provider == "anthropic" else payload["messages"][0]["content"]
        assert json.loads(system.split("Return only JSON conforming to this schema:\n", 1)[1]) == schema
        assert system.startswith("Use the supplied context.")
        if provider == "anthropic":
            return httpx.Response(200, json={"stop_reason": "end_turn", "content": [
                {"type": "text", "text": '{"topic":"citizenship"}'}]})
        assert payload.get("response_format") == ({"type": "json_object"} if json_mode else None)
        assert payload["messages"][1] == {"role": "user", "content": "Private context"}
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"topic":"citizenship"}'}}]})

    transport(monkeypatch, respond)
    base = {"swisscom": SWISSCOM_WEEKS_BASE_URL, "openai": OPENAI_BASE_URL,
            "anthropic": ANTHROPIC_BASE_URL}.get(provider, "https://inference.example/v1")
    settings = Settings(_env_file=None, data_dir=tmp_path, apertus_provider=provider,
        apertus_base_url=base, apertus_product_id="12345", apertus_model="test-model",
        apertus_api_key="test-only-key", apertus_json_mode=json_mode, apertus_request_retries=0)
    result = await ModelClient(settings).complete("Use the supplied context.", "Private context", response_schema=schema)
    assert json.loads(result) == {"topic": "citizenship"} and len(calls) == 1


def test_provider_switch_does_not_reuse_a_different_providers_key(harness):
    client, _, _, _ = harness
    assert client.patch("/api/settings/apertus", json=configuration(key_action="replace", api_key="old-secret")).status_code == 200
    draft = configuration(provider="anthropic", base_url=ANTHROPIC_BASE_URL, model="test-claude")
    blocked = client.post("/api/settings/apertus/test", json=draft)
    assert blocked.status_code == 422 and blocked.json()["code"] == "provider_key_required"
    assert client.patch("/api/settings/apertus", json={**draft, "key_action": "replace", "api_key": "new-secret"}).status_code == 200
    blocked = client.patch("/api/settings/apertus", json=configuration())
    assert blocked.status_code == 422 and "new-secret" not in blocked.text


@pytest.mark.parametrize("url", ["https://evil.example/v1", "http://api.swisscom.com/layer/swiss-ai-platform/a/v1", "https://api.swisscom.com/layer/swiss-ai-platform/a/v1?key=secret"])
def test_swisscom_invalid_routes_are_rejected_without_echoing_secrets(harness, url):
    client, _, _, _ = harness
    response = client.patch("/api/settings/apertus", json=configuration(provider="swisscom", base_url=url,
        key_action="replace", api_key="test-only-private-key"))
    assert response.status_code == 422 and "test-only-private-key" not in response.text


def test_connection_probe_does_not_accept_arbitrary_text(harness, monkeypatch):
    client, _, _, _ = harness
    transport(monkeypatch, lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "not the requested JSON"}}]}))
    result = client.post("/api/settings/apertus/test", json=configuration())
    assert result.status_code == 502 and result.json()["code"] == "model_test_failed"


def test_partner_settings_are_optional_encrypted_revisioned_and_survive_restart(harness):
    client, fetcher, service, _ = harness
    assert all(not item["enabled"] for item in client.get("/api/settings/partners").json()["items"])
    saved = client.patch("/api/settings/partners/supertext", json=partner_settings())
    assert saved.status_code == 200 and saved.json()["revision"] == 1
    assert "test-only-partner-secret" not in saved.text and "api_key" not in saved.json()
    with service.db.session() as session:
        row = session.get(PartnerConfiguration, (service.organization_id, "supertext"))
        assert row.api_key.startswith("enc:v1:") and "test-only-partner-secret" not in row.api_key
    with TestClient(create_app(service.environment_settings, fetcher=fetcher)) as restarted:
        assert restarted.get("/api/settings/partners").json()["items"][0]["api_key_configured"]
    assert client.patch("/api/settings/partners/supertext", json=partner_settings()).status_code == 409
    removed = client.patch("/api/settings/partners/supertext", json=partner_settings(revision=1, key_action="remove", api_key="", enabled=False))
    assert removed.status_code == 200 and not removed.json()["api_key_configured"]
    assert client.post("/api/partner-tools/supertext/translate", json=briefing(target_lang="de-CH", revision=2)).status_code == 422


def test_translation_and_speech_submit_only_reviewed_text_and_do_not_log_it(harness, monkeypatch):
    client, _, service, _ = harness
    calls = []
    def respond(request):
        calls.append(request)
        if request.url.host == "api.supertext.com":
            assert request.headers["authorization"] == "Supertext-Auth-Key test-only-partner-secret"
            assert json.loads(request.content) == {"text": [briefing()["text"]], "target_lang": "de-CH"}
            return httpx.Response(200, json={"translated_text": ["Synthetische Regel: 60 Tage."]})
        assert request.headers["xi-api-key"] == "test-only-partner-secret"
        return httpx.Response(200, content=b"ID3-test-audio", headers={"content-type": "audio/mpeg"})
    transport(monkeypatch, respond)
    for provider in ("supertext", "elevenlabs"):
        assert client.patch(f"/api/settings/partners/{provider}", json=partner_settings()).status_code == 200
    assert client.post("/api/partner-tools/supertext/translate", json=briefing(consent=False, target_lang="de-CH")).status_code == 422
    assert client.post("/api/partner-tools/supertext/translate", json=briefing(revision=3, target_lang="de-CH")).status_code == 409
    assert len(calls) == 0
    result = client.post("/api/partner-tools/supertext/translate", json=briefing(target_lang="de-CH"))
    assert result.status_code == 200 and result.json()["human_verified"] is False
    assert result.headers["cache-control"] == "no-store"
    result = client.post("/api/partner-tools/elevenlabs/speech", json=briefing())
    assert result.status_code == 200
    assert base64.b64decode(result.json()["audio_base64"]) == b"ID3-test-audio"
    assert len(calls) == 2
    with service.db.session() as session:
        logs = session.scalars(select(IntegrationLog).where(IntegrationLog.provider.in_(["supertext", "elevenlabs"]))).all()
        assert len(logs) == 2
        for log in logs:
            serialized = json.dumps({"request": log.request_body, "response": log.response_body, "headers": log.request_headers})
            assert "test-only-partner-secret" not in serialized and briefing()["text"] not in serialized


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [301, 401, 403, 429, 500])
async def test_partner_failures_are_redacted_and_never_retried(monkeypatch, status):
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(status, headers={"location": "https://evil.example/"}, json={"error": "test-only-secret private text"})
    transport(monkeypatch, respond)
    with pytest.raises(DomainError) as error:
        await PartnerClient("supertext", "test-only-secret").json("POST", "/translate/ai/text", {"text": ["private text"]})
    assert "private text" not in str(error.value) and "test-only-secret" not in str(error.value)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_partner_timeout_and_response_size_are_bounded(monkeypatch):
    mode = "large"
    def respond(request):
        if mode == "large":
            return httpx.Response(200, content=b"x" * (MAX_RESPONSE_BYTES+1))
        raise httpx.ReadTimeout("secret internal request", request=request)
    transport(monkeypatch, respond)
    with pytest.raises(DomainError) as error:
        await PartnerClient("supertext", "secret").request("GET", "/features")
    assert error.value.code == "partner_response_invalid"
    mode = "timeout"
    with pytest.raises(DomainError) as error:
        await PartnerClient("supertext", "secret").request("GET", "/features")
    assert error.value.code == "partner_unavailable"


@pytest.mark.parametrize("result", [{"translated_text": []}, {"translated_text": [""]}, {"translated_text": ["a", "b"]}, {"other": "text"}])
def test_malformed_translation_never_becomes_a_briefing(harness, monkeypatch, result):
    client, _, _, _ = harness
    client.patch("/api/settings/partners/supertext", json=partner_settings())
    transport(monkeypatch, lambda request: httpx.Response(200, json=result))
    response = client.post("/api/partner-tools/supertext/translate", json=briefing(target_lang="de-CH"))
    assert response.status_code == 502 and response.json()["code"] == "partner_response_invalid"


def test_partner_credentials_and_tools_obey_tenant_roles_and_csrf(tmp_path):
    app = create_app(_settings(tmp_path))
    with TestClient(app) as alice, TestClient(app) as bob, TestClient(app) as anonymous:
        assert anonymous.get("/api/settings/partners").status_code == 401
        alice_org = _register(alice, "alice@example.ch").json()["organization"]["id"]
        bob_session = _register(bob, "bob@example.ch").json()
        assert alice.patch("/api/settings/partners/supertext", json=partner_settings()).status_code == 403
        assert alice.patch("/api/settings/partners/supertext", json=partner_settings(), headers=_csrf(alice)).status_code == 200
        assert not bob.get("/api/settings/partners").json()["items"][0]["enabled"]
        assert bob.post("/api/partner-tools/supertext/translate", json=briefing(target_lang="de"), headers=_csrf(bob)).status_code == 422
        with app.state.service.db.session(include_all_organizations=True) as session:
            session.add(OrganizationMembership(organization_id=alice_org, user_id=bob_session["user"]["id"], role="viewer"))
            session.commit()
        assert bob.post("/api/auth/session/organization", json={"organization_id": alice_org}, headers=_csrf(bob)).status_code == 200
        assert bob.get("/api/settings/partners").json()["items"][0]["enabled"]
        assert bob.patch("/api/settings/partners/supertext", json=partner_settings(revision=1), headers=_csrf(bob)).status_code == 403
        assert bob.post("/api/partner-tools/supertext/translate", json=briefing(target_lang="de"), headers=_csrf(bob)).status_code == 403
