"""Offline measurements of a bounded gate trial and explicitly fictional traces.

No model calls, source downloads, database access or production dossier lookup.
Exact quote checks reuse the native citation contract; they do not prove truth.
"""
import math
from collections import Counter
from types import SimpleNamespace

from .config import DomainError
from .product_investigations import Citation, citation

OUTCOMES = ("relevant", "uncertain", "unrelated", "unavailable", "interrupted", "not_run")


def indexed(rows):
    result = {row["id"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError("Repeated record identity")
    return result


def gate_metrics(cases, observations):
    """All planned cases stay in denominators; abstentions are not correct answers."""
    expected, actual = indexed(cases), indexed(observations)
    if not actual.keys() <= expected.keys():
        raise ValueError("Observation outside the frozen plan")
    for row in cases:
        if type(row["label"]) is not int or row["label"] not in (0, 1):
            raise ValueError("Labels must retain binary human judgments")
    for row in observations:
        if row["outcome"] not in OUTCOMES[:-1]:
            raise ValueError("Invalid observation outcome")
        ms = row.get("wall_ms")
        if ms is not None and (type(ms) not in (int, float) or not math.isfinite(ms) or ms < 0):
            raise ValueError("Invalid latency")
    groups = {}
    for language in ["all", *sorted({row["language"] for row in cases})]:
        selected = [r for r in cases if language == "all" or r["language"] == language]
        table = {str(label): dict.fromkeys(OUTCOMES, 0) for label in (0, 1)}
        for row in selected:
            table[str(row["label"])][actual.get(row["id"], {}).get("outcome", "not_run")] += 1
        positive, negative = sum(table["1"].values()), sum(table["0"].values())
        divide = lambda a, b: round(a / b, 6) if b else None  # noqa: E731
        groups[language] = {
            "planned": len(selected), "positive_labels": positive, "negative_labels": negative,
            "outcomes_by_label": table,
            "positive_admission_rate": divide(table["1"]["relevant"], positive),
            "positive_harmful_rejection_rate": divide(table["1"]["unrelated"], positive),
            "negative_rejection_rate": divide(table["0"]["unrelated"], negative),
            "negative_false_admission_rate": divide(table["0"]["relevant"], negative),
            "admission_precision": divide(table["1"]["relevant"], table["1"]["relevant"] + table["0"]["relevant"]),
        }
    latencies = sorted(r["wall_ms"] for r in observations if r.get("wall_ms") is not None)
    return {"groups": groups, "observed": len(observations),
        "latency_ms": {"count": len(latencies), "mean": round(sum(latencies) / len(latencies), 2) if latencies else None,
            "p95_nearest_rank": latencies[math.ceil(len(latencies) * .95) - 1] if latencies else None},
        "estimated_cost_usd": None, "cost_basis": "Local CPU/hosting unmetered; unknown, not zero.",
        "interpretation": "Agreement with full-passage human relevance labels given bounded candidate prefixes. Uncertain, unavailable, interrupted and unrun are separate; no truth, professional quality or whole-web recall score."}


def audit_fixture(document):
    """Audit public fictional fixtures only, returning IDs/counts without source text."""
    if document.get("fictional_sources_and_organisations") is not True or document.get("not_live_provider_validation") is not True:
        raise ValueError("Only explicitly fictional public fixture receipts are allowed")
    run = document["run"]
    sources, claims, evidence, entities, branches = (
        indexed(run[key]) for key in ("sources", "claims", "evidence", "entities", "branches"))
    indexed(run["relationships"])
    questions = indexed(run["research"]["questions"])
    if any(s["kind"] != "public_source" for s in sources.values()):
        raise ValueError("Private or saved sources are outside this audit")
    errors, citations = [], []

    def check(value, target):
        try:
            source = sources[value["source_id"]]
            checked = Citation(quote=value["quote"], locator=value["locator"])
            citation(SimpleNamespace(id=source["id"], sha256=source["sha256"], snapshot=source["snapshot"]), checked)
            if value.get("sha256", source["sha256"]) != source["sha256"]:
                raise ValueError("Hash differs")
            citations.append(target)
            return True
        except (DomainError, ValueError, KeyError, TypeError):
            errors.append({"target": target, "code": "invalid_citation"})
            return False

    for value in evidence.values():
        check(value, "evidence:" + value["id"])
        if value["claim_id"] not in claims:
            errors.append({"target": value["id"], "code": "foreign_claim"})
    for entity in entities.values():
        check(entity["evidence"], "entity:" + entity["id"])
        for index, mention in enumerate(entity["evidence"].get("mentions", [])):
            check(mention, f"mention:{entity['id']}:{index}")
    for source in sources.values():
        classification = source["snapshot"].get("source_class")
        if classification:
            check(classification, "classification:" + source["id"])
    for edge in run["relationships"]:
        value = edge["evidence"]
        check(value, "relationship:" + edge["id"])
        if edge["subject_id"] not in entities or edge["object_id"] not in entities:
            errors.append({"target": edge["id"], "code": "foreign_entity"})
        if not any(e["claim_id"] == value.get("claim_id") and e["source_id"] == value["source_id"]
                   and e["quote"] == value["quote"] and e["locator"] == value["locator"]
                   and e["relation"] == "SUPPORTS" for e in evidence.values()):
            errors.append({"target": edge["id"], "code": "missing_supporting_claim_edge"})
    followups = []
    for question in questions.values():
        if not question.get("parent_branch_id"):
            continue
        valid = check(question.get("trigger") or {}, "question:" + question["id"])
        child, parent = branches.get(question.get("branch_id")), branches.get(question["parent_branch_id"])
        if not child or not parent or child.get("parent_branch_id") != parent["id"]:
            errors.append({"target": question["id"], "code": "broken_branch_link"})
            valid = False
        answers = [evidence.get(key) for key in question.get("answer_evidence_ids", [])]
        trigger_source = sources.get((question.get("trigger") or {}).get("source_id"))
        new = []
        for answer in answers:
            source = sources.get(answer.get("source_id")) if answer else None
            if (not source or not child or source["snapshot"].get("branch_id") != child["id"]
                    or not trigger_source or source["sha256"] == trigger_source["sha256"]
                    or source["snapshot"].get("duplicate_of")
                    or (question.get("claim_id") and answer["claim_id"] != question["claim_id"])):
                errors.append({"target": question["id"], "code": "invalid_followup_answer"})
                valid = False
            else:
                new.append(answer)
        claim = claims.get(question.get("claim_id"))
        before = question.get("claim_revision_before")
        changed = bool(claim and type(before) is int and claim["revision"] > before
            and any(h["revision"] > before and h.get("source_id") in {e["source_id"] for e in new}
                    for h in claim["history"]))
        if question.get("status") == "evidence_found" and not new:
            errors.append({"target": question["id"], "code": "evidence_found_without_new_evidence"})
            valid = False
        followups.append({"question_id": question["id"], "valid_linkage": valid,
            "new_evidence_count": len(new), "same_claim_revision_changed": changed})
    contradictory = []
    for claim in claims.values():
        relations = {e["relation"] for e in evidence.values() if e["claim_id"] == claim["id"]}
        if {"SUPPORTS", "CONTRADICTS"} <= relations:
            contradictory.append(claim["id"])
            if claim["status"] != "CONTESTED":
                errors.append({"target": claim["id"], "code": "contradiction_not_preserved"})
    hashes = Counter(s["sha256"] for s in sources.values())
    return {"product": document["product"], "run_id": run["id"], "passed": not errors,
        "verified_citation_links": len(citations), "errors": errors,
        "source_count": len(sources), "unique_body_hashes": len(hashes),
        "duplicate_bodies": sum(n - 1 for n in hashes.values()),
        "contradicted_claim_ids": contradictory, "followups": followups,
        "unresolved_questions": sum(q["status"] != "evidence_found" for q in questions.values()),
        "reported_active_seconds": run["research"]["used"].get("active_seconds"),
        "estimated_cost_usd": None,
        "independent_publisher_count": None, "factual_accuracy": None,
        "scope": "Deterministic structural audit of fictional controlled-adapter trace; exact citation is not entailment or independent factual verification."}
