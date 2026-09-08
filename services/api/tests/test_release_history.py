"""Run on Linux: exercises the actual host journal writer, not a second schema."""

import json
import sqlite3
from types import SimpleNamespace

import pytest
from test_release_manager import release_manager


def manager(tmp_path):
    result = release_manager.ReleaseManager.__new__(release_manager.ReleaseManager)
    result.state_dir = tmp_path
    result.history_path = tmp_path / "history.json"
    result.status_path = tmp_path / "status.json"
    result.history_limit = 3
    result.secrets = ["test-secret-value"]
    result.status = {}
    return result


def run(index, status="succeeded"):
    return {"id": f"run-{index}", "status": status, "started_at": "2026-09-08T08:00:00+00:00",
            "error": None, "steps": [], "target_sha": "a" * 40}


def test_archive_retains_every_run_after_legacy_snapshot_rolls_over(tmp_path):
    host = manager(tmp_path)
    host.history_path.write_text(json.dumps([run("legacy")]))
    for i in range(80):
        host._save_history(run(i))
    assert len(json.loads(host.history_path.read_text())) == 3
    with sqlite3.connect(tmp_path / "history.sqlite3") as db:
        assert db.execute("SELECT count(*) FROM runs").fetchone()[0] == 81
        assert db.execute("SELECT detail FROM runs WHERE id='run-legacy'").fetchone()
        assert db.execute("SELECT value FROM metadata WHERE key='archive_id'").fetchone()[0]


def test_inflight_phases_and_terminal_error_are_durable_redacted_and_immutable(tmp_path):
    host = manager(tmp_path)
    host.run_record = run(1, "deploying")
    host.status = {"last_run": host.run_record}
    with pytest.raises(release_manager.DeploymentError):
        with host.step("api_tests"):
            with sqlite3.connect(tmp_path / "history.sqlite3") as db:
                saved = json.loads(db.execute("SELECT detail FROM runs").fetchone()[0])
                assert saved["steps"][0]["status"] == "running"
            raise release_manager.DeploymentError("api_tests", "Test failed with test-secret-value")
    host.run_record.update(status="failed", error="Test failed with test-secret-value")
    host._save_status()
    with sqlite3.connect(tmp_path / "history.sqlite3") as db:
        before = db.execute("SELECT detail FROM runs").fetchone()[0]
        assert "test-secret-value" not in before and "[redacted]" in before
        assert json.loads(before)["steps"][0]["status"] == "failed"
    host.run_record["status"] = "succeeded"
    host._save_history(host.run_record)
    with sqlite3.connect(tmp_path / "history.sqlite3") as db:
        assert db.execute("SELECT detail FROM runs").fetchone()[0] == before


def test_restart_records_interrupted_before_next_poll_without_invented_finish_time(tmp_path):
    host = manager(tmp_path)
    host.status = {"last_run": {**run(1, "deploying"), "finished_at": None,
                                "steps": [{"name": "start_release", "status": "running"}]}}
    def stop_after_recovery(*args, **kwargs):
        raise RuntimeError("stop before any real Git or deployment operation")
    host._git = stop_after_recovery
    host.remote = "origin"
    with pytest.raises(RuntimeError, match="stop before"):
        host._poll_locked()
    with sqlite3.connect(tmp_path / "history.sqlite3") as db:
        saved = json.loads(db.execute("SELECT detail FROM runs").fetchone()[0])
    assert saved["status"] == "interrupted" and saved["interrupted_at"]
    assert saved["finished_at"] is None and saved["steps"][0]["status"] == "interrupted"
    assert "activated_sha" not in saved


@pytest.mark.parametrize("failure", [None, "api_tests", "public_health_check", "rollback_failed"])
def test_actual_release_pipeline_records_only_verified_activation_and_exact_attempt_notes(tmp_path, failure):
    host = manager(tmp_path)
    old, target = "b" * 40, "a" * 40
    host.expected_repository = "https://github.com/example/project.git"
    host.branch, host.remote = "main", "origin"
    host.source_repo = tmp_path / "source"
    host.poll_seconds, host.retry_seconds = 120, 900
    host.deployed_path = tmp_path / "deployed.json"
    previous = {"sha": old, "release": "git-old", "release_dir": str(tmp_path)}
    release_manager.atomic_json(host.deployed_path, previous)
    host._bootstrap_deployed = lambda: previous
    host._git = lambda *args, **kwargs: (host.expected_repository if args[0] == "remote" else target if args[0] == "rev-parse" else "")
    host._run = lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="")
    host._commit_summary = lambda sha: "Pinned summary " + sha[:7]
    host._changes = lambda *args: [{"sha": target, "subject": "Exact delivered change", "author": "QA", "short_sha": target[:7], "committed_at": release_manager.timestamp()}]
    host.log_dir = tmp_path
    host.env_values = {"HELVETIC_LENS_RELEASE": "git-old"}
    host.env_file = tmp_path / "production.env"
    host.env_file.write_text("HELVETIC_LENS_RELEASE=git-old\nTOKEN=test-secret-value\n")
    host._ensure_release = lambda sha: tmp_path
    def quality(_dir, _command, phase):
        if failure == phase:
            raise release_manager.DeploymentError(phase, "A synthetic test failed: test-secret-value")
    host._run_api_quality_gate = quality
    host._compose_run = lambda *args, **kwargs: SimpleNamespace(stdout="Backup 20260908T080000Z completed.")
    host._model_deployment = lambda step: {"state": "stopped"}
    host._quiesce = lambda *args: None
    host._install_manager_update = lambda *args: None
    host._restore_previous = lambda *args: {"status": "failed" if failure == "rollback_failed" else "succeeded", "backup_restored": failure != "rollback_failed"}
    def health():
        if failure in {"public_health_check", "rollback_failed"}:
            raise release_manager.DeploymentError("public_health_check", "Synthetic health failure")
    host._public_health = health
    if failure:
        with pytest.raises(release_manager.DeploymentError):
            host._poll_locked()
    else:
        host._poll_locked()
    with sqlite3.connect(tmp_path / "history.sqlite3") as db:
        saved = json.loads(db.execute("SELECT detail FROM runs").fetchone()[0])
    expected = "rollback_failed" if failure == "rollback_failed" else "failed" if failure else "succeeded"
    assert saved["status"] == expected
    assert saved["activated_sha"] == (None if failure else target)
    assert saved["previous_sha"] == old and saved["target_sha"] == target
    assert saved["release_notes"]["text"] == "- Exact delivered change"
    assert saved["release_notes"]["previous_sha"] == old
    assert saved["release_notes"]["target_sha"] == target
    assert saved["release_notes"]["kind"] == "commit_summary"
    assert saved["host"] and saved["environment"] == "production"
    if failure:
        assert any(phase["status"] == "failed" for phase in saved["steps"])
        assert "test-secret-value" not in json.dumps(saved)
    if failure in {"public_health_check", "rollback_failed"}:
        assert saved["rollback"]["status"] == ("failed" if failure == "rollback_failed" else "succeeded")
    host._changes = lambda *args: [{"sha": "f" * 40, "subject": "Later main change"}]
    with sqlite3.connect(tmp_path / "history.sqlite3") as db:
        assert json.loads(db.execute("SELECT detail FROM runs").fetchone()[0]) == saved


def test_rejected_history_gate_keeps_the_requested_revision(tmp_path):
    host = manager(tmp_path)
    host.expected_repository, host.branch, host.poll_seconds = "https://github.com/example/project", "main", 120
    host.deployed_path = tmp_path / "deployed.json"
    release_manager.atomic_json(host.deployed_path, {"sha": "b" * 40, "release": "git-old"})
    host.status = {"remote": {"sha": "a" * 40}}
    host._record_poll_failure(release_manager.DeploymentError("verify_history", "Remote main is not a fast-forward."))
    with sqlite3.connect(tmp_path / "history.sqlite3") as db:
        saved = json.loads(db.execute("SELECT detail FROM runs").fetchone()[0])
    assert saved["status"] == "rejected" and saved["target_sha"] == "a" * 40
    assert saved["previous_sha"] == "b" * 40 and saved["activated_sha"] is None
    assert saved["error_step"] == "verify_history"
    for text in ['password="unknown value"', "token='unknown value'", '"api_key": "unknown value"', 'Authorization: Bearer unknown-value']:
        assert "unknown" not in host._redact(text)
