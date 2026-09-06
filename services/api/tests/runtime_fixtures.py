"""Synthetic launch snapshots, never real runtime approvals."""


def local_runtime(model="test-apertus", *, generation="a", revision="1"):
    identity = {
        "model_id": "synthetic-model", "model_revision": revision * 40,
        "artifact_sha256": revision * 64, "tokenizer_sha256": revision * 64,
        "chat_template_sha256": "2" * 64, "runtime_sha256": "3" * 64,
        "hardware_profile": "synthetic-host",
    }
    return {
        "schema_version": "local-runtime-binding-v1", "available": True,
        "deployment_id": generation * 32, "binding_fingerprint": generation * 64,
        "model_id": identity["model_id"], "served_model_id": model,
        "model_revision": identity["model_revision"], "artifact_sha256": identity["artifact_sha256"],
        "identity": identity, "context_window_tokens": 4096, "default_output_tokens": 700,
        "quantization": "synthetic-q4", "runtime_image": "synthetic/runner@sha256:" + "4" * 64,
        "hardware_profile": "synthetic-host",
        "hardware": {"cuda_devices": [{"index": 0, "name": "Synthetic GPU", "vram_bytes": 8 * 1024**3}], "ram_bytes": 32 * 1024**3},
    }
