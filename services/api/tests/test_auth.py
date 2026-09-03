from datetime import timedelta

import pytest
from conftest import LAW_URL, FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from helvetic_lens.auth import CSRF_COOKIE, SESSION_COOKIE
from helvetic_lens.config import Settings
from helvetic_lens.db import utcnow
from helvetic_lens.main import create_app
from helvetic_lens.models import OrganizationMembership, User, UserSession


def _settings(tmp_path, **values):
    return Settings(
        _env_file=None,
        database_url="sqlite:///" + (tmp_path / "auth.db").as_posix(),
        data_dir=tmp_path / "auth-data",
        app_environment="test",
        allow_anonymous_dev=False,
        session_cookie_secure=False,
        job_execution_mode="inline",
        apertus_provider="custom",
        apertus_base_url="",
        apertus_api_key="",
        firecrawl_api_key="",
        **values,
    )


def _register(client, email="Owner@Example.CH", organization="Alpine Legal"):
    return client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "name": "Ada Example",
            "organization_name": organization,
        },
    )


def _csrf(client):
    return {"X-CSRF-Token": client.cookies.get(CSRF_COOKIE)}


def test_registration_creates_private_workspace_and_revocable_cookie_session(tmp_path):
    app = create_app(_settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        registered = _register(client)
        assert registered.status_code == 201, registered.text
        payload = registered.json()
        assert payload["authenticated"] is True
        assert payload["role"] == "organization_admin"
        assert payload["user"]["email"] == "owner@example.ch"
        assert payload["onboarding_required"] is True
        assert client.cookies.get(SESSION_COOKIE)
        assert client.cookies.get(CSRF_COOKIE)
        set_cookies = registered.headers.get_list("set-cookie")
        assert any("HttpOnly" in value and "SameSite=lax" in value for value in set_cookies)

        with app.state.service.db.session(include_all_organizations=True) as session:
            user = session.scalar(select(User).where(User.email == "owner@example.ch"))
            stored_session = session.scalar(select(UserSession).where(UserSession.user_id == user.id))
            membership = session.scalar(
                select(OrganizationMembership).where(OrganizationMembership.user_id == user.id)
            )
            assert user.password_hash.startswith("$argon2id$")
            assert "correct horse" not in user.password_hash
            assert stored_session.token_hash != client.cookies.get(SESSION_COOKIE)
            assert membership.role == "organization_admin"

        blocked = client.post("/api/laws", json={"url": LAW_URL, "synthetic": True})
        assert blocked.status_code == 403 and blocked.json()["code"] == "csrf_failed"
        added = client.post(
            "/api/laws",
            json={"url": LAW_URL, "synthetic": True},
            headers=_csrf(client),
        )
        assert added.status_code == 201, added.text
        assert client.get("/api/auth/session").json()["onboarding_required"] is False

        logged_out = client.post("/api/auth/logout", headers=_csrf(client))
        assert logged_out.status_code == 200
        assert client.get("/api/laws").status_code == 401
        assert client.get("/api/auth/session").json()["authentication_required"] is True


def test_login_is_normalized_and_same_organization_label_never_grants_membership(tmp_path):
    app = create_app(_settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as first, TestClient(app) as second:
        first_result = _register(first, "first@example.ch", "Same Name").json()
        second_result = _register(second, "second@example.ch", "Same Name").json()
        assert first_result["organization"]["id"] != second_result["organization"]["id"]

        duplicate = _register(second, " FIRST@EXAMPLE.CH ", "Another")
        assert duplicate.status_code == 409 and duplicate.json()["code"] == "email_exists"
        wrong = second.post(
            "/api/auth/login", json={"email": "first@example.ch", "password": "not-the-password"}
        )
        assert wrong.status_code == 401 and wrong.json()["code"] == "invalid_credentials"
        signed_in = second.post(
            "/api/auth/login",
            json={"email": "FIRST@EXAMPLE.CH", "password": "correct horse battery staple"},
        )
        assert signed_in.status_code == 200
        assert signed_in.json()["organization"]["id"] == first_result["organization"]["id"]


def test_expired_session_is_rejected_and_workspaces_are_selected_from_session(tmp_path):
    fetcher = FakeFetcher()
    app = create_app(_settings(tmp_path), fetcher=fetcher, model_client=ScriptedModel())
    with TestClient(app) as first, TestClient(app) as second:
        _register(first, "one@example.ch", "One")
        _register(second, "two@example.ch", "Two")
        law = first.post(
            "/api/laws",
            json={"url": LAW_URL, "synthetic": True},
            headers=_csrf(first),
        ).json()
        assert second.get(f"/api/laws/{law['id']}").status_code == 404
        assert second.get("/api/laws").json() == []

        token = second.cookies.get(SESSION_COOKIE)
        from helvetic_lens.auth import token_hash

        with app.state.service.db.session(include_all_organizations=True) as session:
            record = session.scalar(
                select(UserSession).where(UserSession.token_hash == token_hash(token))
            )
            record.expires_at = utcnow() - timedelta(seconds=1)
            session.commit()
        assert second.get("/api/laws").status_code == 401


def test_production_refuses_anonymous_access_or_insecure_cookie_configuration():
    with pytest.raises(ValidationError, match="anonymous development access"):
        Settings(
            _env_file=None,
            app_environment="production",
            allow_anonymous_dev=True,
            session_cookie_secure=True,
        )
    with pytest.raises(ValidationError, match="Secure session cookies"):
        Settings(
            _env_file=None,
            app_environment="production",
            allow_anonymous_dev=False,
            session_cookie_secure=False,
        )
