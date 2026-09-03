"""Validate the structure or completed results of the HL-064 moderated review."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
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
TEXT_EVIDENCE_FIELDS = {
    "main_material_change",
    "organization_relevance",
    "evidence_reference",
    "next_review_step",
    "reviewed_action",
    "moderator_notes",
}
REVIEW_FIELDS = BOOLEAN_FIELDS | TEXT_EVIDENCE_FIELDS | {
    "participant_id",
    "started_at",
    "completed_at",
    "seconds_to_first_useful_insight",
}


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _is_hex_digest(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value.lower())
    )


def validate(path: Path, *, require_results: bool) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "hl064.usability.v2":
        raise ValueError("Unsupported usability-review schema.")
    required_metadata = {
        "review_round_id",
        "moderator_id",
        "build_commit",
        "target_host",
        "model_profile",
        "capacity_report_sha256",
        "corpus_revision",
        "comparison_fixture",
    }
    missing_metadata = required_metadata - set(payload)
    if missing_metadata:
        raise ValueError(f"Missing review metadata: {', '.join(sorted(missing_metadata))}")
    sessions = payload.get("sessions") or []
    if {session.get("locale") for session in sessions} != LOCALES or len(sessions) != 5:
        raise ValueError("Exactly one session for every supported locale is required.")

    failures = []
    session_starts: list[datetime] = []
    session_completions: list[datetime] = []
    for session in sessions:
        locale = session["locale"]
        missing_fields = REVIEW_FIELDS - set(session)
        if missing_fields:
            raise ValueError(f"{locale}: missing fields: {', '.join(sorted(missing_fields))}")
        if not require_results:
            continue
        if not session["participant_id"]:
            failures.append(f"{locale}: participant is required")
        started_at = _parse_timestamp(session["started_at"])
        completed_at = _parse_timestamp(session["completed_at"])
        if started_at is None or completed_at is None or completed_at < started_at:
            failures.append(f"{locale}: valid timezone-aware session timestamps are required")
        else:
            session_starts.append(started_at)
            session_completions.append(completed_at)
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
        if (
            started_at
            and completed_at
            and isinstance(seconds, int | float)
            and not isinstance(seconds, bool)
            and seconds > (completed_at - started_at).total_seconds()
        ):
            failures.append(f"{locale}: insight time exceeds the recorded session duration")
        for field in TEXT_EVIDENCE_FIELDS:
            value = session[field]
            if not isinstance(value, str) or len(value.strip()) < 12:
                failures.append(f"{locale}: {field} must contain a concrete observed value")

    if require_results:
        participant_ids = [session.get("participant_id") for session in sessions]
        if len(set(participant_ids)) != len(participant_ids):
            failures.append("Every locale requires a different independent participant")
        for field in (
            "review_round_id",
            "moderator_id",
            "target_host",
            "model_profile",
        ):
            if not isinstance(payload.get(field), str) or not payload[field].strip():
                failures.append(f"{field} is required")
        build_commit = payload.get("build_commit")
        if not _is_hex_digest(build_commit, 40):
            failures.append("build_commit must be the measured 40-character Git revision")
        report_hash = payload.get("capacity_report_sha256")
        if not _is_hex_digest(report_hash, 64):
            failures.append("capacity_report_sha256 must identify the measured capacity report")

    return {
        "schema_version": payload["schema_version"],
        "mode": "results" if require_results else "template",
        "locales": sorted(LOCALES),
        "sessions": len(sessions),
        "review_round_id": payload.get("review_round_id"),
        "build_commit": payload.get("build_commit"),
        "target_host": payload.get("target_host"),
        "model_profile": payload.get("model_profile"),
        "capacity_report_sha256": payload.get("capacity_report_sha256"),
        "corpus_revision": payload.get("corpus_revision"),
        "comparison_fixture": payload.get("comparison_fixture"),
        "session_window": {
            "started_at": min(session_starts).isoformat() if session_starts else None,
            "completed_at": max(session_completions).isoformat() if session_completions else None,
        },
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
