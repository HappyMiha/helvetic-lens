"""Bounded aggregate metrics for the local-first AI review workflow."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any


def _number(value: Any) -> float:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else 0.0


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return round(ordered[index], 2)


def _latency(values: list[float]) -> dict[str, float | int | None]:
    return {
        "samples": len(values),
        "p50_ms": _percentile(values, 0.50),
        "p95_ms": _percentile(values, 0.95),
        "max_ms": round(max(values), 2) if values else None,
    }


def summarize_ai_triage_metrics(
    analyses: Iterable[Any],
    questions: Iterable[Any],
    comparisons: Iterable[Any],
    decisions: Iterable[Any],
    relation_reviews: Iterable[Any] = (),
) -> dict[str, Any]:
    impacts = list(analyses)
    asks = list(questions)
    records = [*impacts, *asks]
    comparison_records = list(comparisons)
    decision_records = list(decisions)
    review_records = list(relation_reviews)

    queue_waits: list[float] = []
    inference_times: list[float] = []
    provider_calls = 0
    token_counts: dict[str, int] = {}
    validation_samples = 0
    validation_accepted = 0
    limited = 0
    failed = 0
    succeeded = 0
    cache_hits = 0

    for record in records:
        plan = getattr(record, "analysis_plan", None) or {}
        provenance = getattr(record, "provenance", None) or {}
        coverage = getattr(record, "coverage", None) or {}
        actual = plan.get("actual") or {}
        calls = int(actual.get("provider_calls", provenance.get("provider_calls", 0)) or 0)
        provider_calls += calls
        if calls:
            queue_waits.append(_number(actual.get("queue_wait_ms", provenance.get("queue_wait_ms"))))
            inference_times.append(
                _number(actual.get("inference_duration_ms", provenance.get("inference_duration_ms")))
            )
        for key, value in (actual.get("token_counts") or provenance.get("token_counts") or {}).items():
            if isinstance(value, int) and not isinstance(value, bool):
                token_counts[key] = token_counts.get(key, 0) + value
        validation = actual.get("validation") or provenance.get("validation") or {}
        if validation.get("events"):
            validation_samples += 1
            validation_accepted += int(validation.get("accepted") is True)
        limited += int(bool(coverage.get("limited") or actual.get("coverage_limited")))
        failed += int(getattr(record, "status", None) == "failed")
        succeeded += int(getattr(record, "status", None) == "succeeded")
        cache_hits += max(0, int(getattr(record, "use_count", 1) or 1) - 1)

    overview_times = [
        _number(((getattr(comparison, "diff", None) or {}).get("metrics") or {}).get("overview_ms"))
        for comparison in comparison_records
        if ((getattr(comparison, "diff", None) or {}).get("metrics") or {}).get("overview_ms")
        is not None
    ]
    requests = len(records) + cache_hits
    accepted = sum(decision.decision == "accepted" for decision in decision_records)
    dismissed = sum(
        decision.decision in {"dismissed", "not_applicable"} for decision in decision_records
    )
    decisive_reviews = [
        review for review in review_records if review.decision in {"confirmed", "rejected"}
    ]
    review_durations = [
        float(review.review_duration_ms)
        for review in decisive_reviews
        if review.review_duration_ms is not None
    ]
    measured_reviews = [
        review for review in review_records if review.review_duration_ms is not None
    ]
    workflow_variants: dict[str, int] = {}
    for review in measured_reviews:
        variant = review.workflow_variant or "unknown"
        workflow_variants[variant] = workflow_variants.get(variant, 0) + 1
    evidence_opened = sum(bool(review.evidence_opened) for review in measured_reviews)
    variant_metrics = {}
    for variant in sorted(workflow_variants):
        variant_measured = [
            review
            for review in measured_reviews
            if (review.workflow_variant or "unknown") == variant
        ]
        variant_decisions = [
            review
            for review in variant_measured
            if review.decision in {"confirmed", "rejected"}
        ]
        variant_durations = [
            float(review.review_duration_ms)
            for review in variant_decisions
            if review.review_duration_ms is not None
        ]
        variant_evidence_opened = sum(bool(review.evidence_opened) for review in variant_measured)
        variant_metrics[variant] = {
            "measured_entries": len(variant_measured),
            "decisions": len(variant_decisions),
            "duration": _latency(variant_durations),
            "evidence_opened": variant_evidence_opened,
            "evidence_open_rate": round(
                variant_evidence_opened / len(variant_measured), 4
            ),
        }

    return {
        "records": {
            "total": len(records),
            "impact": len(impacts),
            "ask": len(asks),
            "succeeded": succeeded,
            "failed": failed,
            "limited": limited,
            "failed_rate": round(failed / len(records), 4) if records else 0.0,
            "limited_rate": round(limited / len(records), 4) if records else 0.0,
        },
        "latency": {
            "deterministic_overview": _latency(overview_times),
            "time_to_first_useful_insight": {
                **_latency(overview_times),
                "source": "deterministic_overview",
            },
            "provider_queue": _latency(queue_waits),
            "inference": _latency(inference_times),
        },
        "usage": {
            "provider_calls": provider_calls,
            "token_counts": token_counts,
            "cache_hits": cache_hits,
            "requests_including_reuse": requests,
            "cache_hit_rate": round(cache_hits / requests, 4) if requests else 0.0,
        },
        "evidence": {
            "validation_samples": validation_samples,
            "accepted": validation_accepted,
            "rejected": validation_samples - validation_accepted,
            "acceptance_rate": (
                round(validation_accepted / validation_samples, 4) if validation_samples else None
            ),
        },
        "actions": {
            "decision_events": len(decision_records),
            "accepted": accepted,
            "dismissed_or_not_applicable": dismissed,
            "accept_rate": round(accepted / len(decision_records), 4) if decision_records else None,
            "dismiss_rate": round(dismissed / len(decision_records), 4) if decision_records else None,
        },
        "relation_review": {
            "entries": len(review_records),
            "decisions": len(decisive_reviews),
            "annotations": sum(review.decision == "annotated" for review in review_records),
            "duration": _latency(review_durations),
            "measured_entries": len(measured_reviews),
            "evidence_opened": evidence_opened,
            "evidence_open_rate": (
                round(evidence_opened / len(measured_reviews), 4)
                if measured_reviews
                else None
            ),
            "workflow_variants": workflow_variants,
            "by_variant": variant_metrics,
        },
    }
