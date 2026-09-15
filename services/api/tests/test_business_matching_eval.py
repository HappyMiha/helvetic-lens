"""Synthetic packages test accounting only; these are not independent labels."""

import json
import socket
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from helvetic_lens import business_matching_eval as business
from helvetic_lens import semantic_matching_eval as common

ROOT = Path(__file__).resolve().parents[3]


def write(root, name, data):
    raw = (json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n").encode()
    (root / name).write_bytes(raw)
    return {"path": name, "sha256": common.digest(raw)}


def package(root, count=6):
    cases, gold, outputs, audits = [], [], [], []
    for index in range(count):
        identifier, positive = f"pair-{index}", index % 2 == 0
        text = f"Synthetic evidence for candidate {index}, never an independent human label."
        source = write(root, f"source-{index}.json", {"title": text, "other": "Unrelated source field."})
        permission = write(root, f"permission-{index}.json", {
            "schema_version": "mv2.evaluation-permission.v1", "snapshot_sha256": source["sha256"],
            "permitted_fields": ["title"], "evaluation_allowed": True,
            "reference": "Synthetic permission attestation for a unit test only",
            "reviewed_at": "2026-09-01T00:00:00Z", "valid_until": "2026-10-01T00:00:00Z"})
        input_ref = write(root, f"input-{index}.json", {"candidate": index, "profile": "Synthetic only"})
        cases.append({"id": identifier, "family": identifier, "split": "held_out",
            "locale": common.LOCALES[index % 5], "source_type": business.BUSINESSES[index % 3],
            "features": ["negative"] if not positive else [], "release_critical": True,
            "input": input_ref, "sources": [{"id": "official", "public_url": "https://example.invalid/test",
                "artifact": source, "permission": permission}]})
        citation = {"source_id": "official", "field": "title", "quote": text}
        vote = {"reviewer_id": "gold-a", "relevant": positive,
            "rationale": "Synthetic rationale to exercise the evaluator", "citations": [citation]}
        gold.append({"case_id": identifier, "votes": [vote, {**vote, "reviewer_id": "gold-b"}]})
        output_ref = write(root, f"output-{index}.json", {"relevant": positive, "explanation": text})
        outputs.append({"case_id": identifier, "input_sha256": input_ref["sha256"],
            "status": "ok", "relevant": positive, "latency_ms": 1.0,
            "reason_codes": ["synthetic"], "output": output_ref, "citations": [deepcopy(citation)]})
        audit = {"reviewer_id": "audit-a", "decision_matches_output": True, "citations_complete": True,
            "invented_facts": 0, "invented_deadlines": 0, "rationale": "Synthetic output audit only"}
        audits.append({"case_id": identifier, "output_sha256": output_ref["sha256"],
            "votes": [audit, {**audit, "reviewer_id": "audit-b"}]})
    def reviewer(identifier):
        return {"id": identifier, "independent_of_system": True, "fluent_locales": list(common.LOCALES),
            "domain_review_reference": "Synthetic reviewers are not verified people",
            "businesses": list(business.BUSINESSES)}
    config = write(root, "config.json", {"mode": "synthetic"})
    implementation = write(root, "implementation.json", {"system": "synthetic", "revision": "a" * 40})
    data = {
        "dataset": {"schema_version": "mv2.business-dataset.v1", "id": "synthetic-business",
            "revision": "v1", "provenance": "synthetic_fixture", "authors": ["fixture-author"], "cases": cases},
        "labels": {"schema_version": "mv2.business-labels.v1", "dataset_sha256": "0" * 64,
            "frozen_at": "2026-09-02T00:00:00Z", "review_reference": "Synthetic gold",
            "reviewers": [reviewer(name) for name in ("gold-a", "gold-b", "gold-c")], "labels": gold},
        "predictions": {"schema_version": "mv2.business-predictions.v1", "dataset_sha256": "0" * 64,
            "split": "held_out", "run_id": "synthetic-run", "created_at": "2026-09-03T00:00:00Z",
            "system": "synthetic", "system_revision": "a" * 40, "configuration": config,
            "configuration_sha256": config["sha256"], "implementation": implementation,
            "implementation_sha256": implementation["sha256"], "working_tree_dirty": False, "rows": outputs},
        "audits": {"schema_version": "mv2.business-audits.v1", "dataset_sha256": "0" * 64,
            "predictions_sha256": "0" * 64, "reviewed_at": "2026-09-04T00:00:00Z",
            "review_reference": "Synthetic output audit", "reviewers": [reviewer(name)
                for name in ("audit-a", "audit-b", "audit-c")], "rows": audits}}
    save(root, data)
    return data


def save(root, data):
    dataset_hash = write(root, "dataset.json", data["dataset"])["sha256"]
    for name in ("labels", "predictions", "audits"):
        data[name]["dataset_sha256"] = dataset_hash
    write(root, "labels.json", data["labels"])
    data["audits"]["predictions_sha256"] = write(root, "predictions.json", data["predictions"])["sha256"]
    write(root, "audits.json", data["audits"])


def report(root):
    return business.evaluate(root, *[root / f"{name}.json" for name in ("dataset", "labels", "predictions", "audits")])


def test_complete_synthetic_package_reports_all_businesses_but_cannot_pass(tmp_path):
    data = package(tmp_path, 210)
    result = report(tmp_path)
    assert result["coverage"]["reviewed_by_business"] == {"B2": 70, "B7": 70, "B8": 70}
    assert result["coverage"]["outputs_audited"] == 210
    assert result["citation_validity"] == {"numerator": 210, "denominator": 210, "value": 1.0}
    assert result["readiness_blockers"] == ["synthetic_dataset_not_independent_evidence"]
    assert not result["target_failures"] and not result["capability_approved"]
    assert not result["package_targets_met"]
    assert all(len(locales) == 5 for locales in result["by_business_locale"].values())
    # This only tests declared attestation accounting. No real permission or
    # human identity is created by changing an in-memory synthetic test input.
    data["dataset"]["provenance"] = "permitted_source"
    save(tmp_path, data)
    declared = report(tmp_path)
    assert declared["package_targets_met"] and not declared["capability_approved"]
    assert declared["attestations_require_external_verification"]
    assert "captured_run_authenticity" in declared["unmeasured"]


def test_missing_failed_abstained_rows_keep_recall_denominator(tmp_path):
    data = package(tmp_path, 12)
    data["predictions"]["rows"][0].update(status="error", relevant=None)
    data["predictions"]["rows"][2].update(status="abstained", relevant=None)
    data["predictions"]["rows"][1]["relevant"] = True
    data["predictions"]["rows"] = data["predictions"]["rows"][:4]
    data["audits"]["rows"] = data["audits"]["rows"][:4]
    save(tmp_path, data)
    result = report(tmp_path)
    assert result["metrics"]["recall"] == {"numerator": 0, "denominator": 6, "value": 0.0}
    assert result["metrics"]["false_positive_ids"] == ["pair-1"]
    assert result["metrics"]["unknown_predictions"] == 10
    assert "prediction_run_incomplete" in result["readiness_blockers"]
    assert "pair-4" in result["pending_output_reviews"]


def test_business_failure_is_not_hidden_by_overall_precision(tmp_path):
    data = package(tmp_path, 210)
    # Six B2 false positives fail B2 precision (35 / 41), while the overall
    # precision remains above 85%. Other categories must retain their results.
    changed = 0
    for index in range(1, 210, 6):
        # B2 is index % 3 == 0: use odd multiples of three instead.
        target = index + 2
        data["predictions"]["rows"][target]["relevant"] = True
        changed += 1
        if changed == 7:
            break
    save(tmp_path, data)
    result = report(tmp_path)
    assert result["metrics"]["precision"]["value"] > 0.85
    assert result["by_business"]["B2"]["precision"]["value"] < 0.85
    assert result["target_failures"] == ["B2:precision_below_0.85_or_unmeasured"]


def test_all_negative_zero_denominator_is_unmeasured(tmp_path):
    data = package(tmp_path)
    for label in data["labels"]["labels"]:
        for vote in label["votes"]:
            vote["relevant"] = False
    for row in data["predictions"]["rows"]:
        row["relevant"] = False
    save(tmp_path, data)
    result = report(tmp_path)
    assert result["metrics"]["recall"]["value"] is None
    assert result["metrics"]["precision"]["value"] is None
    assert len(result["target_failures"]) == 6


def test_reformatted_same_pair_and_split_leak_are_rejected(tmp_path):
    data = package(tmp_path)
    same = deepcopy(data["dataset"]["cases"][0])
    same.update(id="other-id", family="other-id")
    raw = (tmp_path / same["input"]["path"]).read_bytes()
    (tmp_path / "reformatted.json").write_bytes(b"  " + raw)
    same["input"] = {"path": "reformatted.json", "sha256": common.digest(b"  " + raw)}
    data["dataset"]["cases"].append(same)
    save(tmp_path, data)
    with pytest.raises(ValueError, match="Reformatted duplicate"):
        report(tmp_path)


def test_offline_processing_has_no_network_or_file_writes(tmp_path, monkeypatch):
    package(tmp_path)
    before = {file.name: file.read_bytes() for file in tmp_path.iterdir()}
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline evaluation attempted a network connection")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    report(tmp_path)
    assert {file.name: file.read_bytes() for file in tmp_path.iterdir()} == before


def test_repeated_artifact_processing_is_bounded_even_when_cached(tmp_path, monkeypatch):
    ref = common.Artifact.model_validate(write(tmp_path, "one.json", {"value": "abcdefgh"}))
    raw_size = (tmp_path / ref.path).stat().st_size
    monkeypatch.setattr(common, "MAX_PACKAGE_BYTES", raw_size * 2)
    reader = business.Package(tmp_path)
    reader.read(ref)
    reader.read(ref)
    with pytest.raises(ValueError, match="repeated-artifact"):
        reader.read(ref)


@pytest.mark.parametrize("fault", ["one_vote", "self_review", "locale", "business", "disagreement"])
def test_independent_gold_remains_pending_until_resolved(tmp_path, fault):
    data = package(tmp_path)
    label = data["labels"]["labels"][0]
    if fault == "one_vote":
        label["votes"].pop()
    elif fault == "self_review":
        data["dataset"]["authors"].append("gold-a")
    elif fault == "locale":
        data["labels"]["reviewers"][0]["fluent_locales"] = ["en-CH"]
    elif fault == "business":
        data["labels"]["reviewers"][0]["businesses"] = ["B7"]
    else:
        label["votes"][1]["relevant"] = False
    save(tmp_path, data)
    result = report(tmp_path)
    assert "pair-0" in result["pending_reviews"]
    if fault == "disagreement":
        label["adjudication"] = {**label["votes"][0], "reviewer_id": "gold-c"}
        save(tmp_path, data)
        resolved = report(tmp_path)
        assert "pair-0" not in resolved["pending_reviews"]
        assert resolved["disagreements"] == ["pair-0"]


@pytest.mark.parametrize("fault", ["wrong_field", "wrong_quote", "missing_citations", "deadline", "fact",
    "decision", "incomplete", "unreviewed", "disagreement", "gold_reviewer", "wrong_scope"])
def test_citations_and_complete_output_audits_cannot_silently_pass(tmp_path, fault):
    data = package(tmp_path)
    prediction, audit = data["predictions"]["rows"][0], data["audits"]["rows"][0]
    if fault == "wrong_field":
        prediction["citations"][0]["field"] = "other"
    elif fault == "wrong_quote":
        prediction["citations"][0]["quote"] = "Invented quotation"
    elif fault == "missing_citations":
        prediction["citations"] = []
    elif fault in ("fact", "deadline", "decision", "incomplete"):
        key, value = {"fact": ("invented_facts", 1), "deadline": ("invented_deadlines", 1),
            "decision": ("decision_matches_output", False), "incomplete": ("citations_complete", False)}[fault]
        for vote in audit["votes"]:
            vote[key] = value
    elif fault == "unreviewed":
        data["audits"]["rows"] = []
    elif fault == "disagreement":
        audit["votes"][1]["invented_facts"] = 1
    elif fault == "gold_reviewer":
        data["audits"]["reviewers"].append(data["labels"]["reviewers"][0])
        audit["votes"][0]["reviewer_id"] = "gold-a"
    else:
        data["audits"]["reviewers"][0]["businesses"] = ["B7"]
    save(tmp_path, data)
    result = report(tmp_path)
    assert result["audit_failures"] or result["pending_output_reviews"]
    assert not result["package_targets_met"]


def test_output_disagreement_keeps_history_and_requires_distinct_adjudication(tmp_path):
    data = package(tmp_path)
    row = data["audits"]["rows"][0]
    row["votes"][1]["invented_deadlines"] = 1
    row["adjudication"] = {**row["votes"][1], "reviewer_id": "audit-c"}
    save(tmp_path, data)
    result = report(tmp_path)
    assert result["output_disagreements"] == ["pair-0"]
    assert result["audit_failures"][0]["invented_deadlines"] == 1
    assert not result["pending_output_reviews"]
    row["adjudication"]["reviewer_id"] = "audit-a"
    save(tmp_path, data)
    with pytest.raises(ValueError):
        report(tmp_path)


@pytest.mark.parametrize("fault", ["source", "output", "config", "permission_hash", "input_hash", "audit_hash",
    "dataset_hash", "review_order", "gold_field", "duplicate_pair", "split_leak", "traversal", "duplicate_json"])
def test_changed_or_ambiguous_package_is_rejected(tmp_path, fault):
    data = package(tmp_path)
    if fault in ("source", "output", "config"):
        filename = "config.json" if fault == "config" else f"{fault}-0.json"
        (tmp_path / filename).write_text('{"changed":"PRIVATE-SENTINEL"}')
    elif fault == "permission_hash":
        data["dataset"]["cases"][0]["sources"][0]["permission"]["sha256"] = "f" * 64
    elif fault == "input_hash":
        data["predictions"]["rows"][0]["input_sha256"] = "f" * 64
    elif fault == "audit_hash":
        data["audits"]["rows"][0]["output_sha256"] = "f" * 64
    elif fault == "review_order":
        data["audits"]["reviewed_at"] = "2026-09-01T00:00:00Z"
    elif fault == "gold_field":
        data["labels"]["labels"][0]["votes"][0]["citations"][0]["field"] = "other"
    elif fault == "duplicate_pair":
        case = deepcopy(data["dataset"]["cases"][0])
        case["id"] = "new-name-same-pair"
        data["dataset"]["cases"].append(case)
    elif fault == "split_leak":
        data["dataset"]["cases"][1]["family"] = "pair-0"
        data["dataset"]["cases"][1]["split"] = "development"
    elif fault == "traversal":
        data["dataset"]["cases"][0]["input"]["path"] = "../outside.json"
    save(tmp_path, data)
    if fault == "dataset_hash":
        data["labels"]["dataset_sha256"] = "f" * 64
        write(tmp_path, "labels.json", data["labels"])
    elif fault == "duplicate_json":
        raw = (tmp_path / "dataset.json").read_text()
        (tmp_path / "dataset.json").write_text(raw.replace('"id": "synthetic-business"',
            '"id": "synthetic-business", "id": "hidden-replacement"'))
    with pytest.raises(ValueError):
        report(tmp_path)


@pytest.mark.parametrize("fault", ["denied", "expired"])
def test_revoked_or_expired_permission_never_counts_as_ready(tmp_path, fault):
    data = package(tmp_path)
    ref = data["dataset"]["cases"][0]["sources"][0]["permission"]
    value = json.loads((tmp_path / ref["path"]).read_bytes())
    if fault == "denied":
        value["evaluation_allowed"] = False
    else:
        value["valid_until"] = "2026-09-04T00:00:00Z"
    ref.update(write(tmp_path, ref["path"], value))
    save(tmp_path, data)
    result = report(tmp_path)
    assert result["permission_failures"] == {"pair-0": ["official"]}
    assert "source_permission_not_current_for_review_and_run" in result["readiness_blockers"]


def test_package_shared_budget_and_file_limit(tmp_path, monkeypatch):
    package(tmp_path)
    monkeypatch.setattr(common, "MAX_PACKAGE_BYTES", 100)
    with pytest.raises(ValueError, match="budget"):
        report(tmp_path)
    monkeypatch.setattr(common, "MAX_PACKAGE_BYTES", 128 * 1024 * 1024)
    monkeypatch.setattr(common, "MAX_FILE_BYTES", 10)
    with pytest.raises(ValueError, match="limit"):
        report(tmp_path)


def test_cli_reproducible_report_schema_errors_and_existing_file(tmp_path):
    package(tmp_path)
    command = [sys.executable, "-B", str(ROOT / "scripts" / "evaluate_business_matching.py")]
    schemas = subprocess.run([*command, "schemas"], capture_output=True, text=True, check=False)
    assert schemas.returncode == 0
    assert set(json.loads(schemas.stdout)) == {"Dataset", "Labels", "Predictions", "Audits", "Permission"}
    args = [*command, "evaluate", "--root", str(tmp_path)]
    for name in ("dataset", "labels", "predictions", "audits"):
        args.extend(["--" + name, str(tmp_path / f"{name}.json")])
    first = subprocess.run([*args, "--output", str(tmp_path / "report.json")], capture_output=True, text=True)
    assert first.returncode == 1 and not json.loads(first.stdout)["capability_approved"]
    raw = (tmp_path / "report.json").read_bytes()
    assert json.loads(first.stdout)["sha256"] == common.digest(raw)
    second = subprocess.run([*args, "--output", str(tmp_path / "report2.json")], capture_output=True, text=True)
    assert second.returncode == 1 and raw == (tmp_path / "report2.json").read_bytes()
    again = subprocess.run([*args, "--output", str(tmp_path / "report.json")], capture_output=True, text=True)
    assert again.returncode == 2 and raw == (tmp_path / "report.json").read_bytes()
    (tmp_path / "labels.json").write_text('{"PRIVATE-SENTINEL": "password-value"}')
    failed = subprocess.run(args, capture_output=True, text=True)
    assert failed.returncode == 2
    assert "PRIVATE-SENTINEL" not in failed.stderr and "password-value" not in failed.stderr
    assert not failed.stdout
