"""Validate the structure or completed results of the HL-064 moderated review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

LOCALES = {"de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"}
BOOLEAN_FIELDS = {
    "identified_main_material_change",
    "identified_possible_organization_relevance",
    "opened_exact_evidence",
    "identified_next_review_step",
    "opened_all_exact_changes",
    "action_specificity",
    "action_owner_honest",
    "action_due_state_honest",
}


def validate(path: Path, *, require_results: bool) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "hl064.usability.v1":
        raise ValueError("Unsupported usability-review schema.")
    sessions = payload.get("sessions") or []
    if {session.get("locale") for session in sessions} != LOCALES or len(sessions) != 5:
        raise ValueError("Exactly one session for every supported locale is required.")

    failures = []
    for session in sessions:
        locale = session["locale"]
        missing_fields = (BOOLEAN_FIELDS | {"participant_id", "started_at", "seconds_to_first_useful_insight", "moderator_notes"}) - set(session)
        if missing_fields:
            raise ValueError(f"{locale}: missing fields: {', '.join(sorted(missing_fields))}")
        if not require_results:
            continue
        if not session["participant_id"] or not session["started_at"]:
            failures.append(f"{locale}: participant and start time are required")
        seconds = session["seconds_to_first_useful_insight"]
        if not isinstance(seconds, int | float) or isinstance(seconds, bool) or seconds < 0:
            failures.append(f"{locale}: first-useful-insight time must be a non-negative number")
        elif seconds > 120:
            failures.append(f"{locale}: first useful insight took {seconds} seconds")
        for field in BOOLEAN_FIELDS:
            if not isinstance(session[field], bool):
                failures.append(f"{locale}: {field} must be explicitly true or false")
        required_successes = BOOLEAN_FIELDS - {"opened_all_exact_changes"}
        for field in required_successes:
            if session[field] is not True:
                failures.append(f"{locale}: {field} did not pass")
        if session["opened_all_exact_changes"] is not False:
            failures.append(f"{locale}: participant needed All exact changes before the first useful insight")
        if session["moderator_notes"] is None:
            failures.append(f"{locale}: moderator notes must record observations, even when no issue was found")

    return {
        "schema_version": payload["schema_version"],
        "mode": "results" if require_results else "template",
        "locales": sorted(LOCALES),
        "sessions": len(sessions),
        "passed": not failures,
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path("demo/ai-triage-usability-review.template.json"),
    )
    parser.add_argument("--results", action="store_true", help="Require completed passing sessions.")
    args = parser.parse_args()
    result = validate(args.path, require_results=args.results)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
