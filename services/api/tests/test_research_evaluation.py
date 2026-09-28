"""Evaluation honesty, frozen inputs, bounded calls and real retained trace audit."""
import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest
from scripts import evaluate_iterative_research as runner

from helvetic_lens.decision_engines import Decision, DecisionUnavailable
from helvetic_lens.research_evaluation import audit_fixture, gate_metrics


def cases():
    return [{"id": str(i), "language": "english", "label": 1 if i < 4 else 0,
        "state": {"question": "Synthetic query", "branch": "Synthetic query", "title": "Fixture", "snippet": "Public synthetic text"}}
        for i in range(7)]


def answer(choice="relevant", model=runner.MODEL):
    return Decision("laya", model, choice, {"relevant": 1, "uncertain": 0, "unrelated": 0}, 1, 1, 1, None, None)


def plan(rows):
    return {"plan_sha256": "frozen-test-plan", "cases": rows}


def test_uncertain_failures_and_unrun_are_not_correct_negatives_or_truth():
    rows = [{"id": str(i), "outcome": outcome, "wall_ms": 2} for i, outcome in enumerate(
        ["relevant", "uncertain", "unrelated", "unavailable", "unrelated", "interrupted"])]
    result = gate_metrics(cases(), rows)
    group = result["groups"]["all"]
    assert group["positive_labels"] == 4 and group["negative_labels"] == 3
    assert group["positive_admission_rate"] == .25
    assert group["positive_harmful_rejection_rate"] == .25
    assert group["negative_rejection_rate"] == pytest.approx(1 / 3, abs=.000001)
    assert group["outcomes_by_label"]["0"]["not_run"] == 1
    assert group["outcomes_by_label"]["0"]["interrupted"] == 1
    assert result["estimated_cost_usd"] is None
    assert "accuracy" not in result and "truth" not in group


@pytest.mark.parametrize("change", ["duplicate", "foreign", "invalid_outcome", "nan"])
def test_invalid_measurements_fail_closed(change):
    rows = [{"id": "0", "outcome": "relevant", "wall_ms": 1}]
    if change == "duplicate":
        rows *= 2
    elif change == "foreign":
        rows[0]["id"] = "outside-plan"
    elif change == "invalid_outcome":
        rows[0]["outcome"] = "true"
    else:
        rows[0]["wall_ms"] = float("nan")
    with pytest.raises(ValueError):
        gate_metrics(cases(), rows)


def test_interrupted_call_is_reserved_and_not_repeated_on_resume(tmp_path, monkeypatch):
    rows = cases()[:3]
    expected = plan(rows)
    runner.atomic_write(tmp_path / "journal.json", {"plan_sha256": expected["plan_sha256"],
        "rows": [{"id": "0", "status": "started", "reserved_seconds": 12}]})
    monkeypatch.setattr(runner, "LIMITS", {"calls": 2, "seconds": 240, "per_call_seconds": 12})
    calls = []

    async def choose(state, instructions, criteria):
        calls.append(state)
        assert set(criteria) == {"relevant", "uncertain", "unrelated"}
        return answer()

    result = asyncio.run(runner.collect(tmp_path, expected, choose))
    assert result["attempts"] == 2 and len(calls) == 1
    assert result["reserved_or_elapsed_seconds"] >= 12
    saved = json.loads((tmp_path / "journal.json").read_text())
    assert saved["rows"][0]["outcome"] == "interrupted"
    assert saved["rows"][1]["outcome"] == "relevant"
    asyncio.run(runner.collect(tmp_path, expected, choose))
    assert len(calls) == 1


def test_cumulative_time_exhaustion_does_not_start_another_call(tmp_path, monkeypatch):
    expected = plan(cases()[:2])
    monkeypatch.setattr(runner, "LIMITS", {"calls": 120, "seconds": 12, "per_call_seconds": 12})
    runner.atomic_write(tmp_path / "journal.json", {"plan_sha256": expected["plan_sha256"],
        "rows": [{"id": "0", "status": "started", "reserved_seconds": 12}]})

    async def forbidden(*args):
        pytest.fail("Spent time must stop before any provider call")

    result = asyncio.run(runner.collect(tmp_path, expected, forbidden))
    assert result["attempts"] == 1
    assert result["reserved_or_elapsed_seconds"] == 12


def test_real_deadline_cancels_work_and_stops_at_total_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "LIMITS", {"calls": 120, "seconds": .04, "per_call_seconds": .02})
    calls = []

    async def slow(*args):
        calls.append(True)
        await asyncio.sleep(10)
        pytest.fail("The local deadline must cancel the provider wait")

    asyncio.run(runner.collect(tmp_path, plan(cases()), slow))
    state = json.loads((tmp_path / "journal.json").read_text())
    assert 1 <= len(calls) <= 2
    assert all(row["error"] == "timeout" for row in state["rows"])


def test_concurrent_runner_cannot_duplicate_model_calls(tmp_path):
    calls = []

    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()

        async def waiting(*args):
            calls.append(True)
            started.set()
            await release.wait()
            return answer()

        first = asyncio.create_task(runner.collect(tmp_path, plan(cases()[:1]), waiting))
        await started.wait()
        try:
            with pytest.raises(BlockingIOError):
                await runner.collect(tmp_path, plan(cases()[:1]), waiting)
        finally:
            release.set()
            await first

    asyncio.run(scenario())
    assert len(calls) == 1


@pytest.mark.parametrize("mode", ["unavailable", "timeout", "wrong_model"])
def test_failed_local_attempt_is_reported_without_retry_or_provider_fallback(tmp_path, mode):
    calls = []

    async def choose(*args):
        calls.append(True)
        if mode == "wrong_model":
            return answer(model="different-model")
        if mode == "timeout":
            raise TimeoutError()
        raise DecisionUnavailable("quota")

    expected = plan(cases()[:1])
    asyncio.run(runner.collect(tmp_path, expected, choose))
    asyncio.run(runner.collect(tmp_path, expected, choose))
    saved = json.loads((tmp_path / "journal.json").read_text())
    assert len(calls) == 1 and saved["rows"][0]["outcome"] == "unavailable"


def test_changed_plan_and_journal_identity_are_rejected(tmp_path):
    rows = cases()[:1]
    for row in rows:
        row["input_sha256"] = runner.fingerprint(row["state"])
    payload = {"protocol": runner.protocol(), "cases": rows}
    value = {**payload, "plan_sha256": runner.fingerprint(payload)}
    runner.atomic_write(tmp_path / "plan.json", value)
    assert runner.load_plan(tmp_path)["plan_sha256"] == value["plan_sha256"]
    changed = deepcopy(value)
    changed["cases"][0]["label"] = 0
    runner.atomic_write(tmp_path / "plan.json", changed)
    with pytest.raises(ValueError, match="Frozen plan changed"):
        runner.load_plan(tmp_path)
    runner.atomic_write(tmp_path / "journal.json", {"plan_sha256": "other-plan", "rows": []})
    with pytest.raises(ValueError, match="Journal"):
        runner.journal(tmp_path, value)


def test_cache_tampering_rejected_before_inference(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "english-topics-test.relevant.tsv").write_text("tampered")
    with pytest.raises(ValueError, match="pinned manifest"):
        runner.prepare(cache, tmp_path / "output")
    assert not (tmp_path / "output/plan.json").exists()


def fixture():
    root = Path(__file__).resolve().parents[3]
    return json.loads((root / "docs/research-evaluations/2026-09-28-iterative-pharma-fixture.json").read_text())


def test_actual_saved_worker_trace_passes_without_truth_or_publisher_claim():
    result = audit_fixture(fixture())
    assert result["passed"] and result["verified_citation_links"] > 10
    assert result["followups"][0]["same_claim_revision_changed"]
    assert result["followups"][0]["new_evidence_count"] == 1
    assert len(result["contradicted_claim_ids"]) == 1
    assert result["factual_accuracy"] is None and result["independent_publisher_count"] is None


@pytest.mark.parametrize("mutation,code", [
    ("quote", "invalid_citation"), ("foreign", "foreign_claim"),
    ("duplicate", "invalid_followup_answer"), ("missing", "invalid_followup_answer"),
    ("contradiction", "contradiction_not_preserved"),
])
def test_altered_foreign_and_duplicate_evidence_cannot_pass_audit(mutation, code):
    doc = fixture()
    run = doc["run"]
    if mutation == "quote":
        run["evidence"][0]["quote"] = "This sentence was never present in the captured source."
    elif mutation == "foreign":
        run["evidence"][0]["claim_id"] = "another-dossier"
    elif mutation == "duplicate":
        run["sources"][-1]["sha256"] = run["sources"][-2]["sha256"]
    elif mutation == "missing":
        run["research"]["questions"][-1]["answer_evidence_ids"] = ["missing"]
    else:
        run["claims"][0]["status"] = "SUPPORTED"
    result = audit_fixture(doc)
    assert not result["passed"]
    assert code in {row["code"] for row in result["errors"]}


def test_non_fixture_or_private_receipt_is_refused():
    doc = fixture()
    doc["not_live_provider_validation"] = False
    with pytest.raises(ValueError, match="fictional"):
        audit_fixture(doc)
    doc = fixture()
    doc["run"]["sources"][0]["kind"] = "saved_evidence"
    with pytest.raises(ValueError, match="Private"):
        audit_fixture(doc)
