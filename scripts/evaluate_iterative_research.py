#!/usr/bin/env python3
"""Frozen public gate evaluation and offline fictional-trace audit.

prepare reuses verified cached NoMIRACL files, run-local calls only loopback Laya,
report emits IDs/hashes/metrics, audit checks existing public fictional receipts.
Raw input and journals must live outside the repository. No production DB access.
"""
import argparse
import asyncio
import fcntl
import gzip
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from helvetic_lens import decision_engines, product_research_gate
from helvetic_lens.research_evaluation import audit_fixture, gate_metrics

from scripts.evaluate_dossier_retrieval import DATA_REVISION, LANGUAGES, digest

ROOT = Path(__file__).resolve().parents[1]
LOCAL_URL = "http://127.0.0.1:18761/v1/systemone"
MODEL = "laya-multilingual@e4e9ddf21a7b1903b7acffd8814ad4307bf63a67"
LIMITS = {"calls": 120, "seconds": 240, "per_call_seconds": 12}


def fingerprint(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode())


def file_hash(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def atomic_write(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as output:
        json.dump(value, output, ensure_ascii=False, indent=2, allow_nan=False)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(path)


def outside_repository(path):
    if path.resolve().is_relative_to(ROOT):
        raise ValueError("Raw evaluation inputs and journals must remain outside Git")
    return path


def protocol():
    return {"schema": "research-gate-evaluation/v1", "dataset": "miracl/nomiracl", "revision": DATA_REVISION,
        "sampling": {"split": "test", "offset": 40, "queries_per_subset_language": 2, "languages": list(LANGUAGES)},
        "limits": LIMITS, "endpoint": LOCAL_URL, "model": MODEL,
        "gate_sha256": file_hash(Path(product_research_gate.__file__)),
        "adapter_sha256": file_hash(Path(decision_engines.__file__)),
        "prompt_sha256": fingerprint({"instructions": product_research_gate.INSTRUCTIONS, "criteria": product_research_gate.CRITERIA}),
        "representation": {"title_characters": 240, "snippet_characters": 600, "question_and_branch": "same original dataset query"}}


def prepare(cache, directory):
    outside_repository(directory).mkdir(parents=True, exist_ok=True)
    if (directory / "plan.json").exists():
        raise ValueError("Frozen plan already exists; reuse it")
    receipt = json.loads((ROOT / "docs/product-evaluations/2026-09-28-dossier-retrieval.json").read_text())
    if receipt["revision"] != DATA_REVISION:
        raise ValueError("Unexpected dataset revision")
    manifest = {row["url"]: row for row in receipt["sources"]}
    inputs, cases = [], []
    for language in LANGUAGES:
        def verified(relative, language=language):
            url = f"https://huggingface.co/datasets/miracl/nomiracl/resolve/{DATA_REVISION}/data/{language}/{relative}"
            path = cache / (language + "-" + relative.replace("/", "-"))
            expected = manifest[url]
            actual = file_hash(path)
            if actual != expected["sha256"] or path.stat().st_size != expected["bytes"]:
                raise ValueError("Public source cache does not match its pinned manifest")
            inputs.append({"url": url, "sha256": actual, "bytes": path.stat().st_size})
            return path
        selected = []
        for subset in ("relevant", "non_relevant"):
            topics = dict(line.split("\t", 1) for line in verified(f"topics/test.{subset}.tsv").read_text().splitlines())
            labels = {}
            for line in verified(f"qrels/test.{subset}.tsv").read_text().splitlines():
                query, _, document, label = line.split()
                labels.setdefault(query, {})[document] = int(label)
            keys = sorted(topics, key=lambda k: digest((language + ":" + k).encode()))[40:42]
            if len(keys) != 2:
                raise ValueError("Insufficient held-out queries")
            for key in keys:
                selected.append({"query_id": language + ":" + key, "query": topics[key],
                    "subset": subset, "labels": labels[key]})
        wanted = {key for sample in selected for key in sample["labels"]}
        corpus = {}
        with gzip.open(verified("corpus.jsonl.gz"), "rt") as source:
            for line in source:
                row = json.loads(line)
                if row["docid"] in wanted:
                    corpus[row["docid"]] = row
        if wanted != corpus.keys():
            raise ValueError("Incomplete public corpus")
        for sample in selected:
            for key, label in sorted(sample["labels"].items()):
                row = corpus[key]
                state = {"question": sample["query"], "branch": sample["query"],
                    "title": row["title"][:240], "snippet": row["text"][:600]}
                cases.append({"id": sample["query_id"] + "/" + key, "query_id": sample["query_id"],
                    "document_id": language + ":" + key, "language": language, "subset": sample["subset"],
                    "label": label, "state": state, "input_sha256": fingerprint(state),
                    "passage_sha256": digest(row["text"].encode()), "passage_characters": len(row["text"]),
                    "truncated": len(row["text"]) > 600 or len(row["title"]) > 240})
    # Freeze request order independent of model answers and balance languages over time.
    cases.sort(key=lambda row: digest(row["id"].encode()))
    if not cases or len(cases) > LIMITS["calls"]:
        raise ValueError("Sample exceeds the predeclared call budget")
    gate_metrics(cases, [])
    previous = set()
    for name in ("initial", "dev", "final"):
        name = "2026-09-28-dossier-retrieval" + ("" if name == "final" else "-" + name) + ".json"
        previous.update(row["id"] for row in json.loads((ROOT / "docs/product-evaluations" / name).read_text())["rows"])
    if previous.intersection(row["query_id"] for row in cases):
        raise ValueError("Sample overlaps earlier project measurements")
    payload = {"protocol": protocol(), "sources": inputs, "cases": cases,
        "earlier_project_query_overlap": 0, "created_at": datetime.now(timezone.utc).isoformat()}
    plan = {**payload, "plan_sha256": fingerprint(payload)}
    atomic_write(directory / "plan.json", plan)
    return {"plan_sha256": plan["plan_sha256"], "cases": len(cases), "queries": len({r['query_id'] for r in cases})}


def load_plan(directory):
    outside_repository(directory)
    plan = json.loads((directory / "plan.json").read_text())
    if fingerprint({k: v for k, v in plan.items() if k != "plan_sha256"}) != plan["plan_sha256"]:
        raise ValueError("Frozen plan changed")
    if plan["protocol"] != protocol():
        raise ValueError("Gate, adapter or protocol changed; this trial cannot be resumed")
    if not plan["cases"] or len(plan["cases"]) > LIMITS["calls"]:
        raise ValueError("Invalid planned size")
    for row in plan["cases"]:
        if row["input_sha256"] != fingerprint(row["state"]):
            raise ValueError("Candidate input changed")
    gate_metrics(plan["cases"], [])
    return plan


def journal(directory, plan):
    path = directory / "journal.json"
    value = json.loads(path.read_text()) if path.exists() else {"plan_sha256": plan["plan_sha256"], "rows": []}
    if value["plan_sha256"] != plan["plan_sha256"] or len(value["rows"]) > LIMITS["calls"]:
        raise ValueError("Journal does not match its frozen budget/input")
    for row in value["rows"]:
        if row.get("status") == "started":
            row.update(status="interrupted", outcome="interrupted", wall_ms=None)
        reserved = row.get("reserved_seconds")
        if type(reserved) not in (int, float) or not math.isfinite(reserved) or not 0 < reserved <= LIMITS["per_call_seconds"]:
            raise ValueError("Invalid reserved deadline")
    gate_metrics(plan["cases"], value["rows"])
    return value


def spent(rows):
    return sum(row["wall_ms"] / 1000 if row.get("wall_ms") is not None else row["reserved_seconds"] for row in rows)


async def collect(directory, plan, choose):
    """One journal owns this experiment; reserve each attempt before network I/O."""
    with (directory / "run.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = journal(directory, plan)
        atomic_write(directory / "journal.json", state)
        completed = {row["id"] for row in state["rows"]}
        carried, started = spent(state["rows"]), time.monotonic()
        for case in plan["cases"]:
            if case["id"] in completed:
                continue
            remaining = LIMITS["seconds"] - carried - (time.monotonic() - started)
            if len(state["rows"]) >= LIMITS["calls"] or remaining <= .01:
                break
            timeout = min(LIMITS["per_call_seconds"], remaining)
            row = {"id": case["id"], "status": "started", "reserved_seconds": timeout,
                "started_at": datetime.now(timezone.utc).isoformat()}
            state["rows"].append(row)
            atomic_write(directory / "journal.json", state)
            call_started = time.monotonic()
            try:
                async with asyncio.timeout(timeout):
                    answer = await choose(case["state"], product_research_gate.INSTRUCTIONS, product_research_gate.CRITERIA)
                if answer.model != MODEL or answer.choice not in product_research_gate.CRITERIA:
                    raise decision_engines.DecisionUnavailable("model_or_contract_mismatch")
                row.update(status="completed", outcome=answer.choice, model=answer.model,
                    confidence=answer.confidence, provider_latency_ms=answer.latency_ms,
                    input_tokens=answer.input_tokens, output_tokens=answer.output_tokens)
            except (decision_engines.DecisionUnavailable, TimeoutError) as error:
                row.update(status="failed", outcome="unavailable", error=getattr(error, "code", "timeout"))
            row["wall_ms"] = round((time.monotonic() - call_started) * 1000, 3)
            atomic_write(directory / "journal.json", state)
        return {"attempts": len(state["rows"]), "planned": len(plan["cases"]), "reserved_or_elapsed_seconds": round(spent(state["rows"]), 3)}


def report(directory, destination):
    plan = load_plan(directory)
    state = journal(directory, plan)
    result = {"recorded_at": datetime.now(timezone.utc).isoformat(), "plan_sha256": plan["plan_sha256"],
        "protocol": plan["protocol"], "sources": plan["sources"], "earlier_project_query_overlap": 0,
        "measurements": gate_metrics(plan["cases"], state["rows"]),
        "cases": [{k: v for k, v in row.items() if k != "state"} for row in plan["cases"]],
        "observations": state["rows"], "truncated_candidates": sum(row["truncated"] for row in plan["cases"]),
        "calls": {"local_attempts": len(state["rows"]), "hosted": 0, "web_search": 0, "source_fetch": 0, "reasoning": 0},
        "reserved_or_elapsed_seconds": round(spent(state["rows"]), 3),
        "live_end_to_end_research": "NOT MEASURED", "jev_comparison": "NOT MEASURED",
        "professional_acceptance": "OPEN", "publisher_independence": "NOT MEASURED"}
    atomic_write(destination, result)
    return result["measurements"]["groups"]["all"]


def audit(destination):
    results = []
    for product in ("pharma", "legal"):
        path = ROOT / f"docs/research-evaluations/2026-09-28-iterative-{product}-fixture.json"
        results.append({"receipt": path.relative_to(ROOT).as_posix(), "sha256": file_hash(path),
            **audit_fixture(json.loads(path.read_text()))})
    result = {"recorded_at": datetime.now(timezone.utc).isoformat(), "results": results,
        "passed": all(row["passed"] for row in results), "external_calls": 0}
    atomic_write(destination, result)
    return {"passed": result["passed"], "citation_links": sum(row["verified_citation_links"] for row in results)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "run-local", "report", "audit"))
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--credentials-file", type=Path)
    args = parser.parse_args()
    if args.stage == "prepare":
        result = prepare(args.cache, args.directory)
    elif args.stage == "run-local":
        from helvetic_lens.config import Settings
        from pydantic import SecretStr

        plan = load_plan(args.directory)
        credentials = json.loads(args.credentials_file.read_text())
        # Explicitly select only local Laya: no auto/fallback path can reach Jev.
        settings = Settings(_env_file=None, laya_base_url=LOCAL_URL,
            laya_api_key=SecretStr(credentials["LAYA_API_KEY"]), typesafe_api_key=SecretStr(""), search1api_api_key=SecretStr(""))
        engine = decision_engines.LayaEngine(settings)
        result = asyncio.run(collect(args.directory, plan, engine.choose))
    elif args.stage == "report":
        result = report(args.directory, args.output)
    else:
        result = audit(args.output)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
