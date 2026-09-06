import hashlib
import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from model_manager.core import ModelManager, ModelManagerError
from test_manager import manager_factory as manager_factory_fixture
from test_manager import wait_for


class Process:
    stdout = None

    def __init__(self):
        self.returncode = None

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.returncode = -9


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    factory = manager_factory_fixture.__wrapped__(tmp_path, monkeypatch)
    manager, _ = factory()
    entry = manager.entries["apertus-test"]
    entry["immutable_revision"] = "1" * 40
    entry["requirements"]["recommended_context"] = 4096
    template = tmp_path / "chat.jinja"
    template.write_bytes(b"synthetic-template")
    entry["chat_template"] = str(template)
    manager.llama_server.write_bytes(b"synthetic-runner-not-executable")
    manager.runtime_image = "synthetic/runner@sha256:" + "2" * 64
    manager.accept_license(entry["id"], True)
    manager.start_download(entry["id"], use_cached_copy=True)
    wait_for(manager, entry["id"], lambda model: model["installed"])
    launches = []

    def launch(command, **kwargs):
        process = Process()
        launches.append((command, kwargs, process))
        return process

    def ready(model_id, runner, _alias):
        with manager.lock:
            runner["state"] = "ready"
            manager._sync_deployment_state(model_id)

    monkeypatch.setattr("model_manager.core.subprocess.Popen", launch)
    monkeypatch.setattr(manager, "_drain_logs", lambda _runner: None)
    monkeypatch.setattr(manager, "_wait_until_ready", ready)
    yield manager, entry, launches
    for lease in list(manager.inference_leases):
        manager.release_inference(lease)
    manager.stop_model(entry["id"])


def start(runtime):
    manager, entry, _ = runtime
    manager.start_model(entry["id"])
    wait_for(manager, entry["id"], lambda model: model["state"] == "ready")
    return manager.runtime_snapshot()


def test_snapshot_binds_observed_launch_inputs_without_claiming_quality(runtime):
    manager, entry, launches = runtime
    snapshot = start(runtime)
    identity = snapshot["identity"]
    assert snapshot["schema_version"] == "local-runtime-binding-v1"
    assert snapshot["available"] is True
    assert len(snapshot["binding_fingerprint"]) == 64
    assert len(snapshot["deployment_id"]) == 32
    assert identity["model_revision"] == "1" * 40
    assert identity["artifact_sha256"] == manager._hash_file(manager._artifact_path(entry))
    assert identity["tokenizer_sha256"] == identity["artifact_sha256"]
    assert identity["chat_template_sha256"] == hashlib.sha256(b"synthetic-template").hexdigest()
    manifest = snapshot["identity_evidence"]["runtime_manifest"]
    assert manifest["executable_sha256"] == hashlib.sha256(b"synthetic-runner-not-executable").hexdigest()
    assert identity["runtime_sha256"] == hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert snapshot["identity_evidence"]["image_provenance"] == "trusted_launcher_assertion"
    command = launches[0][0]
    assert command[command.index("--ctx-size") + 1] == str(snapshot["context_window_tokens"]) == "4096"
    assert command[command.index("--n-predict") + 1] == str(snapshot["default_output_tokens"]) == "700"
    assert command[command.index("--alias") + 1] == snapshot["served_model_id"] == "local-apertus"
    snapshot["identity"]["model_id"] = "caller-mutation"
    assert manager.runtime_snapshot()["identity"]["model_id"] == entry["id"]


def test_restart_of_same_model_invalidates_inflight_binding_not_identity(runtime):
    manager, entry, _ = runtime
    before = start(runtime)
    old_target = manager.inference_targets()[0]
    manager.stop_model(entry["id"])
    assert manager.runtime_snapshot()["available"] is False
    assert manager.runtime_snapshot()["identity"] is None
    with pytest.raises(ModelManagerError) as stopped:
        manager.check_runtime_binding(before["binding_fingerprint"])
    assert stopped.value.code == "runtime_binding_changed"
    after = start(runtime)
    assert after["identity"] == before["identity"]
    assert after["deployment_id"] != before["deployment_id"]
    assert after["binding_fingerprint"] != before["binding_fingerprint"]
    with pytest.raises(ModelManagerError):
        manager.reserve_inference(old_target, None, "local-apertus")
    assert not manager.inference_leases


@pytest.mark.parametrize("mutation", ["template", "executable", "image", "context"])
def test_changed_launch_inputs_change_binding(runtime, mutation):
    manager, entry, _ = runtime
    before = start(runtime)
    manager.stop_model(entry["id"])
    if mutation == "template":
        Path(entry["chat_template"]).write_bytes(b"new-template")
    elif mutation == "executable":
        manager.llama_server.write_bytes(b"new-synthetic-runner")
    elif mutation == "image":
        manager.runtime_image = "synthetic/runner@sha256:" + "3" * 64
    else:
        entry["requirements"]["recommended_context"] = 8192
    after = start(runtime)
    assert after["binding_fingerprint"] != before["binding_fingerprint"]
    if mutation == "context":
        assert after["context_window_tokens"] == 8192
        assert after["identity"] == before["identity"]
    else:
        assert after["identity"] != before["identity"]


def test_same_size_model_tampering_after_download_is_rejected_before_launch(runtime):
    manager, entry, launches = runtime
    manager._artifact_path(entry).write_bytes(b"b" * entry["size_bytes"])
    assert manager.describe(entry["id"])["installed"] is True  # Former saved checksum alone.
    with pytest.raises(ModelManagerError) as error:
        manager.start_model(entry["id"])
    assert error.value.code == "checksum_mismatch"
    assert not launches
    assert manager.describe(entry["id"])["installed"] is False
    assert not manager.runtime_snapshot()["available"]


@pytest.mark.parametrize("missing", ["revision", "image", "template", "executable"])
def test_missing_identity_input_never_inherits_catalogue_approval(runtime, missing):
    manager, entry, _ = runtime
    if missing == "revision":
        entry["immutable_revision"] = "main"
    elif missing == "image":
        manager.runtime_image = "runner:latest"
    elif missing == "template":
        entry["chat_template"] = "synthetic-missing-template"
    else:
        manager.llama_server.unlink()
    snapshot = start(runtime)
    assert snapshot["identity"] is None
    assert snapshot["identity_evidence"]["reason"] != "launch_inputs_recorded"
    assert snapshot["binding_fingerprint"]  # Legacy/limited inference can still bind a deployment.


def test_lease_prevents_manager_replacement_until_release_even_after_runner_dies(runtime):
    manager, entry, launches = runtime
    snapshot = start(runtime)
    target = manager.inference_targets()[0]
    lease, observed = manager.reserve_inference(target, snapshot["binding_fingerprint"], "local-apertus")
    assert observed == snapshot
    with pytest.raises(ModelManagerError) as busy:
        manager.stop_model(entry["id"])
    assert busy.value.code == "model_busy"
    launches[0][2].returncode = 1
    with pytest.raises(ModelManagerError) as restarting:
        manager.start_model(entry["id"])
    assert restarting.value.code == "model_busy"
    assert len(launches) == 1
    manager.release_inference(lease)
    manager.release_inference(lease)  # Idempotent cleanup cannot corrupt another lease.
    manager.stop_model(entry["id"])
    after = start(runtime)
    assert after["binding_fingerprint"] != snapshot["binding_fingerprint"]


def test_wrong_model_or_dead_slot_never_acquires_a_lease(runtime):
    manager, _, launches = runtime
    snapshot = start(runtime)
    target = manager.inference_targets()[0]
    with pytest.raises(ModelManagerError) as mismatch:
        manager.reserve_inference(target, snapshot["binding_fingerprint"], "another-model")
    assert mismatch.value.code == "runtime_model_mismatch"
    launches[0][2].returncode = 1
    with pytest.raises(ModelManagerError) as dead:
        manager.reserve_inference(target, None, "local-apertus")
    assert dead.value.code == "runtime_binding_changed"
    assert not manager.inference_leases


def test_late_old_runner_callbacks_cannot_rewrite_a_new_deployment(runtime):
    manager, entry, _ = runtime
    start(runtime)
    old_runner = manager.runners[0]
    manager.stop_model(entry["id"])
    before = start(runtime)
    old_runner["process"].stdout = io.StringIO("")
    ModelManager._drain_logs(manager, old_runner)
    ModelManager._wait_until_ready(manager, entry["id"], old_runner, "local-apertus")
    assert manager.runtime_snapshot() == before
    assert manager.describe(entry["id"])["state"] == "ready"
