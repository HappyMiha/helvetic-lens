#!/usr/bin/env python3
"""Development-only selection followed by one fresh, immutable local validation.

Reuse existing cache verification, bounded local runner and durable journals.
Prepare stores raw inputs outside Git; reports retain IDs, hashes and scores only.
"""
import argparse
import asyncio
import fcntl
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from helvetic_lens import decision_engines
from helvetic_lens import research_gate_policy as policy

from scripts import evaluate_iterative_research as runner

LIMITS = {"local_calls": 241, "seconds": 480,
    "per_stage": {"development": {**runner.LIMITS, "calls": 121}, "validation": runner.LIMITS}}

@contextmanager
def exclusive(directory):
    with (directory / "study.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def freeze(path, payload):
    if path.exists():
        raise ValueError("Immutable record already exists")
    value = {**payload, "sha256": runner.fingerprint(payload)}
    runner.atomic_write(path, value)
    return value


def frozen(path):
    value = json.loads(path.read_text())
    if value["sha256"] != runner.fingerprint({k: v for k, v in value.items() if k != "sha256"}):
        raise ValueError("Immutable record changed")
    return value


def prepare(cache, directory):
    runner.outside_repository(directory).mkdir(parents=True, exist_ok=True)
    if (directory / "study.json").exists():
        raise ValueError("Study exists; reuse its bounded journals")
    old = json.loads((runner.ROOT / "docs/research-evaluations/2026-09-28-research-gate-laya.json").read_text())
    previous = {r["query_id"] for r in old["cases"]}
    development = runner.prepare(cache, directory / "development", split="dev", offset=12, prior_queries=previous, call_limit=121)
    dev_plan = runner.load_plan(directory / "development")
    previous.update(r["query_id"] for r in dev_plan["cases"])
    validation = runner.prepare(cache, directory / "validation", split="test", offset=42, prior_queries=previous)
    study = freeze(directory / "study.json", {
        "schema": "research-gate-policy-study/v1", "created_at": datetime.now(timezone.utc).isoformat(),
        "policy": policy.VERSION, "thresholds": list(policy.THRESHOLDS),
        "policy_sha256": runner.file_hash(Path(policy.__file__)),
        "plans": {"development": development, "validation": validation},
        "limits": LIMITS,
        "heldout_reuse": False, "prior_query_overlap": 0, "split_overlap": 0,
    })
    return {"study_sha256": study["sha256"], "plans": study["plans"]}


def load_study(directory, *, verify_runtime=True):
    runner.outside_repository(directory)
    study = frozen(directory / "study.json")
    if (study["policy_sha256"] != runner.file_hash(Path(policy.__file__))
            or study["policy"] != policy.VERSION or study["thresholds"] != list(policy.THRESHOLDS)
            or study["limits"] != LIMITS):
        raise ValueError("Policy or budgets changed")
    plans = {stage: runner.load_plan(directory / stage, verify_runtime=verify_runtime) for stage in ("development", "validation")}
    for stage, plan in plans.items():
        if plan["plan_sha256"] != study["plans"][stage]["plan_sha256"]:
            raise ValueError("Input plan changed")
        sampling = plan["protocol"]["sampling"]
        expected = ("dev", 12) if stage == "development" else ("test", 42)
        if (sampling["split"], sampling["offset"]) != expected:
            raise ValueError("Unregistered sample")
        if plan["protocol"]["limits"] != LIMITS["per_stage"][stage]:
            raise ValueError("Stage budget changed")
    if ({r["query_id"] for r in plans["development"]["cases"]}
            & {r["query_id"] for r in plans["validation"]["cases"]}):
        raise ValueError("Overlapping development and validation")
    return study, plans


def load_selection(directory, study):
    selected = frozen(directory / "selection.json")
    if (selected["study_sha256"] != study["sha256"]
            or selected["development_journal_sha256"] != runner.file_hash(directory / "development/journal.json")):
        raise ValueError("Selection no longer matches development")
    return selected


async def collect(directory, stage, choose):
    with exclusive(directory):
        if stage not in {"development", "validation"}:
            raise ValueError("Unknown stage")
        study, plans = load_study(directory)
        if stage == "validation":
            selected = load_selection(directory, study)
            if selected["result"]["threshold"] is None:
                raise ValueError("Development did not select a policy; validation must stay unopened")
        elif (directory / "selection.json").exists():
            raise ValueError("Development is frozen; do not repeat it")
        return await runner.collect(directory / stage, plans[stage], choose)


def select(directory):
    with exclusive(directory):
        return select_locked(directory)


def select_locked(directory):
    study, plans = load_study(directory)
    if (directory / "validation/journal.json").exists():
        raise ValueError("Validation was opened before selection")
    state = runner.journal(directory / "development", plans["development"])
    selected = freeze(directory / "selection.json", {
        "study_sha256": study["sha256"],
        "development_journal_sha256": runner.file_hash(directory / "development/journal.json"),
        "selected_at": datetime.now(timezone.utc).isoformat(),
        "result": policy.select_development(plans["development"]["cases"], state["rows"]),
    })
    return {"threshold": selected["result"]["threshold"], "selection_sha256": selected["sha256"],
        "candidates": [{key: row[key] for key in ("threshold", "complete", "deferred_rejections", "extra_review_fraction",
            "positive_labels", "positive_rejections", "positive_rejections_baseline", "negative_rejections_retained", "negative_rejections_baseline")}
            for row in selected["result"]["candidates"]]}


def report(directory, output):
    study, plans = load_study(directory, verify_runtime=False)
    selection = load_selection(directory, study)
    threshold = selection["result"]["threshold"]
    result = {"study": study, "selection": selection, "recorded_at": datetime.now(timezone.utc).isoformat(),
        "professional_acceptance": "OPEN", "cost_usd": None, "confidence_is_accuracy": False,
        "scope": "NoMIRACL full-passage judgments compared with short-snippet topical decisions; no professional accuracy or whole-web recall claim."}
    attempts = 0
    for stage, plan in plans.items():
        if stage == "validation" and threshold is None:
            result[stage] = {"status": "not_run_development_gate_failed", "planned_cases": len(plan["cases"])}
            continue
        state = runner.journal(directory / stage, plan)
        attempts += len(state["rows"])
        result[stage] = {"protocol": plan["protocol"], "plan_sha256": plan["plan_sha256"],
            "sources": plan["sources"], "observations": state["rows"],
            "cases": [{k: v for k, v in row.items() if k != "state"} for row in plan["cases"]],
            "reserved_or_elapsed_seconds": runner.spent(state["rows"])}
        if threshold is not None:
            result[stage]["comparison"] = policy.comparison(plan["cases"], state["rows"], threshold)
    result["promotion"] = policy.promotion(result["validation"]["comparison"]) if threshold is not None else {
        "passed": False, "reason": "No development candidate met the fixed gates."}
    result["calls"] = {"local_attempts": attempts, "hosted": 0, "web_search": 0, "source_fetch": 0, "reasoning": 0}
    runner.atomic_write(output, result)
    return {"calls": result["calls"], "threshold": threshold, "promotion": result["promotion"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "development", "select", "validation", "report"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--credentials-file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.stage == "prepare":
        result = prepare(args.cache, args.directory)
    elif args.stage == "select":
        result = select(args.directory)
    elif args.stage == "report":
        result = report(args.directory, args.output)
    else:
        from helvetic_lens.config import Settings
        from pydantic import SecretStr

        credentials = json.loads(args.credentials_file.read_text())
        settings = Settings(_env_file=None, laya_base_url=runner.LOCAL_URL,
            laya_api_key=SecretStr(credentials["LAYA_API_KEY"]), typesafe_api_key=SecretStr(""), search1api_api_key=SecretStr(""))
        engine = decision_engines.LayaEngine(settings)
        result = asyncio.run(collect(args.directory, args.stage, engine.choose))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
