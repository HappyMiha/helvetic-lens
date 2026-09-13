"""Shared acquisition, immutable cache identity and crash/revocation behavior."""

from datetime import timedelta
from functools import partial
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import event, select
from test_commute_contracts import NOW
from test_commute_jobs import capture, source_grants
from test_commute_static_acquisition import DATASET, RESOURCE, URL, response
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture
from test_transport_feed import feed
from test_transport_static import archive
from test_transport_static import tables as _tables_fixture

from helvetic_lens import commute_static_acquisition as acquisition
from helvetic_lens import commute_static_collector as collector
from helvetic_lens.commute_models import CommuteSourcePermission, CommuteStaticArchive, CommuteStaticPoll
from helvetic_lens.commute_sources import utc
from helvetic_lens.config import Settings

db, template, tables = _database_fixture, _template_fixture, _tables_fixture
CATALOG = {"success": True, "result": {"id": DATASET, "resources": [{"id": RESOURCE, "format": "ZIP", "url": URL}]}}


def fresh(database, grants, second=0, *, mismatch=False):
    for index, permission in enumerate(grants.values()):
        message = feed(second=second)
        if mismatch and index == 1:
            message.header.feed_version = "20260910"
        capture(database, permission, message, second=second)


def setup(database, tmp_path):
    grants = source_grants(database)
    fresh(database, grants)
    settings = Settings(_env_file=None, data_dir=tmp_path / "data", commute_watch_enabled=True,
        commute_source_enabled=True, commute_static_enabled=True, commute_static_dataset_id=DATASET)
    return grants, settings


def denied(*args, **kwargs):
    pytest.fail("No provider request is allowed")


def idle(database, settings, second=0):
    return collector.collect(database, settings, catalog=denied, downloader=denied,
                             now=lambda: NOW + timedelta(seconds=second))


def collect(database, settings, payload, *, second=0, handler=None):
    calls, connections = [], set()

    def checkout(connection, record, proxy):
        connections.add(id(connection))

    def checkin(connection, record):
        connections.discard(id(connection))

    def route(request):
        # A 200 MB source transfer must not hold permission/poll database locks.
        assert not connections
        assert not {"authorization", "cookie", "x-workspace"} & set(request.headers)
        calls.append(str(request.url))
        if handler is not None:
            custom = handler(request)
            if custom is not None:
                return custom
        if str(request.url) == URL:
            return response(payload)
        assert str(request.url) == acquisition.CATALOG_ORIGIN + "/api/3/action/package_show?id=" + DATASET
        import json
        return response(json.dumps(CATALOG).encode())

    event.listen(database.engine, "checkout", checkout)
    event.listen(database.engine, "checkin", checkin)
    try:
        with httpx.Client(transport=httpx.MockTransport(route), auth=("secret", "never-forward"),
                          headers={"X-Workspace": "private", "Cookie": "private"}) as client:
            result = collector.collect(database, settings,
                catalog=partial(acquisition.fetch_catalog, client=client),
                downloader=partial(acquisition.acquire_archive, client=client),
                now=lambda: NOW + timedelta(seconds=second))
            return result, calls
    finally:
        event.remove(database.engine, "checkout", checkout)
        event.remove(database.engine, "checkin", checkin)


def test_default_off_and_missing_configuration_never_request_sources(db, tmp_path):
    _, settings = setup(db, tmp_path)
    assert not Settings(_env_file=None).commute_static_enabled
    for flag in ("commute_watch_enabled", "commute_source_enabled", "commute_static_enabled"):
        assert idle(db, settings.model_copy(update={flag: False})) == {"state": "disabled"}
    assert idle(db, settings.model_copy(update={"commute_static_dataset_id": ""})) == {"state": "unconfigured"}
    with db.session() as session:
        assert session.get(CommuteStaticPoll, "static") is None


@pytest.mark.parametrize("condition", ["stale", "revoked", "mismatch"])
def test_both_current_permitted_sources_must_prove_one_version(db, tmp_path, condition):
    grants, settings = setup(db, tmp_path)
    second = 181 if condition == "stale" else 1
    if condition == "revoked":
        with db.session() as session:
            session.get(CommuteSourcePermission, next(iter(grants.values()))).revoked_at = NOW
            session.commit()
    elif condition == "mismatch":
        fresh(db, grants, second, mismatch=True)
    assert idle(db, settings, second) == {"state": "source_unavailable"}
    with db.session() as session:
        assert session.get(CommuteStaticPoll, "static") is None


def test_shared_download_binds_version_once_and_reuses_verified_cache(db, tmp_path, tables):
    grants, settings = setup(db, tmp_path)
    payload = archive(tmp_path, tables).read_bytes()
    result, calls = collect(db, settings, payload)
    assert result == {"state": "acquired", "version": "20260909"} and len(calls) == 2
    with db.organization_context("org-b"):
        assert idle(db, settings, 1) == {"state": "deferred"}
        fresh(db, grants, 900)
        assert idle(db, settings, 900) == {"state": "cached", "version": "20260909"}
    with db.session() as session:
        row = session.scalars(select(CommuteStaticArchive)).one()
        assert row.resource_url == URL and row.dataset_id == DATASET and row.present
        assert utc(row.acquired_at) == NOW and utc(row.last_used_at) == NOW + timedelta(seconds=900)
        assert (settings.storage_path / "commute-static" / (row.sha256 + ".zip")).read_bytes() == payload
        poll = session.get(CommuteStaticPoll, "static")
        assert poll.lease_token is None and poll.failures == 0


@pytest.mark.parametrize("corruption", ["different_size", "same_size"])
def test_corrupt_cache_is_preserved_and_suspends_automatic_download(db, tmp_path, tables, corruption):
    grants, settings = setup(db, tmp_path)
    payload = archive(tmp_path, tables).read_bytes()
    collect(db, settings, payload)
    path = next((settings.storage_path / "commute-static").glob("*.zip"))
    damaged = b"bad" if corruption == "different_size" else b"x" * len(payload)
    path.write_bytes(damaged)
    fresh(db, grants, 900)
    assert idle(db, settings, 900) == {"state": "unavailable", "code": "static_cache_conflict"}
    assert path.read_bytes() == damaged
    with db.session() as session:
        assert session.get(CommuteStaticPoll, "static").blocked
        assert session.scalars(select(CommuteStaticArchive)).one().size == len(payload)


def test_missing_file_is_refetched_only_with_original_resource_and_hash(db, tmp_path, tables):
    grants, settings = setup(db, tmp_path)
    payload = archive(tmp_path, tables).read_bytes()
    collect(db, settings, payload)
    path = next((settings.storage_path / "commute-static").glob("*.zip"))
    path.unlink()
    fresh(db, grants, 900)
    tables["routes.txt"][1][2] = "S99"
    result, _ = collect(db, settings, archive(tmp_path, tables).read_bytes(), second=900)
    assert result == {"state": "unavailable", "code": "static_checksum_conflict"}
    assert not path.exists()
    with db.session() as session:
        assert session.scalars(select(CommuteStaticArchive)).one().size == len(payload)


def test_changed_dataset_cannot_relabel_an_existing_version(db, tmp_path, tables):
    grants, settings = setup(db, tmp_path)
    collect(db, settings, archive(tmp_path, tables).read_bytes())
    fresh(db, grants, 900)
    assert idle(db, settings.model_copy(update={"commute_static_dataset_id": str(uuid4())}), 900)["code"] == "static_dataset_conflict"


def test_revocation_during_download_prevents_archive_publication(db, tmp_path, tables):
    grants, settings = setup(db, tmp_path)

    def revoke(request):
        if str(request.url) == URL:
            with db.session() as session:
                session.get(CommuteSourcePermission, next(iter(grants.values()))).revoked_at = NOW
                session.commit()

    result, _ = collect(db, settings, archive(tmp_path, tables).read_bytes(), handler=revoke)
    assert result["code"] == "commute_source_permission_unavailable"
    assert list((settings.storage_path / "commute-static").iterdir()) == []
    with db.session() as session:
        assert session.scalars(select(CommuteStaticArchive)).all() == []
        assert session.get(CommuteStaticPoll, "static").lease_token is None


def test_late_worker_cannot_publish_or_release_replacement_lease(db, tmp_path, tables):
    _, settings = setup(db, tmp_path)
    replacement = str(uuid4())

    def steal(request):
        if str(request.url) == URL:
            with db.session() as session:
                session.get(CommuteStaticPoll, "static").lease_token = replacement
                session.commit()

    result, _ = collect(db, settings, archive(tmp_path, tables).read_bytes(), handler=steal)
    assert result["code"] == "static_lease_lost"
    with db.session() as session:
        assert session.get(CommuteStaticPoll, "static").lease_token == replacement
        assert session.scalars(select(CommuteStaticArchive)).all() == []


def test_crashed_worker_lease_expires_without_duplicate_claims(db, tmp_path):
    grants, settings = setup(db, tmp_path)
    first = collector.claim(db, grants, NOW)
    assert first and collector.claim(db, grants, NOW + timedelta(seconds=900)) is None
    replacement = collector.claim(db, grants, NOW + timedelta(seconds=1800))
    assert replacement and replacement != first
    with db.session() as session:
        with pytest.raises(acquisition.AcquisitionError, match="lease_lost"):
            collector.owned(session, settings, first, grants, NOW + timedelta(seconds=1800))


@pytest.mark.parametrize("status,code,blocked", [(403, "static_catalog_access_denied", True),
                                              (429, "static_catalog_throttled", False)])
def test_denial_and_retry_after_are_durable_and_sanitized(db, tmp_path, status, code, blocked):
    grants, settings = setup(db, tmp_path)
    result, calls = collect(db, settings, b"", handler=lambda request: response(b"secret error", status, **{"Retry-After": "7200"}))
    assert result == {"state": "unavailable", "code": code} and len(calls) == 1
    fresh(db, grants, 3600)
    assert idle(db, settings, 3600) == {"state": "deferred"}
    with db.session() as session:
        row = session.get(CommuteStaticPoll, "static")
        assert row.blocked is blocked and row.last_code == code and row.lease_token is None
        if not blocked:
            assert utc(row.next_attempt_at) == NOW + timedelta(seconds=7200)


def test_cache_quota_reclaims_only_old_owned_archives_and_keeps_bindings(db, tmp_path, tables, monkeypatch):
    _, settings = setup(db, tmp_path)
    payload = archive(tmp_path, tables).read_bytes()
    monkeypatch.setattr(collector, "MAX_ARCHIVE", len(payload))
    settings = settings.model_copy(update={"commute_static_cache_max_bytes": len(payload) + 10})
    folder = settings.storage_path / "commute-static"
    folder.mkdir(parents=True)
    (folder / "operator-note").write_bytes(b"keep")
    old = folder / ("a" * 64 + ".zip")
    old.write_bytes(payload)
    with db.session() as session:
        session.add(CommuteStaticArchive(version="20260908", dataset_id=DATASET, resource_id=RESOURCE,
            resource_url=URL, sha256="a" * 64, size=len(payload), valid_from=NOW.date(), valid_to=NOW.date(),
            acquired_at=NOW - timedelta(days=8), last_used_at=NOW - timedelta(days=8), present=True))
        session.commit()
    result, _ = collect(db, settings, payload)
    assert result["state"] == "acquired" and not old.exists()
    assert (folder / "operator-note").read_bytes() == b"keep"
    with db.session() as session:
        assert not session.get(CommuteStaticArchive, "20260908").present
        assert len(session.scalars(select(CommuteStaticArchive)).all()) == 2


def test_unknown_cache_files_are_never_deleted_to_make_space(db, tmp_path, monkeypatch):
    _, settings = setup(db, tmp_path)
    monkeypatch.setattr(collector, "MAX_ARCHIVE", 10)
    settings = settings.model_copy(update={"commute_static_cache_max_bytes": 12})
    folder = settings.storage_path / "commute-static"
    folder.mkdir(parents=True)
    path = folder / "unknown.part"
    path.write_bytes(b"keep-me")
    assert idle(db, settings)["code"] == "static_cache_full"
    assert path.read_bytes() == b"keep-me"


def test_binding_count_limit_stops_before_network(db, tmp_path, monkeypatch):
    _, settings = setup(db, tmp_path)
    monkeypatch.setattr(collector, "MAX_VERSIONS", 0)
    assert idle(db, settings)["code"] == "static_version_limit"
