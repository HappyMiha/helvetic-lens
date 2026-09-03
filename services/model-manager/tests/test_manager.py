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
        catalog.write_text(json.dumps({"catalog_version": 1, "entries": [entry]}))
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
        {"index": 0, "name": "GTX 1080", "vram_bytes": 8 * 1024**3},
        {"index": 1, "name": "GTX 1080", "vram_bytes": 8 * 1024**3},
    ]
    assert manager.select_profile(entry)["name"] == "dual-1080-replicated"
    assert manager.select_profile(entry)["slots"] == 2

    entry["size_bytes"] = 7 * 1024**3
    profile = manager.select_profile(entry)
    assert profile["name"] == "dual-1080-split"
    assert profile["slots"] == 1


def test_explicit_profile_rejects_unavailable_hardware(manager_factory):
    manager, _ = manager_factory()
    entry = manager.entries["apertus-test"]
    with pytest.raises(ModelManagerError, match="two visible CUDA"):
        manager.select_profile(entry, "dual-1080-replicated")
    with pytest.raises(ModelManagerError, match="Unknown hardware"):
        manager.select_profile(entry, "unsafe-profile")
