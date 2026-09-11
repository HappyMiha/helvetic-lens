"""C01a private draft repository. Callers own the transaction and commit/rollback.

The caller supplies a server-authenticated user ID, not one from a request body.
Every call checks current membership and owner scope. No activation or delivery.
"""

import hashlib
import json
from copy import deepcopy
from decimal import Decimal

from pydantic import ValidationError
from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import DomainError
from .db import utcnow
from .models import MonitoringSubject, MonitoringSubjectRevision, OrganizationMembership, User, new_id
from .pollen_contracts import PollenConfiguration


def _actor(session: Session, user_id: str, *, write: bool = False) -> str:
    organization_id = session.info.get("organization_id")
    membership = session.execute(select(User.active, OrganizationMembership.role).join(
        OrganizationMembership, OrganizationMembership.user_id == User.id,
    ).where(User.id == user_id, OrganizationMembership.organization_id == organization_id)).first()
    if not organization_id or not membership or not membership.active:
        raise DomainError("An active workspace membership is required.", 403, "membership_required")
    if membership.role not in {"organization_admin", "viewer"} or (write and membership.role != "organization_admin"):
        raise DomainError("This role cannot modify monitoring drafts.", 403, "subject_role_denied")
    return organization_id


def _plain(value):
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _configuration(value: dict) -> tuple[dict, str]:
    if not isinstance(value, dict):
        raise DomainError("Invalid Pollen Watch configuration.", 422, "subject_configuration_invalid")
    try:
        config = PollenConfiguration.model_validate(value)
    except ValidationError:
        # Do not include submitted private configuration in errors or logs.
        raise DomainError("Invalid Pollen Watch configuration.", 422, "subject_configuration_invalid") from None
    payload = _plain(config.model_dump())
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return json.loads(encoded), hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _savepoint(session):
    connection = session.connection()
    # sqlite3 legacy transaction mode does not BEGIN for SELECT/SAVEPOINT.
    # Ensure releasing a savepoint cannot commit past the caller's rollback.
    if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN")
    return session.begin_nested()


def _owned(session, organization_id, user_id, subject_id):
    subject = session.scalar(select(MonitoringSubject).where(
        MonitoringSubject.id == subject_id, MonitoringSubject.organization_id == organization_id,
        MonitoringSubject.owner_user_id == user_id,
    ).execution_options(populate_existing=True))
    if subject is None:
        raise DomainError("Monitoring draft not found.", 404, "subject_not_found")
    return subject


def _view(session, subject):
    revision = session.scalar(select(MonitoringSubjectRevision).where(
        MonitoringSubjectRevision.subject_id == subject.id,
        MonitoringSubjectRevision.organization_id == subject.organization_id,
        MonitoringSubjectRevision.revision == subject.current_revision,
    ))
    if revision is None:
        raise DomainError("Monitoring configuration is unavailable.", 503, "subject_revision_missing")
    return {"id": subject.id, "status": subject.status, "revision": subject.current_revision,
            "configuration": deepcopy(revision.configuration_json), "configuration_hash": revision.configuration_hash}


def get_subject(session: Session, *, user_id: str, subject_id: str) -> dict:
    organization_id = _actor(session, user_id)
    return _view(session, _owned(session, organization_id, user_id, subject_id))


def list_subjects(session: Session, *, user_id: str, limit: int = 50) -> list[dict]:
    return list_subjects_page(session, user_id=user_id, limit=limit)["items"]


def list_subjects_page(session: Session, *, user_id: str, limit: int = 50, after_id: str | None = None) -> dict:
    organization_id = _actor(session, user_id)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise DomainError("List limit must be between 1 and 100.", 422, "subject_limit_invalid")
    statement = select(MonitoringSubject).where(
        MonitoringSubject.organization_id == organization_id, MonitoringSubject.owner_user_id == user_id,
    )
    if after_id:
        anchor = _owned(session, organization_id, user_id, after_id)
        statement = statement.where(or_(MonitoringSubject.created_at < anchor.created_at,
                                        and_(MonitoringSubject.created_at == anchor.created_at,
                                             MonitoringSubject.id > anchor.id)))
    rows = list(session.scalars(statement.order_by(
        MonitoringSubject.created_at.desc(), MonitoringSubject.id,
    ).limit(limit + 1)))
    return {"items": [_view(session, subject) for subject in rows[:limit]],
            "next_cursor": rows[limit - 1].id if len(rows) > limit else None}


def preview_draft(session: Session, *, user_id: str, configuration: dict) -> dict:
    _actor(session, user_id, write=True)
    payload, digest = _configuration(configuration)
    return {"configuration": payload, "configuration_hash": digest,
            "preview_kind": "configuration_only", "coverage": "unverified",
            "observations": [], "forecasts": [], "start_available": False,
            "blocking_reasons": ["source_acceptance_pending", "live_connector_not_implemented"]}


def create_draft(session: Session, *, user_id: str, request_key: str, configuration: dict) -> dict:
    organization_id = _actor(session, user_id, write=True)
    if (not isinstance(request_key, str) or not request_key.strip() or len(request_key) > 120
            or any(ord(char) < 32 for char in request_key)):
        raise DomainError("A bounded request key is required.", 422, "subject_request_key_invalid")
    payload, digest = _configuration(configuration)

    def existing():
        return session.scalar(select(MonitoringSubject).where(
            MonitoringSubject.organization_id == organization_id, MonitoringSubject.owner_user_id == user_id,
            MonitoringSubject.request_key == request_key,
        ).execution_options(populate_existing=True))

    def replay(subject):
        if subject.request_hash != digest:
            raise DomainError("This request key was used for different settings.", 409, "subject_request_conflict")
        return _view(session, subject)

    if subject := existing():
        return replay(subject)
    subject = MonitoringSubject(id=new_id(), organization_id=organization_id, owner_user_id=user_id,
                                template_id=payload["template_id"], template_version=payload["template_version"],
                                contract_version=payload["contract_version"], status="draft", current_revision=1,
                                request_key=request_key, request_hash=digest)
    try:
        with _savepoint(session):
            session.add(subject)
            session.flush()
            session.add(MonitoringSubjectRevision(organization_id=organization_id, subject_id=subject.id,
                                                  revision=1, configuration_json=payload, configuration_hash=digest))
            session.flush()
    except IntegrityError:
        if winner := existing():
            return replay(winner)
        raise
    return _view(session, subject)


def _expected_revision(value):
    if type(value) is not int or value < 1:
        raise DomainError("A positive expected revision is required.", 422, "subject_revision_invalid")


def revise_draft(session: Session, *, user_id: str, subject_id: str,
                 expected_revision: int, configuration: dict) -> dict:
    organization_id = _actor(session, user_id, write=True)
    _expected_revision(expected_revision)
    _owned(session, organization_id, user_id, subject_id)
    payload, digest = _configuration(configuration)
    with _savepoint(session):
        changed = session.execute(update(MonitoringSubject).where(
            MonitoringSubject.id == subject_id, MonitoringSubject.organization_id == organization_id,
            MonitoringSubject.owner_user_id == user_id, MonitoringSubject.status == "draft",
            MonitoringSubject.current_revision == expected_revision,
        ).values(current_revision=expected_revision + 1, updated_at=utcnow()).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            raise DomainError("The draft changed or is no longer editable.", 409, "subject_revision_conflict")
        session.add(MonitoringSubjectRevision(organization_id=organization_id, subject_id=subject_id,
                                              revision=expected_revision + 1, configuration_json=payload,
                                              configuration_hash=digest))
        session.flush()
    return get_subject(session, user_id=user_id, subject_id=subject_id)


def subject_history(session: Session, *, user_id: str, subject_id: str, limit: int = 100) -> list[dict]:
    return subject_history_page(session, user_id=user_id, subject_id=subject_id, limit=limit)["items"]


def subject_history_page(session: Session, *, user_id: str, subject_id: str,
                         limit: int = 100, before_revision: int | None = None) -> dict:
    organization_id = _actor(session, user_id)
    _owned(session, organization_id, user_id, subject_id)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise DomainError("History limit must be between 1 and 100.", 422, "subject_limit_invalid")
    statement = select(MonitoringSubjectRevision).where(
        MonitoringSubjectRevision.subject_id == subject_id,
        MonitoringSubjectRevision.organization_id == organization_id,
    )
    if before_revision is not None:
        _expected_revision(before_revision)
        statement = statement.where(MonitoringSubjectRevision.revision < before_revision)
    revisions = list(session.scalars(statement.order_by(MonitoringSubjectRevision.revision.desc()).limit(limit + 1)))
    return {"items": [{"revision": row.revision, "configuration": deepcopy(row.configuration_json),
                       "configuration_hash": row.configuration_hash} for row in revisions[:limit]],
            "next_before_revision": revisions[limit - 1].revision if len(revisions) > limit else None}


def delete_draft(session: Session, *, user_id: str, subject_id: str, expected_revision: int) -> None:
    organization_id = _actor(session, user_id, write=True)
    _expected_revision(expected_revision)
    _owned(session, organization_id, user_id, subject_id)
    result = session.execute(delete(MonitoringSubject).where(
        MonitoringSubject.id == subject_id, MonitoringSubject.organization_id == organization_id,
        MonitoringSubject.owner_user_id == user_id, MonitoringSubject.status == "draft",
        MonitoringSubject.current_revision == expected_revision,
    ).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        raise DomainError("The draft changed or is no longer deletable.", 409, "subject_revision_conflict")
