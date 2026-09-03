import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "run_capacity_gate", ROOT / "scripts" / "run_capacity_gate.py"
)
capacity = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = capacity
SPEC.loader.exec_module(capacity)


def valid_manifest():
    organizations = []
    for organization_index in range(10):
        organizations.append(
            {
                "organization_id": f"org-{organization_index}",
                "law_id": f"law-{organization_index}",
                "old_version_id": f"old-{organization_index}",
                "new_version_id": f"new-{organization_index}",
                "comparison_id": f"comparison-{organization_index}",
                "accounts": [
                    {
                        "id": f"account-{organization_index}-{account_index}",
                        "email": f"account-{organization_index}-{account_index}@capacity.invalid",
                        "locale": "en-CH",
                    }
                    for account_index in range(10)
                ],
            }
        )
    return {"account_count": 100, "organizations": organizations}


def passing_gate():
    arguments = SimpleNamespace(
        resource_interval=2,
        inference_report=None,
        backup_report=None,
        read_concurrency=20,
        read_requests=300,
    )
    gate = capacity.CapacityGate(arguments, valid_manifest(), "test-password")
    for index in range(300):
        gate.observations.append(
            capacity.Observation(
                "read",
                ("registry", "evidence", "comparison")[index % 3],
                200,
                100,
                f"read-{index}",
                True,
            )
        )
    operations = ["scan"] * 5 + ["ai_analysis"] * 10 + ["ai_question"] * 10 + ["connector"]
    for index, operation in enumerate(operations):
        gate.observations.append(
            capacity.Observation("enqueue", operation, 202, 200, f"enqueue-{index}", True)
        )
    gate.resource_monitor.samples = [
        {
            "disk": {"used_bytes": 10_000, "free_bytes": 20 * 1024**3},
            "host": {"memory_percent": 45, "swap_used_bytes": 0},
        },
        {
            "disk": {"used_bytes": 20_000, "free_bytes": 20 * 1024**3},
            "host": {"memory_percent": 60, "swap_used_bytes": 0},
        },
    ]
    for organization in gate.manifest["organizations"]:
        comparison_id = organization["comparison_id"]
        gate.consistency_before[comparison_id] = {
            "structure_sha256": f"digest-{comparison_id}",
            "history_ids": [],
            "history_types": {},
        }
        gate.consistency_after[comparison_id] = {
            "structure_sha256": f"digest-{comparison_id}",
            "history_ids": [f"question-{comparison_id}", f"impact-{comparison_id}"],
            "history_types": {"question": 1, "impact": 1},
        }
    gate.recovery_result = {
        "completed": True,
        "active_model_before": "apertus-8b-q4km",
    }
    gate.inference_report = {
        "benchmark": "HL-032-local-structured-v2",
        "result": "pass",
        "promotion_gate": {
            "passed": True,
            "requirements": {"profile": "dual-1080-replicated", "cuda_devices": 2},
        },
        "hardware": {
            "cuda_devices": [
                {"name": "NVIDIA GeForce GTX 1080"},
                {"name": "NVIDIA GeForce GTX 1080"},
            ]
        },
        "representative_calls": {
            "total": 20,
            "successful": 20,
            "schema_valid": 20,
            "citation_valid": 20,
            "timeouts": 0,
            "oom": 0,
        },
    }
    gate.backup_report = {
        "schema_version": "1",
        "target_host": "capacity-server",
        "backup_id": "20260903T155446Z",
        "backup_seconds": 42.7,
        "restore_seconds": 58.4,
        "verified": True,
        "verification": ["database", "artifact", "login"],
    }
    jobs = []
    results = {}
    by_kind = {
        "scan": {"failed": 5},
        "ai_analysis": {"succeeded": 10},
        "ai_question": {"succeeded": 10},
        "connector": {"succeeded": 1},
        "model_runner_start": {"succeeded": 1},
    }
    for kind, counts in by_kind.items():
        for state, count in counts.items():
            for index in range(count):
                job_id = f"{kind}-{state}-{index}"
                jobs.append((job_id, kind, None))
                results[job_id] = {"kind": kind, "state": state, "error_code": None}
    gate.jobs = jobs
    job_summary = {
        "waited": True,
        "submitted": len(jobs),
        "states": {"succeeded": 22, "failed": 5},
        "by_kind": by_kind,
        "timed_out": 0,
        "results": results,
    }
    platform_status = {
        "model": {"model_id": "apertus-8b-q4km", "state": "ready"}
    }
    return gate, job_summary, platform_status


def test_complete_capacity_evidence_passes():
    gate, jobs, platform = passing_gate()

    result = gate.criteria(jobs, platform)

    assert result["passed"] is True
    assert all(result["checks"].values())


def test_capacity_gate_rejects_declared_accounts_without_real_accounts():
    gate, jobs, platform = passing_gate()
    gate.manifest["organizations"][0]["accounts"] = gate.manifest["organizations"][0]["accounts"][:3]

    result = gate.criteria(jobs, platform)

    assert result["checks"]["100_real_unique_accounts"] is False
    assert result["passed"] is False


def test_capacity_gate_rejects_diagnostic_workload_and_missing_telemetry():
    gate, jobs, platform = passing_gate()
    gate.arguments.read_requests = 60
    gate.resource_monitor.samples[0]["host"].pop("swap_used_bytes")
    gate.resource_monitor.samples[1]["host"].pop("swap_used_bytes")

    result = gate.criteria(jobs, platform)

    assert result["checks"]["complete_read_workload_executed"] is False
    assert result["checks"]["resource_telemetry_complete"] is False
    assert result["passed"] is False


def test_capacity_gate_requires_completed_connector_and_target_profile():
    gate, jobs, platform = passing_gate()
    jobs["by_kind"]["connector"] = {"failed": 1}
    gate.inference_report["promotion_gate"]["requirements"]["profile"] = "dev-1070"

    result = gate.criteria(jobs, platform)

    assert result["checks"]["connector_work_completed"] is False
    assert result["checks"]["target_inference_benchmark_passed"] is False
    assert result["passed"] is False


def test_capacity_gate_rejects_duplicate_ai_history_and_unrecovered_model():
    gate, jobs, platform = passing_gate()
    first = gate.manifest["organizations"][0]["comparison_id"]
    gate.consistency_after[first]["history_types"]["question"] = 2
    platform["model"] = {"model_id": None, "state": "stopped"}

    result = gate.criteria(jobs, platform)

    assert result["checks"]["comparison_and_history_consistency"] is False
    assert result["checks"]["active_model_recovered"] is False
    assert result["passed"] is False
