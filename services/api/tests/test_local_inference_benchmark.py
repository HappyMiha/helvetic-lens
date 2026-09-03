import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "benchmark_local_inference.py"
SPEC = importlib.util.spec_from_file_location("benchmark_local_inference", SCRIPT_PATH)
assert SPEC and SPEC.loader
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


def sample(slot: str = "gpu-0", *, ok: bool = True) -> dict:
    return {"ok": ok, "slot": slot}


def representative_calls() -> list[dict]:
    return [sample() for _ in range(20)]


def dual_1080_hardware() -> dict:
    return {
        "cuda_devices": [
            {"name": "NVIDIA GeForce GTX 1080", "index": 0},
            {"name": "NVIDIA GeForce GTX 1080", "index": 1},
        ]
    }


def test_replicated_gate_requires_two_successful_distinct_runner_slots():
    result = benchmark.evaluate_gate(
        {"hardware_profile": "dual-1080-replicated", "accepted_slots": 2},
        dual_1080_hardware(),
        representative_calls(),
        [sample("gpu-0"), sample("gpu-1")],
        required_profile="dual-1080-replicated",
        required_gpu_substring="GTX 1080",
    )

    assert result["passed"] is True
    assert result["requirements"]["cuda_devices"] == 2
    assert result["observed"]["distinct_runner_slots"] == ["gpu-0", "gpu-1"]

    same_slot = benchmark.evaluate_gate(
        {"hardware_profile": "dual-1080-replicated", "accepted_slots": 2},
        dual_1080_hardware(),
        representative_calls(),
        [sample("gpu-0"), sample("gpu-0")],
        required_profile="dual-1080-replicated",
        required_gpu_substring="GTX 1080",
    )
    assert same_slot["passed"] is False
    assert same_slot["checks"]["distinct_runner_slots"] is False


def test_replicated_gate_fails_closed_for_wrong_profile_gpu_or_call_result():
    wrong_profile = benchmark.evaluate_gate(
        {"hardware_profile": "dev-1070", "accepted_slots": 2},
        dual_1080_hardware(),
        representative_calls(),
        [sample("gpu-0"), sample("gpu-1")],
        required_profile="dual-1080-replicated",
        required_gpu_substring="GTX 1080",
    )
    wrong_gpu = benchmark.evaluate_gate(
        {"hardware_profile": "dual-1080-replicated", "accepted_slots": 2},
        {"cuda_devices": [{"name": "GTX 1080"}, {"name": "GTX 1070"}]},
        representative_calls(),
        [sample("gpu-0"), sample("gpu-1")],
        required_profile="dual-1080-replicated",
        required_gpu_substring="GTX 1080",
    )
    failed_call = benchmark.evaluate_gate(
        {"hardware_profile": "dual-1080-replicated", "accepted_slots": 2},
        dual_1080_hardware(),
        representative_calls()[:-1] + [sample(ok=False)],
        [sample("gpu-0"), sample("gpu-1")],
        required_profile="dual-1080-replicated",
        required_gpu_substring="GTX 1080",
    )

    assert wrong_profile["checks"]["hardware_profile"] is False
    assert wrong_profile["passed"] is False
    assert wrong_gpu["checks"]["gpu_names"] is False
    assert wrong_gpu["passed"] is False
    assert failed_call["checks"]["representative_calls"] is False
    assert failed_call["passed"] is False


def test_split_and_development_profiles_keep_their_intended_concurrency():
    split = benchmark.evaluate_gate(
        {"hardware_profile": "dual-1080-split", "accepted_slots": 1},
        dual_1080_hardware(),
        representative_calls(),
        [sample("split-0"), sample("split-0")],
        required_profile="dual-1080-split",
        required_gpu_substring="GTX 1080",
    )
    development = benchmark.evaluate_gate(
        {"hardware_profile": "dev-1070", "accepted_slots": 1},
        {"cuda_devices": [{"name": "NVIDIA GeForce GTX 1070"}]},
        representative_calls(),
        [sample("gpu-0"), sample("gpu-0")],
        required_profile="dev-1070",
        required_gpu_substring="GTX 1070",
    )

    assert split["passed"] is True
    assert split["requirements"]["cuda_devices"] == 2
    assert split["requirements"]["distinct_runner_slots"] == 1
    assert development["passed"] is True


def test_cli_writes_failed_report_and_exits_nonzero(monkeypatch, tmp_path):
    inventory = {
        "deployment": {
            "state": "ready",
            "served_model_id": "apertus-test",
            "hardware_profile": "dual-1080-replicated",
            "accepted_slots": 2,
        },
        "hardware": dual_1080_hardware(),
        "runtime_metrics": {"runner_rss_bytes": 1024},
    }

    def completed_sample(index: int) -> dict:
        return {
            "index": index,
            "ok": True,
            "schema_valid": True,
            "citation_valid": True,
            "latency_ms": 5,
            "queue_wait_ms": 0,
            "slot": "gpu-0",
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "tokens_per_second": 100.0,
            "error": None,
        }

    monkeypatch.setattr(benchmark, "request_json", lambda *_args, **_kwargs: (inventory, {}, 200))
    monkeypatch.setattr(benchmark, "gpu_sample", lambda: [100, 100])
    monkeypatch.setattr(
        benchmark,
        "call",
        lambda _base_url, _model, index, _padding: completed_sample(index),
    )
    output = tmp_path / "failed-report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark_local_inference.py",
            "--output",
            str(output),
            "--required-profile",
            "dual-1080-replicated",
            "--require-gpu-substring",
            "GTX 1080",
        ],
    )

    with pytest.raises(SystemExit) as exit_info:
        benchmark.main()

    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_info.value.code == 1
    assert report["result"] == "fail"
    assert report["promotion_gate"]["checks"]["distinct_runner_slots"] is False
