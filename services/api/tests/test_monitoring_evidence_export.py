"""Private download manifests and real session/CSRF/source revalidation."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_auth import _csrf, _register
from test_business_item_api import seed
from test_monitoring_personal_evidence import air_api as air_api
from test_monitoring_personal_evidence import db as db
from test_monitoring_personal_evidence import river_api as river_api
from test_monitoring_personal_evidence import scenario as scenario
from test_monitoring_personal_evidence import template as template
from test_tender_api import api as api

from helvetic_lens import business_monitor_api
from helvetic_lens import monitoring_evidence_export as exports
from helvetic_lens.auth import Identity
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.models import OrganizationMembership, User, UserSession
from helvetic_lens.monitoring_evidence_ask import Record
from helvetic_lens.monitoring_evidence_packet import FORMAT, canonical, packet

ROOT = "/api/monitoring-centre/evidence/export"


def verify_file(value):
    encoded = value["canonical_json"].encode("utf-8")
    assert hashlib.sha256(encoded).hexdigest() == value["sha256"]
    assert len(encoded) == value["bytes"]
    decoded = json.loads(encoded)
    assert decoded["manifest"] == value["manifest"]
    assert decoded["manifest"]["format"] == FORMAT
    payload = canonical(decoded["payload"]).encode("utf-8")
    assert len(payload) == decoded["manifest"]["payload_bytes"]
    assert hashlib.sha256(payload).hexdigest() == decoded["manifest"]["payload_sha256"]
    assert decoded["manifest"]["raw_provider_payload_included"] is False
    assert "private_decisions" in decoded["payload"]
    assert "private_review" not in decoded["payload"]["native_evidence"]
    return decoded


def login(database, user_id, now):
    with database.session() as session:
        user = session.get(User, user_id)
        organization = session.info["organization_id"]
        role = session.scalar(select(OrganizationMembership.role).where(
            OrganizationMembership.organization_id == organization, OrganizationMembership.user_id == user_id))
        row = UserSession(user_id=user_id, organization_id=organization,
            token_hash=uuid4().hex + uuid4().hex, csrf_hash="c" * 64, expires_at=now + timedelta(hours=1))
        session.add(row)
        session.flush()
        actor = Identity(user_id, organization, role, row.id, row.csrf_hash, user.email, user.name, "Synthetic workspace")
        session.commit()
        return actor


def test_all_personal_packets_have_verifiable_manifest_and_separate_private_review(scenario):
    database, settings, user, record, now = scenario
    with database.session() as session:
        before = session.connection().exec_driver_sql("SELECT total_changes()").scalar()
        result = packet(session, settings, user, record, now=now, prepared_at=now, locale="en-CH")
        decoded = verify_file(result)
        assert decoded["manifest"]["selection"]["item_id"] == record.item_id
        assert decoded["manifest"]["scope"]["user_id"] == user
        assert session.connection().exec_driver_sql("SELECT total_changes()").scalar() == before


def test_all_personal_downloads_recheck_current_membership(scenario):
    database, settings, user, record, now = scenario
    actor = login(database, user, now)
    preview = exports.prepare(database, settings, actor, record, now=now, locale="de-CH")
    result = exports.download(database, settings, actor, preview["confirmation_token"], now=now)
    assert result["sha256"] == preview["sha256"]
    verify_file(result)
    with database.session() as session:
        membership = session.scalar(select(OrganizationMembership).where(
            OrganizationMembership.user_id == user, OrganizationMembership.organization_id == actor.organization_id))
        session.delete(membership)
        session.commit()
    with pytest.raises(DomainError):
        exports.download(database, settings, actor, preview["confirmation_token"], now=now)


def setup(api, monkeypatch, domain):
    if domain != "tenders":
        if domain == "ip":
            import test_trademark_sources as source
        else:
            import test_auction_sources as source
        grant = source.grant
        monkeypatch.setattr(source, "grant", lambda *args, **kwargs: grant(*args, export_allowed=True, **kwargs))
    monitor, item, _ = seed(api, domain, monkeypatch)
    saved_now = business_monitor_api.datetime.now(UTC)

    class Clock(datetime):
        current = saved_now

        @classmethod
        def now(cls, tz=None):
            return cls.current.astimezone(tz) if tz else cls.current.replace(tzinfo=None)

    monkeypatch.setattr(exports, "datetime", Clock)
    return {"domain": domain, "monitor_id": monitor, "item_id": item, "locale": "en-CH"}, Clock


@pytest.mark.parametrize("domain", ("tenders", "ip", "auctions"))
def test_business_http_preview_and_download_are_exact_private_and_integrity_checked(api, monkeypatch, domain):
    client, app, _, _ = api
    body, _ = setup(api, monkeypatch, domain)
    calls = len(app.state.service.model_client.calls)
    assert client.post(ROOT + "/preview", json=body).status_code == 403
    response = client.post(ROOT + "/preview", json=body, headers=_csrf(client))
    assert response.status_code == 200, response.text
    preview = response.json()
    assert response.headers["cache-control"] == "no-store"
    assert "canonical_json" not in preview and "payload" not in preview
    download = {"confirmation_token": preview["confirmation_token"]}
    assert client.post(ROOT + "/download", json=download).status_code == 403
    response = client.post(ROOT + "/download", json=download, headers=_csrf(client))
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    decoded = verify_file(response.json())
    assert response.json()["sha256"] == preview["sha256"]
    assert decoded["manifest"]["selection"]["domain"] == domain
    assert "original" not in decoded["payload"]["native_evidence"]["after"]["facts"]
    with TestClient(app) as peer:
        assert peer.post(ROOT + "/download", json=download).status_code in {401, 403}
        _register(peer, email=f"export-peer-{domain}@example.test")
        denied = peer.post(ROOT + "/download", json=download, headers=_csrf(peer))
        assert denied.status_code == 409
        assert "canonical_json" not in denied.json() and denied.headers["cache-control"] == "no-store"
        assert peer.post(ROOT + "/preview", json=body, headers=_csrf(peer)).status_code == 404
    assert len(app.state.service.model_client.calls) == calls


@pytest.mark.parametrize("fault", ("token", "expired", "password", "revoked_session", "extra_body"))
def test_download_rejects_modified_expired_or_revoked_preview(api, monkeypatch, fault):
    client, app, _, identity = api
    body, clock = setup(api, monkeypatch, "tenders")
    prepared = client.post(ROOT + "/preview", json=body, headers=_csrf(client))
    assert prepared.status_code == 200, prepared.text
    value = {"confirmation_token": prepared.json()["confirmation_token"]}
    if fault == "token":
        value["confirmation_token"] = value["confirmation_token"][:-6] + "AAAAAA"
    elif fault == "expired":
        clock.current += timedelta(minutes=6)
    elif fault == "extra_body":
        value["user_id"] = identity["user"]["id"]
    else:
        with app.state.service.db.session() as session:
            user = session.get(User, identity["user"]["id"])
            if fault == "password":
                user.password_hash += "different-password-binding"
            else:
                for row in session.scalars(select(UserSession).where(UserSession.user_id == user.id)):
                    row.revoked_at = clock.current
            session.commit()
    denied = client.post(ROOT + "/download", json=value, headers=_csrf(client))
    assert denied.status_code in {401, 409, 422}, denied.text
    assert "canonical_json" not in denied.json()
    assert denied.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("phase", ("lock_wait", "assembly"))
def test_elapsed_preview_expiry_is_rechecked_inside_download(api, monkeypatch, phase):
    client, _, _, _ = api
    body, clock = setup(api, monkeypatch, "tenders")
    prepared = client.post(ROOT + "/preview", json=body, headers=_csrf(client))
    assert prepared.status_code == 200, prepared.text
    operation = "lock_scope" if phase == "lock_wait" else "packet"
    original = getattr(exports, operation)

    def elapsed(*args, **kwargs):
        value = original(*args, **kwargs)
        clock.current += timedelta(minutes=6)
        return value

    monkeypatch.setattr(exports, operation, elapsed)
    response = client.post(ROOT + "/download",
        json={"confirmation_token": prepared.json()["confirmation_token"]}, headers=_csrf(client))
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "monitoring_export_preview_expired"
    assert "canonical_json" not in response.json()
    assert response.headers["cache-control"] == "no-store"


def test_authenticated_viewer_can_download_owned_evidence_over_real_http(api, monkeypatch):
    client, app, _, identity = api
    body, _ = setup(api, monkeypatch, "tenders")
    with app.state.service.db.session(include_all_organizations=True) as session:
        membership = session.scalar(select(OrganizationMembership).where(
            OrganizationMembership.user_id == identity["user"]["id"],
            OrganizationMembership.organization_id == identity["organization"]["id"]))
        membership.role = "viewer"
        session.commit()
    assert client.get("/api/auth/session").json()["role"] == "viewer"
    prepared = client.post(ROOT + "/preview", json=body, headers=_csrf(client))
    assert prepared.status_code == 200, prepared.text
    response = client.post(ROOT + "/download",
        json={"confirmation_token": prepared.json()["confirmation_token"]}, headers=_csrf(client))
    assert response.status_code == 200, response.text
    verify_file(response.json())


@pytest.mark.parametrize("domain", ("tenders", "ip", "auctions"))
def test_business_decisions_belong_to_selected_source_and_shared_access_is_rechecked(db, monkeypatch, domain):
    from test_business_item_work import act
    from test_business_monitor_sharing import configure
    from test_monitoring_evidence_versions import advance, fixture

    from helvetic_lens.monitoring_centre import MODELS

    data = fixture(db, monkeypatch, domain)
    monitor, item, now, _ = data
    settings = Settings(_env_file=None, tender_watch_enabled=True, trademark_watch_enabled=True, auction_watch_enabled=True)
    act(db, domain, data, assigned=None, decision={"tenders": "no_bid", "ip": "counsel", "auctions": "inspect"}[domain],
        comment="Private comment for the original source only")
    owner = login(db, "owner", now)
    record = Record(domain, monitor, item)
    original = exports.prepare(db, settings, owner, record, now=now, locale="en-CH")
    first = verify_file(exports.download(db, settings, owner, original["confirmation_token"], now=now))
    assert first["payload"]["private_decisions"]["native_reviews"]
    assert first["payload"]["private_decisions"]["work_history"][0]["comment"] == "Private comment for the original source only"
    advance(db, domain, data)
    later = now + timedelta(seconds=2)
    with db.session() as session:
        latest = packet(session, settings, "owner", record, now=later, prepared_at=later, locale="en-CH")
        selected = packet(session, settings, "owner", record, now=later, prepared_at=later, locale="en-CH",
            revision_id=original["manifest"]["selection"]["revision_id"])
        version = session.get(MODELS[domain], monitor).version
    assert verify_file(latest)["payload"]["private_decisions"]["work_history"] == []
    assert verify_file(selected)["payload"]["private_decisions"] == first["payload"]["private_decisions"]
    # Even a historical preview is invalidated by changed current context; it
    # cannot silently substitute the newer source or stale overview flags.
    with pytest.raises(DomainError):
        exports.download(db, settings, owner, original["confirmation_token"], now=later)
    shared = configure(db, domain, monitor, version=version, now=later)
    viewer = login(db, "viewer", later)
    prepared = exports.prepare(db, settings, viewer, record, now=later, locale="fr-CH")
    verify_file(exports.download(db, settings, viewer, prepared["confirmation_token"], now=later))
    configure(db, domain, monitor, version=shared["monitor_version"], scope="private", responsible=None, now=later)
    with pytest.raises(DomainError):
        exports.download(db, settings, viewer, prepared["confirmation_token"], now=later)


@pytest.mark.parametrize("domain", ("ip", "auctions"))
def test_download_rechecks_export_rights_after_preview(db, monkeypatch, domain):
    from test_monitoring_evidence_versions import fixture

    from helvetic_lens import auction_sources, trademark_sources

    data = fixture(db, monkeypatch, domain)
    monitor, item, now, permission = data
    actor = login(db, "owner", now)
    settings = Settings(_env_file=None, trademark_watch_enabled=True, auction_watch_enabled=True)
    prepared = exports.prepare(db, settings, actor, Record(domain, monitor, item), now=now, locale="it-CH")
    with db.session() as session:
        (trademark_sources if domain == "ip" else auction_sources).revoke_permission(session, permission, now=now)
        session.commit()
    with pytest.raises(DomainError):
        exports.download(db, settings, actor, prepared["confirmation_token"], now=now)
