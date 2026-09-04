import hashlib
import io
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from model_manager.core import ModelManager, ModelManagerError


def wait_for(manager, model_id, predicate, timeout=4):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = manager.describe(model_id)
        if predicate(value):
            return value
        time.sleep(0.02)
    raise AssertionError(manager.describe(model_id))


@pytest.fixture
def manager_factory(tmp_path, monkeypatch):
    def make(payload=b"a" * 64, expected=None):
        cache = tmp_path / "cache.gguf"
        cache.write_bytes(payload)
        entry = {
            "id": "apertus-test",
            "display_name": "Apertus test",
            "family": "Apertus",
            "upstream_repo": "example/Apertus",
            "base_model_repo": "example/Apertus",
            "immutable_revision": "abc123",
            "gguf_file": "apertus-test.gguf",
            "quantization": "Q4_K_M",
            "sha256": expected or hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
            "download_url": "https://invalid.example/model.gguf",
            "legacy_cache_blob": str(cache),
            "license": {"name": "test", "url": "https://example.test/license"},
            "license_acceptance": "required",
            "chat_template": "/templates/apertus.jinja",
            "served_model_id": "local-apertus",
            "structured_output": True,
            "requirements": {
                "min_ram_bytes": 1,
                "min_disk_bytes": 1,
                "min_vram_bytes": 1,
                "recommended_context": 1024,
                "slots": 1,
                "gpu_layers": 99,
            },
            "hardware_profiles": [],
        }
        catalog = tmp_path / "catalog.json"
        entry["assistant_profiles"] = ["assistant-lite"]
        catalog.write_text(
            json.dumps(
                {
                    "catalog_version": 1,
                    "profiles": {
                        "assistant-lite": {
                            "display_name": "Marvin local assistant",
                            "preferred_model_id": "apertus-test",
                            "reuse_active_compatible": True,
                            "priority": "interactive",
                            "cloud_fallback": False,
                            "generation": {"max_tokens": 128},
                        }
                    },
                    "entries": [entry],
                }
            )
        )
        monkeypatch.setenv(
            "MODEL_MANAGER_FAKE_HARDWARE",
            json.dumps(
                {
                    "probed_at": "test",
                    "ram_bytes": 2**34,
                    "disk_total_bytes": 2**40,
                    "disk_free_bytes": 2**39,
                    "cuda_devices": [
                        {"index": 0, "name": "test GPU", "vram_bytes": 2**34, "compute_capability": "6.1"}
                    ],
                    "cuda_error": None,
                    "runtime_supported": True,
                }
            ),
        )
        library = tmp_path / "models"
        return ModelManager(catalog, library, tmp_path / "llama-server", "runtime@sha256:test"), cache

    return make


def test_allowlist_license_and_cached_atomic_download(manager_factory):
    manager, _ = manager_factory()
    model = manager.describe("apertus-test")
    assert model["state"] == "available"
    assert model["compatibility"]["status"] == "compatible"
    assert model["download"]["cached_copy_available"] is True
    with pytest.raises(ModelManagerError, match="license"):
        manager.start_download("apertus-test", use_cached_copy=True)

    manager.accept_license("apertus-test", True)
    manager.start_download("apertus-test", use_cached_copy=True)
    model = wait_for(manager, "apertus-test", lambda item: item["installed"])
    assert model["artifact"]["sha256"] == model["sha256"]
    assert not (manager.library_path / "apertus-test.gguf.part").exists()
    assert manager.start_download("apertus-test", use_cached_copy=True)["installed"] is True


def test_assistant_profile_prefers_small_model_and_never_claims_cloud_fallback(manager_factory):
    manager, _ = manager_factory()
    profile = manager.describe_profile("assistant-lite")

    assert profile["state"] == "needs_download"
    assert profile["selected_model"]["id"] == "apertus-test"
    assert profile["preferred_model"]["id"] == "apertus-test"
    assert profile["policy"] == {
        "priority": "interactive",
        "cloud_fallback": False,
        "single_runtime": True,
        "automatic_model_switch": False,
    }


def test_assistant_profile_reuses_the_active_compatible_runner(manager_factory, monkeypatch):
    manager, _ = manager_factory()
    manager.runner_model_id = "apertus-test"
    monkeypatch.setattr(manager, "inference_targets", lambda: [{"slot": "gpu-0"}])
    manager._model_state("apertus-test")["state"] = "ready"

    profile = manager.describe_profile("assistant-lite")

    assert profile["ready"] is True
    assert profile["state"] == "ready"
    assert profile["reused_active_runner"] is True


def test_checksum_failure_never_replaces_existing_artifact(manager_factory):
    expected = hashlib.sha256(b"expected" * 8).hexdigest()
    manager, _ = manager_factory(payload=b"wrong!!!" * 8, expected=expected)
    manager.accept_license("apertus-test", True)
    target = manager.library_path / "apertus-test.gguf"
    target.write_bytes(b"retained" * 8)
    manager.start_download("apertus-test", use_cached_copy=True)
    model = wait_for(manager, "apertus-test", lambda item: item["state"] == "error")
    assert "SHA-256" in model["error"]
    assert target.read_bytes() == b"retained" * 8


def test_referenced_or_active_artifact_cannot_be_removed(manager_factory):
    manager, _ = manager_factory()
    manager.accept_license("apertus-test", True)
    manager.start_download("apertus-test", use_cached_copy=True)
    wait_for(manager, "apertus-test", lambda item: item["installed"])
    with pytest.raises(ModelManagerError, match="referenced"):
        manager.remove_model("apertus-test", referenced=True)
    assert manager.describe("apertus-test")["installed"] is True


def test_restart_preserves_partial_download_for_resume(manager_factory):
    manager, _ = manager_factory()
    part = manager.library_path / "apertus-test.gguf.part"
    part.write_bytes(b"partial")
    restarted, _ = manager_factory()
    model = restarted.describe("apertus-test")
    assert model["state"] == "paused"
    assert model["download"]["resumable"] is True
    assert model["download"]["downloaded_bytes"] == len(b"partial")


def test_download_can_pause_and_resume_without_discarding_progress(manager_factory):
    payload = b"abcdefgh" * (1024 * 1024)
    manager, _ = manager_factory(payload=payload)

    class SlowStream(io.BytesIO):
        def read(self, size=-1):
            time.sleep(0.02)
            return super().read(size)

    def slow_source(_entry, offset, _use_cached_copy):
        stream = SlowStream(payload)
        stream.seek(offset)
        return stream, True

    manager._open_source = slow_source
    manager.accept_license("apertus-test", True)
    manager.start_download("apertus-test")
    time.sleep(0.05)
    manager.pause_download("apertus-test")
    paused = wait_for(manager, "apertus-test", lambda item: item["state"] == "paused")
    assert 0 < paused["download"]["downloaded_bytes"] < len(payload)

    manager.start_download("apertus-test")
    resumed = wait_for(manager, "apertus-test", lambda item: item["installed"])
    assert resumed["artifact"]["sha256"] == hashlib.sha256(payload).hexdigest()


def test_hardware_profiles_choose_gpu_cpu_replication_and_split(manager_factory, monkeypatch):
    manager, _ = manager_factory()
    entry = manager.entries["apertus-test"]
    assert manager.select_profile(entry)["name"] == "dev-1070"

    manager.hardware["cuda_devices"] = []
    assert manager.select_profile(entry)["name"] == "cpu-degraded"

    manager.hardware["cuda_devices"] = [
        {"index": 0, "name": "small GPU", "vram_bytes": 1024**3}
    ]
    assert manager.select_profile(entry)["name"] == "cpu-degraded"

    manager.hardware["cuda_devices"] = [
        {"index": 0, "name": "GTX 1080", "vram_bytes": 8 * 1024**3},
        {"index": 1, "name": "GTX 1080", "vram_bytes": 8 * 1024**3},
    ]
    assert manager.select_profile(entry)["name"] == "dual-1080-replicated"
    assert manager.select_profile(entry)["slots"] == 2

    entry["size_bytes"] = 7 * 1024**3
    profile = manager.select_profile(entry)
    assert profile["name"] == "dual-1080-split"
    assert profile["slots"] == 1
    assert profile["memory_plan"]["runtime_headroom_bytes"] == 2 * 1024**3

    manager.hardware["cuda_devices"] = [
        {"index": 0, "name": "small GPU", "vram_bytes": 4 * 1024**3},
        {"index": 1, "name": "small GPU", "vram_bytes": 4 * 1024**3},
    ]
    assert manager.select_profile(entry)["name"] == "cpu-degraded"


def test_explicit_gpu_profiles_cannot_bypass_memory_headroom(manager_factory):
    manager, _ = manager_factory()
    entry = manager.entries["apertus-test"]
    entry["size_bytes"] = 7 * 1024**3
    manager.hardware["cuda_devices"] = [
        {"index": 0, "name": "GTX 1080", "vram_bytes": 8 * 1024**3},
        {"index": 1, "name": "GTX 1080", "vram_bytes": 8 * 1024**3},
    ]

    with pytest.raises(ModelManagerError, match="independent model replica"):
        manager.select_profile(entry, "dual-1080-replicated")
    assert manager.select_profile(entry, "dual-1080-split")["name"] == "dual-1080-split"

    manager.hardware["cuda_devices"] = [
        {"index": 0, "name": "small GPU", "vram_bytes": 4 * 1024**3},
        {"index": 1, "name": "small GPU", "vram_bytes": 4 * 1024**3},
    ]
    with pytest.raises(ModelManagerError, match="does not fit across"):
        manager.select_profile(entry, "dual-1080-split")

    manager.hardware["cuda_devices"] = [
        {"index": 0, "name": "small GPU", "vram_bytes": 4 * 1024**3}
    ]
    with pytest.raises(ModelManagerError, match="does not fit on the visible GPU"):
        manager.select_profile(entry, "dev-1070")


def test_explicit_profile_rejects_unavailable_hardware(manager_factory):
    manager, _ = manager_factory()
    entry = manager.entries["apertus-test"]
    with pytest.raises(ModelManagerError, match="two visible CUDA"):
        manager.select_profile(entry, "dual-1080-replicated")
    with pytest.raises(ModelManagerError, match="Unknown hardware"):
        manager.select_profile(entry, "unsafe-profile")


def test_replicated_deployment_is_ready_only_when_every_runner_is_ready(manager_factory):
    manager, _ = manager_factory()

    class Process:
        def __init__(self, return_code=None):
            self.return_code = return_code

        def poll(self):
            return self.return_code

    first = {"slot": "gpu-0", "port": 8081, "device": 0, "state": "ready", "process": Process()}
    second = {
        "slot": "gpu-1",
        "port": 8082,
        "device": 1,
        "state": "starting",
        "process": Process(),
    }
    manager.runner_model_id = "apertus-test"
    manager.runners = [first, second]
    manager.state["deployment"] = {"model_id": "apertus-test", "state": "starting"}

    assert manager._sync_deployment_state("apertus-test") == "starting"
    assert manager.state["deployment"]["available_slots"] == 1
    assert "ready_at" not in manager.state["deployment"]

    second.update(state="ready", error=None)
    assert manager._sync_deployment_state("apertus-test") == "ready"
    assert manager.state["deployment"]["available_slots"] == 2
    assert manager.state["deployment"]["ready_at"]


def test_late_ready_runner_cannot_hide_a_failed_replica(manager_factory):
    manager, _ = manager_factory()

    class Process:
        def __init__(self, return_code=None):
            self.return_code = return_code

        def poll(self):
            return self.return_code

    failed = {
        "slot": "gpu-0",
        "port": 8081,
        "device": 0,
        "state": "error",
        "error": "runner exited",
        "process": Process(1),
    }
    late_ready = {
        "slot": "gpu-1",
        "port": 8082,
        "device": 1,
        "state": "ready",
        "error": None,
        "process": Process(),
    }
    manager.runner_model_id = "apertus-test"
    manager.runners = [failed, late_ready]
    manager.state["deployment"] = {"model_id": "apertus-test", "state": "starting"}

    assert manager._sync_deployment_state("apertus-test") == "degraded"
    assert manager.state["deployment"]["available_slots"] == 1
    assert manager.state["deployment"]["error"] == "runner exited"
    assert manager.state["models"]["apertus-test"]["state"] == "degraded"
