from datetime import timedelta
from functools import partial

import httpx
import pytest
from test_commute_contracts import NOW
from test_commute_jobs import source_grants
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture
from test_transport_feed import trip_feed

from helvetic_lens import commute_acquisition as acquisition
from helvetic_lens.commute_models import CommuteFeedState, CommuteSourcePermission, CommuteSourcePoll
from helvetic_lens.commute_sources import read_feed, record_permission
from helvetic_lens.config import Settings
from helvetic_lens.transport_feed import TRIPS

db, template = _database_fixture, _template_fixture
KEY = "synthetic-test-key"


def response(status=200, content=None, headers=None):
    return httpx.Response(status, headers=headers, stream=httpx.ByteStream(
        content if content is not None else trip_feed().SerializeToString()))


def setup(database):
    permissions = source_grants(database)
    settings = Settings(_env_file=None, commute_watch_enabled=True, commute_source_enabled=True,
        commute_gtfs_rt_key=KEY, commute_gtfs_rt_permission_id=permissions[TRIPS])
    return permissions[TRIPS], settings


def run(database, settings, handler, *, second=0, now=None):
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        return acquisition.collect(database, settings, TRIPS,
            downloader=partial(acquisition.download, client=client),
            now=now or (lambda: NOW + timedelta(seconds=second)))


def fail_request(request):
    pytest.fail("The source must not be requested")


def test_network_requires_flags_credentials_and_current_source_permission(db):
    permission, settings = setup(db)
    assert run(db, settings.model_copy(update={"commute_source_enabled": False}), fail_request)["state"] == "disabled"
    assert run(db, Settings(_env_file=None, commute_watch_enabled=True, commute_source_enabled=True), fail_request)["state"] == "unconfigured"
    with db.session() as session:
        session.get(CommuteSourcePermission, permission).revoked_at = NOW
        session.commit()
    assert run(db, settings, fail_request)["state"] == "source_permission_unavailable"
    with db.session() as session:
        assert session.get(CommuteSourcePoll, TRIPS) is None
        assert session.get(CommuteFeedState, TRIPS) is None


def test_shared_poll_and_replay_do_not_refresh_source_age_or_send_private_routes(db):
    _, settings = setup(db)
    requests = []

    def handler(request):
        requests.append(request)
        assert str(request.url) == acquisition.ENDPOINTS[TRIPS]
        assert request.headers["Authorization"] == "Bearer " + KEY
        assert request.headers["User-Agent"] == "HelveticLens-Monitoring/2"
        assert "cookie" not in request.headers and not request.content
        return response()

    assert run(db, settings, handler) == {"state": "accepted"}
    # Another tenant and another worker share the same feed/cooldown row.
    with db.organization_context("org-b"):
        assert run(db, settings, fail_request, second=59) == {"state": "deferred"}
        assert run(db, settings, handler, second=60) == {"state": "replay"}
    assert len(requests) == 2
    with db.session() as session:
        row, _, snapshot = read_feed(session, TRIPS, now=NOW + timedelta(seconds=60))
        assert row.generation == 1 and acquisition.utc(row.received_at) == NOW
        assert snapshot.observed_at == NOW


def test_redirect_without_explicit_review_never_receives_credentials():
    requests = []

    def handler(request):
        requests.append(request)
        return response(302, headers={"Location": "https://unreviewed.example.test/secret"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(acquisition.AcquisitionError, match="source_redirect_unreviewed"):
            acquisition.download(TRIPS, KEY, client=client)
    assert len(requests) == 1


def test_reviewed_redirect_is_bounded_and_never_receives_api_key_or_cookies():
    requests = []
    destination = "https://fixture-storage.example.test"

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return response(302, headers={"Location": destination + "/feed?signature=fixture",
                "Set-Cookie": "source_session=fixture; Path=/"})
        assert "Authorization" not in request.headers and "cookie" not in request.headers
        assert "referer" not in request.headers
        return response()

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        payload = acquisition.download(TRIPS, KEY, redirect_origins=(destination,), client=client)
    assert payload == trip_feed().SerializeToString() and len(requests) == 2


@pytest.mark.parametrize("destination", ["http://api.opentransportdata.swiss/feed",
    "https://api.opentransportdata.swiss@evil.example.test/feed",
    "https://api.opentransportdata.swiss:444/feed", "https://api.opentransportdata.swiss/feed#part",
    "https://api.opentransportdata.swiss/\\evil", "https://api.opentransportdata.swiss/"])
def test_redirect_configuration_accepts_only_canonical_https_origins(destination):
    with httpx.Client(transport=httpx.MockTransport(fail_request)) as client:
        with pytest.raises(acquisition.AcquisitionError):
            acquisition.download(TRIPS, KEY, redirect_origins=(destination,), client=client)


def test_redirect_loop_stops_before_repeating_a_request():
    calls = []

    def handler(request):
        calls.append(request)
        return response(302, headers={"Location": str(request.url)})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(acquisition.AcquisitionError):
            acquisition.download(TRIPS, KEY, client=client)
    assert len(calls) == 1


@pytest.mark.parametrize("headers", [{"Content-Length": "33554433"}, {"Content-Length": "-1"},
    {"Content-Encoding": "br"}])
def test_oversize_or_unsupported_compression_is_rejected_before_reading_body(headers):
    class Unreadable(httpx.SyncByteStream):
        def __iter__(self):
            pytest.fail("Body must not be consumed")
            yield b""

    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, headers=headers, stream=Unreadable()))) as client:
        with pytest.raises(acquisition.AcquisitionError):
            acquisition.download(TRIPS, KEY, client=client)


def test_chunked_body_limit_and_total_deadline(monkeypatch):
    monkeypatch.setattr(acquisition, "MAX_BYTES", 10)
    with httpx.Client(transport=httpx.MockTransport(lambda request: response(content=b"x" * 11))) as client:
        with pytest.raises(acquisition.AcquisitionError, match="source_size_limit"):
            acquisition.download(TRIPS, KEY, client=client)
    moments = iter((0, 0, 50))
    with httpx.Client(transport=httpx.MockTransport(lambda request: response(content=b"a"))) as client:
        with pytest.raises(acquisition.AcquisitionError, match="source_timeout"):
            acquisition.download(TRIPS, KEY, client=client, monotonic=lambda: next(moments))


def test_bad_feed_and_network_failure_retain_last_good_snapshot_and_back_off(db):
    _, settings = setup(db)
    assert run(db, settings, lambda request: response())["state"] == "accepted"
    assert run(db, settings, lambda request: response(content=b"invalid"), second=60)["code"] == "source_binary_invalid"
    assert run(db, settings, fail_request, second=179)["state"] == "deferred"

    def disconnected(request):
        raise httpx.ReadError("Do not persist " + KEY, request=request)

    assert run(db, settings, disconnected, second=180)["code"] == "source_network_error"
    with db.session() as session:
        row = session.get(CommuteSourcePoll, TRIPS)
        assert acquisition.utc(row.next_request_at) == NOW + timedelta(seconds=420)
        assert KEY not in str(row.__dict__)
        assert session.get(CommuteFeedState, TRIPS).generation == 1


def test_retry_after_is_shared_and_long_retry_suspends_instead_of_truncating(db):
    _, settings = setup(db)
    assert run(db, settings, lambda request: response(429, headers={"Retry-After": "600"}))["code"] == "source_throttled"
    assert run(db, settings, fail_request, second=599)["state"] == "deferred"
    assert run(db, settings, lambda request: response(503, headers={"Retry-After": "90000"}), second=600)["code"] == "source_long_retry_after"
    assert run(db, settings, fail_request, second=100000)["state"] == "deferred"
    from email.utils import format_datetime
    assert acquisition.retry_delay(format_datetime(NOW + timedelta(seconds=500)), NOW) >= 500
    assert acquisition.retry_delay("bad date", NOW) == 0


def test_authentication_failure_blocks_automatic_retry_until_new_reviewed_permission(db):
    _, settings = setup(db)
    assert run(db, settings, lambda request: response(401))["code"] == "source_credentials_rejected"
    assert run(db, settings, fail_request, second=3600)["state"] == "deferred"
    with db.session() as session:
        permission = record_permission(session, source=TRIPS, policy_reference="fixture renewed review",
            accepted_at=NOW, valid_until=NOW + timedelta(days=1), max_age_seconds=180)
        session.commit()
    renewed = settings.model_copy(update={"commute_gtfs_rt_permission_id": permission})
    assert run(db, renewed, lambda request: response(content=trip_feed(second=3600).SerializeToString()), second=3600)["state"] == "accepted"


def test_permission_revoked_during_request_prevents_capture_and_redirect(db):
    permission, settings = setup(db)
    requests = []

    def handler(request):
        requests.append(request)
        with db.session() as session:
            session.get(CommuteSourcePermission, permission).revoked_at = NOW
            session.commit()
        return response(302, headers={"Location": acquisition.API_ORIGIN + "/cached"})

    assert run(db, settings, handler)["code"] == "commute_source_permission_unavailable"
    assert len(requests) == 1
    with db.session() as session:
        assert session.get(CommuteFeedState, TRIPS) is None


def test_expired_worker_cannot_store_or_release_replacement_lease(db):
    permission, settings = setup(db)
    current = [NOW]
    replacement = []

    def handler(request):
        # Claim a new worker after the first lease expires while the first
        # response remains in flight. Its stale completion must be harmless.
        current[0] = NOW + timedelta(seconds=121)
        replacement.append(acquisition.claim(db, TRIPS, permission, now=current[0]))
        return response()

    assert run(db, settings, handler, now=lambda: current[0])["code"] == "source_lease_lost"
    with db.session() as session:
        row = session.get(CommuteSourcePoll, TRIPS)
        assert replacement[0] and row.lease_token == replacement[0]
        assert row.failures == 0
        assert session.get(CommuteFeedState, TRIPS) is None


def test_duplicate_inflight_claim_never_reaches_http(db):
    permission, settings = setup(db)
    token = acquisition.claim(db, TRIPS, permission, now=NOW)
    assert token
    assert acquisition.claim(db, TRIPS, permission, now=NOW + timedelta(seconds=60)) is None
    assert run(db, settings, fail_request, second=60)["state"] == "deferred"


@pytest.mark.parametrize("encoding", ["gzip", "deflate"])
def test_compressed_binary_is_decoded_with_independent_wire_and_expansion_limits(encoding, monkeypatch):
    import gzip
    import zlib

    compress = gzip.compress if encoding == "gzip" else zlib.compress
    binary = trip_feed().SerializeToString()
    content = compress(binary)
    with httpx.Client(transport=httpx.MockTransport(lambda request: response(content=content,
        headers={"Content-Encoding": encoding, "Content-Length": str(len(content))}))) as client:
        assert acquisition.download(TRIPS, KEY, client=client) == binary
    monkeypatch.setattr(acquisition, "MAX_BYTES", 1000)
    bomb = compress(b"x" * 100000)
    assert len(bomb) < 1000
    with httpx.Client(transport=httpx.MockTransport(lambda request: response(content=bomb,
        headers={"Content-Encoding": encoding}))) as client:
        with pytest.raises(acquisition.AcquisitionError, match="source_size_limit"):
            acquisition.download(TRIPS, KEY, client=client)


@pytest.mark.parametrize("mode", ["truncated", "trailing", "broken", "length"])
def test_incomplete_or_concatenated_response_is_not_a_valid_feed(mode):
    import gzip

    binary = gzip.compress(trip_feed().SerializeToString())
    content = {"truncated": binary[:-4], "trailing": binary + b"other", "broken": b"garbage", "length": binary}[mode]
    headers = {"Content-Encoding": "gzip"}
    if mode == "length":
        headers["Content-Length"] = str(len(content) + 1)
    with httpx.Client(transport=httpx.MockTransport(lambda request: response(content=content, headers=headers))) as client:
        with pytest.raises(acquisition.AcquisitionError):
            acquisition.download(TRIPS, KEY, client=client)


def test_collected_feed_drives_existing_private_worker_and_evidence(db):
    from sqlalchemy import select
    from test_commute_jobs import scenario

    from helvetic_lens import commute_jobs
    from helvetic_lens.commute_models import CommuteDevelopment, CommuteEventVersion

    monitor, permissions, settings = scenario(db, delay=0)
    settings = settings.model_copy(update={"commute_source_enabled": True,
        "commute_gtfs_rt_key": Settings(_env_file=None, commute_gtfs_rt_key=KEY).commute_gtfs_rt_key,
        "commute_gtfs_rt_permission_id": permissions[TRIPS]})
    assert run(db, settings, lambda request: response(content=trip_feed(cancelled=True, second=1).SerializeToString()),
        second=1)["state"] == "accepted"
    result = commute_jobs.refresh(db, settings, monitor_id=monitor["id"], version=monitor["version"],
        now=NOW + timedelta(seconds=1))
    assert result["signals"] == 1
    with db.session() as session:
        development = session.scalars(select(CommuteDevelopment)).one()
        assert next(iter(development.current["states"].values()))["condition"] == "cancelled"
        assert session.scalars(select(CommuteEventVersion)).one().evidence["feed_sha256"] == session.get(CommuteFeedState, TRIPS).content_hash
