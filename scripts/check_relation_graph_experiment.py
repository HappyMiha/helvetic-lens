"""Evaluate whether an evidence-first graph prototype earns a product surface."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path

VARIANTS = {"inbox_list_v1", "graph_review_v1"}
LOCALES = {"de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"}
DECISIONS = {"confirmed", "rejected"}
MIN_TRIALS_PER_VARIANT = 30
MIN_PARTICIPANTS_PER_VARIANT = 10
MIN_TASKS = 5


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _hex(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value.lower())
    )


def _percentile(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percent / 100 * len(ordered)) - 1)
    return round(ordered[index], 2)


def _variant_metrics(trials: list[dict], variant: str) -> dict:
    rows = [
        row
        for row in trials
        if isinstance(row, dict) and row.get("variant") == variant
    ]
    completed = [row for row in rows if row.get("completed") is True]
    durations = [
        float(duration)
        for row in completed
        if isinstance((duration := row.get("duration_ms")), int | float)
        and not isinstance(duration, bool)
        and 0 < duration <= 1_800_000
    ]
    correct = sum(row.get("decision") == row.get("expected_decision") for row in completed)
    evidence_opened = sum(row.get("evidence_opened") is True for row in completed)
    return {
        "trials": len(rows),
        "participants": len(
            {
                participant
                for row in rows
                if isinstance((participant := row.get("participant_id")), str)
                and participant.strip()
            }
        ),
        "tasks": len(
            {
                task
                for row in rows
                if isinstance((task := row.get("task_id")), str) and task.strip()
            }
        ),
        "completed": len(completed),
        "completion_rate": round(len(completed) / len(rows), 4) if rows else 0.0,
        "accuracy": round(correct / len(completed), 4) if completed else 0.0,
        "evidence_open_rate": (
            round(evidence_opened / len(completed), 4) if completed else 0.0
        ),
        "duration": {
            "p50_ms": _percentile(durations, 50),
            "p95_ms": _percentile(durations, 95),
            "max_ms": round(max(durations), 2) if durations else None,
        },
    }


def validate(
    path: Path,
    *,
    require_results: bool,
    expected_commit: str | None = None,
    clean_checkout: bool | None = None,
) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "hl053.graph-experiment.v1":
        raise ValueError("Unsupported relation-graph experiment schema.")
    required = {
        "experiment_id",
        "build_commit",
        "task_set_revision",
        "randomization_method",
        "started_at",
        "completed_at",
        "trials",
    }
    missing = required - set(payload)
    if missing:
        raise ValueError(f"Missing experiment metadata: {', '.join(sorted(missing))}")
    trials = payload.get("trials")
    if not isinstance(trials, list):
        raise TypeError("trials must be a list.")
    if not require_results:
        return {
            "schema_version": payload["schema_version"],
            "mode": "template",
            "passed": True,
            "decision": "not_run",
            "trials": len(trials),
            "failures": [],
        }

    failures: list[str] = []
    started_at = _timestamp(payload.get("started_at"))
    completed_at = _timestamp(payload.get("completed_at"))
    if started_at is None or completed_at is None or completed_at < started_at:
        failures.append("valid timezone-aware experiment timestamps are required")
    for field in ("experiment_id", "task_set_revision", "randomization_method"):
        if not isinstance(payload.get(field), str) or len(payload[field].strip()) < 8:
            failures.append(f"{field} must identify the completed experiment")
    if not _hex(payload.get("build_commit"), 40):
        failures.append("build_commit must be a 40-character Git revision")
    elif expected_commit and payload["build_commit"] != expected_commit:
        failures.append("build_commit does not match the checked-out release")
    if clean_checkout is False:
        failures.append("the experiment checkout contains uncommitted changes")

    required_trial_fields = {
        "participant_id",
        "locale",
        "variant",
        "task_id",
        "expected_decision",
        "decision",
        "duration_ms",
        "completed",
        "evidence_opened",
        "authorization_passed",
        "accessible_without_color",
        "list_alternative_complete",
    }
    seen_trials: set[tuple] = set()
    participants_by_variant: dict[str, set[str]] = defaultdict(set)
    tasks_by_variant: dict[str, set[str]] = defaultdict(set)
    for index, trial in enumerate(trials, start=1):
        if not isinstance(trial, dict):
            failures.append(f"trial {index} must be an object")
            continue
        missing_fields = required_trial_fields - set(trial)
        if missing_fields:
            failures.append(f"trial {index} is missing {', '.join(sorted(missing_fields))}")
            continue
        participant = trial.get("participant_id")
        task = trial.get("task_id")
        variant = trial.get("variant")
        if not isinstance(participant, str) or not participant.strip():
            failures.append(f"trial {index} needs a pseudonymous participant_id")
        if not isinstance(task, str) or not task.strip():
            failures.append(f"trial {index} needs a task_id")
        if variant not in VARIANTS:
            failures.append(f"trial {index} has an unsupported workflow variant")
            continue
        if trial.get("locale") not in LOCALES:
            failures.append(f"trial {index} has an unsupported locale")
        if trial.get("expected_decision") not in DECISIONS:
            failures.append(f"trial {index} needs a confirmed/rejected expected decision")
        completed = trial.get("completed")
        if not isinstance(completed, bool):
            failures.append(f"trial {index} must explicitly record completion")
        if completed is True:
            if trial.get("decision") not in DECISIONS:
                failures.append(f"trial {index} needs the participant decision")
            duration = trial.get("duration_ms")
            if (
                not isinstance(duration, int | float)
                or isinstance(duration, bool)
                or not 0 < duration <= 1_800_000
            ):
                failures.append(f"trial {index} needs a duration from 1 to 1800000 ms")
        for field in (
            "evidence_opened",
            "authorization_passed",
            "accessible_without_color",
            "list_alternative_complete",
        ):
            if not isinstance(trial.get(field), bool):
                failures.append(f"trial {index} must explicitly record {field}")
        key = (participant, task, variant)
        if key in seen_trials:
            failures.append(f"trial {index} duplicates a participant/task/variant row")
        seen_trials.add(key)
        participants_by_variant[variant].add(participant)
        tasks_by_variant[variant].add(task)

    participant_overlap = participants_by_variant["inbox_list_v1"] & participants_by_variant[
        "graph_review_v1"
    ]
    if participant_overlap:
        failures.append("participants must be assigned to only one workflow variant")
    if tasks_by_variant["inbox_list_v1"] != tasks_by_variant["graph_review_v1"]:
        failures.append("both variants must use the same task set")
    locales_by_variant = {
        variant: {
            row.get("locale")
            for row in trials
            if isinstance(row, dict) and row.get("variant") == variant
        }
        for variant in VARIANTS
    }
    if any(locales != LOCALES for locales in locales_by_variant.values()):
        failures.append("each variant must cover de-CH, fr-CH, it-CH, rm-CH, and en-CH")

    metrics = {variant: _variant_metrics(trials, variant) for variant in sorted(VARIANTS)}
    baseline = metrics["inbox_list_v1"]
    graph = metrics["graph_review_v1"]
    sample_complete = all(
        (
            item["trials"] >= MIN_TRIALS_PER_VARIANT
            and item["participants"] >= MIN_PARTICIPANTS_PER_VARIANT
            and item["tasks"] >= MIN_TASKS
        )
        for item in metrics.values()
    )
    if not sample_complete:
        failures.append("each variant needs at least 30 trials, 10 participants, and 5 tasks")
    safety_passed = all(
        isinstance(trial, dict)
        and trial.get("authorization_passed") is True
        and trial.get("accessible_without_color") is True
        and trial.get("list_alternative_complete") is True
        for trial in trials
    )
    if not safety_passed:
        failures.append("authorization, accessible status, and complete list fallback must all pass")
    quality_noninferior = (
        graph["accuracy"] >= baseline["accuracy"] - 0.02
        and graph["completion_rate"] >= baseline["completion_rate"] - 0.02
        and graph["evidence_open_rate"] >= baseline["evidence_open_rate"] - 0.05
    )
    if not quality_noninferior:
        failures.append("the graph regressed correctness, completion, or evidence use")
    baseline_p50 = baseline["duration"]["p50_ms"]
    graph_p50 = graph["duration"]["p50_ms"]
    time_improvement = (
        baseline_p50 is not None
        and graph_p50 is not None
        and baseline_p50 > 0
        and (baseline_p50 - graph_p50) / baseline_p50 >= 0.20
    )
    accuracy_improvement = graph["accuracy"] - baseline["accuracy"] >= 0.05
    evidence_valid = not failures
    decision = (
        "promote_graph_as_secondary_view"
        if evidence_valid and (time_improvement or accuracy_improvement)
        else "retain_inbox_list_only"
        if evidence_valid
        else "insufficient_or_unsafe_evidence"
    )
    return {
        "schema_version": payload["schema_version"],
        "mode": "results",
        "experiment_id": payload.get("experiment_id"),
        "build_commit": payload.get("build_commit"),
        "task_set_revision": payload.get("task_set_revision"),
        "passed": evidence_valid,
        "decision": decision,
        "benefit": {
            "time_improvement_at_least_20_percent": time_improvement,
            "accuracy_improvement_at_least_5_points": accuracy_improvement,
        },
        "metrics": metrics,
        "failures": failures,
    }


def _git_state(repo_root: Path) -> tuple[str | None, bool]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None, False
    return commit, not status


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Evaluate the HL-053 graph experiment.")
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=repo_root / "demo" / "relation-graph-experiment.template.json",
    )
    parser.add_argument("--results", action="store_true")
    args = parser.parse_args()
    commit, clean = _git_state(repo_root)
    result = validate(
        args.path,
        require_results=args.results,
        expected_commit=commit if args.results else None,
        clean_checkout=clean if args.results else None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
