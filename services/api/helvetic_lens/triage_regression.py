"""Executable deterministic gate for the labelled HL-064 regression corpus."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .diffing import compare_passages
from .identity import assess_comparison_identity

SUPPORTED_LOCALES = {"de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"}


def load_corpus(path: Path) -> dict[str, Any]:
    corpus = json.loads(path.read_text(encoding="utf-8"))
    if corpus.get("schema_version") != "hl064.v1":
        raise ValueError("Unsupported AI-triage regression schema.")
    locales = set(corpus.get("supported_locales", []))
    if locales != SUPPORTED_LOCALES:
        raise ValueError("The regression corpus must declare every supported product locale exactly once.")
    case_ids = [case.get("id") for case in corpus.get("cases", [])]
    if not case_ids or len(case_ids) != len(set(case_ids)):
        raise ValueError("Regression case IDs must be present and unique.")
    return corpus


def _assert_expected_counts(case: dict[str, Any], result: dict[str, Any]) -> None:
    expected = case["expected"]
    if result["complete"] is not True:
        raise AssertionError(f"{case['id']}: exact diff is incomplete")
    if "material_count" in expected and result["material_count"] != expected["material_count"]:
        raise AssertionError(
            f"{case['id']}: expected {expected['material_count']} material changes, "
            f"received {result['material_count']}"
        )
    for key, value in expected.get("semantic_counts", {}).items():
        actual = result["semantic_counts"].get(key, 0)
        if actual != value:
            raise AssertionError(f"{case['id']}: expected {key}={value}, received {actual}")
    if "change_clusters" in expected and len(result["change_clusters"]) != expected["change_clusters"]:
        raise AssertionError(
            f"{case['id']}: expected {expected['change_clusters']} clusters, "
            f"received {len(result['change_clusters'])}"
        )


def _run_identity_case(case: dict[str, Any]) -> dict[str, Any]:
    law = SimpleNamespace(**case["law"])
    before = SimpleNamespace(**case["before"], passages=[])
    after = SimpleNamespace(**case["after"], passages=[])
    result = assess_comparison_identity(law, before, after)
    expected = case["expected"]
    if result["status"] != expected["status"] or result["reason_code"] != expected["reason_code"]:
        raise AssertionError(f"{case['id']}: identity mismatch was not classified as expected")
    return {"status": result["status"], "reason_code": result["reason_code"]}


def _run_relation_case(case: dict[str, Any]) -> dict[str, Any]:
    relation = case["relation"]
    evidence = relation.get("evidence") or {}
    authoritative = all(
        (
            relation.get("state") == "confirmed",
            relation.get("provenance_method") == "official_metadata",
            relation.get("relation_type") in {"repeals", "replaces", "amends"},
            bool(relation.get("source_url")),
            bool(evidence.get("metadata_field")),
            evidence.get("declared_target") == relation.get("object_identifier"),
        )
    )
    if authoritative is not case["expected"]["authoritative"]:
        raise AssertionError(f"{case['id']}: official relation provenance is incomplete")
    return {"authoritative": authoritative, "relation_type": relation["relation_type"]}


def _generated_passages(template: str, count: int, prefix: str) -> list[dict[str, Any]]:
    return [
        {"id": f"{prefix}-{number}", "page": (number // 40) + 1, "text": template.format(number=number)}
        for number in range(1, count + 1)
    ]


def run_gate(path: Path, *, full: bool = False) -> dict[str, Any]:
    corpus = load_corpus(path)
    observed_locales: set[str] = set()
    results: list[dict[str, Any]] = []

    for case in corpus["cases"]:
        observed_locales.add(case["locale"])
        kind = case["kind"]
        if kind == "identity_mismatch":
            outcome = _run_identity_case(case)
        elif kind == "official_relation":
            outcome = _run_relation_case(case)
        else:
            if kind == "generated_rewrite":
                generator = case["generator"]
                count_key = "full_passages_per_side" if full else "quick_passages_per_side"
                passage_count = int(generator[count_key])
                before = _generated_passages(generator["before_template"], passage_count, "before")
                after = _generated_passages(generator["after_template"], passage_count, "after")
            elif kind == "diff":
                before = case["before"]
                after = case["after"]
                passage_count = max(len(before), len(after))
            else:
                raise ValueError(f"Unsupported regression case kind: {kind}")
            diff = compare_passages(before, after)
            _assert_expected_counts(case, diff)
            if case["expected"].get("all_units_material"):
                exact_old_coverage = sum(item["old"] is not None for item in diff["items"])
                exact_new_coverage = sum(item["new"] is not None for item in diff["items"])
                if (
                    diff["material_count"] != len(diff["items"])
                    or exact_old_coverage != len(before)
                    or exact_new_coverage != len(after)
                    or any(
                        count
                        for classification, count in diff["semantic_counts"].items()
                        if classification in {"moved", "renumbered", "formatting_only"}
                    )
                ):
                    raise AssertionError(f"{case['id']}: the complete rewrite lost material units")
            outcome = {
                "complete": diff["complete"],
                "material_count": diff["material_count"],
                "semantic_counts": diff["semantic_counts"],
                "passages_per_side": passage_count,
            }
        results.append({"id": case["id"], "locale": case["locale"], "kind": kind, **outcome})

    if observed_locales != SUPPORTED_LOCALES:
        missing = sorted(SUPPORTED_LOCALES - observed_locales)
        raise AssertionError(f"Regression cases do not exercise locales: {', '.join(missing)}")
    return {
        "schema_version": corpus["schema_version"],
        "mode": "full" if full else "quick",
        "locales": sorted(observed_locales),
        "cases": results,
        "passed": len(results),
    }
