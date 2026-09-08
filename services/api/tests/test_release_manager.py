import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "release_manager", ROOT / "deploy" / "release_manager.py"
)
assert SPEC and SPEC.loader
release_manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_manager)


def test_release_prefix_accepts_exact_and_named_git_releases():
    assert release_manager.release_prefix("git-0123456789ab") == "0123456789ab"
    assert release_manager.release_prefix("6d781e8-brand-auth1") == "6d781e8"
    assert release_manager.release_prefix("latest") is None


def test_remote_normalization_is_exact_but_ignores_git_suffix():
    assert release_manager.normalize_remote("https://github.com/example/repo.git") == (
        "https://github.com/example/repo"
    )
    assert release_manager.normalize_remote("https://github.com/example/repo/") == (
        "https://github.com/example/repo"
    )


def test_release_update_preserves_secrets_and_file_permissions(tmp_path):
    environment = tmp_path / ".env.production"
    environment.write_text(
        "HELVETIC_LENS_RELEASE=old\nAUTH_SMTP_PASSWORD=do-not-change\n",
        encoding="utf-8",
    )
    environment.chmod(0o600)

    release_manager.atomic_update_release(environment, "git-0123456789ab")

    assert environment.read_text(encoding="utf-8") == (
        "HELVETIC_LENS_RELEASE=git-0123456789ab\n"
        "AUTH_SMTP_PASSWORD=do-not-change\n"
    )
    assert environment.stat().st_mode & 0o777 == 0o600


def test_backup_id_comes_from_the_successful_container_output():
    assert release_manager.ReleaseManager._backup_id(
        "Container ready\nBackup 20260904T112145Z completed.\n"
    ) == "20260904T112145Z"


def test_only_a_live_allowlisted_model_is_preserved_for_a_release():
    manager = release_manager.ReleaseManager

    assert manager._active_model_id({"model_id": "apertus-8b-q4km", "state": "ready"}) == (
        "apertus-8b-q4km"
    )
    assert manager._active_model_id({"model_id": "apertus-8b-q4km", "state": "stopped"}) is None
    assert manager._active_model_id({"model_id": "../../secret", "state": "ready"}) is None


def test_quality_gate_builds_test_tools_without_mounting_host_git_or_production_data(tmp_path):
    manager = release_manager.ReleaseManager.__new__(release_manager.ReleaseManager)
    manager.cache_dir = tmp_path / "cache"
    calls = []
    def capture(command, **options):
        calls.append((command, options))
        return subprocess.CompletedProcess(command, 0, stdout="")
    manager._run = capture
    manager._run_api_quality_gate(ROOT, "--project services/api pytest -q", "api_tests")

    build, execution, cleanup = calls
    context = ROOT / "deploy/api-quality"
    assert build[0][:3] == ["/usr/bin/docker", "build", "--tag"]
    assert build[0][-1] == str(context)
    image = build[0][3]
    assert image.startswith("helvetic-lens-api-quality:")
    assert image in execution[0]
    mounts = [execution[0][i + 1] for i, value in enumerate(execution[0]) if value == "-v"]
    assert mounts == [f"{ROOT}:/workspace:ro", f"{manager.cache_dir}:/cache"]
    assert "--user" in execution[0] and "--frozen" in execution[0]
    assert execution[1]["timeout"] == release_manager.API_TEST_TIMEOUT_DEFAULT
    assert "PYTHONUNBUFFERED=1" in execution[0] and "--init" in execution[0]
    name = execution[0][execution[0].index("--name") + 1]
    assert cleanup[0] == ["/usr/bin/docker", "rm", "--force", name]
    assert cleanup[1] == {"step": "api_tests_cleanup", "check": False, "timeout": 60}
    assert "--no-install-recommends git" in (context / "Dockerfile").read_text()


def host(tmp_path):
    manager = release_manager.ReleaseManager.__new__(release_manager.ReleaseManager)
    manager.cache_dir = tmp_path / "cache"
    manager.secrets = ["synthetic-private-value"]
    manager.log_path = tmp_path / "gate.log"
    return manager


def test_actual_command_timeout_preserves_output_and_redacts_secrets(tmp_path):
    manager = host(tmp_path)
    with pytest.raises(release_manager.DeploymentError) as caught:
        manager._run([sys.executable, "-u", "-c",
            "import time;print('tests/test_example.py::test_slow',flush=True);"
            "print('synthetic-private-value Bearer second-sensitive-value',flush=True);time.sleep(10)"],
            step="api_tests", timeout=1)
    error = caught.value
    assert "1-second" in error.detail and "test_slow" in error.detail
    assert "synthetic-private-value" not in error.detail and "second-sensitive-value" not in error.detail
    log = manager.log_path.read_text()
    assert "test_slow" in log and "synthetic-private-value" not in log and "second-sensitive-value" not in log


@pytest.mark.parametrize("outcome", ["success", "failure", "timeout", "interrupt"])
def test_quality_gate_cleans_only_its_named_container_on_every_exit(tmp_path, outcome):
    manager, calls = host(tmp_path), []
    def fake(command, **options):
        calls.append(command)
        if command[1] == "run":
            if outcome == "interrupt":
                raise KeyboardInterrupt()
            if outcome in {"failure", "timeout"}:
                raise release_manager.DeploymentError("api_tests", f"Synthetic {outcome}")
        return subprocess.CompletedProcess(command, 0, stdout="")
    manager._run = fake
    if outcome == "success":
        manager._run_api_quality_gate(ROOT, "--project services/api pytest -q", "api_tests")
    else:
        with pytest.raises(KeyboardInterrupt if outcome == "interrupt" else release_manager.DeploymentError):
            manager._run_api_quality_gate(ROOT, "--project services/api pytest -q", "api_tests")
    launched, cleanup = calls[1:]
    name = launched[launched.index("--name") + 1]
    assert name.startswith("helvetic-api-qa-")
    assert cleanup == ["/usr/bin/docker", "rm", "--force", name]
    assert not any("prune" in row or "down" in row for row in calls)


@pytest.mark.parametrize("initial_failure", [False, True])
def test_unconfirmed_cleanup_is_visible_without_hiding_original_failure(tmp_path, initial_failure):
    manager = host(tmp_path)
    def fake(command, **options):
        if command[1] == "run" and initial_failure:
            raise release_manager.DeploymentError("api_tests", "Original test timeout")
        return subprocess.CompletedProcess(command, 1 if command[1] == "rm" else 0, stdout="daemon unavailable")
    manager._run = fake
    with pytest.raises(release_manager.DeploymentError) as caught:
        manager._run_api_quality_gate(ROOT, "--project services/api pytest -q", "api_tests")
    assert "container" in caught.value.detail
    if initial_failure:
        assert "Original test timeout" in caught.value.detail and "Cleanup could not be confirmed" in caught.value.detail


def test_already_removed_container_is_not_a_failed_gate(tmp_path):
    manager = host(tmp_path)
    manager._run = lambda command, **options: subprocess.CompletedProcess(command,
        1 if command[1] == "rm" else 0, stdout="Error: No such container: synthetic")
    manager._run_api_quality_gate(ROOT, "--project services/api pytest -q", "api_tests")


@pytest.mark.parametrize("value", ["bad", "0", "299", "21601"])
def test_invalid_operator_timeout_is_rejected_before_docker(tmp_path, monkeypatch, value):
    monkeypatch.setenv("HELVETIC_LENS_API_TEST_TIMEOUT_SECONDS", value)
    manager = host(tmp_path)
    manager._run = lambda *args, **kwargs: pytest.fail("Invalid budget must not launch Docker")
    with pytest.raises(ValueError):
        manager._run_api_quality_gate(ROOT, "--project services/api pytest -q", "api_tests")


def test_operator_budget_applies_only_to_tests(tmp_path, monkeypatch):
    monkeypatch.setenv("HELVETIC_LENS_API_TEST_TIMEOUT_SECONDS", "5400")
    manager, calls = host(tmp_path), []
    def fake(command, **options):
        calls.append((command, options))
        return subprocess.CompletedProcess(command, 0, stdout="")
    manager._run = fake
    manager._run_api_quality_gate(ROOT, "--project services/api pytest -q", "api_tests")
    manager._run_api_quality_gate(ROOT, "--project services/api ruff check services/api", "api_lint")
    assert [options["timeout"] for command, options in calls if command[1] == "run"] == [5400, 1800]
