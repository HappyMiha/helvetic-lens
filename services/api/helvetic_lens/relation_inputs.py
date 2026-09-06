"""Compact persisted evidence identity, shared by execution and SQL freshness.

No archived passages are hydrated during inbox selection. Revisions are advanced
by database triggers, including bulk SQL corrections that bypass ORM callbacks.
"""

from sqlalchemy import String, cast, func, select

from .models import (
    EvidenceRevisionEpoch,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryRelation,
    RegulatoryWork,
    RelationCandidate,
    Version,
)

INPUT_NAMES = (
    "candidate",
    "event",
    "source_work",
    "target_work",
    "source_version",
    "target_version",
    "target_legacy",
    "official_relation",
)
INPUT_FIELDS = ("epoch",) + tuple(f"{name}_{field}" for name in INPUT_NAMES for field in ("id", "revision"))


def input_query(organization_id):
    candidate = RelationCandidate.__table__.alias("evidence_candidate")
    event = RegulatoryEvent.__table__.alias("evidence_event")
    source = RegulatoryWork.__table__.alias("evidence_source_work")
    target = RegulatoryWork.__table__.alias("evidence_target_work")
    source_version = RegulatoryDocumentVersion.__table__.alias("evidence_source_version")
    target_version = RegulatoryDocumentVersion.__table__.alias("evidence_target_version")
    legacy = Version.__table__.alias("evidence_target_legacy")
    relation = RegulatoryRelation.__table__.alias("evidence_official_relation")
    epoch = EvidenceRevisionEpoch.__table__.alias("evidence_epoch")
    tables = (candidate, event, source, target, source_version, target_version, legacy, relation)
    columns = {"epoch": epoch.c.epoch}
    for name, table in zip(INPUT_NAMES, tables):
        columns[name + "_id"] = func.coalesce(table.c.id, "")
        columns[name + "_revision"] = func.coalesce(cast(table.c.evidence_revision, String), "")
    query = (
        select(*(column.label(key) for key, column in columns.items()))
        .select_from(candidate)
        .join(epoch, epoch.c.id == "inputs")
        .join(event, event.c.id == candidate.c.event_id)
        .join(source, source.c.id == candidate.c.source_work_id)
        .join(target, target.c.id == candidate.c.target_work_id)
        .outerjoin(source_version, source_version.c.id == candidate.c.source_version_id)
        .outerjoin(target_version, target_version.c.id == candidate.c.target_version_id)
        .outerjoin(
            legacy,
            (legacy.c.id == target_version.c.legacy_version_id)
            & (
                (legacy.c.owner_organization_id.is_(None))
                | (legacy.c.owner_organization_id == organization_id)
            ),
        )
        .outerjoin(relation, relation.c.id == candidate.c.relation_id)
    )
    return query, candidate, columns


def capture_inputs(session, candidate_id: str) -> dict:
    session.flush()
    query, candidate, _ = input_query(session.info.get("organization_id"))
    return dict(session.execute(query.where(candidate.c.id == candidate_id)).mappings().one())


def uses_inputs(plan: dict | None, expected: dict) -> bool:
    execution = plan.get("execution") if isinstance(plan, dict) else None
    saved = execution.get("evidence_binding") if isinstance(execution, dict) else None
    return isinstance(saved, dict) and all(saved.get(key) == expected[key] for key in INPUT_FIELDS)


def matching_inputs_predicate(model):
    query, candidate, columns = input_query(model.organization_id)
    return (
        query.where(
            candidate.c.id == model.candidate_id,
            *(
                column == model.analysis_plan["execution"]["evidence_binding"][key].as_string()
                for key, column in columns.items()
            ),
        )
        .correlate(model)
        .exists()
    )
