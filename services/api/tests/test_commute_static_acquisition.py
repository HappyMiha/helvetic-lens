"""Archive retrieval must preserve exact source identity and leave no partial file."""

from dataclasses import replace
from hashlib import sha256

import httpx
import pytest
from test_transport_static import archive
from test_transport_static import tables as _tables_fixture

from helvetic_lens import commute_static_acquisition as static
from helvetic_lens.commute_acquisition import AcquisitionError

tables = _tables_fixture
DATASET = "3d2c18f9-9ef1-463f-a249-5c67604efd74"
RESOURCE = "fe5f2e22-156a-4375-9373-031ecdd7e72c"
URL = f"{static.CATALOG_ORIGIN}/dataset/{DATASET}/resource/{RESOURCE}/download/gtfs_fp2026_20260909.zip"
RECORD = static.StaticResource(DATASET, RESOURCE, "20260909", URL)


def response(content, status=200, **headers):
    return httpx.Response(status, headers=headers, stream=httpx.ByteStream(content))


def run(tmp_path, handler, **kwargs):
    with httpx.Client(transport=httpx.MockTransport(handler), auth=("must", "not-leak"),
                      headers={"X-Workspace": "private", "Authorization": "secret", "Cookie": "session=secret"}) as client:
        return static.acquire_archive(RECORD, tmp_path / "cache", client=client, **kwargs)


def test_streamed_archive_publishes_by_hash_and_retains_existing_copy(tmp_path, tables):
    payload = archive(tmp_path, tables).read_bytes()
    requests = []

    def handler(request):
        requests.append(request)
        assert str(request.url) == URL and request.method == "GET"
        assert not {"authorization", "cookie", "x-workspace"} & set(request.headers)
        return response(payload, **{"Content-Length": str(len(payload))})

    artifact = run(tmp_path, handler, expected_sha256=sha256(payload).hexdigest())
    assert artifact.size == len(payload) and artifact.path.read_bytes() == payload
    assert artifact.path.name == sha256(payload).hexdigest() + ".zip"
    assert run(tmp_path, handler) == artifact
    assert list((tmp_path / "cache").iterdir()) == [artifact.path]
    assert len(requests) == 2


def test_only_reviewed_redirects_and_no_credentials_are_forwarded(tmp_path, tables):
    payload = archive(tmp_path, tables).read_bytes()
    calls = []

    def handler(request):
        calls.append(request)
        assert not {"authorization", "cookie", "x-workspace"} & set(request.headers)
        if len(calls) == 1:
            return response(b"", 302, Location="https://objects.example.invalid/archive?signature=synthetic",
                            **{"Set-Cookie": "tracking=secret"})
        return response(payload)

    with pytest.raises(AcquisitionError, match="static_redirect_unreviewed"):
        run(tmp_path, handler)
    assert len(calls) == 1 and list((tmp_path / "cache").iterdir()) == []
    calls.clear()
    artifact = run(tmp_path, handler, redirect_origins=("https://objects.example.invalid",))
    assert len(calls) == 2 and artifact.resource.url == URL
    assert "signature" not in repr(artifact)


@pytest.mark.parametrize("status,code", [(401, "access_denied"), (403, "access_denied"),
                                       (429, "throttled"), (503, "throttled"), (500, "http_error")])
def test_http_failures_are_bounded_and_sanitized(tmp_path, status, code):
    with pytest.raises(AcquisitionError, match="static_" + code) as error:
        run(tmp_path, lambda _: response(b"private upstream error", status, **{"Retry-After": "600"}))
    assert "private" not in str(error.value)
    if code == "throttled":
        assert error.value.retry_after == 600
    assert list((tmp_path / "cache").iterdir()) == []


@pytest.mark.parametrize("headers,code", [({"Content-Length": "9999999999999"}, "size_limit"),
    ({"Content-Length": "1"}, "body_incomplete"), ({"Content-Encoding": "gzip"}, "encoding_unsupported")])
def test_wrong_size_or_transport_encoding_does_not_publish(tmp_path, tables, headers, code):
    with pytest.raises(AcquisitionError, match="static_" + code):
        run(tmp_path, lambda _: response(archive(tmp_path, tables).read_bytes(), **headers))
    assert list((tmp_path / "cache").iterdir()) == []


def test_actual_wire_size_bound_applies_without_length(tmp_path, tables, monkeypatch):
    payload = archive(tmp_path, tables).read_bytes()
    monkeypatch.setattr(static, "MAX_ARCHIVE", len(payload) - 1)
    with pytest.raises(AcquisitionError, match="size_limit"):
        run(tmp_path, lambda _: response(payload))
    assert list((tmp_path / "cache").iterdir()) == []


@pytest.mark.parametrize("change,code", [("version", "archive_invalid"), ("html", "archive_invalid"),
                                      ("hash", "checksum_conflict")])
def test_payload_must_prove_selected_version_and_checksum(tmp_path, tables, change, code):
    if change == "version":
        tables["feed_info.txt"][1][0] = "20260910"
    payload = b"<html>Login</html>" if change == "html" else archive(tmp_path, tables).read_bytes()
    options = {"expected_sha256": "0" * 64} if change == "hash" else {}
    with pytest.raises(AcquisitionError, match="static_" + code):
        run(tmp_path, lambda _: response(payload), **options)
    assert list((tmp_path / "cache").iterdir()) == []


def test_guard_revocation_discards_staging_before_publication(tmp_path, tables):
    calls = 0

    def guard():
        nonlocal calls
        calls += 1
        if calls == 3:
            raise AcquisitionError("source_permission_unavailable")

    with pytest.raises(AcquisitionError, match="permission"):
        run(tmp_path, lambda _: response(archive(tmp_path, tables).read_bytes()), guard=guard)
    assert list((tmp_path / "cache").iterdir()) == []


def test_existing_corrupt_cache_entry_is_not_replaced(tmp_path, tables):
    payload = archive(tmp_path, tables).read_bytes()
    folder = tmp_path / "cache"
    folder.mkdir()
    destination = folder / (sha256(payload).hexdigest() + ".zip")
    destination.write_bytes(b"must preserve")
    with pytest.raises(AcquisitionError):
        run(tmp_path, lambda _: response(payload))
    assert destination.read_bytes() == b"must preserve"
    assert list(folder.iterdir()) == [destination]


def test_catalog_selects_exact_version_and_rejects_ambiguity():
    row = {"id": RESOURCE, "format": "ZIP", "name": "Display name is not identity", "url": URL}
    data = {"success": True, "result": {"id": DATASET, "resources": [row]}}
    assert static.select_resource(data, dataset_id=DATASET, version="20260909") == RECORD
    with pytest.raises(AcquisitionError, match="unavailable"):
        static.select_resource(data, dataset_id=DATASET, version="20260910")
    second = "00000000-0000-4000-8000-000000000001"
    data["result"]["resources"].append({**row, "id": second, "url": URL.replace(RESOURCE, second)})
    with pytest.raises(AcquisitionError, match="ambiguous"):
        static.select_resource(data, dataset_id=DATASET, version="20260909")


@pytest.mark.parametrize("url", [URL + "?token=secret", URL.replace("https:", "http:"),
    URL.replace("data.opentransportdata.swiss", "localhost"), URL.replace("20260909.zip", "20260910.zip")])
def test_resource_url_cannot_redirect_selection_to_arbitrary_endpoint(url):
    with pytest.raises((ValueError, AcquisitionError)):
        replace(RECORD, url=url)


def test_total_time_guard_and_network_failure_leave_no_partial_artifact(tmp_path, tables):
    times = iter((0, 0, static.TOTAL_SECONDS + 1))
    with pytest.raises(AcquisitionError, match="static_timeout"):
        run(tmp_path, lambda _: response(archive(tmp_path, tables).read_bytes()), monotonic=lambda: next(times))
    assert list((tmp_path / "cache").iterdir()) == []

    def failed(request):
        raise httpx.ConnectError("signed-secret-url-must-not-escape", request=request)

    with pytest.raises(AcquisitionError) as error:
        run(tmp_path, failed)
    assert str(error.value) == "static_network_error"
    assert list((tmp_path / "cache").iterdir()) == []


def test_invalid_catalog_identity_or_resource_bound_cannot_select_a_download(monkeypatch):
    row = {"id": RESOURCE, "format": "ZIP", "url": URL}
    payload = {"success": True, "result": {"id": DATASET, "resources": [row]}}
    with pytest.raises(AcquisitionError, match="identity_invalid"):
        static.select_resource(payload, dataset_id="wrong", version="20260909")
    monkeypatch.setattr(static, "MAX_RESOURCES", 0)
    with pytest.raises(AcquisitionError, match="size_limit"):
        static.select_resource(payload, dataset_id=DATASET, version="20260909")


@pytest.mark.parametrize("body,headers,code", [(b"{}", {"Content-Length": "999999999"}, "size_limit"),
    (b"{}", {"Content-Length": "3"}, "body_incomplete"),
    (b"{}", {"Content-Encoding": "gzip"}, "encoding_unsupported"),
    (b"<html>Login required</html>", {}, "invalid"),
    (b"[" * 2000 + b"]" * 2000, {}, "invalid")])
def test_catalog_transport_and_parser_failures_are_sanitized(body, headers, code):
    with httpx.Client(transport=httpx.MockTransport(lambda request: response(body, **headers))) as client:
        with pytest.raises(AcquisitionError, match="static_catalog_" + code):
            static.fetch_catalog(DATASET, client=client)


def test_catalog_actual_size_deadline_and_redirect_do_not_produce_a_resource(monkeypatch):
    monkeypatch.setattr(static, "MAX_CATALOG_BYTES", 5)
    with httpx.Client(transport=httpx.MockTransport(lambda request: response(b'{"oversized":true}'))) as client:
        with pytest.raises(AcquisitionError, match="static_catalog_size_limit"):
            static.fetch_catalog(DATASET, client=client)
    with httpx.Client(transport=httpx.MockTransport(lambda request: response(b"{}"))) as client:
        moments = iter((0, 31))
        with pytest.raises(AcquisitionError, match="static_catalog_timeout"):
            static.fetch_catalog(DATASET, client=client, monotonic=lambda: next(moments))
    calls = []

    def redirected(request):
        calls.append(request)
        return response(b"", 302, Location="https://example.invalid/login?token=never-log")

    with httpx.Client(transport=httpx.MockTransport(redirected)) as client:
        with pytest.raises(AcquisitionError) as error:
            static.fetch_catalog(DATASET, client=client)
    assert len(calls) == 1 and error.value.blocked
    assert str(error.value) == "static_catalog_access_denied"


def test_catalog_network_error_never_exposes_provider_message():
    def failed(request):
        raise httpx.ReadError("sensitive-upstream-message", request=request)

    with httpx.Client(transport=httpx.MockTransport(failed)) as client:
        with pytest.raises(AcquisitionError) as error:
            static.fetch_catalog(DATASET, client=client)
    assert str(error.value) == "static_catalog_network_error"
