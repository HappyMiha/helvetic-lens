import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
import test_release_instance
from fastapi.testclient import TestClient
from test_administration import FakeFetcher, ScriptedModel, csrf, promote, register, settings
from test_release_instance import pipeline
from test_release_manager import release_manager

from helvetic_lens.config import DomainError
from helvetic_lens.deployment_history import history_detail
from helvetic_lens.deployment_policy import PolicyUpdate, read_policy, update_policy
from helvetic_lens.main import create_app

instance = test_release_instance.instance
REASON = "Emergency repair for incident 123"


def save(directory, scope, profile, revision=None):
    return update_policy(directory, PolicyUpdate(
        expected_revision=read_policy(directory)["revision"] if revision is None else revision,
        scope=scope, profile=profile, reason=REASON if profile == "hotfix" else None,
    ), actor="synthetic-admin")


@pytest.mark.parametrize("default", ["standard", "full", "hotfix"])
@pytest.mark.parametrize("override", ["standard", "full", "hotfix"])
def test_next_attempt_consumes_once_then_restores_each_saved_default(instance, default, override):
    manager, calls, _, target = pipeline(instance, bootstrap=False)
    save(manager.policy_dir, "default", default)
    before = save(manager.policy_dir, "next", override)
    manager.poll()
    run = history_detail(manager.state_dir, manager.run_record["id"])
    assert run["test_policy"]["profile"] == override
    assert run["test_policy"]["source"] == "next"
    assert run["test_policy"]["settings_revision"] == before["revision"]
    assert ("api_tests" in [step for _, step in calls]) == (override != "hotfix")
    after = read_policy(manager.policy_dir)
    assert after["next"] is None and after["default"]["profile"] == default
    assert after["revision"] == before["revision"] + 1
    # Retrying the same claim is idempotent even after a newer override is saved.
    pending = save(manager.policy_dir, "next", "full")
    assert manager._claim_test_policy()["profile"] == override
    assert read_policy(manager.policy_dir) == pending
    save(manager.policy_dir, "next", None)
    # Fresh controller process, new attempt: default is durable across restarts.
    restarted = release_manager.ReleaseManager(instance[0])
    restarted.run_record = {"id": "another-attempt", "target_sha": target}
    selected = restarted._claim_test_policy()
    assert selected["profile"] == default and selected["source"] == "default"


@pytest.mark.parametrize("failure", ["api_tests", "public_health_check"])
def test_failed_attempt_does_not_reuse_override(instance, failure):
    manager, _, previous, _ = pipeline(instance, bootstrap=False, failure=failure)
    save(manager.policy_dir, "next", "full")
    with pytest.raises(release_manager.DeploymentError):
        manager.poll()
    assert read_policy(manager.policy_dir)["next"] is None
    assert manager.run_record["test_policy"]["source"] == "next"
    assert manager._load_deployed()["sha"] == previous
    manager.run_record = {"id": "retry", "target_sha": "a" * 40}
    assert manager._claim_test_policy()["profile"] == "standard"


@pytest.mark.parametrize("blocked", ["idle", "lock", "retry", "fetch", "ancestry"])
def test_polls_without_eligible_attempt_preserve_override(instance, blocked):
    manager, _, _, target = pipeline(instance, bootstrap=False)
    saved = save(manager.policy_dir, "next", "hotfix")
    if blocked == "idle":
        manager._bootstrap_deployed = lambda: {"sha": target, "release": "existing"}
    if blocked == "retry":
        manager.status["last_run"] = {"id": "failed", "status": "failed", "target_sha": target,
                                      "finished_at": release_manager.timestamp(), "steps": []}
    if blocked in {"fetch", "ancestry"}:
        original = manager._git if blocked == "fetch" else manager._run
        def fail(*args, **kwargs):
            if kwargs.get("step") == ("fetch" if blocked == "fetch" else "verify_history"):
                raise release_manager.DeploymentError(kwargs["step"], "Synthetic unavailable prerequisite")
            return original(*args, **kwargs)
        if blocked == "fetch":
            manager._git = fail
        else:
            manager._run = fail
        with pytest.raises(release_manager.DeploymentError):
            manager.poll()
    elif blocked == "lock":
        with release_manager.deployment_lock(manager.lock_path):
            manager.poll()
    else:
        manager.poll()
    assert read_policy(manager.policy_dir) == saved


@pytest.mark.parametrize("bootstrap", [False, True])
def test_manual_and_bootstrap_profiles_preserve_queued_choice(instance, bootstrap):
    manager, _, _, _ = pipeline(instance, bootstrap=bootstrap)
    manager.profile_explicit = True
    manager.test_profile = "full"
    saved = save(manager.policy_dir, "next", "hotfix")
    manager.poll()
    assert manager.run_record["test_policy"]["source"] == ("bootstrap" if bootstrap else "invocation")
    assert read_policy(manager.policy_dir) == saved


def test_two_admins_cannot_overwrite_each_other_and_consumption_invalidates_old_forms(instance):
    manager, _, _, _ = pipeline(instance, bootstrap=False)
    read_policy(manager.policy_dir)
    def attempt(mode):
        try:
            return save(manager.policy_dir, "next", mode, revision=0)
        except DomainError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, ["full", "hotfix"]))
    assert sum(isinstance(value, dict) for value in outcomes) == 1
    assert "deployment_policy_conflict" in outcomes
    before = read_policy(manager.policy_dir)
    manager.poll()
    with pytest.raises(DomainError) as caught:
        save(manager.policy_dir, "default", "full", revision=before["revision"])
    assert caught.value.code == "deployment_policy_conflict"
    assert read_policy(manager.policy_dir)["default"]["profile"] == "standard"


def test_new_choice_saved_during_attempt_applies_only_to_later_attempt(instance):
    manager, calls, _, _ = pipeline(instance, bootstrap=False)
    save(manager.policy_dir, "next", "full")
    checkout = manager._ensure_release
    def changing_settings(sha):
        save(manager.policy_dir, "default", "hotfix")
        save(manager.policy_dir, "next", "standard")
        return checkout(sha)
    manager._ensure_release = changing_settings
    manager.poll()
    assert manager.run_record["test_policy"]["profile"] == "full"
    assert "api_tests" in [step for _, step in calls]
    assert read_policy(manager.policy_dir)["next"]["profile"] == "standard"


def test_invalid_policy_fails_before_host_changes(instance):
    manager, calls, _, _ = pipeline(instance, bootstrap=False)
    save(manager.policy_dir, "next", "hotfix")
    with sqlite3.connect(manager.policy_dir / "policy.sqlite3") as connection:
        document = read_policy(manager.policy_dir)
        document = {key: document[key] for key in ("default", "next", "updated_at")}
        document["next"]["reason"] = None
        connection.execute("UPDATE settings SET document=?", (json.dumps(document),))
    with pytest.raises(release_manager.DeploymentError, match="settings are unavailable or invalid"):
        manager.poll()
    assert "build_images" not in [step for _, step in calls]
    assert manager.run_record["error_step"] == "test_policy"


def test_manual_hotfix_reason_is_redacted_even_when_checkout_fails(instance):
    manager, _, _, target = pipeline(instance, bootstrap=False)
    manager.profile_explicit, manager.test_profile, manager.requested_sha = True, "hotfix", target
    manager.hotfix_reason = REASON + " token=synthetic-private-value"
    def unavailable_checkout(sha):
        raise release_manager.DeploymentError("checkout", "Synthetic checkout failure")
    manager._ensure_release = unavailable_checkout
    with pytest.raises(release_manager.DeploymentError):
        manager.poll()
    assert "synthetic-private-value" not in manager.status_path.read_text()
    assert "synthetic-private-value" not in manager.history_path.read_text()
    assert "[redacted]" in manager.status_path.read_text()


@pytest.mark.parametrize("reason", ["П" * 500, "🔧" * 500, "token=x " * 60],
                         ids=["cyrillic", "emoji", "redaction"])
def test_valid_unicode_and_redacted_reasons_remain_usable_by_host(instance, reason):
    manager, _, _, _ = pipeline(instance, bootstrap=False)
    for scope in ("default", "next"):
        update_policy(manager.policy_dir, PolicyUpdate(
            expected_revision=read_policy(manager.policy_dir)["revision"],
            scope=scope, profile="hotfix", reason=reason,
        ), actor="synthetic-admin")
    manager.poll()
    after = read_policy(manager.policy_dir)
    assert after["next"] is None and after["default"]["profile"] == "hotfix"
    assert 10 <= len(after["default"]["reason"]) <= 500
    assert "token=x" not in str(after)


def test_policy_api_requires_admin_csrf_and_records_edit_without_secrets(tmp_path):
    configured = settings(tmp_path)
    configured.deployment_policy_dir = tmp_path / "policy"
    app = create_app(configured, fetcher=FakeFetcher(), model_client=ScriptedModel())
    endpoint = "/api/admin/deployments/policy"
    with TestClient(app) as client:
        assert client.get(endpoint).status_code == 401
        register(client, "policy@example.ch")
        assert client.get(endpoint).status_code == 403
        body = {"scope": "next", "profile": "hotfix", "reason": REASON + " token=private-token",
                "expected_revision": 0}
        assert client.patch(endpoint, json=body, headers=csrf(client)).status_code == 403
        promote(app.state.service, "policy@example.ch")
        assert client.patch(endpoint, json=body).status_code == 403
        assert client.get(endpoint).json()["next"] is None
        for invalid in [{**body, "reason": "short"}, {**body, "profile": "unknown"},
                        {**body, "expected_revision": True}, {**body, "command": "arbitrary"}]:
            assert client.patch(endpoint, json=invalid, headers=csrf(client)).status_code == 422
        saved = client.patch(endpoint, json=body, headers=csrf(client))
        assert saved.status_code == 200
        assert "private-token" not in saved.text and "[redacted]" in saved.text
        assert client.patch(endpoint, json=body, headers=csrf(client)).status_code == 409
        current = client.get(endpoint).json()
        assert current == saved.json()
        cleared = client.patch(endpoint, json={"scope": "next", "profile": None,
                                               "expected_revision": current["revision"]}, headers=csrf(client))
        assert cleared.status_code == 200 and cleared.json()["next"] is None
    with sqlite3.connect(configured.deployment_policy_dir / "policy.sqlite3") as connection:
        edits = connection.execute("SELECT actor, document FROM edits ORDER BY revision").fetchall()
    assert len(edits) == 2 and all(row[0] for row in edits)
    assert "private-token" not in str(edits)


def test_unconfigured_and_anonymous_dev_cannot_change_host_policy(tmp_path):
    configured = settings(tmp_path)
    configured.allow_anonymous_dev = True
    app = create_app(configured, fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        endpoint = "/api/admin/deployments/policy"
        assert client.get(endpoint).status_code == 403
        assert client.patch(endpoint, json={"scope": "next", "profile": "full", "expected_revision": 0}).status_code == 403
    assert read_policy(None)["enabled"] is False
    with pytest.raises(DomainError):
        save(None, "default", "full")
