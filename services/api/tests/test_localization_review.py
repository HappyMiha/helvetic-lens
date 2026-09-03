import hashlib
import json
from pathlib import Path

from scripts.check_localization_review import validate

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "demo" / "localization-review.template.json"
CATALOGUE = ROOT / "apps" / "web" / "lib" / "i18n.tsx"


def completed_payload():
    payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    payload.update(
        review_round_id="public-beta-round-1",
        build_commit="a" * 40,
        catalogue_sha256=hashlib.sha256(CATALOGUE.read_bytes()).hexdigest(),
    )
    for review in payload["reviews"]:
        review.update(
            reviewer_id=f"reviewer-{review['locale']}",
            proficiency="native" if review["locale"] == "rm-CH" else "fluent",
            reviewed_at="2026-09-03T15:00:00+02:00",
            catalogue_complete=True,
            critical_flows_clear=True,
            legal_status_language_clear=True,
            local_model_sample_reviewed=True,
            local_model_language_natural=True,
            source_evidence_unchanged=True,
            approved=True,
            notes="Reviewed the complete critical-flow and model sample matrix.",
        )
    return payload


def test_blank_review_template_is_valid_without_claiming_results():
    result = validate(TEMPLATE, CATALOGUE, require_results=False)

    assert result["passed"] is True
    assert result["reviews"] == 4


def test_completed_reviews_pass_for_exact_catalogue_and_commit(tmp_path):
    results_path = tmp_path / "reviews.json"
    results_path.write_text(json.dumps(completed_payload()), encoding="utf-8")

    result = validate(
        results_path,
        CATALOGUE,
        require_results=True,
        expected_commit="a" * 40,
        clean_checkout=True,
    )

    assert result["passed"] is True
    assert result["unresolved_findings"] == 0


def test_review_rejects_non_native_romansh_and_duplicate_reviewers(tmp_path):
    payload = completed_payload()
    payload["reviews"][3]["proficiency"] = "fluent"
    payload["reviews"][1]["reviewer_id"] = payload["reviews"][0]["reviewer_id"]
    results_path = tmp_path / "reviews.json"
    results_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate(
        results_path,
        CATALOGUE,
        require_results=True,
        expected_commit="a" * 40,
        clean_checkout=True,
    )

    assert result["passed"] is False
    assert any("rm-CH: reviewer proficiency" in failure for failure in result["failures"])
    assert "Every locale requires a different fluent/native reviewer" in result["failures"]


def test_review_rejects_catalogue_drift_and_unresolved_findings(tmp_path):
    payload = completed_payload()
    payload["reviews"][0]["findings"] = [
        {
            "key": "compare.reviewPlan",
            "description": "The wording is ambiguous in this context.",
            "resolved": False,
            "resolution_commit": None,
        }
    ]
    results_path = tmp_path / "reviews.json"
    results_path.write_text(json.dumps(payload), encoding="utf-8")
    changed_catalogue = tmp_path / "i18n.tsx"
    changed_catalogue.write_bytes(CATALOGUE.read_bytes() + b"\n")

    result = validate(
        results_path,
        changed_catalogue,
        require_results=True,
        expected_commit="a" * 40,
        clean_checkout=True,
    )

    assert result["passed"] is False
    assert result["unresolved_findings"] == 1
    assert any("catalogue_sha256" in failure for failure in result["failures"])
    assert any("is unresolved" in failure for failure in result["failures"])
