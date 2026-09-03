import hashlib
import json
from pathlib import Path

from scripts.check_ai_triage_release import evaluate

TEMPLATE = Path(__file__).resolve().parents[3] / "demo" / "ai-triage-usability-review.template.json"


def capacity_payload():
    return {
        "schema_version": "1",
        "started_at": "2026-09-03T11:00:00+02:00",
        "criteria": {"passed": True, "checks": {"complete": True}},
        "target": {
            "base_url": "https://capacity.example.ch",
            "host": "capacity-server",
            "git": {"commit": "a" * 40, "clean": True},
        },
        "scenario": {
            "account_count": 100,
            "organization_count": 10,
            "read_requests": 300,
            "ai_submissions": 20,
        },
        "inference_benchmark": {
            "deployment": {"hardware_profile": "dual-1080-replicated"}
        },
        "platform_status": {
            "generated_at": "2026-09-03T12:00:00+02:00",
            "ai_triage": {
                "records": {"failed": 0, "failed_rate": 0.0, "limited_rate": 0.0},
                "latency": {
                    "deterministic_overview": {"samples": 10, "p95_ms": 250},
                    "time_to_first_useful_insight": {"source": "deterministic_overview"},
                    "provider_queue": {"samples": 20, "p95_ms": 400},
                    "inference": {"samples": 20, "p95_ms": 2_000},
                },
                "usage": {
                    "provider_calls": 30,
                    "token_counts": {"total_tokens": 12_000},
                    "requests_including_reuse": 20,
                    "cache_hit_rate": 0.0,
                },
                "evidence": {"validation_samples": 20, "acceptance_rate": 1.0},
                "actions": {
                    "decision_events": 5,
                    "accept_rate": 0.6,
                    "dismiss_rate": 0.4,
                },
            },
        },
    }


def usability_payload(capacity_sha256: str):
    payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    payload.update(
        review_round_id="round-2026-09-03",
        moderator_id="moderator-1",
        build_commit="a" * 40,
        target_host="capacity-server",
        model_profile="dual-1080-replicated",
        capacity_report_sha256=capacity_sha256,
    )
    for session in payload["sessions"]:
        session.update(
            participant_id=f"reviewer-{session['locale']}",
            started_at="2026-09-03T10:00:00+02:00",
            completed_at="2026-09-03T10:03:00+02:00",
            seconds_to_first_useful_insight=90,
            identified_main_material_change=True,
            main_material_change="The inserted deadline duty was identified.",
            identified_possible_organization_relevance=True,
            organization_relevance="The participant linked it to the compliance team.",
            opened_exact_evidence=True,
            evidence_reference="Saved passage evidence row 4 was opened.",
            identified_next_review_step=True,
            next_review_step="Assign legal review of the new deadline.",
            opened_all_exact_changes=False,
            action_specificity=True,
            action_owner_honest=True,
            action_due_state_honest=True,
            reviewed_action="Review the deadline with the compliance owner.",
            moderator_notes="Observed in the moderated fixture flow.",
        )
    return payload


def write_evidence(tmp_path, capacity):
    capacity_path = tmp_path / "capacity.json"
    capacity_path.write_text(json.dumps(capacity), encoding="utf-8")
    capacity_sha256 = hashlib.sha256(capacity_path.read_bytes()).hexdigest()
    usability_path = tmp_path / "usability.json"
    usability_path.write_text(
        json.dumps(usability_payload(capacity_sha256)), encoding="utf-8"
    )
    return capacity_path, usability_path


def test_release_gate_passes_only_with_bound_machine_and_human_evidence(tmp_path):
    capacity_path, usability_path = write_evidence(tmp_path, capacity_payload())

    result = evaluate(capacity_path, usability_path)

    assert result["passed"] is True
    assert all(result["checks"].values())


def test_release_gate_rejects_report_substitution(tmp_path):
    capacity_path, usability_path = write_evidence(tmp_path, capacity_payload())
    capacity = json.loads(capacity_path.read_text(encoding="utf-8"))
    capacity["platform_status"]["generated_at"] = "2026-09-03T12:01:00+02:00"
    capacity_path.write_text(json.dumps(capacity), encoding="utf-8")

    result = evaluate(capacity_path, usability_path)

    assert result["checks"]["capacity_report_bound_to_usability_round"] is False
    assert result["passed"] is False


def test_release_gate_rejects_missing_target_metrics_and_action_outcomes(tmp_path):
    capacity = capacity_payload()
    metrics = capacity["platform_status"]["ai_triage"]
    metrics["latency"]["provider_queue"]["samples"] = 0
    metrics["actions"]["decision_events"] = 0
    capacity_path, usability_path = write_evidence(tmp_path, capacity)

    result = evaluate(capacity_path, usability_path)

    assert result["checks"]["local_ai_latency_baseline_measured"] is False
    assert result["checks"]["review_action_outcomes_measured"] is False
    assert result["passed"] is False
