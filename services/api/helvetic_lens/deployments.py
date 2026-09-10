"""Bounded, read-only production deployment status for platform administrators."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 512 * 1024
MAX_STRING_LENGTH = 8_000
MAX_LIST_ITEMS = 100
MAX_DEPTH = 7
MONITORING_STATUSES = {"PLANNED", "READY", "IN PROGRESS", "VERIFYING", "DONE", "BLOCKED", "DEFERRED"}


def _progress_snapshot(value: Any) -> dict[str, Any]:
    """Invalid or truncated task data must never look like a smaller denominator."""
    value = value if isinstance(value, dict) else {}
    sha = value.get("sha")
    sha = sha if isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha) else None
    invalid = {"sha": sha, "state": "unavailable", "reason": "Stored backlog snapshot is invalid.", "tasks": []}
    reason = value.get("reason")
    if value.get("state") == "unavailable":
        if isinstance(reason, str) and 0 < len(reason) <= 500:
            return {**invalid, "reason": reason}
        return invalid
    tasks = value.get("tasks")
    if (value.get("state") != "available" or not sha or reason is not None
            or not isinstance(tasks, list) or not 0 < len(tasks) <= MAX_LIST_ITEMS):
        return invalid
    result = []
    seen = set()
    for task in tasks:
        if not isinstance(task, dict):
            return invalid
        task_id, title, status = task.get("id"), task.get("title"), task.get("status")
        if (not isinstance(task_id, str) or not re.fullmatch(r"MV2-[0-9]{3}", task_id)
                or task_id in seen or not isinstance(title, str) or not title.strip() or len(title) > 500
                or not isinstance(status, str) or status not in MONITORING_STATUSES):
            return invalid
        seen.add(task_id)
        result.append({"id": task_id, "title": title, "status": status})
    return {"sha": sha, "state": "available", "reason": None, "tasks": sorted(result, key=lambda task: task["id"])}


def _monitoring_progress(value: Any) -> dict[str, Any] | None:
    """Validate generated host metadata without reading Git or executing commands."""
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int
            or value["schema_version"] != 1 or value.get("source_path") != "BACKLOG_MONITORING_V2.md"):
        return None
    branch, updated_at = value.get("branch"), value.get("updated_at")
    if (not isinstance(branch, str) or not 0 < len(branch) <= 200
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", branch)
            or not isinstance(updated_at, str) or len(updated_at) > 40):
        return None
    try:
        if datetime.fromisoformat(updated_at.replace("Z", "+00:00")).utcoffset() != timedelta(0):
            return None
    except ValueError:
        return None
    latest, deployed = _progress_snapshot(value.get("latest")), _progress_snapshot(value.get("deployed"))
    if (latest["state"] == deployed["state"] == "available" and latest["sha"] == deployed["sha"]
            and latest["tasks"] != deployed["tasks"]):
        for snapshot in (latest, deployed):
            snapshot.update(state="unavailable", reason="Backlog snapshots disagree for the same commit.", tasks=[])
    return {
        "schema_version": 1, "source_path": "BACKLOG_MONITORING_V2.md", "updated_at": updated_at,
        "branch": branch, "latest": latest, "deployed": deployed,
    }


def _bounded(value: Any, *, depth: int = 0) -> Any:
    if depth > MAX_DEPTH:
        return None
    if isinstance(value, dict):
        return {
            str(key)[:120]: _bounded(item, depth=depth + 1)
            for key, item in list(value.items())[:MAX_LIST_ITEMS]
        }
    if isinstance(value, list):
        return [_bounded(item, depth=depth + 1) for item in value[:MAX_LIST_ITEMS]]
    if isinstance(value, str):
        return value[:MAX_STRING_LENGTH]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return str(value)[:MAX_STRING_LENGTH]


def _read_json(path: Path) -> Any:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("deployment status file exceeds the read limit")
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def deployment_snapshot(state_dir: Path) -> dict[str, Any]:
    """Return only bounded JSON written by the host-side release manager."""

    fallback: dict[str, Any] = {
        "schema_version": 1,
        "service": {
            "enabled": False,
            "state": "not_configured",
            "poll_interval_seconds": None,
            "last_checked_at": None,
            "next_retry_at": None,
        },
        "remote": {
            "repository": None,
            "branch": None,
            "sha": None,
            "checked_at": None,
        },
        "current": {
            "sha": None,
            "release": None,
            "summary": None,
            "deployed_at": None,
        },
        "last_run": None,
        "history": [],
        "monitoring_progress": None,
    }
    try:
        status = _read_json(state_dir / "status.json")
        history = _read_json(state_dir / "history.json")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        fallback["service"]["state"] = "status_unavailable"
        fallback["service"]["error"] = str(exc)[:500]
        return fallback

    if not isinstance(status, dict):
        return fallback
    result = _bounded(status)
    if not isinstance(result, dict):
        return fallback
    result.setdefault("schema_version", 1)
    result.setdefault("service", fallback["service"])
    result.setdefault("remote", fallback["remote"])
    result.setdefault("current", fallback["current"])
    result.setdefault("last_run", None)
    # Inspect the original arrays before _bounded could truncate an invalid >100-task snapshot.
    result["monitoring_progress"] = _monitoring_progress(status.get("monitoring_progress"))
    result["history"] = _bounded(history if isinstance(history, list) else [])[:30]
    return result
