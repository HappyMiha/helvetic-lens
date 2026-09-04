import json
from pathlib import Path

import pytest
from scripts.check_ai_triage_usability import validate

TEMPLATE = Path(__file__).resolve().parents[3] / "demo" / "ai-triage-usability-review.template.json"


def completed_payload():
    payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    payload.update(
        review_round_id="round-2026-09-03",
        moderator_id="moderator-1",
        build_commit="a" * 40,
        target_host="capacity-server",
        model_profile="dual-1080-replicated",
        capacity_report_sha256="b" * 64,
    )
    for session in payload["sessions"]:
        session.update(
            participant_id=f"reviewer-{session['locale']}",
            started_at="2026-09-03T10:00:00+02:00",
            completed_at="2026-09-03T10:03:00+02:00",
            seconds_to_first_useful_insight=90,
            identified_main_material_change=True,
            main_material_change="The inserted deadline duty was identified.",
            identified_possible_organization_relevance=True,
            organization_relevance="The participant linked it to the compliance team.",
            opened_exact_evidence=True,
            evidence_reference="Saved passage evidence row 4 was opened.",
            identified_next_review_step=True,
            next_review_step="Assign legal review of the new deadline.",
            opened_all_exact_changes=False,
            action_specificity=True,
            action_owner_honest=True,
            action_due_state_honest=True,
            reviewed_action="Review the deadline with the compliance owner.",
            moderator_notes="Observed in the moderated fixture flow.",
        )
    return payload


def test_review_template_covers_five_locales_without_claiming_human_results():
    result = validate(TEMPLATE, require_results=False)
    payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))

    assert result["passed"] is True and result["sessions"] == 5
    assert all(session["participant_id"] is None for session in payload["sessions"])
    assert all(session["seconds_to_first_useful_insight"] is None for session in payload["sessions"])


def test_completed_review_fails_when_insight_takes_over_two_minutes(tmp_path):
    payload = completed_payload()
    payload["sessions"][3]["seconds_to_first_useful_insight"] = 121
    completed = tmp_path / "review.json"
    completed.write_text(json.dumps(payload), encoding="utf-8")

    result = validate(completed, require_results=True)

    assert result["passed"] is False
    assert result["failures"] == ["rm-CH: first useful insight took 121 seconds"]


def test_completed_review_passes_only_with_explicit_observed_results(tmp_path):
    payload = completed_payload()
    completed = tmp_path / "review.json"
    completed.write_text(json.dumps(payload), encoding="utf-8")

    result = validate(completed, require_results=True)

    assert result["passed"] is True
    assert result["failures"] == []


def test_completed_review_requires_independent_participants_and_concrete_notes(tmp_path):
    payload = completed_payload()
    payload["sessions"][1]["participant_id"] = payload["sessions"][0]["participant_id"]
    payload["sessions"][2]["moderator_notes"] = "   "
    completed = tmp_path / "review.json"
    completed.write_text(json.dumps(payload), encoding="utf-8")

    result = validate(completed, require_results=True)

    assert result["passed"] is False
    assert "Every locale requires a different independent participant" in result["failures"]
    assert any("moderator_notes" in failure for failure in result["failures"])


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -1, True, None])
def test_invalid_observed_duration_cannot_pass_human_acceptance(tmp_path, invalid):
    payload = completed_payload()
    payload["sessions"][0]["seconds_to_first_useful_insight"] = invalid
    completed = tmp_path / "review.json"
    completed.write_text(json.dumps(payload), encoding="utf-8")
    result = validate(completed, require_results=True)
    assert result["passed"] is False
    assert any("time must be a non-negative number" in failure for failure in result["failures"])
