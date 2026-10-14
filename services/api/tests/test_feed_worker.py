"""Native collection checkpoints, complete originals, failure isolation and authority."""
import asyncio
import os
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_auth import _csrf
from test_legal_profiles import signed as signed

from helvetic_lens import (
    decision_search,
    decision_sources,
    feed_intelligence,
    feed_sources,
    feed_worker,
    jobs,
)
from helvetic_lens.db import utcnow
from helvetic_lens.feed_models import Feed, FeedCheck, FeedUpdate
from helvetic_lens.maintenance import cleanup_operational_data
from helvetic_lens.models import Job, User

URL = "https://publisher.example/document"


@pytest.fixture(autouse=True)
def semantic_models(monkeypatch):
    """No paid providers or local model servers in collection integration tests."""
    async def prepare(service, specification):
        return {"contract": feed_intelligence.CONTRACT, "binding": specification["binding"],
            "feed_revision": specification["feed_revision"], "status": "ready",
            "understanding": "Watch changes in applicable public legislation.",
            "relevance_scope": "Include public legislative changes and relevant contrary evidence. Do not include unrelated policy subjects.",
            "concepts": ["legislative reform"], "synonyms": ["Gesetzesänderung"],
            "queries": [{"query": "Changes to applicable public legislation", "language": "en", "purpose": "Track legal changes"}]}

    async def evaluate(configuration, specification, plan, item):
        assert len(item["source_text"]) <= feed_intelligence.GATE_CHARACTERS
        if plan["status"] != "ready":
            return {"verdict": "unavailable", "engine": None, "error": "semantic_context_unavailable"}
        return {"verdict": "relevant", "engine": "laya", "model": "test-local-laya",
            "evaluated_characters": len(item["source_text"]), "confidence": .8}

    async def retrieve(*args, **kwargs):
        return {"status": "complete", "items": [], "next_cursors": None}
    monkeypatch.setattr(feed_intelligence, "prepare", prepare)
    monkeypatch.setattr(feed_intelligence, "evaluate", evaluate)
    monkeypatch.setattr(decision_search, "federated_retrieve", retrieve)


def create(service, identity, sources=None):
    with service.db.session() as session:
        feed = Feed(owner_user_id=identity["user"]["id"], product="loyer", name="Public source watch",
            query="Public legislative changes", sources_json=[URL] if sources is None else sources)
        session.add(feed)
        session.flush()
        job = feed_worker.enqueue_check(session, feed, service.settings, str(uuid4()))
        session.commit()
        return feed.id, job.id


def next_check(service, identifier, key=None):
    with service.db.session() as session:
        job = feed_worker.enqueue_check(session, session.get(Feed, identifier), service.settings, key or str(uuid4()))
        session.commit()
        return job.id


def step(service, identifier):
    return asyncio.run(service.execute_job(identifier, "feed-test"))


def finish(service, identifier):
    # Test guard only: production continuations do not have this delivery cap.
    for _ in range(100):
        result = step(service, identifier)
        if result["state"] in jobs.TERMINAL_STATES:
            return result
    raise AssertionError("Collection failed to make forward progress")


def downloads(monkeypatch, values):
    calls = []

    async def fetch(_client, url, _limit, **kwargs):
        assert kwargs["check_robots"] is True
        calls.append(url)
        value = values[url]
        if isinstance(value, Exception):
            raise value
        media, body = value
        response = decision_sources.Download(200, media, body)
        response.redirect_chain = [url]
        return url, response
    monkeypatch.setattr(decision_sources, "redirect_fetch", fetch)
    return calls


def test_entire_original_is_read_across_deliveries_without_model_or_duplicates(signed, monkeypatch):
    client, service, identity = signed
    body = ("Long original paragraph. " * 2200 + "THE LAST MATERIAL CONCLUSION").encode()
    calls = downloads(monkeypatch, {URL: ("text/plain", body)})
    identifier, job_id = create(service, identity)
    assert next_check(service, identifier) == job_id
    assert step(service, job_id)["state"] == "queued"  # Semantic plan precedes collection.
    assert step(service, job_id)["state"] == "queued"
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(FeedUpdate)) == 0
        saved = session.get(Job, job_id).payload["checkpoint"]["reading"]
        assert saved["cursor"] == {"page": 0, "offset": 24000}
    assert finish(service, job_id)["state"] == "succeeded"
    step(service, job_id)  # Duplicate broker delivery cannot replay extraction.
    with service.db.session() as session:
        update = session.scalar(select(FeedUpdate))
        assert update.snapshot_json["reading_complete"] is True
        assert "".join(p["text"] for p in update.snapshot_json["excerpts"]) == body.decode()
        assert "THE LAST MATERIAL CONCLUSION" in update.source_text
        artifact = update.snapshot_json["retained_document"]["artifact_key"]
        assert (service.environment_settings.storage_path / "artifacts" / artifact).read_bytes() == body
        check = session.scalar(select(FeedCheck))
        assert check.status == "completed" and check.receipts_json["portions"] == 3
    assert calls == [URL] and service.model_client.calls == []
    assert all(row["id"] != job_id for row in client.get("/api/jobs").json())
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    for action in ("retry", "cancel"):
        assert client.post(f"/api/jobs/{job_id}/{action}", headers=_csrf(client)).status_code == 404


def test_one_failed_original_does_not_hide_another_and_retry_uses_exact_saved_bytes(signed, monkeypatch):
    _, service, identity = signed
    other = URL + "/other"
    body = ("A saved original segment. " * 1800 + "END OF ORIGINAL").encode()
    calls = downloads(monkeypatch, {URL: ("text/plain", body), other: ("text/plain", b"Independent retained text.")})
    identifier, job_id = create(service, identity, [URL, other])
    original_read = feed_sources.read
    fail = True

    async def intermittent(service, item, prefix, progress):
        nonlocal fail
        if item["url"] == URL and progress.get("cursor") and fail:
            fail = False
            raise OSError("temporary storage failure")
        return await original_read(service, item, prefix, progress)
    monkeypatch.setattr(feed_sources, "read", intermittent)
    finish(service, job_id)
    with service.db.session() as session:
        assert [row.url for row in session.scalars(select(FeedUpdate))] == [other]
        check = session.scalar(select(FeedCheck).where(FeedCheck.job_id == job_id))
        assert check.status == "partial" and check.receipts_json["retry_reads"][0]["reading"]["cursor"]["offset"] == 24000
    retry = next_check(service, identifier)
    finish(service, retry)
    with service.db.session() as session:
        row = session.scalar(select(FeedUpdate).where(FeedUpdate.url == URL))
        assert row and "END OF ORIGINAL" in row.source_text
        assert "".join(p["text"] for p in row.snapshot_json["excerpts"]) == body.decode()
        assert session.scalar(select(func.count()).select_from(FeedUpdate)) == 2
    assert calls.count(URL) == 1 and calls.count(other) == 2


def test_rss_pages_fetch_originals_and_preserve_invalid_entry_gap(signed, monkeypatch):
    _, service, identity = signed
    rss, second = "https://publisher.example/rss", "https://publisher.example/rss?page=2"
    values = {
        rss: ("application/rss+xml", b'<rss xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
            b'<atom:link rel="next" href="?page=2"/><item><title>One</title><link>/one</link>'
            b'<description>Only a publisher preview</description></item><item><title>Missing link</title></item></channel></rss>'),
        second: ("application/atom+xml", b'<feed xmlns="http://www.w3.org/2005/Atom"><link rel="next" href="/rss"/>'
            b'<entry><title>Two</title><link href="/two"/><summary>Other preview</summary></entry></feed>'),
        "https://publisher.example/one": ("text/plain", b"Full first document ending."),
        "https://publisher.example/two": ("text/plain", b"Full second document ending."),
    }
    calls = downloads(monkeypatch, values)
    _, job_id = create(service, identity, [rss])
    finish(service, job_id)
    with service.db.session() as session:
        rows = list(session.scalars(select(FeedUpdate).order_by(FeedUpdate.sequence)))
        assert [row.source_text for row in rows] == ["Full first document ending.", "Full second document ending."]
        assert rows[0].summary == "Only a publisher preview"
        check = session.scalar(select(FeedCheck))
        assert check.status == "partial"
        assert [c["omitted_records"] for c in check.receipts_json["coverage"] if c.get("kind") == "rss_atom"] == [1, 0]
    assert set(calls) == set(values) and len(calls) == 4


def test_rss_parser_has_no_silent_entry_cap_and_rejects_entity_documents():
    body = ("<rss><channel>" + "".join(f"<item><title>{i}</title><link>https://publisher.example/{i}</link></item>" for i in range(350)) + "</channel></rss>").encode()
    entries, pages, omitted = feed_sources.feed_items(body, URL)
    assert len(entries) == 350 and entries[-1]["url"].endswith("/349") and not pages and omitted == 0
    with pytest.raises(ValueError):
        feed_sources.feed_items(b'<!DOCTYPE x [<!ENTITY ext SYSTEM "file:///etc/passwd">]><rss/>', URL)


def test_scheduler_resumes_crashed_discovery_tail_without_requerying_changed_index(signed, monkeypatch):
    _, service, identity = signed
    downloads(monkeypatch, {URL: ("text/plain", b"First source."), URL + "/tail": ("text/plain", b"Older final source.")})
    discoveries = []

    async def retrieve(*args, **kwargs):
        discoveries.append(kwargs)
        assert len(discoveries) == 1, "A recovered check must finish its saved discovery page first"
        return {"status": "complete", "items": [{"url": url, "title": "Retained lead", "summary": "Preview"}
            for url in (URL, URL + "/tail")], "next_cursors": None}
    monkeypatch.setattr(decision_search, "federated_retrieve", retrieve)
    identifier, job_id = create(service, identity, [])
    step(service, job_id)  # Persist semantic search directions.
    step(service, job_id)  # Save a discovery page before any originals.
    step(service, job_id)  # Retain the first original.
    with service.db.session() as session:
        job = session.get(Job, job_id)
        job.state, job.finished_at, job.error_code = "failed", utcnow(), "attempts_exhausted"
        session.get(Feed, identifier).next_check_at = utcnow() - timedelta(seconds=1)
        session.commit()
    assert feed_worker.enqueue_due(service.db, service.settings)["started"] == 1
    with service.db.session() as session:
        replacement = session.get(Feed, identifier).job_id
        assert replacement != job_id
        assert session.scalar(select(FeedCheck).where(FeedCheck.job_id == job_id)).status == "failed"
        assert session.get(Job, replacement).payload["checkpoint"]["position"] == 1
    finish(service, replacement)
    with service.db.session() as session:
        rows = list(session.scalars(select(FeedUpdate).order_by(FeedUpdate.sequence)))
        assert [row.source_text for row in rows] == ["First source.", "Older final source."]
        assert session.scalar(select(FeedCheck).where(FeedCheck.job_id == replacement)).receipts_json["captured"] == 1
    assert len(discoveries) == 1


def test_catalogue_pagination_and_explicit_source_survive_broad_channel_failure(signed, monkeypatch):
    _, service, identity = signed
    service.settings = service.settings.model_copy(update={"web_search_provider": "searxng"})
    calls = downloads(monkeypatch, {URL: ("text/plain", b"First source."), URL + "/2": ("text/plain", b"Last source.")})
    discovery = []

    async def retrieve(settings, query, index, depth, product, **kwargs):
        discovery.append(kwargs)
        assert kwargs["complete_page"] is True and kwargs["selected_catalogues"] == ["fedlex"]
        assert settings.web_search_provider == "searxng"
        last = kwargs["cursors"] is not None
        return {"status": "partial", "lanes": [{"name": "broad", "status": "unavailable"}],
            "items": [{"url": URL + "/2" if last else URL, "title": "Source", "summary": "Preview"}],
            "next_cursors": None if last else {"fedlex": "next-page"}}
    monkeypatch.setattr(decision_search, "federated_retrieve", retrieve)
    _, job_id = create(service, identity, [URL, "fedlex"])
    finish(service, job_id)
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(FeedUpdate)) == 2
        assert session.scalar(select(FeedCheck)).status == "partial"
    assert len(discovery) == 2 and calls == [URL, URL + "/2"]


@pytest.mark.parametrize("change", ["paused", "revision", "access", "cancelled", "reclaimed", "expired"])
def test_stale_or_unowned_worker_cannot_publish_download(signed, monkeypatch, change):
    _, service, identity = signed
    downloads(monkeypatch, {URL: ("text/plain", b"Uncommitted original.")})
    identifier, job_id = create(service, identity)
    actual = feed_sources.read

    async def changing(service, item, prefix, progress):
        result = await actual(service, item, prefix, progress)
        with service.db.session() as session:
            feed, job = session.get(Feed, identifier), session.get(Job, job_id)
            if change == "paused":
                feed.status = "paused"
            elif change == "revision":
                feed.revision += 1
            elif change == "access":
                session.get(User, identity["user"]["id"]).active = False
            elif change == "cancelled":
                jobs.cancel(session, job.id)
            elif change == "expired":
                job.heartbeat_at = utcnow() - timedelta(seconds=service.settings.job_lease_seconds + 1)
            else:
                # Same worker name, but a different claimed attempt must win.
                job.attempts += 1
                job.leased_at += timedelta(seconds=1)
            session.commit()
        return result
    monkeypatch.setattr(feed_sources, "read", changing)
    step(service, job_id)  # Planning must not bypass the subsequent download fence.
    step(service, job_id)
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(FeedUpdate)) == 0
        assert session.scalar(select(FeedCheck)).status != "completed"
        if change in {"reclaimed", "expired"}:
            assert session.get(Job, job_id).state == "running"


def test_version_history_a_b_a_and_originals_survive_operational_cleanup(signed, monkeypatch):
    _, service, identity = signed
    values = {URL: ("text/plain", b"Version A")}
    downloads(monkeypatch, values)
    identifier, job_id = create(service, identity)
    finish(service, job_id)
    for body in (b"Version A", b"Version B", b"Version A"):
        values[URL] = ("text/plain", body)
        finish(service, next_check(service, identifier))
    artifacts = service.environment_settings.storage_path / "artifacts"
    with service.db.session() as session:
        rows = list(session.scalars(select(FeedUpdate).order_by(FeedUpdate.sequence)))
        assert [row.source_text for row in rows] == ["Version A", "Version B", "Version A"]
        assert [row.sequence for row in rows] == [1, 2, 3]
        keys = feed_worker.retained_artifacts(session)
    for path in artifacts.iterdir():
        os.utime(path, (0, 0))
    (artifacts / "abandoned.original").write_bytes(b"orphan")
    os.utime(artifacts / "abandoned.original", (0, 0))
    cleanup_operational_data(service.db, service.environment_settings, now=utcnow() + timedelta(days=400))
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job).where(Job.type == feed_worker.TYPE)) == 0
        assert session.scalar(select(func.count()).select_from(FeedCheck)) == 4
        assert session.scalar(select(func.count()).select_from(FeedUpdate)) == 3
    assert keys <= {path.name for path in artifacts.iterdir()} and not (artifacts / "abandoned.original").exists()


def test_invalid_xml_retained_as_gap_and_scheduler_requires_current_owner(signed, monkeypatch):
    _, service, identity = signed
    calls = downloads(monkeypatch, {URL: ("application/rss+xml", b"<rss><broken")})
    identifier, job_id = create(service, identity)
    finish(service, job_id)
    with service.db.session() as session:
        check = session.scalar(select(FeedCheck))
        assert check.status == "partial"
        assert check.receipts_json["failures"][0]["code"] == "invalid_feed_source"
        key = check.receipts_json["failures"][0]["retained_document"]["artifact_key"]
        assert (service.environment_settings.storage_path / "artifacts" / key).read_bytes() == b"<rss><broken"
        session.get(User, identity["user"]["id"]).active = False
        session.get(Feed, identifier).next_check_at = utcnow() - timedelta(seconds=1)
        session.commit()
    assert feed_worker.enqueue_due(service.db, service.settings)["started"] == 0
    with service.db.session() as session:
        assert "permission" in session.get(Feed, identifier).error
        assert session.scalar(select(func.count()).select_from(Job).where(Job.type == feed_worker.TYPE)) == 1
    assert calls == [URL]


def test_pause_resume_finishes_same_original_bytes_under_fresh_revision(signed, monkeypatch):
    client, service, identity = signed
    body = ("Retained original passage. " * 2100 + "THE OLD FINAL CONCLUSION").encode()
    values = {URL: ("text/plain", body)}
    calls = downloads(monkeypatch, values)
    identifier, job_id = create(service, identity)
    step(service, job_id)  # Plan
    step(service, job_id)  # First original portion
    route = f"/api/feeds/{identifier}"
    configuration = {"name": "Public source watch", "query": "Public legislative changes", "sources": [URL]}
    paused = client.patch(route, headers=_csrf(client), json={**configuration,
        "expected_revision": 1, "status": "paused", "request_key": str(uuid4())})
    assert paused.status_code == 200, paused.text
    values[URL] = ("text/plain", b"A different document now served by the publisher")
    resumed = client.patch(route, headers=_csrf(client), json={**configuration,
        "expected_revision": paused.json()["revision"], "status": "active", "request_key": str(uuid4())})
    assert resumed.status_code == 200, resumed.text
    with service.db.session() as session:
        current = session.get(Feed, identifier)
        replacement = session.get(Job, current.job_id)
        assert replacement.id != job_id and current.revision == 3
        checkpoint = replacement.payload["checkpoint"]
        assert checkpoint["search_plan"] is None and checkpoint["search_cursors"] is None
        assert checkpoint["resume_reads"][0]["reading"]["cursor"] == {"page": 0, "offset": 24000}
        assert checkpoint["intelligence_spec"]["feed_revision"] == 3
        replacement_id = replacement.id
    assert finish(service, replacement_id)["state"] == "succeeded"
    with service.db.session() as session:
        update = session.scalar(select(FeedUpdate))
        assert "THE OLD FINAL CONCLUSION" in update.source_text
        assert "".join(part["text"] for part in update.snapshot_json["excerpts"]) == body.decode()
        assert update.snapshot_json["reading_complete"]
        assert session.scalar(select(func.count()).select_from(FeedUpdate)) == 1
    assert calls == [URL], "A resumed original must use its saved bytes, not a changed publisher body"
