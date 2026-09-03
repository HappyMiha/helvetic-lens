from types import SimpleNamespace

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


def test_empty_ai_triage_metrics_are_explicit_and_division_safe():
    metrics = summarize_ai_triage_metrics([], [], [], [])

    assert metrics["records"]["total"] == 0
    assert metrics["latency"]["deterministic_overview"]["p95_ms"] is None
    assert metrics["usage"]["cache_hit_rate"] == 0.0
    assert metrics["evidence"]["acceptance_rate"] is None
    assert metrics["actions"]["accept_rate"] is None


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
