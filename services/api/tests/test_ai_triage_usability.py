import json
from pathlib import Path

from scripts.check_ai_triage_usability import validate

TEMPLATE = Path(__file__).resolve().parents[3] / "demo" / "ai-triage-usability-review.template.json"


def test_review_template_covers_five_locales_without_claiming_human_results():
    result = validate(TEMPLATE, require_results=False)
    payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))

    assert result["passed"] is True and result["sessions"] == 5
    assert all(session["participant_id"] is None for session in payload["sessions"])
    assert all(session["seconds_to_first_useful_insight"] is None for session in payload["sessions"])


def test_completed_review_fails_when_insight_takes_over_two_minutes(tmp_path):
    payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    for session in payload["sessions"]:
        session.update(
            participant_id=f"reviewer-{session['locale']}",
            started_at="2026-09-03T10:00:00+02:00",
            seconds_to_first_useful_insight=90,
            identified_main_material_change=True,
            identified_possible_organization_relevance=True,
            opened_exact_evidence=True,
            identified_next_review_step=True,
            opened_all_exact_changes=False,
            action_specificity=True,
            action_owner_honest=True,
            action_due_state_honest=True,
            moderator_notes="No issue observed.",
        )
    payload["sessions"][3]["seconds_to_first_useful_insight"] = 121
    completed = tmp_path / "review.json"
    completed.write_text(json.dumps(payload), encoding="utf-8")

    result = validate(completed, require_results=True)

    assert result["passed"] is False
    assert result["failures"] == ["rm-CH: first useful insight took 121 seconds"]


def test_completed_review_passes_only_with_explicit_observed_results(tmp_path):
    payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    for session in payload["sessions"]:
        session.update(
            participant_id=f"reviewer-{session['locale']}",
            started_at="2026-09-03T10:00:00+02:00",
            seconds_to_first_useful_insight=90,
            identified_main_material_change=True,
            identified_possible_organization_relevance=True,
            opened_exact_evidence=True,
            identified_next_review_step=True,
            opened_all_exact_changes=False,
            action_specificity=True,
            action_owner_honest=True,
            action_due_state_honest=True,
            moderator_notes="Observed in the moderated fixture flow.",
        )
    completed = tmp_path / "review.json"
    completed.write_text(json.dumps(payload), encoding="utf-8")

    result = validate(completed, require_results=True)

    assert result["passed"] is True
    assert result["failures"] == []
