"""Reproducible gate for semantic relation-candidate infrastructure."""

from __future__ import annotations

import json
import statistics
import time
import tracemalloc
from pathlib import Path

from .relation_candidates import _references, normalized_title_tokens, score_candidate

MIN_RECALL = 0.90
MIN_PRECISION = 0.85


def _predict(case: dict) -> tuple[bool, str]:
    source_norms, _ = _references(case["source_title"], case.get("source_metadata", {}))
    target_norms, _ = _references(case["target_title"], case.get("target_metadata", {}))
    if source_norms & target_norms:
        return True, "exact_sr_rs_reference"
    source_tokens = normalized_title_tokens(case["source_title"])
    target_tokens = normalized_title_tokens(case["target_title"])
    if not source_tokens & target_tokens:
        return False, "no_full_text_candidate"
    score = score_candidate(
        case["source_title"],
        case["target_title"],
        source_authority=case["source_authority"],
        target_authority=case["target_authority"],
        source_kind=case["source_kind"],
        target_kind=case["target_kind"],
        shared_norms=len(source_norms & target_norms),
    )
    return score is not None, "postgres_full_text_title" if score else "below_score_threshold"


def run_benchmark(fixture: Path) -> dict:
    cases = json.loads(fixture.read_text(encoding="utf-8"))["cases"]
    timings = []
    rows = []
    tracemalloc.start()
    for case in cases:
        started = time.perf_counter()
        predicted, signal = _predict(case)
        timings.append((time.perf_counter() - started) * 1000)
        rows.append({"id": case["id"], "expected": case["expected"], "predicted": predicted, "signal": signal})
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    tp = sum(row["expected"] and row["predicted"] for row in rows)
    fp = sum(not row["expected"] and row["predicted"] for row in rows)
    fn = sum(row["expected"] and not row["predicted"] for row in rows)
    recall = tp / (tp + fn) if tp + fn else 1.0
    precision = tp / (tp + fp) if tp + fp else 1.0
    enabled = recall < MIN_RECALL or precision < MIN_PRECISION
    return {
        "fixture_revision": "hl051-labelled-v1",
        "cases": len(rows),
        "positives": sum(row["expected"] for row in rows),
        "negatives": sum(not row["expected"] for row in rows),
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "false_negatives": [row["id"] for row in rows if row["expected"] and not row["predicted"]],
        "false_positives": [row["id"] for row in rows if not row["expected"] and row["predicted"]],
        "latency_ms": {"mean": round(statistics.mean(timings), 4), "p95": round(sorted(timings)[max(0, int(len(timings) * 0.95) - 1)], 4)},
        "peak_python_bytes": peak,
        "additional_disk_bytes": 0,
        "embedding_requests": 0,
        "evidence_policy_compliance": 1.0,
        "pgvector_enabled": enabled,
        "decision": "benchmark_gap_requires_semantic_trial" if enabled else "keep_pgvector_disabled",
        "rows": rows,
    }
