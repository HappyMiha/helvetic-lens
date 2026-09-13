"""Development/validation accounting for B2 experiments, not MV2-051 promotion.

Reads captured experiment results without model calls, database or source access.
Source permission and reviewer/runtime authenticity require separate evidence.
"""

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from .ai_capabilities import RuntimeIdentity
from .tender_contracts import TenderLotFacts, TenderProfile, match_lot
from .tender_semantic import REVISION, SYSTEM, Contract, Proposal, digest, prepare, validate_proposal


class Case(Contract):
    id: str = Field(min_length=1, max_length=100)
    family: str = Field(min_length=1, max_length=100)
    split: Literal["development", "validation"]
    locale: Literal["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]
    now: AwareDatetime
    profile: TenderProfile
    facts: TenderLotFacts
    expected_relevant: bool
    label_reference: str = Field(min_length=1, max_length=500)


class Dataset(Contract):
    schema_version: Literal["tender-semantic-experiment-v1"]
    provenance: Literal["synthetic_fixture", "permitted_source_experiment"]
    author: str = Field(min_length=1, max_length=100)
    cases: tuple[Case, ...] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def no_leakage(self):
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Experiment case IDs must be unique")
        partitions = {}
        for case in self.cases:
            for key in ("family:" + case.family, "source:" + case.facts.evidence_sha256,
                        "scope:" + digest([fragment.model_dump() for fragment in case.facts.text])):
                if key in partitions and partitions[key] != case.split:
                    raise ValueError("A source/scope family leaks between development and validation")
                partitions[key] = case.split
        return self


def check_result(case, result):
    """Validate captured evidence binding before counting a prediction."""
    if not isinstance(result, dict):
        raise ValueError("Captured experiment result must be an object")
    baseline = match_lot(case.profile, case.facts, now=case.now)
    bindings = {
        "schema_version": REVISION,
        "profile_sha256": case.profile.fingerprint(),
        "source_sha256": case.facts.evidence_sha256,
        "facts_sha256": digest(case.facts.model_dump(mode="json")),
        "deterministic": baseline,
        "prompt_sha256": hashlib.sha256(SYSTEM.encode()).hexdigest(),
        "schema_sha256": digest(Proposal.model_json_schema()),
        "promotion": "not_approved",
        "evaluated_at": case.now.isoformat(),
    }
    if any(result.get(key) != value for key, value in bindings.items()):
        raise ValueError("Captured result does not match this case and experiment revision")
    status = result.get("status")
    if status not in {"disabled", "excluded", "insufficient_scope", "model_unavailable",
                      "input_too_large", "timeout", "model_error", "invalid_output", "assessed"}:
        raise ValueError("Unknown experiment status")
    if status == "excluded":
        if not baseline["exclusions"] or result.get("proposal") is not None:
            raise ValueError("Unsupported deterministic exclusion")
        return None, None
    if status != "assessed":
        if result.get("proposal") is not None:
            raise ValueError("Failed/disabled experiment cannot contain a proposal")
        return None, None
    if baseline["exclusions"] or not case.profile.capabilities or not case.facts.text:
        raise ValueError("Semantic result bypasses a deterministic exclusion")
    context, raw = prepare(case.profile, case.facts)
    if result.get("input_sha256") != hashlib.sha256(raw.encode()).hexdigest():
        raise ValueError("Captured model input differs from the complete bounded scope")
    runtime = RuntimeIdentity.model_validate(result.get("runtime"))
    raw_response = result.get("raw_response")
    proposal = validate_proposal(raw_response, context)
    if proposal.model_dump(mode="json") != result.get("proposal"):
        raise ValueError("Parsed proposal differs from its captured model response")
    # A response digest identifies the retained raw response but cannot prove that
    # it came from the stated model. The evaluator does not make that claim.
    response_hash = result.get("response_sha256")
    if not isinstance(response_hash, str) or len(response_hash) != 64 or any(c not in "0123456789abcdef" for c in response_hash):
        raise ValueError("Missing captured response fingerprint")
    if hashlib.sha256(raw_response.encode()).hexdigest() != response_hash:
        raise ValueError("Captured response fingerprint does not match its bytes")
    return proposal, digest(runtime.model_dump(mode="json"))


def metrics(rows):
    tp = sum(row["expected"] and row["predicted"] is True for row in rows)
    fp = sum(not row["expected"] and row["predicted"] is True for row in rows)
    fn = sum(row["expected"] and row["predicted"] is not True for row in rows)
    tn = sum(not row["expected"] and row["predicted"] is False for row in rows)
    return {"cases": len(rows), "true_positive": tp, "false_positive": fp,
            "false_negative_including_abstentions": fn, "true_negative": tn,
            "abstained_or_failed": sum(row["predicted"] is None for row in rows),
            "prediction_coverage": sum(row["predicted"] is not None for row in rows) / len(rows) if rows else None,
            "invalid_results": sum(row["status"] == "invalid_record" for row in rows),
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None}


def evaluate(dataset: Dataset, results: dict, *, threshold: int):
    if type(threshold) is not int or not 0 <= threshold <= 100:
        raise ValueError("Supply an explicit integer experiment threshold, 0 to 100")
    if not isinstance(results, dict) or set(results) - {case.id for case in dataset.cases}:
        raise ValueError("Results contain cases outside this dataset")
    rows, groups, runtimes = [], defaultdict(list), set()
    for case in dataset.cases:
        result, prediction = results.get(case.id), None
        if result is None:
            status = "missing_result"
        else:
            try:
                proposal, runtime = check_result(case, result)
                status = result["status"]
                if runtime:
                    runtimes.add(runtime)
                if status == "excluded":
                    prediction = False
                elif proposal and proposal.relevance != "uncertain":
                    prediction = proposal.relevance == "relevant" and proposal.score >= threshold
            except (ValueError, TypeError):
                status = "invalid_record"
        row = {"id": case.id, "split": case.split, "locale": case.locale,
               "expected": case.expected_relevant, "predicted": prediction, "status": status}
        rows.append(row)
        groups[f"{case.split}/{case.locale}"].append(row)
    if len(runtimes) > 1:
        raise ValueError("Evaluate different model runtime identities in separate runs")
    return {
        "schema_version": "tender-semantic-experiment-report-v1",
        "dataset_sha256": digest(dataset.model_dump(mode="json")),
        "results_sha256": digest(results),
        "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "assessor_implementation_sha256": hashlib.sha256(Path(__file__).with_name("tender_semantic.py").read_bytes()).hexdigest(),
        "threshold": threshold,
        "runtime_identity_sha256": next(iter(runtimes), None),
        "metrics": metrics(rows),
        "by_split": {split: metrics([row for row in rows if row["split"] == split])
                     for split in ("development", "validation")},
        "by_split_locale": {key: metrics(value) for key, value in sorted(groups.items())},
        "cases": rows,
        "promotion_allowed": False,
        "limitations": ["Author-supplied development/validation labels are not independent held-out review.",
                        "Exact citations do not establish semantic correctness or legal eligibility.",
                        "Source permission and model/reviewer authenticity are not established by hashes.",
                        "This report cannot activate semantic matching or change a user decision."],
    }
