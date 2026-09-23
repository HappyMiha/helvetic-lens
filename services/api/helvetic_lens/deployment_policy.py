"""Administrator settings shared with the host through an isolated SQLite mount.

Protocol v1: the API owns schema/settings; the standalone host controller reads
settings and atomically clears `next` while inserting an immutable attempt claim.
There is no command, path, environment or executable content in this protocol.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import DomainError
from .deployment_history import redact

Profile = Literal["standard", "full", "hotfix"]


class Choice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: Profile
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def check_reason(self):
        self.reason = self.reason.strip() if self.reason else None
        if self.profile == "hotfix":
            if self.reason is None or len(self.reason) < 10:
                raise ValueError("Hotfix requires a reason of 10–500 characters; do not include secrets.")
        elif self.reason is not None:
            raise ValueError("A reason applies only to hotfix.")
        return self


class PolicyDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default: Choice = Field(default_factory=lambda: Choice(profile="standard"))
    next: Choice | None = None
    updated_at: str | None = None


class PolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0, strict=True)
    scope: Literal["default", "next"]
    profile: Profile | None = None
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def check_choice(self):
        if self.profile is None:
            if self.scope != "next" or self.reason is not None:
                raise ValueError("Only the next deployment override can be cleared.")
        else:
            choice = Choice(profile=self.profile, reason=self.reason)
            self.reason = redact(choice.reason)[:500] if choice.reason else None
        return self


@contextmanager
def _database(directory: Path):
    connection = None
    try:
        directory.mkdir(parents=True, exist_ok=True, mode=0o2770)
        path = directory / "policy.sqlite3"
        if directory.is_symlink() or path.is_symlink():
            raise ValueError("Symlink policy storage is not supported.")
        # The host creates a setgid directory. Group-readable/writable files let
        # the unprivileged host controller consume API-created settings.
        fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o660)
        os.close(fd)
        if os.name != "nt" and path.stat().st_uid == os.getuid():
            path.chmod(0o660)
        connection = sqlite3.connect(path, timeout=3)
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN IMMEDIATE")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in {0, 1}:
            raise ValueError("Unsupported deployment policy schema.")
        connection.execute("CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), "
                           "revision INTEGER NOT NULL, document TEXT NOT NULL)")
        connection.execute("CREATE TABLE IF NOT EXISTS claims (run_id TEXT PRIMARY KEY, target_sha TEXT NOT NULL, "
                           "profile TEXT NOT NULL, reason TEXT, source TEXT NOT NULL, "
                           "settings_revision INTEGER NOT NULL, claimed_at TEXT NOT NULL)")
        connection.execute("CREATE TABLE IF NOT EXISTS edits (revision INTEGER PRIMARY KEY, actor TEXT NOT NULL, "
                           "changed_at TEXT NOT NULL, scope TEXT NOT NULL, document TEXT NOT NULL)")
        connection.execute("INSERT OR IGNORE INTO settings VALUES (1, 0, ?)", (PolicyDocument().model_dump_json(),))
        connection.execute("PRAGMA user_version=1")
        connection.commit()
        yield connection
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise DomainError("Deployment mode settings are unavailable. Retry after the host recovers.",
                          503, "deployment_policy_unavailable") from exc
    finally:
        if connection is not None:
            connection.close()


def _snapshot(connection):
    row = connection.execute("SELECT revision, document FROM settings WHERE id=1").fetchone()
    if row is None or type(row["revision"]) is not int or row["revision"] < 0 or len(row["document"]) > 16_384:
        raise ValueError("Malformed deployment policy.")
    document = PolicyDocument.model_validate_json(row["document"])
    for choice in (document.default, document.next):
        if choice and choice.reason:
            choice.reason = redact(choice.reason)[:500]
    return {"enabled": True, "revision": row["revision"], **document.model_dump()}


def read_policy(directory: Path | None):
    if directory is None:
        return {"enabled": False, "revision": 0, **PolicyDocument().model_dump()}
    with _database(directory) as connection:
        return _snapshot(connection)


def update_policy(directory: Path | None, change: PolicyUpdate, *, actor: str):
    if directory is None:
        raise DomainError("Deployment mode settings are not configured on this host.",
                          503, "deployment_policy_unavailable")
    with _database(directory) as connection:
        connection.execute("BEGIN IMMEDIATE")
        current = _snapshot(connection)
        if current["revision"] != change.expected_revision:
            raise DomainError("Deployment settings changed. Reload them before saving again.",
                              409, "deployment_policy_conflict")
        document = {key: current[key] for key in ("default", "next", "updated_at")}
        document[change.scope] = {"profile": change.profile, "reason": change.reason} if change.profile else None
        document["updated_at"] = datetime.now(UTC).isoformat()
        encoded = json.dumps(document)
        revision = current["revision"] + 1
        connection.execute("UPDATE settings SET revision=?, document=? WHERE id=1", (revision, encoded))
        connection.execute("INSERT INTO edits VALUES (?, ?, ?, ?, ?)",
                           (revision, actor, document["updated_at"], change.scope, encoded))
        connection.commit()
        return {"enabled": True, "revision": revision, **document}
