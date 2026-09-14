import gzip
import xml.etree.ElementTree as ET
from datetime import timedelta
from functools import partial
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select
from test_road_feed import D2, NOW, SOAP, STAMP, feed, record
from test_road_sources import grant
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens import road_acquisition as acquisition
from helvetic_lens import road_sources as sources
from helvetic_lens.config import Settings
from helvetic_lens.road_models import RoadSourceEvidence, RoadSourceHead, RoadSourcePoll

db, template = _database_fixture, _template_fixture
KEY = "synthetic-road-source-key"


def setup(database, **policy):
    permission_id = grant(database, **policy)
    return permission_id, Settings(_env_file=None, road_watch_enabled=True, road_source_enabled=True,
        road_source_key=KEY, road_source_permission_id=permission_id)


def response(status=200, content=None, headers=None):
    return httpx.Response(status, headers=headers, stream=httpx.ByteStream(feed().encode() if content is None else content))


def run(database, settings, handler, *, second=0):
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        return acquisition.collect(database, settings, downloader=partial(acquisition.download, client=client),
                                   now=lambda: NOW + timedelta(seconds=second))


def no_network(_request):
    pytest.fail("No source request is permitted")


def test_flags_key_selected_permission_and_current_rights_all_gate_network(db):
    settings = Settings(_env_file=None)
    assert run(object(), settings, no_network) == {"state": "disabled"}
    settings.road_watch_enabled = settings.road_source_enabled = True
    assert run(object(), settings, no_network) == {"state": "unconfigured"}
    settings.road_source_key = Settings(_env_file=None, road_source_key=KEY).road_source_key
    settings.road_source_permission_id = str(uuid4())
    assert run(db, settings, no_network)["state"] == "source_permission_unavailable"
    permission_id, settings = setup(db)
    with db.session() as session:
        sources.revoke_permission(session, permission_id, now=NOW)
        session.commit()
    assert run(db, settings, no_network)["state"] == "source_permission_unavailable"


def test_http_request_is_fixed_soap_and_excludes_injected_client_identity():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.method == "POST" and str(request.url) == acquisition.ENDPOINT
        assert request.headers["authorization"] == "Bearer " + KEY
        assert request.headers["soapaction"] == acquisition.SOAP_ACTION
        assert request.headers["if-modified-since"] == "Sun, 13 Sep 2026 09:59:00 GMT"
        assert "cookie" not in request.headers and "x-private-company" not in request.headers
        assert request.url.query == b""
        root = ET.fromstring(request.content)
        model = root.find(f"{{{SOAP}}}Body/{{{D2}}}d2LogicalModel")
        assert model.get("modelBaseVersion") == "2"
        assert model.find(f"{{{D2}}}exchange/{{{D2}}}supplierIdentification/{{{D2}}}nationalIdentifier").text == "FEDRO"
        assert model.find(f"{{{D2}}}exchange/{{{D2}}}subscription/{{{D2}}}target/{{{D2}}}address").text is None
        assert b"2025-05-01T08:00:00.00+01:00" in request.content
        return response()

    with httpx.Client(transport=httpx.MockTransport(handler), cookies={"private": "sentinel"},
                      headers={"X-Private-Company": "sentinel"}, params={"private_route": "sentinel"},
                      auth=("private", "password")) as client:
        assert acquisition.download(KEY, since=NOW - timedelta(minutes=1), client=client, now=lambda: NOW) == feed().encode()
    assert len(calls) == 1


def test_one_shared_stream_claim_prevents_duplicate_network_and_recovers_as_delta(db):
    permission_id, settings = setup(db)
    seen = []

    def initial(request):
        seen.append(request)
        assert "if-modified-since" not in request.headers
        assert run(db, settings, no_network)["state"] == "deferred"
        return response()

    assert run(db, settings, initial)["state"] == "accepted"
    assert run(db, settings, no_network, second=59)["state"] == "deferred"

    def delta(request):
        seen.append(request)
        assert request.headers["if-modified-since"] == "Sun, 13 Sep 2026 09:59:50 GMT"
        return response(content=feed(situations="").replace(STAMP, "2026-09-13T10:01:00Z").encode())

    assert run(db, settings, delta, second=60)["state"] == "accepted"
    with db.session() as session:
        state = sources.read_state(session, permission_id, now=NOW + timedelta(minutes=1))
        assert state.situations[0].present and state.situations[0].seen_at == NOW
        assert session.scalar(select(func.count()).select_from(RoadSourceEvidence)) == 2
    assert len(seen) == 2


def test_delta_cursor_uses_earlier_provider_clock_to_avoid_skipping_updates(db):
    _, settings = setup(db)
    behind = feed().replace(f"<publicationTime>{STAMP}</publicationTime>",
                           "<publicationTime>2026-09-13T09:59:30Z</publicationTime>")
    assert run(db, settings, lambda _: response(content=behind.encode()))["state"] == "accepted"

    def handler(request):
        assert request.headers["if-modified-since"] == "Sun, 13 Sep 2026 09:59:20 GMT"
        return response(content=feed(situations="").replace(STAMP, "2026-09-13T10:01:00Z").encode())

    assert run(db, settings, handler, second=60)["state"] == "accepted"


@pytest.mark.parametrize("second", [301, 86400])
def test_gap_or_daily_boundary_requests_full_and_never_invents_reopening(db, second):
    permission_id, settings = setup(db, derived_retention_seconds=2 * 86400)
    assert run(db, settings, lambda _: response())["state"] == "accepted"

    def handler(request):
        assert "if-modified-since" not in request.headers
        stamp = (NOW + timedelta(seconds=second)).isoformat()
        return response(content=feed(situations="").replace(STAMP, stamp).encode())

    assert run(db, settings, handler, second=second)["state"] == "accepted"
    with db.session() as session:
        state = sources.read_state(session, permission_id, now=NOW + timedelta(seconds=second))
        assert not state.situations[0].present and not state.situations[0].situation.cancelled


@pytest.mark.parametrize("change", ["revoke", "disable", "generation", "lease"])
def test_mid_transfer_state_change_cannot_publish_or_release_another_worker(db, change):
    permission_id, settings = setup(db)
    replacement_token = str(uuid4())

    def handler(_request):
        if change == "disable":
            settings.road_source_enabled = False
        else:
            with db.session() as session:
                if change == "revoke":
                    sources.revoke_permission(session, permission_id, now=NOW)
                elif change == "generation":
                    session.get(RoadSourceHead, sources.SOURCE).generation += 1
                else:
                    session.get(RoadSourcePoll, sources.SOURCE).lease_token = replacement_token
                session.commit()
        return response()

    assert run(db, settings, handler)["state"] == "unavailable"
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(RoadSourceEvidence)) == 0
        if change == "lease":
            assert session.get(RoadSourcePoll, sources.SOURCE).lease_token == replacement_token


def test_expired_lease_reclaimed_and_old_guard_cannot_publish(db):
    permission_id, _ = setup(db)
    old = acquisition.claim(db, permission_id, now=NOW)
    assert acquisition.claim(db, permission_id, now=NOW + timedelta(seconds=60)) is None
    new = acquisition.claim(db, permission_id, now=NOW + timedelta(seconds=181))
    assert new.token != old.token
    with db.session() as session:
        with pytest.raises(acquisition.RoadAcquisitionError, match="road_source_lease_lost"):
            acquisition._owned(session, old, NOW + timedelta(seconds=181))


@pytest.mark.parametrize(("status", "headers", "code", "blocked"), [
    (401, {}, "road_credentials_rejected", True),
    (403, {}, "road_credentials_rejected", True),
    (302, {"Location": "https://outside.invalid/private"}, "road_response_contract_unreviewed", True),
    (304, {}, "road_response_contract_unreviewed", True),
    (429, {"Retry-After": "600"}, "road_source_throttled", False),
    (503, {"Retry-After": "90000"}, "road_long_retry_after", True),
    (500, {}, "road_http_error", False),
])
def test_provider_errors_are_sanitized_and_cooldown_or_block_is_durable(db, status, headers, code, blocked):
    _, settings = setup(db)
    result = run(db, settings, lambda _: response(status, b"PRIVATE_PROVIDER_BODY", headers))
    assert result == {"state": "unavailable", "code": code}
    assert KEY not in repr(result) and "PRIVATE_PROVIDER_BODY" not in repr(result)
    with db.session() as session:
        poll = session.get(RoadSourcePoll, sources.SOURCE)
        assert poll.blocked == blocked and poll.force_full and poll.lease_token is None
        if status == 429:
            assert sources._utc(poll.next_request_at) >= NOW + timedelta(seconds=600)
    assert run(db, settings, no_network, second=60)["state"] == "deferred"


def test_new_reviewed_selected_grant_recovers_credential_denial_after_cooldown(db):
    _, settings = setup(db)
    run(db, settings, lambda _: response(403))
    new = grant(db, expected_generation=1)
    settings.road_source_permission_id = new
    assert run(db, settings, no_network, second=60)["state"] == "deferred"
    assert run(db, settings, lambda _: response(content=feed().replace(STAMP, "2026-09-13T10:02:00Z").encode()),
               second=120)["state"] == "accepted"


def test_failed_payload_preserves_previous_closure_and_retries_with_full_snapshot(db):
    permission_id, settings = setup(db)
    run(db, settings, lambda _: response())
    assert run(db, settings, lambda _: response(content=b"<html>Login</html>"), second=60)["code"] == "road_payload_invalid"
    with db.session() as session:
        assert sources.read_state(session, permission_id, now=NOW + timedelta(minutes=1)).situations[0].present

    def handler(request):
        assert "if-modified-since" not in request.headers
        return response(content=feed(record(cancelled=True)).replace(STAMP, "2026-09-13T10:03:00Z").encode())

    assert run(db, settings, handler, second=180)["state"] == "accepted"


@pytest.mark.parametrize("case", ["wire", "expanded", "incomplete", "unsupported", "gzip_truncated", "gzip_trailing"])
def test_transfer_bounds_and_compression_fail_without_returning_partial_xml(monkeypatch, case):
    headers, body = {}, b"x" * 20
    if case == "wire":
        monkeypatch.setattr(acquisition, "MAX_BYTES", 10)
    elif case == "expanded":
        monkeypatch.setattr(acquisition, "MAX_BYTES", 100)
        body, headers = gzip.compress(b"x" * 200), {"Content-Encoding": "gzip"}
    elif case == "incomplete":
        headers = {"Content-Length": "21"}
    elif case == "unsupported":
        headers = {"Content-Encoding": "br"}
    else:
        body, headers = gzip.compress(b"test"), {"Content-Encoding": "gzip"}
        body = body[:-2] if case == "gzip_truncated" else body + b"trailing"
    with httpx.Client(transport=httpx.MockTransport(lambda _: response(content=body, headers=headers))) as client:
        with pytest.raises(acquisition.RoadAcquisitionError):
            acquisition.download(KEY, client=client, now=lambda: NOW)


def test_valid_compression_and_total_time_guard():
    body = gzip.compress(feed().encode())
    with httpx.Client(transport=httpx.MockTransport(lambda _: response(content=body, headers={"Content-Encoding": "gzip"}))) as client:
        assert acquisition.download(KEY, client=client) == feed().encode()
        ticks = iter((0, 46, 47))
        with pytest.raises(acquisition.RoadAcquisitionError, match="road_transfer_timeout"):
            acquisition.download(KEY, client=client, monotonic=lambda: next(ticks))


def test_retention_cleanup_is_independent_of_source_flags_and_does_not_repeat_reset(db):
    permission_id, settings = setup(db, raw_retention_seconds=10, derived_retention_seconds=30)
    run(db, settings, lambda _: response())
    settings.road_source_enabled = False
    assert acquisition.cleanup(db, now=lambda: NOW + timedelta(seconds=31)) == {"state": "retention_checked"}
    with db.session() as session:
        generation = session.get(RoadSourceHead, sources.SOURCE).generation
        assert session.scalar(select(func.count()).select_from(RoadSourceEvidence)) == 0
        sources.revoke_permission(session, permission_id, now=NOW + timedelta(seconds=32))
        session.commit()
    acquisition.cleanup(db, now=lambda: NOW + timedelta(seconds=33))
    with db.session() as session:
        assert session.get(RoadSourceHead, sources.SOURCE).generation == generation


@pytest.mark.parametrize("change", ["lease", "expiry", "configuration", "disable"])
def test_expiry_or_configuration_change_during_storage_rolls_back_before_commit(db, monkeypatch, change):
    _, settings = setup(db, valid_until=NOW + timedelta(seconds=30) if change == "expiry" else NOW + timedelta(days=1))
    current = [NOW]
    original = acquisition.accept_snapshot

    def delayed(*args, **kwargs):
        result = original(*args, **kwargs)
        if change in {"lease", "expiry"}:
            current[0] = NOW + timedelta(seconds=181 if change == "lease" else 31)
        elif change == "configuration":
            settings.road_source_permission_id = str(uuid4())
        else:
            settings.road_source_enabled = False
        return result

    monkeypatch.setattr(acquisition, "accept_snapshot", delayed)
    result = acquisition.collect(db, settings, downloader=lambda *_a, **_kw: feed().encode(), now=lambda: current[0])
    assert result["state"] == "unavailable"
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(RoadSourceEvidence)) == 0
        assert session.get(RoadSourceHead, sources.SOURCE).generation == 1


def test_scheduler_runs_cleanup_with_sources_disabled_and_disposes_database(db, monkeypatch):
    from helvetic_lens import celery_app as runtime

    _, settings = setup(db, raw_retention_seconds=10, derived_retention_seconds=30)
    run(db, settings, lambda _: response())
    settings.road_source_enabled = False
    monkeypatch.setattr(runtime, "settings", settings)
    opened, disposed = [], []
    dispose = db.engine.dispose

    def database(_settings):
        opened.append(True)
        return db

    def close():
        disposed.append(True)
        dispose()

    cleanup = acquisition.cleanup
    monkeypatch.setattr(runtime, "Database", database)
    monkeypatch.setattr(db.engine, "dispose", close)
    monkeypatch.setattr(acquisition, "cleanup", lambda database: cleanup(database, now=lambda: NOW + timedelta(seconds=31)))
    # Read persisted connector overrides before deciding whether collection is
    # disabled; an environment flag alone no longer establishes that decision.
    assert runtime.collect_road_source.run() == {"state": "disabled"}
    assert opened == disposed == [True]
    assert runtime.cleanup_road_source.run() == {"state": "retention_checked"}
    assert opened == disposed == [True, True]
    assert runtime.celery_app.conf.beat_schedule["cleanup-road-source"]["schedule"] == 60.0
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(RoadSourceEvidence)) == 0
