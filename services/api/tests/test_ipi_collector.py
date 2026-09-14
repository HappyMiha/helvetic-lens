"""Bounded HTTP/auth protocol fixtures; no live accounts or source approval."""

import json
from datetime import timedelta
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select
from test_ipi_acquisition import another_record, page, permission
from test_ipi_acquisition import db as _database_fixture
from test_ipi_acquisition import template as _template_fixture
from test_trademark_sources import NOW

from helvetic_lens import ipi_collector as collector
from helvetic_lens import ipi_tokens as tokens
from helvetic_lens.config import Settings
from helvetic_lens.ipi_models import IPIPageEvidence, IPITokenCache, IPITraversal
from helvetic_lens.ipi_protocol import IPIProtocolError, parse_xml
from helvetic_lens.ipi_transport import API_ENDPOINT, TOKEN_ENDPOINT, exchange
from helvetic_lens.trademark_source_models import TrademarkSourcePermission

db, template = _database_fixture, _template_fixture


def settings(db, approved):
    return Settings(_env_file=None, app_environment="test", trademark_watch_enabled=True,
        ipi_source_permission_id=approved, ipi_username="fixture@example.invalid", ipi_password="synthetic-password",
        credential_encryption_key="synthetic-local-encryption-material",
        data_dir=db.engine.url.database + "-data")


def response(status=200, body=b"", **headers):
    return httpx.Response(status, headers=headers, stream=httpx.ByteStream(body))


def token_body(**changes):
    return json.dumps({"access_token": "synthetic-access", "refresh_token": "synthetic-refresh", "expires_in": 720,
        "refresh_expires_in": 360, "token_type": "bearer", **changes}).encode()


def test_collector_uses_official_origins_reuses_encrypted_token_and_resumes_native_pages(db):
    approved = permission(db)
    config, now, requests = settings(db, approved), [NOW], []

    def handle(request):
        requests.append(request)
        assert "cookie" not in request.headers and "x-injected" not in request.headers
        assert not request.url.query
        if str(request.url) == TOKEN_ENDPOINT:
            fields = parse_qs(request.content.decode())
            assert fields["grant_type"] == ["password"] and fields["client_id"] == [tokens.CLIENT_ID]
            assert "authorization" not in request.headers
            return response(body=token_body(), **{"content-type": "application/json"})
        assert str(request.url) == API_ENDPOINT and request.headers["authorization"] == "Bearer synthetic-access"
        uid = parse_xml(request.content).get("uuid")
        first = uid.endswith("-0")
        body = page({"request_uuid": uid}, records=None if first else [another_record()], offset=0 if first else 1,
            total=2, continuation="next-private-token" if first else None)
        return response(body=body, **{"content-type": "application/xml", "x-ipi-success": "true"})

    with httpx.Client(transport=httpx.MockTransport(handle), cookies={"private": "forbidden"},
            headers={"X-Injected": "forbidden"}, auth=("unexpected", "secret")) as client:
        first = collector.collect(db, config, client=client, now=lambda: now[0])
        assert first["state"] == "accepted"
        now[0] += timedelta(seconds=3)
        second = collector.collect(db, config, client=client, now=lambda: now[0])
        assert second["traversal"]["state"] == "completed"
    assert len(requests) == 3
    with db.session() as session:
        cache = session.scalar(select(IPITokenCache))
        assert cache.encrypted_payload.startswith("enc:v1:")
        assert not any(value in cache.encrypted_payload for value in ("synthetic-access", "synthetic-refresh", "synthetic-password"))
        assert session.scalar(select(IPITraversal)).unique_count == 2


def test_refresh_before_refresh_expiry_works_in_another_worker(db):
    config, now, forms = settings(db, permission(db)), [NOW], []
    def handle(request):
        forms.append(parse_qs(request.content.decode()))
        return response(body=token_body(access_token=f"synthetic-access-{len(forms)}"),
            **{"content-type": "application/json"})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert tokens.obtain(db, config, client, guard=lambda: None, now=lambda: now[0]) == "synthetic-access-1"
        now[0] += timedelta(seconds=100)
        assert tokens.obtain(db, config, client, guard=lambda: None, now=lambda: now[0]) == "synthetic-access-1"
        now[0] = NOW + timedelta(seconds=331)
        assert tokens.obtain(db, config, client, guard=lambda: None, now=lambda: now[0]) == "synthetic-access-2"
    assert [value["grant_type"] for value in forms] == [["password"], ["refresh_token"]]
    assert "password" not in forms[-1] and forms[-1]["refresh_token"] == ["synthetic-refresh"]


def test_publisher_retry_after_survives_permission_generation_change(db):
    approved = permission(db)
    config, requests = settings(db, approved), []
    def handle(request):
        requests.append(str(request.url))
        if str(request.url) == TOKEN_ENDPOINT:
            return response(body=token_body(), **{"content-type": "application/json"})
        return response(429, **{"retry-after": "1800"})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert collector.collect(db, config, client=client, now=lambda: NOW)["reason"] == "ipi_http_429"
        config.ipi_source_permission_id = permission(db, generation=1)
        assert collector.collect(db, config, client=client, now=lambda: NOW + timedelta(seconds=10))["state"] == "waiting"
    assert requests == [TOKEN_ENDPOINT, API_ENDPOINT]


@pytest.mark.parametrize("missing", ["credentials", "permission", "revoked", "origin", "retention"])
def test_missing_prerequisites_never_call_identity_or_register_endpoint(db, missing):
    changes = {"raw_retention_seconds": 120} if missing == "retention" else {}
    approved = permission(db, **changes)
    config = settings(db, approved)
    if missing == "credentials":
        config.ipi_password = SecretStr("")
    if missing == "permission":
        config.ipi_source_permission_id = ""
    if missing == "revoked":
        with db.session() as session:
            session.get(TrademarkSourcePermission, approved).revoked_at = NOW
            session.commit()
    if missing == "origin":
        from test_trademark_sources import grant
        config.ipi_source_permission_id = grant(db, generation=1, endpoint=API_ENDPOINT)
    def unexpected(request):
        pytest.fail("Unapproved network request")
    with httpx.Client(transport=httpx.MockTransport(unexpected)) as client:
        result = collector.collect(db, config, client=client, now=lambda: NOW)
    assert result["state"] in {"credentials_required", "permission_required", "unavailable"}
    assert not result["coverage_verified"]


def test_revoked_while_downloading_discards_complete_http_body(db):
    approved = permission(db)
    config = settings(db, approved)
    def handle(request):
        if str(request.url) == TOKEN_ENDPOINT:
            return response(body=token_body(), **{"content-type": "application/json"})
        with db.session() as session:
            session.get(TrademarkSourcePermission, approved).revoked_at = NOW
            session.commit()
        body = page({"request_uuid": parse_xml(request.content).get("uuid")})
        return response(body=body, **{"content-type": "application/xml", "x-ipi-success": "true"})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert collector.collect(db, config, client=client, now=lambda: NOW)["state"] == "unavailable"
    with db.session() as session:
        assert session.scalar(select(IPIPageEvidence)) is None


@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_redirect_never_receives_token_or_password(status):
    seen = []
    def handle(request):
        seen.append(str(request.url))
        return response(status, location="https://other.example.invalid/steal")
    with httpx.Client(transport=httpx.MockTransport(handle), follow_redirects=True) as client:
        with pytest.raises(IPIProtocolError):
            exchange(client, API_ENDPOINT, content=b"<request/>", token="synthetic-secret")
    assert seen == [API_ENDPOINT]


@pytest.mark.parametrize("kind", ["declared_size", "stream_size", "encoding"])
def test_transport_refuses_oversized_or_unexpectedly_compressed_bodies(monkeypatch, kind):
    from helvetic_lens import ipi_transport

    monkeypatch.setattr(ipi_transport, "MAX_BYTES", 16)
    headers = {"content-length": "999999999"} if kind == "declared_size" else {"content-encoding": "gzip"} if kind == "encoding" else {}
    with httpx.Client(transport=httpx.MockTransport(lambda request: response(body=b"x" * 17, **headers))) as client:
        with pytest.raises(IPIProtocolError):
            exchange(client, API_ENDPOINT, content=b"<request/>", token="synthetic-secret")


@pytest.mark.parametrize("body", [
    b'{"access_token":"first","access_token":"second"}',
    token_body(expires_in=True),
    token_body(access_token="unsafe\r\nheader"),
])
def test_malformed_token_response_is_not_cached_or_retried(db, body):
    config = settings(db, permission(db))
    with httpx.Client(transport=httpx.MockTransport(lambda request: response(body=body, **{"content-type": "application/json"}))) as client:
        with pytest.raises(IPIProtocolError, match="ipi_token_response_invalid"):
            tokens.obtain(db, config, client, guard=lambda: None, now=lambda: NOW)
    with db.session() as session:
        assert session.scalar(select(IPITokenCache)).encrypted_payload is None


def test_failed_refresh_is_not_retried_and_tokens_do_not_appear_in_errors(db):
    config, now, count = settings(db, permission(db)), [NOW], [0]
    def handle(request):
        count[0] += 1
        return response(body=token_body(), **{"content-type": "application/json"}) if count[0] == 1 else response(400, b"synthetic-secret-error")
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        tokens.obtain(db, config, client, guard=lambda: None, now=lambda: now[0])
        now[0] += timedelta(seconds=331)
        with pytest.raises(IPIProtocolError, match="ipi_http_400"):
            tokens.obtain(db, config, client, guard=lambda: None, now=lambda: now[0])
        with pytest.raises(IPIProtocolError, match="ipi_account_backoff"):
            tokens.obtain(db, config, client, guard=lambda: None, now=lambda: now[0])
    assert count[0] == 2
    with db.session() as session:
        assert session.scalar(select(IPITokenCache)).encrypted_payload is None


def test_scheduled_cleanup_erases_native_parent_and_expired_tokens_while_section_disabled(db, monkeypatch):
    from helvetic_lens import celery_app as worker
    from helvetic_lens import trademark_sources as source

    approved = permission(db)
    config = settings(db, approved)
    def handle(request):
        if str(request.url) == TOKEN_ENDPOINT:
            return response(body=token_body(), **{"content-type": "application/json"})
        return response(body=page({"request_uuid": parse_xml(request.content).get("uuid")}),
            **{"content-type": "application/xml", "x-ipi-success": "true"})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert collector.collect(db, config, client=client, now=lambda: NOW)["state"] == "accepted"
    monkeypatch.setattr(worker.settings, "trademark_watch_enabled", False)
    monkeypatch.setattr(worker, "Database", lambda config: db)
    original = source.cleanup
    monkeypatch.setattr(source, "cleanup", lambda database: original(database, now=NOW + timedelta(seconds=721)))
    result = worker.cleanup_trademark_source.run()
    assert result["ipi"]["pages"] == result["ipi"]["tokens"] == 1
    with db.session() as session:
        assert session.scalar(select(IPIPageEvidence)).raw_payload is None
        assert session.scalar(select(IPITokenCache)).encrypted_payload is None
