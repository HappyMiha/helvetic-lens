"""Shared feed authority, immutable observations and checked mutation receipts."""
from copy import deepcopy

from sqlalchemy import func, select

from .db import utcnow
from .feed_models import Feed, FeedCheck, FeedDossierLink, FeedImport, FeedReceipt, FeedUpdate
from .models import Job, User
from .product_access import organization_member
from .product_api import fail, iso
from .product_operations import fingerprint


def require_owner(session, feed, user_id, *, write=False):
    user = session.get(User, user_id, populate_existing=True)
    member = organization_member(session, user_id, session.info["organization_id"])
    if not feed or feed.owner_user_id != user_id or not member or not user or not user.active:
        fail("Feed not found.", 404, "not_found")
    if feed.organization_id != session.info["organization_id"]:
        fail("Feed not found.", 404, "not_found")
    if write and member.role != "organization_admin":
        fail("Your workspace role cannot change feeds.", 403, "feed_access_required")
    return feed


def owned(session, identifier, user_id, *, write=False):
    return require_owner(session, session.get(Feed, identifier, populate_existing=True), user_id, write=write)


def revision(feed, expected):
    if feed.revision != expected:
        fail("This feed changed. Reload its saved settings before continuing.", 409, "feed_revision_conflict")


def receipt(session, identity, request_key, action, command):
    existing = session.scalar(select(FeedReceipt).where(FeedReceipt.owner_user_id == identity.user_id,
        FeedReceipt.request_key == str(request_key)))
    key = fingerprint({"action": action, "command": command})
    if existing and (existing.action != action or existing.fingerprint != key):
        fail("This request key belongs to another feed change.", 409, "feed_request_conflict")
    return existing, key


def remember(session, identity, request_key, action, key, result):
    session.add(FeedReceipt(owner_user_id=identity.user_id, request_key=str(request_key),
        action=action, fingerprint=key, result_json=result))


def payload(session, feed, user_id):
    require_owner(session, feed, user_id)
    total = session.scalar(select(func.count()).select_from(FeedUpdate).where(FeedUpdate.feed_id == feed.id))
    latest = session.scalar(select(FeedCheck).where(FeedCheck.feed_id == feed.id)
        .order_by(FeedCheck.created_at.desc(), FeedCheck.id.desc()).limit(1))
    job = session.get(Job, feed.job_id) if feed.job_id else None
    from .feed_following import state
    from .feed_intelligence import projection
    follow = state(session, feed, user_id)
    return {"id": feed.id, "product": "legal" if feed.product == "loyer" else feed.product,
        "name": feed.name, "query": feed.query, "sources": feed.sources_json, "status": feed.status,
        "revision": feed.revision, "checked_at": iso(feed.checked_at) if feed.checked_at else None, "next_check_at": iso(feed.next_check_at) if feed.next_check_at else None,
        "error": feed.error, "created_at": iso(feed.created_at), "updated_at": iso(feed.updated_at),
        "intelligence": projection(session, feed), "update_count": total, "unread_count": follow["unread_count"], "follow": follow,
        "can_manage": organization_member(session, user_id, feed.organization_id).role == "organization_admin",
        "job": {"id": job.id, "status": job.state} if job else None,
        "last_check": {"id": latest.id, "status": latest.status, "finished_at": iso(latest.finished_at) if latest.finished_at else None} if latest else None}


def update_payload(update):
    return {"id": update.id, "sequence": update.sequence, "title": update.title, "url": update.url,
        "summary": update.summary, "content_hash": update.content_hash, "published_at": update.published_at,
        "created_at": iso(update.created_at), "reading_complete": bool(update.snapshot_json.get("reading_complete")),
        "original_url": f"/api/feeds/{update.feed_id}/updates/{update.id}/original",
        "scope": "Retained publisher material; the preview is not a verified research conclusion."}


def record_update(session, feed, *, title, url, summary, source_text, content_hash, snapshot_json, published_at=None):
    """Caller holds the organization lock. Only a consecutive unchanged body is a no-op."""
    latest = session.scalar(select(FeedUpdate).where(FeedUpdate.feed_id == feed.id, FeedUpdate.source_key == url)
        .order_by(FeedUpdate.sequence.desc()).limit(1))
    if latest and latest.content_hash == content_hash:
        return latest, False
    sequence = 1 + (session.scalar(select(func.max(FeedUpdate.sequence)).where(FeedUpdate.feed_id == feed.id)) or 0)
    row = FeedUpdate(feed_id=feed.id, organization_id=feed.organization_id, sequence=sequence, source_key=url,
        title=title[:700], url=url, summary=summary, source_text=source_text, content_hash=content_hash,
        snapshot_json=deepcopy(snapshot_json), published_at=published_at.strip()
            if isinstance(published_at, str) and len(published_at.strip()) <= 80 else None)
    session.add(row)
    session.flush()
    for link in session.scalars(select(FeedDossierLink).where(FeedDossierLink.feed_id == feed.id,
            FeedDossierLink.status == "active")):
        session.add(FeedImport(link_id=link.id, update_id=row.id, organization_id=feed.organization_id))
    feed.updated_at = utcnow()
    return row, True


def check_progress(check):
    """Deliberate reader projection: no artifact paths, buffered text or provider bodies."""
    data = check.receipts_json or {}
    return {"captured": data.get("captured", 0), "unchanged": data.get("unchanged", 0),
        "portions": data.get("portions", 0), "worker_error": data.get("worker_error"),
        "semantic_counts": {key: data.get("semantic_counts", {}).get(key, 0)
            for key in ("relevant", "uncertain", "unrelated", "unavailable")},
        "plan_status": (data.get("search_plan") or {}).get("status", "pending"),
        "query_index": data.get("query_index", 0), "query_count": len(data.get("search_queries", [])),
        "assessed_characters": (data.get("gate") or {}).get("offset", 0),
        "coverage": [{key: lane[key] for key in ("kind", "name", "url", "status", "omitted_records", "count", "query", "language", "purpose") if key in lane}
            for lane in data.get("coverage", [])],
        "failures": [{key: failure[key] for key in ("phase", "url", "code", "at") if key in failure}
            for failure in data.get("failures", [])]}
