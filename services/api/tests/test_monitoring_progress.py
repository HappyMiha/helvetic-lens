"""Backlog provenance and availability across real journal transitions, without Docker."""

import copy
import json
import shutil
import subprocess

import pytest
from test_release_instance import instance as instance
from test_release_instance import pipeline
from test_release_manager import ROOT, release_manager

from helvetic_lens.deployments import deployment_snapshot


def backlog(*statuses):
    rows, sections = [], []
    for number, status in enumerate(statuses, 1):
        task_id = f"MV2-{number:03}"
        rows.append(f"| [{task_id}](#{task_id.lower()}) | Task {number} | FIRST | P0 | M | {status} | None |")
        sections.append(f"### {task_id} — Task {number}\n\n**Status:** {status} · **Priority:** P0\n")
    return ("# Backlog\n\n" + "\n".join(rows) + "\n\n" + "\n".join(sections)).encode("utf-8")


def test_actual_backlog_has_complete_unique_sections_and_preserves_customs_deferral():
    tasks = release_manager.parse_monitoring_backlog((ROOT / "BACKLOG_MONITORING_V2.md").read_bytes())
    by_id = {task["id"]: task for task in tasks}
    assert 0 < len(tasks) == len(by_id) <= 100
    assert {"MV2-001", "MV2-069", "MV2-070", "MV2-030", "MV2-031", "MV2-071", "MV2-073"} <= by_id.keys()
    assert all(by_id[task_id]["status"] == "DEFERRED" for task_id in ("MV2-026", "MV2-027", "MV2-061"))


def test_parser_accepts_bom_notes_and_ignores_code_examples():
    source = backlog("PLANNED — first priority", "IN PROGRESS", "DONE", "DEFERRED — future scope")
    source += b"\n```markdown\n### MV2-099 fake example\n**Status:** DONE\n```\n"
    tasks = release_manager.parse_monitoring_backlog(b"\xef\xbb\xbf" + source)
    assert [task["status"] for task in tasks] == ["PLANNED", "IN PROGRESS", "DONE", "DEFERRED"]


@pytest.mark.parametrize("indent", [" ", "  ", "   "])
def test_parser_counts_valid_markdown_indentation(indent):
    source = "\n".join(indent + line for line in backlog("DONE", "PLANNED").decode("utf-8").splitlines())
    tasks = release_manager.parse_monitoring_backlog(source.encode("utf-8"))
    assert [task["id"] for task in tasks] == ["MV2-001", "MV2-002"]


@pytest.mark.parametrize("indent", ["    ", "\t"])
def test_parser_rejects_unsupported_indented_task_records_instead_of_omitting_them(indent):
    extra = backlog("PLANNED").replace(b"MV2-001", b"MV2-002").replace(b"mv2-001", b"mv2-002")
    source = backlog("DONE") + b"\n" + b"\n".join(indent.encode() + line for line in extra.splitlines())
    with pytest.raises(ValueError, match="indented"):
        release_manager.parse_monitoring_backlog(source)


def test_parser_does_not_close_a_longer_fence_with_a_shorter_nested_fence():
    extra = backlog("PLANNED").replace(b"MV2-001", b"MV2-002").replace(b"mv2-001", b"mv2-002")
    source = backlog("DONE") + b"\n````markdown\n```\n" + extra + b"\n```\n````\n"
    tasks = release_manager.parse_monitoring_backlog(source)
    assert [task["id"] for task in tasks] == ["MV2-001"]


@pytest.mark.parametrize("change", [
    lambda value: value.replace(b"**Status:** DONE", b"**Status:** READY"),
    lambda value: value.replace(b"**Status:** DONE", b"**Status:** DONE\n**Status:** DONE"),
    lambda value: value.replace(b"**Status:** DONE", "**Status:** DONE · **Status:** BLOCKED".encode()),
    lambda value: value.replace(b"**Status:** DONE", b"**Other:** DONE"),
    lambda value: value + b"\n### MV2-001 \xe2\x80\x94 Duplicate\n**Status:** DONE\n",
    lambda value: value.replace(b"### MV2-001", b"### MV2-099"),
    lambda value: value.replace(b"[MV2-001](#mv2-001)", b"[MV2-001](#mv2-002)"),
    lambda value: value.replace(b"DONE", b"DONEISH"),
    lambda value: b"\n".join(line for line in value.splitlines() if not line.startswith(b"| [")),
    lambda value: value + b"\n| [MV2-001](#mv2-001) | Duplicate | F0 | P0 | S | DONE | None |\n",
    lambda value: value + b"\n```unterminated\n",
])
def test_parser_rejects_incomplete_or_ambiguous_task_counts(change):
    with pytest.raises(ValueError):
        release_manager.parse_monitoring_backlog(change(backlog("DONE")))


def test_parser_enforces_byte_and_task_limits_without_truncation():
    for value in (backlog(*(["PLANNED"] * 101)), b"x" * (512 * 1024 + 1), b"", b"\xff"):
        with pytest.raises(ValueError):
            release_manager.parse_monitoring_backlog(value)


def test_collector_reads_exact_commits_despite_dirty_worktree_and_replace_refs(instance):
    manager = release_manager.ReleaseManager(instance[0])
    git = shutil.which("git")
    assert git
    def command(*args):
        return subprocess.run([git, "-C", str(manager.source_repo), *args], check=True,
                              capture_output=True, text=True, timeout=15).stdout.strip()
    command("init")
    source = manager.source_repo / release_manager.MONITORING_BACKLOG_PATH
    commits = []
    for status in ("PLANNED", "DONE"):
        source.write_bytes(backlog(status, "DEFERRED"))
        command("add", release_manager.MONITORING_BACKLOG_PATH)
        command("-c", "user.name=Progress test", "-c", "user.email=progress@example.invalid",
                "commit", "-m", status)
        commits.append(command("rev-parse", "HEAD"))
    source.write_bytes(backlog("BLOCKED"))
    command("replace", commits[0], commits[1])
    assert manager._monitoring_snapshot(commits[0])["tasks"][0]["status"] == "PLANNED"
    assert manager._monitoring_snapshot(commits[1])["tasks"][0]["status"] == "DONE"
    assert manager._monitoring_snapshot("--help")["state"] == "unavailable"
    assert manager._monitoring_snapshot("c" * 40)["state"] == "unavailable"


def test_blob_size_is_checked_before_content_read(instance, monkeypatch):
    manager = release_manager.ReleaseManager(instance[0])
    commands = []
    def command(arguments, **kwargs):
        commands.append(arguments)
        return subprocess.CompletedProcess(arguments, 0, stdout=b"524289\n", stderr=b"")
    monkeypatch.setattr(release_manager.subprocess, "run", command)
    snapshot = manager._monitoring_snapshot("a" * 40)
    assert snapshot["state"] == "unavailable" and snapshot["tasks"] == []
    assert len(commands) == 1 and commands[0][-2] == "-s"
    assert "--no-replace-objects" in commands[0]


def instrument(manager, previous, target):
    manager._monitoring_blob = lambda sha: backlog("DONE", "DEFERRED", "PLANNED") if sha == target else backlog("PLANNED", "DEFERRED")
    saved = []
    original = manager._save_status
    def save():
        original()
        saved.append(copy.deepcopy(manager.status))
    manager._save_status = save
    return saved


def test_fetch_and_activation_keep_git_and_deployed_denominators_separate(instance):
    manager, _, previous, target = pipeline(instance, bootstrap=False)
    saved = instrument(manager, previous, target)
    manager.poll()
    running = next(item for item in saved if item["service"]["state"] == "deploying")["monitoring_progress"]
    assert running["latest"]["sha"] == target and len(running["latest"]["tasks"]) == 3
    assert running["deployed"]["sha"] == previous and len(running["deployed"]["tasks"]) == 2
    final = json.loads(manager.status_path.read_text(encoding="utf-8"))["monitoring_progress"]
    assert final["latest"] == final["deployed"]
    assert final["deployed"]["sha"] == target


@pytest.mark.parametrize("failure", ["api_tests", "public_health_check"])
def test_gate_failure_or_verified_rollback_preserves_previous_backlog(instance, failure):
    manager, _, previous, target = pipeline(instance, bootstrap=False, failure=failure)
    instrument(manager, previous, target)
    with pytest.raises(release_manager.DeploymentError):
        manager.poll()
    progress = manager.status["monitoring_progress"]
    assert progress["latest"]["sha"] == target and progress["latest"]["tasks"][0]["status"] == "DONE"
    assert progress["deployed"]["sha"] == previous and progress["deployed"]["state"] == "available"
    assert progress["deployed"]["tasks"][0]["status"] == "PLANNED"


def test_failed_rollback_remains_unavailable_across_later_failed_poll(instance):
    manager, _, previous, target = pipeline(instance, bootstrap=False, failure="public_health_check")
    instrument(manager, previous, target)
    manager._restore_previous = lambda *args: {"status": "failed"}
    with pytest.raises(release_manager.DeploymentError):
        manager.poll()
    assert manager.status["monitoring_progress"]["deployed"]["state"] == "unavailable"
    manager._record_poll_failure(release_manager.DeploymentError("fetch", "private failure details"))
    progress = manager.status["monitoring_progress"]
    assert progress["latest"]["state"] == progress["deployed"]["state"] == "unavailable"
    assert progress["latest"]["sha"] == target and progress["deployed"]["sha"] == previous
    assert "private failure" not in json.dumps(progress)
    manager._refresh_monitoring_progress(target)
    assert manager.status["monitoring_progress"]["deployed"]["state"] == "unavailable"
    manager._refresh_monitoring_progress(target, runtime_verified=True)
    assert manager.status["monitoring_progress"]["deployed"]["state"] == "available"


def test_interrupted_attempt_does_not_claim_a_noop_poll_reverified_runtime(instance):
    manager, _, previous, target = pipeline(instance, bootstrap=False)
    instrument(manager, previous, target)
    manager.status["last_run"] = {"id": "interrupted-test", "status": "deploying", "steps": []}
    manager._git = lambda *args, **kwargs: manager.expected_repository if args[0] == "remote" else previous if args[0] == "rev-parse" else ""
    manager.poll()
    assert manager.status["service"]["state"] == "idle"
    progress = manager.status["monitoring_progress"]
    assert progress["latest"]["state"] == "available"
    assert progress["deployed"]["sha"] == previous and progress["deployed"]["state"] == "unavailable"


def test_failing_fetch_preserves_independent_verified_deployed_snapshot(instance):
    manager, _, previous, target = pipeline(instance, bootstrap=False)
    instrument(manager, previous, target)
    manager.status["remote"] = {"sha": target}
    manager._git = lambda *args, **kwargs: (_ for _ in ()).throw(release_manager.DeploymentError("fetch", "secret"))
    with pytest.raises(release_manager.DeploymentError):
        manager.poll()
    progress = manager.status["monitoring_progress"]
    assert progress["latest"]["state"] == "unavailable" and progress["latest"]["tasks"] == []
    assert progress["latest"]["sha"] == target
    assert progress["deployed"]["state"] == "available" and progress["deployed"]["sha"] == previous


def test_progress_failure_does_not_reject_bootstrap_or_fabricate_completion(instance):
    manager, _, _, target = pipeline(instance)
    manager._monitoring_blob = lambda sha: (_ for _ in ()).throw(RuntimeError("do not expose this secret"))
    manager.poll()
    assert manager.status["last_run"]["status"] == "succeeded" and manager._load_deployed()["sha"] == target
    progress = manager.status["monitoring_progress"]
    assert all(progress[name]["state"] == "unavailable" and progress[name]["tasks"] == [] for name in ("latest", "deployed"))
    assert "secret" not in json.dumps(progress)


def test_other_instances_do_not_collect_monitoring_progress(instance):
    manager = release_manager.ReleaseManager(instance[0])
    manager.instance = None
    manager._monitoring_blob = lambda sha: pytest.fail("main must not read the Monitoring backlog")
    manager._refresh_monitoring_progress("a" * 40)
    assert "monitoring_progress" not in manager.status


def envelope():
    snapshot = {"sha": "a" * 40, "state": "available", "reason": None,
                "tasks": [{"id": "MV2-001", "title": "Task", "status": "DONE"}]}
    return {"schema_version": 1, "source_path": "BACKLOG_MONITORING_V2.md",
            "updated_at": "2026-09-10T20:00:00+00:00", "branch": "codex/HappyDucky02/monitoring-v2",
            "latest": snapshot, "deployed": copy.deepcopy(snapshot)}


def api_progress(tmp_path, value):
    (tmp_path / "status.json").write_text(json.dumps({"monitoring_progress": value}), encoding="utf-8")
    return deployment_snapshot(tmp_path)["monitoring_progress"]


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(schema_version=True),
    lambda value: value.update(source_path="../private.env"),
    lambda value: value.update(branch=[]),
    lambda value: value.update(updated_at="2026-09-10T20:00:00"),
    lambda value: value.update(updated_at="not a date"),
])
def test_api_rejects_invalid_progress_envelope(tmp_path, mutation):
    value = envelope()
    mutation(value)
    assert api_progress(tmp_path, value) is None


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(tasks=[]),
    lambda value: value.update(tasks=[value["tasks"][0]] * 101),
    lambda value: value.update(tasks=value["tasks"] * 2),
    lambda value: value["tasks"][0].update(status="COMPLETE"),
    lambda value: value["tasks"][0].update(status=[]),
    lambda value: value.update(sha="a" * 12),
    lambda value: value.update(reason="available despite error"),
])
def test_api_invalid_snapshot_is_unavailable_without_losing_other_snapshot(tmp_path, mutation):
    value = envelope()
    mutation(value["latest"])
    result = api_progress(tmp_path, value)
    assert result["latest"]["state"] == "unavailable" and result["latest"]["tasks"] == []
    assert result["deployed"]["state"] == "available"


def test_api_disagreement_for_same_commit_is_unavailable(tmp_path):
    value = envelope()
    value["deployed"]["tasks"][0]["status"] = "PLANNED"
    result = api_progress(tmp_path, value)
    assert result["latest"]["state"] == result["deployed"]["state"] == "unavailable"


def test_api_keeps_deferred_different_denominators_and_strips_extra_fields(tmp_path):
    value = envelope()
    value["latest"]["sha"] = "b" * 40
    value["latest"]["tasks"].append({"id": "MV2-026", "title": "Customs", "status": "DEFERRED", "extra": "discard"})
    value["private_path"] = "discard"
    result = api_progress(tmp_path, value)
    assert len(result["latest"]["tasks"]) == 2 and len(result["deployed"]["tasks"]) == 1
    assert result["latest"]["tasks"][1]["status"] == "DEFERRED"
    assert "discard" not in json.dumps(result)


def test_api_unavailable_never_exposes_attached_task_counts_and_missing_is_null(tmp_path):
    assert deployment_snapshot(tmp_path)["monitoring_progress"] is None
    value = envelope()
    value["latest"].update(state="unavailable", reason="Latest fetch failed.")
    result = api_progress(tmp_path, value)
    assert result["latest"]["tasks"] == [] and result["latest"]["reason"] == "Latest fetch failed."
