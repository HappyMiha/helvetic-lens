import json
from uuid import uuid4

import httpx
import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_auth import _csrf, _register, _settings
from test_monitoring_topics import add_candidate
from test_settings import configuration, transport

from helvetic_lens import monitoring_topics
from helvetic_lens.config import SWISSCOM_WEEKS_BASE_URL, SWISSCOM_WEEKS_MODEL, DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.legal_profile_models import LegalMonitoringProfile
from helvetic_lens.main import create_app
from helvetic_lens.models import (
    DigestPreference,
    Job,
    MonitoringTopic,
    MonitoringTopicRevision,
    OrganizationMembership,
    SourcePackSubscription,
    User,
)

ROOT = "/api/monitoring-profiles"


def config(**values):
    return {"name": "Citizenship advice", "sector": "Legal services", "goal": "Follow simplified naturalisation",
            "topics": [{"id": str(uuid4()), "name": "Naturalisation", "description": "Follow citizenship reform",
                        "keywords": ["naturalisation"]}], "source_pack_ids": ["fedlex-legislation"], **values}


@pytest.fixture
def signed(tmp_path):
    app = create_app(_settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        identity = _register(client).json()
        with app.state.service.db.organization_context(identity["organization"]["id"]):
            yield client, app.state.service, identity


def post(client, path, data):
    return client.post(path, headers=_csrf(client), json=data)


def create(client, **values):
    body = {"creation_key": str(uuid4()), "config": config(**values)}
    response = post(client, ROOT, body)
    assert response.status_code == 201, response.text
    return response.json(), body


def activate(client, profile):
    return post(client, ROOT + f"/{profile['id']}/activate", {"expected_revision": profile["revision"]})


def test_durable_five_steps_atomic_activation_retry_and_native_status(signed):
    client, service, _ = signed
    profile, body = create(client)
    assert post(client, ROOT, body).json()["id"] == profile["id"]
    route = ROOT + "/" + profile["id"]
    assert client.get(route).json()["config"]["name"] == "Citizenship advice"
    assert client.get(route).json()["updated_at"] == profile["updated_at"]
    assert profile["updated_at"].endswith("+00:00")
    saved = client.put(route, headers=_csrf(client), json={"expected_revision": 1, "step": 4,
        "config": {**body["config"], "source_requests": [{"id": str(uuid4()), "label": "Requested EU source",
        "url": "https://eur-lex.europa.eu/", "kind": "binding"}], "requested_jurisdictions": "EU"}})
    assert saved.status_code == 200, saved.text
    assert client.put(route, headers=_csrf(client), json={"expected_revision": 1, "step": 1,
        "config": body["config"]}).status_code == 409
    preview = post(client, route + "/preview", {"expected_revision": 2}).json()
    assert preview["topics"][0]["items"] == []
    result = activate(client, saved.json())
    assert result.status_code == 200, result.text
    active = result.json()
    assert active["status"] == "active" and len(active["topics"]) == 1
    assert active["config"]["source_requests"][0]["status"] == "requested"
    assert activate(client, saved.json()).json()["reused"] is True
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(MonitoringTopic)) == 1
        assert session.scalar(select(SourcePackSubscription)).enabled
        assert {j.type for j in session.scalars(select(Job))} >= {"source_pack_backfill", "topic_match_backfill"}
    paused = post(client, route + "/status", {"expected_revision": active["revision"], "status": "paused"})
    assert paused.status_code == 200, paused.text
    assert paused.json()["topics"][0]["status"] == "paused"
    resumed = post(client, route + "/status", {"expected_revision": paused.json()["revision"], "status": "active"})
    assert resumed.json()["topics"][0]["current_revision"] == 3
    assert client.get(ROOT).json()["total"] == 1


def test_second_topic_failure_rolls_back_topics_sources_jobs_and_delivery(signed, monkeypatch):
    client, service, identity = signed
    cards = config()["topics"] + config()["topics"]
    profile, _ = create(client, topics=cards, delivery="off", delivery_consent=True)
    original = monitoring_topics.create_topic
    calls = []

    def fail_second(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            raise DomainError("Test failure", 503, "test_failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(monitoring_topics, "create_topic", fail_second)
    response = activate(client, profile)
    assert response.status_code == 503
    with service.db.session() as session:
        for model in (MonitoringTopic, MonitoringTopicRevision, SourcePackSubscription, DigestPreference, Job):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        assert session.get(LegalMonitoringProfile, profile["id"]).status == "draft"


def test_real_preview_and_incomplete_or_unknown_sources_never_activate(signed):
    client, service, _ = signed
    profile, _ = create(client)
    event_id = add_candidate(service)
    result = post(client, ROOT + f"/{profile['id']}/preview", {"expected_revision": 1})
    assert result.status_code == 200, result.text
    candidate = result.json()["topics"][0]["items"][0]
    assert candidate["event_id"] == event_id and candidate["legal_relation_confirmed"] is False
    for values in ({"topics": []}, {"source_pack_ids": []}, {"source_pack_ids": ["invented-eu-pack"]}, {"name": ""}):
        other, _ = create(client, **values)
        assert activate(client, other).status_code == 422


class ProposalModel:
    def __init__(self):
        self.inputs = []

    async def complete(self, system, user, **kwargs):
        self.inputs.append(json.loads(user))
        return json.dumps({"topics": [{"name": "Citizenship procedure", "description": "Review naturalisation changes",
                                       "keywords": ["naturalisation", "Einbürgerung"]}]})


def test_suggestions_use_context_feedback_require_review_and_keep_provenance(signed):
    client, service, _ = signed
    service.model_client = model = ProposalModel()
    profile, _ = create(client)
    route = ROOT + "/" + profile["id"]
    suggestion = post(client, route + "/suggest", {"expected_revision": 1, "feedback": "Focus on procedure", "locale": "en-CH"})
    assert suggestion.status_code == 200, suggestion.text
    assert model.inputs[0]["context"]["goal"] == "Follow simplified naturalisation"
    assert model.inputs[0]["feedback"] == "Focus on procedure"
    data = suggestion.json()
    assert data["profile"]["config"]["topics"][0]["name"] == "Naturalisation"
    assert client.get(route).json()["config"]["feedback"] == "Focus on procedure"
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(MonitoringTopic)) == 0
    saved = client.put(route, headers=_csrf(client), json={"expected_revision": 2, "step": 2,
        "config": {**data["profile"]["config"], "topics": data["suggestions"]}}).json()
    result = activate(client, saved)
    assert result.status_code == 200, result.text
    assert result.json()["topics"][0]["plan"]["ai_assisted"] is True


def test_model_failure_leaves_manual_draft_usable(signed):
    client, service, _ = signed
    service.model_client = ScriptedModel(fail=True)
    profile, _ = create(client)
    result = post(client, ROOT + f"/{profile['id']}/suggest", {"expected_revision": 1})
    assert result.status_code == 504
    assert client.get(ROOT + "/" + profile["id"]).json()["revision"] == 1
    assert activate(client, profile).status_code == 200


@pytest.mark.parametrize("outcome", ["valid", "repaired", "invalid", "unavailable"])
def test_suggestions_through_saved_swisscom_adapter(signed, monkeypatch, outcome):
    client, service, _ = signed
    saved = client.patch("/api/settings/apertus", headers=_csrf(client), json=configuration(
        provider="swisscom", base_url=SWISSCOM_WEEKS_BASE_URL, model=SWISSCOM_WEEKS_MODEL,
        key_action="replace", api_key="test-only-swisscom-key", json_mode=False, request_retries=0))
    assert saved.status_code == 200, saved.text
    # Exercise persisted organization settings and the real production adapter;
    # only the external HTTP transport is controlled.
    service._provided_model_client = False
    calls = []

    def respond(request):
        payload = json.loads(request.content)
        calls.append(payload)
        assert str(request.url) == SWISSCOM_WEEKS_BASE_URL + "/chat/completions"
        assert request.headers["authorization"] == "Bearer test-only-swisscom-key"
        assert "response_format" not in payload
        schema = json.loads(payload["messages"][0]["content"].split("Return only JSON conforming to this schema:\n", 1)[1])
        assert schema["required"] == ["topics"]
        assert schema["$defs"]["TopicSuggestion"]["required"] == ["name", "description", "keywords"]
        context = json.loads(payload["messages"][1]["content"])
        assert context["context"]["goal"] == "Follow simplified naturalisation"
        assert context["feedback"] == "Focus on procedure" and context["output_locale"] == "en-CH"
        if outcome == "unavailable":
            return httpx.Response(429, json={"error": "test-only-provider-private-detail"})
        if outcome == "invalid" or (outcome == "repaired" and len(calls) == 1):
            # The actual failing production response used this incompatible shape.
            content = {"topics": [{"title": "Naturalisation", "keywords": ["Einbürgerung"],
                                   "jurisdiction": "CH", "source_suggestions": []}]}
        else:
            if outcome == "repaired":
                assert context["task"] == "repair_legal_profile_topics" and "previous_response" in context
            content = {"topics": [{"name": "Citizenship procedure", "description": "Follow procedure changes.",
                                   "keywords": ["Einbürgerung", "naturalisation"]}]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}}]})

    transport(monkeypatch, respond)
    profile, _ = create(client)
    route = ROOT + "/" + profile["id"]
    before = client.get(route).json()
    result = post(client, route + "/suggest", {"expected_revision": 1, "feedback": "Focus on procedure"})
    assert "test-only-swisscom-key" not in result.text and "test-only-provider-private-detail" not in result.text
    assert len(calls) == (2 if outcome in {"repaired", "invalid"} else 1)
    if outcome in {"valid", "repaired"}:
        assert result.status_code == 200, result.text
        assert result.json()["provider"] == "swisscom" and result.json()["model"] == SWISSCOM_WEEKS_MODEL
        assert result.json()["suggestions"][0]["name"] == "Citizenship procedure"
        assert result.json()["profile"]["revision"] == 2
    else:
        assert result.status_code == (502 if outcome == "invalid" else 503)
        assert result.json()["code"] == ("legal_profile_suggestions_invalid" if outcome == "invalid" else "model_rate_limited")
        assert client.get(route).json() == before
        # A provider failure cannot prevent manual editing and saving.
        changed = {**before["config"], "goal": "Manually refined monitoring goal"}
        assert client.put(route, headers=_csrf(client), json={"expected_revision": 1, "config": changed, "step": 1}).status_code == 200
    after = client.get(route).json()
    assert after["config"]["topics"] == before["config"]["topics"] and after["status"] == "draft"
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(MonitoringTopic)) == 0
        assert session.scalar(select(func.count()).select_from(SourcePackSubscription)) == 0


def test_delivery_requires_explicit_consent_and_preserves_existing_filters(signed):
    client, service, identity = signed
    profile, _ = create(client, delivery="weekly")
    assert activate(client, profile).json()["code"] == "legal_profile_delivery_consent"
    profile, _ = create(client, delivery="weekly", delivery_consent=True)
    assert activate(client, profile).json()["code"] == "legal_profile_email_unavailable"
    with service.db.session() as session:
        preference = DigestPreference(user_id=identity["user"]["id"], enabled=True, frequency="daily",
            sources=["fedlex"], severities=["high"], schedule_json={"timezone": "Europe/Zurich", "time": "09:00"})
        session.add(preference)
        session.commit()
    keep, _ = create(client)
    assert activate(client, keep).status_code == 200
    with service.db.session() as session:
        preference = session.scalar(select(DigestPreference))
        assert preference.enabled and preference.frequency == "daily"
        session.get(User, identity["user"]["id"]).email_verified_at = utcnow()
        session.commit()
    service.environment_settings.auth_email_mode = "smtp"
    assert activate(client, profile).status_code == 200
    with service.db.session() as session:
        preference = session.scalar(select(DigestPreference))
        assert preference.frequency == "weekly" and preference.next_delivery_at
        assert preference.sources == ["fedlex"] and preference.severities == ["high"]
        assert preference.schedule_json["time"] == "09:00"


def test_drafts_private_shared_active_tenant_isolation_csrf_and_fresh_viewer_denial(signed):
    client, service, owner = signed
    profile, _ = create(client)
    route = ROOT + "/" + profile["id"]
    assert client.post(route + "/activate", json={"expected_revision": 1}).json()["code"] == "csrf_failed"
    client.post("/api/auth/logout", headers=_csrf(client))
    other = _register(client, email="other@example.ch", organization="Other workspace").json()
    assert client.get(route).status_code == 404 and client.get(ROOT).json()["total"] == 0
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=other["user"]["id"], organization_id=owner["organization"]["id"], role="organization_admin"))
        session.commit()
    assert post(client, "/api/auth/session/organization", {"organization_id": owner["organization"]["id"]}).status_code == 200
    assert client.get(route).status_code == 404 and client.get(ROOT).json()["total"] == 0
    with service.db.session() as session:
        row = session.get(LegalMonitoringProfile, profile["id"])
        row.status = "active"
        member = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == other["user"]["id"]))
        member.role = "viewer"
        session.commit()
    assert client.get(route).status_code == 200
    assert post(client, route + "/status", {"expected_revision": 1, "status": "paused"}).status_code == 403


def test_untrusted_source_url_and_duplicate_card_ids_rejected(signed):
    client, _, _ = signed
    card = config()["topics"][0]
    for values in ({"topics": [card, card]}, {"source_requests": [{"id": str(uuid4()), "label": "Bad", "url": "javascript:alert(1)"}]},
                   {"source_requests": [{"id": str(uuid4()), "label": "Secret", "url": "https://user:password@example.org/"}]}):
        assert post(client, ROOT, {"creation_key": str(uuid4()), "config": config(**values)}).status_code == 422


def test_late_model_response_cannot_overwrite_newer_private_draft(signed):
    client, service, _ = signed
    profile, _ = create(client)

    class ConcurrentModel(ProposalModel):
        async def complete(self, *args, **kwargs):
            with service.db.session() as session:
                row = session.get(LegalMonitoringProfile, profile["id"])
                row.revision += 1
                row.config_json = {**row.config_json, "goal": "Newer author decision"}
                session.commit()
            return await super().complete(*args, **kwargs)

    service.model_client = ConcurrentModel()
    result = post(client, ROOT + f"/{profile['id']}/suggest", {"expected_revision": 1})
    assert result.status_code == 409
    with service.db.session() as session:
        row = session.get(LegalMonitoringProfile, profile["id"])
        assert row.config_json["goal"] == "Newer author decision" and row.proposals_json == {}


def test_account_erasure_removes_private_draft_and_retains_shared_profile(signed):
    from helvetic_lens.account_erasure_store import erase_selected, select_private_rows

    client, service, identity = signed
    draft, _ = create(client)
    shared, _ = create(client)
    assert activate(client, shared).status_code == 200
    with service.db.session(include_all_organizations=True) as session:
        user = session.get(User, identity["user"]["id"])
        selected = select_private_rows(session, user, [])
        assert selected.keys["legal_monitoring_profiles"] == {(draft["id"],)}
        erase_selected(session, user, selected)
        session.commit()
        assert session.get(LegalMonitoringProfile, draft["id"]) is None
        session.expire_all()
        retained = session.get(LegalMonitoringProfile, shared["id"])
        assert retained.status == "active" and retained.created_by_user_id is None
        assert session.connection().exec_driver_sql("PRAGMA foreign_key_check").all() == []


def test_new_database_connection_and_migration_preserve_profile(signed):
    from helvetic_lens.db import Database

    client, service, identity = signed
    draft, _ = create(client)
    database = Database(service.environment_settings, organization_id=identity["organization"]["id"])
    database.migrate()
    with database.session() as session:
        saved = session.get(LegalMonitoringProfile, draft["id"])
        assert saved.config_json["name"] == "Citizenship advice" and saved.revision == 1
    database.engine.dispose()


def test_cantonal_pack_preserves_its_exact_jurisdiction_in_preview_and_activation(signed):
    from helvetic_lens.regulatory_corpus import DocumentInput, EventInput, ExpressionInput, IdentifierInput

    client, service, _ = signed
    profile, _ = create(client, source_pack_ids=["basel-stadt-legislation"])
    with service.db.session() as session:
        merged = service.regulatory_corpus.merge_document(session, DocumentInput(
            kind="act", authority="basel_stadt", title="Naturalisation procedure",
            identifiers=(IdentifierInput("local", "basel-profile-test"),),
            expression=ExpressionInput(language="de", key="basel-profile-test:de", title="Naturalisation procedure"),
            metadata={"jurisdiction": "CH-BS"}))
        event = service.regulatory_corpus.record_event(session, EventInput(
            work_id=merged.work.id, expression_id=merged.expression.id, authority="basel_stadt",
            event_type="amended", detected_at=utcnow(), provenance_method="official_metadata",
            source_url="https://data.bs.ch/explore/dataset/100354/",
            connector="basel-stadt-legislation", evidence={"stream": "latest-de"}))
        from helvetic_lens.models import RegulatoryEventState
        session.add(RegulatoryEventState(event_id=event.id))
        session.commit()
    preview = post(client, ROOT + f"/{profile['id']}/preview", {"expected_revision": 1})
    assert preview.status_code == 200, preview.text
    assert preview.json()["topics"][0]["candidate_count"] == 1
    active = activate(client, profile)
    assert active.status_code == 200, active.text
    assert active.json()["topics"][0]["plan"]["jurisdictions"] == ["CH-BS"]
