"""Read-only, paginated host deployment journal. Never executes deployment code."""

import base64
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .config import DomainError
from .deployments import MAX_FILE_BYTES, _read_json

STATUSES = {"succeeded", "failed", "deploying", "running", "interrupted", "rejected", "rollback_failed"}
SUMMARY_FIELDS = ("id", "kind", "status", "target_sha", "previous_sha", "activated_sha", "release",
                  "started_at", "finished_at", "duration_seconds", "host", "environment", "error_step", "interrupted_at")


def redact(value: str) -> str:
    value = re.sub(r"(?i)\bBearer\s+[^\s\"'<>]+", "Bearer [redacted]", value)
    value = re.sub(r"(?i)((?:password|secret|token|api[_-]?key|authorization)[\"']?\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)", r"\1[redacted]", value)
    return re.sub(r"(https?://)[^/@\s]+:[^/@\s]+@", r"\1[redacted]@", value)


def _text(value, limit=8000):
    return redact(str(value))[:limit] if value is not None else None


def _summary(run):
    if not isinstance(run, dict):
        raise DomainError("The deployment history record is malformed.", 503, "deployment_history_unavailable")
    if not isinstance(run.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", run["id"]):
        raise DomainError("The deployment history ID is malformed.", 503, "deployment_history_unavailable")
    if len(str(run.get("started_at") or "")) > 400:
        raise DomainError("The deployment history date is malformed.", 503, "deployment_history_unavailable")
    result = {key: (_text(run.get(key), 400) if key != "duration_seconds" else
                  run.get(key) if isinstance(run.get(key), (float, int)) else None)
            for key in SUMMARY_FIELDS}
    for key in ("started_at", "finished_at", "interrupted_at"):
        try:
            if result[key]:
                datetime.fromisoformat(result[key].replace("Z", "+00:00"))
        except ValueError:
            result[key] = None
    return result


def _detail(run):
    if (not isinstance(run, dict) or not isinstance(run.get("steps", []), list)
            or not isinstance(run.get("changes", []), list)):
        raise DomainError("The deployment record is malformed.", 503, "deployment_history_unavailable")
    value = _summary(run)
    for key in ("error", "backup_id", "model_id"):
        value[key] = _text(run.get(key))
    value["steps"] = [{key: (_text(item.get(key)) if key != "duration_seconds" else item.get(key))
                       for key in ("name", "status", "started_at", "finished_at", "duration_seconds", "error", "interrupted_at")}
                      for item in run.get("steps", [])[:100] if isinstance(item, dict)]
    value["changes"] = [{key: _text(item.get(key), 500) for key in ("sha", "short_sha", "subject", "author", "committed_at")}
                        for item in run.get("changes", [])[:100] if isinstance(item, dict)]
    rollback = run.get("rollback") if isinstance(run.get("rollback"), dict) else {}
    value["rollback"] = {key: _text(rollback.get(key)) for key in ("status", "error", "started_at", "finished_at")}
    value["rollback"]["status"] = value["rollback"]["status"] or "not_required"
    value["rollback"]["backup_restored"] = rollback.get("backup_restored") is True
    notes = run.get("release_notes")
    value["release_notes"] = None if not isinstance(notes, dict) else {
        key: _text(notes.get(key), 16000 if key == "text" else 400)
        for key in ("kind", "previous_sha", "target_sha", "captured_at", "text")
    }
    value["details_truncated"] = (len(run.get("steps", [])) > 100 or len(run.get("changes", [])) > 100
                                  or len(str(run.get("error") or "")) > 8000
                                  or any(item.get("error_truncated") or len(str(item.get("error") or "")) > 8000
                                         for item in run.get("steps", []) if isinstance(item, dict)))
    if value["release_notes"] is not None:
        value["release_notes"].update(
            repository_notes_available=notes.get("repository_notes_available") is True,
            changes_may_be_truncated=notes.get("changes_may_be_truncated") is True,
            text_truncated=len(str(notes.get("text") or "")) > 16000,
        )
    repository = run.get("repository") or ""
    old, new = run.get("previous_sha") or "", run.get("target_sha") or ""
    value["compare_url"] = (
        f"{repository}/compare/{old}...{new}"
        if re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
        and re.fullmatch(r"[a-f0-9]{40}", old) and re.fullmatch(r"[a-f0-9]{40}", new) else None
    )
    return value


@contextmanager
def _archive(state_dir):
    path = state_dir / "history.sqlite3"
    if path.is_symlink():
        raise DomainError("Deployment history is unavailable.", 503, "deployment_history_unavailable")
    connection = None
    try:
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
        connection.row_factory = sqlite3.Row
        yield connection
    except (sqlite3.Error, OSError, ValueError) as error:
        raise DomainError("Deployment history is unavailable. Retry or inspect the host release manager.",
                          503, "deployment_history_unavailable") from error
    finally:
        if connection is not None:
            connection.close()


def _legacy(state_dir):
    try:
        records = _read_json(state_dir / "history.json") or []
        status = _read_json(state_dir / "status.json") or {}
        last = status.get("last_run") if isinstance(status, dict) else None
        if not isinstance(records, list):
            raise ValueError("invalid history")
        by_id = {row["id"]: row for row in records if isinstance(row, dict) and isinstance(row.get("id"), str)}
        if isinstance(last, dict) and isinstance(last.get("id"), str):
            by_id[last["id"]] = last
        return sorted(by_id.values(), key=lambda row: (str(row.get("started_at") or ""), row["id"]), reverse=True)
    except (ValueError, OSError) as error:
        raise DomainError("Legacy deployment history is unavailable.", 503, "deployment_history_unavailable") from error


def _decode(cursor, status, mode):
    if not cursor:
        return None
    try:
        if len(cursor) > 2000:
            raise ValueError()
        data = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        if (data["v"] != 1 or data["status"] != status or data["mode"] != mode
                or not isinstance(data["after"], list) or len(data["after"]) != 2
                or not all(isinstance(item, str) and len(item) <= 400 for item in data["after"])
                or type(data["ceiling"]) is not int or not 0 <= data["ceiling"] <= 2**63-1):
            raise ValueError()
        return data
    except (ValueError, KeyError, TypeError) as error:
        raise DomainError("The deployment history cursor is invalid; start from the latest page.", 422, "invalid_cursor") from error


def _encode(data):
    return base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode().rstrip("=")


def history_page(state_dir: Path, *, status: str = "", cursor: str | None = None, limit: int = 20):
    if status and status not in STATUSES:
        raise DomainError("Unsupported deployment status filter.")
    if not 1 <= limit <= 50:
        raise DomainError("Deployment page size must be between 1 and 50.")
    mode = "journal" if (state_dir / "history.sqlite3").exists() else "legacy"
    seek = _decode(cursor, status, mode)
    archived_since = None
    if mode == "journal":
        with _archive(state_dir) as archive:
            metadata = dict(archive.execute("SELECT key, value FROM metadata"))
            archived_since = metadata.get("archive_started_at")
            identity = metadata.get("archive_id", archived_since)
            if seek and seek.get("archive_id") != identity:
                raise DomainError("Deployment history changed; start from the latest page.", 422, "invalid_cursor")
            ceiling = seek["ceiling"] if seek else archive.execute("SELECT coalesce(max(rowid), 0) FROM runs").fetchone()[0]
            clauses, args = ["rowid <= ?"], [ceiling]
            if status:
                clauses.append("status = ?")
                args.append(status)
            if seek:
                clauses.append("(started_at, id) < (?, ?)")
                args.extend(seek["after"])
            args.append(limit + 1)
            rows = archive.execute("SELECT summary FROM runs WHERE " + " AND ".join(clauses)
                                   + " ORDER BY started_at DESC, id DESC LIMIT ?", args).fetchall()
            records = [json.loads(row["summary"]) for row in rows]
    else:
        identity = "legacy"
        ceiling = 0
        records = [row for row in _legacy(state_dir) if not status or row.get("status") == status]
        if seek:
            records = [row for row in records if (str(row.get("started_at") or ""), row["id"]) < tuple(seek["after"])]
        records = records[:limit + 1]
    more = len(records) > limit
    items = [_summary(row) for row in records[:limit]]
    next_cursor = None
    if more:
        # Seek using stored ordering keys, even if an invalid legacy date was
        # rendered as unavailable. Presentation normalization must not skip rows.
        last = records[limit - 1]
        next_cursor = _encode({"v": 1, "status": status, "mode": mode, "archive_id": identity,
                               "ceiling": ceiling, "after": [last["started_at"] or "", last["id"]]})
    return {"items": items, "next_cursor": next_cursor, "mode": mode,
            "archive_started_at": archived_since, "legacy_retention_unknown": True}


def history_detail(state_dir: Path, run_id: str):
    if not run_id or len(run_id) > 160:
        raise DomainError("Deployment attempt not found.", 404, "not_found")
    if (state_dir / "history.sqlite3").exists():
        with _archive(state_dir) as archive:
            row = archive.execute("SELECT detail FROM runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise DomainError("Deployment attempt not found.", 404, "not_found")
            if len(row["detail"].encode()) > MAX_FILE_BYTES:
                raise DomainError("This deployment record exceeds the readable detail limit.", 503, "deployment_history_unavailable")
            return _detail(json.loads(row["detail"]))
    for run in _legacy(state_dir):
        if run["id"] == run_id:
            return _detail(run)
    raise DomainError("Deployment attempt not found.", 404, "not_found")
