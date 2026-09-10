"""Native host controls and real journal transitions; Docker/Git never mutate here."""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_release_manager import ROOT, release_manager


@pytest.fixture
def instance(tmp_path):
    configuration = {
        "version": 1, "instance": "monitoring-v2", "branch": "codex/HappyDucky02/monitoring-v2",
        "compose_project": "helvetic-lens-v2", "docker_context": "desktop-linux",
        "base_dir": str(tmp_path), "expected_repository": "https://github.com/HappyMiha/helvetic-lens.git",
        "public_url": "https://monitoring.helveticlens.ch", "self_update": False,
    }
    for name in ("source_repo", "control_dir", "releases_dir", "state_dir", "tunnel_dir"):
        configuration[name] = str(tmp_path / name)
        (tmp_path / name).mkdir()
    (Path(configuration["tunnel_dir"]) / "token").write_text("synthetic tunnel token", encoding="utf-8")
    configuration["env_file"] = str(tmp_path / "private" / "production.env")
    Path(configuration["env_file"]).parent.mkdir()
    Path(configuration["env_file"]).write_text(
        "PUBLIC_BASE_URL=https://monitoring.helveticlens.ch\n"
        "HELVETIC_LENS_RELEASE=bootstrap-pending\n"
        f"HELVETIC_LENS_BACKUP_DIR={tmp_path / 'backups'}\n"
        "AUTH_SMTP_PASSWORD=synthetic-mail-secret\n", encoding="utf-8",
    )
    path = tmp_path / "selector.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    return path, configuration


def test_config_roundtrip_ignores_ambient_main_selectors(instance, monkeypatch):
    path, config = instance
    monkeypatch.setenv("HELVETIC_LENS_GIT_BRANCH", "main")
    monkeypatch.setenv("HELVETIC_LENS_BASE_DIR", "/wrong-main-root")
    monkeypatch.setenv("COMPOSE_PROFILES", "direct")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://wrong.example.ch")
    manager = release_manager.ReleaseManager(path)
    command = manager._compose(ROOT, "git-" + "a" * 40, "config", "--quiet")
    assert command[1:4] == ["--context", "desktop-linux", "compose"]
    assert command[command.index("--project-name") + 1] == "helvetic-lens-v2"
    assert manager.branch == config["branch"] and manager.source_repo == Path(config["source_repo"])
    environment = manager._compose_environment("git-" + "a" * 40)
    assert "COMPOSE_PROFILES" not in environment
    assert environment["PUBLIC_BASE_URL"] == config["public_url"]
    assert environment["HELVETIC_LENS_INSTANCE"] == "monitoring-v2"
    assert environment["HELVETIC_LENS_TUNNEL_DIR"] == config["tunnel_dir"]
    assert environment["HELVETIC_LENS_CONFIG_FILE"] == config["env_file"]
    assert environment["HELVETIC_LENS_DEPLOY_STATE_DIR"] == config["state_dir"]


@pytest.mark.parametrize("field,value", [
    ("PASSWORD", "secret"), ("version", True), ("self_update", True),
    ("compose_project", "helvetic-lens"), ("branch", "main"), ("branch", "--upload-pack=evil"),
    ("branch", "topic/../main"), ("public_url", "https://user:pass@monitoring.helveticlens.ch"),
    ("public_url", "https://monitoring.helveticlens.ch/other"), ("qa_user", "0:0"),
    ("api_test_timeout_seconds", 0), ("qa_memory", "unlimited"), ("source_repo", "relative"),
])
def test_invalid_instance_selectors_fail_without_commands(instance, field, value):
    path, config = instance
    config[field] = value
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError):
        release_manager.ReleaseManager(path)


def test_overlapping_paths_and_public_origin_mismatch_are_rejected(instance):
    path, config = instance
    config["control_dir"] = config["source_repo"]
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="overlap"):
        release_manager.load_config(path)
    config["control_dir"] = str(Path(config["base_dir"]) / "control")
    config["public_url"] = "https://other.helveticlens.ch"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="must match"):
        release_manager.ReleaseManager(path)


@pytest.mark.parametrize("selector", ["COMPOSE_PROFILES=direct", "COMPOSE_PROFILES=restore",
                                      "DOCKER_HOST=tcp://other-host:2375"])
def test_reserved_selectors_in_app_env_file_are_rejected_before_compose(instance, selector):
    path, config = instance
    with Path(config["env_file"]).open("a", encoding="utf-8") as stream:
        stream.write(selector + "\n")
    with pytest.raises(ValueError, match="reserved"):
        release_manager.ReleaseManager(path)


def test_native_lock_excludes_another_process_and_releases_after_exit(tmp_path):
    lock = tmp_path / "deployment.lock"
    module = ROOT / "deploy" / "release_manager.py"
    code = (
        "import importlib.util,sys;from pathlib import Path;"
        "s=importlib.util.spec_from_file_location('manager',sys.argv[1]);"
        "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
        "\nwith m.deployment_lock(Path(sys.argv[2])) as acquired: print(int(acquired))"
    )
    def child():
        return subprocess.run([sys.executable, "-c", code, str(module), str(lock)],
                              capture_output=True, text=True, check=True, timeout=15).stdout.strip()
    with release_manager.deployment_lock(lock) as acquired:
        assert acquired and child() == "0"
    assert child() == "1" and lock.exists()


def test_configured_controller_never_self_updates_or_infers_live_sha_from_env(instance):
    path, config = instance
    manager = release_manager.ReleaseManager(path)
    controller = Path(config["control_dir"]) / "release_manager.py"
    controller.write_text("pinned controller", encoding="utf-8")
    manager._install_manager_update(ROOT)
    assert controller.read_text(encoding="utf-8") == "pinned controller"
    with pytest.raises(release_manager.DeploymentError, match="explicit --bootstrap"):
        manager._bootstrap_deployed()
    manager.bootstrap = True
    assert manager._bootstrap_deployed() == {}
    release_manager.atomic_json(manager.deployed_path, {"sha": "a" * 40})
    with pytest.raises(release_manager.DeploymentError, match="already has"):
        manager._bootstrap_deployed()


def test_tunnel_configuration_uses_external_mount_without_symlink(instance):
    path, _ = instance
    manager = release_manager.ReleaseManager(path)
    manager._link_runtime_configuration(manager.releases_dir)
    assert not (manager.releases_dir / ".cloudflared").exists()


def test_bom_environment_keeps_one_release_during_publication_and_rollback(tmp_path):
    path = tmp_path / "production.env"
    path.write_text("HELVETIC_LENS_RELEASE=old-release\nAUTH_SMTP_PASSWORD=synthetic-secret\n",
                    encoding="utf-8-sig")
    for release in ("git-new-release", "old-release"):
        release_manager.atomic_update_release(path, release)
        data = path.read_text(encoding="utf-8")
        assert data.count("HELVETIC_LENS_RELEASE=") == 1 and "\ufeff" not in data
        assert release_manager.read_env(path) == {
            "HELVETIC_LENS_RELEASE": release, "AUTH_SMTP_PASSWORD": "synthetic-secret",
        }


@pytest.mark.parametrize("existing", ["container", "labelled_volume", "unlabelled_volume", "backup"])
def test_bootstrap_refuses_existing_instance_resources(instance, existing):
    path, config = instance
    manager = release_manager.ReleaseManager(path, bootstrap=True)
    def command(arguments, **_):
        output = ""
        if existing == "container" and "ps" in arguments:
            output = "existing-container"
        if existing == "labelled_volume" and "volume" in arguments and "-q" in arguments:
            output = "existing-volume"
        if existing == "unlabelled_volume" and "{{.Name}}" in arguments:
            output = "other-volume\nhelvetic-lens-v2_postgres_data\n"
        return SimpleNamespace(stdout=output, returncode=0)
    manager._run = command
    if existing == "backup":
        backups = Path(config["base_dir"]) / "backups"
        backups.mkdir()
        (backups / "old-backup").touch()
    with pytest.raises(release_manager.DeploymentError):
        manager._assert_empty_instance()


def pipeline(instance, *, bootstrap=True, failure=None):
    path, _ = instance
    manager = release_manager.ReleaseManager(path, bootstrap=bootstrap)
    previous, target = "b" * 40, "a" * 40
    manager._git = lambda *args, **kwargs: (manager.expected_repository if args[0] == "remote"
                                           else target if args[0] == "rev-parse" else "")
    manager._commit_summary = lambda sha: "Synthetic release"
    manager._changes = lambda *args: []
    manager._ensure_release = lambda sha: ROOT
    calls = []
    def command(arguments, **options):
        calls.append((arguments, options["step"]))
        if options["step"] == failure:
            raise release_manager.DeploymentError(failure, "synthetic-mail-secret failed")
        if "backup" in arguments and "once" in arguments:
            return SimpleNamespace(returncode=0, stdout="Backup 20260910T170000Z completed.\n")
        if options["step"] == "capture_model_runtime":
            return SimpleNamespace(returncode=0, stdout='{"state":"stopped"}')
        return SimpleNamespace(returncode=0, stdout="")
    manager._run = command
    def health():
        calls.append(([], "public_health_check"))
        if failure == "public_health_check" and manager.health_release == "git-" + target:
            raise release_manager.DeploymentError(failure, "synthetic health failure")
    manager._public_health = health
    if not bootstrap:
        release_manager.atomic_json(manager.deployed_path, {
            "sha": previous, "release": "git-" + previous, "release_dir": str(ROOT),
        })
    return manager, calls, previous, target


def test_bootstrap_executes_gates_initial_backup_and_exact_activation(instance):
    manager, calls, _, target = pipeline(instance)
    manager.poll()
    phases = [phase for _, phase in calls]
    assert phases.index("api_tests") < phases.index("start_release") < phases.index("initial_backup")
    assert "capture_model_runtime" not in phases and "pre_deploy_backup" not in phases
    assert manager._load_deployed()["sha"] == target
    assert manager.status["last_run"]["status"] == "succeeded"
    assert manager.status["last_run"]["activated_sha"] == target
    assert manager.status["last_run"]["backup_id"] == "20260910T170000Z"
    for arguments, _ in calls:
        if "compose" in arguments:
            assert arguments[arguments.index("--project-name") + 1] == "helvetic-lens-v2"
            assert arguments[1:3] == ["--context", "desktop-linux"]
    qa = next(arguments for arguments, phase in calls if phase == "api_tests" and "--user" in arguments)
    assert qa[qa.index("--user") + 1] == "1000:1000"
    assert qa[qa.index("--memory") + 1] == "4g" and qa[qa.index("--cpus") + 1] == "2"


@pytest.mark.parametrize("failure", ["api_tests", "start_release", "initial_backup", "public_health_check"])
def test_failed_bootstrap_never_claims_old_release_or_borrows_resources(instance, failure):
    manager, calls, _, _ = pipeline(instance, failure=failure)
    with pytest.raises(release_manager.DeploymentError):
        manager.poll()
    assert manager._load_deployed() == {}
    run = manager.status["last_run"]
    assert run["status"] == "failed" and run["activated_sha"] is None
    assert "synthetic-mail-secret" not in json.dumps(run)
    phases = [phase for _, phase in calls]
    assert "capture_model_runtime" not in phases and "rollback_restore" not in phases
    if failure == "api_tests":
        assert "start_release" not in phases and "bootstrap_stop" not in phases
    else:
        assert "bootstrap_stop" in phases
        assert run["rollback"]["candidate_stopped"]
        assert "No previous release" in run["rollback"]["reason"]


def test_upgrade_health_failure_restores_only_configured_instance_and_previous_identity(instance):
    manager, calls, previous, _ = pipeline(instance, bootstrap=False, failure="public_health_check")
    with pytest.raises(release_manager.DeploymentError):
        manager.poll()
    assert manager._load_deployed()["sha"] == previous
    assert manager.health_release == "git-" + previous
    assert manager.status["last_run"]["rollback"]["status"] == "succeeded"
    phases = [phase for _, phase in calls]
    assert "pre_deploy_backup" in phases and "rollback_restore" in phases
    model = next(arguments for arguments, phase in calls if phase == "capture_model_runtime")
    assert "helvetic-lens-v2-model-manager-1" in model
    for arguments, _ in calls:
        assert "helvetic-lens-model-manager-1" not in arguments
        if "compose" in arguments:
            assert arguments[arguments.index("--project-name") + 1] == "helvetic-lens-v2"


def test_failed_writer_stop_prevents_destructive_rollback_restore(instance):
    manager = release_manager.ReleaseManager(instance[0])
    calls = []
    def command(arguments, **options):
        calls.append((arguments, options))
        assert options.get("check") is True
        raise release_manager.DeploymentError("quiesce", "Could not stop candidate writers.")
    manager._run = command
    result = manager._restore_previous(ROOT, "git-old", ROOT, "git-new", "20260910T170000Z", True, None)
    assert result["status"] == "failed" and result["backup_restored"] is False
    assert len(calls) == 1 and calls[0][1]["step"] == "quiesce"
    assert "migrate" in calls[0][0] and "restore" not in calls[0][0]


@pytest.mark.parametrize("changes", [" M compose.monitoring.yaml", "?? extra.txt", "!! .env.production"])
def test_modified_immutable_checkout_is_rejected_before_use(instance, changes):
    manager = release_manager.ReleaseManager(instance[0])
    sha = "a" * 40
    (manager.releases_dir / sha).mkdir()
    calls = []
    def command(arguments, **options):
        calls.append(arguments)
        return SimpleNamespace(returncode=0, stdout=sha if "rev-parse" in arguments else changes)
    manager._run = command
    with pytest.raises(release_manager.DeploymentError, match="local changes or extra files"):
        manager._ensure_release(sha)
    assert len(calls) == 2 and "--ignored" in calls[1]


def test_public_health_rejects_wrong_instance_or_release(instance, monkeypatch):
    manager = release_manager.ReleaseManager(instance[0])
    manager.health_release = "git-" + "a" * 40
    class Response:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, limit):
            return json.dumps({"status": "ready", "instance": "main", "release": manager.health_release}).encode()
    monkeypatch.setattr(release_manager.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    monkeypatch.setattr(release_manager.time, "sleep", lambda *_: None)
    with pytest.raises(release_manager.DeploymentError, match="expected instance"):
        manager._public_health()


@pytest.mark.parametrize("directory,valid", [
    ("C:/HelveticLens/monitoring-backups", True), ("C:/", False),
    ("C:relative", False), ("./backups", False), ("/srv/monitoring-backups", False),
])
def test_validator_uses_explicit_windows_path_semantics(directory, valid):
    from scripts.validate_production_env import validate
    errors = validate({"HELVETIC_LENS_BACKUP_DIR": directory}, host_platform="nt")
    rejected = any(error.startswith("HELVETIC_LENS_BACKUP_DIR:") for error in errors)
    assert rejected is not valid
