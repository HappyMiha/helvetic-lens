from pathlib import Path

from helvetic_lens.candidate_benchmark import run_benchmark


def test_labelled_candidate_gate_keeps_pgvector_disabled():
    fixture = Path(__file__).resolve().parents[3] / "demo" / "relation-candidate-benchmark.json"
    result = run_benchmark(fixture)
    assert result["recall"] >= 0.90
    assert result["precision"] >= 0.85
    assert result["false_negatives"] == []
    assert result["evidence_policy_compliance"] is None
    assert result["independent_quality_review"] == "not_performed"
    assert result["validation_kind"] == "unreviewed_title_regression"
    assert result["additional_disk_bytes"] == 0
    assert result["pgvector_enabled"] is False


def test_empty_legacy_fixture_does_not_invent_perfect_quality_or_enable_embeddings(tmp_path):
    fixture = tmp_path / "empty.json"
    fixture.write_text('{"cases": []}')
    result = run_benchmark(fixture)
    assert result["recall"] is None and result["precision"] is None
    assert result["latency_ms"] == {"mean": None, "p95": None}
    assert result["semantic_trial_recommended"] and not result["pgvector_enabled"]
    assert result["evidence_policy_compliance"] is None
