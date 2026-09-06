"""Personal introduction state and honest organization setup availability."""

from datetime import UTC
from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .corpus_access import visible
from .db import utcnow
from .models import DocumentWatch, Law, MonitoringTopic, SourcePackSubscription, UserOnboarding


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

    return {
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
