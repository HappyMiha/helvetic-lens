"""Personal introduction is neither shared setup nor verified first value."""

import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_auth import _csrf, _register, _settings
from test_workflow import add_law

from helvetic_lens import onboarding
from helvetic_lens.main import create_app
from helvetic_lens.models import DocumentWatch, OrganizationMembership, UserOnboarding


def test_read_is_passive_and_shared_watches_do_not_finish_personal_setup(harness):
    client, fetcher, service, model = harness
    initial = client.get("/api/onboarding").json()
    assert initial["state"] == "new" and initial["completion_verified"] is False
    assert initial["organization_setup"]["active_document_watch"] is False
    law = add_law(client)
    calls = (len(fetcher.calls), len(model.calls))
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(UserOnboarding)) == 0
    after = client.get("/api/onboarding").json()
    assert after["state"] == "new" and after["organization_setup"]["active_document_watch"] is True
    chosen = client.patch("/api/onboarding", json={"action": "topic"}).json()
    assert chosen["state"] == "started" and chosen["intent"] == "topic"
    with service.db.session() as session:
        watch = session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law["id"]))
        watch.active = False
        session.commit()
    after = client.get("/api/onboarding").json()
    assert after["state"] == "started" and after["organization_setup"]["active_document_watch"] is False
    assert (len(fetcher.calls), len(model.calls)) == calls


def test_defer_resume_idempotence_and_principal_isolation(harness):
    client, _, service, _ = harness
    first = client.patch("/api/onboarding", json={"action": "later"}).json()
    assert first["state"] == "deferred" and first["intent"] is None and first["started_at"] is None
    assert client.patch("/api/onboarding", json={"action": "later"}).json() == first
    started = client.patch("/api/onboarding", json={"action": "law"}).json()
    assert started["state"] == "started" and started["deferred_at"] is None
    assert client.patch("/api/onboarding", json={"action": "law"}).json() == started
    deferred = client.patch("/api/onboarding", json={"action": "later"}).json()
    assert deferred["intent"] == "law" and deferred["started_at"] == started["started_at"]
    resumed = client.patch("/api/onboarding", json={"action": "explore"}).json()
    assert resumed["intent"] == "explore" and resumed["started_at"] == started["started_at"]
    with service.db.session(include_all_organizations=True) as session:
        assert onboarding.read(session, service.organization_id, "colleague")["state"] == "new"
        assert onboarding.read(session, "other-organization", "anonymous-development")["state"] == "new"
        assert session.scalar(select(func.count()).select_from(UserOnboarding)) == 1


@pytest.mark.parametrize(
    "body",
    [
        {"action": "complete"},
        {"action": "topic", "organization_id": "another"},
        {"action": "topic", "principal_key": "colleague"},
        {},
    ],
)
def test_invalid_or_forged_action_does_not_create_state(harness, body):
    client, _, service, _ = harness
    assert client.patch("/api/onboarding", json=body).status_code == 422
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(UserOnboarding)) == 0


def test_authenticated_viewer_csrf_login_and_workspace_isolation(tmp_path):
    app = create_app(_settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as first, TestClient(app) as second:
        account = _register(first).json()
        colleague = _register(second, email="second@example.ch").json()
        with app.state.service.db.session(include_all_organizations=True) as session:
            membership = session.scalar(
                select(OrganizationMembership).where(OrganizationMembership.user_id == account["user"]["id"])
            )
            membership.role = "viewer"
            session.commit()
        assert first.patch("/api/onboarding", json={"action": "topic"}).status_code == 403
        assert (
            first.patch("/api/onboarding", json={"action": "topic"}, headers=_csrf(first)).status_code == 200
        )
        assert first.get("/api/auth/session").json()["onboarding_required"] is False
        assert second.get("/api/onboarding").json()["state"] == "new"
        assert second.get("/api/auth/session").json()["onboarding_required"] is True
        with app.state.service.db.session(include_all_organizations=True) as session:
            session.add(
                OrganizationMembership(
                    organization_id=account["organization"]["id"],
                    user_id=colleague["user"]["id"],
                    role="viewer",
                )
            )
            session.commit()
        switched = second.post(
            "/api/auth/session/organization",
            json={"organization_id": account["organization"]["id"]},
            headers=_csrf(second),
        )
        assert switched.status_code == 200
        assert second.get("/api/onboarding").json()["state"] == "new"
        assert (
            second.patch("/api/onboarding", json={"action": "later"}, headers=_csrf(second)).status_code
            == 200
        )
        assert first.get("/api/onboarding").json()["intent"] == "topic"
        switched = second.post(
            "/api/auth/session/organization",
            json={"organization_id": colleague["organization"]["id"]},
            headers=_csrf(second),
        )
        assert switched.status_code == 200
        assert second.get("/api/onboarding").json()["state"] == "new"
        first.post("/api/auth/logout", headers=_csrf(first))
        assert first.get("/api/onboarding").status_code == 401
        logged_in = first.post(
            "/api/auth/login", json={"email": "owner@example.ch", "password": "correct horse battery staple"}
        )
        assert logged_in.status_code == 200 and logged_in.json()["onboarding_required"] is False
        assert first.get("/api/onboarding").json()["intent"] == "topic"


def test_onboarding_migration_preserves_existing_watch(harness):
    from pathlib import Path

    from alembic.config import Config
    from sqlalchemy import inspect

    from alembic import command

    client, _, service, _ = harness
    law = add_law(client)
    directory = Path(__file__).resolve().parents[1]
    config = Config(str(directory / "alembic.ini"))
    config.set_main_option("script_location", str(directory / "alembic"))
    with service.db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "fb38a72e4109")
        assert "user_onboarding" not in inspect(connection).get_table_names()
        command.upgrade(config, "head")
        assert "uq_onboarding_org_principal" in {
            row["name"] for row in inspect(connection).get_unique_constraints("user_onboarding")
        }
    with service.db.session() as session:
        assert session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law["id"])).active
        assert onboarding.needed(session, service.organization_id, "anonymous-development")


def test_postgres_first_use_from_two_tabs_is_one_personal_record(harness):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    _, _, service, _ = harness
    if service.db.engine.dialect.name != "postgresql":
        pytest.skip("Real row-lock concurrency requires disposable PostgreSQL")
    ready = Barrier(2)

    def write(_):
        with service.db.session() as session:
            ready.wait(timeout=10)
            return onboarding.save(session, service.organization_id, "anonymous-development", None, "topic")

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(write, [1, 2]))
    assert results[0] == results[1]
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(UserOnboarding)) == 1
