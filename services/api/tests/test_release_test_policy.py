"""Actual controller/journal transitions with isolated Git and Docker doubles."""

import pytest
import test_release_instance
from test_release_instance import pipeline
from test_release_manager import release_manager

from helvetic_lens.deployment_history import history_detail

instance = test_release_instance.instance


@pytest.mark.parametrize("profile", ["standard", "full", "hotfix"])
def test_profiles_select_checks_and_record_truthful_activation(instance, profile):
    manager, calls, _, target = pipeline(instance, bootstrap=False)
    manager.test_profile = profile
    if profile == "hotfix":
        manager.requested_sha = target
        manager.hotfix_reason = "Emergency repair for incident 123; token=synthetic-mail-secret"
    manager.poll()
    run = history_detail(manager.state_dir, manager.run_record["id"])
    assert run["test_policy"]["profile"] == profile
    assert run["activated_sha"] == target and run["status"] == "succeeded"
    phases = [phase for _, phase in calls]
    for required in ("api_lint", "validate_configuration", "build_images", "quiesce",
                     "pre_deploy_backup", "start_release", "public_health_check"):
        assert required in phases
    skipped = {step["name"]: step for step in run["steps"] if step["status"] == "skipped"}
    build = next(arguments for arguments, phase in calls if phase == "build_images")
    if profile == "hotfix":
        assert "api_tests" not in phases
        assert set(skipped) == {"api_tests", "web_tests"}
        assert "HELVETIC_LENS_SKIP_TESTS=1" in build
        assert run["test_policy"]["suites"] == []
        assert "synthetic-mail-secret" not in str(run)
        assert "incident 123" in skipped["api_tests"]["reason"]
        # A later automatic invocation never inherits an emergency bypass.
        assert release_manager.ReleaseManager(instance[0]).test_profile == "standard"
    else:
        assert set(skipped) == ({"integration_tests"} if profile == "standard" else set())
        assert "--build-arg" not in build
        qa = next(arguments for arguments, phase in calls if phase == "api_tests" and "--user" in arguments)
        assert qa[qa.index("--suite") + 1] == ("release" if profile == "standard" else "full")
        assert qa[qa.index("--workers") + 1] == "2" and "--fail-fast" in qa
        assert qa[qa.index("--cpus") + 1] == "2"


@pytest.mark.parametrize("profile", ["standard", "full"])
def test_failed_checks_prevent_image_build_or_activation(instance, profile):
    manager, calls, previous, _ = pipeline(instance, bootstrap=False, failure="api_tests")
    manager.test_profile = profile
    with pytest.raises(release_manager.DeploymentError):
        manager.poll()
    assert manager._load_deployed()["sha"] == previous
    assert manager.run_record["activated_sha"] is None
    assert not {"build_images", "quiesce_writers", "start_release"} & {phase for _, phase in calls}
    assert next(step for step in manager.run_record["steps"] if step["name"] == "api_tests")["status"] == "failed"


def test_hotfix_still_rolls_back_when_readiness_fails(instance):
    manager, _, previous, target = pipeline(instance, bootstrap=False, failure="public_health_check")
    manager.test_profile, manager.requested_sha = "hotfix", target
    manager.hotfix_reason = "Emergency repair for incident 123"
    with pytest.raises(release_manager.DeploymentError):
        manager.poll()
    assert manager._load_deployed()["sha"] == previous
    assert manager.run_record["status"] == "failed" and manager.run_record["activated_sha"] is None
    assert manager.run_record["rollback"]["status"] == "succeeded"


def test_hotfix_rejects_moving_main_before_any_release_command(instance):
    manager, calls, _, _ = pipeline(instance, bootstrap=False)
    manager.test_profile, manager.requested_sha = "hotfix", "c" * 40
    manager.hotfix_reason = "Emergency repair for incident 123"
    with pytest.raises(release_manager.DeploymentError, match="does not match fetched main"):
        manager.poll()
    assert calls == [] and manager.run_record is None


def test_hotfix_never_interrupts_an_active_deployment(instance):
    manager, calls, _, target = pipeline(instance, bootstrap=False)
    manager.requested_sha = target
    with release_manager.deployment_lock(manager.lock_path):
        with pytest.raises(release_manager.DeploymentError, match="deployment is active"):
            manager.poll()
    assert calls == [] and manager.run_record is None


@pytest.mark.parametrize("profile", ["standard", "hotfix"])
def test_only_explicit_hotfix_can_bypass_a_failed_candidates_retry_delay(instance, profile):
    manager, calls, _, target = pipeline(instance, bootstrap=False)
    manager.status["last_run"] = {
        "id": "previous-failure", "status": "failed", "target_sha": target,
        "finished_at": release_manager.timestamp(), "steps": [],
    }
    manager.test_profile = profile
    if profile == "hotfix":
        manager.requested_sha = target
        manager.hotfix_reason = "Emergency retry for incident 123"
    manager.poll()
    if profile == "hotfix":
        assert manager.run_record["status"] == "succeeded"
        assert manager.run_record["activated_sha"] == target
        assert "api_tests" not in {phase for _, phase in calls}
    else:
        assert manager.status["service"]["state"] == "retry_wait"
        assert manager.run_record is None and calls == []


@pytest.mark.parametrize("sha,reason", [(None, "Emergency repair"), ("main", "Emergency repair"),
                                       ("a" * 40, None), ("a" * 40, " "), ("a" * 40, "x" * 501)])
def test_invalid_hotfix_is_rejected_before_host_access(sha, reason):
    with pytest.raises(ValueError, match="Hotfix requires"):
        release_manager.ReleaseManager(test_profile="hotfix", requested_sha=sha, hotfix_reason=reason)


def test_old_target_keeps_its_complete_original_gate(tmp_path):
    manager = release_manager.ReleaseManager.__new__(release_manager.ReleaseManager)
    manager.test_profile = "standard"
    assert manager._release_test_policy(tmp_path) == {
        "profile": "full", "suites": ["full"], "workers": 0, "reason": None,
    }
    manager.test_profile = "hotfix"
    with pytest.raises(release_manager.DeploymentError, match="predates audited hotfix"):
        manager._release_test_policy(tmp_path)
