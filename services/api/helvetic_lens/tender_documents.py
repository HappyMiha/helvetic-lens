"""Private originals; trusted worker/operator writes, authenticated owner reads."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update

from .config import DomainError
from .document_comparison import ParsedDocument
from .document_parsing import MAX_DOCUMENT_BYTES
from .simap_sources import aware
from .tender_models import (
    TenderDocumentAccess,
    TenderDocumentObservation,
    TenderDocumentSnapshot,
    TenderDossier,
    TenderDossierVersion,
    TenderMonitor,
)
from .tender_repository import limit_value, owned_dossier
from .tender_rights import permitted, require_permitted

MAX_DOSSIER_BYTES = 64 * 1024 * 1024
MAX_DOSSIER_SNAPSHOTS = 1000


def used_bytes(session, dossier_id):
    return sum(session.scalar(select(func.coalesce(func.sum(model.stored_bytes), 0))
                              .where(model.dossier_id == dossier_id))
               for model in (TenderDocumentSnapshot, TenderDocumentObservation))


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def unavailable():
    return DomainError("Tender document is unavailable.", 404, "tender_document_unavailable")


def record_access(session, user_id, dossier_id, *, source_id, publication_id,
                  account_reference, policy_reference, valid_until, retain_until, now):
    """Operator only, after reviewed capture/retention/download source permission.

    No HTTP endpoint. References identify reviewed evidence, never credentials.
    General public source access does not permit calling this grant operation.
    """
    dossier = owned_dossier(session, user_id, dossier_id, write=True)
    now, valid_until, retain_until = map(aware, (now, valid_until, retain_until))
    if not now < valid_until <= retain_until:
        raise ValueError("Explicit future access and retention deadlines are required")
    for value, bound in ((source_id, 100), (account_reference, 200), (policy_reference, 500)):
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= bound:
            raise ValueError("Source policy and account evidence must be explicit")
    publication_id = str(UUID(publication_id))
    if not session.scalar(select(TenderDossierVersion.id).where(
        TenderDossierVersion.dossier_id == dossier.id,
        TenderDossierVersion.publication_id == publication_id,
    ).limit(1)):
        raise ValueError("Grant publication must belong to the retained dossier")
    require_permitted(session, dossier.project_id, publication_id)
    row = TenderDocumentAccess(organization_id=dossier.organization_id, dossier_id=dossier.id,
                               source_id=source_id, publication_id=publication_id,
                               account_reference=account_reference, policy_reference=policy_reference,
                               valid_until=valid_until, retain_until=retain_until, created_at=now)
    session.add(row)
    session.flush()
    return row


def access(session, user_id, dossier_id, access_id, now, *, write=False):
    dossier = owned_dossier(session, user_id, dossier_id, write=write)
    grant = session.scalar(select(TenderDocumentAccess).where(
        TenderDocumentAccess.id == access_id, TenderDocumentAccess.dossier_id == dossier.id,
        TenderDocumentAccess.organization_id == dossier.organization_id,
    ).execution_options(populate_existing=True).with_for_update())
    if grant is None or grant.revoked_at is not None or utc(grant.valid_until) <= now or utc(grant.retain_until) <= now:
        raise unavailable()
    require_permitted(session, dossier.project_id, grant.publication_id)
    return dossier, grant


def store(session, user_id, dossier_id, parsed, body, *, content_type, now):
    """Worker only; commit atomically with manifest. Never browser-supplied facts."""
    now = aware(now)
    parsed = ParsedDocument.model_validate(parsed.model_dump())
    # Lock order matches monitor lifecycle commands; SQLite uses the no-op write.
    dossier = owned_dossier(session, user_id, dossier_id, write=True)
    session.execute(update(TenderMonitor).where(TenderMonitor.id == dossier.monitor_id)
                    .values(version=TenderMonitor.version))
    monitor = session.scalar(select(TenderMonitor).where(TenderMonitor.id == dossier.monitor_id)
                             .execution_options(populate_existing=True).with_for_update())
    session.execute(update(TenderDossier).where(TenderDossier.id == dossier.id)
                    .values(version=TenderDossier.version))
    dossier, grant = access(session, user_id, dossier_id, str(parsed.access_scope_id), now, write=True)
    if monitor is None or monitor.status != "active":
        raise DomainError("Collection requires an active monitor.", 409, "tender_monitor_inactive")
    if (parsed.dossier_id != dossier.id or parsed.source_id != grant.source_id
            or not isinstance(body, bytes) or not 0 < len(body) <= MAX_DOCUMENT_BYTES
            or hashlib.sha256(body).hexdigest() != parsed.content_sha256):
        raise ValueError("Document scope or bytes do not match the parsed evidence")
    mime = content_type.split(";", 1)[0].strip().lower()
    if not mime or len(mime) > 100 or any(ord(c) < 33 for c in mime):
        raise ValueError("Invalid document media type")
    existing = session.scalar(select(TenderDocumentSnapshot).where(
        TenderDocumentSnapshot.access_id == grant.id, TenderDocumentSnapshot.item_id == parsed.item_id,
        TenderDocumentSnapshot.content_sha256 == parsed.content_sha256,
        TenderDocumentSnapshot.text_sha256 == parsed.text_sha256,
        TenderDocumentSnapshot.extractor_version == parsed.extractor_version,
    ))
    if existing is not None:
        if existing.purged_at is not None:
            raise unavailable()
        stored = ParsedDocument.model_validate(existing.parsed)
        if (existing.body != body or stored.model_dump(exclude={"snapshot_id"}) != parsed.model_dump(exclude={"snapshot_id"})):
            raise ValueError("Conflicting immutable document projection")
        return existing.id
    projection = parsed.model_dump(mode="json")
    size = len(body) + len(json.dumps(projection, ensure_ascii=False, separators=(",", ":")).encode())
    used = used_bytes(session, dossier.id)
    count = session.scalar(select(func.count()).select_from(TenderDocumentSnapshot)
                           .where(TenderDocumentSnapshot.dossier_id == dossier.id))
    if used + size > MAX_DOSSIER_BYTES or count >= MAX_DOSSIER_SNAPSHOTS:
        raise DomainError("Document storage capacity reached.", 409, "tender_document_capacity")
    session.add(TenderDocumentSnapshot(id=str(parsed.snapshot_id), organization_id=dossier.organization_id,
                                       dossier_id=dossier.id, access_id=grant.id, item_id=parsed.item_id,
                                       content_sha256=parsed.content_sha256, text_sha256=parsed.text_sha256,
                                       extractor_version=parsed.extractor_version, content_type=mime,
                                       body=body, parsed=projection, stored_bytes=size, created_at=now))
    session.flush()
    return str(parsed.snapshot_id)


def read(session, user_id, dossier_id, snapshot_id, *, now=None, check_item_access=True):
    now = aware(now or datetime.now(UTC))
    dossier = owned_dossier(session, user_id, dossier_id)
    row = session.scalar(select(TenderDocumentSnapshot).where(
        TenderDocumentSnapshot.id == snapshot_id, TenderDocumentSnapshot.dossier_id == dossier.id,
        TenderDocumentSnapshot.organization_id == dossier.organization_id,
    ).execution_options(populate_existing=True))
    if row is None:
        raise unavailable()
    _, grant = access(session, user_id, dossier_id, row.access_id, now)
    if check_item_access:
        from .tender_document_observations import item_permitted

        if not item_permitted(session, row.access_id, row.item_id):
            raise unavailable()
    if row.purged_at is not None or row.body is None or row.parsed is None:
        raise unavailable()
    try:
        parsed = ParsedDocument.model_validate(row.parsed)
        if (parsed.snapshot_id != UUID(row.id) or parsed.access_scope_id != UUID(row.access_id)
                or parsed.dossier_id != dossier.id or parsed.item_id != row.item_id
                or parsed.source_id != grant.source_id or parsed.extractor_version != row.extractor_version
                or parsed.text_sha256 != row.text_sha256 or parsed.content_sha256 != row.content_sha256
                or hashlib.sha256(row.body).hexdigest() != row.content_sha256):
            raise ValueError("Integrity mismatch")
    except ValueError:
        raise DomainError("Document integrity could not be verified.", 503, "tender_document_invalid") from None
    return row, parsed


def index(session, user_id, dossier_id, *, limit=20, after_id=None, now=None):
    now = aware(now or datetime.now(UTC))
    dossier = owned_dossier(session, user_id, dossier_id)
    limit_value(limit)
    rows = select(TenderDocumentSnapshot.id, TenderDocumentSnapshot.item_id,
                  TenderDocumentSnapshot.content_sha256, TenderDocumentSnapshot.created_at,
                  TenderDocumentSnapshot.access_id).join(
        TenderDocumentAccess, TenderDocumentAccess.id == TenderDocumentSnapshot.access_id,
    ).where(TenderDocumentSnapshot.dossier_id == dossier.id,
            TenderDocumentSnapshot.organization_id == dossier.organization_id,
            TenderDocumentSnapshot.purged_at.is_(None), TenderDocumentAccess.revoked_at.is_(None),
            TenderDocumentAccess.valid_until > now, TenderDocumentAccess.retain_until > now,
            permitted(dossier.project_id, TenderDocumentAccess.publication_id))
    if after_id:
        rows = rows.where(TenderDocumentSnapshot.id > str(UUID(after_id)))
    result = session.execute(rows.order_by(TenderDocumentSnapshot.id).limit(limit + 1)).all()
    from .tender_document_observations import denied_items

    denied = {grant_id: denied_items(session, grant_id) for grant_id in {row.access_id for row in result[:limit]}}
    return {"items": [{"id": row.id, "item_id": row.item_id, "content_sha256": row.content_sha256,
                       "created_at": utc(row.created_at).isoformat()} for row in result[:limit]
                     if row.item_id not in denied[row.access_id]],
            "next_cursor": result[limit - 1].id if len(result) > limit else None,
            "coverage": "retained_only"}


def purge_expired(session, *, now, limit=100):
    """Trusted bounded maintenance; caller commits. Backup retention is separate.

    Clear expired payloads, retain IDs/hashes for unavailable historical links.
    Revocation denies reads now; the retention deadline controls physical purge.
    """
    now = aware(now)
    limit_value(limit)
    ids = list(session.scalars(select(TenderDocumentSnapshot.id).join(
        TenderDocumentAccess, TenderDocumentAccess.id == TenderDocumentSnapshot.access_id,
    ).where(TenderDocumentAccess.retain_until <= now, TenderDocumentSnapshot.purged_at.is_(None))
        .order_by(TenderDocumentSnapshot.id).limit(limit)))
    if ids:
        session.execute(update(TenderDocumentSnapshot).where(TenderDocumentSnapshot.id.in_(ids))
                        .values(body=None, parsed=None, stored_bytes=0, purged_at=now))
    return len(ids)


def cleanup(database, *, now=None):
    """Retention remains active even when collection or email is disabled."""
    with database.session(include_all_organizations=True) as session:
        now = aware(now or datetime.now(UTC))
        purged = purge_expired(session, now=now)
        ids = list(session.scalars(select(TenderDocumentObservation.id).join(
            TenderDocumentAccess, TenderDocumentAccess.id == TenderDocumentObservation.access_id,
        ).where(TenderDocumentAccess.retain_until <= now, TenderDocumentObservation.purged_at.is_(None))
            .order_by(TenderDocumentObservation.id).limit(100)))
        if ids:
            session.execute(update(TenderDocumentObservation).where(TenderDocumentObservation.id.in_(ids))
                            .values(state=None, deltas=None, stored_bytes=0, purged_at=now))
        session.commit()
        return {"purged": purged}
