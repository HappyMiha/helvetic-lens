"""Explicit event context reuses cited briefs, never companion-generated claims."""
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from test_brief_feedback import prepared
from test_interest_execution import artifacts, execution

from helvetic_lens.models import AssistantConversation, RegulatoryEventState

__all__ = ["artifacts", "execution"]


def context(event, locale="en-CH"):
    return {"route": "/", "locale": locale, "entity": {"kind": "regulatory_event", "id": event}}


def test_event_context_and_shared_reader_reuse_exact_assessment(execution, harness):
    service, saved, _ = prepared(execution)
    service.model_client = execution[1].client
    client, state = harness[0], execution[4]
    generated, counts = len(state["generated"]), len(state["counts"])
    response = client.post("/api/assistant/context", json=context(execution[2]))
    assert response.status_code == 200, response.text
    assert response.json()["actions"][0]["target"] == f"/?event={execution[2]}"
    assert "result" not in response.json() and "evidence" not in response.json()
    first = client.post("/api/assistant/conversations", json=context(execution[2])).json()
    again = client.post("/api/assistant/conversations", json=context(execution[2])).json()
    assert first["id"] == again["id"] and first["visibility"] == "personal"
    assert first["messages"] == []
    brief = client.get(f"/api/interest-feed/events/{execution[2]}/brief", params={"locale": "en"}).json()
    assert brief["status"] == "available" and brief["assessment_id"] == saved["id"]
    assert brief["result"] == saved["result"] and brief["ai_calls"] == 0
    assert len(state["generated"]) == generated and len(state["counts"]) == counts
    with service.db.session() as session:
        records = list(session.scalars(select(AssistantConversation)))
        assert len(records) == 1 and records[0].entity_kind == "regulatory_event"


@pytest.mark.parametrize("locale", ["de-CH", "fr-CH", "it-CH", "rm-CH"])
def test_event_user_language_does_not_fallback_or_translate(execution, harness, locale):
    prepared(execution)
    state, client = execution[4], harness[0]
    before = len(state["requests"])
    opened = client.post("/api/assistant/conversations", json=context(execution[2], locale))
    assert opened.status_code == 200 and opened.json()["locale"] == locale
    response = client.get(f"/api/interest-feed/events/{execution[2]}/brief", params={"locale":locale[:2]}).json()
    assert response["locale"] == locale[:2] and response["status"] == "not_scheduled"
    assert response["result"] is None and len(state["requests"]) == before


def test_unavailable_event_cannot_open_context_or_send_chat(execution, harness):
    service, _, _ = prepared(execution)
    client = harness[0]
    path = "/api/assistant/conversations"
    opened = client.post(path, json=context(execution[2])).json()
    assert client.post(path, json=context(str(uuid4()))).status_code == 404
    assert client.post(path, json={**context(execution[2]),"route":"/sources"}).status_code == 422
    before = len(execution[4]["requests"])
    with service.db.session() as session:
        session.execute(delete(RegulatoryEventState).where(RegulatoryEventState.organization_id == service.organization_id))
        session.commit()
    assert client.post("/api/assistant/context", json=context(execution[2])).status_code == 404
    assert client.post(path, json=context(execution[2])).status_code == 404
    assert client.post(f"{path}/{opened['id']}/messages", json={"message":"What changed?"}).status_code == 404
    assert len(execution[4]["requests"]) == before
