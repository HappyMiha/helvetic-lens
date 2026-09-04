from types import SimpleNamespace

import pytest
from conftest import add_law, import_old

from helvetic_lens.ai_metrics import summarize_ai_triage_metrics


def record(
    *,
    status="succeeded",
    calls=1,
    queue=10,
    inference=100,
    limited=False,
    uses=1,
    accepted=True,
    tokens=50,
):
    validation = {"accepted": accepted, "events": [{"validation": "accepted"}]}
    return SimpleNamespace(
        status=status,
        use_count=uses,
        coverage={"limited": limited},
        provenance={},
        analysis_plan={
            "actual": {
                "provider_calls": calls,
                "queue_wait_ms": queue,
                "inference_duration_ms": inference,
                "token_counts": {"total_tokens": tokens},
                "validation": validation,
                "coverage_limited": limited,
            }
        },
    )


def test_ai_triage_metrics_report_latency_usage_validation_cache_and_decisions():
    metrics = summarize_ai_triage_metrics(
        [record(queue=20, inference=200, uses=3, tokens=80)],
        [record(status="failed", calls=2, queue=40, inference=400, limited=True, accepted=False)],
        [
            SimpleNamespace(diff={"metrics": {"overview_ms": 12.5}}),
            SimpleNamespace(diff={"metrics": {"overview_ms": 25.0}}),
        ],
        [
            SimpleNamespace(decision="accepted"),
            SimpleNamespace(decision="dismissed"),
            SimpleNamespace(decision="assigned"),
        ],
        [
            SimpleNamespace(
                decision="confirmed",
                review_duration_ms=15_000,
                evidence_opened=True,
                workflow_variant="inbox_list_v1",
            ),
            SimpleNamespace(
                decision="rejected",
                review_duration_ms=45_000,
                evidence_opened=False,
                workflow_variant="inbox_list_v1",
            ),
            SimpleNamespace(
                decision="annotated",
                review_duration_ms=None,
                evidence_opened=False,
                workflow_variant="inbox_list_v1",
            ),
        ],
    )

    assert metrics["records"] == {
        "total": 2,
        "impact": 1,
        "ask": 1,
        "succeeded": 1,
        "failed": 1,
        "limited": 1,
        "failed_rate": 0.5,
        "limited_rate": 0.5,
    }
    assert metrics["latency"]["deterministic_overview"] == {
        "samples": 2,
        "p50_ms": 12.5,
        "p95_ms": 25.0,
        "max_ms": 25.0,
    }
    assert metrics["latency"]["provider_queue"]["p95_ms"] == 40.0
    assert metrics["latency"]["inference"]["p95_ms"] == 400.0
    assert metrics["latency"]["time_to_first_useful_insight"]["source"] == "deterministic_overview"
    legacy = metrics["latency"]["time_to_first_useful_insight"]
    assert legacy["deprecated"] is True
    assert legacy["replacement"] == "latency.deterministic_overview"
    assert legacy["measurement_kind"] == "machine_processing_latency"
    for field, value in metrics["latency"]["deterministic_overview"].items():
        assert legacy[field] == value
    assert metrics["usage"] == {
        "provider_calls": 3,
        "token_counts": {"total_tokens": 130},
        "cache_hits": 2,
        "requests_including_reuse": 4,
        "cache_hit_rate": 0.5,
    }
    assert metrics["evidence"] == {
        "validation_samples": 2,
        "accepted": 1,
        "rejected": 1,
        "acceptance_rate": 0.5,
    }
    assert metrics["actions"]["accepted"] == 1
    assert metrics["actions"]["dismissed_or_not_applicable"] == 1
    assert metrics["actions"]["accept_rate"] == 0.3333
    assert metrics["relation_review"] == {
        "entries": 3,
        "decisions": 2,
        "annotations": 1,
        "duration": {
            "samples": 2,
            "p50_ms": 15_000.0,
            "p95_ms": 45_000.0,
            "max_ms": 45_000.0,
        },
        "measured_entries": 2,
        "evidence_opened": 1,
        "evidence_open_rate": 0.5,
        "workflow_variants": {"inbox_list_v1": 2},
        "by_variant": {
            "inbox_list_v1": {
                "measured_entries": 2,
                "decisions": 2,
                "duration": {
                    "samples": 2,
                    "p50_ms": 15_000.0,
                    "p95_ms": 45_000.0,
                    "max_ms": 45_000.0,
                },
                "evidence_opened": 1,
                "evidence_open_rate": 0.5,
            }
        },
    }


def test_empty_ai_triage_metrics_are_explicit_and_division_safe():
    metrics = summarize_ai_triage_metrics([], [], [], [])

    assert metrics["records"]["total"] == 0
    assert metrics["latency"]["deterministic_overview"]["p95_ms"] is None
    assert metrics["usage"]["cache_hit_rate"] == 0.0
    assert metrics["evidence"]["acceptance_rate"] is None
    assert metrics["actions"]["accept_rate"] is None
    assert metrics["relation_review"]["duration"]["p95_ms"] is None
    assert metrics["relation_review"]["evidence_open_rate"] is None
    assert metrics["relation_review"]["by_variant"] == {}


@pytest.mark.parametrize("unknown", [None, "12", True, -1, float("nan"), float("inf")])
def test_unknown_or_invalid_timings_do_not_become_zero_latency_samples(unknown):
    metrics = summarize_ai_triage_metrics(
        [record(queue=unknown, inference=unknown), record(queue=0, inference=12)], [],
        [SimpleNamespace(diff={"metrics": {"overview_ms": unknown}}),
         SimpleNamespace(diff={"metrics": {"overview_ms": 0}})], [],
    )
    overview = metrics["latency"]["deterministic_overview"]
    assert overview == {"samples": 1, "p50_ms": 0, "p95_ms": 0, "max_ms": 0}
    assert metrics["latency"]["provider_queue"]["samples"] == 1
    assert metrics["latency"]["provider_queue"]["p95_ms"] == 0
    assert metrics["latency"]["inference"]["samples"] == 1
    assert metrics["latency"]["inference"]["p95_ms"] == 12
    assert metrics["records"]["total"] == 2
    assert metrics["usage"]["provider_calls"] == 2


def test_relation_review_metrics_keep_experiment_variants_separate():
    reviews = [
        SimpleNamespace(
            decision="confirmed",
            review_duration_ms=40_000,
            evidence_opened=True,
            workflow_variant="inbox_list_v1",
        ),
        SimpleNamespace(
            decision="rejected",
            review_duration_ms=20_000,
            evidence_opened=False,
            workflow_variant="graph_review_v1",
        ),
        SimpleNamespace(
            decision="annotated",
            review_duration_ms=10_000,
            evidence_opened=True,
            workflow_variant="graph_review_v1",
        ),
    ]

    metrics = summarize_ai_triage_metrics([], [], [], [], reviews)["relation_review"]

    assert metrics["by_variant"]["inbox_list_v1"]["duration"]["p50_ms"] == 40_000
    assert metrics["by_variant"]["graph_review_v1"] == {
        "measured_entries": 2,
        "decisions": 1,
        "duration": {
            "samples": 1,
            "p50_ms": 20_000.0,
            "p95_ms": 20_000.0,
            "max_ms": 20_000.0,
        },
        "evidence_opened": 1,
        "evidence_open_rate": 0.5,
    }


def test_new_comparison_persists_time_to_deterministic_overview(harness):
    client, _, _, _ = harness
    law = add_law(client)
    old = import_old(client, law["id"])["version"]

    response = client.post(
        "/api/comparisons",
        json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]},
    )

    assert response.status_code == 201
    timing = response.json()["diff"]["metrics"]
    assert timing["overview_ms"] >= 0
    assert timing["measured_at"]
