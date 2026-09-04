"""Combine target capacity evidence and independent usability results for HL-064."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from scripts.check_ai_triage_usability import validate as validate_usability
except ModuleNotFoundError:  # Direct execution adds scripts/, rather than the repo root, to sys.path.
    from check_ai_triage_usability import validate as validate_usability


def _load(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _at_least(value: Any, minimum: float) -> bool:
    return (
        isinstance(value, int | float) and not isinstance(value, bool)
        and math.isfinite(value) and value >= minimum
    )


def _is_git_commit(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value.lower())
    )


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def evaluate(capacity_path: Path, usability_path: Path) -> dict:
    capacity, capacity_sha256 = _load(capacity_path)
    usability = validate_usability(usability_path, require_results=True)
    criteria = capacity.get("criteria") or {}
    target = capacity.get("target") or {}
    git = target.get("git") or {}
    scenario = capacity.get("scenario") or {}
    platform_status = capacity.get("platform_status") or {}
    metrics = platform_status.get("ai_triage") or {}
    records = metrics.get("records") or {}
    latency = metrics.get("latency") or {}
    # Compatibility with older exports never converts a machine timing into
    # observed comprehension. Prefer the canonical field when present, even if
    # it is empty: an obsolete alias must not mask a missing current sample.
    legacy_overview = latency.get("time_to_first_useful_insight") or {}
    deterministic = latency.get("deterministic_overview") or {}
    if "deterministic_overview" not in latency:
        deterministic = (
            legacy_overview if legacy_overview.get("source") == "deterministic_overview" else {}
        )
    provider_queue = latency.get("provider_queue") or {}
    inference_latency = latency.get("inference") or {}
    usage = metrics.get("usage") or {}
    evidence = metrics.get("evidence") or {}
    actions = metrics.get("actions") or {}
    inference = capacity.get("inference_benchmark") or {}
    inference_profile = (inference.get("deployment") or {}).get("hardware_profile")
    capacity_started = _timestamp(capacity.get("started_at"))
    review_completed = _timestamp((usability.get("session_window") or {}).get("completed_at"))

    checks = {
        "capacity_gate_passed": criteria.get("passed") is True
        and bool(criteria.get("checks"))
        and all(criteria["checks"].values()),
        "measured_clean_release_commit": bool(
            _is_git_commit(git.get("commit")) and git.get("clean") is True
        ),
        "public_https_target_measured": isinstance(target.get("base_url"), str)
        and target["base_url"].startswith("https://"),
        "complete_capacity_scenario_measured": (
            scenario.get("account_count") == 100
            and scenario.get("organization_count", 0) >= 10
            and scenario.get("read_requests", 0) >= 300
            and scenario.get("ai_submissions", 0) >= 20
        ),
        "capacity_report_bound_to_usability_round": usability.get("capacity_report_sha256")
        == capacity_sha256,
        "same_build_host_and_model_reviewed": (
            usability.get("build_commit") == git.get("commit")
            and usability.get("target_host") == target.get("host")
            and usability.get("model_profile") == inference_profile
        ),
        "expected_regression_fixture_reviewed": (
            usability.get("corpus_revision") == "hl064.v1"
            and usability.get("comparison_fixture") == "insertion-and-renumbering"
        ),
        "five_independent_usability_sessions_passed": usability.get("passed") is True,
        "usability_decisions_precede_captured_metrics": bool(
            capacity_started and review_completed and review_completed <= capacity_started
        ),
        "deterministic_overview_latency_measured": (
            _at_least(deterministic.get("samples"), 10)
            and _at_least(deterministic.get("p95_ms"), 0)
            and deterministic["p95_ms"] < 1000
        ),
        "local_ai_latency_baseline_measured": (
            _at_least(provider_queue.get("samples"), 20)
            and _at_least(inference_latency.get("samples"), 20)
            and _at_least(usage.get("provider_calls"), 20)
            and usage.get("provider_calls", 81) <= 80
        ),
        "token_cache_and_outcome_rates_recorded": (
            _at_least((usage.get("token_counts") or {}).get("total_tokens"), 1)
            and _at_least(usage.get("requests_including_reuse"), 20)
            and isinstance(usage.get("cache_hit_rate"), int | float)
            and isinstance(records.get("failed_rate"), int | float)
            and isinstance(records.get("limited_rate"), int | float)
        ),
        "all_capacity_ai_results_validated": (
            records.get("failed") == 0
            and _at_least(evidence.get("validation_samples"), 20)
            and evidence.get("acceptance_rate") == 1.0
        ),
        "review_action_outcomes_measured": (
            _at_least(actions.get("decision_events"), 5)
            and isinstance(actions.get("accept_rate"), int | float)
            and isinstance(actions.get("dismiss_rate"), int | float)
        ),
    }
    return {
        "schema_version": "hl064.release.v2",
        "passed": all(checks.values()),
        "checks": checks,
        "evidence": {
            "capacity_report_sha256": capacity_sha256,
            "build_commit": git.get("commit"),
            "target_host": target.get("host"),
            "model_profile": inference_profile,
            "review_round_id": usability.get("review_round_id"),
            "metrics_generated_at": platform_status.get("generated_at"),
            "deterministic_overview": deterministic,
            "provider_queue": provider_queue,
            "inference": inference_latency,
            "provider_calls": usage.get("provider_calls"),
            "evidence_acceptance_rate": evidence.get("acceptance_rate"),
            "action_outcomes": actions,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the complete HL-064 release evidence.")
    parser.add_argument("--capacity-report", type=Path, required=True)
    parser.add_argument("--usability-results", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(args.capacity_report, args.usability_results)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
