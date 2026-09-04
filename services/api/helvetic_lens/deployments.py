"""Bounded, read-only production deployment status for platform administrators."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 512 * 1024
MAX_STRING_LENGTH = 8_000
MAX_LIST_ITEMS = 100
MAX_DEPTH = 7


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
            "branch": "main",
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
    result["history"] = _bounded(history if isinstance(history, list) else [])[:30]
    return result
