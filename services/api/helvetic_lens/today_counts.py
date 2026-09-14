"""Counts of readable, unreviewed Today units, never source coverage.

All page continuations are internal and run in one database read snapshot. Native
readers remain the visibility authority. No partial scan is a numeric total.
"""

from datetime import UTC, datetime
from time import monotonic

from sqlalchemy import select

from . import (
    air_today,
    auction_today,
    commute_today,
    hazard_today,
    monitoring_runtime,
    river_today,
    road_today,
    tender_today,
    trademark_today,
)
from .hazard_boundary_store import BoundaryStore
from .interest_feed import InterestFeedReader
from .monitoring_contracts import ReaderMode
from .monitoring_live_models import MonitoringReview
from .monitoring_subjects import _actor

MAX_PAGES = 20
SCAN_SECONDS = 15
DOMAINS = ("pollen", "air", "river", "tenders", "commute", "traffic", "warnings", "ip", "auctions", "legal")


def _scan(read, *, deadline, eligible=lambda items: items):
    cursor, count, seen = None, 0, set()
    for _ in range(MAX_PAGES):
        if monotonic() >= deadline:
            return {"count": None, "state": "incomplete"}
        page = read(cursor)
        count += len(eligible(page["items"]))
        cursor = page.get("next_cursor")
        if not cursor:
            return {"count": count, "state": "complete"}
        # Also fail closed if a domain accidentally returns a non-advancing
        # cursor. Sparse pages with a *new* cursor must continue normally.
        key = repr(cursor)
        if key in seen:
            break
        seen.add(key)
    return {"count": None, "state": "incomplete"}


def _pair(cursor):
    return {"before": datetime.fromisoformat(cursor["before"]), "before_id": cursor["before_id"]} if cursor else {}


def counts(session, settings, user_id, *, now, prompts, runtime=None):
    organization = _actor(session, user_id)
    deadline = monotonic() + SCAN_SECONDS
    enabled = {
        "pollen": settings.deployment_instance in {"main", "monitoring-v2"}
        and monitoring_runtime._mode(settings, organization) == ReaderMode.ENABLED,
        "air": settings.air_watch_enabled, "river": settings.river_watch_enabled,
        "tenders": settings.tender_watch_enabled, "commute": settings.commute_watch_enabled,
        "traffic": settings.road_watch_enabled and settings.road_source_enabled,
        "warnings": settings.hazard_watch_enabled, "ip": settings.trademark_watch_enabled,
        "auctions": settings.auction_watch_enabled, "legal": True,
    }
    boundaries = BoundaryStore(settings.storage_path)
    legal = InterestFeedReader(organization, user_id, settings=settings, prompts=prompts, runtime=runtime)

    def pollen_unreviewed(items):
        ids = [item["id"] for item in items]
        reviewed = set(session.scalars(select(MonitoringReview.entry_id).where(MonitoringReview.entry_id.in_(ids)))) if ids else set()
        return [item for item in items if item["id"] not in reviewed]

    def air_page(cursor):
        result = air_today.today(session, user_id, **_pair(cursor))
        return {"items": [item for item in result["items"] if item["decision"] is None], "next_cursor": result["next"]}

    readers = {
        "pollen": lambda cursor: monitoring_runtime.today(session, settings=settings, user_id=user_id, now=now, before_id=cursor),
        "air": air_page,
        "commute": lambda cursor: commute_today.today(session, settings, user_id, now=now, before_id=cursor, limit=50),
        "traffic": lambda cursor: road_today.today(session, settings, user_id, now=now, cursor=cursor, limit=50),
        "warnings": lambda cursor: hazard_today.page(session, settings, user_id, store=boundaries, now=now, cursor=cursor, limit=20),
        "ip": lambda cursor: trademark_today.page(session, settings, user_id, now=now, cursor=cursor, limit=50),
        "auctions": lambda cursor: auction_today.page(session, settings, user_id, now=now, cursor=cursor, limit=50),
        "legal": lambda cursor: legal.feed(session, state="unread", cursor=cursor or "", limit=50),
    }
    results = []
    for domain in DOMAINS:
        if not enabled[domain]:
            result = {"count": None, "state": "unavailable"}
        elif monotonic() >= deadline:
            result = {"count": None, "state": "incomplete"}
        elif domain == "river":
            result = {"count": river_today.today(session, user_id, unreviewed=True, limit=1, now=now)["unreviewed_count"], "state": "complete"}
        elif domain == "tenders":
            result = {"count": tender_today.today(session, user_id, review_state="pending", limit=1, now=now)["pending_count"], "state": "complete"}
        else:
            result = _scan(readers[domain], deadline=deadline,
                           **({"eligible": pollen_unreviewed} if domain == "pollen" else {}))
        results.append({"domain": domain, **result})
    complete = all(row["state"] == "complete" for row in results)
    return {"items": results, "total": sum(row["count"] for row in results) if complete else None,
            "state": "complete" if complete else "incomplete", "evaluated_at": now.isoformat(),
            "scope": "unreviewed_today", "coverage_verified": False}


def read(service, settings, user_id):
    runtime = service.relation_runtime_observation()
    with service.db.session() as session:
        # Selects on SQLite otherwise use legacy autocommit semantics. PostgreSQL
        # requires isolation before the first membership/read statement.
        connection = session.connection()
        if connection.dialect.name == "postgresql":
            connection.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        elif connection.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN")
        return counts(session, settings, user_id, now=datetime.now(UTC),
                      prompts=service.prompt_settings, runtime=runtime)
