"""Durable collection: one discovery page or original portion per delivery."""
import asyncio
from copy import deepcopy
from datetime import UTC, timedelta

import httpx
from sqlalchemy import select

from . import decision_search, feed_intelligence, feed_sources, jobs, search_channels
from .config import DomainError
from .db import utcnow
from .decision_engines import DecisionUnavailable
from .membership_locks import lock_organization
from .models import Job
from .monitoring_queues import SOURCES
from .product_operations import fingerprint
from .product_search_budget import reserve_paid_or_skip

TYPE = "feed_collect"
TARGET = "feed"


def _utc(value):
    return value.replace(tzinfo=UTC)


def _binding(feed):
    config = deepcopy(feed.config_json or {})
    if isinstance(config.get("intelligence"), dict):
        config["intelligence"].pop("cached_plan", None)
        if not config["intelligence"]:
            config.pop("intelligence")
    return fingerprint({"revision": feed.revision, "owner": feed.owner_user_id, "product": feed.product,
        "query": feed.query, "sources": feed.sources_json, "config": config})


def enqueue_check(session, feed, settings, request_key):
    from .feed_models import FeedCheck
    from .feed_operations import require_owner

    lock_organization(session, feed.organization_id)
    require_owner(session, feed, feed.owner_user_id, write=True)
    if feed.status != "active":
        raise DomainError("Resume this feed before checking its sources.", 409, "feed_paused")
    key = "feed:" + fingerprint([feed.id, str(request_key)])
    previous = session.scalar(select(Job).where(Job.type == TYPE, Job.idempotency_key == key))
    if previous:
        return previous
    current = session.get(Job, feed.job_id) if feed.job_id else None
    if current and current.state in {"failed", "cancelled"}:
        retained = session.scalar(select(FeedCheck).where(FeedCheck.job_id == current.id))
        if retained and retained.status in {"queued", "running"}:
            retained.status, retained.finished_at = current.state, current.finished_at or utcnow()
            retained.receipts_json = {**(retained.receipts_json or {}),
                "worker_error": current.error_code or "collection_interrupted"}
    if current and current.state not in jobs.TERMINAL_STATES:
        if current.payload.get("binding") == _binding(feed):
            return current
        jobs.cancel(session, current.id)
        check = session.scalar(select(FeedCheck).where(FeedCheck.job_id == current.id))
        if check:
            check.status, check.finished_at = "cancelled", utcnow()
    urls = [value for value in feed.sources_json if decision_search.public_url(value)]
    intelligence = feed_intelligence.spec(session, feed)
    cached = (feed.config_json or {}).get("intelligence", {}).get("cached_plan")
    if (not isinstance(cached, dict) or not feed_intelligence.cached(intelligence, cached)
            or cached.get("status") != "ready" or not cached.get("queries")
            or not isinstance(cached.get("relevance_scope"), str) or not 20 <= len(cached["relevance_scope"]) <= 1200):
        cached = None
    checkpoint = {"items": [{"url": url, "title": url, "summary": "", "date": None} for url in urls],
        "position": 0, "reading": {}, "search_pending": True,
        "search_cursors": None, "seen_cursors": [], "seen_pages": [], "seen_urls": [], "coverage": [], "failures": [],
        "retry_reads": [], "captured": 0, "unchanged": 0, "portions": 0,
        "intelligence_spec": intelligence, "search_plan": deepcopy(cached), "query_index": 0,
        "search_queries": deepcopy(cached.get("queries", [])) if cached else [], "gate": None,
        "assessment_cursor": 0, "assess_turn": True, "semantic_counts": {}}
    # Continue incomplete originals from the previous check at their exact saved
    # position. A changed feed starts a new scope instead of reviving old work.
    prior = session.scalar(select(FeedCheck).where(FeedCheck.feed_id == feed.id)
        .order_by(FeedCheck.created_at.desc(), FeedCheck.id.desc()).limit(1))
    if prior:
        old = prior.receipts_json or {}
        if (prior.feed_revision == feed.revision and prior.status == "failed" and "items" in old
                and old.get("intelligence_spec", {}).get("binding") == intelligence["binding"]):
            # A crash between documents must not drop the rest of a discovery
            # page or restart a moving catalogue before reaching its older tail.
            checkpoint = deepcopy(old)
            checkpoint.update(resumed_from_check=prior.id, captured=0, unchanged=0, portions=0)
            checkpoint.pop("worker_error", None)
        same_scope = ({key: value for key, value in old.get("intelligence_spec", {}).items()
            if key not in {"binding", "feed_revision"}} == {key: value for key, value in intelligence.items()
            if key not in {"binding", "feed_revision"}})
        if same_scope:
            if not checkpoint.get("resumed_from_check"):
                checkpoint["resume_reads"] = deepcopy(old.get("resume_reads", []))
                position = old.get("position", 0)
                if (old.get("reading", {}).get("retained_document") and type(position) is int
                        and 0 <= position < len(old.get("items", []))):
                    # Pause/rename revisions cannot strand a saved original's
                    # unread tail. A fresh plan/cursors still govern discovery.
                    checkpoint["resume_reads"].append({"item": deepcopy(old["items"][position]),
                        "reading": deepcopy(old["reading"])})
            checkpoint["resume_reads"] = [*deepcopy(checkpoint.get("resume_reads", [])),
                *deepcopy(old.get("retry_reads", []))]
            checkpoint["retry_reads"] = []
    job, _ = jobs.enqueue(session, job_type=TYPE, target_type=TARGET, target_id=feed.id,
        queue=SOURCES, priority=5, idempotency_key=key, max_attempts=settings.job_max_attempts,
        payload={"actor_id": feed.owner_user_id, "binding": _binding(feed), "revision": feed.revision,
            "checkpoint": checkpoint}, steps=[("Collect source originals", {})])
    session.add(FeedCheck(feed_id=feed.id, organization_id=feed.organization_id, job_id=job.id,
        feed_revision=feed.revision, status="queued", receipts_json=deepcopy(checkpoint)))
    feed.job_id, feed.error = job.id, None
    return job


def enqueue_due(database, settings):
    from .feed_models import Feed

    now = utcnow()
    with database.session(include_all_organizations=True) as session:
        due = list(session.execute(select(Feed.id, Feed.organization_id).where(Feed.status == "active",
            Feed.next_check_at <= now).order_by(Feed.next_check_at, Feed.id).limit(100)))
    started = 0
    for identifier, organization_id in due:
        with database.organization_context(organization_id), database.session() as session:
            lock_organization(session, organization_id)
            feed = session.get(Feed, identifier, populate_existing=True)
            if not feed or feed.status != "active" or _utc(feed.next_check_at) > now:
                continue
            try:
                job = enqueue_check(session, feed, settings, "scheduled:" + feed.next_check_at.isoformat())
                started += int(job.state == "queued")
                feed.next_check_at = now + timedelta(minutes=5)
            except DomainError:
                feed.error = "The feed owner no longer has permission to collect in this workspace."
                feed.next_check_at = now + timedelta(hours=1)
            session.commit()
    return {"checked": len(due), "started": started}


def _lease(job):
    return job.lease_owner, _utc(job.leased_at) if job.leased_at else None, job.attempts


def _current(session, service, job_id, lease):
    from .feed_models import Feed, FeedCheck
    from .feed_operations import require_owner

    job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if (not job or job.state != "running" or job.cancel_requested or _lease(job) != lease
            or not job.heartbeat_at or (utcnow() - _utc(job.heartbeat_at)).total_seconds() >= service.settings.job_lease_seconds):
        raise jobs.JobCancelled()
    feed = session.get(Feed, job.target_id, populate_existing=True)
    check = session.scalar(select(FeedCheck).where(FeedCheck.job_id == job.id))
    if not feed or not check:
        raise DomainError("Feed collection no longer exists.", 404, "feed_scope_changed")
    require_owner(session, feed, job.payload["actor_id"], write=True)
    if feed.status != "active" or feed.job_id != job.id or _binding(feed) != job.payload["binding"]:
        raise DomainError("Feed configuration changed.", 409, "feed_scope_changed")
    saved = job.payload.get("checkpoint", {}).get("intelligence_spec")
    if saved and feed_intelligence.spec(session, feed)["binding"] != saved["binding"]:
        raise DomainError("The feed's authorized research context changed.", 409, "feed_scope_changed")
    return job, feed, check


def _prepare(state):
    if not state.get("search_plan"):
        return {"phase": "plan", "spec": deepcopy(state["intelligence_spec"])}
    if state.get("gate"):
        return {"phase": "gate"}
    if not state.get("reading") and state.get("resume_reads"):
        saved = state["resume_reads"].pop(0)
        state["items"].insert(state["position"], saved["item"])
        state["reading"] = saved["reading"]
    while state["position"] < len(state["items"]):
        item = state["items"][state["position"]]
        if item["url"] not in state["seen_urls"] or state.get("reading"):
            return {"phase": "read", "item": deepcopy(item), "reading": deepcopy(state["reading"])}
        state["position"] += 1
    if state["search_pending"]:
        query = state["search_queries"][state["query_index"]]
        return {"phase": "search", "cursors": state["search_cursors"], "query": query["query"],
            "query_index": state["query_index"], "language": query.get("language"), "purpose": query.get("purpose")}
    return {"phase": "finish"}


def _remember_plan(feed, state, result):
    specification = state["intelligence_spec"]
    valid = (feed_intelligence.cached(specification, result) and result.get("status") == "ready"
        and isinstance(result.get("relevance_scope"), str) and 20 <= len(result["relevance_scope"]) <= 1200)
    queries = result.get("queries", []) if valid else []
    if not queries:
        valid = False
        queries = [{"query": specification["query"], "language": "und",
            "purpose": "Check the submitted public question while semantic planning is unavailable."}]
    plan = {**result, "contract": feed_intelligence.CONTRACT, "binding": specification["binding"],
        "feed_revision": specification["feed_revision"], "status": "ready" if valid else "unavailable",
        "queries": queries}
    state["search_plan"], state["search_queries"], state["query_index"] = plan, queries, 0
    state["coverage"].append({"kind": "semantic_plan", "status": plan["status"],
        "count": len(queries), "at": utcnow().isoformat()})
    if valid:
        config = deepcopy(feed.config_json or {})
        config["intelligence"] = {**config.get("intelligence", {}), "cached_plan": deepcopy(plan)}
        feed.config_json = config
    else:
        state["failures"].append({"phase": "plan", "code": result.get("error", "semantic_plan_unavailable"),
            "at": utcnow().isoformat()})


def _next_gate(session, feed, state):
    """Interleave reassessment with collection; eventually drain the whole history."""
    if not state.get("search_plan") or state.get("gate") or state.get("reading"):
        return
    drained = (not state["search_pending"] and state["position"] >= len(state["items"])
        and not state.get("resume_reads"))
    if not state.get("assess_turn") and not drained:
        return
    specification = state["intelligence_spec"]
    update = feed_intelligence.next_unassessed(session, feed, specification,
        after_sequence=state.get("assessment_cursor", 0))
    state["assess_turn"] = False
    if not update:
        return
    gate = {"update_id": update.id, "sequence": update.sequence, "offset": 0, "portions": []}
    previous = feed_intelligence.latest_assessment(session, feed, update, specification)
    resume = (previous.decision_json or {}).get("continuation", {}) if previous else {}
    if (resume.get("content_hash") == update.content_hash and resume.get("spec_binding") == specification["binding"]
            and type(resume.get("offset")) is int and 0 <= resume["offset"] < len(update.source_text)):
        gate.update(offset=resume["offset"], portions=deepcopy(resume.get("portions", [])))
    state["gate"] = gate


def _gate_work(session, feed, state):
    from .feed_models import FeedUpdate

    gate = state["gate"]
    update = session.get(FeedUpdate, gate["update_id"])
    if not update or update.feed_id != feed.id:
        raise DomainError("The retained feed version changed.", 409, "feed_scope_changed")
    start = gate["offset"]
    item = {"title": update.title, "url": update.url}
    size = feed_intelligence.gate_characters(state["intelligence_spec"], state["search_plan"],
        item, update.source_text[start:start + feed_intelligence.GATE_CHARACTERS])
    text = update.source_text[start:start + size]
    return {"update_id": update.id, "content_hash": update.content_hash, "start": start,
        "end": start + len(text), "original_characters": len(update.source_text),
        "reading_complete": bool(update.snapshot_json.get("reading_complete")),
        "item": {**item, "source_text": text},
        "gate_error": "semantic_context_unavailable" if update.source_text else "source_text_unavailable",
        "spec": deepcopy(state["intelligence_spec"]), "plan": deepcopy(state["search_plan"])}


def _remember_gate(session, feed, state, work, result):
    from .feed_models import FeedUpdate

    gate = state["gate"]
    decision = deepcopy(result)
    if decision.get("verdict") not in {"relevant", "uncertain", "unrelated", "unavailable"}:
        decision = {"verdict": "unavailable", "engine": None,
            "error": decision.get("error_code", "semantic_relevance_unavailable")}
    if decision["verdict"] != "unavailable" and decision.get("engine") != "laya":
        decision = {"verdict": "unavailable", "engine": None, "error": "semantic_relevance_not_verified"}
    unavailable = decision["verdict"] == "unavailable"
    completed = [*gate["portions"], {"start": work["start"], "end": work["end"], "decision": decision}]
    if not unavailable and decision["verdict"] != "relevant" and work["end"] < work["original_characters"]:
        gate.update(offset=work["end"], portions=completed)
        return
    verdicts = [part["decision"]["verdict"] for part in completed]
    verdict = ("relevant" if "relevant" in verdicts else "unavailable" if unavailable else
        "uncertain" if "uncertain" in verdicts or not work["reading_complete"] else "unrelated")
    aggregate = {"verdict": verdict, "engine": "laya" if not unavailable else None,
        "policy_version": feed_intelligence.CONTRACT, "content_hash": work["content_hash"],
        "original_characters": work["original_characters"], "reading_complete": work["reading_complete"],
        "assessed_characters": sum(p["end"] - p["start"] for p in completed if p["decision"]["verdict"] != "unavailable"),
        "portions": completed, "scope": "Semantic relevance of retained original portions; a matching portion supports inclusion. "
            "Unrelated requires every extracted portion and complete original reading. This is not factual verification."}
    if unavailable:
        aggregate["error"] = decision.get("error", "semantic_relevance_unavailable")
        aggregate["continuation"] = {"offset": work["start"], "portions": deepcopy(gate["portions"]),
            "content_hash": work["content_hash"], "spec_binding": work["spec"]["binding"]}
        state["failures"].append({"phase": "gate", "url": work["item"]["url"],
            "code": aggregate["error"], "at": utcnow().isoformat()})
    update = session.get(FeedUpdate, work["update_id"])
    if not update or update.feed_id != feed.id or update.content_hash != work["content_hash"]:
        raise DomainError("The retained feed version changed.", 409, "feed_scope_changed")
    feed_intelligence.persist_assessment(session, feed, update, work["spec"], work["plan"], aggregate)
    counts = state.setdefault("semantic_counts", {})
    counts[verdict] = counts.get(verdict, 0) + 1
    state["assessment_cursor"] = gate["sequence"]
    state["gate"] = None


def _read_failure(state, work, code, result=None):
    reading = deepcopy(state.get("reading", {}))
    if result and result.get("_retained_document") and not reading.get("retained_document"):
        reading["retained_document"] = result["_retained_document"]
    state["failures"].append({"phase": "read", "url": work["item"]["url"], "code": code,
        "at": utcnow().isoformat(), "retained_document": reading.get("retained_document")})
    state["retry_reads"].append({"item": work["item"], "reading": reading})
    state["seen_urls"].append(work["item"]["url"])
    state["reading"] = {}
    state["position"] += 1


def _remember_read(session, feed, state, work, result):
    from .feed_operations import record_update

    if result.get("status") == "index":
        state["coverage"].append({"kind": "rss_atom", "url": work["item"]["url"],
            "count": len(result["items"]), "omitted_records": result["omitted_records"],
            "status": "partial" if result["omitted_records"] else "complete",
            "retained_document": result["_retained_document"], "at": utcnow().isoformat()})
        state["items"].extend(result["items"])
        state["items"].extend({"url": url, "title": url, "summary": "", "date": None} for url in result["next_pages"])
        state["seen_urls"].append(work["item"]["url"])
        state["position"] += 1
        state["reading"] = {}
        return
    if result.get("error") or result.get("status") != "complete":
        _read_failure(state, work, result.get("error_code", "source_extraction_unavailable"), result)
        return
    reading = result.get("reading")
    expected = work["reading"].get("cursor") or {"page": 0, "offset": 0}
    original = result.get("_retained_document")
    next_cursor = reading.get("next_cursor") if isinstance(reading, dict) else None
    if (not reading or reading.get("contract") != "document-reading/v1" or reading.get("cursor") != expected
            or not original or result.get("sha256") != original.get("sha256")
            or work["reading"].get("retained_document", {}).get("sha256", result.get("sha256")) != result.get("sha256")
            or next_cursor and (next_cursor.get("page", -1), next_cursor.get("offset", -1)) <= (expected["page"], expected["offset"])):
        _read_failure(state, work, "source_reading_changed", result)
        return
    saved = state["reading"]
    saved.setdefault("excerpts", []).extend(deepcopy(result.get("excerpts", [])))
    saved["warnings"] = list(dict.fromkeys([*saved.get("warnings", []), *result.get("warnings", [])]))
    saved.update(cursor=next_cursor, retained_document=original, reading=reading)
    state["portions"] += 1
    if next_cursor:
        return
    text = "\n".join(part["text"] for part in saved["excerpts"])
    if not text.strip():
        _read_failure(state, work, "source_has_no_readable_text", result)
        return
    snapshot = {"contract": "feed-original/v1", "retained_document": original,
        "reading_complete": not saved["warnings"], "reading": reading, "warnings": saved["warnings"],
        "excerpts": saved["excerpts"], "summary_kind": "publisher_or_discovery_metadata",
        "requested_url": work["item"]["url"], "captured_at": original["fetched_at"]}
    _, created = record_update(session, feed, title=work["item"]["title"], url=original["url"],
        summary=work["item"].get("summary", ""), source_text=text, content_hash=original["sha256"],
        snapshot_json=snapshot, published_at=str(work["item"]["date"])[:80] if work["item"].get("date") else None)
    state["captured" if created else "unchanged"] += 1
    if saved["warnings"]:
        state["failures"].append({"phase": "read", "url": work["item"]["url"],
            "code": "source_extraction_warnings", "warnings": saved["warnings"], "at": utcnow().isoformat()})
    state["seen_urls"].append(work["item"]["url"])
    state["position"] += 1
    state["reading"] = {}
    state["assess_turn"] = True


async def execute(service, job_id, worker):
    from .feed_models import FeedCheck

    with service.write_guard, service.db.session() as session:
        lock_organization(session, service.organization_id)
        pending = session.get(Job, job_id)
        if not pending or pending.type != TYPE or _utc(pending.available_at) > utcnow():
            return {"id": job_id, "state": "not_claimed"}
        job = jobs.claim(session, job_id, worker)
        if not job:
            session.commit()
            return {"id": job_id, "state": "not_claimed"}
        lease = _lease(job)
        session.commit()
    try:
        with service.write_guard, service.db.session() as session:
            lock_organization(session, service.organization_id)
            job, feed, check = _current(session, service, job_id, lease)
            state = deepcopy(job.payload["checkpoint"])
            _next_gate(session, feed, state)
            work = _prepare(state)
            if work["phase"] == "gate":
                work.update(_gate_work(session, feed, state))
            work.setdefault("query", feed.query)
            work.update(product=feed.product, sources=list(feed.sources_json))
            skipped_paid = None
            if work["phase"] == "search" and service.settings.web_search_provider == "search1api":
                skipped_paid = reserve_paid_or_skip(session, service.settings, 2)
            check.status = "running"
            job.payload = {**job.payload, "checkpoint": state}
            session.commit()
        if work["phase"] == "finish":
            result = None
        else:
            try:
                async with asyncio.timeout(max(1, min(100, service.settings.job_lease_seconds - 5))):
                    if work["phase"] == "plan":
                        result = await feed_intelligence.prepare(service, work["spec"])
                    elif work["phase"] == "gate":
                        result = (await feed_intelligence.evaluate(service.settings, work["spec"], work["plan"], work["item"])
                            if work["item"]["source_text"] else {"verdict": "unavailable", "engine": None, "error": work["gate_error"]})
                    elif work["phase"] == "search":
                        settings = search_channels.request_settings(service.settings, skipped_paid)
                        selected = [source for source in work["sources"] if not decision_search.public_url(source)]
                        result = await decision_search.federated_retrieve(settings, work["query"], "web", "balanced",
                            work["product"], cursors=work["cursors"], complete_page=True,
                            selected_catalogues=selected or None)
                        search_channels.note_skipped_paid(result, skipped_paid)
                    else:
                        result = await feed_sources.read(service, work["item"], "feed-" + job_id, work["reading"])
            except (DomainError, DecisionUnavailable, httpx.HTTPError, TimeoutError, ValueError, OSError) as error:
                result = {"status": "unavailable", "error_code": getattr(error, "code", "source_unavailable")}
        with service.write_guard, service.db.session() as session:
            lock_organization(session, service.organization_id)
            job, feed, check = _current(session, service, job_id, lease)
            if work["phase"] == "plan":
                _remember_plan(feed, state, result)
            elif work["phase"] == "gate":
                _remember_gate(session, feed, state, work, result)
            elif work["phase"] == "search":
                state["coverage"].append({**{key: result[key] for key in
                    ("lanes", "skipped_channels", "omitted_records", "candidate_limit", "status") if key in result},
                    "query": work["query"], "query_index": work["query_index"], "language": work["language"],
                    "purpose": work["purpose"], "cursors": work["cursors"], "at": utcnow().isoformat()})
                if result.get("status") == "unavailable":
                    state["failures"].append({"phase": "search", "code": result.get("error_code", "search_unavailable"), "at": utcnow().isoformat()})
                state["items"] = result.get("items", [])
                state["position"] = 0
                following = result.get("next_cursors")
                marker = fingerprint([work["query_index"], following]) if following else None
                page = fingerprint([work["query_index"], [item["url"] for item in state["items"]]])
                if following and state["items"] and page in state.setdefault("seen_pages", []):
                    state["failures"].append({"phase": "search", "code": "search_page_repeated", "at": utcnow().isoformat()})
                    following = None
                state.setdefault("seen_pages", []).append(page)
                if marker and marker in state["seen_cursors"]:
                    state["failures"].append({"phase": "search", "code": "search_cursor_repeated", "at": utcnow().isoformat()})
                    following = None
                if marker:
                    state["seen_cursors"].append(marker)
                state["search_cursors"] = following
                if not following:
                    state["query_index"] += 1
                state["search_pending"] = bool(following) or state["query_index"] < len(state["search_queries"])
                state["assess_turn"] = True
            elif work["phase"] == "read":
                _remember_read(session, feed, state, work, result)
            check.receipts_json = deepcopy(state)
            job.payload = {**job.payload, "checkpoint": state}
            if work["phase"] == "finish":
                check.status = "partial" if state["failures"] or any(c.get("status") in {"partial", "unavailable"} for c in state["coverage"]) else "completed"
                check.finished_at = feed.checked_at = utcnow()
                feed.error = "Some sources could not be completely checked. Open check history for the retained gaps." if check.status == "partial" else None
                feed.next_check_at = utcnow() + timedelta(hours=1)
                jobs.complete(session, job.id, result_type="feed_check", result_id=check.id,
                    result_json={"status": check.status, "captured": state["captured"], "unchanged": state["unchanged"]})
            else:
                jobs.yield_batch(session, job)
            session.commit()
            return {"id": job_id, "state": job.state}
    except jobs.JobCancelled:
        return {"id": job_id, "state": "not_owned"}
    except DomainError:
        with service.write_guard, service.db.session() as session:
            lock_organization(session, service.organization_id)
            job = session.get(Job, job_id)
            if job and job.state == "running" and _lease(job) == lease:
                jobs.cancel(session, job.id)
                check = session.scalar(select(FeedCheck).where(FeedCheck.job_id == job.id))
                if check:
                    check.status, check.finished_at = "cancelled", utcnow()
                session.commit()
        return {"id": job_id, "state": "cancelled"}


def retained_artifacts(session):
    """Feed originals and unfinished portions outlive operational job cleanup."""
    from .feed_models import FeedCheck, FeedUpdate

    def keys(value):
        if isinstance(value, dict):
            key = value.get("artifact_key")
            if isinstance(key, str) and "/" not in key and "\\" not in key:
                yield key
            for child in value.values():
                yield from keys(child)
        elif isinstance(value, list):
            for child in value:
                yield from keys(child)
    result = set()
    for statement in (select(FeedUpdate.snapshot_json), select(FeedCheck.receipts_json),
            select(Job.payload).where(Job.type == TYPE, Job.state.not_in(jobs.TERMINAL_STATES))):
        for value in session.scalars(statement):
            result.update(keys(value))
    return result
