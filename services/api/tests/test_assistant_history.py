"""Private history reads/deletion never become shared writes or inference requests."""

import asyncio
import base64
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event

import pytest
from conftest import FakeFetcher, ScriptedModel, add_law, import_old
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from test_auth import _csrf, _register, _settings

from helvetic_lens.db import utcnow
from helvetic_lens.main import create_app
from helvetic_lens.models import (
    AskRecord,
    AssistantConversation,
    Comparison,
    DocumentWatch,
    Job,
    Law,
    MonitoringTopic,
    Organization,
    OrganizationMembership,
    Version,
)


def opened(client, headers=None):
    response = client.post("/api/assistant/conversations", json={"route": "/sources"}, headers=headers or {})
    assert response.status_code == 200, response.text
    return response.json()


def test_metadata_pages_are_bounded_read_only_and_have_no_private_bodies(harness):
    client, _, service, model = harness
    original = opened(client)
    at = utcnow() - timedelta(seconds=5)
    with service.db.session() as session:
        first = session.get(AssistantConversation, original["id"])
        first.updated_at = at
        for index in range(25):
            session.add(AssistantConversation(principal_key="anonymous-development", context_key=f"test:{index}",
                route="/sources", title=f"Context {index}", draft="PRIVATE DRAFT", messages_json=[{"content": "PRIVATE MESSAGE"}],
                handoffs_json=[{"question": "PRIVATE HANDOFF"}], updated_at=at))
        session.commit()
        expected = list(session.scalars(select(AssistantConversation.id).order_by(AssistantConversation.id.desc())))
    queries = []
    def trace(conn, cursor, statement, parameters, context, executemany):
        if "assistant_conversations" in statement:
            queries.append(statement)
    event.listen(service.db.engine, "before_cursor_execute", trace)
    try:
        first = client.get("/api/assistant/conversations").json()
        second = client.get("/api/assistant/conversations", params={"cursor": first["next_cursor"]}).json()
    finally:
        event.remove(service.db.engine, "before_cursor_execute", trace)
    assert len(first["items"]) == 20 and len(second["items"]) == 6
    assert [row["id"] for row in first["items"] + second["items"]] == expected
    assert second["next_cursor"] is None
    assert "PRIVATE" not in json.dumps([first, second])
    assert all(not {"messages", "draft", "handoffs", "messages_json"} & row.keys() for row in first["items"])
    assert len(queries) == 2 and all(q.lstrip().upper().startswith("SELECT") and "LIMIT" in q for q in queries)
    assert all("json_array_length(assistant_conversations.messages_json)" in q for q in queries)
    detail = client.get(f"/api/assistant/conversations/{original['id']}").json()
    assert detail["updated_at"].startswith(at.isoformat()[:19])
    assert detail["updated_at"].endswith("+00:00") and detail["created_at"].endswith("+00:00")
    assert model.calls == []


@pytest.mark.parametrize("change", ["principal", "organization", "limit", "future", "corrupt", "oversize"])
def test_cursor_cannot_change_owner_scope_or_admit_invalid_dates(harness, change):
    client, _, service, _ = harness
    opened(client)
    with service.db.session() as session:
        session.add(AssistantConversation(principal_key="anonymous-development", context_key="two", route="/sources"))
        session.commit()
    token = client.get("/api/assistant/conversations?limit=1").json()["next_cursor"]
    raw = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
    if change in {"principal", "organization"}:
        raw[change] = "someone-else"
    elif change == "limit":
        raw["limit"] = 2
    elif change == "future":
        raw["as_of"] = (utcnow() + timedelta(days=1)).isoformat()
    token = base64.urlsafe_b64encode(json.dumps(raw).encode()).decode()
    if change == "corrupt":
        token = "invalid@@@"
    elif change == "oversize":
        token = "x" * 2049
    assert client.get("/api/assistant/conversations", params={"limit": 1, "cursor": token}).status_code == 422


@pytest.mark.parametrize("role", ["viewer", "organization_admin"])
def test_only_owner_can_read_delete_even_admins_and_viewers_keep_csrf_boundary(tmp_path, role):
    app = create_app(_settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        identity = _register(client).json()
        service = app.state.service
        with service.db.session(include_all_organizations=True) as session:
            member = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"]))
            member.role = role
            other_org = Organization(name="Other", slug="other-history")
            session.add(other_org)
            session.flush()
            colleague = AssistantConversation(organization_id=member.organization_id, principal_key="user:colleague", context_key="sources", route="/sources", draft="COLLEAGUE SECRET")
            foreign = AssistantConversation(organization_id=other_org.id, principal_key=f"user:{identity['user']['id']}", context_key="sources", route="/sources", draft="FOREIGN SECRET")
            session.add_all([colleague, foreign])
            session.commit()
            forbidden = [colleague.id, foreign.id]
        own = opened(client, _csrf(client))
        assert [row["id"] for row in client.get("/api/assistant/conversations").json()["items"]] == [own["id"]]
        for key in forbidden:
            assert client.get(f"/api/assistant/conversations/{key}").status_code == 404
            assert client.delete(f"/api/assistant/conversations/{key}", headers=_csrf(client)).status_code == 404
        assert client.delete(f"/api/assistant/conversations/{own['id']}").status_code == 403
        assert client.delete(f"/api/assistant/conversations/{own['id']}", headers=_csrf(client)).status_code == 200
        assert client.get(f"/api/assistant/conversations/{own['id']}").status_code == 404
        assert client.get("/api/assistant/conversations").json()["items"] == []
        client.cookies.clear()
        assert client.get("/api/assistant/conversations").status_code == 401


def test_delete_preserves_shared_evidence_and_old_context_requires_new_id(harness):
    client, _, service, _ = harness
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post("/api/comparisons", json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]}).json()
    record = opened(client)
    path = f"/api/assistant/conversations/{record['id']}"
    client.patch(path, json={"draft": "PRIVATE"})
    client.post(path + "/handoffs", json={"question": "PRIVATE"})
    models = [Law, Version, Comparison, DocumentWatch, Job, MonitoringTopic, AskRecord]
    with service.db.session() as session:
        session.add(AskRecord(comparison_id=comparison["id"], cache_key="synthetic-shared-history",
            question="Shared question", status="succeeded", result={"answer": "Shared cited answer"}, model="synthetic"))
        session.add(MonitoringTopic(idempotency_key="synthetic-shared-monitor"))
        session.commit()
        counts = [session.scalar(select(func.count()).select_from(m)) for m in models]
        assert counts[-2:] == [1, 1]
    assert client.delete(path).json()["deleted"]
    assert client.delete(path).status_code == 404
    assert client.patch(path, json={"draft": "cannot resurrect"}).status_code == 404
    assert client.post(path + "/handoffs", json={"question": "cannot resurrect"}).status_code == 404
    new = opened(client)
    assert new["id"] != record["id"] and new["draft"] == "" and new["messages"] == new["handoffs"] == []
    with service.db.session() as session:
        assert counts == [session.scalar(select(func.count()).select_from(m)) for m in models]


def test_in_flight_model_response_cannot_recreate_deleted_conversation(harness, monkeypatch):
    client, _, service, _ = harness
    path = f"/api/assistant/conversations/{opened(client)['id']}"
    started, release = Event(), Event()
    async def slow_answer(*args, **kwargs):
        started.set()
        assert await asyncio.to_thread(release.wait, 10)
        return {"reply": "late answer", "requires_cited_ask": False, "provenance": {"local": True}}
    monkeypatch.setattr(service, "assistant_chat", slow_answer)
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(client.post, path + "/messages", json={"message": "Help me"})
        try:
            assert started.wait(10)
            assert client.delete(path).status_code == 200
        finally:
            release.set()
        assert pending.result(timeout=10).status_code == 404
    assert client.get("/api/assistant/conversations").json()["items"] == []
