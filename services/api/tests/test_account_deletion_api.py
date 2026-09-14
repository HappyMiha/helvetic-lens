"""The whole authenticated database-erasure transaction, never real accounts."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_auth import _csrf, _register
from test_monitoring_configuration_export import seed
from test_tender_api import api as api

from helvetic_lens import jobs
from helvetic_lens.account_deletion import erase
from helvetic_lens.account_erasure_store import PREFIX
from helvetic_lens.auth import CSRF_COOKIE, SESSION_COOKIE, AuthService
from helvetic_lens.config import DomainError
from helvetic_lens.models import (
    AccountToken,
    AdministrativeAudit,
    AssistantConversation,
    Job,
    MonitoringSourceAcknowledgement,
    Organization,
    OrganizationMembership,
    RegulatoryWork,
    User,
    UserSession,
)
from helvetic_lens.monitoring_centre import MODELS

URL = "/api/account/deletion"
PASSWORD = "correct horse battery staple"


def confirmation(client):
    response = client.get(URL)
    assert response.status_code == 200, response.text
    value = response.json()
    assert response.headers["cache-control"] == "no-store"
    assert value["can_delete"], value["blockers"]
    return {"password": PASSWORD, "confirmed": True, "confirmation_token": value["confirmation_token"],
        "erase_workspaces": [row["id"] for row in value["workspaces"] if row["disposition"] == "erase_private_workspace"]}


def test_confirmed_account_erasure_deletes_nine_categories_sessions_jobs_and_private_workspace(api):
    client, app, _, identity = api
    database = app.state.service.db
    identifiers = {domain: seed(app, identity, domain) for domain in MODELS}
    conversation = client.post("/api/assistant/conversations", json={"route": "/", "locale": "en-CH"}, headers=_csrf(client))
    assert conversation.status_code == 200, conversation.text
    with database.organization_context(identity["organization"]["id"]), database.session() as session:
        for domain, identifier in identifiers.items():
            jobs.enqueue(session, job_type=domain + "_refresh", target_type=PREFIX[domain], target_id=identifier,
                queue="maintenance", idempotency_key="erasure-" + domain, payload={"private": "work"}, steps=[("Private step", {})])
        session.add(RegulatoryWork(id="retained-official-work", kind="act", authority="official",
            canonical_key="retained-official-work", title="Retained official corpus"))
        session.add(MonitoringSourceAcknowledgement(user_id=identity["user"]["id"],
            issue_key="air:air:acquisition_errors", fingerprint="a" * 64, acknowledged_at=datetime.now(UTC)))
        session.commit()
    cookie, headers = client.cookies.get(SESSION_COOKIE), _csrf(client)
    body = confirmation(client)
    response = client.post(URL, json=body, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["deleted"] and response.headers["cache-control"] == "no-store"
    assert not client.cookies.get(SESSION_COOKIE) and not client.cookies.get(CSRF_COOKIE)
    assert client.get(URL).status_code == 401
    assert client.post("/api/auth/login", json={"email": identity["user"]["email"], "password": PASSWORD}).status_code == 401
    with database.session(include_all_organizations=True) as session:
        assert session.scalar(select(MonitoringSourceAcknowledgement.user_id)) is None
        assert session.get(User, identity["user"]["id"]) is None
        assert session.get(Organization, identity["organization"]["id"]) is None
        assert session.get(AssistantConversation, conversation.json()["id"]) is None
        assert session.get(RegulatoryWork, "retained-official-work") is not None
        assert session.scalar(select(UserSession.id).where(UserSession.user_id == identity["user"]["id"])) is None
        assert session.scalar(select(AccountToken.id).where(AccountToken.user_id == identity["user"]["id"])) is None
        assert session.scalar(select(Job.id).where(Job.organization_id == identity["organization"]["id"])) is None
        for domain, model in MODELS.items():
            assert session.get(model, identifiers[domain]) is None
        audit = session.scalar(select(AdministrativeAudit).where(AdministrativeAudit.action == "account/deletion"))
        assert audit.actor_user_id is None and audit.organization_id is None and audit.actor_kind == "erased_account"
        assert session.connection().exec_driver_sql("PRAGMA foreign_key_check").all() == []
    client.cookies.set(SESSION_COOKIE, cookie)
    assert client.get(URL).status_code == 401


@pytest.mark.parametrize("change,status", (({"password": "incorrect"}, 401), ({"confirmed": False}, 422),
    ({"erase_workspaces": []}, 422), ({"confirmation_token": "forged"}, 409)))
def test_invalid_password_confirmation_or_proof_never_erases_any_account_data(api, change, status):
    client, app, _, identity = api
    identifier = seed(app, identity, "air")
    response = client.post(URL, json={**confirmation(client), **change}, headers=_csrf(client))
    assert response.status_code == status, response.text
    assert response.headers["cache-control"] == "no-store"
    assert "incorrect" not in response.text and PASSWORD not in response.text
    with app.state.service.db.session(include_all_organizations=True) as session:
        assert session.get(User, identity["user"]["id"]).active
        assert session.get(MODELS["air"], identifier) is not None


def test_csrf_and_expired_or_changed_inventory_require_a_new_preview(api):
    client, app, settings, identity = api
    body = confirmation(client)
    assert client.post(URL, json=body).status_code == 403
    auth = AuthService(app.state.service.db, settings)
    actor = auth.resolve(client.cookies.get(SESSION_COOKIE))
    with pytest.raises(DomainError) as expired:
        erase(auth, actor, **body, now=datetime.now(UTC) + timedelta(minutes=16))
    assert expired.value.code == "account_deletion_preview_expired"
    identifier = seed(app, identity, "air")
    response = client.post(URL, json=body, headers=_csrf(client))
    assert response.status_code == 409, response.text
    with app.state.service.db.session(include_all_organizations=True) as session:
        assert session.get(MODELS["air"], identifier) is not None
    current = client.post(URL, json=confirmation(client), headers=_csrf(client))
    assert current.status_code == 200, current.text


def test_viewer_can_erase_own_account_but_not_borrow_a_colleagues_preview(api):
    owner, app, _, identity = api
    original = seed(app, identity, "air")
    body = confirmation(owner)
    with TestClient(app) as viewer:
        second = _register(viewer, email="erasing-viewer@example.test").json()
        with app.state.service.db.session(include_all_organizations=True) as session:
            session.add(OrganizationMembership(organization_id=identity["organization"]["id"],
                user_id=second["user"]["id"], role="viewer"))
            session.commit()
        switched = viewer.post("/api/auth/session/organization", json={"organization_id": identity["organization"]["id"]}, headers=_csrf(viewer))
        assert switched.status_code == 200
        denied = viewer.post(URL, json=body, headers=_csrf(viewer))
        assert denied.status_code == 409, denied.text
        response = viewer.post(URL, json=confirmation(viewer), headers=_csrf(viewer))
        assert response.status_code == 200, response.text
    with app.state.service.db.session(include_all_organizations=True) as session:
        assert session.get(User, identity["user"]["id"]) is not None
        assert session.get(MODELS["air"], original) is not None
        assert session.get(User, second["user"]["id"]) is None
    assert owner.get(URL).status_code == 200
    assert "erasing-viewer@example.test" not in json.dumps(owner.get(URL).json())


def test_late_assistant_answer_cannot_recreate_account_conversation_or_break_audit(api, monkeypatch):
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    client, app, _, identity = api
    response = client.post("/api/assistant/conversations", json={"route": "/", "locale": "en-CH"}, headers=_csrf(client))
    assert response.status_code == 200, response.text
    identifier = response.json()["id"]
    started, release = Event(), Event()

    async def slow_answer(*args, **kwargs):
        started.set()
        assert await asyncio.to_thread(release.wait, 20)
        return {"reply": "late private answer", "requires_cited_ask": False, "provenance": {"local": True}}

    monkeypatch.setattr(app.state.service, "assistant_chat", slow_answer)
    headers = _csrf(client)
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(client.post, f"/api/assistant/conversations/{identifier}/messages",
            json={"message": "Synthetic question"}, headers=headers)
        try:
            assert started.wait(10)
            removed = client.post(URL, json=confirmation(client), headers=headers)
            assert removed.status_code == 200, removed.text
        finally:
            release.set()
        assert pending.result(timeout=15).status_code == 404
    with app.state.service.db.session(include_all_organizations=True) as session:
        assert session.get(User, identity["user"]["id"]) is None
        assert session.get(AssistantConversation, identifier) is None
        assert session.connection().exec_driver_sql("PRAGMA foreign_key_check").all() == []
