"""Private version links for the in-app centre; opening never means reviewing."""

import base64
import json
from datetime import datetime
from urllib.parse import quote
from uuid import UUID

from .config import DomainError
from .monitoring_review_queue import DOMAINS, ReviewQueues


def _cursor(raw, scope):
    if not raw:
        return None
    try:
        if not isinstance(raw, str) or len(raw) > 2048:
            raise ValueError()
        value = json.loads(base64.b64decode(raw + "=" * (-len(raw) % 4), altchars=b"-_", validate=True))
        if not isinstance(value, dict) or set(value) != {"v", "scope", "position"} or type(value["v"]) is not int or value["v"] != 1 or value["scope"] != scope:
            raise ValueError()
        position = value["position"]
        if scope[-1] in {"air", "river"}:
            if not isinstance(position, dict) or set(position) != {"before", "before_id"}:
                raise ValueError()
            if not isinstance(position["before"], str) or len(position["before"]) > 64:
                raise ValueError()
            if datetime.fromisoformat(position["before"]).tzinfo is None:
                raise ValueError()
            UUID(position["before_id"])
        else:
            UUID(position)
        return position
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError) as exc:
        raise DomainError("Refresh this private notification queue.", 422, "monitoring_notification_cursor_invalid") from exc


def _encode(position, scope):
    if position is None:
        return None
    return base64.urlsafe_b64encode(json.dumps({"v": 1, "scope": scope, "position": position}, separators=(",", ":")).encode()).decode().rstrip("=")


def _item(domain, row):
    if domain == "pollen":
        href = f"/pollen-watch?entry={quote(row['id'], safe='')}#draft={quote(row['subject_id'], safe='')}"
        name = row["station_id"]
    elif domain == "air":
        href = f"/air-watch?monitor={quote(row['monitor_id'], safe='')}&change={quote(row['id'], safe='')}"
        name = row["monitor_name"]
    else:
        href = row["href"]
        name = row.get("monitor_name", row.get("name"))
    item_key = {"ip": "candidate_id", "auctions": "item_id", "warnings": "event_id",
        "commute": "event_id", "traffic": "event_id"}.get(domain, "id")
    selected = {"domain": domain, "monitor_id": row["subject_id" if domain == "pollen" else "monitor_id"],
        "item_id": row[item_key],
        "sequence": row.get("revision") if domain == "warnings" else row.get("sequence") if domain in {"commute", "traffic"} else None}
    return {"id": row["id"], "domain": domain, "monitor_name": name, "href": href, "record": selected,
            "detected_at": row.get("detected_at", row.get("created_at", row.get("observed_at"))),
            "allergen": row.get("allergen") if domain == "pollen" else None}


def page(session, settings, user_id, *, domain, now, prompts, cursor=None):
    if domain not in DOMAINS or domain == "legal":
        raise DomainError("Choose a Monitoring notification queue.", 422, "monitoring_notification_domain_invalid")
    queues = ReviewQueues(session, settings, user_id, now=now, prompts=prompts)
    scope = [queues.organization, user_id, domain]
    position = _cursor(cursor, scope)
    result = queues.page(domain, position)
    return {"domain": domain, "state": result["state"], "items": [_item(domain, item) for item in result["items"]],
            "next_cursor": _encode(result["next_cursor"], scope), "evaluated_at": now.isoformat(),
            "coverage_verified": False, "review_required": True}
