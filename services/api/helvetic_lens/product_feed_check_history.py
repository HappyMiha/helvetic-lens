"""Safe retained shared-collection history under current dossier selection."""
from sqlalchemy import func, select

from .db import utcnow
from .models import ConnectorRun, ConnectorSchedule
from .product_api import fail
from .product_coverage import selection
from .topic_coverage import _iso as iso
from .topic_coverage import snapshot

LIMIT = 10
STATES = {"queued", "running", "persisted", "partial", "degraded", "failed", "cancelled", "interrupted"}


def check(row):
    state = row["status"] if row["status"] in STATES else "unknown"
    # The native run counters describe shared events, not document membership or
    # current unresolved errors. Successful retries can retain old item errors.
    terminal = state in {"persisted", "partial", "degraded", "failed"}
    counts = {key: row[key + "_count"] if type(row[key + "_count"]) is int and row[key + "_count"] >= 0 else None
              for key in ("new", "changed", "failed")} if terminal else None
    return {"id": row["id"], "status": state, "created_at": iso(row["created_at"]),
        "started_at": iso(row["started_at"]), "finished_at": iso(row["finished_at"]),
        "reported_counts": counts,
        "explanation": (
            "This collection did not finish successfully. Earlier retained evidence is still available."
            if state in {"failed", "degraded"} else
            "Some items were retained, but collection was incomplete."
            if state == "partial" else
            "Completion was recorded. Item errors may include earlier attempts, not only unresolved failures."
            if state == "persisted" and counts and counts["failed"] else
            "No new or changed feed events were recorded. This does not establish unchanged sources or no relevant changes."
            if state == "persisted" and counts and counts["new"] == counts["changed"] == 0 else
            "This saved run has no recorded completed result."
            if state in {"queued", "running", "unknown", "interrupted", "cancelled"} else None)}


def payload(session, parent, pack_id, connector, stream, *, offset=0, as_of=None):
    profile, topics, pack_ids = selection(session, parent)
    if pack_id not in pack_ids:
        fail("This source collection is no longer selected in the dossier.", 404)
    now = utcnow()
    pack = snapshot(session, [pack_id], now=now, organization_id=parent.organization_id)["items"][0]
    source = next((row for row in pack["streams"] if row["connector"] == connector and row["stream"] == stream), None)
    if not source:
        fail("This source has no supported collection history in the dossier.", 404)
    if (offset and as_of is None) or (as_of is not None and (as_of.tzinfo is None or as_of > now)):
        fail("Open the first page to restart collection history.", 422)
    cutoff = as_of or now
    query = select(ConnectorRun).join(ConnectorSchedule, ConnectorSchedule.id == ConnectorRun.schedule_id).where(
        ConnectorRun.connector == connector, ConnectorRun.stream == stream,
        ConnectorSchedule.connector == connector, ConnectorSchedule.stream == stream,
        ConnectorRun.created_at <= cutoff)
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    # Whitelist scalar fields: no requester, job, cursors, raw errors or event bodies.
    rows = session.execute(query.with_only_columns(*[getattr(ConnectorRun, key) for key in
        ("id", "status", "created_at", "started_at", "finished_at", "new_count", "changed_count", "failed_count")])
        .order_by(ConnectorRun.created_at.desc(), ConnectorRun.id.desc()).offset(offset).limit(LIMIT)).mappings()
    return {"schema_id": "feed-check-history/v1", "dossier_id": parent.id,
        "profile_status": profile.status,
        "topics": [t for t in topics if pack_id in t["pack_ids"]],
        "pack": {key: pack[key] for key in ("id", "name", "definition_state", "subscription_enabled", "subscription_state")},
        "source": source, "items": [check(row) for row in rows], "total": total,
        "offset": offset, "page_size": LIMIT, "as_of": iso(cutoff),
        "next_offset": offset + LIMIT if offset + LIMIT < total else None,
        "scope": "Shared collection history for this selected source, not a dossier-wide scan. "
            "Reported event counts do not establish which documents were checked or their relevance to your question. "
            "Earlier runs can predate this dossier's source selection. Newer runs appear after refresh; retries may update saved rows.",
        "ai_calls": 0}
