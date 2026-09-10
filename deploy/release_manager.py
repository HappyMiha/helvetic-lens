#!/usr/bin/env python3
"""Poll Git and deploy immutable Helvetic Lens releases on the local server."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

if os.name == "nt":
    import msvcrt
else:
    import fcntl

SCHEMA_VERSION = 1
DEFAULT_BASE_DIR = Path("/srv/helvetic-lens")
DEFAULT_REPOSITORY = "https://github.com/HappyMiha/helvetic-lens.git"
WRITER_SERVICES = (
    "cloudflared",
    "web",
    "scheduler",
    "worker-ai",
    "worker-cpu",
    "api",
    "backup",
    "model-manager",
)
SECRET_KEY_PARTS = ("PASSWORD", "SECRET", "TOKEN", "CREDENTIAL", "API_KEY")
API_TEST_TIMEOUT_DEFAULT = 7200
CONFIG_REQUIRED = {
    "version", "instance", "branch", "compose_project", "docker_context", "base_dir",
    "source_repo", "control_dir", "releases_dir", "state_dir", "env_file", "tunnel_dir",
    "expected_repository", "public_url", "self_update",
}
CONFIG_OPTIONAL = {"qa_cpus", "qa_memory", "qa_user", "api_test_timeout_seconds"}


def load_config(path: Path) -> dict[str, Any]:
    """A deployment selector, never an alternate store for application secrets."""
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or set(value) - CONFIG_REQUIRED - CONFIG_OPTIONAL:
        raise ValueError("Deployment configuration contains unsupported fields.")
    if CONFIG_REQUIRED - set(value):
        raise ValueError("Deployment configuration is missing required selector fields.")
    if type(value["version"]) is not int or value["version"] != 1:
        raise ValueError("Unsupported deployment configuration version.")
    if value["self_update"] is not False:
        raise ValueError("Configured instances require a separately pinned controller (self_update=false).")
    for name in CONFIG_REQUIRED - {"version", "self_update"}:
        if not isinstance(value[name], str) or not value[name] or any(ord(c) < 32 for c in value[name]):
            raise ValueError(f"Invalid deployment selector: {name}.")
    for name in ("instance", "compose_project", "docker_context"):
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,62}", value[name]):
            raise ValueError(f"Invalid deployment selector: {name}.")
    if value["compose_project"] == "helvetic-lens" or value["branch"] == "main":
        raise ValueError("An independent instance cannot target the main project or main branch.")
    branch = value["branch"]
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", branch)
            or any(part in branch for part in ("..", "//"))
            or any(part.startswith(".") or part.endswith((".", ".lock")) or not part for part in branch.split("/"))):
        raise ValueError("Invalid application branch.")
    from urllib.parse import urlsplit
    for name in ("expected_repository", "public_url"):
        url = urlsplit(value[name])
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError(f"Invalid HTTPS selector: {name}.")
        if name == "public_url" and (url.path not in {"", "/"} or url.port not in {None, 443}):
            raise ValueError("public_url must be an HTTPS origin.")
    base = Path(value["base_dir"]).resolve()
    if not Path(value["base_dir"]).is_absolute() or base == Path(base.anchor):
        raise ValueError("base_dir must be an absolute dedicated directory.")
    paths = []
    for name in ("source_repo", "control_dir", "releases_dir", "state_dir", "env_file", "tunnel_dir"):
        original = Path(value[name])
        resolved = original.resolve()
        if not original.is_absolute() or resolved == base or not resolved.is_relative_to(base):
            raise ValueError(f"{name} must be inside the dedicated base_dir.")
        paths.append((name, resolved))
    for index, (name, current) in enumerate(paths):
        for other_name, other in paths[index + 1:]:
            if current.is_relative_to(other) or other.is_relative_to(current):
                raise ValueError(f"Instance paths must not overlap: {name}/{other_name}.")
    if not re.fullmatch(r"(?:[1-9][0-9]?)(?:\.[0-9]+)?", str(value.get("qa_cpus", "2"))):
        raise ValueError("qa_cpus must be a positive bounded CPU count.")
    if not re.fullmatch(r"[1-9][0-9]{0,2}[mg]", str(value.get("qa_memory", "4g"))):
        raise ValueError("qa_memory must be an explicit Docker memory budget.")
    if not re.fullmatch(r"[1-9][0-9]*:[1-9][0-9]*", str(value.get("qa_user", "1000:1000"))):
        raise ValueError("qa_user must specify a non-root Linux UID:GID.")
    timeout = value.get("api_test_timeout_seconds", API_TEST_TIMEOUT_DEFAULT)
    if type(timeout) is not int or not 300 <= timeout <= 21600:
        raise ValueError("api_test_timeout_seconds must be between 300 and 21600.")
    return value


@contextmanager
def deployment_lock(path: Path) -> Iterator[bool]:
    """Never unlink this file: the installer and runner lock the same first byte."""
    with path.open("a+b") as stream:
        try:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, PermissionError):
            yield False
            return
        try:
            yield True
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def api_test_timeout() -> int:
    """Host operator budget; fail closed on a typo rather than disabling the gate."""
    value = os.getenv("HELVETIC_LENS_API_TEST_TIMEOUT_SECONDS", str(API_TEST_TIMEOUT_DEFAULT))
    try:
        seconds = int(value)
    except ValueError as exc:
        raise ValueError("HELVETIC_LENS_API_TEST_TIMEOUT_SECONDS must be an integer") from exc
    if not 300 <= seconds <= 21600:
        raise ValueError("HELVETIC_LENS_API_TEST_TIMEOUT_SECONDS must be between 300 and 21600")
    return seconds


def now() -> datetime:
    return datetime.now(UTC)


def timestamp(value: datetime | None = None) -> str:
    return (value or now()).isoformat(timespec="seconds")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def release_prefix(release: str | None) -> str | None:
    match = re.match(r"^(?:git-)?([0-9a-f]{7,40})(?:$|[-_.])", release or "")
    return match.group(1) if match else None


def normalize_remote(value: str) -> str:
    normalized = value.strip().rstrip("/")
    return normalized.removesuffix(".git")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o644)
    temporary.replace(path)


def atomic_update_release(path: Path, release: str) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    updated = False
    output: list[str] = []
    for line in lines:
        if line.startswith("HELVETIC_LENS_RELEASE="):
            output.append(f"HELVETIC_LENS_RELEASE={release}")
            updated = True
        else:
            output.append(line)
    if not updated:
        output.insert(0, f"HELVETIC_LENS_RELEASE={release}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text("\n".join(output) + "\n", encoding="utf-8")
    temporary.chmod(path.stat().st_mode & 0o777)
    temporary.replace(path)


class DeploymentError(RuntimeError):
    def __init__(self, step: str, detail: str):
        super().__init__(detail)
        self.step = step
        self.detail = detail


class ReleaseManager:
    def __init__(self, config_path: Path | None = None, *, bootstrap: bool = False) -> None:
        config = load_config(config_path) if config_path else {}
        self.instance = config.get("instance")
        self.bootstrap = bootstrap
        if bootstrap and not config:
            raise ValueError("Bootstrap requires an explicit independent instance configuration.")
        self.base_dir = Path(os.getenv("HELVETIC_LENS_BASE_DIR", DEFAULT_BASE_DIR))
        self.source_repo = Path(
            os.getenv("HELVETIC_LENS_SOURCE_REPO", self.base_dir / "helvetic-lens")
        )
        self.control_dir = Path(
            os.getenv("HELVETIC_LENS_DEPLOY_CONTROL_DIR", self.base_dir / "deploy-control")
        )
        self.releases_dir = Path(
            os.getenv("HELVETIC_LENS_RELEASES_DIR", self.base_dir / "releases")
        )
        self.state_dir = Path(
            os.getenv("HELVETIC_LENS_DEPLOY_STATE_DIR", self.base_dir / "deploy-state")
        )
        self.env_file = Path(
            os.getenv("HELVETIC_LENS_PRODUCTION_ENV", self.source_repo / ".env.production")
        )
        self.tunnel_dir = Path(
            os.getenv("HELVETIC_LENS_TUNNEL_DIR", self.source_repo / ".cloudflared")
        )
        self.remote = os.getenv("HELVETIC_LENS_GIT_REMOTE", "origin")
        self.branch = os.getenv("HELVETIC_LENS_GIT_BRANCH", "main")
        self.expected_repository = os.getenv(
            "HELVETIC_LENS_EXPECTED_REPOSITORY", DEFAULT_REPOSITORY
        )
        self.poll_seconds = int(os.getenv("HELVETIC_LENS_DEPLOY_POLL_SECONDS", "120"))
        self.retry_seconds = int(os.getenv("HELVETIC_LENS_DEPLOY_RETRY_SECONDS", "900"))
        self.history_limit = int(os.getenv("HELVETIC_LENS_DEPLOY_HISTORY_LIMIT", "30"))
        if config:
            for name in ("base_dir", "source_repo", "control_dir", "releases_dir", "state_dir", "env_file", "tunnel_dir"):
                setattr(self, name, Path(config[name]).resolve())
            self.remote = "origin"
            self.branch = config["branch"]
            self.expected_repository = config["expected_repository"]
        self.compose_project = config.get("compose_project", "helvetic-lens")
        self.docker_context = config.get("docker_context")
        self.public_url = config.get("public_url")
        self.self_update = config.get("self_update", True)
        self.qa_cpus = str(config.get("qa_cpus", "2"))
        self.qa_memory = str(config.get("qa_memory", "4g"))
        self.qa_user = str(config.get("qa_user", "1000:1000")) if os.name == "nt" or config else f"{os.getuid()}:{os.getgid()}"
        self.api_timeout = config.get("api_test_timeout_seconds", api_test_timeout())
        self.status_path = self.state_dir / "status.json"
        self.history_path = self.state_dir / "history.json"
        self.deployed_path = self.control_dir / "deployed.json"
        self.lock_path = self.control_dir / "deployment.lock"
        self.log_dir = self.state_dir / "logs"
        self.cache_dir = self.control_dir / "uv-cache"
        self.run_record: dict[str, Any] | None = None
        self.status = self._load_status()
        self.env_values = read_env(self.env_file)
        if config:
            if any(key.startswith(("COMPOSE_", "DOCKER_")) for key in self.env_values):
                raise ValueError("Application env_file must not contain reserved COMPOSE_ or DOCKER_ selectors.")
            if self.env_values.get("PUBLIC_BASE_URL", "").rstrip("/") != self.public_url.rstrip("/"):
                raise ValueError("Instance public_url and PUBLIC_BASE_URL must match.")
            backup = Path(self.env_values.get("HELVETIC_LENS_BACKUP_DIR", ""))
            if (not backup.is_absolute() or backup.resolve() == Path(backup.anchor)
                    or backup.resolve() == self.base_dir
                    or any(backup.resolve().is_relative_to(p) or p.is_relative_to(backup.resolve())
                           for p in (self.source_repo, self.control_dir, self.releases_dir, self.state_dir, self.env_file, self.tunnel_dir))):
                raise ValueError("The instance requires an absolute separate backup directory.")
        self.secrets = [
            value
            for key, value in self.env_values.items()
            if value and len(value) >= 4 and any(part in key.upper() for part in SECRET_KEY_PARTS)
        ]
        self.log_path: Path | None = None

    def _executable(self, name: str) -> str:
        if name == "python3":
            return sys.executable if os.name == "nt" else "/usr/bin/python3"
        return (shutil.which(name) or name) if os.name == "nt" else f"/usr/bin/{name}"

    def _docker(self, *arguments: str) -> list[str]:
        prefix = [self._executable("docker")]
        context = getattr(self, "docker_context", None)
        if context:
            prefix.extend(["--context", context])
        return [*prefix, *arguments]

    def _load_json(self, path: Path, fallback: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
            return fallback

    def _load_status(self) -> dict[str, Any]:
        loaded = self._load_json(self.status_path, {})
        return loaded if isinstance(loaded, dict) else {}

    def _load_deployed(self) -> dict[str, Any]:
        loaded = self._load_json(self.deployed_path, {})
        return loaded if isinstance(loaded, dict) else {}

    def _history(self) -> list[dict[str, Any]]:
        loaded = self._load_json(self.history_path, [])
        return loaded if isinstance(loaded, list) else []

    def _redact(self, value: str) -> str:
        result = value
        for secret in sorted(self.secrets, key=len, reverse=True):
            result = result.replace(secret, "[redacted]")
        result = re.sub(r"(https?://[^:/\s]+:)[^@\s]+@", r"\1[redacted]@", result)
        result = re.sub(r"(?i)\bBearer\s+[^\s\"'<>]+", "Bearer [redacted]", result)
        result = re.sub(r"(?i)((?:password|secret|token|api[_-]?key|authorization)[\"']?\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)", r"\1[redacted]", result)
        return result

    def _log(self, message: str) -> None:
        if self.log_path is None:
            return
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"[{timestamp()}] {self._redact(message).rstrip()}\n")

    def _run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        step: str,
        check: bool = True,
        timeout: int = 3600,
    ) -> subprocess.CompletedProcess[str]:
        self._log("$ " + " ".join(command))
        process_env = dict(os.environ if env is None else env)
        process_env.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
        if getattr(self, "instance", None):
            for name in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
                process_env.pop(name, None)
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=process_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                timeout=timeout,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except subprocess.TimeoutExpired as exc:
            partial = exc.output or ""
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", errors="replace")
            output = self._redact(partial)
            if output:
                self._log(output)
            excerpt = "\n".join(output.strip().splitlines()[-40:])[-6500:]
            detail = f"{step} exceeded its {timeout}-second time limit. This is not a passing test result."
            detail += (f"\nLast captured output:\n{excerpt}" if excerpt else "\nNo command output was captured.")
            raise DeploymentError(step, detail) from exc
        except OSError as exc:
            raise DeploymentError(step, self._redact(f"Unable to run {step}: {exc}")) from exc
        output = self._redact(completed.stdout or "")
        if output:
            self._log(output)
        if check and completed.returncode != 0:
            excerpt = "\n".join(output.strip().splitlines()[-24:])
            detail = f"{step} failed with exit code {completed.returncode}."
            if excerpt:
                detail += f"\n{excerpt}"
            raise DeploymentError(step, detail[:8_000])
        return completed

    def _git(self, *arguments: str, step: str = "git") -> str:
        completed = self._run(
            [self._executable("git"), "-C", str(self.source_repo), *arguments],
            step=step,
        )
        return completed.stdout.strip()

    def _resolve_commit(self, revision: str | None) -> str | None:
        if not revision:
            return None
        completed = self._run(
            [self._executable("git"), "-C", str(self.source_repo), "rev-parse", f"{revision}^{{commit}}"],
            step="resolve_release",
            check=False,
        )
        value = completed.stdout.strip()
        return value if completed.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", value) else None

    def _commit_summary(self, sha: str | None) -> str | None:
        if not sha:
            return None
        completed = self._run(
            [self._executable("git"), "-C", str(self.source_repo), "show", "-s", "--format=%s", sha],
            step="commit_summary",
            check=False,
        )
        return completed.stdout.strip()[:300] if completed.returncode == 0 else None

    def _bootstrap_deployed(self) -> dict[str, Any]:
        deployed = self._load_deployed()
        if getattr(self, "instance", None):
            if deployed.get("sha"):
                if self.bootstrap:
                    raise DeploymentError("bootstrap", "This instance already has a deployed release; use --poll.")
                if not re.fullmatch(r"[0-9a-f]{40}", str(deployed["sha"])):
                    raise DeploymentError("bootstrap", "The instance deployment record has an invalid SHA.")
                return deployed
            if not self.bootstrap:
                raise DeploymentError("bootstrap", "No verified release exists for this instance; use explicit --bootstrap.")
            return {}
        if deployed.get("sha"):
            return deployed
        current_release = self.env_values.get("HELVETIC_LENS_RELEASE")
        current_sha = self._resolve_commit(release_prefix(current_release))
        release_dir = self._ensure_release(current_sha) if current_sha else self.source_repo
        deployed = {
            "sha": current_sha,
            "release": current_release,
            "summary": self._commit_summary(current_sha),
            "deployed_at": None,
            "release_dir": str(release_dir),
        }
        atomic_json(self.deployed_path, deployed)
        return deployed

    def _public_current(self, deployed: dict[str, Any]) -> dict[str, Any]:
        return {
            "sha": deployed.get("sha"),
            "release": deployed.get("release"),
            "summary": deployed.get("summary"),
            "deployed_at": deployed.get("deployed_at"),
        }

    def _base_status(self, deployed: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "service": {
                "enabled": True,
                "state": "idle",
                "poll_interval_seconds": self.poll_seconds,
                "last_checked_at": self.status.get("service", {}).get("last_checked_at"),
                "next_retry_at": None,
            },
            "remote": self.status.get("remote")
            or {
                "repository": normalize_remote(self.expected_repository),
                "branch": self.branch,
                "sha": None,
                "checked_at": None,
            },
            "current": self._public_current(deployed),
            "last_run": self.status.get("last_run"),
        }

    def _save_status(self) -> None:
        atomic_json(self.status_path, self.status)
        run = self.status.get("last_run")
        if isinstance(run, dict) and run.get("id"):
            self._archive_run(run)

    def _archive_run(self, run: dict[str, Any]) -> None:
        """Keep every attempt independently of the legacy 30-entry snapshot.

        SQLite is a host-side journal using only the Python standard library.
        The API opens it read-only; application PostgreSQL is not required for
        recording failures that happen while the application itself is down.
        """
        self.state_dir.mkdir(parents=True, exist_ok=True)
        path = self.state_dir / "history.sqlite3"
        def sanitized(value):
            if isinstance(value, str):
                return self._redact(value)
            if isinstance(value, dict):
                return {key: sanitized(item) for key, item in value.items()}
            if isinstance(value, list):
                return [sanitized(item) for item in value]
            return value

        with sqlite3.connect(path, timeout=10) as archive:
            archive.execute("BEGIN IMMEDIATE")
            archive.execute("""CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, started_at TEXT NOT NULL, status TEXT NOT NULL,
                summary TEXT NOT NULL, detail TEXT NOT NULL)""")
            archive.execute("CREATE INDEX IF NOT EXISTS runs_chronology ON runs(started_at DESC, id DESC)")
            archive.execute("CREATE INDEX IF NOT EXISTS runs_status ON runs(status, started_at DESC, id DESC)")
            archive.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            def save(record):
                if not isinstance(record, dict) or not isinstance(record.get("id"), str):
                    return
                record = sanitized(record)
                summary = {key: record.get(key) for key in (
                    "id", "kind", "status", "target_sha", "previous_sha", "activated_sha",
                    "release", "started_at", "finished_at", "duration_seconds", "host", "environment",
                    "error_step", "interrupted_at",
                )}
                archive.execute("""INSERT INTO runs(id, started_at, status, summary, detail)
                    VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status, summary=excluded.summary, detail=excluded.detail
                    WHERE runs.status IN ('deploying', 'running')""",
                    (record["id"], record.get("started_at") or "", record.get("status") or "unknown",
                     json.dumps(summary, ensure_ascii=False), json.dumps(record, ensure_ascii=False)))
            if not archive.execute("SELECT value FROM metadata WHERE key='archive_started_at'").fetchone():
                for previous in self._history():
                    save(previous)
                archive.execute("INSERT INTO metadata VALUES ('archive_started_at', ?)", (timestamp(),))
                archive.execute("INSERT INTO metadata VALUES ('archive_id', ?)", (str(uuid.uuid4()),))
                archive.execute("INSERT INTO metadata VALUES ('legacy_retention_unknown', 'true')")
            save(run)
        path.chmod(0o644)  # Read-only API mount; no environment secrets in this journal.

    def _save_history(self, run: dict[str, Any]) -> None:
        self._archive_run(run)
        history = [run, *[item for item in self._history() if item.get("id") != run.get("id")]]
        atomic_json(self.history_path, history[: self.history_limit])

    @contextmanager
    def step(self, name: str) -> Iterator[None]:
        if self.run_record is None:
            yield
            return
        item = {"name": name, "status": "running", "started_at": timestamp()}
        self.run_record["steps"].append(item)
        self.status["last_run"] = self.run_record
        self._save_status()
        started = time.monotonic()
        try:
            yield
        except Exception as error:
            item["status"] = "failed"
            item["error"] = self._redact(str(error))[:8_000]
            item["error_truncated"] = len(self._redact(str(error))) > 8_000
            raise
        else:
            item["status"] = "succeeded"
        finally:
            item["finished_at"] = timestamp()
            item["duration_seconds"] = round(time.monotonic() - started, 1)
            self._save_status()

    def _ensure_release(self, sha: str | None) -> Path:
        if not sha or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise DeploymentError("checkout", "The release commit is not a full Git SHA.")
        destination = self.releases_dir / sha
        if destination.exists():
            completed = self._run(
                [self._executable("git"), "-C", str(destination), "rev-parse", "HEAD"],
                step="checkout",
                check=False,
            )
            if completed.returncode == 0 and completed.stdout.strip() == sha:
                if getattr(self, "instance", None):
                    changes = self._run(
                        [self._executable("git"), "-C", str(destination), "status", "--porcelain", "--untracked-files=all", "--ignored"],
                        step="checkout",
                    )
                    if changes.stdout.strip():
                        raise DeploymentError("checkout", "The immutable release directory has local changes or extra files.")
                self._link_runtime_configuration(destination)
                return destination
            raise DeploymentError("checkout", f"Existing release directory does not match {sha[:12]}.")
        self.releases_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        self._run(
            [
                self._executable("git"),
                "-c", "core.autocrlf=false",
                "-C",
                str(self.source_repo),
                "worktree",
                "add",
                "--detach",
                str(destination),
                sha,
            ],
            step="checkout",
        )
        self._link_runtime_configuration(destination)
        return destination

    def _link_runtime_configuration(self, release_dir: Path) -> None:
        if not self.tunnel_dir.is_dir():
            raise DeploymentError("checkout", "Cloudflare Tunnel configuration directory is missing.")
        if getattr(self, "instance", None):
            # Configured instances mount the protected directory directly. No
            # privileged Windows symlink or credential path in build contexts.
            token = self.tunnel_dir / "token"
            if not token.is_file() or token.stat().st_size == 0:
                raise DeploymentError("checkout", "The dedicated tunnel token file is missing or empty.")
            return
        link = release_dir / ".cloudflared"
        if link.is_symlink() and link.resolve() == self.tunnel_dir.resolve():
            return
        if link.exists() or link.is_symlink():
            raise DeploymentError("checkout", "Release checkout contains an unexpected .cloudflared path.")
        link.symlink_to(self.tunnel_dir, target_is_directory=True)

    def _compose_environment(self, release: str) -> dict[str, str]:
        environment = os.environ.copy()
        if getattr(self, "instance", None):
            environment = {key: value for key, value in environment.items() if not key.startswith("COMPOSE_")}
            environment.update(self.env_values)
            environment["HELVETIC_LENS_INSTANCE"] = self.instance
            environment["HELVETIC_LENS_TUNNEL_DIR"] = str(self.tunnel_dir)
        environment["HELVETIC_LENS_RELEASE"] = release
        environment["HELVETIC_LENS_CONFIG_FILE"] = str(self.env_file)
        environment["HELVETIC_LENS_DEPLOY_STATE_DIR"] = str(self.state_dir)
        return environment

    def _compose(self, release_dir: Path, release: str, *arguments: str) -> list[str]:
        return [
            *self._docker(),
            "compose",
            "--project-name",
            getattr(self, "compose_project", "helvetic-lens"),
            "--project-directory",
            str(release_dir),
            "--env-file",
            str(self.env_file),
            "-f",
            str(release_dir / "compose.production.yaml"),
            "-f",
            str(release_dir / "compose.cloudflare-tunnel.yaml"),
            *(["-f", str(release_dir / "compose.monitoring.yaml")] if getattr(self, "instance", None) else []),
            *arguments,
        ]

    def _compose_run(
        self,
        release_dir: Path,
        release: str,
        *arguments: str,
        step: str,
        check: bool = True,
        timeout: int = 3600,
    ) -> subprocess.CompletedProcess[str]:
        return self._run(
            self._compose(release_dir, release, *arguments),
            cwd=release_dir,
            env=self._compose_environment(release),
            step=step,
            check=check,
            timeout=timeout,
        )

    def _changes(self, previous_sha: str | None, target_sha: str) -> list[dict[str, str]]:
        revision = f"{previous_sha}..{target_sha}" if previous_sha else target_sha
        completed = self._run(
            [
                self._executable("git"),
                "-C",
                str(self.source_repo),
                "log",
                "--reverse",
                "--max-count=50",
                "--format=%H%x1f%h%x1f%s%x1f%an%x1f%aI",
                revision,
            ],
            step="describe_changes",
        )
        changes = []
        for line in completed.stdout.splitlines():
            fields = line.split("\x1f")
            if len(fields) == 5:
                changes.append(
                    {
                        "sha": fields[0],
                        "short_sha": fields[1],
                        "subject": fields[2][:300],
                        "author": fields[3][:150],
                        "committed_at": fields[4],
                    }
                )
        return changes

    def _run_api_quality_gate(self, release_dir: Path, command: str, step: str) -> None:
        timeout = getattr(self, "api_timeout", api_test_timeout()) if step == "api_tests" else 1800
        self.cache_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        context = release_dir / "deploy" / "api-quality"
        # Build from a tiny, secret-free context, and cache by the reviewed recipe.
        recipe_hash = hashlib.sha256((context / "Dockerfile").read_bytes()).hexdigest()[:16]
        image = f"helvetic-lens-api-quality:{recipe_hash}"
        self._run(
            self._docker("build", "--tag", image, str(context)),
            step=step,
            timeout=600,
        )
        container = f"helvetic-api-qa-{uuid.uuid4().hex}"
        run_command = [
            *self._docker(), "run", "--rm", "--init", "--name", container,
            "--label", "helvetic-lens.purpose=deployment-quality-gate",
            "--user", getattr(self, "qa_user", "1000:1000" if os.name == "nt" else f"{os.getuid()}:{os.getgid()}"),
            "-e", "HOME=/tmp",
            "-e", "UV_CACHE_DIR=/cache",
            "-e", "UV_PROJECT_ENVIRONMENT=/tmp/helvetic-lens-venv",
            "-e", "RUFF_CACHE_DIR=/tmp/ruff-cache",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-e", "PYTHONUNBUFFERED=1",
            "-e", "HELVETIC_LENS_DATA_DIR=/tmp/helvetic-lens-data",
            "-e", "PYTHONPATH=/workspace",
            "-v", f"{release_dir}:/workspace:ro",
            "-v", f"{self.cache_dir}:/cache",
            "-w", "/workspace", image, "uv", "run", "--frozen", *command.split(),
        ]
        if getattr(self, "instance", None):
            insertion = run_command.index("--user")
            run_command[insertion:insertion] = ["--cpus", self.qa_cpus, "--memory", self.qa_memory,
                                              "--memory-swap", self.qa_memory, "--pids-limit", "512"]
        failure = None
        try:
            self._run(run_command, step=step, timeout=timeout)
        except BaseException as exc:
            failure = exc
            raise
        finally:
            # A timeout kills the Docker CLI, not necessarily its container.
            # This UUID identifies only this gate; never prune the host or volumes.
            try:
                cleanup = self._run(self._docker("rm", "--force", container),
                    step=f"{step}_cleanup", check=False, timeout=60)
                if cleanup.returncode and "No such container" not in (cleanup.stdout or ""):
                    raise DeploymentError(step, "Could not confirm removal of the quality-gate container.")
            except DeploymentError as cleanup_error:
                self._log(f"Quality-gate cleanup needs attention: {cleanup_error}")
                if failure is None:
                    raise
                if isinstance(failure, DeploymentError):
                    failure.detail += f"\nCleanup could not be confirmed for test container {container}; inspect it on the host."
                    failure.args = (failure.detail,)

    def _public_health(self) -> None:
        public_base = self.env_values.get("PUBLIC_BASE_URL", "").rstrip("/")
        if not public_base.startswith("https://"):
            raise DeploymentError("health_check", "PUBLIC_BASE_URL is not a public HTTPS URL.")
        last_error = "no response"
        for _attempt in range(12):
            try:
                ready_request = urllib.request.Request(
                    f"{public_base}/api/ready",
                    headers={"User-Agent": "HelveticLens-ReleaseManager/1.0", "Accept": "application/json"},
                )
                with urllib.request.urlopen(ready_request, timeout=10) as response:
                    ready = json.loads(response.read(64 * 1024))
                    if response.status != 200 or ready.get("status") != "ready":
                        raise ValueError(f"readiness returned {response.status}: {ready}")
                    if getattr(self, "instance", None) and (
                        ready.get("instance") != self.instance
                        or ready.get("release") != getattr(self, "health_release", None)
                    ):
                        raise ValueError("The public endpoint is not the expected instance and release.")
                login_request = urllib.request.Request(
                    f"{public_base}/login",
                    headers={"User-Agent": "HelveticLens-ReleaseManager/1.0", "Accept": "text/html"},
                )
                with urllib.request.urlopen(login_request, timeout=10) as response:
                    body = response.read(256 * 1024)
                    if response.status != 200 or b"Helvetic Lens" not in body:
                        raise ValueError(f"login returned {response.status} without the product marker")
                return
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                last_error = str(exc)
                time.sleep(5)
        raise DeploymentError("health_check", f"Public health check failed: {last_error}"[:2_000])

    def _model_deployment(self, step: str) -> dict[str, Any]:
        code = (
            "import json,urllib.request;"
            "d=json.load(urllib.request.urlopen('http://127.0.0.1:8090/v1/inventory',timeout=10));"
            "print(json.dumps(d.get('deployment') or {}))"
        )
        completed = self._run(
            [
                *self._docker(),
                "exec",
                f"{getattr(self, 'compose_project', 'helvetic-lens')}-model-manager-1",
                "python3",
                "-c",
                code,
            ],
            step=step,
            timeout=30,
        )
        try:
            deployment = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise DeploymentError(step, "The model manager returned invalid deployment state.") from exc
        return deployment if isinstance(deployment, dict) else {}

    @staticmethod
    def _active_model_id(deployment: dict[str, Any]) -> str | None:
        model_id = deployment.get("model_id")
        if deployment.get("state") not in {"ready", "degraded", "starting"}:
            return None
        return model_id if isinstance(model_id, str) and re.fullmatch(r"[a-z0-9._-]+", model_id) else None

    def _restore_model_runtime(self, model_id: str) -> None:
        if not re.fullmatch(r"[a-z0-9._-]+", model_id):
            raise DeploymentError("restore_model_runtime", "The active model identifier is invalid.")
        code = (
            "import urllib.request;"
            f"r=urllib.request.Request('http://127.0.0.1:8090/v1/models/{model_id}/start',"
            "data=b'',method='POST');"
            "urllib.request.urlopen(r,timeout=30).read();print('accepted')"
        )
        self._run(
            [
                *self._docker(),
                "exec",
                f"{getattr(self, 'compose_project', 'helvetic-lens')}-model-manager-1",
                "python3",
                "-c",
                code,
            ],
            step="restore_model_runtime",
            timeout=60,
        )
        last_state = "starting"
        for _attempt in range(90):
            deployment = self._model_deployment("restore_model_runtime")
            last_state = str(deployment.get("state") or "stopped")
            if last_state == "ready" and int(deployment.get("available_slots") or 0) > 0:
                return
            if last_state == "error":
                raise DeploymentError(
                    "restore_model_runtime",
                    f"The local model runtime failed to restart: {deployment.get('error') or 'unknown error'}",
                )
            time.sleep(2)
        raise DeploymentError(
            "restore_model_runtime",
            f"The local model runtime did not become ready; last state was {last_state}.",
        )

    @staticmethod
    def _backup_id(output: str) -> str:
        matches = re.findall(r"\bBackup (20\d{6}T\d{6}Z) completed\.\s*$", output, re.MULTILINE)
        if not matches:
            raise DeploymentError("backup", "The backup service did not report a valid backup identifier.")
        return matches[-1]

    def _quiesce(self, release_dir: Path, release: str, *, check: bool = True) -> None:
        self._compose_run(
            release_dir,
            release,
            "stop",
            *WRITER_SERVICES,
            *(["migrate"] if getattr(self, "instance", None) else []),
            step="quiesce",
            check=check,
            timeout=300,
        )

    def _restore_previous(
        self,
        previous_dir: Path,
        previous_release: str,
        target_dir: Path,
        target_release: str,
        backup_id: str | None,
        target_started: bool,
        active_model_id: str | None,
    ) -> dict[str, Any]:
        rollback: dict[str, Any] = {"status": "running", "started_at": timestamp()}
        errors: list[str] = []
        try:
            self._quiesce(target_dir, target_release, check=bool(getattr(self, "instance", None)))
            if target_started and backup_id:
                environment = self._compose_environment(previous_release)
                environment["BACKUP_ID"] = backup_id
                environment["CONFIRM_RESTORE"] = backup_id
                self._run(
                    self._compose(
                        previous_dir,
                        previous_release,
                        "--profile",
                        "restore",
                        "run",
                        "--rm",
                        "-e",
                        "BACKUP_ID",
                        "-e",
                        "CONFIRM_RESTORE",
                        "restore",
                    ),
                    cwd=previous_dir,
                    env=environment,
                    step="rollback_restore",
                    timeout=1800,
                )
            self._compose_run(
                previous_dir,
                previous_release,
                "up",
                "-d",
                "--wait",
                "--wait-timeout",
                "300",
                "--remove-orphans",
                step="rollback_start",
                timeout=900,
            )
            if active_model_id:
                self._restore_model_runtime(active_model_id)
            self.health_release = previous_release
            self._public_health()
            if getattr(self, "instance", None):
                atomic_update_release(self.env_file, previous_release)
        except (DeploymentError, OSError, ValueError) as exc:
            errors.append(str(exc))
        rollback["finished_at"] = timestamp()
        rollback["status"] = "succeeded" if not errors else "failed"
        rollback["backup_restored"] = bool(target_started and backup_id and not errors)
        if errors:
            rollback["error"] = self._redact("\n".join(errors))[:4_000]
        return rollback

    def _install_manager_update(self, release_dir: Path) -> None:
        if not getattr(self, "self_update", True):
            return
        source = release_dir / "deploy" / "release_manager.py"
        destination = self.control_dir / "release_manager.py"
        if not source.is_file():
            return
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
        shutil.copyfile(source, temporary)
        temporary.chmod(0o755)
        temporary.replace(destination)

    def _assert_empty_instance(self) -> None:
        """First installation must not adopt an unexplained existing stack."""
        project = self.compose_project
        for resource, arguments in (
            ("containers", ["ps", "-aq", "--filter", f"label=com.docker.compose.project={project}"]),
            ("volumes", ["volume", "ls", "-q", "--filter", f"label=com.docker.compose.project={project}"]),
            ("networks", ["network", "ls", "-q", "--filter", f"label=com.docker.compose.project={project}"]),
        ):
            result = self._run(self._docker(*arguments), step="bootstrap", timeout=60)
            if result.stdout.strip():
                raise DeploymentError("bootstrap", f"Instance {resource} already exist; inspect and recover explicitly.")
        # Also catch unlabelled volumes that Compose could otherwise adopt.
        volumes = self._run(self._docker("volume", "ls", "--format", "{{.Name}}"), step="bootstrap", timeout=60)
        if any(name.startswith(project + "_") for name in volumes.stdout.splitlines()):
            raise DeploymentError("bootstrap", "Instance volume names already exist; adoption is prohibited.")
        networks = self._run(self._docker("network", "ls", "--format", "{{.Name}}"), step="bootstrap", timeout=60)
        if any(name.startswith(project + "_") for name in networks.stdout.splitlines()):
            raise DeploymentError("bootstrap", "Instance network names already exist; adoption is prohibited.")
        containers = self._run(self._docker("ps", "-a", "--format", "{{.Names}}"), step="bootstrap", timeout=60)
        if any(name.startswith(project + "-") for name in containers.stdout.splitlines()):
            raise DeploymentError("bootstrap", "Instance container names already exist; adoption is prohibited.")
        backup = Path(self.env_values["HELVETIC_LENS_BACKUP_DIR"])
        if backup.exists() and any(backup.iterdir()):
            raise DeploymentError("bootstrap", "The first-install backup directory is not empty.")

    def _stop_failed_bootstrap(self, target_dir: Path, release: str) -> dict[str, Any]:
        recovery = {"status": "not_required", "reason": "No previous release exists for this first installation.",
                    "backup_restored": False, "candidate_stopped": False}
        try:
            self._compose_run(target_dir, release, "stop", step="bootstrap_stop", timeout=300)
            recovery["candidate_stopped"] = True
        except DeploymentError as exc:
            recovery.update(status="failed", error=self._redact(str(exc)))
        return recovery

    def _record_poll_failure(self, error: Exception) -> None:
        checked_at = timestamp()
        deployed = self._load_deployed()
        rejected = isinstance(error, DeploymentError) and error.step in {"verify_remote", "verify_history"}
        rejected_target = self.status.get("remote", {}).get("sha") if rejected and error.step == "verify_history" else None
        run = {
            "id": str(uuid.uuid4()),
            "status": "rejected" if rejected else "failed",
            "kind": "poll",
            "target_sha": rejected_target,
            "previous_sha": deployed.get("sha"),
            "release": None,
            "started_at": checked_at,
            "finished_at": checked_at,
            "duration_seconds": 0,
            "changes": [],
            "steps": [],
            "backup_id": None,
            "model_id": None,
            "rollback": {"status": "not_required"},
            "error": self._redact(str(error))[:8_000],
            "error_step": error.step if isinstance(error, DeploymentError) else "poll",
            "host": socket.gethostname(),
            "environment": "production",
            "activated_sha": None,
        }
        self.status = self._base_status(deployed)
        self.status["service"].update(state="error", last_checked_at=checked_at)
        self.status["last_run"] = run
        self._save_status()
        self._save_history(run)

    def poll(self) -> None:
        self.control_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        self.log_dir.mkdir(parents=True, exist_ok=True, mode=0o750)
        self.cache_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        with deployment_lock(self.lock_path) as acquired:
            if not acquired:
                return
            try:
                self._poll_locked()
            except (DeploymentError, OSError, ValueError, json.JSONDecodeError) as exc:
                if self.run_record is None:
                    self._record_poll_failure(exc)
                raise

    def _poll_locked(self) -> None:
        # The host lock is held, so a saved unfinished run belongs to a previous
        # process. Record observation time, not a fabricated completion timestamp.
        previous_run = self.status.get("last_run")
        if isinstance(previous_run, dict) and previous_run.get("status") in {"deploying", "running"}:
            previous_run = json.loads(json.dumps(previous_run))
            previous_run.update(status="interrupted", interrupted_at=timestamp(),
                                error="The release manager restarted before this attempt recorded a final outcome.")
            for phase in previous_run.get("steps", []):
                if phase.get("status") == "running":
                    phase.update(status="interrupted", interrupted_at=previous_run["interrupted_at"])
            self.status["last_run"] = previous_run
            self._save_status()
            self._save_history(previous_run)
        repository = self._git("remote", "get-url", self.remote, step="verify_remote")
        if normalize_remote(repository) != normalize_remote(self.expected_repository):
            raise DeploymentError(
                "verify_remote",
                f"Refusing unexpected Git remote {normalize_remote(repository)}.",
            )
        self._git("fetch", "--prune", self.remote,
                  f"refs/heads/{self.branch}:refs/remotes/{self.remote}/{self.branch}", step="fetch")
        target_sha = self._git(
            "rev-parse", f"refs/remotes/{self.remote}/{self.branch}^{{commit}}", step="fetch"
        )
        if not re.fullmatch(r"[0-9a-f]{40}", target_sha):
            raise DeploymentError("fetch", "Remote branch did not resolve to a full commit SHA.")

        deployed = self._bootstrap_deployed()
        first_install = bool(getattr(self, "instance", None) and getattr(self, "bootstrap", False))
        if first_install:
            self._assert_empty_instance()
        checked_at = timestamp()
        self.status = self._base_status(deployed)
        self.status["remote"] = {
            "repository": normalize_remote(repository),
            "branch": self.branch,
            "sha": target_sha,
            "summary": self._commit_summary(target_sha),
            "checked_at": checked_at,
        }
        self.status["service"]["last_checked_at"] = checked_at

        if deployed.get("sha") == target_sha:
            self.status["service"]["state"] = "idle"
            self._save_status()
            return

        last_run = self.status.get("last_run") or {}
        last_finished = parse_iso(last_run.get("finished_at"))
        retry_at = last_finished + timedelta(seconds=self.retry_seconds) if last_finished else None
        if (
            last_run.get("status") in {"failed", "rollback_failed"}
            and last_run.get("target_sha") == target_sha
            and retry_at
            and now() < retry_at
        ):
            self.status["service"].update(state="retry_wait", next_retry_at=timestamp(retry_at))
            self._save_status()
            return

        previous_sha = deployed.get("sha")
        if previous_sha:
            ancestry = self._run(
                [
                    self._executable("git"),
                    "-C",
                    str(self.source_repo),
                    "merge-base",
                    "--is-ancestor",
                    previous_sha,
                    target_sha,
                ],
                step="verify_history",
                check=False,
            )
            if ancestry.returncode != 0:
                raise DeploymentError(
                    "verify_history",
                    "Remote branch is not a fast-forward from the deployed commit; manual review is required.",
                )

        release = f"git-{target_sha if getattr(self, 'instance', None) else target_sha[:12]}"
        run_started = now()
        self.log_path = self.log_dir / f"{run_started.strftime('%Y%m%dT%H%M%SZ')}-{target_sha[:12]}.log"
        self.log_path.touch(mode=0o640)
        self.run_record = {
            "id": str(uuid.uuid4()),
            "status": "deploying",
            "kind": "release",
            "target_sha": target_sha,
            "previous_sha": previous_sha,
            "release": release,
            "started_at": timestamp(run_started),
            "finished_at": None,
            "duration_seconds": None,
            "changes": self._changes(previous_sha, target_sha),
            "steps": [],
            "backup_id": None,
            "model_id": None,
            "rollback": {"status": "not_required"},
            "error": None,
            "log_id": self.log_path.name,
            "host": socket.gethostname(),
            "environment": "production",
            "activated_sha": None,
            "repository": normalize_remote(repository),
        }
        self.run_record["release_notes"] = {
            "kind": "commit_summary",
            "previous_sha": previous_sha,
            "target_sha": target_sha,
            "captured_at": timestamp(),
            "text": "\n".join("- " + change["subject"] for change in self.run_record["changes"]),
            "repository_notes_available": False,
            "changes_may_be_truncated": len(self.run_record["changes"]) == 50,
        }
        self.status["service"]["state"] = "deploying"
        self.status["last_run"] = self.run_record
        self._save_status()

        previous_release = deployed.get("release") or self.env_values.get("HELVETIC_LENS_RELEASE")
        previous_dir: Path | None = None
        target_dir: Path | None = None
        quiesced = False
        target_started = False
        backup_id: str | None = None
        active_model_id: str | None = None
        try:
            with self.step("checkout"):
                target_dir = self._ensure_release(target_sha)
                if previous_sha:
                    previous_dir = self._ensure_release(previous_sha)
                elif not first_install:
                    previous_dir = Path(deployed.get("release_dir") or self.source_repo)

            with self.step("validate_configuration"):
                self._run(
                    [
                        self._executable("python3"),
                        str(target_dir / "scripts" / "validate_production_env.py"),
                        "--env-file",
                        str(self.env_file),
                    ],
                    cwd=target_dir,
                    step="validate_configuration",
                )
                self._compose_run(
                    target_dir,
                    release,
                    "config",
                    "--quiet",
                    step="validate_configuration",
                )

            with self.step("api_lint"):
                self._run_api_quality_gate(
                    target_dir,
                    "--project services/api ruff check services/api deploy/release_manager.py",
                    "api_lint",
                )

            with self.step("api_tests"):
                self._run_api_quality_gate(
                    target_dir,
                    "--project services/api pytest -p no:cacheprovider services/api/tests -vv --durations=25 -o faulthandler_timeout=120",
                    "api_tests",
                )

            with self.step("build_images"):
                self._compose_run(
                    target_dir,
                    release,
                    "build",
                    "migrate",
                    "model-manager",
                    "web",
                    step="build_images",
                    timeout=3600,
                )

            if first_install:
                with self.step("bootstrap_guard"):
                    self._assert_empty_instance()
            else:
                with self.step("capture_model_runtime"):
                    active_model_id = self._active_model_id(
                        self._model_deployment("capture_model_runtime")
                    )
                    self.run_record["model_id"] = active_model_id

                with self.step("quiesce_writers"):
                    quiesced = True
                    self._quiesce(previous_dir, previous_release)

                with self.step("pre_deploy_backup"):
                    backup = self._compose_run(
                        previous_dir,
                        previous_release,
                        "run",
                        "--rm",
                        "backup",
                        "once",
                        step="pre_deploy_backup",
                        timeout=1800,
                    )
                    backup_id = self._backup_id(backup.stdout)
                    self.run_record["backup_id"] = backup_id

            with self.step("start_release"):
                target_started = True
                self._compose_run(
                    target_dir,
                    release,
                    "up",
                    "-d",
                    "--wait",
                    "--wait-timeout",
                    "300",
                    "--remove-orphans",
                    step="start_release",
                    timeout=900,
                )

            if active_model_id:
                with self.step("restore_model_runtime"):
                    self._restore_model_runtime(active_model_id)

            if first_install:
                with self.step("initial_backup"):
                    self._quiesce(target_dir, release)
                    backup = self._compose_run(target_dir, release, "run", "--rm", "backup", "once",
                                               step="initial_backup", timeout=1800)
                    self.run_record["backup_id"] = self._backup_id(backup.stdout)
                    self._compose_run(target_dir, release, "up", "-d", "--wait", "--wait-timeout", "300",
                                      step="initial_start", timeout=900)

            with self.step("public_health_check"):
                self.health_release = release
                self._public_health()

            with self.step("publish_release"):
                deployed = {
                    "sha": target_sha,
                    "release": release,
                    "summary": self._commit_summary(target_sha),
                    "deployed_at": timestamp(),
                    "release_dir": str(target_dir),
                }
                atomic_update_release(self.env_file, release)
                atomic_json(self.deployed_path, deployed)
                self._install_manager_update(target_dir)

        except (DeploymentError, OSError, ValueError, json.JSONDecodeError) as exc:
            error = exc if isinstance(exc, DeploymentError) else DeploymentError("deployment", str(exc))
            self.run_record["error"] = self._redact(error.detail)[:8_000]
            self.run_record["error_step"] = error.step
            if quiesced and previous_dir and target_dir:
                self.run_record["rollback"] = self._restore_previous(
                    previous_dir,
                    previous_release,
                    target_dir,
                    release,
                    backup_id,
                    target_started,
                    active_model_id,
                )
            elif first_install and target_started and target_dir:
                self.run_record["rollback"] = self._stop_failed_bootstrap(target_dir, release)
            self.run_record["status"] = (
                "rollback_failed" if self.run_record["rollback"].get("status") == "failed" else "failed"
            )
            self.run_record["finished_at"] = timestamp()
            self.run_record["duration_seconds"] = round((now() - run_started).total_seconds(), 1)
            self.status["service"].update(
                state="error",
                next_retry_at=timestamp(now() + timedelta(seconds=self.retry_seconds)),
            )
            self.status["current"] = self._public_current(self._load_deployed())
            self.status["last_run"] = self.run_record
            self._save_status()
            self._save_history(self.run_record)
            raise error

        self.run_record["status"] = "succeeded"
        self.run_record["activated_sha"] = target_sha
        self.run_record["finished_at"] = timestamp()
        self.run_record["duration_seconds"] = round((now() - run_started).total_seconds(), 1)
        self.status["service"].update(state="idle", next_retry_at=None)
        self.status["current"] = self._public_current(deployed)
        self.status["last_run"] = self.run_record
        self._save_status()
        self._save_history(self.run_record)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Protected JSON instance selector; application secrets remain in env_file.")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--poll", action="store_true", help="Check the configured Git branch and deploy a new commit.")
    modes.add_argument("--status", action="store_true", help="Print the current sanitized status JSON.")
    modes.add_argument("--bootstrap", action="store_true", help="Explicit first installation of an empty configured instance.")
    arguments = parser.parse_args()
    try:
        manager = ReleaseManager(arguments.config, bootstrap=arguments.bootstrap)
    except (OSError, ValueError) as exc:
        print(f"Invalid deployment configuration: {exc}", file=sys.stderr)
        return 2
    if arguments.status:
        print(json.dumps(manager._load_status(), ensure_ascii=False, indent=2))
        return 0
    try:
        manager.poll()
    except (DeploymentError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Helvetic Lens deployment check failed: {manager._redact(str(exc))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
