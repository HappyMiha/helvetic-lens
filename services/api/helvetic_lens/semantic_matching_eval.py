"""Offline relevance evaluation. Evidence integrity is not reviewer authenticity.

No model calls, dataset relabelling, capability promotion or database connection.
Gold labels and prediction files are independently supplied and hash-bound.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,119}$")]
Locale = Literal["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]
Split = Literal["development", "held_out"]
SourceType = Literal["fedlex", "parliament", "court", "news", "other"]
LOCALES = ("de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH")
FEATURES = (
    "negative",
    "paraphrase",
    "german_compound",
    "cross_language_reference",
    "scope_exception",
    "high_value",
)
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_PACKAGE_BYTES = 128 * 1024 * 1024


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Artifact(Contract):
    path: str = Field(min_length=1, max_length=240)
    sha256: Digest

    @model_validator(mode="after")
    def safe_relative_path(self):
        parts = self.path.split("/")
        if (
            PurePosixPath(self.path).is_absolute()
            or "\\" in self.path
            or ":" in self.path
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise ValueError(
                "Artifact paths must be relative without traversal, drive names or empty components."
            )
        return self


class Source(Contract):
    id: Identifier
    artifact: Artifact
    # URL is provenance text only; the evaluator never fetches it.
    public_url: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def provenance_url(self):
        url = urlsplit(self.public_url)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
            raise ValueError("Source provenance needs an HTTP(S) URL without embedded credentials.")
        return self


class Case(Contract):
    id: Identifier
    family: Identifier
    split: Split
    locale: Locale
    source_type: SourceType
    features: list[Identifier] = Field(max_length=20)
    input: Artifact
    sources: list[Source] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique_sources(self):
        if len({source.id for source in self.sources}) != len(self.sources):
            raise ValueError("Source IDs must be unique within a case.")
        if len(set(self.features)) != len(self.features):
            raise ValueError("Case features must be unique.")
        return self


class Dataset(Contract):
    schema_version: Literal["hl093.matching-dataset.v1"]
    id: Identifier
    revision: Identifier
    provenance: Literal["public_source", "synthetic_fixture"]
    authors: list[Identifier] = Field(min_length=1, max_length=30)
    cases: list[Case] = Field(max_length=20000)

    @model_validator(mode="after")
    def distinct_cases_and_splits(self):
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Case IDs must be unique.")
        seen = {}
        for case in self.cases:
            # Different wrappers/IDs do not permit the same source in both splits.
            keys = [
                "family:" + case.family,
                "content:" + case.input.sha256,
                *["content:" + source.artifact.sha256 for source in case.sources],
            ]
            for key in keys:
                if key in seen and seen[key] != case.split:
                    raise ValueError(
                        "A family or source/input artifact leaks across development and held-out splits."
                    )
                seen[key] = case.split
        return self


class Reviewer(Contract):
    id: Identifier
    independent_of_system: bool
    fluent_locales: list[Locale] = Field(min_length=1, max_length=5)
    domain_review_reference: str = Field(min_length=1, max_length=500)


class Quote(Contract):
    source_id: Identifier
    quote: str = Field(min_length=8, max_length=2000)


class Vote(Contract):
    reviewer_id: Identifier
    relevant: bool
    rationale: str = Field(min_length=12, max_length=2000)
    citations: list[Quote] = Field(min_length=1, max_length=10)


class Label(Contract):
    case_id: Identifier
    votes: list[Vote] = Field(max_length=5)
    adjudication: Vote | None = None

    @model_validator(mode="after")
    def independent_votes(self):
        ids = [vote.reviewer_id for vote in self.votes]
        if len(set(ids)) != len(ids):
            raise ValueError("One reviewer cannot count as two independent votes.")
        if self.adjudication and self.adjudication.reviewer_id in ids:
            raise ValueError("The adjudicator must be distinct from all initial reviewers.")
        return self


class Labels(Contract):
    schema_version: Literal["hl093.matching-labels.v1"]
    dataset_sha256: Digest
    frozen_at: AwareDatetime
    review_reference: str = Field(min_length=1, max_length=500)
    reviewers: list[Reviewer] = Field(max_length=100)
    labels: list[Label] = Field(max_length=20000)

    @model_validator(mode="after")
    def unique_records(self):
        if len({row.id for row in self.reviewers}) != len(self.reviewers):
            raise ValueError("Reviewer IDs must be unique.")
        if len({row.case_id for row in self.labels}) != len(self.labels):
            raise ValueError("A case cannot have two label records.")
        return self


class Prediction(Contract):
    case_id: Identifier
    input_sha256: Digest
    status: Literal["ok", "abstained", "error"]
    relevant: bool | None
    reason_codes: list[Identifier] = Field(max_length=20)
    latency_ms: float = Field(ge=0)

    @model_validator(mode="after")
    def no_silent_negative(self):
        if (self.relevant is not None) != (self.status == "ok"):
            raise ValueError("Only a successful prediction may have a relevance decision.")
        return self


class Predictions(Contract):
    schema_version: Literal["hl093.matching-predictions.v1"]
    dataset_sha256: Digest
    split: Split
    run_id: Identifier
    created_at: AwareDatetime
    system: Identifier
    system_revision: Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")]
    implementation_sha256: Digest
    configuration_sha256: Digest
    working_tree_dirty: bool
    rows: list[Prediction] = Field(max_length=20000)

    @model_validator(mode="after")
    def unique_predictions(self):
        if len({row.case_id for row in self.rows}) != len(self.rows):
            raise ValueError("Duplicate predictions cannot inflate denominators.")
        return self


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_bounded(path: Path) -> bytes:
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("Evaluation artifact exceeds the eight MiB per-file limit.")
    return raw


def strict_json(raw: bytes):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON keys are not allowed in evaluation artifacts.")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("Nonfinite JSON numbers are not allowed.")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)


def load_contract(path: Path, schema):
    raw = read_bounded(path)
    strict_json(raw)
    return schema.model_validate_json(raw), digest(raw)


def load_dataset(path: Path, root: Path):
    dataset, dataset_hash = load_contract(path, Dataset)
    root = root.resolve(strict=True)
    artifacts = {}
    size = 0
    for case in dataset.cases:
        for ref in [case.input, *[source.artifact for source in case.sources]]:
            target = (root / ref.path).resolve(strict=True)
            if not target.is_relative_to(root):
                raise ValueError("Evaluation artifact escapes the package root.")
            if ref.path not in artifacts:
                raw = read_bounded(target)
                size += len(raw)
                if size > MAX_PACKAGE_BYTES:
                    raise ValueError("Evaluation package exceeds the 128 MiB read budget.")
                artifacts[ref.path] = raw
            if digest(artifacts[ref.path]) != ref.sha256:
                raise ValueError("Evaluation input/source checksum mismatch.")
        strict_json(artifacts[case.input.path])
        for source in case.sources:
            artifacts[source.artifact.path].decode("utf-8")
    return dataset, dataset_hash, artifacts


def resolve_labels(dataset: Dataset, labels: Labels, artifacts: dict[str, bytes]):
    reviewers = {row.id: row for row in labels.reviewers}
    cases = {case.id: case for case in dataset.cases}
    expected, pending, disagreements = {}, {}, []
    for label in labels.labels:
        if label.case_id not in cases:
            raise ValueError("Labels include a case outside the frozen dataset.")
        case = cases[label.case_id]
        sources = {source.id: artifacts[source.artifact.path].decode("utf-8") for source in case.sources}
        reasons = set()
        for vote in [*label.votes, *([label.adjudication] if label.adjudication else [])]:
            reviewer = reviewers.get(vote.reviewer_id)
            if reviewer is None:
                raise ValueError("A vote names an unregistered reviewer.")
            if vote.reviewer_id in dataset.authors or not reviewer.independent_of_system:
                reasons.add("reviewer_not_independent")
            if case.locale not in reviewer.fluent_locales:
                reasons.add("locale_not_reviewed")
            for citation in vote.citations:
                if citation.source_id not in sources or citation.quote not in sources[citation.source_id]:
                    raise ValueError("A gold vote cites missing or changed source wording.")
        if len(label.votes) < 2:
            reasons.add("two_independent_votes_required")
        different = len({vote.relevant for vote in label.votes}) > 1
        if different:
            disagreements.append(
                {
                    "case_id": case.id,
                    "votes": [vote.model_dump() for vote in label.votes],
                    "adjudication": label.adjudication.model_dump() if label.adjudication else None,
                }
            )
            if label.adjudication is None:
                reasons.add("unresolved_disagreement")
        elif label.adjudication is not None:
            raise ValueError(
                "Adjudication cannot override agreement; preserve/revise the original frozen labels instead."
            )
        if reasons:
            pending[case.id] = sorted(reasons)
        else:
            expected[case.id] = label.adjudication.relevant if different else label.votes[0].relevant
    for case in dataset.cases:
        if case.id not in expected and case.id not in pending:
            pending[case.id] = ["unlabelled"]
    return expected, pending, disagreements


def ratio(numerator: int, denominator: int):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def metrics(rows: list[dict]):
    tp = sum(row["expected"] is True and row["predicted"] is True for row in rows)
    fp = sum(row["expected"] is False and row["predicted"] is True for row in rows)
    fn = sum(row["expected"] is True and row["predicted"] is not True for row in rows)
    tn = sum(row["expected"] is False and row["predicted"] is False for row in rows)
    return {
        "cases": len(rows),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "unknown_predictions": sum(row["predicted"] is None for row in rows),
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "false_positive_ids": [
            row["case_id"] for row in rows if row["expected"] is False and row["predicted"] is True
        ],
        "false_negative_ids": [
            row["case_id"] for row in rows if row["expected"] is True and row["predicted"] is not True
        ],
    }


def evaluate(
    dataset: Dataset,
    dataset_hash: str,
    artifacts: dict[str, bytes],
    labels: Labels,
    predictions: Predictions,
    *,
    labels_hash: str,
    predictions_hash: str,
) -> dict:
    if labels.dataset_sha256 != dataset_hash or predictions.dataset_sha256 != dataset_hash:
        raise ValueError("Labels and predictions must name the exact frozen dataset hash.")
    if predictions.created_at < labels.frozen_at:
        raise ValueError("Gold labels must be frozen before the evaluated prediction run.")
    expected, pending, disagreements = resolve_labels(dataset, labels, artifacts)
    cases = [case for case in dataset.cases if case.split == predictions.split]
    by_id = {case.id: case for case in cases}
    outputs = {row.case_id: row for row in predictions.rows}
    for row in predictions.rows:
        if row.case_id not in by_id or row.input_sha256 != by_id[row.case_id].input.sha256:
            raise ValueError("Predictions contain an unknown/wrong-split case or a different input revision.")
    rows = []
    for case in cases:
        output = outputs.get(case.id)
        rows.append(
            {
                "case_id": case.id,
                "locale": case.locale,
                "source_type": case.source_type,
                "features": case.features,
                "expected": expected.get(case.id),
                "predicted": output.relevant if output else None,
                "status": output.status if output else "missing",
                "reason_codes": output.reason_codes if output else [],
            }
        )
    scored = [row for row in rows if row["expected"] is not None]
    overall = metrics(scored)
    strata = {}
    for dimension in ("locale", "source_type", "features"):
        groups = defaultdict(list)
        for row in scored:
            for key in row[dimension] if dimension == "features" else [row[dimension]]:
                groups[key].append(row)
        known = (
            LOCALES
            if dimension == "locale"
            else ("fedlex", "parliament", "court", "news", "other")
            if dimension == "source_type"
            else FEATURES
        )
        strata[dimension] = {key: metrics(groups[key]) for key in sorted(set(known) | set(groups))}
    reviewed_cases = [case for case in dataset.cases if case.id in expected]
    held_out = [case for case in reviewed_cases if case.split == "held_out"]
    locale_counts = Counter(case.locale for case in held_out)
    source_counts = Counter(case.source_type for case in held_out)
    feature_counts = Counter(feature for case in held_out for feature in case.features)
    blockers = []
    if dataset.provenance != "public_source":
        blockers.append("synthetic_dataset_not_independent_evidence")
    if len(reviewed_cases) < 200:
        blockers.append("fewer_than_200_reviewed_pairs")
    if len(held_out) < 50:
        blockers.append("fewer_than_50_held_out_pairs")
    if any(locale_counts[locale] < 5 for locale in LOCALES):
        blockers.append("held_out_locale_coverage_incomplete")
    if any(
        {expected[case.id] for case in held_out if case.locale == locale} != {False, True}
        for locale in LOCALES
    ):
        blockers.append("held_out_each_locale_needs_positive_and_negative_pairs")
    if any(source_counts[source] < 5 for source in ("fedlex", "parliament", "court")):
        blockers.append("held_out_core_source_coverage_incomplete")
    if any(not feature_counts[feature] for feature in FEATURES):
        blockers.append("held_out_edge_case_coverage_incomplete")
    if pending:
        blockers.append("gold_reviews_pending")
    if not any(expected.get(case.id) is True for case in held_out) or not any(
        expected.get(case.id) is False for case in held_out
    ):
        blockers.append("held_out_requires_positive_and_negative_pairs")
    if predictions.split != "held_out":
        blockers.append("development_run_not_release_evidence")
    if predictions.working_tree_dirty:
        blockers.append("prediction_implementation_not_clean_revision")
    if any(row["status"] != "ok" for row in rows):
        blockers.append("prediction_run_incomplete")
    if not rows:
        blockers.append("empty_prediction_partition")
    precision, recall = overall["precision"]["value"], overall["recall"]["value"]
    target_failures = []
    if precision is None or precision < 0.85:
        target_failures.append("precision_below_0.85_or_unmeasured")
    if recall is None or recall < 0.90:
        target_failures.append("recall_below_0.90_or_unmeasured")
    return {
        "schema_version": "hl093.matching-evaluation.v1",
        "dataset_id": dataset.id,
        "dataset_sha256": dataset_hash,
        "labels_sha256": labels_hash,
        "predictions_sha256": predictions_hash,
        "run_id": predictions.run_id,
        "split": predictions.split,
        "system": predictions.system,
        "system_revision": predictions.system_revision,
        "implementation_sha256": predictions.implementation_sha256,
        "configuration_sha256": predictions.configuration_sha256,
        "review_reference": labels.review_reference,
        "independence_is_attestation_not_verified_identity": True,
        "coverage": {
            "dataset_cases": len(dataset.cases),
            "reviewed_pairs": len(expected),
            "held_out_reviewed": len(held_out),
            "partition_cases": len(cases),
            "scored_pairs": len(scored),
            "predictions_received": len(outputs),
            "held_out_by_locale": {locale: locale_counts[locale] for locale in LOCALES},
            "held_out_by_source": {
                source: source_counts[source] for source in ("fedlex", "parliament", "court", "news", "other")
            },
            "held_out_by_feature": {
                feature: feature_counts[feature] for feature in sorted(set(FEATURES) | set(feature_counts))
            },
        },
        "readiness_blockers": blockers,
        "target_failures": target_failures,
        "matching_target_met": not blockers and not target_failures,
        "explanation_capability_approved": False,
        "unmeasured": [
            "factual_entailment",
            "material_omissions",
            "action_usefulness",
            "language_quality",
            "human_comprehension",
            "target_hardware_capacity",
        ],
        "metrics": overall,
        "strata": strata,
        "pending_reviews": pending,
        "vote_disagreement": ratio(len(disagreements), sum(len(label.votes) >= 2 for label in labels.labels)),
        "disagreements": disagreements,
        "rows": rows,
    }
