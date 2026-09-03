import json
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from helvetic_lens.auth import _aware, token_hash
from helvetic_lens.config import Settings
from helvetic_lens.db import utcnow
from helvetic_lens.main import create_app
from helvetic_lens.models import AccountToken, SecurityEvent, User, UserSession


def settings(tmp_path):
    return Settings(
        _env_file=None,
        database_url="sqlite:///" + (tmp_path / "recovery.db").as_posix(),
        data_dir=tmp_path / "recovery-data",
        app_environment="test",
        allow_anonymous_dev=False,
        session_cookie_secure=False,
        job_execution_mode="inline",
        apertus_provider="custom",
        apertus_base_url="",
        apertus_api_key="",
        firecrawl_api_key="",
        auth_email_mode="development",
        public_base_url="http://127.0.0.1:3000",
    )


def register(client, email="owner@example.ch"):
    return client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "name": "Ada Example",
            "organization_name": "Alpine Legal",
        },
    )


def latest_token(tmp_path, parameter):
    files = sorted((tmp_path / "recovery-data" / "auth-mailbox").glob("*.json"))
    message = json.loads(files[-1].read_text(encoding="utf-8"))
    link = message["body"].splitlines()[0].split(": ", 1)[1]
    return parse_qs(urlsplit(link).query)[parameter][0]


def test_email_verification_is_hashed_expiring_and_one_time(tmp_path):
    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        registered = register(client)
        assert registered.status_code == 201
        assert registered.json()["user"]["email_verified"] is False
        raw_token = latest_token(tmp_path, "verify")

        with app.state.service.db.session(include_all_organizations=True) as session:
            record = session.scalar(select(AccountToken).where(AccountToken.purpose == "verify_email"))
            assert record.token_hash == token_hash(raw_token)
            assert raw_token not in record.token_hash
            assert _aware(record.expires_at) > utcnow()

        verified = client.post(
            "/api/auth/email-verification/complete", json={"token": raw_token}
        )
        assert verified.status_code == 200 and verified.json() == {"verified": True}
        assert client.get("/api/auth/session").json()["user"]["email_verified"] is True
        replay = client.post(
            "/api/auth/email-verification/complete", json={"token": raw_token}
        )
        assert replay.status_code == 410 and replay.json()["code"] == "account_token_invalid"


def test_password_reset_is_non_enumerating_and_revokes_every_session(tmp_path):
    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as first, TestClient(app) as second, TestClient(app) as requester:
        register(first)
        signed_in = second.post(
            "/api/auth/login",
            json={"email": "owner@example.ch", "password": "correct horse battery staple"},
        )
        assert signed_in.status_code == 200
        known = requester.post(
            "/api/auth/password-reset/request", json={"email": "owner@example.ch"}
        )
        unknown = requester.post(
            "/api/auth/password-reset/request", json={"email": "nobody@example.ch"}
        )
        assert known.status_code == unknown.status_code == 200
        assert known.json() == unknown.json()
        raw_token = latest_token(tmp_path, "reset")

        changed = requester.post(
            "/api/auth/password-reset/complete",
            json={"token": raw_token, "password": "a completely new passphrase"},
        )
        assert changed.status_code == 200 and changed.json() == {"reset": True}
        assert first.get("/api/laws").status_code == 401
        assert second.get("/api/laws").status_code == 401
        assert requester.post(
            "/api/auth/login",
            json={"email": "owner@example.ch", "password": "correct horse battery staple"},
        ).status_code == 401
        assert requester.post(
            "/api/auth/login",
            json={"email": "owner@example.ch", "password": "a completely new passphrase"},
        ).status_code == 200

        with app.state.service.db.session(include_all_organizations=True) as session:
            user = session.scalar(select(User).where(User.email == "owner@example.ch"))
            assert session.scalar(
                select(func.count()).select_from(UserSession).where(
                    UserSession.user_id == user.id, UserSession.revoked_at.is_not(None)
                )
            ) == 2
            assert session.scalar(
                select(func.count()).select_from(SecurityEvent).where(
                    SecurityEvent.kind == "password_reset_completed"
                )
            ) == 1


def test_expired_reset_is_rejected_and_requests_are_rate_limited(tmp_path):
    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        register(client)
        client.post("/api/auth/password-reset/request", json={"email": "owner@example.ch"})
        raw_token = latest_token(tmp_path, "reset")
        with app.state.service.db.session(include_all_organizations=True) as session:
            record = session.scalar(
                select(AccountToken).where(AccountToken.token_hash == token_hash(raw_token))
            )
            record.expires_at = utcnow() - timedelta(seconds=1)
            session.commit()
        expired = client.post(
            "/api/auth/password-reset/complete",
            json={"token": raw_token, "password": "a completely new passphrase"},
        )
        assert expired.status_code == 410

        results = [
            client.post("/api/auth/password-reset/request", json={"email": "rate@example.ch"})
            for _ in range(6)
        ]
        assert [item.status_code for item in results] == [200, 200, 200, 200, 200, 429]


def test_production_refuses_the_development_mailbox(tmp_path):
    with pytest.raises(ValueError, match="development mailbox"):
        Settings(
            _env_file=None,
            database_url="sqlite:///" + (tmp_path / "production.db").as_posix(),
            data_dir=tmp_path / "production-data",
            app_environment="production",
            allow_anonymous_dev=False,
            session_cookie_secure=True,
            auth_email_mode="development",
        )
