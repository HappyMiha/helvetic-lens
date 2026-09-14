"""A first-run choice is private intent, never source or monitor activation."""

from pathlib import Path

import pytest
from alembic.config import Config
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from test_auth import _csrf, _register, _settings

from alembic import command
from helvetic_lens import onboarding
from helvetic_lens.main import create_app
from helvetic_lens.models import (
    Job,
    OnboardingMilestone,
    OrganizationMembership,
    OutboxMessage,
    UserOnboarding,
)

DOMAINS = ("pollen", "river", "air", "warnings", "commute", "traffic", "tenders", "ip", "auctions")


def test_nine_choices_retry_defer_resume_and_legacy_return_are_only_personal_intent(harness):
    client, fetcher, service, model = harness
    with service.db.session() as session:
        before = [session.scalar(select(func.count()).select_from(table)) for table in (Job, OnboardingMilestone, OutboxMessage)]
    calls = (len(fetcher.calls), len(model.calls))
    assert client.get("/api/onboarding").json()["monitoring_template"] is None
    for domain in DOMAINS:
        body = {"action": "monitoring", "monitoring_template": domain}
        response = client.patch("/api/onboarding", json=body)
        assert response.status_code == 200, response.text
        chosen = response.json()
        assert chosen["monitoring_template"] == domain and chosen["intent"] == "explore"
        assert chosen["state"] == "started" and not chosen["completion_verified"]
        assert client.patch("/api/onboarding", json=body).json() == chosen
        assert client.get("/api/onboarding").json() == chosen
    deferred = client.patch("/api/onboarding", json={"action": "later"}).json()
    assert deferred["state"] == "deferred" and deferred["monitoring_template"] == "auctions"
    resumed = client.patch("/api/onboarding", json={"action": "monitoring", "monitoring_template": "pollen"}).json()
    assert resumed["state"] == "started" and resumed["started_at"] == chosen["started_at"]
    for action in ("topic", "law", "explore"):
        result = client.patch("/api/onboarding", json={"action": action}).json()
        assert result["intent"] == action and result["monitoring_template"] is None
    assert (len(fetcher.calls), len(model.calls)) == calls
    with service.db.session() as session:
        assert [session.scalar(select(func.count()).select_from(table)) for table in (Job, OnboardingMilestone, OutboxMessage)] == before
        assert session.scalar(select(func.count()).select_from(UserOnboarding)) == 1


@pytest.mark.parametrize("body", [
    {"action": "monitoring"}, {"action": "monitoring", "monitoring_template": "customs"},
    {"action": "monitoring", "monitoring_template": ["pollen"]},
    {"action": "later", "monitoring_template": "pollen"},
    {"action": "explore", "monitoring_template": "pollen"},
    {"action": "monitoring", "monitoring_template": "pollen", "user_id": "peer"},
    {"action": "monitoring", "monitoring_template": "pollen", "completed": True},
])
def test_invalid_choice_cannot_forge_setup_or_create_state(harness, body):
    client, _, service, _ = harness
    assert client.patch("/api/onboarding", json=body).status_code == 422
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(UserOnboarding)) == 0


def test_viewer_choice_is_csrf_protected_private_and_survives_login(tmp_path):
    app = create_app(_settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as owner, TestClient(app) as peer:
        first = _register(owner, organization="").json()
        second = _register(peer, email="peer@example.ch").json()
        with app.state.service.db.session(include_all_organizations=True) as session:
            membership = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == first["user"]["id"]))
            membership.role = "viewer"
            session.add(OrganizationMembership(user_id=second["user"]["id"], organization_id=first["organization"]["id"], role="viewer"))
            session.commit()
        body = {"action": "monitoring", "monitoring_template": "pollen"}
        assert owner.patch("/api/onboarding", json=body).status_code == 403
        result = owner.patch("/api/onboarding", json=body, headers=_csrf(owner))
        assert result.status_code == 200 and "no-store" in result.headers["cache-control"]
        assert not owner.get("/api/auth/session").json()["onboarding_required"]
        assert peer.get("/api/onboarding").json()["monitoring_template"] is None
        assert peer.post("/api/auth/session/organization", json={"organization_id": first["organization"]["id"]}, headers=_csrf(peer)).status_code == 200
        assert peer.get("/api/onboarding").json()["monitoring_template"] is None
        assert peer.patch("/api/onboarding", json={"action": "monitoring", "monitoring_template": "air"}, headers=_csrf(peer)).status_code == 200
        assert owner.get("/api/onboarding").json()["monitoring_template"] == "pollen"
        owner.post("/api/auth/logout", headers=_csrf(owner))
        assert owner.get("/api/onboarding").status_code == 401
        assert owner.post("/api/auth/login", json={"email": "owner@example.ch", "password": "correct horse battery staple"}).status_code == 200
        assert owner.get("/api/onboarding").json()["monitoring_template"] == "pollen"


def test_additive_migration_preserves_legacy_intent_and_rejects_customs(harness):
    client, _, service, _ = harness
    chosen = client.patch("/api/onboarding", json={"action": "topic"}).json()
    directory = Path(__file__).resolve().parents[1]
    config = Config(str(directory / "alembic.ini"))
    config.set_main_option("script_location", str(directory / "alembic"))
    with service.db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "4d2a0b146cef")
        assert "monitoring_template" not in {column["name"] for column in inspect(connection).get_columns("user_onboarding")}
        assert connection.execute(text("SELECT intent FROM user_onboarding")).scalar_one() == "topic"
        command.upgrade(config, "head")
        assert "ck_onboarding_monitoring_template" in {row["name"] for row in inspect(connection).get_check_constraints("user_onboarding")}
    assert client.get("/api/onboarding").json() == chosen
    with service.db.engine.begin() as connection:
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(text("UPDATE user_onboarding SET monitoring_template='customs'"))
    with service.db.session() as session:
        assert onboarding.read(session, service.organization_id, "anonymous-development")["monitoring_template"] is None
