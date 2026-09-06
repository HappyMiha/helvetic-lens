import json
import subprocess
import sys
from pathlib import Path

import pytest
from semantic_matching_fixtures import matching_input, package, write_json

from helvetic_lens.semantic_matching_baseline import predict_one, run_baseline
from helvetic_lens.semantic_matching_eval import Labels, Predictions, evaluate, load_contract, load_dataset

ROOT = Path(__file__).resolve().parents[3]


def evaluate_package(root):
    dataset, dataset_hash, artifacts = load_dataset(root / "dataset.json", root)
    labels, labels_hash = load_contract(root / "labels.json", Labels)
    predictions, predictions_hash = load_contract(root / "predictions.json", Predictions)
    return evaluate(
        dataset,
        dataset_hash,
        artifacts,
        labels,
        predictions,
        labels_hash=labels_hash,
        predictions_hash=predictions_hash,
    )


def test_synthetic_perfect_scores_cannot_become_independent_acceptance(tmp_path):
    package(tmp_path, count=200)
    result = evaluate_package(tmp_path)
    assert result["metrics"]["precision"] == {"numerator": 100, "denominator": 100, "value": 1.0}
    assert result["metrics"]["recall"]["value"] == 1.0
    assert result["readiness_blockers"] == ["synthetic_dataset_not_independent_evidence"]
    assert not result["matching_target_met"] and not result["explanation_capability_approved"]
    assert result["coverage"]["scored_pairs"] == 200
    assert len(result["strata"]["locale"]) == 5 and len(result["strata"]["source_type"]) == 5
    assert result["strata"]["source_type"]["news"]["cases"] == 0
    assert result["strata"]["source_type"]["news"]["recall"]["value"] is None
    assert "factual_entailment" in result["unmeasured"]


def test_metrics_preserve_denominators_failures_missing_predictions_and_labels(tmp_path):
    _, gold, run = package(tmp_path)
    run["rows"][0].update(status="error", relevant=None)
    run["rows"][1]["relevant"] = True
    run["rows"] = run["rows"][:4]
    gold["labels"] = gold["labels"][:5]
    write_json(tmp_path / "labels.json", gold)
    write_json(tmp_path / "predictions.json", run)
    result = evaluate_package(tmp_path)
    assert result["metrics"]["precision"] == {"numerator": 1, "denominator": 2, "value": 0.5}
    assert result["metrics"]["recall"]["denominator"] == 3
    assert result["metrics"]["false_negative_ids"] == ["case-0000", "case-0004"]
    assert result["metrics"]["false_positive_ids"] == ["case-0001"]
    assert result["pending_reviews"] == {"case-0005": ["unlabelled"]}
    assert result["coverage"]["partition_cases"] == 6 and result["coverage"]["scored_pairs"] == 5
    assert "prediction_run_incomplete" in result["readiness_blockers"]


def test_empty_denominators_are_unmeasured_not_perfect(tmp_path):
    _, gold, run = package(tmp_path)
    for label in gold["labels"]:
        for vote in label["votes"]:
            vote["relevant"] = False
    for row in run["rows"]:
        row["relevant"] = False
    write_json(tmp_path / "labels.json", gold)
    write_json(tmp_path / "predictions.json", run)
    report = evaluate_package(tmp_path)
    assert report["metrics"]["precision"]["value"] is None
    assert report["metrics"]["recall"]["value"] is None
    assert len(report["target_failures"]) == 2


def test_disagreement_retained_and_only_distinct_adjudicator_resolves(tmp_path):
    _, gold, _ = package(tmp_path)
    label = gold["labels"][0]
    label["votes"][1]["relevant"] = False
    write_json(tmp_path / "labels.json", gold)
    before = evaluate_package(tmp_path)
    assert before["pending_reviews"][label["case_id"]] == ["unresolved_disagreement"]
    assert len(before["disagreements"]) == 1 and before["coverage"]["scored_pairs"] == 5
    label["adjudication"] = {**label["votes"][0], "reviewer_id": "reviewer-c"}
    write_json(tmp_path / "labels.json", gold)
    after = evaluate_package(tmp_path)
    assert not after["pending_reviews"] and after["coverage"]["scored_pairs"] == 6
    assert after["disagreements"][0]["votes"] == before["disagreements"][0]["votes"]
    label["adjudication"]["reviewer_id"] = "reviewer-a"
    write_json(tmp_path / "labels.json", gold)
    with pytest.raises(ValueError):
        evaluate_package(tmp_path)


@pytest.mark.parametrize("fault", ["one_vote", "self_review", "language", "not_independent"])
def test_unreviewed_labels_remain_pending_without_changing_the_gold(tmp_path, fault):
    dataset, gold, _ = package(tmp_path)
    if fault == "one_vote":
        gold["labels"][0]["votes"].pop()
    if fault == "self_review":
        gold["reviewers"][0]["id"] = dataset["authors"][0]
        gold["labels"][0]["votes"][0]["reviewer_id"] = dataset["authors"][0]
    if fault == "language":
        gold["reviewers"][0]["fluent_locales"] = ["en-CH"]
    if fault == "not_independent":
        gold["reviewers"][0]["independent_of_system"] = False
    if fault == "self_review":
        for label in gold["labels"][1:]:
            label["votes"][0]["reviewer_id"] = dataset["authors"][0]
    write_json(tmp_path / "labels.json", gold)
    frozen = (tmp_path / "labels.json").read_bytes()
    result = evaluate_package(tmp_path)
    assert "case-0000" in result["pending_reviews"] and not result["matching_target_met"]
    assert (tmp_path / "labels.json").read_bytes() == frozen


@pytest.mark.parametrize(
    "fault",
    [
        "input_hash",
        "source_hash",
        "dataset_binding",
        "quote",
        "wrong_case",
        "prediction_input",
        "duplicate_prediction",
        "nonfinite",
        "boolean_decision",
        "chronology",
        "extra_field",
    ],
)
def test_corrupt_or_mismatched_evidence_cannot_be_evaluated(tmp_path, fault):
    dataset, gold, run = package(tmp_path)
    if fault == "input_hash":
        (tmp_path / dataset["cases"][0]["input"]["path"]).write_text("{}")
    if fault == "source_hash":
        (tmp_path / dataset["cases"][0]["sources"][0]["artifact"]["path"]).write_text("Changed source")
    if fault == "dataset_binding":
        gold["dataset_sha256"] = "0" * 64
    if fault == "quote":
        gold["labels"][0]["votes"][0]["citations"][0]["quote"] = "Invented exact source quote."
    if fault == "wrong_case":
        run["rows"][0]["case_id"] = "missing-case"
    if fault == "prediction_input":
        run["rows"][0]["input_sha256"] = "0" * 64
    if fault == "duplicate_prediction":
        run["rows"].append(run["rows"][0])
    if fault == "nonfinite":
        run["rows"][0]["latency_ms"] = float("nan")
    if fault == "boolean_decision":
        run["rows"][0]["relevant"] = 1
    if fault == "chronology":
        run["created_at"] = "2026-08-01T10:00:00Z"
    if fault == "extra_field":
        run["semantic_quality_passed"] = True
    write_json(tmp_path / "labels.json", gold)
    write_json(tmp_path / "predictions.json", run)
    with pytest.raises(ValueError):
        evaluate_package(tmp_path)


@pytest.mark.parametrize("leak", ["family", "source", "input"])
def test_frozen_split_rejects_shared_families_and_exact_artifacts(tmp_path, leak):
    dataset, _, _ = package(tmp_path)
    first, second = dataset["cases"][:2]
    first["split"] = "development"
    if leak == "family":
        second["family"] = first["family"]
    if leak == "source":
        second["sources"] = first["sources"]
    if leak == "input":
        second["input"] = first["input"]
    write_json(tmp_path / "dataset.json", dataset)
    with pytest.raises(ValueError):
        load_dataset(tmp_path / "dataset.json", tmp_path)


@pytest.mark.parametrize(
    "path", ["../outside.json", "/outside.json", "C:/outside.json", "inputs\\bad.json", "inputs//bad.json"]
)
def test_artifact_paths_cannot_escape_package(tmp_path, path):
    dataset, _, _ = package(tmp_path)
    dataset["cases"][0]["input"]["path"] = path
    write_json(tmp_path / "dataset.json", dataset)
    with pytest.raises(ValueError):
        load_dataset(tmp_path / "dataset.json", tmp_path)


@pytest.mark.parametrize(
    "override,expected",
    [
        ({}, True),
        ({"exclusions": ["retention"]}, False),
        ({"languages": ["fr"]}, False),
        ({"concepts": ["not-mentioned"]}, False),
    ],
)
def test_baseline_uses_real_production_plan_and_scorer(override, expected):
    value = matching_input()
    value["plan"].update(override)
    decision, _ = predict_one(json.dumps(value).encode())
    assert decision is expected
    # A later case starts without previous identifiers/source packs.
    assert predict_one(json.dumps(matching_input(1, False)).encode())[0] is False


def test_baseline_matches_normalized_official_references_and_no_property_names():
    value = matching_input(1, False)
    value["plan"]["concepts"] = ["RS 141.0"]
    value["identifiers"] = [{"scheme": "sr_rs", "value": "141.0", "normalized_value": "141.0"}]
    assert "official_identifier" in predict_one(json.dumps(value).encode())[1]
    value["plan"]["concepts"] = ["jurisdiction"]
    assert predict_one(json.dumps(value).encode())[0] is False


def test_baseline_never_reads_gold_and_keeps_input_failures_explicit(tmp_path):
    dataset, _, _ = package(tmp_path)
    value = matching_input()
    value["plan"]["source_pack_ids"] = ["missing-pack"]
    dataset["cases"][0]["input"] = write_json(tmp_path / "input-0.json", value)
    write_json(tmp_path / "dataset.json", dataset)
    (tmp_path / "labels.json").unlink()
    data, sha, artifacts = load_dataset(tmp_path / "dataset.json", tmp_path)
    result = run_baseline(
        data,
        sha,
        artifacts,
        "held_out",
        {"system_revision": "a" * 40, "implementation_sha256": "b" * 64, "working_tree_dirty": True},
    )
    assert result["rows"][0]["status"] == "error" and result["rows"][0]["relevant"] is None
    assert result["rows"][1]["status"] == "ok" and result["rows"][1]["relevant"] is False
    assert result["rows"][2]["relevant"] is True


def test_cli_evaluates_without_overwriting_evidence_or_claiming_promotion(tmp_path):
    package(tmp_path)
    command = [
        sys.executable,
        str(ROOT / "scripts/evaluate_semantic_matching.py"),
        "evaluate",
        "--dataset",
        str(tmp_path / "dataset.json"),
        "--root",
        str(tmp_path),
        "--labels",
        str(tmp_path / "labels.json"),
        "--predictions",
        str(tmp_path / "predictions.json"),
        "--output",
        str(tmp_path / "report.json"),
    ]
    response = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, timeout=30)
    assert response.returncode == 1, response.stderr
    assert not json.loads((tmp_path / "report.json").read_text())["matching_target_met"]
    before = (tmp_path / "report.json").read_bytes()
    again = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, timeout=30)
    assert again.returncode == 2 and (tmp_path / "report.json").read_bytes() == before
    assert "invalid_evaluation_package" in again.stderr


def test_gate_calculus_with_synthetic_attestations_is_not_model_approval(tmp_path):
    # Deliberately synthetic declarations exercise the acceptance calculation,
    # not reviewer authenticity. This temporary result is never published as gold.
    _, _, run = package(tmp_path, count=200, provenance="public_source")
    passing = evaluate_package(tmp_path)
    assert passing["matching_target_met"] and not passing["explanation_capability_approved"]
    assert passing["independence_is_attestation_not_verified_identity"]
    for row in run["rows"][:40]:
        if row["relevant"] is False:
            row["relevant"] = True
    write_json(tmp_path / "predictions.json", run)
    failing = evaluate_package(tmp_path)
    assert not failing["readiness_blockers"]
    assert failing["target_failures"] == ["precision_below_0.85_or_unmeasured"]
    assert len(failing["metrics"]["false_positive_ids"]) == 20
    run["working_tree_dirty"] = True
    write_json(tmp_path / "predictions.json", run)
    assert "prediction_implementation_not_clean_revision" in evaluate_package(tmp_path)["readiness_blockers"]


def test_duplicate_json_and_read_budgets_are_rejected(tmp_path, monkeypatch):
    from helvetic_lens import semantic_matching_eval as evaluator

    package(tmp_path)
    raw = (tmp_path / "predictions.json").read_text()
    (tmp_path / "predictions.json").write_text(raw.replace('"run_id":', '"run_id": "duplicate", "run_id":'))
    with pytest.raises(ValueError):
        evaluate_package(tmp_path)
    monkeypatch.setattr(evaluator, "MAX_PACKAGE_BYTES", 1)
    with pytest.raises(ValueError):
        evaluator.load_dataset(tmp_path / "dataset.json", tmp_path)
    monkeypatch.setattr(evaluator, "MAX_FILE_BYTES", 1)
    with pytest.raises(ValueError):
        evaluator.read_bounded(tmp_path / "dataset.json")


def test_baseline_has_no_socket_or_external_database_access(monkeypatch):
    import socket

    def forbidden(*args, **kwargs):
        raise AssertionError("Offline evaluation attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused.invalid/not_allowed")
    assert predict_one(json.dumps(matching_input()).encode())[0]


def test_cli_schema_export_and_checked_in_unreviewed_walkthrough(tmp_path):
    command = [sys.executable, str(ROOT / "scripts/evaluate_semantic_matching.py")]
    schema = subprocess.run([*command, "schemas"], capture_output=True, text=True, cwd=ROOT, timeout=30)
    assert schema.returncode == 0, schema.stderr
    assert set(json.loads(schema.stdout)["schemas"]) == {"Dataset", "Labels", "Predictions", "MatchingInput"}
    example = ROOT / "demo/semantic-matching-example"
    output = tmp_path / "baseline.json"
    baseline = subprocess.run(
        [
            *command,
            "baseline",
            "--dataset",
            str(example / "dataset.json"),
            "--root",
            str(example),
            "--split",
            "held_out",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=30,
    )
    assert baseline.returncode == 0, baseline.stderr
    data = json.loads(output.read_text())
    assert len(data["rows"]) == 2 and all(row["status"] == "ok" for row in data["rows"])
    assert {row["relevant"] for row in data["rows"]} == {True, False}
    evaluation = subprocess.run(
        [
            *command,
            "evaluate",
            "--dataset",
            str(example / "dataset.json"),
            "--root",
            str(example),
            "--labels",
            str(example / "labels.json"),
            "--predictions",
            str(output),
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=30,
    )
    assert evaluation.returncode == 1, evaluation.stderr
    report = json.loads(evaluation.stdout)
    assert report["coverage"]["scored_pairs"] == 0 and report["metrics"]["recall"]["value"] is None
    assert "gold_reviews_pending" in report["readiness_blockers"]


def test_frozen_example_survives_windows_git_checkout(tmp_path):
    import shutil

    checkout = tmp_path / "checkout"
    checkout.mkdir()
    shutil.copy(ROOT / ".gitattributes", checkout / ".gitattributes")
    example = Path("demo/semantic-matching-example")
    shutil.copytree(ROOT / example, checkout / example)

    def git(*args):
        return subprocess.run(["git", *args], cwd=checkout, check=True, capture_output=True, timeout=30)

    git("init")
    git("config", "core.autocrlf", "true")
    git("add", ".gitattributes", example.as_posix())
    exported = tmp_path / "exported"
    git("checkout-index", "--all", "--prefix=" + exported.as_posix() + "/")
    frozen = exported / example
    dataset, dataset_hash, artifacts = load_dataset(frozen / "dataset.json", frozen)
    labels, _ = load_contract(frozen / "labels.json", Labels)
    assert labels.dataset_sha256 == dataset_hash
    assert len(dataset.cases) == 6 and artifacts
    for source in (ROOT / example).iterdir():
        if source.suffix in {".json", ".txt"}:
            assert (frozen / source.name).read_bytes() == source.read_bytes()
