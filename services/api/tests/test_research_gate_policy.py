"""Conservative exclusion, blind selection and immutable bounded experiments."""
import asyncio
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import evaluate_iterative_research as runner
from scripts import evaluate_research_gate_policy as study

from helvetic_lens import product_research_gate
from helvetic_lens import research_gate_policy as policy
from helvetic_lens.decision_engines import Decision, DecisionUnavailable


def observation(identifier, choice, selected):
    return {"id": str(identifier), "model": policy.MODEL, "outcome": choice,
        "probabilities": {k: selected if k == choice else (1 - selected) / 2 for k in ("relevant", "uncertain", "unrelated")},
        "wall_ms": 1, "status": "completed", "reserved_seconds": 12}


def fixture():
    cases = [{"id": str(i), "query_id": "q" + str(i), "language": "english", "label": int(i < 2),
        "state": {"question": "Fictional question", "title": "Fixture"}} for i in range(10)]
    rows = [observation(0, "unrelated", .60), observation(1, "relevant", .90)]
    rows += [observation(i, "unrelated", .90) for i in range(2, 6)]
    rows += [observation(i, "uncertain", .80) for i in range(6, 10)]
    return cases, rows


@pytest.mark.parametrize("choice", ["relevant", "uncertain", "unrelated"])
def test_guard_can_only_defer_rejection_never_admit_an_uncertain_item(choice):
    row = observation(0, choice, .60)
    original = deepcopy(row)
    result = policy.guarded_observations([row], .65)[0]
    assert result["outcome"] == ("uncertain" if choice == "unrelated" else choice)
    assert row == original
    assert result["probabilities"] == row["probabilities"]


def test_exact_threshold_retains_rejection_and_does_not_use_provider_confidence():
    row = observation(0, "unrelated", .65)
    row["confidence"] = 0
    assert policy.guarded_observations([row], .65)[0]["outcome"] == "unrelated"


@pytest.mark.parametrize("fault", ["nan", "missing", "wrong_sum", "wrong_max", "wrong_model"])
def test_malformed_scores_and_unvalidated_models_cannot_enter_policy_measurements(fault):
    row = observation(0, "unrelated", .80)
    if fault == "nan":
        row["probabilities"]["unrelated"] = float("nan")
    elif fault == "missing":
        del row["probabilities"]["uncertain"]
    elif fault == "wrong_sum":
        row["probabilities"]["relevant"] = .90
    elif fault == "wrong_max":
        row["outcome"] = "relevant"
    else:
        row["model"] = "unvalidated"
    with pytest.raises((DecisionUnavailable, ValueError)):
        policy.guarded_observations([row], .65)


def test_development_selection_has_no_validation_input_and_uses_fixed_tie_break():
    cases, rows = fixture()
    result = policy.select_development(cases, rows)
    assert result["threshold"] == .65 and result["selected_from"] == "development_only"
    compared = policy.comparison(cases, rows, result["threshold"])
    assert compared["positive_rejections"] == 0
    assert compared["positive_rejections_baseline"] == 1
    assert compared["negative_rejections_retained"] == 4
    assert compared["extra_review_fraction"] == .1
    assert policy.promotion(compared)["passed"]
    for label in ("0", "1"):
        assert (compared["baseline"]["groups"]["all"]["outcomes_by_label"][label]["relevant"]
            == compared["guarded"]["groups"]["all"]["outcomes_by_label"][label]["relevant"])


def test_development_without_qualifying_policy_does_not_choose_one_anyway():
    cases, rows = fixture()
    rows[0] = observation(0, "unrelated", .99)
    assert policy.select_development(cases, rows)["threshold"] is None


@pytest.mark.parametrize("fault", ["not_run", "unavailable", "harmful", "burden", "no_change"])
def test_validation_failure_prevents_promotion_without_relabelling_uncertainty(fault):
    cases, rows = fixture()
    if fault == "not_run":
        rows = rows[:-1]
    elif fault == "unavailable":
        rows[-1]["outcome"] = "unavailable"
    elif fault == "harmful":
        rows[0] = observation(0, "unrelated", .99)
    elif fault == "burden":
        rows[2:6] = [observation(i, "unrelated", .60) for i in range(2, 6)]
    else:
        rows[0] = observation(0, "relevant", .90)
    result = policy.comparison(cases, rows, .65)
    assert not policy.promotion(result)["passed"]


def saved_study(tmp_path):
    cases, _ = fixture()
    plans = {}
    for stage, split, offset in (("development", "dev", 12), ("validation", "test", 42)):
        directory = tmp_path / stage
        directory.mkdir()
        selected = deepcopy(cases)
        for row in selected:
            row["query_id"] = stage + row["query_id"]
            row["input_sha256"] = runner.fingerprint(row["state"])
        payload = {"cases": selected, "sources": [], "protocol": runner.protocol(split=split, offset=offset, call_limit=study.LIMITS["per_stage"][stage]["calls"])}
        plan = {**payload, "plan_sha256": runner.fingerprint(payload)}
        runner.atomic_write(directory / "plan.json", plan)
        plans[stage] = {"plan_sha256": plan["plan_sha256"]}
    return study.freeze(tmp_path / "study.json", {"policy": policy.VERSION,
        "policy_sha256": runner.file_hash(Path(policy.__file__)), "thresholds": list(policy.THRESHOLDS),
        "plans": plans, "limits": study.LIMITS})


def test_validation_cannot_call_any_model_until_selection_is_frozen(tmp_path):
    saved_study(tmp_path)

    async def forbidden(*args):
        pytest.fail("Validation must not run before development selection")

    with pytest.raises(FileNotFoundError):
        asyncio.run(study.collect(tmp_path, "validation", forbidden))
    assert not (tmp_path / "validation/journal.json").exists()


def test_selection_is_immutable_and_bound_to_exact_development_journal(tmp_path):
    saved_study(tmp_path)
    _, plans = study.load_study(tmp_path)
    _, rows = fixture()
    path = tmp_path / "development/journal.json"
    state = {"plan_sha256": plans["development"]["plan_sha256"], "rows": rows}
    runner.atomic_write(path, state)
    assert study.select(tmp_path)["threshold"] == .65
    with pytest.raises(ValueError, match="already exists"):
        study.select(tmp_path)
    state["rows"][0]["outcome"] = "relevant"
    runner.atomic_write(path, state)
    study_record, _ = study.load_study(tmp_path)
    with pytest.raises(ValueError, match="development"):
        study.load_selection(tmp_path, study_record)


def test_concurrent_development_cannot_freeze_selection_or_start_validation(tmp_path):
    saved_study(tmp_path)

    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()

        async def choose(*args):
            started.set()
            await release.wait()
            return Decision("laya", policy.MODEL, "relevant", {"relevant": 1, "uncertain": 0, "unrelated": 0}, 1, 1, 1, None, None)

        task = asyncio.create_task(study.collect(tmp_path, "development", choose))
        await started.wait()
        try:
            with pytest.raises(BlockingIOError):
                study.select(tmp_path)
            with pytest.raises(BlockingIOError):
                await study.collect(tmp_path, "validation", choose)
        finally:
            release.set()
            await task

    asyncio.run(scenario())
    assert len(json.loads((tmp_path / "development/journal.json").read_text())["rows"]) == 10


def test_policy_change_or_hash_tampering_prevents_resuming(tmp_path):
    saved_study(tmp_path)
    path = tmp_path / "study.json"
    value = json.loads(path.read_text())
    value["thresholds"] = [.10]
    runner.atomic_write(path, value)
    with pytest.raises(ValueError, match="changed"):
        study.load_study(tmp_path)


def test_failed_development_keeps_validation_unopened_and_reports_no_raw_inputs(tmp_path):
    saved_study(tmp_path)
    _, plans = study.load_study(tmp_path)
    _, rows = fixture()
    rows[0] = observation(0, "unrelated", .99)
    runner.atomic_write(tmp_path / "development/journal.json", {
        "plan_sha256": plans["development"]["plan_sha256"], "rows": rows})
    assert study.select(tmp_path)["threshold"] is None

    async def forbidden(*args):
        pytest.fail("No validation calls after failed development")

    with pytest.raises(ValueError, match="unopened"):
        asyncio.run(study.collect(tmp_path, "validation", forbidden))
    output = tmp_path / "report.json"
    result = study.report(tmp_path, output)
    report = json.loads(output.read_text())
    assert result["calls"]["local_attempts"] == 10 and not result["promotion"]["passed"]
    assert report["validation"] == {"status": "not_run_development_gate_failed", "planned_cases": 10}
    assert "Fictional question" not in output.read_text()
    assert not (tmp_path / "validation/journal.json").exists()


def test_report_can_read_historical_gate_but_inference_cannot_resume_with_changed_code(tmp_path, monkeypatch):
    saved_study(tmp_path)
    original = runner.protocol

    def changed(**kwargs):
        return {**original(**kwargs), "gate_sha256": "different-code"}

    monkeypatch.setattr(runner, "protocol", changed)
    with pytest.raises(ValueError, match="changed"):
        study.load_study(tmp_path)
    _, plans = study.load_study(tmp_path, verify_runtime=False)
    assert plans["development"]["protocol"]["gate_sha256"] != "different-code"


def test_resigned_plans_with_overlapping_query_identity_are_still_refused(tmp_path):
    saved_study(tmp_path)
    path = tmp_path / "validation/plan.json"
    plan = json.loads(path.read_text())
    plan["cases"][0]["query_id"] = "developmentq0"
    plan["plan_sha256"] = runner.fingerprint({k: v for k, v in plan.items() if k != "plan_sha256"})
    runner.atomic_write(path, plan)
    path = tmp_path / "study.json"
    record = json.loads(path.read_text())
    record["plans"]["validation"]["plan_sha256"] = plan["plan_sha256"]
    record["sha256"] = runner.fingerprint({k: v for k, v in record.items() if k != "sha256"})
    runner.atomic_write(path, record)
    with pytest.raises(ValueError, match="Overlapping"):
        study.load_study(tmp_path)


def test_sampling_rejects_unknown_splits_and_does_not_change_legacy_defaults():
    assert runner.protocol()["sampling"]["offset"] == 40
    for split, offset in (("train", 0), ("dev", -1), ("test", True)):
        with pytest.raises(ValueError, match="sampling"):
            runner.protocol(split=split, offset=offset)
    for limit in (0, True, 122):
        with pytest.raises(ValueError, match="budget"):
            runner.protocol(call_limit=limit)


@pytest.mark.parametrize("engine", ["laya", "jev"])
def test_production_records_raw_scores_but_does_not_activate_failed_experimental_guard(monkeypatch, engine):
    scores = {"relevant": .1, "uncertain": .15, "unrelated": .75}

    class FakeEngine:
        async def choose(self, state, instructions, criteria):
            assert state == {"question": "Public question", "branch": "Public branch", "title": "Public title", "snippet": "Public snippet"}
            return Decision(engine, policy.MODEL if engine == "laya" else "fixture-jev", "unrelated", scores, .99, .75, 2, 30, 1)

    monkeypatch.setattr(product_research_gate.decision, "engines", lambda settings: {engine: FakeEngine()})
    settings = SimpleNamespace(jev_input_usd_per_million=None, jev_output_usd_per_million=None)
    result = asyncio.run(product_research_gate.evaluate(settings, "Public question", "Public branch",
        {"title": "Public title", "summary": "Public snippet"}, "laya_first" if engine == "laya" else "jev_first"))
    assert result["verdict"] == result["raw_verdict"] == "unrelated"
    assert result["probabilities"] == scores and result["selected_probability"] == .75
    assert result["confidence"] == .99 and result["policy_version"] == "topical-snippet/v1"
    assert "uncalibrated" in result["basis"]
    assert result["usage"]["estimated_cost_usd"] is None
