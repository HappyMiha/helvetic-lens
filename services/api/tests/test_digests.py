import asyncio
from datetime import timedelta

import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_relation_analysis import relation_delivery

from helvetic_lens.auth import CSRF_COOKIE
from helvetic_lens.auth_mail import AuthMailer
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.db import utcnow
from helvetic_lens.digests import deliver, enqueue_due, preference_token
from helvetic_lens.impact_inbox import ImpactInboxFilters, ImpactInboxReader
from helvetic_lens.main import create_app
from helvetic_lens.models import DigestDelivery, DigestPreference, User


def test_saved_digest_uses_inbox_without_changing_personal_read_state(harness):
    _, _, service, _ = harness
    relation_delivery(harness, confirmed=True)
    with service.db.session(include_all_organizations=True) as session:
        user = User(
            email="digest@example.ch",
            password_hash="test",
            name="Digest reviewer",
            locale="de-CH",
        )
        session.add(user)
        session.commit()
        user_id = user.id

    saved = service.save_digest_preference(
        user_id,
        enabled=True,
        frequency="daily",
        severities=["unknown"],
        sources=[],
    )
    assert saved["preference"]["enabled"] is True
    assert len(saved["preview"]["events"]) == 1

    job = service.enqueue_digest_now(user_id)
    completed = asyncio.run(service.execute_job(job["id"]))

    assert completed["state"] == "succeeded"
    with service.db.session() as session:
        delivery = session.scalar(select(DigestDelivery))
        assert delivery.status == "succeeded"
        assert delivery.item_count == 1
        assert delivery.summary["events"][0]["impacts"][0]["evidence"]
    with service.db.session() as session:
        inbox = ImpactInboxReader(service.organization_id, user_id).page(
            session, ImpactInboxFilters()
        )
        assert inbox["items"][0]["read_state"] == "unread"
    messages = list((service.environment_settings.storage_path / "auth-mailbox").glob("*.json"))
    assert len(messages) == 1


def test_due_scheduler_is_idempotent_and_direct_unsubscribe_disables_email(harness):
    _, _, service, _ = harness
    with service.db.session(include_all_organizations=True) as session:
        user = User(email="schedule@example.ch", password_hash="test", name="Schedule")
        session.add(user)
        session.flush()
        preference = DigestPreference(
            organization_id=service.organization_id,
            user_id=user.id,
            enabled=True,
            frequency="weekly",
            severities=[],
            sources=[],
            next_delivery_at=utcnow() - timedelta(minutes=1),
        )
        session.add(preference)
        session.commit()
        token = preference_token(service.environment_settings, preference.id)

    first = enqueue_due(service.db, service.environment_settings)
    second = enqueue_due(service.db, service.environment_settings)
    assert first == {"due": 1, "queued": 1}
    assert second == {"due": 0, "queued": 0}

    assert service.unsubscribe_digest(token) == {"unsubscribed": True}
    with service.db.session() as session:
        preference = session.scalar(select(DigestPreference))
        assert preference.enabled is False
        assert preference.next_delivery_at is None


def test_delivery_failure_is_saved_without_changing_inbox_state(harness, monkeypatch):
    _, _, service, _ = harness
    relation_delivery(harness, confirmed=True)
    with service.db.session(include_all_organizations=True) as session:
        user = User(email="failed-digest@example.ch", password_hash="test", name="Failure")
        session.add(user)
        session.commit()
        user_id = user.id
    service.save_digest_preference(
        user_id,
        enabled=True,
        frequency="daily",
        severities=["unknown"],
        sources=[],
    )
    job = service.enqueue_digest_now(user_id)

    def fail_delivery(*_args, **_kwargs):
        raise DomainError("SMTP unavailable", 503, "email_delivery_failed")

    monkeypatch.setattr(AuthMailer, "send_message", fail_delivery)
    with pytest.raises(DomainError, match="SMTP unavailable"):
        deliver(service.db, service.environment_settings, job["target_id"])

    with service.db.session() as session:
        delivery = session.get(DigestDelivery, job["target_id"])
        assert delivery.status == "failed"
        assert delivery.summary["events"]
        inbox = ImpactInboxReader(service.organization_id, user_id).page(
            session, ImpactInboxFilters()
        )
        assert inbox["items"][0]["read_state"] == "unread"


def test_digest_preferences_are_personal_and_viewers_can_opt_in(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url="sqlite:///" + (tmp_path / "digest-auth.db").as_posix(),
        data_dir=tmp_path / "digest-auth-data",
        app_environment="test",
        allow_anonymous_dev=False,
        job_execution_mode="inline",
        apertus_provider="custom",
        apertus_base_url="",
    )
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        registered = client.post(
            "/api/auth/register",
            json={
                "email": "digest-owner@example.ch",
                "password": "correct horse battery staple",
                "name": "Digest owner",
                "organization_name": "Digest workspace",
            },
        )
        assert registered.status_code == 201
        response = client.put(
            "/api/digests/preferences",
            headers={"X-CSRF-Token": client.cookies.get(CSRF_COOKIE)},
            json={
                "enabled": True,
                "frequency": "weekly",
                "severities": ["high", "medium"],
                "sources": ["fedlex"],
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["preference"]["severities"] == ["high", "medium"]
        with app.state.service.db.session(include_all_organizations=True) as session:
            preference = session.scalar(select(DigestPreference))
            token = preference_token(settings, preference.id)

    with TestClient(app) as public_client:
        unsubscribed = public_client.post(
            "/api/digests/unsubscribe", json={"token": token}
        )
        assert unsubscribed.status_code == 200
        assert unsubscribed.json() == {"unsubscribed": True}
