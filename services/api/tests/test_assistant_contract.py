import pytest
from pydantic import ValidationError

from helvetic_lens.assistant_contract import (
    AssistantActionProposal,
    AssistantContextInput,
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
