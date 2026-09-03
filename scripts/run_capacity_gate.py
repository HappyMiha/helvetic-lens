#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import platform
import shutil
import subprocess
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

TERMINAL_JOB_STATES = {"succeeded", "failed", "cancelled"}
RECOVERY_ACK = "dedicated-capacity-environment"
RECOVERY_SERVICES = ("scheduler", "api", "redis", "worker-cpu", "worker-ai", "model-manager")


def percentile(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percent / 100 * len(ordered)) - 1)
    return round(ordered[index], 2)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def elapsed_ms(started_at: str | None, finished_at: str | None) -> float | None:
    if not started_at or not finished_at:
        return None
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        finished = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return round(max(0.0, (finished - started).total_seconds() * 1000), 2)


def command_json(command: list[str]) -> Any:
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=20)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    output = result.stdout.strip()
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        rows = []
        for line in output.splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows or output


def resource_snapshot() -> dict:
    disk = shutil.disk_usage(Path.cwd())
    snapshot: dict[str, Any] = {
        "at": now_iso(),
        "disk": {"total_bytes": disk.total, "used_bytes": disk.used, "free_bytes": disk.free},
        "docker": command_json(["docker", "stats", "--no-stream", "--format", "{{json .}}"]),
        "gpu": command_json(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.used,memory.total,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ]
        ),
    }
    try:
        import psutil

        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        snapshot["host"] = {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_total_bytes": memory.total,
            "memory_available_bytes": memory.available,
            "memory_percent": memory.percent,
            "swap_total_bytes": swap.total,
            "swap_used_bytes": swap.used,
            "swap_percent": swap.percent,
        }
    except ImportError:
        if Path("/proc/meminfo").is_file():
            values = {}
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                key, _, raw_value = line.partition(":")
                if raw_value.strip().endswith(" kB"):
                    values[key] = int(raw_value.split()[0]) * 1024
            snapshot["host"] = {
                "collector": "procfs",
                "memory_total_bytes": values.get("MemTotal"),
                "memory_available_bytes": values.get("MemAvailable"),
                "swap_total_bytes": values.get("SwapTotal"),
                "swap_free_bytes": values.get("SwapFree"),
                "load_average": list(os.getloadavg()),
            }
        elif platform.system() == "Windows":
            memory = command_json(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    (
                        "Get-CimInstance Win32_OperatingSystem | Select-Object "
                        "TotalVisibleMemorySize,FreePhysicalMemory,TotalVirtualMemorySize,"
                        "FreeVirtualMemory | ConvertTo-Json -Compress"
                    ),
                ]
            )
            snapshot["host"] = {"collector": "windows_cim", "memory_kib": memory}
        else:
            snapshot["host"] = {"collector": "unavailable"}
    return snapshot


@dataclass
class ResourceMonitor:
    interval: float = 2.0
    samples: list[dict] = field(default_factory=list)
    _stop: asyncio.Event = field(default_factory=asyncio.Event)

    async def run(self):
        while not self._stop.is_set():
            self.samples.append(await asyncio.to_thread(resource_snapshot))
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
            except TimeoutError:
                pass

    def stop(self):
        self._stop.set()


@dataclass
class Observation:
    phase: str
    operation: str
    status: int
    latency_ms: float
    request_id: str | None
    expected: bool
    error_code: str | None = None


@dataclass
class Account:
    organization: dict
    account: dict
    client: httpx.AsyncClient

    @property
    def csrf_headers(self) -> dict[str, str]:
        token = self.client.cookies.get("helvetic_lens_csrf")
        return {"X-CSRF-Token": token} if token else {}


class CapacityGate:
    def __init__(self, arguments, manifest: dict, password: str):
        self.arguments = arguments
        self.manifest = manifest
        self.password = password
        self.run_id = uuid4().hex[:12]
        self.observations: list[Observation] = []
        self.accounts: dict[str, Account] = {}
        self.jobs: list[tuple[str, str, Account]] = []
        self.resource_monitor = ResourceMonitor(arguments.resource_interval)
        self.started_at = now_iso()
        self.recovery_result: dict = {"exercised": False, "services": []}
        self.inference_report = self._load_optional_report(arguments.inference_report)
        self.backup_report = self._load_optional_report(arguments.backup_report)

    @staticmethod
    def _load_optional_report(path: Path | None) -> dict | None:
        return json.loads(path.read_text(encoding="utf-8")) if path else None

    async def login(self, organization: dict, account_data: dict) -> Account:
        client = httpx.AsyncClient(
            base_url=self.arguments.base_url,
            timeout=self.arguments.request_timeout,
            follow_redirects=False,
        )
        started = time.perf_counter()
        response = await client.post(
            "/api/auth/login",
            json={"email": account_data["email"], "password": self.password},
        )
        self.record("login", "login", response, started, {200})
        if response.status_code != 200:
            await client.aclose()
            raise RuntimeError(f"Login failed for a synthetic account (HTTP {response.status_code}).")
        return Account(organization, account_data, client)

    def record(
        self,
        phase: str,
        operation: str,
        response: httpx.Response,
        started: float,
        expected_statuses: set[int],
    ):
        error_code = None
        if response.status_code >= 400:
            try:
                error_code = response.json().get("code")
            except (ValueError, AttributeError):
                error_code = None
        self.observations.append(
            Observation(
                phase=phase,
                operation=operation,
                status=response.status_code,
                latency_ms=(time.perf_counter() - started) * 1000,
                request_id=response.headers.get("x-request-id"),
                expected=response.status_code in expected_statuses,
                error_code=error_code,
            )
        )

    async def request(
        self,
        account: Account,
        method: str,
        path: str,
        *,
        phase: str,
        operation: str,
        expected_statuses: set[int],
        body: dict | None = None,
    ) -> httpx.Response:
        started = time.perf_counter()
        response = await account.client.request(
            method,
            path,
            json=body,
            headers=account.csrf_headers if method != "GET" else None,
        )
        self.record(phase, operation, response, started, expected_statuses)
        return response

    async def login_scenario_accounts(self):
        required = []
        for organization in self.manifest["organizations"]:
            required.extend((organization, item) for item in organization["accounts"][:3])
        semaphore = asyncio.Semaphore(self.arguments.login_concurrency)

        async def bounded(organization, account_data):
            async with semaphore:
                account = await self.login(organization, account_data)
                self.accounts[account_data["email"]] = account

        await asyncio.gather(*(bounded(*item) for item in required))

    def account_for(self, organization: dict, index: int) -> Account:
        return self.accounts[organization["accounts"][index]["email"]]

    async def run_reads(self):
        organizations = self.manifest["organizations"]
        readers = []
        for organization in organizations:
            readers.extend(
                [self.account_for(organization, 0), self.account_for(organization, 2)]
            )
        readers = readers[: self.arguments.read_concurrency]
        semaphore = asyncio.Semaphore(self.arguments.read_concurrency)

        async def one(index: int):
            async with semaphore:
                account = readers[index % len(readers)]
                organization = account.organization
                kind = index % 3
                if kind == 0:
                    query = "&q=Governance" if index % 2 else "&health=changed"
                    await self.request(
                        account,
                        "GET",
                        f"/api/registry?view=monitored&limit=30{query}",
                        phase="read",
                        operation="registry",
                        expected_statuses={200},
                    )
                elif kind == 1:
                    await self.request(
                        account,
                        "GET",
                        f"/api/versions/{organization['new_version_id']}",
                        phase="read",
                        operation="evidence",
                        expected_statuses={200},
                    )
                else:
                    await self.request(
                        account,
                        "GET",
                        f"/api/comparisons/{organization['comparison_id']}",
                        phase="read",
                        operation="comparison",
                        expected_statuses={200},
                    )

        await asyncio.gather(*(one(index) for index in range(self.arguments.read_requests)))

    async def run_commands(self):
        organizations = self.manifest["organizations"]
        command_tasks = []

        for organization in organizations[: self.arguments.scan_submissions]:
            account = self.account_for(organization, 0)

            async def scan(selected_account=account, selected=organization):
                response = await self.request(
                    selected_account,
                    "POST",
                    "/api/scans",
                    phase="enqueue",
                    operation="scan",
                    expected_statuses={202},
                    body={"law_ids": [selected["law_id"]]},
                )
                if response.status_code == 202:
                    payload = response.json()
                    if payload.get("job", {}).get("id"):
                        self.jobs.append((payload["job"]["id"], "scan", selected_account))

            command_tasks.append(scan())

        for index, organization in enumerate(organizations):
            analysis_account = self.account_for(organization, 0)
            ask_account = self.account_for(organization, 1)

            async def analyse(selected_account=analysis_account, selected=organization):
                response = await self.request(
                    selected_account,
                    "POST",
                    f"/api/comparisons/{selected['comparison_id']}/analyse-jobs",
                    phase="enqueue",
                    operation="ai_analysis",
                    expected_statuses={202},
                    body={"output_locale": selected_account.account["locale"]},
                )
                if response.status_code == 202 and response.json().get("id"):
                    self.jobs.append((response.json()["id"], "ai_analysis", selected_account))

            async def ask(selected_account=ask_account, selected=organization, number=index):
                response = await self.request(
                    selected_account,
                    "POST",
                    f"/api/comparisons/{selected['comparison_id']}/ask-jobs",
                    phase="enqueue",
                    operation="ai_question",
                    expected_statuses={202},
                    body={
                        "question": (
                            "What material deadline and operational changes should we review? "
                            f"Capacity run {self.run_id}, organization {number}."
                        ),
                        "history": [],
                        "output_locale": selected_account.account["locale"],
                    },
                )
                if response.status_code == 202 and response.json().get("id"):
                    self.jobs.append((response.json()["id"], "ai_question", selected_account))

            command_tasks.extend([analyse(), ask()])

        if not self.arguments.skip_connector:
            platform_account = self.account_for(organizations[0], 0)
            connector, stream = self.arguments.connector.split(":", 1)

            async def connector_sync():
                response = await self.request(
                    platform_account,
                    "POST",
                    f"/api/admin/connectors/{connector}/{stream}/sync",
                    phase="enqueue",
                    operation="connector",
                    expected_statuses={202},
                )
                if response.status_code == 202 and response.json().get("id"):
                    self.jobs.append((response.json()["id"], "connector", platform_account))

            command_tasks.append(connector_sync())

        semaphore = asyncio.Semaphore(self.arguments.command_concurrency)

        async def bounded(command):
            async with semaphore:
                await command

        await asyncio.gather(*(bounded(command) for command in command_tasks))

    async def wait_for_jobs(self) -> dict:
        if not self.arguments.wait_for_jobs:
            return {"waited": False, "submitted": len(self.jobs), "states": {}}
        wait_started = time.perf_counter()
        deadline = time.monotonic() + self.arguments.job_timeout
        pending = {(job_id, kind): account for job_id, kind, account in self.jobs}
        results = {}
        while pending and time.monotonic() < deadline:
            for job_key, account in list(pending.items()):
                job_id, kind = job_key
                started = time.perf_counter()
                try:
                    response = await account.client.get(f"/api/jobs/{job_id}")
                except httpx.HTTPError:
                    continue
                self.record("job_poll", kind, response, started, {200})
                if response.status_code != 200:
                    continue
                payload = response.json()
                state = payload.get("state") or payload.get("status")
                if state in TERMINAL_JOB_STATES:
                    error = payload.get("error") or {}
                    results[job_id] = {
                        "kind": kind,
                        "state": state,
                        "attempts": payload.get("attempts"),
                        "queue_wait_ms": elapsed_ms(
                            payload.get("created_at"), payload.get("started_at")
                        ),
                        "duration_ms": elapsed_ms(
                            payload.get("started_at"), payload.get("finished_at")
                        ),
                        "error_code": error.get("code") if isinstance(error, dict) else None,
                    }
                    pending.pop(job_key)
            if pending:
                await asyncio.sleep(1)
        queue_waits = [
            item["queue_wait_ms"]
            for item in results.values()
            if item["queue_wait_ms"] is not None
        ]
        durations = [
            item["duration_ms"]
            for item in results.values()
            if item["duration_ms"] is not None
        ]
        kinds = sorted({item["kind"] for item in results.values()})
        return {
            "waited": True,
            "submitted": len(self.jobs),
            "states": dict(Counter(item["state"] for item in results.values())),
            "by_kind": {
                kind: dict(Counter(item["state"] for item in results.values() if item["kind"] == kind))
                for kind in kinds
            },
            "timings": {
                "drain_duration_ms": round((time.perf_counter() - wait_started) * 1000, 2),
                "queue_wait_p50_ms": percentile(queue_waits, 50),
                "queue_wait_p95_ms": percentile(queue_waits, 95),
                "queue_wait_max_ms": round(max(queue_waits), 2) if queue_waits else None,
                "duration_p50_ms": percentile(durations, 50),
                "duration_p95_ms": percentile(durations, 95),
                "duration_max_ms": round(max(durations), 2) if durations else None,
                "by_kind": {
                    kind: {
                        "duration_p95_ms": percentile(
                            [
                                item["duration_ms"]
                                for item in results.values()
                                if item["kind"] == kind and item["duration_ms"] is not None
                            ],
                            95,
                        ),
                        "queue_wait_p95_ms": percentile(
                            [
                                item["queue_wait_ms"]
                                for item in results.values()
                                if item["kind"] == kind and item["queue_wait_ms"] is not None
                            ],
                            95,
                        ),
                    }
                    for kind in kinds
                },
            },
            "attempts": sum(item.get("attempts") or 0 for item in results.values()),
            "retries": sum(max(0, (item.get("attempts") or 1) - 1) for item in results.values()),
            "timed_out": len(pending),
            "results": results,
        }

    def compose_command(self, *arguments: str) -> list[str]:
        command = [
            "docker",
            "compose",
            "--project-directory",
            str(self.arguments.compose_project_directory),
        ]
        for compose_file in self.arguments.compose_file:
            command.extend(["-f", str(compose_file)])
        if self.arguments.compose_env_file:
            command.extend(["--env-file", str(self.arguments.compose_env_file)])
        return [*command, *arguments]

    async def wait_for_api(self, timeout: float = 120) -> bool:
        deadline = time.monotonic() + timeout
        async with httpx.AsyncClient(base_url=self.arguments.base_url, timeout=5) as client:
            while time.monotonic() < deadline:
                try:
                    response = await client.get("/api/health")
                    if response.status_code == 200:
                        return True
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(1)
        return False

    async def service_is_running(self, service: str) -> bool:
        result = await asyncio.to_thread(
            subprocess.run,
            self.compose_command("ps", "--status", "running", "--services", service),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0 and service in result.stdout.splitlines()

    async def exercise_recovery(self):
        if not self.arguments.recovery:
            return
        if os.getenv("HELVETIC_LENS_RECOVERY_ACK") != RECOVERY_ACK:
            raise RuntimeError(
                f"Set HELVETIC_LENS_RECOVERY_ACK={RECOVERY_ACK} only for the isolated test stack."
            )
        before = await self.platform_status()
        model = (before or {}).get("model") or {}
        active_model_id = model.get("model_id") if model.get("state") in {"ready", "degraded"} else None
        results = []
        for service in RECOVERY_SERVICES:
            started = time.perf_counter()
            result = await asyncio.to_thread(
                subprocess.run,
                self.compose_command("restart", service),
                capture_output=True,
                text=True,
                timeout=180,
            )
            service_running = result.returncode == 0 and await self.service_is_running(service)
            api_recovered = service_running and await self.wait_for_api()
            results.append(
                {
                    "service": service,
                    "return_code": result.returncode,
                    "service_running": service_running,
                    "api_recovered": api_recovered,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            )
            if not api_recovered:
                break
        if active_model_id and all(item["api_recovered"] for item in results):
            account = self.account_for(self.manifest["organizations"][0], 0)
            response = await self.request(
                account,
                "POST",
                f"/api/admin/models/{active_model_id}/start",
                phase="recovery",
                operation="model_runner_start",
                expected_statuses={202},
            )
            if response.status_code == 202 and response.json().get("id"):
                self.jobs.append((response.json()["id"], "model_runner_start", account))
        self.recovery_result = {
            "exercised": True,
            "services": results,
            "active_model_before": active_model_id,
            "resources_before": (before or {}).get("resources"),
            "completed": len(results) == len(RECOVERY_SERVICES)
            and all(item["service_running"] and item["api_recovered"] for item in results),
        }

    async def platform_status(self) -> dict | None:
        account = self.account_for(self.manifest["organizations"][0], 0)
        try:
            response = await account.client.get("/api/admin/status")
            return response.json() if response.status_code == 200 else {"http_status": response.status_code}
        except httpx.HTTPError as exc:
            return {"error": type(exc).__name__}

    def phase_summary(self, phase: str) -> dict:
        selected = [item for item in self.observations if item.phase == phase]
        latencies = [item.latency_ms for item in selected]
        return {
            "requests": len(selected),
            "expected": sum(item.expected for item in selected),
            "unexpected": sum(not item.expected for item in selected),
            "p50_ms": percentile(latencies, 50),
            "p95_ms": percentile(latencies, 95),
            "max_ms": round(max(latencies), 2) if latencies else None,
            "status_counts": dict(Counter(str(item.status) for item in selected)),
            "operations": {
                operation: {
                    "requests": len(rows),
                    "p95_ms": percentile([item.latency_ms for item in rows], 95),
                    "unexpected": sum(not item.expected for item in rows),
                }
                for operation, rows in self._group_operations(selected).items()
            },
        }

    @staticmethod
    def _group_operations(rows: list[Observation]) -> dict[str, list[Observation]]:
        grouped = defaultdict(list)
        for row in rows:
            grouped[row.operation].append(row)
        return grouped

    def criteria(self, job_summary: dict) -> dict:
        reads = self.phase_summary("read")
        enqueues = self.phase_summary("enqueue")
        considered = [
            item
            for item in self.observations
            if item.phase in {"read", "enqueue"} and item.status not in {422, 429}
        ]
        error_rate = (
            100 * sum(item.status >= 400 for item in considered) / len(considered)
            if considered
            else 100.0
        )
        operations = Counter(
            item.operation
            for item in self.observations
            if item.phase == "enqueue" and item.expected
        )
        checks = {
            "100_accounts": self.manifest.get("account_count", 0) >= 100,
            "several_organizations": len(self.manifest.get("organizations", [])) >= 5,
            "reader_concurrency_10_to_20": 10 <= self.arguments.read_concurrency <= 20,
            "read_p95_below_500_ms": (reads["p95_ms"] or math.inf) < 500,
            "enqueue_p95_below_1000_ms": (enqueues["p95_ms"] or math.inf) < 1000,
            "http_error_rate_below_1_percent": error_rate < 1,
            "20_ai_submissions_accepted": (
                operations["ai_analysis"] + operations["ai_question"] >= 20
            ),
            "concurrent_scans_accepted": operations["scan"] >= 2,
            "connector_work_accepted": operations["connector"] >= 1,
            "request_ids_present": all(item.request_id for item in considered),
            "service_recovery_exercised": bool(self.recovery_result.get("completed")),
            "target_inference_benchmark_passed": bool(
                self.inference_report
                and self.inference_report.get("result") == "pass"
                and len(self.inference_report.get("hardware", {}).get("cuda_devices") or []) >= 2
                and self.inference_report.get("representative_calls", {}).get("oom") == 0
                and self.inference_report.get("representative_calls", {}).get("schema_valid", 0) >= 20
            ),
            "backup_restore_rehearsal_verified": bool(
                self.backup_report
                and self.backup_report.get("verified") is True
                and self.backup_report.get("backup_seconds", 0) > 0
                and self.backup_report.get("restore_seconds", 0) > 0
            ),
        }
        if job_summary.get("waited"):
            ai_states = Counter()
            for kind in ("ai_analysis", "ai_question"):
                ai_states.update(job_summary.get("by_kind", {}).get(kind, {}))
            checks["accepted_ai_work_completed"] = ai_states["succeeded"] >= 20
            checks["queues_drained_before_timeout"] = job_summary.get("timed_out", 1) == 0
            checks["no_false_successes"] = all(
                item.get("state") != "succeeded" or not item.get("error_code")
                for item in job_summary.get("results", {}).values()
            )
        return {"checks": checks, "passed": all(checks.values()), "http_error_rate_percent": round(error_rate, 3)}

    async def run(self) -> dict:
        monitor_task = asyncio.create_task(self.resource_monitor.run())
        try:
            await self.login_scenario_accounts()
            await self.run_reads()
            await self.run_commands()
            await self.exercise_recovery()
            job_summary = await self.wait_for_jobs()
            platform_status = await self.platform_status()
        finally:
            self.resource_monitor.stop()
            await monitor_task
            await asyncio.gather(
                *(account.client.aclose() for account in self.accounts.values()),
                return_exceptions=True,
            )
        return {
            "schema_version": "1",
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": now_iso(),
            "target": {
                "base_url": self.arguments.base_url,
                "host": platform.node(),
                "platform": platform.platform(),
                "python": platform.python_version(),
            },
            "scenario": {
                "account_count": self.manifest.get("account_count"),
                "organization_count": len(self.manifest.get("organizations", [])),
                "authenticated_scenario_accounts": len(self.accounts),
                "read_concurrency": self.arguments.read_concurrency,
                "read_requests": self.arguments.read_requests,
                "scan_submissions": self.arguments.scan_submissions,
                "ai_submissions": 2 * len(self.manifest.get("organizations", [])),
                "command_concurrency": self.arguments.command_concurrency,
                "connector": None if self.arguments.skip_connector else self.arguments.connector,
            },
            "phases": {
                phase: self.phase_summary(phase)
                for phase in ("login", "read", "enqueue", "job_poll")
            },
            "jobs": job_summary,
            "recovery": self.recovery_result,
            "platform_status": platform_status,
            "inference_benchmark": self.inference_report,
            "backup_restore_rehearsal": self.backup_report,
            "resources": {
                "samples": self.resource_monitor.samples,
                "disk_growth_bytes": (
                    self.resource_monitor.samples[-1]["disk"]["used_bytes"]
                    - self.resource_monitor.samples[0]["disk"]["used_bytes"]
                    if len(self.resource_monitor.samples) >= 2
                    else None
                ),
            },
            "criteria": self.criteria(job_summary),
        }


def parse_arguments():
    parser = argparse.ArgumentParser(description="Run the Helvetic Lens 100-user capacity gate.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--read-concurrency", type=int, default=20, choices=range(10, 21))
    parser.add_argument("--read-requests", type=int, default=300)
    parser.add_argument("--scan-submissions", type=int, default=5)
    parser.add_argument("--command-concurrency", type=int, default=5, choices=range(2, 21))
    parser.add_argument("--connector", default="fedlex:catalogue")
    parser.add_argument("--skip-connector", action="store_true")
    parser.add_argument("--login-concurrency", type=int, default=3)
    parser.add_argument("--request-timeout", type=float, default=30)
    parser.add_argument("--job-timeout", type=float, default=1800)
    parser.add_argument("--resource-interval", type=float, default=2)
    parser.add_argument("--wait-for-jobs", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--recovery",
        action="store_true",
        help="Restart every stateful/runtime service; requires the dedicated-stack acknowledgement.",
    )
    parser.add_argument(
        "--compose-project-directory",
        type=Path,
        default=Path.cwd(),
    )
    parser.add_argument(
        "--compose-file",
        action="append",
        type=Path,
        default=[],
        help="Repeat for Compose overlays; defaults to compose.production.yaml.",
    )
    parser.add_argument("--compose-env-file", type=Path)
    parser.add_argument(
        "--inference-report",
        type=Path,
        help="Target-host JSON emitted by benchmark_local_inference.py.",
    )
    parser.add_argument(
        "--backup-report",
        type=Path,
        help="Operator-verified target-host backup/restore timing JSON.",
    )
    arguments = parser.parse_args()
    if not arguments.compose_file:
        arguments.compose_file = [arguments.compose_project_directory / "compose.production.yaml"]
    return arguments


async def async_main() -> int:
    arguments = parse_arguments()
    password = os.getenv("CAPACITY_GATE_PASSWORD", "")
    if not password:
        raise SystemExit("Set CAPACITY_GATE_PASSWORD; the runner never writes it to reports.")
    manifest = json.loads(arguments.manifest.read_text(encoding="utf-8"))
    gate = CapacityGate(arguments, manifest, password)
    report = await gate.run()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(arguments.output), "criteria": report["criteria"]}, indent=2))
    return 0 if report["criteria"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
