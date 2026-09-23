"""Cloud profiles retain separate encrypted credentials and explicit tenant activation."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_auth import _csrf, _register, _settings
from test_settings import configuration, transport

from helvetic_lens.config import OPENAI_BASE_URL, SWISSCOM_WEEKS_BASE_URL, SWISSCOM_WEEKS_MODEL
from helvetic_lens.main import create_app
from helvetic_lens.models import OrganizationMembership, PartnerConfiguration

ROOT = "/api/settings/inference-connections"


def profile(provider="swisscom", **changes):
    return configuration(provider=provider,
        base_url=OPENAI_BASE_URL if provider == "openai" else SWISSCOM_WEEKS_BASE_URL,
        model="test-openai-model" if provider == "openai" else SWISSCOM_WEEKS_MODEL,
        revision=0, key_action="replace", api_key=f"synthetic-{provider}-secret", **changes)


def test_connections_persist_separately_without_activation_or_secret_disclosure(harness):
    client, fetcher, service, _ = harness
    active = client.get("/api/settings/apertus").json()
    for provider in ("openai", "swisscom"):
        response = client.patch(f"{ROOT}/{provider}", json=profile(provider))
        assert response.status_code == 200, response.text
        assert response.json()["revision"] == 1 and response.json()["api_key_configured"]
        assert "api_key" not in response.json() and "synthetic-" not in response.text
        assert response.headers["cache-control"] == "no-store"
        with service.db.session() as session:
            row = session.get(PartnerConfiguration, (service.organization_id, "inference_" + provider))
            assert row.api_key.startswith("enc:v1:") and "synthetic-" not in row.api_key
    assert client.get("/api/settings/apertus").json() == active
    with TestClient(create_app(service.environment_settings, fetcher=fetcher)) as restarted:
        result = restarted.get(ROOT)
        assert result.headers["cache-control"] == "no-store" and "synthetic-" not in result.text
        assert all(item["api_key_configured"] for item in result.json()["items"])
        assert restarted.get("/api/settings/apertus").json() == active
        activated = restarted.post(f"{ROOT}/swisscom/activate", json={"revision": 1})
        assert activated.status_code == 200, activated.text
        assert activated.json()["model"] == SWISSCOM_WEEKS_MODEL
        assert "synthetic-" not in activated.text
        removed = restarted.patch(f"{ROOT}/swisscom", json={**profile(), "revision": 1, "key_action": "remove", "api_key": ""})
        assert removed.status_code == 200 and not removed.json()["api_key_configured"]
        # The active configuration is a copy: editing a profile does not replace it.
        assert restarted.get("/api/settings/apertus").json() == activated.json()
        assert restarted.post(f"{ROOT}/swisscom/activate", json={"revision": 2}).status_code == 422
        assert restarted.post(f"{ROOT}/openai/activate", json={"revision": 1}).status_code == 200
        assert restarted.get("/api/settings/apertus").json()["provider"] == "openai"
    with TestClient(create_app(service.environment_settings, fetcher=fetcher)) as restarted:
        assert restarted.get("/api/settings/apertus").json()["provider"] == "openai"
        assert restarted.app.state.service.settings.apertus_api_key.get_secret_value() == "synthetic-openai-secret"


@pytest.mark.parametrize("provider", ["openai", "swisscom"])
def test_saved_probe_uses_its_own_key_and_protocol_without_changing_active_settings(harness, monkeypatch, provider):
    client, _, _, _ = harness
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": '{"status":"ok"}'}}]})
    transport(monkeypatch, respond)
    assert client.patch(f"{ROOT}/{provider}", json=profile(provider)).status_code == 200
    active = client.get("/api/settings/apertus").json()
    result = client.post(f"{ROOT}/{provider}/test", json={"revision": 1})
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "connected" and not result.json()["activated"]
    assert client.get("/api/settings/apertus").json() == active
    assert len(calls) == 1
    assert str(calls[0].url) == profile(provider)["base_url"] + "/chat/completions"
    assert calls[0].headers["authorization"] == f"Bearer synthetic-{provider}-secret"
    payload = json.loads(calls[0].content)
    assert payload["model"] == profile(provider)["model"]
    assert payload.get("max_completion_tokens", payload.get("max_tokens")) == 512
    if provider == "openai":
        assert payload["store"] is False
        assert not {"temperature", "top_p", "presence_penalty", "max_tokens"} & payload.keys()
    else:
        assert payload["max_tokens"] == 512


def test_stale_edits_and_activations_and_wrong_provider_are_rejected(harness):
    client, _, _, _ = harness
    assert client.patch(f"{ROOT}/swisscom", json=profile()).status_code == 200
    assert client.patch(f"{ROOT}/swisscom", json=profile()).status_code == 409
    for operation in ("test", "activate"):
        assert client.post(f"{ROOT}/swisscom/{operation}", json={"revision": 2}).status_code == 409
    assert client.patch(f"{ROOT}/openai", json=profile()).status_code == 422
    changed_origin = {**profile(), "revision": 1, "key_action": "keep", "api_key": "",
        "base_url": "https://api.swisscom.com/layer/swiss-ai-platform/other/v1"}
    assert client.patch(f"{ROOT}/swisscom", json=changed_origin).json()["code"] == "provider_key_required"


@pytest.mark.parametrize("provider,base", [
    ("openai", "https://evil.example/v1"),
    ("openai", "https://api.openai.com/v1/other"),
    ("openai", "https://api.openai.com.evil.example/v1"),
    ("swisscom", "https://api.swisscom.com/products/other/v1"),
    ("swisscom", SWISSCOM_WEEKS_BASE_URL + "/../../other/v1"),
    ("swisscom", SWISSCOM_WEEKS_BASE_URL + "?key=secret"),
])
def test_cloud_destinations_are_pinned_without_disclosing_invalid_secrets(harness, provider, base):
    client, _, _, _ = harness
    result = client.patch(f"{ROOT}/{provider}", json={**profile(provider), "base_url": base})
    assert result.status_code == 422 and "synthetic-" not in result.text
    assert not any(item["api_key_configured"] for item in client.get(ROOT).json()["items"])


def test_switching_to_or_from_openai_requires_the_matching_credential(harness):
    client, _, _, _ = harness
    assert client.patch("/api/settings/apertus", json=configuration(key_action="replace", api_key="custom-secret")).status_code == 200
    draft = configuration(provider="openai", base_url=OPENAI_BASE_URL)
    assert client.patch("/api/settings/apertus", json=draft).json()["code"] == "provider_key_required"
    assert client.patch("/api/settings/apertus", json={**draft, "key_action": "replace", "api_key": "openai-secret"}).status_code == 200
    assert client.post("/api/settings/apertus/test", json=configuration()).json()["code"] == "provider_key_required"


def test_failed_probe_has_no_retry_fallback_activation_or_secret_echo(harness, monkeypatch):
    client, _, _, _ = harness
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(401, json={"error": "synthetic-swisscom-secret private provider error"})
    transport(monkeypatch, respond)
    client.patch(f"{ROOT}/swisscom", json=profile())
    active = client.get("/api/settings/apertus").json()
    result = client.post(f"{ROOT}/swisscom/test", json={"revision": 1})
    assert result.status_code == 502 and len(calls) == 1
    assert "synthetic-" not in result.text and "private provider error" not in result.text
    assert client.get("/api/settings/apertus").json() == active


def test_connections_enforce_tenant_isolation_csrf_roles_and_current_membership(tmp_path):
    app = create_app(_settings(tmp_path))
    with TestClient(app) as alice, TestClient(app) as bob, TestClient(app) as anonymous:
        assert anonymous.get(ROOT).status_code == 401
        alice_org = _register(alice, "alice@example.ch").json()["organization"]["id"]
        bob_session = _register(bob, "bob@example.ch").json()
        assert alice.patch(f"{ROOT}/swisscom", json=profile()).status_code == 403
        assert alice.patch(f"{ROOT}/swisscom", json=profile(), headers=_csrf(alice)).status_code == 200
        assert alice.post(f"{ROOT}/swisscom/activate", json={"revision": 1}).status_code == 403
        assert alice.post(f"{ROOT}/swisscom/activate", json={"revision": 1}, headers=_csrf(alice)).status_code == 200
        assert not any(item["api_key_configured"] for item in bob.get(ROOT).json()["items"])
        assert bob.get("/api/settings/apertus").json()["provider"] == "custom"
        assert bob.post(f"{ROOT}/swisscom/activate", json={"revision": 1}, headers=_csrf(bob)).status_code == 409
        with app.state.service.db.session(include_all_organizations=True) as session:
            session.add(OrganizationMembership(organization_id=alice_org, user_id=bob_session["user"]["id"], role="viewer"))
            session.commit()
        assert bob.post("/api/auth/session/organization", json={"organization_id": alice_org}, headers=_csrf(bob)).status_code == 200
        assert any(item["api_key_configured"] for item in bob.get(ROOT).json()["items"])
        assert bob.patch(f"{ROOT}/swisscom", json={**profile(), "revision": 1}, headers=_csrf(bob)).status_code == 403
        for operation in ("test", "activate"):
            assert bob.post(f"{ROOT}/swisscom/{operation}", json={"revision": 1}, headers=_csrf(bob)).status_code == 403
        with app.state.service.db.session(include_all_organizations=True) as session:
            membership = session.scalar(select(OrganizationMembership).where(
                OrganizationMembership.organization_id == alice_org,
                OrganizationMembership.user_id == bob_session["user"]["id"],
            ))
            session.delete(membership)
            session.commit()
        assert bob.get(ROOT).status_code in (401, 403)
