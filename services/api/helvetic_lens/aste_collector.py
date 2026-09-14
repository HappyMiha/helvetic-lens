"""Production orchestration of one committed, rate-limited public source request."""

from datetime import UTC, datetime

import httpx
from sqlalchemy import func, select

from . import aste_collection as collection
from .aste_models import AsteCollector, AsteItem
from .aste_parser import SOURCE_KEY
from .aste_transport import AsteTransportError, fetch
from .config import DomainError


def readiness(settings):
    if not settings.aste_source_enabled:
        return "disabled"
    return "configured" if settings.aste_source_permission_id else "permission_required"


def collect(database, settings, *, now=None, client=None):
    state = readiness(settings)
    if state != "configured":
        return {"state": state}
    clock = (lambda: now) if now is not None else (lambda: datetime.now(UTC))
    ticket = None
    owned = client is None
    try:
        with database.session() as session:
            ticket = collection.claim(session, settings.aste_source_permission_id, now=clock())
            session.commit()
        if ticket is None:
            return {"state": "waiting"}

        def guard():
            with database.session() as session:
                collection.guard(session, ticket, now=clock())

        client = client or httpx.Client(trust_env=False)
        raw = fetch(client, ticket["url"], guard=guard, now=clock)
        with database.session() as session:
            collection.succeed(session, ticket, raw, now=clock())
            session.commit()
        return {"state": "collected", "operation": ticket["kind"]}
    except (AsteTransportError, DomainError, ValueError) as error:
        code = getattr(error, "code", "aste_format_changed")
        if ticket:
            try:
                with database.session() as session:
                    collection.failed(session, ticket, code, now=clock(),
                        retry_after_seconds=getattr(error, "retry_after_seconds", None))
                    session.commit()
            except DomainError:
                pass  # Revoked permission or a replaced lease cannot be mutated.
        return {"state": "unavailable", "reason": code}
    finally:
        if owned and client is not None:
            client.close()


def status(session, settings, *, now):
    result = {"state": readiness(settings), "coverage_verified": False, "collection": None}
    if result["state"] != "configured":
        return result
    policy, selected = collection.scope(session, settings.aste_source_permission_id, now=now)
    row = session.get(AsteCollector, SOURCE_KEY)
    if row is None or row.permission_id != settings.aste_source_permission_id or row.generation != selected.generation:
        result["state"] = "waiting"
        return result
    query = select(func.count()).select_from(AsteItem).where(AsteItem.permission_id == row.permission_id, AsteItem.generation == row.generation)
    result["collection"] = {
        "known_items": session.scalar(query), "failed_items": session.scalar(query.where(AsteItem.last_error.is_not(None))),
        "pending_listing_pages": len(row.listing_queue), "last_request_at": row.last_request_at,
        "last_record_at": row.last_record_at, "last_completed_at": row.last_completed_at,
        "next_request_at": row.next_request_at, "last_error": row.last_error,
        "source_categories": list(row.category_labels.values()),
        "configured_categories": sorted({v.category for v in policy.native_access.category_mapping.values()}),
        "request_interval_seconds": policy.native_access.request_interval_seconds,
        "item_refresh_seconds": policy.min_poll_seconds,
    }
    return result
