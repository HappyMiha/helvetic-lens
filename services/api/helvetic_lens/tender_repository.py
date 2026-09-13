"""Private B2 persistence. Callers own transactions; no source actions or email.

Only a server-authenticated actor may call these operations. Evidence ingestion
is a worker boundary in tender_observations, never request-body supplied facts.
"""

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError

from .config import DomainError
from .models import User
from .monitoring_subjects import _actor, _savepoint
from .simap_sources import PublicationEmbargo, aware, parse_publication
from .tender_contracts import TenderProfile
from .tender_models import (
    TenderDecision,
    TenderDossier,
    TenderDossierVersion,
    TenderMonitor,
    TenderProfileRevision,
)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def configuration(value):
    try:
        profile = TenderProfile.model_validate(value)
    except ValidationError:
        raise DomainError("Invalid tender profile.", 422, "tender_profile_invalid") from None
    return profile.model_dump(mode="json"), profile.fingerprint()


def request_key(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 100 or any(ord(c) < 32 for c in value):
        raise DomainError("A bounded request key is required.", 422, "tender_request_key_invalid")


def positive(value):
    if type(value) is not int or value < 1:
        raise DomainError("A positive version is required.", 422, "tender_version_invalid")


def limit_value(limit):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise DomainError("Choose a page size from 1 to 100.", 422, "tender_limit_invalid")


def owned(session, user_id, monitor_id, *, write=False):
    organization = _actor(session, user_id, write=write)
    row = session.scalar(
        select(TenderMonitor)
        .where(
            TenderMonitor.id == monitor_id,
            TenderMonitor.organization_id == organization,
            TenderMonitor.owner_user_id == user_id,
        )
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise DomainError("Tender monitor not found.", 404, "tender_not_found")
    return row


def timestamp(value):
    if value is None:
        return None
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)).isoformat()


def view(row):
    return {
        "id": row.id,
        "configuration": deepcopy(row.configuration),
        "revision": row.revision,
        "version": row.version,
        "status": row.status,
        "health": row.health,
        "semantic_status": "disabled",
        "last_poll_at": timestamp(row.last_poll_at),
        "next_poll_at": timestamp(row.next_poll_at),
        "source_scope": "public_publications",
        "document_coverage": "not_verified",
        "qa_coverage": "not_verified",
    }


def get_monitor(session, user_id, monitor_id):
    return view(owned(session, user_id, monitor_id))


def list_monitors(session, user_id, *, limit=50, after_id=None):
    organization = _actor(session, user_id)
    limit_value(limit)
    statement = select(TenderMonitor).where(
        TenderMonitor.organization_id == organization, TenderMonitor.owner_user_id == user_id
    )
    if after_id:
        anchor = owned(session, user_id, after_id)
        statement = statement.where(
            or_(
                TenderMonitor.created_at < anchor.created_at,
                and_(TenderMonitor.created_at == anchor.created_at, TenderMonitor.id > anchor.id),
            )
        )
    rows = list(
        session.scalars(
            statement.order_by(TenderMonitor.created_at.desc(), TenderMonitor.id).limit(limit + 1)
        )
    )
    return {
        "items": [view(row) for row in rows[:limit]],
        "next_cursor": rows[limit - 1].id if len(rows) > limit else None,
    }


def create_profile(session, user_id, payload, key):
    organization = _actor(session, user_id, write=True)
    request_key(key)
    config, hashed = configuration(payload)

    def previous():
        return session.scalar(
            select(TenderMonitor)
            .where(
                TenderMonitor.organization_id == organization,
                TenderMonitor.owner_user_id == user_id,
                TenderMonitor.request_key == key,
            )
            .execution_options(populate_existing=True)
        )

    def replay(row):
        if row.request_hash != hashed:
            raise DomainError("This save request has different settings.", 409, "tender_request_conflict")
        return view(row)

    if row := previous():
        return replay(row)
    # Serialize quota checks for this owner on PostgreSQL, where COUNT itself
    # cannot protect a limit against simultaneous distinct creation requests.
    session.scalar(select(User).where(User.id == user_id).with_for_update())
    if (
        session.scalar(
            select(func.count())
            .select_from(TenderMonitor)
            .where(
                TenderMonitor.organization_id == organization,
                TenderMonitor.owner_user_id == user_id,
            )
        )
        >= 50
    ):
        raise DomainError("Archive or reuse an existing tender profile.", 409, "tender_monitor_limit")
    try:
        with _savepoint(session):
            row = TenderMonitor(
                organization_id=organization,
                owner_user_id=user_id,
                request_key=key,
                request_hash=hashed,
                configuration=config,
                status="draft",
                revision=1,
                version=1,
            )
            session.add(row)
            session.flush()
            session.add(
                TenderProfileRevision(
                    organization_id=organization,
                    monitor_id=row.id,
                    revision=1,
                    configuration=config,
                    configuration_hash=hashed,
                )
            )
            session.flush()
    except IntegrityError:
        if row := previous():
            return replay(row)
        raise
    return view(row)


def revise_profile(session, user_id, monitor_id, version, payload):
    row = owned(session, user_id, monitor_id, write=True)
    positive(version)
    if row.version != version:
        raise DomainError("The profile changed. Reload before editing.", 409, "tender_version_conflict")
    config, hashed = configuration(payload)
    revision = row.revision + 1
    with _savepoint(session):
        changed = session.execute(
            update(TenderMonitor)
            .where(
                TenderMonitor.id == row.id,
                TenderMonitor.organization_id == row.organization_id,
                TenderMonitor.owner_user_id == user_id,
                TenderMonitor.version == version,
                TenderMonitor.status.in_(("draft", "paused")),
            )
            .values(configuration=config, revision=revision, version=version + 1, health="waiting")
            .execution_options(synchronize_session=False)
        )
        if changed.rowcount != 1:
            raise DomainError(
                "The profile changed or must be paused before editing.", 409, "tender_version_conflict"
            )
        session.add(
            TenderProfileRevision(
                organization_id=row.organization_id,
                monitor_id=row.id,
                revision=revision,
                configuration=config,
                configuration_hash=hashed,
            )
        )
        session.flush()
    return get_monitor(session, user_id, monitor_id)


def profile_history(session, user_id, monitor_id, *, limit=50, before_revision=None):
    monitor = owned(session, user_id, monitor_id)
    limit_value(limit)
    statement = select(TenderProfileRevision).where(
        TenderProfileRevision.monitor_id == monitor_id,
        TenderProfileRevision.organization_id == monitor.organization_id,
    )
    if before_revision is not None:
        positive(before_revision)
        statement = statement.where(TenderProfileRevision.revision < before_revision)
    rows = list(session.scalars(statement.order_by(TenderProfileRevision.revision.desc()).limit(limit + 1)))
    return {
        "items": [
            {
                "revision": row.revision,
                "configuration": deepcopy(row.configuration),
                "configuration_hash": row.configuration_hash,
            }
            for row in rows[:limit]
        ],
        "next_cursor": rows[limit - 1].revision if len(rows) > limit else None,
    }


def owned_dossier(session, user_id, dossier_id, *, write=False):
    organization = _actor(session, user_id, write=write)
    row = session.scalar(
        select(TenderDossier)
        .join(TenderMonitor, TenderMonitor.id == TenderDossier.monitor_id)
        .where(
            TenderDossier.id == dossier_id,
            TenderDossier.organization_id == organization,
            TenderMonitor.organization_id == organization,
            TenderMonitor.owner_user_id == user_id,
        )
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise DomainError("Tender dossier not found.", 404, "tender_dossier_not_found")
    return row


def source_readable(row, now, *, include_documents=True):
    from sqlalchemy.orm import object_session

    from .tender_rights import require_permitted

    session = object_session(row)
    if session is None:
        raise DomainError("Tender evidence is unavailable.", 503, "tender_evidence_invalid")
    require_permitted(session, row.snapshot.project_id, row.publication_id)
    gate = row.publish_after
    # SQLite drops timezone metadata from a timestamp column, not its UTC value.
    if gate.tzinfo is None:
        gate = gate.replace(tzinfo=UTC)
    if gate > aware(now):
        raise DomainError("This publication is not yet available.", 404, "tender_publication_unavailable")
    try:
        checked = parse_publication(
            row.evidence["original"],
            project_id=row.evidence["project_id"],
            publication_id=row.publication_id,
            now=now,
        )
    except PublicationEmbargo:
        raise DomainError(
            "This publication is not yet available.", 404, "tender_publication_unavailable"
        ) from None
    except (ValueError, KeyError, TypeError):
        raise DomainError("Tender evidence is unavailable.", 503, "tender_evidence_invalid") from None
    if checked["evidence_sha256"] != row.source_hash:
        raise DomainError(
            "Tender evidence no longer matches its fingerprint.", 503, "tender_evidence_invalid"
        )
    if include_documents and row.observation_key and row.document_observation_id:
        from .tender_document_observations import require_current_changes

        dossier = session.get(TenderDossier, row.dossier_id)
        monitor = session.get(TenderMonitor, dossier.monitor_id)
        require_current_changes(session, monitor.owner_user_id, dossier.id, row.document_observation_id, now=now)


def dossier_view(session, row, now):
    latest = session.scalar(
        select(TenderDossierVersion).where(
            TenderDossierVersion.dossier_id == row.id,
            TenderDossierVersion.organization_id == row.organization_id,
            TenderDossierVersion.sequence == row.latest_sequence,
        )
    )
    if latest is None:
        raise DomainError("Tender evidence is unavailable.", 503, "tender_evidence_missing")
    source_readable(latest, now)
    return {
        "id": row.id,
        "monitor_id": row.monitor_id,
        "project_id": row.project_id,
        "lot_id": row.lot_key or None,
        "version": row.version,
        "sequence": row.latest_sequence,
        "following": row.following,
        "review_state": row.review_state,
        "decision": row.decision,
        "reviewed_sequence": row.reviewed_sequence,
        "match": deepcopy(latest.match),
        "changes": deepcopy(latest.changes),
        "kind": latest.kind,
        "evidence_version_id": latest.id,
        "source_hash": latest.source_hash,
        "document_observation_id": latest.document_observation_id,
        "publication_id": latest.publication_id,
        "profile_revision": latest.profile_revision,
        "current_profile_revision": session.scalar(
            select(TenderMonitor.revision).where(TenderMonitor.id == row.monitor_id)
        ),
        "material": deepcopy(latest.material),
        "decision_scope": "internal_only",
    }


def get_dossier(session, user_id, dossier_id, *, now=None):
    return dossier_view(session, owned_dossier(session, user_id, dossier_id), now or datetime.now(UTC))


def list_dossiers(
    session, user_id, monitor_id, *, limit=20, after_id=None, following=None, review_state=None, now=None
):
    from .tender_rights import permitted

    monitor = owned(session, user_id, monitor_id)
    limit_value(limit)
    now = aware(now or datetime.now(UTC))
    if following is not None and type(following) is not bool:
        raise DomainError("Invalid following filter.", 422, "tender_filter_invalid")
    if review_state is not None and review_state not in {"new", "needs_review", "reviewed"}:
        raise DomainError("Invalid review filter.", 422, "tender_filter_invalid")
    # Select bounded projections only. Never hydrate 100 full 8 MB originals or
    # duplicate shared terms for every card in the discovery list.
    query = (
        select(
            TenderDossier,
            TenderDossierVersion.summary,
            TenderDossierVersion.kind,
            TenderDossierVersion.id,
            TenderDossierVersion.profile_revision,
        )
        .join(
            TenderDossierVersion,
            and_(
                TenderDossierVersion.dossier_id == TenderDossier.id,
                TenderDossierVersion.organization_id == TenderDossier.organization_id,
                TenderDossierVersion.sequence == TenderDossier.latest_sequence,
            ),
        )
        .where(
            TenderDossier.monitor_id == monitor.id,
            TenderDossier.organization_id == monitor.organization_id,
            TenderDossierVersion.publish_after <= now,
            permitted(TenderDossier.project_id, TenderDossierVersion.publication_id),
        )
    )
    if following is not None:
        query = query.where(TenderDossier.following == following)
    if review_state is not None:
        query = query.where(TenderDossier.review_state == review_state)
    if after_id:
        anchor = owned_dossier(session, user_id, after_id)
        if anchor.monitor_id != monitor.id:
            raise DomainError("Refresh the tender list.", 422, "tender_cursor_invalid")
        query = query.where(
            or_(
                TenderDossier.updated_at < anchor.updated_at,
                and_(TenderDossier.updated_at == anchor.updated_at, TenderDossier.id > anchor.id),
            )
        )
    rows = list(
        session.execute(query.order_by(TenderDossier.updated_at.desc(), TenderDossier.id).limit(limit + 1))
    )
    return {
        "items": [
            {
                "id": row.id,
                "monitor_id": row.monitor_id,
                "project_id": row.project_id,
                "lot_id": row.lot_key or None,
                "version": row.version,
                "sequence": row.latest_sequence,
                "following": row.following,
                "review_state": row.review_state,
                "decision": row.decision,
                "reviewed_sequence": row.reviewed_sequence,
                "updated_at": row.updated_at,
                "summary": deepcopy(summary),
                "kind": kind,
                "evidence_version_id": version_id,
                "profile_revision": revision,
                "current_profile_revision": monitor.revision,
            }
            for row, summary, kind, version_id, revision in rows[:limit]
        ],
        "next_cursor": rows[limit - 1][0].id if len(rows) > limit else None,
    }


def version_index(session, user_id, dossier_id, *, limit=20, before_sequence=None, now=None):
    from .tender_rights import permitted

    row = owned_dossier(session, user_id, dossier_id)
    limit_value(limit)
    query = select(
        TenderDossierVersion.id,
        TenderDossierVersion.sequence,
        TenderDossierVersion.publication_id,
        TenderDossierVersion.kind,
        TenderDossierVersion.summary,
        TenderDossierVersion.changes,
        TenderDossierVersion.source_hash,
        TenderDossierVersion.observed_at,
        TenderDossierVersion.profile_revision,
        TenderDossierVersion.document_observation_id,
    ).where(
        TenderDossierVersion.dossier_id == row.id,
        TenderDossierVersion.organization_id == row.organization_id,
        TenderDossierVersion.publish_after <= aware(now or datetime.now(UTC)),
        permitted(row.project_id, TenderDossierVersion.publication_id),
    )
    if before_sequence is not None:
        positive(before_sequence)
        query = query.where(TenderDossierVersion.sequence < before_sequence)
    rows = list(
        session.execute(query.order_by(TenderDossierVersion.sequence.desc()).limit(limit + 1)).mappings()
    )
    return {
        "items": [dict(item) for item in rows[:limit]],
        "next_cursor": rows[limit - 1]["sequence"] if len(rows) > limit else None,
    }


def dossier_history(session, user_id, dossier_id, *, limit=50, before_sequence=None, now=None):
    from .tender_rights import permitted

    row = owned_dossier(session, user_id, dossier_id)
    limit_value(limit)
    now = aware(now or datetime.now(UTC))
    statement = select(TenderDossierVersion).where(
        TenderDossierVersion.dossier_id == row.id,
        TenderDossierVersion.organization_id == row.organization_id,
        TenderDossierVersion.publish_after <= now,
        permitted(row.project_id, TenderDossierVersion.publication_id),
    )
    if before_sequence is not None:
        positive(before_sequence)
        statement = statement.where(TenderDossierVersion.sequence < before_sequence)
    versions = list(
        session.scalars(statement.order_by(TenderDossierVersion.sequence.desc()).limit(limit + 1))
    )
    for version in versions[:limit]:
        source_readable(version, now)
    return {
        "items": [
            {
                "id": item.id,
                "sequence": item.sequence,
                "publication_id": item.publication_id,
                "kind": item.kind,
                "changes": deepcopy(item.changes),
                "source_hash": item.source_hash,
                "document_observation_id": item.document_observation_id,
                "material": deepcopy(item.material),
            }
            for item in versions[:limit]
        ],
        "next_cursor": versions[limit - 1].sequence if len(versions) > limit else None,
    }


def evidence_version(session, user_id, dossier_id, version_id, *, now=None):
    row = owned_dossier(session, user_id, dossier_id)
    version = session.scalar(
        select(TenderDossierVersion).where(
            TenderDossierVersion.id == version_id,
            TenderDossierVersion.dossier_id == row.id,
            TenderDossierVersion.organization_id == row.organization_id,
        )
    )
    if version is None:
        raise DomainError("Tender evidence not found.", 404, "tender_evidence_not_found")
    source_readable(version, now or datetime.now(UTC))
    return deepcopy(version.evidence)


def record_decision(session, user_id, dossier_id, *, version, sequence, decision, key, now=None):
    row = owned_dossier(session, user_id, dossier_id, write=True)
    positive(version)
    positive(sequence)
    request_key(key)
    if decision not in {"bid", "no_bid", "monitor"}:
        raise DomainError("Choose Bid, No-bid or Monitor.", 422, "tender_decision_invalid")
    hashed = digest({"version": version, "sequence": sequence, "decision": decision})
    previous = session.scalar(
        select(TenderDecision).where(
            TenderDecision.dossier_id == row.id,
            TenderDecision.organization_id == row.organization_id,
            TenderDecision.request_key == key,
        )
    )
    if previous:
        if previous.request_hash != hashed:
            raise DomainError("This decision request has different values.", 409, "tender_request_conflict")
        # A retry after a material update must not mark the new evidence reviewed.
        return get_dossier(session, user_id, dossier_id, now=now)
    dossier_view(session, row, now or datetime.now(UTC))
    with _savepoint(session):
        changed = session.execute(
            update(TenderDossier)
            .where(
                TenderDossier.id == row.id,
                TenderDossier.organization_id == row.organization_id,
                TenderDossier.version == version,
                TenderDossier.latest_sequence == sequence,
            )
            .values(
                version=version + 1,
                review_state="reviewed",
                decision=decision,
                reviewed_sequence=sequence,
                following=True,
            )
            .execution_options(synchronize_session=False)
        )
        if changed.rowcount != 1:
            raise DomainError(
                "The tender changed. Review its current evidence first.", 409, "tender_version_conflict"
            )
        session.add(
            TenderDecision(
                organization_id=row.organization_id,
                dossier_id=row.id,
                user_id=user_id,
                sequence=sequence,
                decision=decision,
                request_key=key,
                request_hash=hashed,
            )
        )
        session.flush()
    return get_dossier(session, user_id, dossier_id, now=now)
