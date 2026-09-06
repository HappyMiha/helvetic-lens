"""Run the actual topic scorer offline; never use app DB URLs or gold labels."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .config import DomainError
from .db import Base
from .models import (
    MonitoringTopicRevision,
    RegulatoryEvent,
    RegulatoryExpression,
    RegulatoryIdentifier,
    RegulatoryWork,
    SourcePackDefinition,
)
from .monitoring_topics import TopicDraftOutput, normalize_plan
from .semantic_matching_eval import Contract, Dataset, Identifier, Predictions, Split, digest
from .topic_matching import EVALUATION_REVISION, RULE_REVISION, score_event


class WorkInput(Contract):
    title: str = Field(max_length=10000)
    kind: str = Field(min_length=1, max_length=80)
    authority: str = Field(min_length=1, max_length=80)
    metadata: dict = Field(default_factory=dict)


class EventInput(Contract):
    event_type: str = Field(min_length=1, max_length=80)
    connector: str = Field(min_length=1, max_length=80)
    impact: str = Field(min_length=1, max_length=20)
    evidence: dict = Field(default_factory=dict)


class ExpressionInput(Contract):
    title: str = Field(max_length=10000)
    language: str = Field(min_length=1, max_length=20)


class IdentifierInput(Contract):
    scheme: str = Field(min_length=1, max_length=50)
    value: str = Field(min_length=1, max_length=2000)
    normalized_value: str = Field(min_length=1, max_length=700)


class PackInput(Contract):
    id: Identifier
    revision: str = Field(min_length=1, max_length=40)
    streams: list[tuple[str, str]] = Field(min_length=1, max_length=100)


class MatchingInput(Contract):
    schema_version: Literal["hl093.matching-input.v1"]
    plan: TopicDraftOutput
    work: WorkInput
    event: EventInput
    expression: ExpressionInput | None = None
    identifiers: list[IdentifierInput] = Field(default_factory=list, max_length=100)
    packs: list[PackInput] = Field(min_length=1, max_length=20)


def predict_one(raw: bytes) -> tuple[bool, list[str]]:
    data = MatchingInput.model_validate_json(raw)
    # A fresh memory-only database per case prevents identifier/pack contamination.
    # No Settings/.env loading, source fetch, background worker or application write.
    engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            root = SourcePackDefinition(id="evaluation-root", revision="v1", active=True)
            session.add(root)
            definitions = {}
            for pack in data.packs:
                if pack.id in definitions or pack.id == root.id:
                    raise ValueError("Evaluation source pack IDs must be distinct.")
                definition = SourcePackDefinition(
                    id=pack.id,
                    parent_id=root.id,
                    revision=pack.revision,
                    active=True,
                    filters_json={"streams": pack.streams},
                )
                definitions[pack.id] = definition
                session.add(definition)
            session.flush()
            plan = normalize_plan(data.plan.model_dump(), session)
            work = RegulatoryWork(
                id="evaluation-work",
                kind=data.work.kind,
                authority=data.work.authority,
                canonical_key="evaluation-work",
                title=data.work.title,
                metadata_json=data.work.metadata,
            )
            session.add(work)
            session.flush()
            for identifier in data.identifiers:
                session.add(
                    RegulatoryIdentifier(work_id=work.id, authority=work.authority, **identifier.model_dump())
                )
            session.flush()
            event = RegulatoryEvent(
                work_id=work.id,
                **data.event.model_dump(exclude={"evidence"}),
                evidence_json=data.event.evidence,
            )
            expression = RegulatoryExpression(**data.expression.model_dump()) if data.expression else None
            revision = MonitoringTopicRevision(
                **{
                    (key if key in {"name", "goal", "importance_floor"} else key + "_json"): value
                    for key, value in plan.items()
                }
            )
            scored = score_event(session, event, work, expression, revision, definitions)
            return scored is not None, sorted({signal["type"] for signal in scored[1]}) if scored else [
                "no_match"
            ]
    finally:
        engine.dispose()


def implementation_identity(repo: Path) -> dict:
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=repo, text=True).strip())
    package = repo / "services" / "api" / "helvetic_lens"
    files = {
        path.relative_to(repo).as_posix(): digest(path.read_bytes()) for path in sorted(package.glob("*.py"))
    }
    files["scripts/evaluate_semantic_matching.py"] = digest(
        (repo / "scripts" / "evaluate_semantic_matching.py").read_bytes()
    )
    return {
        "system_revision": revision,
        "working_tree_dirty": dirty,
        "implementation_sha256": digest(json.dumps(files, sort_keys=True).encode()),
    }


def run_baseline(
    dataset: Dataset, dataset_hash: str, artifacts: dict[str, bytes], split: Split, identity: dict
) -> dict:
    rows = []
    for case in dataset.cases:
        if case.split != split:
            continue
        start = time.perf_counter()
        try:
            relevant, reasons = predict_one(artifacts[case.input.path])
            status = "ok"
        except DomainError as error:
            relevant, reasons, status = None, [error.code], "error"
        except (ValueError, TypeError, KeyError, SQLAlchemyError):
            relevant, reasons, status = None, ["invalid_baseline_input"], "error"
        rows.append(
            {
                "case_id": case.id,
                "input_sha256": case.input.sha256,
                "status": status,
                "relevant": relevant,
                "reason_codes": reasons,
                "latency_ms": (time.perf_counter() - start) * 1000,
            }
        )
    result = {
        "schema_version": "hl093.matching-predictions.v1",
        "dataset_sha256": dataset_hash,
        "split": split,
        "run_id": "topic-scorer-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"),
        "created_at": datetime.now(UTC).isoformat(),
        "system": "production-topic-scorer",
        **identity,
        "configuration_sha256": digest(
            json.dumps(
                {
                    "rule": RULE_REVISION,
                    "evaluator": EVALUATION_REVISION,
                    "selection": "all_cases_in_requested_split",
                    "input_schema": "hl093.matching-input.v1",
                },
                sort_keys=True,
            ).encode()
        ),
        "rows": rows,
    }
    return Predictions.model_validate_json(json.dumps(result)).model_dump(mode="json")
