import json
from pathlib import Path

from scripts.check_relation_graph_experiment import validate

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "demo" / "relation-graph-experiment.template.json"
LOCALES = ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]
VARIANTS = ["inbox_list_v1", "graph_review_v1"]


def completed_payload(*, graph_duration_ms: int = 70_000) -> dict:
    payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    payload.update(
        experiment_id="relation-review-round-1",
        build_commit="a" * 40,
        task_set_revision="federal-relation-set-v1",
        randomization_method="blocked-by-locale-separate-participants",
        started_at="2026-09-03T10:00:00+02:00",
        completed_at="2026-09-03T16:00:00+02:00",
    )
    for variant in VARIANTS:
        duration = 100_000 if variant == "inbox_list_v1" else graph_duration_ms
        for participant_number in range(10):
            locale = LOCALES[participant_number % len(LOCALES)]
            for trial_number in range(3):
                task_number = (participant_number + trial_number) % 5
                expected = "confirmed" if task_number % 2 == 0 else "rejected"
                payload["trials"].append(
                    {
                        "participant_id": f"{variant}-reviewer-{participant_number}",
                        "locale": locale,
                        "variant": variant,
                        "task_id": f"relation-task-{task_number}",
                        "expected_decision": expected,
                        "decision": expected,
                        "duration_ms": duration,
                        "completed": True,
                        "evidence_opened": True,
                        "authorization_passed": True,
                        "accessible_without_color": True,
                        "list_alternative_complete": True,
                    }
                )
    return payload


def write_payload(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "relation-graph-results.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def evaluate(tmp_path: Path, payload: dict) -> dict:
    return validate(
        write_payload(tmp_path, payload),
        require_results=True,
        expected_commit="a" * 40,
        clean_checkout=True,
    )


def test_blank_template_is_valid_without_claiming_results():
    result = validate(TEMPLATE, require_results=False)

    assert result == {
        "schema_version": "hl053.graph-experiment.v1",
        "mode": "template",
        "passed": True,
        "decision": "not_run",
        "trials": 0,
        "failures": [],
    }


def test_graph_is_promoted_only_with_noninferior_quality_and_material_time_gain(
    tmp_path,
):
    result = evaluate(tmp_path, completed_payload())

    assert result["passed"] is True
    assert result["decision"] == "promote_graph_as_secondary_view"
    assert result["benefit"] == {
        "time_improvement_at_least_20_percent": True,
        "accuracy_improvement_at_least_5_points": False,
    }
    assert result["metrics"]["graph_review_v1"]["participants"] == 10
    assert result["metrics"]["graph_review_v1"]["tasks"] == 5


def test_valid_experiment_without_material_benefit_retains_list(tmp_path):
    result = evaluate(tmp_path, completed_payload(graph_duration_ms=90_000))

    assert result["passed"] is True
    assert result["decision"] == "retain_inbox_list_only"
    assert not result["failures"]


def test_incomplete_or_mismatched_experiment_fails_closed(tmp_path):
    payload = completed_payload()
    payload["trials"] = payload["trials"][:29] + payload["trials"][30:59]

    result = evaluate(tmp_path, payload)

    assert result["passed"] is False
    assert result["decision"] == "insufficient_or_unsafe_evidence"
    assert any("at least 30 trials" in failure for failure in result["failures"])


def test_shared_participant_and_accessibility_failure_block_promotion(tmp_path):
    payload = completed_payload()
    graph_trial = next(
        trial for trial in payload["trials"] if trial["variant"] == "graph_review_v1"
    )
    graph_trial["participant_id"] = payload["trials"][0]["participant_id"]
    graph_trial["accessible_without_color"] = False

    result = evaluate(tmp_path, payload)

    assert result["passed"] is False
    assert result["decision"] == "insufficient_or_unsafe_evidence"
    assert any("assigned to only one" in failure for failure in result["failures"])
    assert any("accessible status" in failure for failure in result["failures"])


def test_every_variant_must_include_all_five_locales(tmp_path):
    payload = completed_payload()
    for trial in payload["trials"]:
        if trial["variant"] == "graph_review_v1" and trial["locale"] == "rm-CH":
            trial["locale"] = "de-CH"

    result = evaluate(tmp_path, payload)

    assert result["passed"] is False
    assert any("each variant must cover" in failure for failure in result["failures"])


def test_malformed_completed_trial_fails_closed_instead_of_crashing(tmp_path):
    payload = completed_payload()
    payload["trials"][0]["duration_ms"] = None
    payload["trials"].append(["invalid-row"])

    result = evaluate(tmp_path, payload)

    assert result["passed"] is False
    assert result["decision"] == "insufficient_or_unsafe_evidence"
    assert any("needs a duration" in failure for failure in result["failures"])
    assert any("must be an object" in failure for failure in result["failures"])
