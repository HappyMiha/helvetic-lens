from pathlib import Path

from helvetic_lens.candidate_benchmark import run_benchmark


def test_labelled_candidate_gate_keeps_pgvector_disabled():
    fixture = Path(__file__).resolve().parents[3] / "demo" / "relation-candidate-benchmark.json"
    result = run_benchmark(fixture)
    assert result["recall"] >= 0.90
    assert result["precision"] >= 0.85
    assert result["false_negatives"] == []
    assert result["evidence_policy_compliance"] == 1.0
    assert result["additional_disk_bytes"] == 0
    assert result["pgvector_enabled"] is False
