"""Offline B2/B7/B8 evidence accounting. Never approves a runtime capability.

Hashes prove package integrity, not permission or reviewer authenticity. A human
must verify those attestations and inspect the complete captured system output.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from . import semantic_matching_eval as common

Business = Literal["B2", "B7", "B8"]
BUSINESSES = ("B2", "B7", "B8")


class Permission(common.Contract):
    schema_version: Literal["mv2.evaluation-permission.v1"]
    snapshot_sha256: common.Digest
    permitted_fields: list[common.Identifier] = Field(min_length=1, max_length=256)
    evaluation_allowed: bool
    reference: str = Field(min_length=1, max_length=1000)
    reviewed_at: AwareDatetime
    valid_until: AwareDatetime

    @model_validator(mode="after")
    def interval(self):
        if self.reviewed_at >= self.valid_until or len(set(self.permitted_fields)) != len(self.permitted_fields):
            raise ValueError("Invalid evaluation permission interval or duplicate fields")
        return self


class Source(common.Source):
    # Source artifacts are normalized flat JSON maps: exact field ID -> text.
    # Normalization provenance belongs in the input artifact and permission.
    permission: common.Artifact


class Case(common.Case):
    source_type: Business
    sources: list[Source] = Field(min_length=1, max_length=10)
    release_critical: bool


class Dataset(common.Dataset):
    schema_version: Literal["mv2.business-dataset.v1"]
    provenance: Literal["permitted_source", "synthetic_fixture"]
    cases: list[Case] = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def distinct_pairs(self):
        keys = [(case.source_type, case.input.sha256, tuple(sorted(s.artifact.sha256 for s in case.sources)))
            for case in self.cases]
        if len(keys) != len(set(keys)):
            raise ValueError("Repeated input/source pairs cannot inflate evaluation counts")
        return self


class Reviewer(common.Reviewer):
    businesses: list[Business] = Field(min_length=1, max_length=3)


class Citation(common.Quote):
    field: common.Identifier


class Vote(common.Vote):
    citations: list[Citation] = Field(min_length=1, max_length=10)


class Label(common.Label):
    votes: list[Vote] = Field(max_length=5)
    adjudication: Vote | None = None


class Labels(common.Labels):
    schema_version: Literal["mv2.business-labels.v1"]
    reviewers: list[Reviewer] = Field(max_length=100)
    labels: list[Label] = Field(max_length=2000)


class Prediction(common.Prediction):
    output: common.Artifact
    citations: list[Citation] = Field(max_length=50)


class Predictions(common.Predictions):
    schema_version: Literal["mv2.business-predictions.v1"]
    # Captured configurations/runtime manifests are local artifacts, not claims
    # established by a SHA alone. They must contain no credentials.
    configuration: common.Artifact
    implementation: common.Artifact
    rows: list[Prediction] = Field(max_length=2000)

    @model_validator(mode="after")
    def manifest_binding(self):
        if (self.configuration.sha256 != self.configuration_sha256
                or self.implementation.sha256 != self.implementation_sha256):
            raise ValueError("Run manifests differ from their declared hashes")
        return self


class AuditVote(common.Contract):
    reviewer_id: common.Identifier
    decision_matches_output: bool
    citations_complete: bool
    invented_facts: int = Field(ge=0, le=10000)
    invented_deadlines: int = Field(ge=0, le=10000)
    rationale: str = Field(min_length=12, max_length=2000)

    def verdict(self):
        return (self.decision_matches_output, self.citations_complete, self.invented_facts, self.invented_deadlines)


class Audit(common.Contract):
    case_id: common.Identifier
    output_sha256: common.Digest
    votes: list[AuditVote] = Field(max_length=5)
    adjudication: AuditVote | None = None

    @model_validator(mode="after")
    def distinct_votes(self):
        ids = [vote.reviewer_id for vote in self.votes]
        if len(ids) != len(set(ids)) or (self.adjudication and self.adjudication.reviewer_id in ids):
            raise ValueError("Output audit needs distinct reviewers and adjudicator")
        return self


class Audits(common.Contract):
    schema_version: Literal["mv2.business-audits.v1"]
    dataset_sha256: common.Digest
    predictions_sha256: common.Digest
    reviewed_at: AwareDatetime
    review_reference: str = Field(min_length=1, max_length=1000)
    reviewers: list[Reviewer] = Field(max_length=100)
    rows: list[Audit] = Field(max_length=2000)

    @model_validator(mode="after")
    def unique(self):
        if (len({row.id for row in self.reviewers}) != len(self.reviewers)
                or len({row.case_id for row in self.rows}) != len(self.rows)):
            raise ValueError("Duplicate audit case or reviewer")
        return self


class Package:
    """One bounded cache across inputs, sources, permissions and full outputs."""

    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        self.artifacts = {}
        self.size = 0
        self.processed_size = 0

    def read(self, ref):
        if ref.path not in self.artifacts:
            path = (self.root / ref.path).resolve(strict=True)
            if not path.is_relative_to(self.root):
                raise ValueError("Artifact escapes evaluation root")
            raw = common.read_bounded(path)
            self.size += len(raw)
            if self.size > common.MAX_PACKAGE_BYTES:
                raise ValueError("Evaluation package exceeds total read budget")
            self.artifacts[ref.path] = raw
        raw = self.artifacts[ref.path]
        self.processed_size += len(raw)
        if self.processed_size > common.MAX_PACKAGE_BYTES:
            raise ValueError("Evaluation repeated-artifact processing exceeds total budget")
        if common.digest(raw) != ref.sha256:
            raise ValueError("Evaluation artifact checksum mismatch")
        return raw


def _citation_valid(citation, fields, permissions):
    permission = permissions.get(citation.source_id)
    source = fields.get(citation.source_id, {})
    return bool(permission and citation.field in permission.permitted_fields
        and citation.field in source and citation.quote in source[citation.field])


def _audit(case, row, output, reviewers, excluded):
    if row.output_sha256 != output.output.sha256:
        raise ValueError("Audit names a different captured output")
    reasons = set()
    for vote in [*row.votes, *([row.adjudication] if row.adjudication else [])]:
        reviewer = reviewers.get(vote.reviewer_id)
        if reviewer is None:
            raise ValueError("Unregistered output reviewer")
        if vote.reviewer_id in excluded or not reviewer.independent_of_system:
            reasons.add("output_reviewer_not_independent")
        if case.locale not in reviewer.fluent_locales or case.source_type not in reviewer.businesses:
            reasons.add("output_reviewer_scope_missing")
    different = len({vote.verdict() for vote in row.votes}) > 1
    if row.adjudication and not different:
        raise ValueError("An audit adjudication cannot replace reviewer agreement")
    if len(row.votes) < 2:
        reasons.add("two_output_reviewers_required")
    if different and not row.adjudication:
        reasons.add("output_audit_disagreement")
    resolved = None if reasons else row.adjudication if different else row.votes[0]
    return resolved, sorted(reasons), different


def evaluate(root, dataset_path, labels_path, predictions_path, audits_path):
    dataset, dataset_hash = common.load_contract(dataset_path, Dataset)
    labels, labels_hash = common.load_contract(labels_path, Labels)
    predictions, predictions_hash = common.load_contract(predictions_path, Predictions)
    audits, audits_hash = common.load_contract(audits_path, Audits)
    if (any(value != dataset_hash for value in (labels.dataset_sha256, predictions.dataset_sha256,
            audits.dataset_sha256)) or audits.predictions_sha256 != predictions_hash):
        raise ValueError("Evaluation files name different frozen revisions")
    if not labels.frozen_at <= predictions.created_at <= audits.reviewed_at:
        raise ValueError("Required order is frozen gold, captured run, output review")
    package = Package(root)
    for ref in (predictions.configuration, predictions.implementation):
        common.strict_json(package.read(ref))
    fields, permissions, flattened = {}, {}, {}
    rights_failures = {}
    canonical_pairs, canonical_splits = set(), {}
    for case in dataset.cases:
        input_value = common.strict_json(package.read(case.input))
        content_hashes = []
        fields[case.id], permissions[case.id] = {}, {}
        for source in case.sources:
            raw = package.read(source.artifact)
            content = common.strict_json(raw)
            if (not isinstance(content, dict) or not 1 <= len(content) <= 256
                    or any(not isinstance(value, str) for value in content.values())):
                raise ValueError("Source snapshot must be a bounded map of field IDs to text")
            permission_raw = package.read(source.permission)
            common.strict_json(permission_raw)
            permission = Permission.model_validate_json(permission_raw)
            if permission.snapshot_sha256 != source.artifact.sha256:
                raise ValueError("Permission names a different source snapshot")
            if (not permission.evaluation_allowed
                    or not permission.reviewed_at <= labels.frozen_at <= predictions.created_at
                        <= audits.reviewed_at < permission.valid_until):
                rights_failures.setdefault(case.id, []).append(source.id)
            fields[case.id][source.id] = content
            permissions[case.id][source.id] = permission
            flattened[source.artifact.path] = "\n".join(content.values()).encode()
            content_hashes.append(common.digest(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()))
        input_hash = common.digest(json.dumps(input_value, sort_keys=True, ensure_ascii=False).encode())
        pair = (case.source_type, input_hash, tuple(sorted(content_hashes)))
        if pair in canonical_pairs:
            raise ValueError("Reformatted duplicate pairs cannot inflate evaluation counts")
        canonical_pairs.add(pair)
        for content_hash in [input_hash, *content_hashes]:
            if canonical_splits.get(content_hash, case.split) != case.split:
                raise ValueError("Reformatted source/input leaks across evaluation splits")
            canonical_splits[content_hash] = case.split
    cases = {case.id: case for case in dataset.cases}
    gold_reviewers = {row.id: row for row in labels.reviewers}
    for label in labels.labels:
        if label.case_id not in cases:
            raise ValueError("Unknown labelled case")
        for vote in [*label.votes, *([label.adjudication] if label.adjudication else [])]:
            if any(not _citation_valid(cite, fields[label.case_id], permissions[label.case_id])
                    for cite in vote.citations):
                raise ValueError("Gold label lacks exact permitted snapshot/field quotation")
    expected, pending, disagreements = common.resolve_labels(dataset, labels, flattened)
    for label in labels.labels:
        votes = [*label.votes, *([label.adjudication] if label.adjudication else [])]
        if any(cases[label.case_id].source_type not in gold_reviewers[v.reviewer_id].businesses for v in votes):
            expected.pop(label.case_id, None)
            pending.setdefault(label.case_id, []).append("gold_reviewer_business_missing")
    partition = {key: case for key, case in cases.items() if case.split == predictions.split}
    outputs = {row.case_id: row for row in predictions.rows}
    for output in predictions.rows:
        case = partition.get(output.case_id)
        if case is None or output.input_sha256 != case.input.sha256:
            raise ValueError("Prediction has unknown case, wrong split or input hash")
        if not package.read(output.output).decode("utf-8").strip():
            raise ValueError("Captured output cannot be empty")
    audit_rows = {row.case_id: row for row in audits.rows}
    if set(audit_rows) - set(outputs):
        raise ValueError("Audit has no captured prediction")
    if any(row.output_sha256 != outputs[row.case_id].output.sha256 for row in audits.rows):
        raise ValueError("Audit names a different captured output")
    audit_reviewers = {row.id: row for row in audits.reviewers}
    excluded = set(dataset.authors) | {vote.reviewer_id for label in labels.labels
        for vote in [*label.votes, *([label.adjudication] if label.adjudication else [])]}
    rows, audit_pending, audit_disagreements, audit_failures = [], {}, [], []
    citation_count, valid_citations, audited_count = 0, 0, 0
    for case in partition.values():
        output = outputs.get(case.id)
        row = {"case_id": case.id, "business": case.source_type, "locale": case.locale,
            "features": case.features, "expected": expected.get(case.id),
            "predicted": output.relevant if output else None, "status": output.status if output else "missing"}
        rows.append(row)
        if output is None or output.status != "ok":
            audit_pending[case.id] = ["successful_output_required"]
            continue
        citation_count += len(output.citations)
        valid = sum(_citation_valid(cite, fields[case.id], permissions[case.id])
            and cite.source_id not in rights_failures.get(case.id, []) for cite in output.citations)
        valid_citations += valid
        if valid != len(output.citations) or not output.citations:
            audit_failures.append({"case_id": case.id, "reason": "missing_or_invalid_citations"})
        if case.id not in audit_rows:
            audit_pending[case.id] = ["output_not_reviewed"]
            continue
        resolved, reasons, different = _audit(case, audit_rows[case.id], output, audit_reviewers, excluded)
        if different:
            audit_disagreements.append(case.id)
        if reasons:
            audit_pending[case.id] = reasons
        else:
            audited_count += 1
            if (not resolved.decision_matches_output or not resolved.citations_complete
                    or resolved.invented_facts or resolved.invented_deadlines):
                audit_failures.append({"case_id": case.id, "reason": "output_audit_failed",
                    "decision_matches_output": resolved.decision_matches_output,
                    "citations_complete": resolved.citations_complete,
                    "invented_facts": resolved.invented_facts, "invented_deadlines": resolved.invented_deadlines})
    scored = [row for row in rows if row["expected"] is not None]
    by_business = {key: common.metrics([row for row in scored if row["business"] == key]) for key in BUSINESSES}
    blockers, targets = [], []
    counts = Counter(case.source_type for case in dataset.cases if case.id in expected)
    if dataset.provenance != "permitted_source":
        blockers.append("synthetic_dataset_not_independent_evidence")
    if len(expected) < 200:
        blockers.append("fewer_than_200_reviewed_pairs")
    if len(scored) < 50:
        blockers.append("fewer_than_50_scored_partition_pairs")
    for business in BUSINESSES:
        if counts[business] < 50:
            blockers.append(f"{business}:fewer_than_50_reviewed_pairs")
        selected = [row for row in scored if row["business"] == business]
        if {row["expected"] for row in selected} != {False, True}:
            blockers.append(f"{business}:positive_and_negative_coverage_required")
        for locale in common.LOCALES:
            if {row["expected"] for row in selected if row["locale"] == locale} != {False, True}:
                blockers.append(f"{business}:{locale}:positive_and_negative_coverage_required")
        if not any(case.release_critical for case in partition.values() if case.source_type == business):
            blockers.append(f"{business}:release_critical_cases_missing")
        for metric, threshold in (("precision", 0.85), ("recall", 0.90)):
            value = by_business[business][metric]["value"]
            if value is None or value < threshold:
                targets.append(f"{business}:{metric}_below_{threshold}_or_unmeasured")
    if predictions.split != "held_out":
        blockers.append("development_run_not_release_evidence")
    if predictions.working_tree_dirty:
        blockers.append("prediction_implementation_not_clean_revision")
    if pending:
        blockers.append("gold_reviews_incomplete")
    if rights_failures:
        blockers.append("source_permission_not_current_for_review_and_run")
    if not rows or any(row["status"] != "ok" for row in rows):
        blockers.append("prediction_run_incomplete")
    if audit_pending:
        blockers.append("output_reviews_incomplete")
    if audit_failures:
        blockers.append("citation_or_factual_audit_failed")
    return {
        "schema_version": "mv2.business-evaluation.v1", "dataset_sha256": dataset_hash,
        "labels_sha256": labels_hash, "predictions_sha256": predictions_hash, "audits_sha256": audits_hash,
        "configuration_sha256": predictions.configuration_sha256,
        "implementation_sha256": predictions.implementation_sha256,
        "system_revision": predictions.system_revision, "system": predictions.system,
        "run_id": predictions.run_id, "split": predictions.split,
        "reviewed_at": audits.reviewed_at.isoformat(),
        "package_targets_met": not blockers and not targets, "capability_approved": False,
        "attestations_require_external_verification": True,
        "scope": "business_candidate_relevance_not_legal_conflict_accuracy",
        "readiness_blockers": blockers, "target_failures": targets,
        "coverage": {"dataset_cases": len(cases), "reviewed_pairs": len(expected),
            "reviewed_by_business": {key: counts[key] for key in BUSINESSES},
            "partition_cases": len(rows), "scored_pairs": len(scored), "outputs_audited": audited_count},
        "metrics": common.metrics(scored), "by_business": by_business,
        "by_business_locale": {key: {locale: common.metrics([row for row in scored
            if row["business"] == key and row["locale"] == locale]) for locale in common.LOCALES}
            for key in BUSINESSES},
        "negative_examples": {key: common.metrics([row for row in scored
            if row["business"] == key and row["expected"] is False]) for key in BUSINESSES},
        "citation_validity": common.ratio(valid_citations, citation_count),
        "pending_reviews": pending, "disagreements": [row["case_id"] for row in disagreements],
        "pending_output_reviews": audit_pending, "output_disagreements": audit_disagreements,
        "audit_failures": audit_failures, "permission_failures": rights_failures, "rows": rows,
        "unmeasured": ["reviewer_identity_and_independence", "permission_authenticity_and_revocation",
            "captured_run_authenticity", "score_probability_calibration", "legal_conflict_accuracy",
            "target_hardware_capacity", "production_activation", "human_pilot_acceptance"],
    }
