from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

GPU_RUNTIME_HEADROOM_BYTES = 2 * 1024**3


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class ModelManagerError(Exception):
    def __init__(self, message: str, status: int = 422, code: str = "model_manager_error"):
        super().__init__(message)
        self.message, self.status, self.code = message, status, code


class ModelManager:
    def __init__(
        self,
        catalog_path: Path,
        library_path: Path,
        llama_server: Path,
        runtime_image: str,
    ):
        self.catalog_path = catalog_path
        self.library_path = library_path
        self.llama_server = llama_server
        self.runtime_image = runtime_image
        self.library_path.mkdir(parents=True, exist_ok=True)
        self.catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        if self.catalog.get("catalog_version") != 1 or not self.catalog.get("entries"):
            raise RuntimeError("Unsupported or empty local model catalogue.")
        self.entries = {entry["id"]: entry for entry in self.catalog["entries"]}
        self.profiles = self.catalog.get("profiles", {})
        self.state_path = self.library_path / "manager-state.json"
        self.lock = threading.RLock()
        self.controls: dict[str, dict[str, threading.Event]] = {}
        self.threads: dict[str, threading.Thread] = {}
        self.runner: subprocess.Popen[str] | None = None
        self.runners: list[dict] = []
        self.runner_model_id: str | None = None
        self.logs: list[str] = []
        self.state = self._load_state()
        self._reconcile_after_restart()
        self.hardware = self.probe_hardware()
        for model_id, entry in self.entries.items():
            if self._model_state(model_id)["state"] == "verifying":
                worker = threading.Thread(
                    target=self._verify_existing,
                    args=(entry,),
                    daemon=True,
                    name=f"model-verify-{model_id}",
                )
                self.threads[model_id] = worker
                worker.start()

    def _load_state(self) -> dict:
        if self.state_path.exists():
            try:
                value = json.loads(self.state_path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    return value
            except (OSError, json.JSONDecodeError):
                pass
        return {"accepted": {}, "models": {}, "deployment": None, "updated_at": now_iso()}

    def _save_state(self):
        self.state["updated_at"] = now_iso()
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.state_path)

    def _model_state(self, model_id: str) -> dict:
        return self.state.setdefault("models", {}).setdefault(
            model_id,
            {
                "state": "available",
                "downloaded_bytes": 0,
                "error": None,
                "verified_at": None,
                "artifact_sha256": None,
            },
        )

    def _entry(self, model_id: str) -> dict:
        try:
            return self.entries[model_id]
        except KeyError as exc:
            raise ModelManagerError("This model is not in the versioned allowlist.", 404, "model_not_allowed") from exc

    def _artifact_path(self, entry: dict) -> Path:
        return self.library_path / entry["gguf_file"]

    def _part_path(self, entry: dict) -> Path:
        return self.library_path / (entry["gguf_file"] + ".part")

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _verify_existing(self, entry: dict):
        model_id = entry["id"]
        try:
            actual = self._hash_file(self._artifact_path(entry))
            if actual != entry["sha256"]:
                raise ModelManagerError("The installed model failed SHA-256 verification.", 422, "checksum_mismatch")
            with self.lock:
                self._model_state(model_id).update(
                    state="stopped",
                    downloaded_bytes=entry["size_bytes"],
                    artifact_sha256=actual,
                    verified_at=now_iso(),
                    error=None,
                )
                self._save_state()
        except Exception as exc:  # noqa: BLE001 - background verifier persists failures for the UI
            message = exc.message if isinstance(exc, ModelManagerError) else str(exc)
            with self.lock:
                self._model_state(model_id).update(state="error", error=message[:1000])
                self._save_state()

    def _reconcile_after_restart(self):
        with self.lock:
            self.state["deployment"] = None
            for model_id, entry in self.entries.items():
                record = self._model_state(model_id)
                artifact = self._artifact_path(entry)
                part = self._part_path(entry)
                if artifact.exists() and artifact.stat().st_size == entry["size_bytes"]:
                    record["state"] = "stopped" if record.get("verified_at") else "verifying"
                    record["downloaded_bytes"] = entry["size_bytes"]
                elif part.exists():
                    record["state"] = "paused"
                    record["downloaded_bytes"] = part.stat().st_size
                else:
                    record.update(state="available", downloaded_bytes=0, verified_at=None, artifact_sha256=None)
            self._save_state()

    def probe_hardware(self) -> dict:
        fake = os.getenv("MODEL_MANAGER_FAKE_HARDWARE")
        if fake:
            return json.loads(fake)
        ram_bytes = 0
        try:
            values = Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()
            ram_bytes = int(next(line for line in values if line.startswith("MemTotal:")).split()[1]) * 1024
        except (OSError, StopIteration, ValueError):
            pass
        disk = shutil.disk_usage(self.library_path)
        devices: list[dict] = []
        cuda_error = None
        command = [
            "nvidia-smi",
            "--query-gpu=index,name,memory.total,compute_cap",
            "--format=csv,noheader,nounits",
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=8, check=True)
            for row in result.stdout.splitlines():
                index, name, memory_mb, compute = [value.strip() for value in row.split(",", 3)]
                devices.append(
                    {
                        "index": int(index),
                        "name": name,
                        "vram_bytes": int(memory_mb) * 1024 * 1024,
                        "compute_capability": compute,
                    }
                )
        except (FileNotFoundError, subprocess.SubprocessError, ValueError) as exc:
            cuda_error = str(exc)[:300]
        return {
            "probed_at": now_iso(),
            "ram_bytes": ram_bytes,
            "disk_total_bytes": disk.total,
            "disk_free_bytes": disk.free,
            "cuda_devices": devices,
            "cuda_error": cuda_error,
            "runtime_supported": self.llama_server.exists() and os.access(self.llama_server, os.X_OK),
        }

    def refresh_hardware(self) -> dict:
        with self.lock:
            self.hardware = self.probe_hardware()
            return self.hardware

    def compatibility(self, entry: dict) -> dict:
        requirements = entry["requirements"]
        problems = []
        if not self.hardware["runtime_supported"]:
            problems.append("The pinned llama.cpp runtime is unavailable.")
        if self.hardware["ram_bytes"] and self.hardware["ram_bytes"] < requirements["min_ram_bytes"]:
            problems.append("System RAM is below this profile's minimum.")
        if self.hardware["disk_free_bytes"] < requirements["min_disk_bytes"]:
            problems.append("Available model-library disk space is below the safe minimum.")
        if problems:
            return {"status": "incompatible", "reason": " ".join(problems)}
        devices = self.hardware["cuda_devices"]
        if not devices:
            return {
                "status": "unverified",
                "reason": "No CUDA device is visible. CPU execution may work but is not the intended profile.",
            }
        if max(device["vram_bytes"] for device in devices) < requirements["min_vram_bytes"]:
            return {
                "status": "unverified",
                "reason": "The model needs a measured multi-GPU split or CPU offload on this host.",
            }
        return {"status": "compatible", "reason": "The host meets the declared minimums; run a benchmark before public use."}

    def accept_license(self, model_id: str, accepted: bool) -> dict:
        entry = self._entry(model_id)
        with self.lock:
            if accepted:
                self.state["accepted"][model_id] = {
                    "revision": entry["immutable_revision"],
                    "accepted_at": now_iso(),
                }
            else:
                self.state["accepted"].pop(model_id, None)
            self._save_state()
        return self.describe(model_id)

    def _license_accepted(self, entry: dict) -> bool:
        if entry.get("license_acceptance") != "required":
            return True
        accepted = self.state["accepted"].get(entry["id"], {})
        return accepted.get("revision") == entry["immutable_revision"]

    def describe(self, model_id: str) -> dict:
        entry = self._entry(model_id)
        with self.lock:
            record = dict(self._model_state(model_id))
            artifact = self._artifact_path(entry)
            part = self._part_path(entry)
            legacy = Path(entry.get("legacy_cache_blob", ""))
            installed = (
                artifact.exists()
                and artifact.stat().st_size == entry["size_bytes"]
                and record.get("artifact_sha256") == entry["sha256"]
            )
            return {
                **{key: value for key, value in entry.items() if key not in {"download_url", "legacy_cache_blob"}},
                "catalog_version": self.catalog["catalog_version"],
                "state": record["state"],
                "download": {
                    "downloaded_bytes": part.stat().st_size if part.exists() else record.get("downloaded_bytes", 0),
                    "total_bytes": entry["size_bytes"],
                    "resumable": part.exists(),
                    "cached_copy_available": bool(entry.get("legacy_cache_blob")) and legacy.is_file(),
                },
                "installed": installed,
                "artifact": {
                    "sha256": record.get("artifact_sha256"),
                    "verified_at": record.get("verified_at"),
                }
                if installed
                else None,
                "license_accepted": self._license_accepted(entry),
                "compatibility": self.compatibility(entry),
                "error": record.get("error"),
                "active": self.runner_model_id == model_id and bool(self.inference_targets()),
            }

    def inventory(self) -> dict:
        return {
            "catalog_version": self.catalog["catalog_version"],
            "runtime_image": self.runtime_image,
            "hardware": self.hardware,
            "deployment": self.state.get("deployment"),
            "runtime_metrics": self.runtime_metrics(),
            "models": [self.describe(model_id) for model_id in self.entries],
            "profiles": [self.describe_profile(profile_id) for profile_id in self.profiles],
        }

    def describe_profile(self, profile_id: str) -> dict:
        """Resolve a workload profile without starting or swapping a model."""
        try:
            profile = self.profiles[profile_id]
        except KeyError as exc:
            raise ModelManagerError(
                "This workload profile is not in the versioned allowlist.",
                404,
                "profile_not_allowed",
            ) from exc
        preferred_id = profile["preferred_model_id"]
        preferred = self._entry(preferred_id)
        selected_id = preferred_id
        reused_active_runner = False
        active_id = self.runner_model_id
        if (
            profile.get("reuse_active_compatible", False)
            and active_id in self.entries
            and profile_id in self.entries[active_id].get("assistant_profiles", [])
        ):
            selected_id = active_id
            reused_active_runner = True
        selected = self.describe(selected_id)
        selected_state = selected["state"]
        if selected["active"] and selected_state in {"ready", "degraded"}:
            state = selected_state
        elif selected["active"]:
            state = "starting"
        elif selected["installed"]:
            state = "stopped"
        else:
            state = "needs_download"
        return {
            "id": profile_id,
            "display_name": profile["display_name"],
            "state": state,
            "ready": state in {"ready", "degraded"},
            "reused_active_runner": reused_active_runner,
            "selected_model": {
                "id": selected["id"],
                "display_name": selected["display_name"],
                "served_model_id": selected["served_model_id"],
                "state": selected_state,
                "installed": selected["installed"],
                "active": selected["active"],
                "immutable_revision": selected["immutable_revision"],
                "artifact_sha256": selected["sha256"],
                "quantization": selected["quantization"],
                "base_repository": selected.get("base_repository"),
            },
            "preferred_model": {
                "id": preferred_id,
                "display_name": preferred["display_name"],
            },
            "policy": {
                "priority": profile.get("priority", "interactive"),
                "cloud_fallback": bool(profile.get("cloud_fallback", False)),
                "single_runtime": True,
                "automatic_model_switch": False,
            },
            "generation": profile.get("generation", {}),
        }

    def runtime_metrics(self) -> dict:
        runners = []
        with self.lock:
            current = list(self.runners)
        for runner in current:
            rss_bytes = None
            try:
                status = Path(f"/proc/{runner['process'].pid}/status").read_text(encoding="utf-8")
                rss_line = next(line for line in status.splitlines() if line.startswith("VmRSS:"))
                rss_bytes = int(rss_line.split()[1]) * 1024
            except (OSError, StopIteration, ValueError):
                pass
            runners.append(
                {
                    "slot": runner["slot"],
                    "pid": runner["process"].pid,
                    "state": runner["state"],
                    "rss_bytes": rss_bytes,
                }
            )
        return {"runner_rss_bytes": sum(item["rss_bytes"] or 0 for item in runners), "runners": runners}

    def select_profile(self, entry: dict, requested: str | None = None) -> dict:
        """Choose a safe runtime layout from measured visible hardware."""
        devices = self.hardware.get("cuda_devices", [])
        allowed = {"dev-1070", "dual-1080-replicated", "dual-1080-split", "cpu-degraded"}
        single_card_need = max(
            int(entry["size_bytes"]) + GPU_RUNTIME_HEADROOM_BYTES,
            int(entry["requirements"]["min_vram_bytes"]),
        )
        split_total_need = single_card_need
        if requested and requested not in allowed:
            raise ModelManagerError("Unknown hardware profile.", 422, "invalid_hardware_profile")
        if requested:
            name = requested
        elif not devices:
            name = "cpu-degraded"
        elif len(devices) == 1:
            name = (
                "dev-1070"
                if int(devices[0]["vram_bytes"]) >= single_card_need
                else "cpu-degraded"
            )
        else:
            # Reserve 2 GiB for KV/cache/runtime. Replicate only when each card
            # can own an independent copy with headroom.
            first_two = devices[:2]
            if min(int(device["vram_bytes"]) for device in first_two) >= single_card_need:
                name = "dual-1080-replicated"
            elif sum(int(device["vram_bytes"]) for device in first_two) >= split_total_need:
                name = "dual-1080-split"
            else:
                name = "cpu-degraded"
        if name.startswith("dual-1080") and len(devices) < 2:
            raise ModelManagerError("This profile requires two visible CUDA devices.", 409, "profile_unavailable")
        if name == "dual-1080-replicated" and min(
            int(device["vram_bytes"]) for device in devices[:2]
        ) < single_card_need:
            raise ModelManagerError(
                "An independent model replica plus runtime headroom does not fit on each GPU. Use the split profile.",
                409,
                "profile_unavailable",
            )
        if name == "dual-1080-split" and sum(
            int(device["vram_bytes"]) for device in devices[:2]
        ) < split_total_need:
            raise ModelManagerError(
                "The model plus runtime headroom does not fit across the two visible GPUs.",
                409,
                "profile_unavailable",
            )
        if name == "dev-1070":
            if not devices:
                raise ModelManagerError(
                    "The GPU development profile requires one visible CUDA device.",
                    409,
                    "profile_unavailable",
                )
            if int(devices[0]["vram_bytes"]) < single_card_need:
                raise ModelManagerError(
                    "The model plus runtime headroom does not fit on the visible GPU.",
                    409,
                    "profile_unavailable",
                )
        slots = 2 if name == "dual-1080-replicated" else 1
        return {
            "name": name,
            "slots": slots,
            "gpu_enabled": name != "cpu-degraded",
            "degraded": name == "cpu-degraded",
            "memory_plan": {
                "model_bytes": int(entry["size_bytes"]),
                "runtime_headroom_bytes": GPU_RUNTIME_HEADROOM_BYTES,
                "required_single_card_bytes": single_card_need,
                "required_split_total_bytes": split_total_need,
                "visible_vram_bytes": [int(device["vram_bytes"]) for device in devices],
            },
        }

    def inference_targets(self) -> list[dict]:
        with self.lock:
            return [
                {
                    "slot": runner["slot"],
                    "url": f"http://127.0.0.1:{runner['port']}",
                    "device": runner.get("device"),
                }
                for runner in self.runners
                if runner.get("state") == "ready" and runner["process"].poll() is None
            ]

    def _ensure_download_allowed(self, entry: dict):
        if not self._license_accepted(entry):
            raise ModelManagerError(
                "Accept the model license and usage policy before downloading.",
                409,
                "license_not_accepted",
            )
        compatibility = self.compatibility(entry)
        if compatibility["status"] == "incompatible":
            raise ModelManagerError(compatibility["reason"], 409, "model_incompatible")

    def start_download(self, model_id: str, use_cached_copy: bool = False) -> dict:
        entry = self._entry(model_id)
        self._ensure_download_allowed(entry)
        description = self.describe(model_id)
        if description["installed"]:
            return description
        with self.lock:
            current = self.threads.get(model_id)
            if current and current.is_alive():
                return self.describe(model_id)
            controls = {"pause": threading.Event(), "cancel": threading.Event()}
            self.controls[model_id] = controls
            worker = threading.Thread(
                target=self._download,
                args=(entry, controls, use_cached_copy),
                daemon=True,
                name=f"model-download-{model_id}",
            )
            self.threads[model_id] = worker
            record = self._model_state(model_id)
            record.update(state="downloading", error=None)
            self._save_state()
            worker.start()
        return self.describe(model_id)

    def pause_download(self, model_id: str) -> dict:
        self._entry(model_id)
        with self.lock:
            controls = self.controls.get(model_id)
            if controls:
                controls["pause"].set()
        return self.describe(model_id)

    def cancel_download(self, model_id: str) -> dict:
        self._entry(model_id)
        with self.lock:
            controls = self.controls.get(model_id)
            if controls:
                controls["cancel"].set()
        return self.describe(model_id)

    def _open_source(self, entry: dict, offset: int, use_cached_copy: bool):
        if use_cached_copy:
            source = Path(entry.get("legacy_cache_blob", ""))
            if not source.is_file():
                raise ModelManagerError("The verified legacy cache does not contain this model.", 404, "cache_missing")
            handle = source.open("rb")
            handle.seek(offset)
            return handle, True
        request = urllib.request.Request(entry["download_url"])
        if offset:
            request.add_header("Range", f"bytes={offset}-")
        response = urllib.request.urlopen(request, timeout=60)
        resumed = offset == 0 or getattr(response, "status", 200) == 206
        return response, resumed

    def _download(self, entry: dict, controls: dict[str, threading.Event], use_cached_copy: bool):
        model_id = entry["id"]
        part = self._part_path(entry)
        artifact = self._artifact_path(entry)
        try:
            offset = part.stat().st_size if part.exists() else 0
            if offset > entry["size_bytes"]:
                part.unlink()
                offset = 0
            remaining = entry["size_bytes"] - offset
            free = shutil.disk_usage(self.library_path).free
            if free < remaining + 268435456:
                raise ModelManagerError("Not enough free disk space to download and verify this model.", 409, "disk_full")
            source, resumed = self._open_source(entry, offset, use_cached_copy)
            if offset and not resumed:
                source.close()
                part.unlink(missing_ok=True)
                offset = 0
                source, _ = self._open_source(entry, 0, use_cached_copy)
            mode = "ab" if offset else "wb"
            last_saved = offset
            with source, part.open(mode) as destination:
                while True:
                    if controls["pause"].is_set() or controls["cancel"].is_set():
                        with self.lock:
                            record = self._model_state(model_id)
                            record.update(state="paused", downloaded_bytes=destination.tell())
                            self._save_state()
                        return
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    destination.write(chunk)
                    if destination.tell() - last_saved >= 16 * 1024 * 1024:
                        with self.lock:
                            self._model_state(model_id)["downloaded_bytes"] = destination.tell()
                            self._save_state()
                        last_saved = destination.tell()
            if part.stat().st_size != entry["size_bytes"]:
                raise ModelManagerError("The download ended before the expected model size was received.", 502, "download_incomplete")
            with self.lock:
                self._model_state(model_id).update(state="verifying", downloaded_bytes=entry["size_bytes"])
                self._save_state()
            actual = self._hash_file(part)
            if actual != entry["sha256"]:
                invalid = part.with_suffix(part.suffix + f".invalid-{int(time.time())}")
                os.replace(part, invalid)
                raise ModelManagerError("The downloaded model failed SHA-256 verification.", 422, "checksum_mismatch")
            if artifact.exists():
                existing_digest = self._hash_file(artifact)
                if existing_digest != entry["sha256"]:
                    os.replace(artifact, artifact.with_suffix(artifact.suffix + f".invalid-{int(time.time())}"))
            os.replace(part, artifact)
            with self.lock:
                self._model_state(model_id).update(
                    state="available",
                    downloaded_bytes=entry["size_bytes"],
                    artifact_sha256=actual,
                    verified_at=now_iso(),
                    error=None,
                )
                self._save_state()
        except Exception as exc:  # noqa: BLE001 - background downloader persists failures for the UI
            message = exc.message if isinstance(exc, ModelManagerError) else str(exc)
            with self.lock:
                self._model_state(model_id).update(state="error", error=message[:1000])
                self._save_state()

    def _drain_logs(self, runner: dict):
        process = runner["process"]
        if process.stdout is None:
            return
        for line in process.stdout:
            with self.lock:
                self.logs.append(f"[{runner['slot']}] {line.rstrip()[:1950]}")
                self.logs = self.logs[-200:]
        return_code = process.poll()
        with self.lock:
            model_id = self.runner_model_id
            runner["state"] = "error"
            runner["error"] = f"llama.cpp exited unexpectedly with code {return_code}."
            if model_id and return_code is not None:
                self._sync_deployment_state(model_id)

    def _sync_deployment_state(self, model_id: str) -> str:
        """Persist one aggregate state for every planned runner. Caller holds self.lock."""

        ready = self.inference_targets()
        planned = len(self.runners)
        starting = any(
            runner.get("state") == "starting" and runner["process"].poll() is None
            for runner in self.runners
        )
        failed = [runner for runner in self.runners if runner.get("state") == "error"]
        if planned and len(ready) == planned:
            state = "ready"
        elif ready and failed:
            state = "degraded"
        elif starting:
            state = "starting"
        else:
            state = "error"
        error = failed[-1].get("error") if failed else None
        self._model_state(model_id).update(state=state, error=error)
        deployment = self.state.get("deployment") or {}
        if deployment.get("model_id") == model_id:
            update = {
                "state": state,
                "error": error,
                "available_slots": len(ready),
                "runners": [
                    {k: item.get(k) for k in ("slot", "port", "device", "state", "error")}
                    for item in self.runners
                ],
            }
            if state in {"ready", "degraded"} and not deployment.get("ready_at"):
                update["ready_at"] = now_iso()
            deployment.update(update)
        self._save_state()
        return state

    def _runner_specs(self, profile: dict) -> list[dict]:
        if profile["name"] == "dual-1080-replicated":
            return [
                {"slot": "gpu-0", "port": 8081, "device": 0, "visible": "0"},
                {"slot": "gpu-1", "port": 8082, "device": 1, "visible": "1"},
            ]
        if profile["name"] == "dual-1080-split":
            return [{"slot": "gpu-split", "port": 8081, "device": [0, 1], "visible": "0,1"}]
        if profile["name"] == "cpu-degraded":
            return [{"slot": "cpu-0", "port": 8081, "device": None, "visible": ""}]
        return [{"slot": "gpu-0", "port": 8081, "device": 0, "visible": "0"}]

    def start_model(self, model_id: str, profile_name: str | None = None) -> dict:
        entry = self._entry(model_id)
        description = self.describe(model_id)
        if not description["installed"]:
            raise ModelManagerError("Download and verify this model before starting it.", 409, "model_not_installed")
        if description["compatibility"]["status"] == "incompatible":
            raise ModelManagerError(description["compatibility"]["reason"], 409, "model_incompatible")
        with self.lock:
            if self.inference_targets() or any(r["process"].poll() is None for r in self.runners):
                if self.runner_model_id == model_id:
                    return self.describe(model_id)
                raise ModelManagerError("Stop the active model before starting another one.", 409, "model_active")
            requirements = entry["requirements"]
            profile = self.select_profile(entry, profile_name)
            self._model_state(model_id).update(state="starting", error=None)
            self.state["deployment"] = {
                "model_id": model_id,
                "served_model_id": entry["served_model_id"],
                "model_revision": entry["immutable_revision"],
                "artifact_sha256": entry["sha256"],
                "quantization": entry["quantization"],
                "state": "starting",
                "runtime_image": self.runtime_image,
                "hardware_profile": profile["name"],
                "memory_plan": profile["memory_plan"],
                "accepted_slots": profile["slots"],
                "available_slots": 0,
                "context_size": requirements["recommended_context"],
                "generation": {"max_tokens": 700, "parallel_per_runner": 1},
                "started_at": now_iso(),
            }
            self._save_state()
            self.runner_model_id = model_id
            self.runners = []
            for spec in self._runner_specs(profile):
                gpu_layers = 0 if profile["name"] == "cpu-degraded" else requirements["gpu_layers"]
                command = [
                    str(self.llama_server), "-m", str(self._artifact_path(entry)),
                    "--alias", entry["served_model_id"],
                    "--chat-template-file", entry["chat_template"],
                    "--host", "127.0.0.1", "--port", str(spec["port"]),
                    "--ctx-size", str(requirements["recommended_context"]),
                    "--parallel", "1", "--n-predict", "700",
                    "--n-gpu-layers", str(gpu_layers),
                ]
                if profile["name"] == "dual-1080-split":
                    command.extend(["--split-mode", "layer", "--tensor-split", "1,1"])
                environment = os.environ.copy()
                if spec["visible"]:
                    environment["CUDA_VISIBLE_DEVICES"] = spec["visible"]
                elif profile["name"] == "cpu-degraded":
                    environment["CUDA_VISIBLE_DEVICES"] = ""
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=environment,
                )
                runner = {**spec, "process": process, "state": "starting", "error": None}
                self.runners.append(runner)
                threading.Thread(target=self._drain_logs, args=(runner,), daemon=True).start()
                threading.Thread(
                    target=self._wait_until_ready,
                    args=(model_id, runner, entry["served_model_id"]),
                    daemon=True,
                ).start()
            self.runner = self.runners[0]["process"]
        return self.describe(model_id)

    def _warm_up(self, port: int, model_id: str) -> None:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        body = json.dumps(
            {
                "model": model_id,
                "messages": [{"role": "user", "content": "Return only {\"ready\":true}."}],
                "temperature": 0,
                "max_tokens": 12,
                "response_format": {
                    "type": "json_object",
                    "schema": {
                        "type": "object",
                        "properties": {"ready": {"type": "boolean", "const": True}},
                        "required": ["ready"],
                        "additionalProperties": False,
                    },
                },
            }
        ).encode()
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with opener.open(request, timeout=90) as response:
            if response.status != 200:
                raise OSError(f"warm-up returned HTTP {response.status}")

    def _wait_until_ready(self, model_id: str, runner: dict, served_model_id: str):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline = time.monotonic() + 300
        error = "The local inference runtime did not become ready in time."
        while time.monotonic() < deadline:
            with self.lock:
                process = runner["process"]
                if self.runner_model_id != model_id:
                    return
                if process.poll() is not None:
                    error = f"llama.cpp exited with code {process.returncode}."
                    break
            try:
                with opener.open(f"http://127.0.0.1:{runner['port']}/health", timeout=2) as response:
                    if response.status == 200:
                        self._warm_up(runner["port"], served_model_id)
                        with self.lock:
                            runner["state"] = "ready"
                            runner["error"] = None
                            self._sync_deployment_state(model_id)
                        return
            except (OSError, urllib.error.URLError, TimeoutError) as exc:
                error = f"Local runtime warm-up failed: {exc}"
                time.sleep(1)
        with self.lock:
            runner.update(state="error", error=error)
            self._sync_deployment_state(model_id)

    def stop_model(self, model_id: str) -> dict:
        self._entry(model_id)
        with self.lock:
            if self.runner_model_id != model_id or not self.runners:
                return self.describe(model_id)
            for runner in self.runners:
                process = runner["process"]
                if process.poll() is None:
                    process.terminate()
            for runner in self.runners:
                process = runner["process"]
                if process.poll() is None:
                    try:
                        process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        process.kill()
            self.runner = None
            self.runners = []
            self.runner_model_id = None
            self._model_state(model_id).update(state="stopped", error=None)
            if self.state.get("deployment", {}).get("model_id") == model_id:
                self.state["deployment"].update(state="stopped", stopped_at=now_iso())
            self._save_state()
        return self.describe(model_id)

    def remove_model(self, model_id: str, referenced: bool = False) -> dict:
        entry = self._entry(model_id)
        with self.lock:
            if self.runner_model_id == model_id and any(
                runner["process"].poll() is None for runner in self.runners
            ):
                raise ModelManagerError("Stop the active model before removing its artifact.", 409, "model_active")
            if referenced:
                raise ModelManagerError(
                    "This model artifact is referenced by retained analysis provenance.",
                    409,
                    "model_referenced",
                )
            self._artifact_path(entry).unlink(missing_ok=True)
            self._part_path(entry).unlink(missing_ok=True)
            self._model_state(model_id).update(
                state="available",
                downloaded_bytes=0,
                artifact_sha256=None,
                verified_at=None,
                error=None,
            )
            self._save_state()
        return self.describe(model_id)

    def log_tail(self) -> list[str]:
        with self.lock:
            return list(self.logs[-100:])
