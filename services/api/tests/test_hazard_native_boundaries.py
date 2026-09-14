"""First-install native geometry with synthetic bytes; no source coverage grant."""

import hashlib
from datetime import timedelta

import httpx
import pytest
from test_hazard_boundary_store import PLACE, archive

from helvetic_lens import hazard_boundary_store as store
from helvetic_lens import hazard_native_boundaries as native
from helvetic_lens.hazard_boundaries import BoundaryError

NOW = native.REVIEWED_AT + timedelta(hours=1)


@pytest.fixture
def payload(tmp_path, monkeypatch):
    path, _ = archive(tmp_path)
    raw = path.read_bytes()
    monkeypatch.setattr(native, "ARCHIVE_BYTES", len(raw))
    monkeypatch.setattr(native, "ARCHIVE_SHA256", hashlib.sha256(raw).hexdigest())
    return raw


def response(raw, *, mime="application/zip", **kwargs):
    return httpx.Response(200, stream=httpx.ByteStream(raw), headers={"Content-Type": mime}, **kwargs)


@pytest.mark.parametrize("mime", ["application/zip", "application/x.geopackage+zip"])
def test_first_install_hash_checks_native_geometry_then_never_reinstalls_removed_selection(tmp_path, payload, mime):
    calls = []

    def handle(request):
        calls.append(request)
        return response(payload, mime=mime)

    target = tmp_path / "data"
    with httpx.Client(transport=httpx.MockTransport(handle), auth=("private", "secret"), cookies={"session": "private"},
                      params={"private": "value"}) as client:
        result = native.ensure(target, now=NOW, client=client)
        assert result["state"] == "installed" and result["cantons"] == 26
        assert store.BoundaryStore(target).verify_location(PLACE, now=NOW)["state"] == "verified"
        (target / "hazard-boundaries/current.json").unlink()
        assert native.ensure(target, now=NOW, client=client) == {"state": "existing_catalogue"}
    assert len(calls) == 1 and str(calls[0].url) == native.URL
    assert "authorization" not in calls[0].headers and "cookie" not in calls[0].headers
    assert not (target / ".hazard-boundary-download.lock").exists()
    assert not list(target.glob(".hazard-boundary-*.zip"))


@pytest.mark.parametrize("failure", ["redirect", "html", "size", "hash", "deadline", "cancelled"])
def test_failed_or_cancelled_download_cannot_publish_catalogue_and_releases_owned_files(tmp_path, payload, failure):
    def handle(request):
        if failure == "redirect":
            return httpx.Response(302, headers={"Location": "https://example.invalid/elsewhere"})
        if failure == "html":
            return httpx.Response(200, headers={"Content-Type": "text/html"})
        return response(payload + b"extra" if failure == "size" else b"X" * len(payload) if failure == "hash" else payload)

    ticks = iter((0, 0, 61))
    checks = []

    def checkpoint():
        checks.append(True)
        if failure == "cancelled" and len(checks) >= 3:
            raise RuntimeError("Owner cancelled the pending work")

    target = tmp_path / "data"
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(RuntimeError if failure == "cancelled" else BoundaryError):
            native.ensure(target, now=NOW, client=client, checkpoint=checkpoint,
                          monotonic=lambda: next(ticks) if failure == "deadline" else 0)
    assert not (target / "hazard-boundaries").exists()
    assert not (target / ".hazard-boundary-download.lock").exists()
    assert not list(target.glob(".hazard-boundary-*.zip"))


def test_existing_lock_expired_review_and_operator_catalogue_prevent_download(tmp_path):
    calls = []

    def handle(request):
        calls.append(request)
        pytest.fail("Unexpected network request")

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(BoundaryError):
            native.ensure(tmp_path, now=NOW.replace(year=2027), client=client)
        lock = tmp_path / ".hazard-boundary-download.lock"
        lock.write_text("other worker")
        assert native.ensure(tmp_path, now=NOW, client=client)["state"] == "installation_in_progress"
        assert lock.read_text() == "other worker"
        (tmp_path / "hazard-boundaries").mkdir()
        assert native.ensure(tmp_path, now=NOW, client=client)["state"] == "existing_catalogue"
    assert calls == []


def test_operator_install_during_decode_cannot_be_adopted_or_overwritten(tmp_path, payload, monkeypatch):
    target = tmp_path / "data"
    original = store.load_geopackage

    def decode(*args, **kwargs):
        result = original(*args, **kwargs)
        root = target / "hazard-boundaries"
        root.mkdir()
        (root / "operator-marker").write_text("Do not reactivate")
        return result

    monkeypatch.setattr(store, "load_geopackage", decode)
    with httpx.Client(transport=httpx.MockTransport(lambda request: response(payload))) as client:
        with pytest.raises(FileExistsError):
            native.ensure(target, now=NOW, client=client)
    assert not (target / "hazard-boundaries/current.json").exists()
    assert (target / "hazard-boundaries/operator-marker").read_text() == "Do not reactivate"
