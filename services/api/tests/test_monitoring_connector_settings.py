"""Real HTTP, encrypted persistence, hot adoption, revision and probe boundaries."""

import json
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select, update
from test_auth import _csrf
from test_tender_api import api as api

from helvetic_lens import monitoring_connector_probe as probe
from helvetic_lens import monitoring_connector_settings as config
from helvetic_lens.config import DomainError
from helvetic_lens.models import User
from helvetic_lens.monitoring_connector_models import MonitoringConnectorConfiguration as Configuration

ROOT = "/api/admin/monitoring-connectors"


def admin(api):
    client, app, settings, identity = api
    with app.state.service.db.session(include_all_organizations=True) as session:
        session.execute(update(User).where(User.id == identity["user"]["id"]).values(platform_admin=True))
        session.commit()
    return client, app.state.service, settings


def test_private_admin_boundary_and_nine_visible_categories(api):
    client, app, _, _ = api
    response = client.get("/api/monitoring-settings")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert {row["id"] for row in response.json()["items"]} == set(config.FIELDS)
    assert response.json()["can_configure_connectors"] is False
    assert "credentials" not in response.text
    for domain in config.FIELDS:
        assert client.get(f"{ROOT}/{domain}").status_code == 403
        assert client.patch(f"{ROOT}/{domain}", json={"revision": 0}, headers=_csrf(client)).status_code == 403
        assert client.post(f"{ROOT}/{domain}/check", json={"revision": 0}, headers=_csrf(client)).status_code == 403
    admin(api)
    for domain in config.FIELDS:
        assert client.get(f"{ROOT}/{domain}").status_code == 200
    assert client.get(f"{ROOT}/customs").status_code == 404
    assert client.patch(f"{ROOT}/ip", json={"revision": 0}).status_code == 403


def test_encryption_replace_clear_conflict_and_request_worker_adoption(api):
    client, service, base = admin(api)
    before = base.ipi_password.get_secret_value()
    body = {"revision": 0, "values": {"ipi_source_enabled": True},
        "secrets": {"ipi_username": "connector-check@example.test", "ipi_password": "test-only-private-password"}}
    response = client.patch(f"{ROOT}/ip", json=body, headers=_csrf(client))
    assert response.status_code == 200, response.text
    assert "test-only-private-password" not in response.text and "connector-check@" not in response.text
    assert response.json()["revision"] == 1
    with service.db.session() as session:
        row = session.get(Configuration, "ip")
        assert row.encrypted_credentials.startswith("enc:v1:")
        assert "test-only-private-password" not in row.encrypted_credentials
        assert row.values == {"ipi_source_enabled": True}
    with service.organization_runtime():
        assert service.settings.ipi_password.get_secret_value() == "test-only-private-password"
        native = config.RequestSettings(service, base)
        assert native.ipi_username.get_secret_value() == "connector-check@example.test"
        assert native.database_url == base.database_url
    worker = config.load(service.db, base)
    assert worker.ipi_password.get_secret_value() == "test-only-private-password"
    assert base.ipi_password.get_secret_value() == before
    assert client.patch(f"{ROOT}/ip", json=body, headers=_csrf(client)).status_code == 409
    response = client.patch(f"{ROOT}/ip", json={"revision": 1, "secrets": {"ipi_password": ""}}, headers=_csrf(client))
    assert response.status_code == 200
    assert config.load(service.db, base).ipi_password.get_secret_value() == ""
    with pytest.raises(DomainError, match="changed"):
        config.assert_current(service.db, worker, "ip")
    assert next(field for field in response.json()["fields"] if field["id"] == "ipi_password")["configured"] is False


def test_invalid_values_never_persist_or_echo_secrets(api):
    client, service, _ = admin(api)
    invalid = [
        {"secrets": {"website_password": "do-not-echo"}},
        {"values": {"ipi_source_enabled": "true"}},
        {"values": {"ipi_password": "do-not-echo"}},
        {"secrets": {"ipi_password": "do-not-echo\n"}},
        {"values": {"ipi_source_permission_id": "00000000-0000-0000-0000-000000000000"}},
        {"secrets": {"ipi_username": "x" * 321}},
        {"website": "https://untrusted.test"},
    ]
    for value in invalid:
        result = client.patch(f"{ROOT}/ip", json={"revision": 0, **value}, headers=_csrf(client))
        assert result.status_code == 422, result.text
        assert "do-not-echo" not in result.text
    with service.db.session() as session:
        assert session.scalar(select(Configuration.revision).where(Configuration.domain == "ip")) == 0


def test_access_check_saved_revision_rate_limit_and_stale_result(api, monkeypatch):
    client, service, _ = admin(api)
    calls = []
    def check(domain, settings):
        calls.append(domain)
        return {"checked_at": datetime.now(UTC).isoformat(), "coverage_verified": False,
            "channels": [{"id": "public", "state": "http_accessible"}]}
    monkeypatch.setattr(probe, "check", check)
    result = client.post(f"{ROOT}/air/check", json={"revision": 0}, headers=_csrf(client))
    assert result.status_code == 200 and result.json()["coverage_verified"] is False
    assert client.post(f"{ROOT}/air/check", json={"revision": 0}, headers=_csrf(client)).status_code == 429
    assert calls == ["air"]
    assert client.get(f"{ROOT}/air").json()["check"] == result.json()
    def racing_check(domain, settings):
        with service.db.session() as session:
            config.save(session, service.environment_settings, service.credential_cipher, "tenders", 0,
                {"simap_public_source_enabled": True}, {})
            session.commit()
        return check(domain, settings)
    monkeypatch.setattr(probe, "check", racing_check)
    assert client.post(f"{ROOT}/tenders/check", json={"revision": 0}, headers=_csrf(client)).status_code == 409
    assert client.get(f"{ROOT}/tenders").json()["check"] is None


def test_corrupted_credentials_disable_source_but_allow_admin_repair(api):
    client, service, base = admin(api)
    with service.db.session() as session:
        session.execute(update(Configuration).where(Configuration.domain == "ip").values(encrypted_credentials="not-encrypted"))
        session.commit()
    state = client.get(f"{ROOT}/ip")
    assert state.status_code == 200 and state.json()["credential_error"] is True
    resolved = config.load(service.db, base)
    assert not resolved.ipi_source_enabled and resolved.ipi_password.get_secret_value() == ""
    assert client.patch(f"{ROOT}/ip", json={"revision": 0, "secrets": {"ipi_password": ""}}, headers=_csrf(client)).status_code == 422
    repaired = client.patch(f"{ROOT}/ip", json={"revision": 0, "secrets": {"ipi_password": "", "ipi_username": ""}}, headers=_csrf(client))
    assert repaired.status_code == 200 and repaired.json()["credential_error"] is False


@pytest.mark.parametrize("status,kind,body,expected", [(200,"application/json",b'{"access_token":"never-return-me","token_type":"Bearer"}',"authenticated"),
    (200,"text/html",b"login","unexpected_response"), (401,"application/json",b"secret-body","access_denied"),
    (302,"text/html",b"","redirect_not_followed"), (429,"text/plain",b"","rate_limited")])
def test_fixed_origin_probe_redacts_credentials_and_response(api, status, kind, body, expected):
    _, _, base, _ = api
    from pydantic import SecretStr
    settings = base.model_copy(update={"ipi_username": SecretStr("test-user"), "ipi_password": SecretStr("test-password")})
    requests = []
    def respond(request):
        requests.append(request)
        assert str(request.url) == probe.TOKEN_ENDPOINT
        assert b"username=test-user" in request.content and b"password=test-password" in request.content
        assert "cookie" not in request.headers
        return httpx.Response(status, headers={"content-type": kind, "location": "https://untrusted.test"}, content=body)
    with httpx.Client(transport=httpx.MockTransport(respond), cookies={"private": "no"}, headers={"X-Private": "no"}) as client:
        result = probe.check("ip", settings, client=client)
    assert len(requests) == 1 and result["channels"][0]["state"] == expected
    assert all(value not in json.dumps(result) for value in ("never-return-me", "test-password", "secret-body"))
    assert result["coverage_verified"] is False


@pytest.mark.parametrize("domain", list(config.FIELDS))
def test_all_native_probe_endpoints_and_distinct_keys(api, domain):
    from pydantic import SecretStr
    _, _, base, _ = api
    settings = base.model_copy(update={"ipi_username": SecretStr("probe-account"), "ipi_password": SecretStr("probe-password"),
        "commute_gtfs_rt_key": SecretStr("trip-key"), "commute_gtfs_sa_key": SecretStr("alert-key"), "road_source_key": SecretStr("road-key")})
    seen = []
    def respond(request):
        seen.append(request)
        if domain == "commute":
            assert request.headers["authorization"] == "Bearer " + ("trip-key" if request.url.path.endswith("gtfs-rt") else "alert-key")
        elif domain == "traffic":
            assert request.headers["authorization"] == "Bearer road-key"
        else:
            assert "authorization" not in request.headers
        assert request.url.scheme == "https" and "cookie" not in request.headers and "x-private" not in request.headers
        return httpx.Response(403, headers={"content-type": "text/plain"}, content=b"untrusted details")
    with httpx.Client(transport=httpx.MockTransport(respond), headers={"X-Private": "never-forward"}) as client:
        result = probe.check(domain, settings, client=client)
    assert len(seen) == (2 if domain == "commute" else 1)
    assert all(row["state"] == "access_denied" for row in result["channels"])
    assert "untrusted" not in json.dumps(result)


@pytest.mark.parametrize("task,module,function,domain,field", [
    ("collect_ipi_source", "ipi_collector", "collect", "ip", "ipi_source_enabled"),
    ("collect_aste_source", "aste_collector", "collect", "auctions", "aste_source_enabled"),
    ("collect_commute_sources", "commute_acquisition", "collect_due", "commute", "commute_source_enabled"),
    ("collect_road_source", "road_acquisition", "collect", "traffic", "road_source_enabled"),
    ("schedule_road_monitoring", "road_jobs", "enqueue_due", "traffic", "road_source_enabled"),
    ("schedule_tender_monitoring", "tender_jobs", "enqueue_due", "tenders", "simap_public_source_enabled"),
])
def test_actual_periodic_worker_entry_uses_saved_snapshot(api, monkeypatch, task, module, function, domain, field):
    import importlib

    from helvetic_lens import celery_app
    _, service, original = admin(api)
    base = original.model_copy(update={field: False, "trademark_watch_enabled": True, "road_watch_enabled": True})
    with service.db.session() as session:
        config.save(session, service.environment_settings, service.credential_cipher, domain, 0, {field: True}, {})
        session.commit()
    monkeypatch.setattr(celery_app, "settings", base)
    native = importlib.import_module("helvetic_lens." + module)
    if hasattr(native, "readiness"):
        monkeypatch.setattr(native, "readiness", lambda settings: "configured")
    captured = []
    def operation(database, settings):
        assert settings is not base and getattr(settings, field) is True
        captured.append(settings)
        return {"state": "tested"}
    monkeypatch.setattr(native, function, operation)
    result = getattr(celery_app, task)()
    assert (result["refresh"] if task == "schedule_tender_monitoring" else result) == {"state": "tested"}
    assert len(captured) == 1 and getattr(base, field) is False


def test_native_http_source_reader_uses_new_credentials_without_restart(api, monkeypatch):
    from helvetic_lens import ipi_collector
    client, service, base = admin(api)
    base.trademark_watch_enabled = True
    seen = []
    def readiness(settings):
        seen.append(settings.ipi_password.get_secret_value())
        return "permission_required"
    monkeypatch.setattr(ipi_collector, "readiness", readiness)
    response = client.patch(f"{ROOT}/ip", json={"revision": 0, "secrets": {"ipi_password": "new-native-password"}}, headers=_csrf(client))
    assert response.status_code == 200
    result = client.get("/api/trademark-watch/source-status")
    assert result.status_code == 200 and seen == ["new-native-password"]
    assert "new-native-password" not in result.text


def test_existing_named_permission_and_password_rotation_token_invalidation(api):
    import hashlib
    from datetime import timedelta

    from helvetic_lens.ipi_models import IPITokenCache
    from helvetic_lens.trademark_source_models import TrademarkSourcePermission
    client, service, _ = admin(api)
    now = datetime.now(UTC)
    account = hashlib.sha256(b"rotation@example.test").hexdigest()
    with service.db.session() as session:
        session.add(TrademarkSourcePermission(id="reviewed-native", policy={}, policy_hash="a" * 64,
            accepted_at=now - timedelta(days=1), valid_until=now + timedelta(days=1)))
        session.commit()
    value = client.patch(f"{ROOT}/ip", json={"revision": 0, "values": {"ipi_source_permission_id": "reviewed-native"},
        "secrets": {"ipi_username": "rotation@example.test", "ipi_password": "old-password"}}, headers=_csrf(client))
    assert value.status_code == 200
    with service.db.session() as session:
        session.add(IPITokenCache(account_hash=account, encrypted_payload="discard-test-token", next_attempt_at=now))
        session.commit()
    value = client.patch(f"{ROOT}/ip", json={"revision": 1, "secrets": {"ipi_password": "replacement-password"}}, headers=_csrf(client))
    assert value.status_code == 200
    with service.db.session() as session:
        assert session.get(IPITokenCache, account) is None
        assert session.get(TrademarkSourcePermission, "reviewed-native").policy_hash == "a" * 64
