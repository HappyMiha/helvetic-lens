"""Personal Marvin messages can seed explicit drafts, never implicit shared rules."""
import pytest
from conftest import FakeFetcher, ScriptedModel, add_law
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_assistant_contract import FakeAssistantManager
from test_auth import _csrf, _register, _settings
from test_monitoring_topics import plan

from helvetic_lens.config import DomainError
from helvetic_lens.main import create_app
from helvetic_lens.models import (
    AssistantConversation,
    Job,
    Law,
    MonitoringTopic,
    Organization,
    OrganizationMembership,
)
from helvetic_lens.monitoring_context import assistant_message_context


def saved_message(client, headers=None, entity=None):
    context = {"route": "/laws" if entity else "/sources", "locale": "en-CH"}
    if entity:
        context["entity"] = {"kind": "law", "id": entity}
    opened = client.post("/api/assistant/conversations", json=context, headers=headers or {})
    assert opened.status_code == 200, opened.text
    conversation_id = opened.json()["id"]
    response = client.post(f"/api/assistant/conversations/{conversation_id}/messages",
        json={"message": "What should I review here about privacy?", "tone": "neutral"}, headers=headers or {})
    assert response.status_code == 200, response.text
    return response.json()


def params(record, message=None):
    return {"kind": "assistant", "id": record["id"], "message": message or record["messages"][0]["id"]}


def test_personal_message_context_reads_selected_user_text_without_sharing_or_inference(harness):
    client, _, service, model = harness
    manager = FakeAssistantManager()
    service.model_manager = manager
    record = saved_message(client)
    with service.db.session() as session:
        before = [session.scalar(select(func.count()).select_from(t)) for t in (AssistantConversation, MonitoringTopic, Job)]
        original = session.get(AssistantConversation, record["id"])
        before_messages, before_updated = original.messages_json, original.updated_at
    response = client.get("/api/monitoring-context", params=params(record))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["question"] == record["messages"][0]["content"]
    assert result["message_id"] == record["messages"][0]["id"]
    assert result["message_created_at"] and result["visibility"] == "personal"
    assert result["requires_confirmation"] and result["ai_calls"] == 0
    assert result["watches"] == [] and result["source_url"] is None and result["reference_url"] is None
    assert "messages" not in result and "draft" not in result and "handoffs" not in result
    assert record["messages"][1]["content"] not in response.text
    with service.db.session() as session:
        assert before == [session.scalar(select(func.count()).select_from(t)) for t in (AssistantConversation, MonitoringTopic, Job)]
        current = session.get(AssistantConversation, record["id"])
        assert current.messages_json == before_messages and current.updated_at == before_updated
    assert model.calls == manager.calls == []


@pytest.mark.parametrize("condition", ["other_user", "other_org", "reply", "missing", "expired", "blank", "oversize", "date", "duplicate", "too_many"])
def test_personal_context_fails_closed_for_wrong_owner_role_or_unavailable_message(harness, condition):
    client, _, service, _ = harness
    service.model_manager = FakeAssistantManager()
    record = saved_message(client)
    request_params = params(record)
    with service.db.session(include_all_organizations=True) as session:
        conversation = session.get(AssistantConversation, record["id"])
        messages = [dict(item) for item in conversation.messages_json]
        if condition == "other_user":
            conversation.principal_key = "user:somebody-else"
        elif condition == "other_org":
            other = Organization(name="Another organization", slug="private-marvin-context")
            session.add(other)
            session.flush()
            conversation.organization_id = other.id
        elif condition == "reply":
            request_params["message"] = messages[1]["id"]
        elif condition == "missing":
            request_params["message"] = "missing"
        elif condition == "expired":
            messages = messages[1:]
        elif condition in {"blank", "oversize"}:
            messages[0]["content"] = " " if condition == "blank" else "x" * 2001
        elif condition == "date":
            messages[0]["created_at"] = "not-a-date"
        elif condition == "duplicate":
            messages.append(dict(messages[0]))
        elif condition == "too_many":
            messages += [dict(messages[1])] * 39
        conversation.messages_json = messages
        session.commit()
        with pytest.raises(DomainError) as denied:
            assistant_message_context(session, service.organization_id, "anonymous-development", record["id"], request_params["message"])
        assert denied.value.status == 404
    response = client.get("/api/monitoring-context", params=request_params)
    assert response.status_code == 404 and "privacy" not in response.text


def test_message_context_revalidates_document_owner_and_existing_watch(harness):
    client, _, service, _ = harness
    service.model_manager = FakeAssistantManager()
    law = add_law(client)
    record = saved_message(client, entity=law["id"])
    response = client.get("/api/monitoring-context", params=params(record))
    assert response.status_code == 200, response.text
    assert response.json()["title"] == law["name"]
    assert response.json()["watches"][0]["law_id"] == law["id"]
    with service.db.session() as session:
        other = Organization(name="Private document", slug="private-marvin-law")
        session.add(other)
        session.flush()
        session.get(Law, law["id"]).owner_organization_id = other.id
        session.commit()
    assert client.get("/api/monitoring-context", params=params(record)).status_code == 404


def test_logged_in_viewer_reads_own_message_but_cannot_share_topic_or_read_colleague(tmp_path):
    app = create_app(_settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        registered = _register(client).json()
        app.state.service.model_manager = FakeAssistantManager()
        with app.state.service.db.session(include_all_organizations=True) as session:
            membership = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == registered["user"]["id"]))
            membership.role = "viewer"
            session.commit()
        record = saved_message(client, _csrf(client))
        response = client.get("/api/monitoring-context", params=params(record))
        assert response.status_code == 200, response.text
        assert client.post("/api/monitoring-topics", json={**plan(), "idempotency_key": "marvin-viewer-test-0001"}, headers=_csrf(client)).status_code == 403
        with app.state.service.db.session(include_all_organizations=True) as session:
            conversation = session.get(AssistantConversation, record["id"])
            assert conversation.principal_key == f"user:{registered['user']['id']}"
            conversation.principal_key = "user:colleague"
            session.commit()
        assert client.get("/api/monitoring-context", params=params(record)).status_code == 404


@pytest.mark.parametrize("message,expected", [(None, 404), ("x"*37, 422)])
def test_message_identifier_is_required_and_bounded(harness, message, expected):
    client, _, _, _ = harness
    request_params = {"kind": "assistant", "id": "missing"}
    if message is not None:
        request_params["message"] = message
    assert client.get("/api/monitoring-context", params=request_params).status_code == expected
