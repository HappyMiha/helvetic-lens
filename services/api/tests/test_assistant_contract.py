import pytest
from conftest import add_law, import_old
from pydantic import ValidationError

from helvetic_lens.assistant_contract import (
    ASSISTANT_CHAT_SCHEMA,
    ASSISTANT_PERSONA_VERSION,
    ASSISTANT_REMARK_SCHEMA,
    AssistantActionProposal,
    AssistantChatInput,
    AssistantContextInput,
    AssistantRemarkInput,
    assistant_chat_messages,
    assistant_remark_messages,
    assistant_remark_schema,
    assistant_route_help,
    build_assistant_context,
)


def test_context_forbids_untyped_or_sensitive_payloads():
    with pytest.raises(ValidationError):
        AssistantContextInput.model_validate(
            {
                "route": "/sources",
                "intent": "explain_screen",
                "raw_page_text": "token=secret",
            }
        )
    with pytest.raises(ValidationError):
        AssistantContextInput.model_validate({"route": "https://example.com", "intent": "explain_screen"})


def test_change_questions_require_a_comparison_on_the_comparison_route():
    with pytest.raises(ValidationError):
        AssistantContextInput.model_validate({"route": "/compare", "intent": "explain_change"})
    with pytest.raises(ValidationError):
        AssistantContextInput.model_validate(
            {
                "route": "/sources",
                "intent": "explain_change",
                "entity": {
                    "kind": "comparison",
                    "id": "00000000-0000-0000-0000-000000000001",
                },
            }
        )


def test_sensitive_product_states_suppress_persona_quips():
    data = AssistantContextInput.model_validate(
        {
            "route": "/impact",
            "signals": {"has_high_impact_alert": True},
        }
    )
    result = build_assistant_context(data, role="organization_admin")
    assert result["persona"] == {
        "quip_allowed": False,
        "suppression_reason": "sensitive_product_state",
    }


def test_viewer_cannot_receive_an_enabled_shared_write_proposal():
    data = AssistantContextInput.model_validate({"route": "/topics", "intent": "draft_monitoring_topic"})
    result = build_assistant_context(data, role="viewer")
    write = next(item for item in result["actions"] if item["writes_shared_state"])
    assert write["confirmation_required"] is True
    assert write["enabled"] is False
    assert write["disabled_reason"] == "organization_admin_required"


def test_shared_writes_cannot_skip_confirmation():
    with pytest.raises(ValidationError):
        AssistantActionProposal(
            action_id="unsafe",
            kind="retry_job",
            target="/api/jobs/one/retry",
            writes_shared_state=True,
            confirmation_required=False,
        )


def test_context_endpoint_returns_only_the_versioned_bounded_contract(harness):
    client, _, _, _ = harness
    response = client.post(
        "/api/assistant/context",
        json={
            "schema_version": "assistant-context.v1",
            "intent": "explain_screen",
            "route": "/sources",
            "signals": {"result_count": 4, "source_health": "partial"},
            "locale": "en-CH",
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["context"] == {
        "route": "/sources",
        "entity": None,
        "signals": {
            "result_count": 4,
            "source_health": "partial",
            "has_visible_error": False,
            "has_high_impact_alert": False,
            "has_destructive_confirmation": False,
            "has_unsupported_evidence": False,
        },
    }
    assert "arbitrary_page_text" in result["privacy"]["excluded"]
    assert result["persona"]["quip_allowed"] is True


def test_context_endpoint_rejects_an_unavailable_tenant_entity(harness):
    client, _, _, _ = harness
    response = client.post(
        "/api/assistant/context",
        json={
            "intent": "explain_change",
            "route": "/compare",
            "entity": {
                "kind": "comparison",
                "id": "00000000-0000-0000-0000-000000000000",
            },
        },
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_context_endpoint_labels_only_a_validated_tenant_entity(harness):
    client, _, _, _ = harness
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]},
    ).json()

    response = client.post(
        "/api/assistant/context",
        json={
            "intent": "explain_screen",
            "route": "/compare",
            "entity": {"kind": "comparison", "id": comparison["id"]},
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["context"]["entity"] == {
        "kind": "comparison",
        "id": comparison["id"],
        "label": law["name"],
    }
    assert "validated_entity_label" in result["privacy"]["included"]


def test_personal_assistant_conversation_persists_draft_and_handoffs(harness):
    client, _, _, _ = harness
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]},
    ).json()
    context = {
        "intent": "explain_screen",
        "route": "/compare",
        "entity": {"kind": "comparison", "id": comparison["id"]},
        "locale": "de-CH",
    }

    opened = client.post("/api/assistant/conversations", json=context)
    assert opened.status_code == 200, opened.text
    conversation = opened.json()
    assert conversation["entity"]["label"] == law["name"]
    assert conversation["visibility"] == "personal"

    saved = client.patch(
        f"/api/assistant/conversations/{conversation['id']}",
        json={"draft": "Welche Frist hat sich geändert?"},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["draft"] == "Welche Frist hat sich geändert?"

    handed_off = client.post(
        f"/api/assistant/conversations/{conversation['id']}/handoffs",
        json={"question": "Welche Frist hat sich geändert?"},
    )
    assert handed_off.status_code == 200, handed_off.text
    assert handed_off.json()["draft"] == ""
    assert handed_off.json()["handoffs"][-1]["question"] == "Welche Frist hat sich geändert?"

    reopened = client.post("/api/assistant/conversations", json=context)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["id"] == conversation["id"]
    assert reopened.json()["handoffs"] == handed_off.json()["handoffs"]


def test_personal_assistant_conversation_rejects_unknown_record(harness):
    client, _, _, _ = harness
    response = client.patch(
        "/api/assistant/conversations/00000000-0000-0000-0000-000000000099",
        json={"draft": "private"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_chat_prompt_is_bounded_and_forces_cited_legal_handoff():
    data = AssistantChatInput(message="What changed in this law?", tone="very_dry")
    messages = assistant_chat_messages(
        message=data.message,
        locale="en-CH",
        tone=data.tone,
        route="/compare",
        entity_kind="comparison",
        entity_label="Test law",
        history=[
            {"role": "user", "content": f"old-{index}"}
            for index in range(10)
        ],
    )
    serialized = "\n".join(item["content"] for item in messages)
    assert [item["role"] for item in messages[:2]] == ["system", "user"]
    assert ASSISTANT_PERSONA_VERSION in serialized
    assert "requires_cited_ask=true" in serialized
    assert "old-0" not in serialized
    assert "old-9" in serialized
    assert ASSISTANT_CHAT_SCHEMA["additionalProperties"] is False


def test_screen_help_is_localized_deterministic_and_route_specific():
    reply = assistant_route_help(
        "Was soll ich auf dieser Seite prüfen?", "de-CH", "/sources", "very_dry"
    )
    assert "Abdeckung offizieller Quellen" in reply
    assert "planetengrosses Gehirn" in reply
    assert assistant_route_help("Hallo Marvin", "de-CH", "/sources", "very_dry") is None


def test_personal_assistant_chat_is_persisted_and_local(harness):
    client, _, service, _ = harness
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]},
    ).json()
    context = {
        "route": "/compare",
        "entity": {"kind": "comparison", "id": comparison["id"]},
        "locale": "en-CH",
    }
    conversation = client.post("/api/assistant/conversations", json=context).json()

    class ChatManager(FakeAssistantManager):
        async def complete_profile(self, profile_id, organization_id, messages, **kwargs):
            self.calls.append((profile_id, organization_id, messages, kwargs))
            return {
                "content": '{"reply":"Use the cited comparison. The paperwork insists.","requires_cited_ask":true}',
                "profile": {
                    "id": "assistant-lite",
                    "selected_model": {
                        "served_model_id": "apertus-test",
                        "immutable_revision": "abc123",
                    },
                },
            }

    manager = ChatManager()
    service.model_manager = manager
    response = client.post(
        f"/api/assistant/conversations/{conversation['id']}/messages",
        json={"message": "What changed?", "tone": "very_dry"},
    )
    assert response.status_code == 200, response.text
    saved = response.json()["messages"]
    assert [item["role"] for item in saved] == ["user", "assistant"]
    assert saved[-1]["requires_cited_ask"] is True
    assert saved[-1]["provenance"]["local"] is True
    assert saved[-1]["provenance"]["cloud_fallback"] is False
    assert manager.calls[0][0] == "assistant-lite"

    reopened = client.post("/api/assistant/conversations", json=context).json()
    assert reopened["messages"] == saved


def test_screen_help_chat_skips_model_and_persists_trusted_route_answer(harness):
    client, _, service, _ = harness
    manager = FakeAssistantManager()
    service.model_manager = manager
    conversation = client.post(
        "/api/assistant/conversations",
        json={"route": "/sources", "locale": "en-CH"},
    ).json()
    response = client.post(
        f"/api/assistant/conversations/{conversation['id']}/messages",
        json={"message": "What should I review on this screen?", "tone": "very_dry"},
    )
    assert response.status_code == 200, response.text
    answer = response.json()["messages"][-1]
    assert "official-source coverage" in answer["content"]
    assert answer["requires_cited_ask"] is False
    assert answer["provenance"]["model"] == "deterministic-route-help"
    assert manager.calls == []


def test_remark_prompt_contains_only_bounded_context_and_versioned_persona():
    data = AssistantRemarkInput.model_validate(
        {
            "route": "/sources",
            "locale": "de-CH",
            "trigger": "activity",
            "tone": "very_dry",
            "signals": {"result_count": 4},
        }
    )
    messages = assistant_remark_messages(data)
    serialized = "\n".join(item["content"] for item in messages)
    assert ASSISTANT_PERSONA_VERSION in serialized
    assert "official source coverage" in serialized
    assert "de-CH" in serialized
    assert "field" not in messages[1]["content"].lower()
    assert ASSISTANT_REMARK_SCHEMA["properties"]["angle"]["enum"] == [
        "bureaucracy",
        "evidence",
        "queue",
        "progress",
    ]
    assert assistant_remark_schema(data)["properties"]["angle"]["enum"][0] == "queue"


@pytest.mark.parametrize(
    ("route", "expected"),
    [
        ("/compare", "evidence"),
        ("/sources", "queue"),
        ("/topics", "bureaucracy"),
        ("/registry", "progress"),
    ],
)
def test_remark_angle_is_ranked_from_safe_route_context(route, expected):
    data = AssistantRemarkInput.model_validate(
        {"route": route, "trigger": "arrival", "tone": "very_dry"}
    )
    assert assistant_remark_schema(data)["properties"]["angle"]["enum"] == [expected]


class FakeAssistantManager:
    def __init__(self):
        self.calls = []

    async def complete_profile(self, profile_id, organization_id, messages, **kwargs):
        self.calls.append((profile_id, organization_id, messages, kwargs))
        return {
            "content": '{"angle":"queue"}',
            "profile": {
                "id": "assistant-lite",
                "selected_model": {
                    "served_model_id": "apertus-test",
                    "immutable_revision": "abc123",
                },
            },
        }


def test_remark_endpoint_uses_local_profile_and_returns_provenance(harness):
    client, _, service, _ = harness
    manager = FakeAssistantManager()
    service.model_manager = manager

    response = client.post(
        "/api/assistant/remark",
        json={
            "route": "/sources",
            "locale": "en-CH",
            "trigger": "arrival",
            "tone": "very_dry",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["key"] == "companion.generated.queue"
    assert response.json()["provenance"] == {
        "profile": "assistant-lite",
        "persona_version": ASSISTANT_PERSONA_VERSION,
        "model": "apertus-test",
        "model_revision": "abc123",
        "local": True,
        "cloud_fallback": False,
    }
    assert manager.calls[0][0] == "assistant-lite"


def test_sensitive_state_rejects_remark_before_local_inference(harness):
    client, _, service, _ = harness
    manager = FakeAssistantManager()
    service.model_manager = manager

    response = client.post(
        "/api/assistant/remark",
        json={
            "route": "/impact",
            "trigger": "arrival",
            "signals": {"has_high_impact_alert": True},
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "assistant_quip_suppressed"
    assert manager.calls == []


def test_invalid_local_remark_gets_one_bounded_repair(harness):
    client, _, service, _ = harness

    class RepairingManager(FakeAssistantManager):
        async def complete_profile(self, profile_id, organization_id, messages, **kwargs):
            result = await super().complete_profile(
                profile_id, organization_id, messages, **kwargs
            )
            if len(self.calls) == 1:
                result["content"] = "not json"
            return result

    manager = RepairingManager()
    service.model_manager = manager

    response = client.post(
        "/api/assistant/remark",
        json={"route": "/sources", "trigger": "activity", "tone": "dry"},
    )

    assert response.status_code == 200, response.text
    assert len(manager.calls) == 2
    assert manager.calls[1][2][-1]["content"].startswith("Repair the answer")
    assert manager.calls[0][3]["response_schema"]["additionalProperties"] is False
    assistant_chat_messages,
