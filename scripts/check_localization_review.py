"""Validate fluent/native language approval without storing reviewer prose in Git."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

REVIEW_LOCALES = {"de-CH", "fr-CH", "it-CH", "rm-CH"}
BOOLEAN_FIELDS = {
    "catalogue_complete",
    "critical_flows_clear",
    "legal_status_language_clear",
    "local_model_sample_reviewed",
    "local_model_language_natural",
    "source_evidence_unchanged",
    "approved",
}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hex(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value.lower())
    )


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def validate(
    results_path: Path,
    catalogue_path: Path,
    *,
    require_results: bool,
    expected_commit: str | None = None,
    clean_checkout: bool | None = None,
) -> dict:
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "hl057.language-review.v1":
        raise ValueError("Unsupported localization-review schema.")
    required_metadata = {"review_round_id", "build_commit", "catalogue_sha256", "reviews"}
    missing_metadata = required_metadata - set(payload)
    if missing_metadata:
        raise ValueError(f"Missing review metadata: {', '.join(sorted(missing_metadata))}")
    reviews = payload.get("reviews") or []
    if len(reviews) != 4 or {item.get("locale") for item in reviews} != REVIEW_LOCALES:
        raise ValueError("Exactly one review for de-CH, fr-CH, it-CH, and rm-CH is required.")

    failures: list[str] = []
    unresolved_findings = 0
    for review in reviews:
        locale = review["locale"]
        required_fields = BOOLEAN_FIELDS | {
            "reviewer_id",
            "proficiency",
            "reviewed_at",
            "notes",
            "findings",
        }
        missing_fields = required_fields - set(review)
        if missing_fields:
            raise ValueError(f"{locale}: missing fields: {', '.join(sorted(missing_fields))}")
        if not require_results:
            continue
        if not isinstance(review["reviewer_id"], str) or not review["reviewer_id"].strip():
            failures.append(f"{locale}: reviewer_id is required")
        permitted_proficiency = {"native"} if locale == "rm-CH" else {"fluent", "native"}
        if review["proficiency"] not in permitted_proficiency:
            failures.append(f"{locale}: reviewer proficiency must be {sorted(permitted_proficiency)}")
        if _timestamp(review["reviewed_at"]) is None:
            failures.append(f"{locale}: reviewed_at must be timezone-aware")
        for field in BOOLEAN_FIELDS:
            if review[field] is not True:
                failures.append(f"{locale}: {field} must be explicitly true")
        if not isinstance(review["notes"], str) or len(review["notes"].strip()) < 12:
            failures.append(f"{locale}: notes must contain a concrete review observation")
        findings = review["findings"]
        if not isinstance(findings, list):
            failures.append(f"{locale}: findings must be a list")
            continue
        for index, finding in enumerate(findings, start=1):
            if not isinstance(finding, dict):
                failures.append(f"{locale}: finding {index} must be an object")
                continue
            if not isinstance(finding.get("key"), str) or not finding["key"].strip():
                failures.append(f"{locale}: finding {index} needs the catalogue key")
            if not isinstance(finding.get("description"), str) or len(finding["description"].strip()) < 12:
                failures.append(f"{locale}: finding {index} needs a concrete description")
            if finding.get("resolved") is not True:
                unresolved_findings += 1
                failures.append(f"{locale}: finding {index} is unresolved")
            if not _hex(finding.get("resolution_commit"), 40):
                failures.append(f"{locale}: finding {index} needs its resolution commit")

    if require_results:
        reviewer_ids = [item.get("reviewer_id") for item in reviews]
        if len(set(reviewer_ids)) != len(reviewer_ids):
            failures.append("Every locale requires a different fluent/native reviewer")
        if not isinstance(payload.get("review_round_id"), str) or not payload["review_round_id"].strip():
            failures.append("review_round_id is required")
        if not _hex(payload.get("build_commit"), 40):
            failures.append("build_commit must be a 40-character Git revision")
        elif expected_commit and payload["build_commit"] != expected_commit:
            failures.append("build_commit does not match the checked-out release")
        catalogue_sha256 = payload.get("catalogue_sha256")
        if not _hex(catalogue_sha256, 64) or catalogue_sha256.lower() != _digest(catalogue_path):
            failures.append("catalogue_sha256 does not match the reviewed catalogue")
        if clean_checkout is False:
            failures.append("the release checkout contains uncommitted changes")

    return {
        "schema_version": payload["schema_version"],
        "mode": "results" if require_results else "template",
        "review_round_id": payload.get("review_round_id"),
        "build_commit": payload.get("build_commit"),
        "catalogue_sha256": payload.get("catalogue_sha256"),
        "locales": sorted(REVIEW_LOCALES),
        "reviews": len(reviews),
        "unresolved_findings": unresolved_findings,
        "passed": not failures,
        "failures": failures,
    }


def _git_state(repo_root: Path) -> tuple[str | None, bool]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None, False
    return commit, not status


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Validate the HL-057 human language review.")
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=repo_root / "demo" / "localization-review.template.json",
    )
    parser.add_argument("--results", action="store_true")
    parser.add_argument(
        "--catalogue",
        type=Path,
        default=repo_root / "apps" / "web" / "lib" / "i18n.tsx",
    )
    args = parser.parse_args()
    commit, clean = _git_state(repo_root)
    result = validate(
        args.path,
        args.catalogue,
        require_results=args.results,
        expected_commit=commit if args.results else None,
        clean_checkout=clean if args.results else None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
