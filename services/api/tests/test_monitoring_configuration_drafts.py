"""Synthetic reviewed runtime; proposals never change native monitor records."""

import asyncio
import copy
import json
from uuid import uuid4

import httpx
import pytest
from runtime_fixtures import local_runtime
from sqlalchemy import delete, select, update
from test_ai_capabilities import artifacts as artifacts
from test_analysis_runtime_binding import transport
from test_auth import _csrf
from test_pollen_contracts import configuration as pollen
from test_prompt_token_measurements import measurement
from test_tender_api import api as api

from helvetic_lens import monitoring_configuration_drafts as drafts
from helvetic_lens.analysis import ModelClient
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.models import IntegrationLog, OrganizationMembership, User


def example(domain):
    from test_air_watch import configuration as air
    from test_commute_contracts import configuration as commute
    from test_river_watch import config as river
    from test_tender_matching import profile as tender
    values = {
        "pollen": pollen,
        "river": river,
        "air": air,
        "commute": lambda: commute().model_dump(mode="json"),
        "traffic": lambda: {"name": "Basel road", "corridor_reference_ids": [str(uuid4())]},
        "warnings": lambda: {"name": "Basel warnings", "location": {"kind": "municipality", "canton": "BS", "municipality_code": "2701"}, "hazards": ["storm"]},
        "tenders": lambda: tender().model_dump(mode="json"),
        "ip": lambda: {"name": "My brands", "brands": [{"key": "brand", "name": "Example", "language": "en"}]},
        "auctions": lambda: {"name": "Equipment", "categories": ["equipment"]},
    }
    return drafts.configuration(domain, values[domain]())


@pytest.mark.parametrize("domain", list(drafts.CONTRACTS))
def test_native_proposals_round_trip_without_hidden_authority(domain):
    current = example(domain)
    proposed = copy.deepcopy(current)
    key = "timezone" if domain == "pollen" else "name"
    proposed[key] = "Europe/Berlin" if domain == "pollen" else "Renamed by the user"
    assert drafts.parse_proposal(domain, current, json.dumps({"configuration": proposed})) == proposed
    assert drafts.parse_proposal(domain, current, '{"configuration":null}') is None
    for key in ("owner_user_id", "source_ready", "status", "email_consent", "command"):
        with pytest.raises(DomainError):
            drafts.parse_proposal(domain, current, json.dumps({"configuration": {**proposed, key: "unexpected"}}))


@pytest.mark.parametrize("domain", list(drafts.PROTECTED))
def test_model_cannot_invent_a_location_reference_or_deadline(domain):
    current = example(domain)
    proposed = copy.deepcopy(current)
    if domain in {"pollen", "river", "air"}:
        proposed["station_id"] = {"pollen": "PZH", "river": "2001", "air": "LUG"}[domain]
    elif domain in {"commute", "traffic"}:
        proposed[drafts.PROTECTED[domain][0]] = [str(uuid4())]
    elif domain == "warnings":
        proposed["location"]["municipality_code"] = "2702"
    else:
        proposed["deadline_context"] = {"invented": "legal deadline"}
    with pytest.raises(DomainError):
        drafts.parse_proposal(domain, current, json.dumps({"configuration": proposed}))


@pytest.mark.parametrize("raw", [
    '{"configuration":null,"configuration":{}}', '{"configuration":{"name":"a","name":"b"}}',
    '{"configuration":null,"send_email":true}', '[]', 'null', '```json\n{}\n```', 'x' * 32769,
    '{"configuration":{"maximum_price_chf_cents":NaN}}',
], ids=["duplicate_root", "duplicate_nested", "command", "array", "null", "fence", "oversized", "nonfinite"])
def test_untrusted_model_output_is_bounded_strict_json(raw):
    with pytest.raises(DomainError):
        drafts.parse_proposal("auctions", example("auctions"), raw)


@pytest.fixture
def runtime(artifacts, monkeypatch):
    root, identity, review, registry, write = artifacts
    observed = {**local_runtime(), "prompt_budget_schema": "local-prompt-budget-v1"}
    identity.clear()
    identity.update(observed["identity"])
    review["task"] = "monitoring_configuration"
    registry["profiles"][0]["grants"][0]["task"] = review["task"]
    settings = Settings(_env_file=None, apertus_provider="docker", apertus_base_url="http://synthetic-manager/openai/v1",
        apertus_model=observed["served_model_id"], apertus_explanation_profile="synthetic-explanations",
        ai_capability_registry=write(), ai_capability_evidence_root=root, apertus_max_tokens=700)
    state = {"requests": [], "tokens": 400, "status": 200, "mutate": None, "raw": None}

    async def handler(request):
        state["requests"].append(request)
        if request.method == "GET":
            return httpx.Response(200, json=observed)
        wire = json.loads(request.content)
        data = json.loads(wire["messages"][-1]["content"])
        count = request.url.path.endswith("/input_tokens")
        headers = {"x-helvetic-runtime-binding": observed["binding_fingerprint"],
            "x-helvetic-token-budget": json.dumps(measurement(wire, input_tokens=state["tokens"]))}
        if count:
            return httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": state["tokens"]}, headers=headers)
        if state["mutate"]:
            state["mutate"]()
        proposed = data["configuration"]
        if data["domain"] == "pollen":
            proposed["timezone"] = "Europe/Berlin"
        else:
            proposed["name"] = "Explicit private proposed name"
        raw = state["raw"] if state["raw"] is not None else json.dumps({"configuration": proposed})
        return httpx.Response(state["status"], json={"choices": [{"message": {"content": raw}}]}, headers=headers)

    transport(monkeypatch, handler)
    return settings, state, review, registry, write


@pytest.mark.parametrize("domain", list(drafts.CONTRACTS))
def test_actual_model_transport_review_budget_and_native_schema(runtime, domain):
    settings, state, _, _, _ = runtime
    result = asyncio.run(drafts.propose(ModelClient(settings), domain=domain, current=example(domain), request="Rename this monitor", locale="en-CH"))
    assert result["changed_fields"] == (["timezone"] if domain == "pollen" else ["name"])
    assert len(result["input_binding"]) == len(result["capability_binding"]) == 64
    assert len(state["requests"]) == 3  # bound runtime, measured prompt, one generation
    schema = json.loads(state["requests"][-1].content)["response_format"]["schema"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["configuration"]["anyOf"][0]["title"] == drafts.CONTRACTS[domain].__name__


@pytest.mark.parametrize("locale", ["en-CH", "de-CH", "fr-CH", "it-CH", "rm-CH"])
def test_locale_is_an_exact_reviewed_scope_and_input_binding(runtime, locale):
    settings, state, review, registry, write = runtime
    review["locale"] = registry["profiles"][0]["grants"][0]["locale"] = locale
    write()
    current = example("auctions")
    result = asyncio.run(drafts.propose(ModelClient(settings), domain="auctions", current=current,
        request="Explicit request", locale=locale))
    assert result["locale"] == locale
    assert result["input_binding"] == drafts.fingerprint({"domain": "auctions", "configuration": current,
        "request": "Explicit request", "locale": locale})
    assert json.loads(json.loads(state["requests"][-1].content)["messages"][-1]["content"])["locale"] == locale


def test_invalid_current_configuration_starts_no_runtime_or_model_request(runtime):
    settings, state, _, _, _ = runtime
    with pytest.raises(DomainError) as invalid:
        asyncio.run(drafts.propose(ModelClient(settings), domain="auctions", current={"name": ""}, request="Rename", locale="en-CH"))
    assert invalid.value.code == "configuration_draft_input_invalid"
    assert state["requests"] == []


def test_model_cannot_reset_omitted_settings_to_defaults():
    current = example("auctions")
    current["maximum_price_chf_cents"] = 20000
    proposed = {key: value for key, value in current.items() if key != "maximum_price_chf_cents"}
    with pytest.raises(DomainError):
        drafts.parse_proposal("auctions", current, json.dumps({"configuration": proposed}))


@pytest.mark.parametrize("denial", ["viewer", "inactive", "anonymous"])
def test_http_access_denied_before_any_model_request(api, runtime, denial):
    client, app, _, identity = api
    _, state, _, _, _ = runtime
    if denial == "anonymous":
        client.cookies.clear()
    else:
        with app.state.service.db.session(include_all_organizations=True) as session:
            if denial == "viewer":
                session.execute(update(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"]).values(role="viewer"))
            else:
                session.execute(update(User).where(User.id == identity["user"]["id"]).values(active=False))
            session.commit()
    response = client.post("/api/monitoring-centre/configuration/draft", headers={} if denial == "anonymous" else _csrf(client),
        json={"domain": "auctions", "configuration": example("auctions"), "request": "Rename", "locale": "en-CH", "request_key": str(uuid4())})
    assert response.status_code in {401, 403}
    assert state["requests"] == []


@pytest.mark.parametrize("failure", ["unreviewed_task", "locale", "revoked", "budget", "provider", "changed_approval"])
def test_unreviewed_or_failed_generation_preserves_manual_fallback(runtime, failure):
    settings, state, review, registry, write = runtime
    if failure == "unreviewed_task":
        review["task"] = registry["profiles"][0]["grants"][0]["task"] = "ask"
        write()
    if failure == "revoked":
        registry["profiles"][0]["status"] = "revoked"
        write()
    if failure == "budget":
        state["tokens"] = 3001
    if failure == "provider":
        state["status"] = 503
    if failure == "changed_approval":
        def revoke():
            registry["profiles"][0]["status"] = "revoked"
            write()
        state["mutate"] = revoke
    with pytest.raises(DomainError):
        asyncio.run(drafts.propose(ModelClient(settings), domain="auctions", current=example("auctions"),
            request="Rename", locale="de-CH" if failure == "locale" else "en-CH"))
    generations = [r for r in state["requests"] if r.url.path.endswith("/chat/completions")]
    assert len(generations) <= (1 if failure in {"provider", "changed_approval"} else 0)


def test_actual_http_explicit_draft_csrf_revocation_and_no_private_integration_logs(api, runtime):
    client, app, _, identity = api
    settings, state, _, _, _ = runtime
    # Keep request-scoped database/auth settings and change only the model inputs.
    for key in ("apertus_provider", "apertus_base_url", "apertus_model", "apertus_explanation_profile", "ai_capability_registry", "ai_capability_evidence_root", "apertus_max_tokens"):
        setattr(app.state.service.environment_settings, key, getattr(settings, key))
    body = {"domain": "auctions", "configuration": example("auctions"), "request": "My private request marker", "locale": "en-CH", "request_key": str(uuid4())}
    path = "/api/monitoring-centre/configuration/draft"
    assert client.post(path, json=body).status_code == 403
    response = client.post(path, json=body, headers=_csrf(client))
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["request_key"] == body["request_key"]
    assert "request" not in response.json()
    with app.state.service.db.session(include_all_organizations=True) as session:
        assert not session.scalars(select(IntegrationLog)).all()

    def revoke():
        with app.state.service.db.session(include_all_organizations=True) as session:
            session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"]))
            session.commit()
    state["mutate"] = revoke
    response = client.post(path, json=body, headers=_csrf(client))
    assert response.status_code == 403 and "Explicit private proposed name" not in response.text
