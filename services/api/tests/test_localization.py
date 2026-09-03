import json
from types import SimpleNamespace

from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from sqlalchemy import select

from helvetic_lens import analysis
from helvetic_lens.auth import CSRF_COOKIE
from helvetic_lens.config import Settings
from helvetic_lens.locales import locale_from_accept_language, normalize_locale
from helvetic_lens.main import create_app
from helvetic_lens.models import OrganizationInvitation, User


def settings(tmp_path):
    return Settings(
        _env_file=None,
        database_url="sqlite:///" + (tmp_path / "locale.db").as_posix(),
        data_dir=tmp_path / "locale-data",
        app_environment="test",
        allow_anonymous_dev=False,
        session_cookie_secure=False,
        job_execution_mode="inline",
        apertus_provider="custom",
        apertus_base_url="",
        apertus_api_key="",
        firecrawl_api_key="",
        auth_email_mode="development",
        default_locale="de-CH",
    )


def csrf(client):
    return {"X-CSRF-Token": client.cookies.get(CSRF_COOKIE)}


def test_supported_locale_resolution_honours_weights_and_base_languages():
    assert locale_from_accept_language("es;q=1, fr-FR;q=.8, de;q=.7") == "fr-CH"
    assert locale_from_accept_language("rm;q=.9, it;q=.8") == "rm-CH"
    assert normalize_locale("de_DE") == "de-CH"
    assert normalize_locale("unsupported", "fr-CH") == "fr-CH"


def test_user_and_invitation_locales_are_personal_and_persisted(tmp_path):
    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        registered = client.post(
            "/api/auth/register",
            headers={"Accept-Language": "it-IT,fr;q=.8"},
            json={
                "email": "locale@example.ch",
                "password": "correct horse battery staple",
                "name": "Ada Example",
                "organization_name": "Locale Test",
            },
        )
        assert registered.status_code == 201
        assert registered.json()["user"]["locale"] == "it-CH"

        changed = client.patch(
            "/api/auth/locale", headers=csrf(client), json={"locale": "rm-CH"}
        )
        assert changed.status_code == 200
        assert changed.json()["user"]["locale"] == "rm-CH"
        assert client.get("/api/auth/session").json()["user"]["locale"] == "rm-CH"

        invitation = client.post(
            "/api/organization/invitations",
            headers=csrf(client),
            json={
                "email": "colleague@example.ch",
                "role": "viewer",
                "recipient_locale": "fr-CH",
            },
        )
        assert invitation.status_code == 201
        assert invitation.json()["recipient_locale"] == "fr-CH"
        with app.state.service.db.session(include_all_organizations=True) as session:
            assert session.scalar(select(User).where(User.email == "locale@example.ch")).locale == "rm-CH"
            assert session.scalar(select(OrganizationInvitation)).recipient_locale == "fr-CH"


def test_authentication_mail_uses_saved_locale_and_locale_preserving_link(tmp_path):
    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        client.post(
            "/api/auth/register",
            json={
                "email": "mail@example.ch",
                "password": "correct horse battery staple",
                "name": "Ada Example",
                "organization_name": "Courrier",
                "locale": "fr-CH",
            },
        )
    message_path = sorted((tmp_path / "locale-data" / "auth-mailbox").glob("*.json"))[-1]
    message = json.loads(message_path.read_text(encoding="utf-8"))
    assert message["locale"] == "fr-CH"
    assert message["subject"] == "Confirmez votre adresse Helvetic Lens"
    assert "locale=fr-CH" in message["body"]
    assert '<html lang="fr-CH">' in message["html"]


def test_analysis_cache_is_separate_for_each_output_locale():
    comparison = SimpleNamespace(
        id="comparison",
        identity_json={"fingerprint": "identity", "effective_status": "verified"},
        diff={
            "schema_version": "semantic-diff-v1",
            "algorithm": "test",
            "counts": {},
            "classification_counts": {},
            "items": [],
        },
    )
    profile = SimpleNamespace(revision=2)
    configured = Settings(
        _env_file=None,
        app_environment="test",
        apertus_provider="custom",
        apertus_base_url="http://model.invalid/v1",
        apertus_model="test",
    )
    german = analysis.cache_key(comparison, profile, configured, output_locale="de-CH")
    french = analysis.cache_key(comparison, profile, configured, output_locale="fr-CH")
    assert german != french
    route = analysis.classify_question_intent("What changed?", "it-CH")
    assert route["locale"] == "it-CH"
    assert route["provider_calls"] == 0
