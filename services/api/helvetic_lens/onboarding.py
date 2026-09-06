"""Personal introduction state and honest organization setup availability."""

from datetime import UTC
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .config import DomainError
from .corpus_access import accessible_versions, visible
from .db import utcnow
from .models import (
    DocumentWatch,
    Law,
    MonitoringTopic,
    OnboardingMilestone,
    RegulatoryDocumentVersion,
    SourcePackSubscription,
    UserOnboarding,
    Version,
)


class OnboardingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["topic", "law", "explore", "later"]


def needed(session, organization_id, principal_key):
    return not bool(
        session.scalar(
            select(UserOnboarding.id)
            .where(
                UserOnboarding.organization_id == organization_id,
                UserOnboarding.principal_key == principal_key,
            )
            .limit(1)
        )
    )


def read(session, organization_id, principal_key):
    state = session.execute(
        select(
            UserOnboarding.intent,
            UserOnboarding.started_at,
            UserOnboarding.deferred_at,
            UserOnboarding.updated_at,
        ).where(
            UserOnboarding.organization_id == organization_id, UserOnboarding.principal_key == principal_key
        )
    ).first()
    packs, documents, topics = session.execute(
        select(
            select(SourcePackSubscription.id)
            .where(
                SourcePackSubscription.organization_id == organization_id,
                SourcePackSubscription.enabled.is_(True),
            )
            .exists(),
            select(DocumentWatch.id)
            .join(Law, Law.id == DocumentWatch.law_id)
            .where(
                DocumentWatch.organization_id == organization_id,
                DocumentWatch.active.is_(True),
                visible(Law, organization_id),
            )
            .exists(),
            select(MonitoringTopic.id)
            .where(MonitoringTopic.organization_id == organization_id, MonitoringTopic.status == "active")
            .exists(),
        )
    ).one()

    def timestamp(value):
        if value is None:
            return None
        return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).isoformat()

    milestones = session.execute(
        select(OnboardingMilestone.kind, OnboardingMilestone.object_kind, OnboardingMilestone.recorded_at)
        .where(
            OnboardingMilestone.organization_id == organization_id,
            OnboardingMilestone.principal_key == principal_key,
        )
        .order_by(OnboardingMilestone.recorded_at, OnboardingMilestone.kind)
    ).all()
    return {
        "milestones": [
            {"kind": item.kind, "object_kind": item.object_kind, "recorded_at": timestamp(item.recorded_at)}
            for item in milestones
        ],
        "state": "new" if state is None else "deferred" if state.deferred_at else "started",
        "intent": state.intent if state else None,
        "started_at": timestamp(state.started_at) if state else None,
        "deferred_at": timestamp(state.deferred_at) if state else None,
        "updated_at": timestamp(state.updated_at) if state else None,
        "visibility": "personal",
        "completion_verified": False,
        "organization_setup": {
            "source_package_enabled": bool(packs),
            "active_document_watch": bool(documents),
            "active_topic": bool(topics),
        },
    }


def save(session, organization_id, principal_key, user_id, action):
    # A unique insert plus row lock coalesces first-use requests from two tabs.
    insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
    now = utcnow()
    session.execute(
        insert(UserOnboarding)
        .values(
            organization_id=organization_id,
            principal_key=principal_key,
            user_id=user_id,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(index_elements=["organization_id", "principal_key"])
    )
    record = session.scalar(
        select(UserOnboarding)
        .where(
            UserOnboarding.organization_id == organization_id, UserOnboarding.principal_key == principal_key
        )
        .with_for_update()
    )
    if action == "later":
        if record.deferred_at is None:
            record.deferred_at = now
            record.updated_at = now
    elif record.intent != action or record.deferred_at is not None:
        record.intent = action
        record.started_at = record.started_at or now
        record.deferred_at = None
        record.updated_at = now
    session.commit()
    return read(session, organization_id, principal_key)


class EvidenceDisplayInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["version", "native_version"]
    id: str = Field(min_length=1, max_length=36)


def record(session, organization_id, user_id, kind, object_kind, object_id=None):
    """Join the caller's transaction: never commit business data independently."""
    insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
    principal = f"user:{user_id}" if user_id else "anonymous-development"
    session.execute(
        insert(OnboardingMilestone)
        .values(
            organization_id=organization_id,
            principal_key=principal,
            user_id=user_id,
            kind=kind,
            object_kind=object_kind,
            object_id=object_id,
            recorded_at=utcnow(),
        )
        .on_conflict_do_nothing(index_elements=["organization_id", "principal_key", "kind"])
    )


def evidence_displayed(session, organization_id, user_id, kind, version_id):
    # Check current access with scalar fields, never trust a browser completion flag.
    if kind == "native_version":
        query = accessible_versions(organization_id).where(RegulatoryDocumentVersion.id == version_id)
        row = session.execute(
            query.with_only_columns(
                RegulatoryDocumentVersion.id,
                RegulatoryDocumentVersion.metadata_json["synthetic"].as_string(),
                func.length(func.trim(RegulatoryDocumentVersion.text)),
            )
        ).first()
    else:
        row = session.execute(
            select(Version.id, Version.synthetic, func.length(func.trim(Version.text)))
            .join(Law, Law.id == Version.law_id)
            .where(Version.id == version_id, visible(Version, organization_id), visible(Law, organization_id))
        ).first()
    if row is None:
        raise DomainError("The saved source evidence is unavailable in this organization.", 404, "not_found")
    if row[1] not in (None, False, 0, "false") or not row[2]:
        return {"recorded": False, "reason": "sample_or_empty_evidence"}
    record(session, organization_id, user_id, "evidence_displayed", kind, version_id)
    session.commit()
    return {"recorded": True}
