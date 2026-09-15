import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_capacity_gate_runner import capacity

from helvetic_lens import worker_supervisor as supervisor
from helvetic_lens.celery_app import celery_app


@pytest.mark.asyncio
@pytest.mark.parametrize("recovers", [True, False])
async def test_capacity_recovery_waits_for_the_whole_cpu_group(monkeypatch, recovers):
    gate = object.__new__(capacity.CapacityGate)
    gate.compose_command = lambda *args: ["synthetic-compose", *args]
    calls = []
    def run(command, **options):
        calls.append(command)
        assert command[-3:] == ["-m", "helvetic_lens.worker_supervisor", "--healthcheck"]
        assert options["timeout"] == 8 and options["capture_output"] is True
        return SimpleNamespace(returncode=0 if recovers and len(calls) == 2 else 1)
    monkeypatch.setattr(capacity.subprocess, "run", run)
    assert await gate.wait_for_cpu_consumers(timeout=3 if recovers else 0.01) is recovers
    assert len(calls) == (2 if recovers else 1)


@pytest.mark.parametrize("state", ["ready", "missing", "wrong", "unavailable"])
def test_health_requires_every_exact_consumer_and_redacts_broker_failure(monkeypatch, state, capsys):
    def inspect(*, destination, timeout):
        assert len(destination) == len(set(destination)) == 6 and timeout == 3
        replies = {name: {"ok": "pong"} for name in destination}
        if state == "missing":
            replies.pop(destination[-1])
        elif state == "wrong":
            replies[destination[0]] = {"ok": "starting"}
        elif state == "unavailable":
            raise ConnectionError("redis://private:never-print@broker")
        return SimpleNamespace(ping=lambda: replies)
    monkeypatch.setattr(celery_app.control, "inspect", inspect)
    assert supervisor.healthy() is (state == "ready")
    output = capsys.readouterr()
    assert "never-print" not in output.out + output.err


@pytest.mark.parametrize("scenario", ["stop", "ignore", "crash"])
def test_real_linux_supervisor_stops_every_process_group(tmp_path, scenario):
    probe = Path(__file__).with_name("worker_supervisor_probe.py")
    container = None
    if sys.platform.startswith("linux"):
        command = [sys.executable, "-B", str(probe), scenario]
    else:
        image = os.getenv("HL_SUPERVISOR_TEST_IMAGE")
        if not image:
            pytest.skip("Requires Linux processes; use an explicitly selected cached Docker test image on Windows")
        package = tmp_path / "fixture" / "helvetic_lens"
        tests = tmp_path / "fixture" / "tests"
        package.mkdir(parents=True)
        tests.mkdir()
        (package / "__init__.py").write_text("")
        for name in ("worker_supervisor.py", "monitoring_queues.py"):
            shutil.copyfile(Path(supervisor.__file__).with_name(name), package / name)
        shutil.copyfile(probe, tests / probe.name)
        container = "hl-supervisor-test-" + uuid4().hex
        command = ["docker", "run", "--rm", "--pull", "never", "--name", container,
            "--network", "none", "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--memory", "256m", "--cpus", "1",
            "--pids-limit", "64", "--mount", f"type=bind,source={package.parent},target=/fixture,readonly",
            image, "python", "-B", "/fixture/tests/" + probe.name, scenario]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=25)
    finally:
        if container:
            subprocess.run(["docker", "rm", "-f", container], capture_output=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report == {"scenario": scenario, "parents_stopped": 6, "grandchildren_stopped": 6,
        "database_budgets_preserved": True}
