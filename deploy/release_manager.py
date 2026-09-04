#!/usr/bin/env python3
"""Poll Git and deploy immutable Helvetic Lens releases on the local server."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shutil
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

SCHEMA_VERSION = 1
DEFAULT_BASE_DIR = Path("/srv/helvetic-lens")
DEFAULT_REPOSITORY = "https://github.com/HappyMiha/helvetic-lens.git"
UV_IMAGE = (
    "ghcr.io/astral-sh/uv@"
    "sha256:4f5d923c9dcea037f57bda425dd209f3ec643da2f0b74227f68d09dab0b3bb36"
)
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
    for raw_line in path.read_text(encoding="utf-8").splitlines():
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
    lines = path.read_text(encoding="utf-8").splitlines()
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
    def __init__(self) -> None:
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
        self.status_path = self.state_dir / "status.json"
        self.history_path = self.state_dir / "history.json"
        self.deployed_path = self.control_dir / "deployed.json"
        self.lock_path = self.control_dir / "deployment.lock"
        self.log_dir = self.state_dir / "logs"
        self.cache_dir = self.control_dir / "uv-cache"
        self.run_record: dict[str, Any] | None = None
        self.status = self._load_status()
        self.env_values = read_env(self.env_file)
        self.secrets = [
            value
            for key, value in self.env_values.items()
            if value and len(value) >= 4 and any(part in key.upper() for part in SECRET_KEY_PARTS)
        ]
        self.log_path: Path | None = None

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
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DeploymentError(step, f"Unable to run {step}: {exc}") from exc
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
            ["/usr/bin/git", "-C", str(self.source_repo), *arguments],
            step=step,
        )
        return completed.stdout.strip()

    def _resolve_commit(self, revision: str | None) -> str | None:
        if not revision:
            return None
        completed = self._run(
            ["/usr/bin/git", "-C", str(self.source_repo), "rev-parse", f"{revision}^{{commit}}"],
            step="resolve_release",
            check=False,
        )
        value = completed.stdout.strip()
        return value if completed.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", value) else None

    def _commit_summary(self, sha: str | None) -> str | None:
        if not sha:
            return None
        completed = self._run(
            ["/usr/bin/git", "-C", str(self.source_repo), "show", "-s", "--format=%s", sha],
            step="commit_summary",
            check=False,
        )
        return completed.stdout.strip()[:300] if completed.returncode == 0 else None

    def _bootstrap_deployed(self) -> dict[str, Any]:
        deployed = self._load_deployed()
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

    def _save_history(self, run: dict[str, Any]) -> None:
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
        except Exception:
            item["status"] = "failed"
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
                ["/usr/bin/git", "-C", str(destination), "rev-parse", "HEAD"],
                step="checkout",
                check=False,
            )
            if completed.returncode == 0 and completed.stdout.strip() == sha:
                self._link_runtime_configuration(destination)
                return destination
            raise DeploymentError("checkout", f"Existing release directory does not match {sha[:12]}.")
        self.releases_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        self._run(
            [
                "/usr/bin/git",
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
        link = release_dir / ".cloudflared"
        if link.is_symlink() and link.resolve() == self.tunnel_dir.resolve():
            return
        if link.exists() or link.is_symlink():
            raise DeploymentError("checkout", "Release checkout contains an unexpected .cloudflared path.")
        link.symlink_to(self.tunnel_dir, target_is_directory=True)

    def _compose_environment(self, release: str) -> dict[str, str]:
        environment = os.environ.copy()
        environment["HELVETIC_LENS_RELEASE"] = release
        environment["HELVETIC_LENS_CONFIG_FILE"] = str(self.env_file)
        environment["HELVETIC_LENS_DEPLOY_STATE_DIR"] = str(self.state_dir)
        return environment

    def _compose(self, release_dir: Path, release: str, *arguments: str) -> list[str]:
        return [
            "/usr/bin/docker",
            "compose",
            "--project-name",
            "helvetic-lens",
            "--project-directory",
            str(release_dir),
            "--env-file",
            str(self.env_file),
            "-f",
            str(release_dir / "compose.production.yaml"),
            "-f",
            str(release_dir / "compose.cloudflare-tunnel.yaml"),
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
                "/usr/bin/git",
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
        self.cache_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        self._run(
            [
                "/usr/bin/docker",
                "run",
                "--rm",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "-e",
                "HOME=/tmp",
                "-e",
                "UV_CACHE_DIR=/cache",
                "-e",
                "UV_PROJECT_ENVIRONMENT=/tmp/helvetic-lens-venv",
                "-e",
                "RUFF_CACHE_DIR=/tmp/ruff-cache",
                "-e",
                "PYTHONDONTWRITEBYTECODE=1",
                "-e",
                "HELVETIC_LENS_DATA_DIR=/tmp/helvetic-lens-data",
                "-e",
                "PYTHONPATH=/workspace",
                "-v",
                f"{release_dir}:/workspace:ro",
                "-v",
                f"{self.cache_dir}:/cache",
                "-w",
                "/workspace",
                UV_IMAGE,
                "uv",
                "run",
                "--frozen",
                *command.split(),
            ],
            step=step,
            timeout=1800,
        )

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
                "/usr/bin/docker",
                "exec",
                "helvetic-lens-model-manager-1",
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
                "/usr/bin/docker",
                "exec",
                "helvetic-lens-model-manager-1",
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
            self._quiesce(target_dir, target_release, check=False)
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
            self._public_health()
        except DeploymentError as exc:
            errors.append(str(exc))
        rollback["finished_at"] = timestamp()
        rollback["status"] = "succeeded" if not errors else "failed"
        rollback["backup_restored"] = bool(target_started and backup_id and not errors)
        if errors:
            rollback["error"] = self._redact("\n".join(errors))[:4_000]
        return rollback

    def _install_manager_update(self, release_dir: Path) -> None:
        source = release_dir / "deploy" / "release_manager.py"
        destination = self.control_dir / "release_manager.py"
        if not source.is_file():
            return
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
        shutil.copyfile(source, temporary)
        temporary.chmod(0o755)
        temporary.replace(destination)

    def _record_poll_failure(self, error: Exception) -> None:
        checked_at = timestamp()
        deployed = self._load_deployed()
        run = {
            "id": str(uuid.uuid4()),
            "status": "failed",
            "kind": "poll",
            "target_sha": None,
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
        lock_stream = self.lock_path.open("a+")
        try:
            fcntl.flock(lock_stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return

        try:
            self._poll_locked()
        except (DeploymentError, OSError, ValueError, json.JSONDecodeError) as exc:
            if self.run_record is None:
                self._record_poll_failure(exc)
            raise
        finally:
            lock_stream.close()

    def _poll_locked(self) -> None:
        repository = self._git("remote", "get-url", self.remote, step="verify_remote")
        if normalize_remote(repository) != normalize_remote(self.expected_repository):
            raise DeploymentError(
                "verify_remote",
                f"Refusing unexpected Git remote {normalize_remote(repository)}.",
            )
        self._git("fetch", "--prune", self.remote, self.branch, step="fetch")
        target_sha = self._git(
            "rev-parse", f"refs/remotes/{self.remote}/{self.branch}^{{commit}}", step="fetch"
        )
        if not re.fullmatch(r"[0-9a-f]{40}", target_sha):
            raise DeploymentError("fetch", "Remote branch did not resolve to a full commit SHA.")

        deployed = self._bootstrap_deployed()
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
            last_run.get("status") == "failed"
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
                    "/usr/bin/git",
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
                    "Remote main is not a fast-forward from the deployed commit; manual review is required.",
                )

        release = f"git-{target_sha[:12]}"
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
                else:
                    previous_dir = Path(deployed.get("release_dir") or self.source_repo)

            with self.step("validate_configuration"):
                self._run(
                    [
                        "/usr/bin/python3",
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
                    "--project services/api pytest -p no:cacheprovider services/api/tests -q",
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

            with self.step("public_health_check"):
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
            self.run_record["status"] = "failed"
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
        self.run_record["finished_at"] = timestamp()
        self.run_record["duration_seconds"] = round((now() - run_started).total_seconds(), 1)
        self.status["service"].update(state="idle", next_retry_at=None)
        self.status["current"] = self._public_current(deployed)
        self.status["last_run"] = self.run_record
        self._save_status()
        self._save_history(self.run_record)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poll", action="store_true", help="Check Git and deploy a new main commit.")
    parser.add_argument("--status", action="store_true", help="Print the current sanitized status JSON.")
    arguments = parser.parse_args()
    manager = ReleaseManager()
    if arguments.status:
        print(json.dumps(manager._load_status(), ensure_ascii=False, indent=2))
        return 0
    if not arguments.poll:
        parser.error("choose --poll or --status")
    try:
        manager.poll()
    except (DeploymentError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Helvetic Lens deployment check failed: {manager._redact(str(exc))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
