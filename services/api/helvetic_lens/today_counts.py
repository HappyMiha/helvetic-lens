"""Counts of readable, unreviewed Today units, never source coverage.

All page continuations are internal and run in one database read snapshot. Native
readers remain the visibility authority. No partial scan is a numeric total.
"""

from datetime import UTC, datetime
from time import monotonic

from . import river_today, tender_today
from .monitoring_review_queue import DOMAINS, ReviewQueues

MAX_PAGES = 20
SCAN_SECONDS = 15


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


def counts(session, settings, user_id, *, now, prompts, runtime=None):
    queues = ReviewQueues(session, settings, user_id, now=now, prompts=prompts, runtime=runtime)
    deadline = monotonic() + SCAN_SECONDS
    results = []
    for domain in DOMAINS:
        if not queues.enabled(domain):
            result = {"count": None, "state": "unavailable"}
        elif monotonic() >= deadline:
            result = {"count": None, "state": "incomplete"}
        elif domain == "river":
            result = {"count": river_today.today(session, user_id, unreviewed=True, limit=1, now=now)["unreviewed_count"], "state": "complete"}
        elif domain == "tenders":
            result = {"count": tender_today.today(session, user_id, review_state="pending", limit=1, now=now)["pending_count"], "state": "complete"}
        else:
            result = _scan(lambda cursor: queues.page(domain, cursor), deadline=deadline)
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
