"""Internal permitted register journal. No accounts, HTTP, public write API or email.

A native collector must verify the transport and normalize the complete record
before calling accept_record. Callers own commits; each mutation is atomic in a
savepoint. Raw register evidence must not contain private user portfolio queries.
Reading records is not evidence that a complete register traversal succeeded.
"""

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from .config import DomainError
from .monitoring_subjects import _savepoint
from .trademark_contracts import TrademarkFacts, fingerprint, valid_text
from .trademark_source_models import (
    TrademarkRegisterHead,
    TrademarkRegisterRevision,
    TrademarkSourcePermission,
    TrademarkSourceReceipt,
    TrademarkSourceSelection,
)

MAX_RECORD_BYTES = 2 * 1024 * 1024
MAX_REVISIONS = 200_000
MAX_RECEIPTS = 500_000
MAX_RETAINED_BYTES = 2 * 1024 * 1024 * 1024


def _error(code, status=409):
    raise DomainError("Trademark evidence or source permission is unavailable.", status, code) from None


def _clock(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        _error("trademark_source_clock_invalid", 422)
    return value.astimezone(UTC)


def _utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


def _hash(value):
    return hashlib.sha256(value).hexdigest()


class TrademarkSourcePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    source_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    reference: str = Field(min_length=1, max_length=1000)
    attribution: str = Field(min_length=1, max_length=1000)
    endpoint: str = Field(min_length=1, max_length=2048)
    accepted_at: datetime
    valid_until: datetime
    origins: tuple[Literal["national_ch", "international_designating_ch"], ...] = Field(min_length=1, max_length=2)
    min_poll_seconds: int = Field(ge=60, le=7 * 86400)
    max_age_seconds: int = Field(ge=1, le=31 * 86400)
    raw_retention_seconds: int = Field(ge=0, le=366 * 86400)
    normalized_retention_seconds: int = Field(ge=1, le=366 * 86400)
    automated_access_allowed: bool
    store_source_allowed: bool
    retain_minimal_audit: bool
    matching_allowed: bool
    display_allowed: bool
    notifications_allowed: bool = False
    export_allowed: bool = False
    private_decisions_allowed: bool = False

    @model_validator(mode="after")
    def reviewed(self):
        for value in (self.reference, self.attribution):
            valid_text(value)
        address = urlsplit(self.endpoint)
        if (any(v.tzinfo is None or v.utcoffset() is None for v in (self.accepted_at, self.valid_until))
                or self.accepted_at >= self.valid_until
                or self.raw_retention_seconds > self.normalized_retention_seconds
                or not self.retain_minimal_audit or len(set(self.origins)) != len(self.origins)
                or address.scheme != "https" or not address.hostname or address.username or address.password
                or address.query or address.fragment or address.port not in (None, 443)
                or any(c.isspace() for c in self.endpoint)):
            raise ValueError("Invalid reviewed trademark source policy")
        return self


def record_permission(session, *, policy):
    policy = TrademarkSourcePolicy.model_validate(policy)
    payload = policy.model_dump(mode="json")
    row = TrademarkSourcePermission(policy=payload, policy_hash=fingerprint(payload),
        accepted_at=_clock(policy.accepted_at), valid_until=_clock(policy.valid_until))
    session.add(row)
    session.flush()
    return row.id


def require_permission(session, permission_id, *, now, purpose="storage"):
    now = _clock(now)
    row = session.scalar(select(TrademarkSourcePermission).where(TrademarkSourcePermission.id == permission_id)
        .with_for_update().execution_options(populate_existing=True))
    if row is None or row.revoked_at is not None or not _utc(row.accepted_at) <= now < _utc(row.valid_until):
        _error("trademark_permission_unavailable")
    try:
        encoded = _encoded(row.policy)
        policy = TrademarkSourcePolicy.model_validate_json(encoded, strict=True)
        if (_hash(encoded) != row.policy_hash or _clock(policy.accepted_at) != _utc(row.accepted_at)
                or _clock(policy.valid_until) != _utc(row.valid_until)):
            _error("trademark_permission_invalid", 503)
    except (ValueError, TypeError):
        _error("trademark_permission_invalid", 503)
    allowed = {"storage": policy.store_source_allowed, "acquisition": policy.automated_access_allowed,
        "matching": policy.matching_allowed, "display": policy.display_allowed,
        "notification": policy.notifications_allowed, "export": policy.export_allowed,
        "decision": policy.private_decisions_allowed}
    if not allowed.get(purpose, False):
        _error("trademark_source_use_denied", 403)
    return row, policy


def _selection(session, source_key, *, lock=True):
    query = select(TrademarkSourceSelection).where(TrademarkSourceSelection.source_key == source_key)
    return session.scalar((query.with_for_update() if lock else query).execution_options(populate_existing=True))


def activate_permission(session, permission_id, *, expected_generation, now):
    _, policy = require_permission(session, permission_id, now=now, purpose="acquisition")
    require_permission(session, permission_id, now=now)
    if type(expected_generation) is not int or expected_generation < 0:
        _error("trademark_generation_invalid", 422)
    try:
        with _savepoint(session):
            current = _selection(session, policy.source_key)
            if (current.generation if current else 0) != expected_generation:
                _error("trademark_source_selection_conflict")
            if current is None:
                session.add(TrademarkSourceSelection(source_key=policy.source_key, permission_id=permission_id,
                    generation=1, cursor_version=0))
            else:
                changed = session.execute(update(TrademarkSourceSelection).where(
                    TrademarkSourceSelection.source_key == policy.source_key,
                    TrademarkSourceSelection.generation == expected_generation).values(
                    permission_id=permission_id, generation=expected_generation + 1,
                    cursor_version=0, last_received_at=None).execution_options(synchronize_session=False))
                if changed.rowcount != 1:
                    _error("trademark_source_selection_conflict")
            session.flush()
    except IntegrityError:
        _error("trademark_source_selection_conflict")
    return expected_generation + 1


def record_key(facts):
    return fingerprint({"origin": facts.origin, "official_id": facts.official_id})


def _restore(row):
    if row.normalized_payload is None or _hash(row.normalized_payload) != row.normalized_hash:
        _error("trademark_evidence_unavailable")
    if row.raw_payload is not None and _hash(row.raw_payload) != row.raw_hash:
        _error("trademark_evidence_unavailable")
    try:
        facts = TrademarkFacts.model_validate_json(row.normalized_payload)
    except ValueError:
        _error("trademark_evidence_unavailable")
    if (facts.material_fingerprint() != row.material_hash or record_key(facts) != row.record_key
            or facts.source_sha256 != row.raw_hash):
        _error("trademark_evidence_unavailable")
    return facts


def accept_record(session, permission_id, raw, facts, *, request_key, request_url,
                  expected_generation, expected_cursor_version, received_at, now):
    now, received_at = _clock(now), _clock(received_at)
    _, policy = require_permission(session, permission_id, now=now, purpose="acquisition")
    require_permission(session, permission_id, now=now)
    if (type(expected_generation) is not int or expected_generation < 1
            or type(expected_cursor_version) is not int or expected_cursor_version < 0
            or not isinstance(request_key, str) or not request_key.strip() or len(request_key) > 100
            or any(ord(c) < 32 for c in request_key)):
        _error("trademark_source_request_invalid", 422)
    if (received_at > now or now - received_at > timedelta(seconds=policy.max_age_seconds)
            or now - received_at >= timedelta(seconds=policy.normalized_retention_seconds)
            or received_at < _clock(policy.accepted_at)):
        _error("trademark_source_time_invalid", 422)
    if request_url != policy.endpoint:
        _error("trademark_source_endpoint_denied", 403)
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_RECORD_BYTES:
        _error("trademark_source_size_invalid", 422)
    facts = TrademarkFacts.model_validate(facts)
    if facts.source_sha256 != _hash(raw) or facts.origin not in policy.origins:
        _error("trademark_source_evidence_invalid", 422)
    encoded = _encoded(facts.model_dump(mode="json"))
    if len(encoded) > MAX_RECORD_BYTES:
        _error("trademark_source_size_invalid", 422)
    key, normalized_hash = record_key(facts), _hash(encoded)
    request_hash = fingerprint({"record": normalized_hash, "endpoint": request_url,
        "cursor": expected_cursor_version, "received_at": received_at.isoformat()})
    try:
        with _savepoint(session):
            selected = _selection(session, policy.source_key)
            if not selected or selected.permission_id != permission_id or selected.generation != expected_generation:
                _error("trademark_source_selection_conflict")
            replay = session.scalar(select(TrademarkSourceReceipt).where(
                TrademarkSourceReceipt.permission_id == permission_id,
                TrademarkSourceReceipt.generation == expected_generation,
                TrademarkSourceReceipt.request_key == request_key))
            if replay:
                if replay.request_hash != request_hash:
                    _error("trademark_source_request_conflict")
                return deepcopy(replay.change)
            if (selected.cursor_version != expected_cursor_version
                    or selected.last_received_at and received_at < _utc(selected.last_received_at)):
                _error("trademark_source_cursor_conflict")
            if session.scalar(select(func.count()).select_from(TrademarkSourceReceipt).where(
                    TrademarkSourceReceipt.permission_id == permission_id)) >= MAX_RECEIPTS:
                _error("trademark_source_capacity")
            head = session.get(TrademarkRegisterHead, (permission_id, key), populate_existing=True)
            previous = session.get(TrademarkRegisterRevision, head.revision_id) if head else None
            if previous is not None and previous.normalized_payload is not None:
                _restore(previous)
            # Expired payload is never resurrected or given a new retention date.
            reusable = (previous is not None and previous.normalized_hash == normalized_hash
                and previous.normalized_payload is not None and previous.raw_payload is not None
                and _utc(previous.normalized_expires_at) > now and _utc(previous.raw_expires_at) > now)
            material = previous is None or previous.material_hash != facts.material_fingerprint()
            row = previous
            if not reusable:
                count, retained = session.execute(select(func.count(),
                    func.coalesce(func.sum(func.coalesce(func.length(TrademarkRegisterRevision.raw_payload), 0)
                        + func.coalesce(func.length(TrademarkRegisterRevision.normalized_payload), 0)), 0))
                    .where(TrademarkRegisterRevision.permission_id == permission_id)).one()
                if count >= MAX_REVISIONS or retained + len(raw) + len(encoded) > MAX_RETAINED_BYTES:
                    _error("trademark_source_capacity")
                row = TrademarkRegisterRevision(permission_id=permission_id, record_key=key,
                    sequence=previous.sequence + 1 if previous else 1,
                    material_sequence=previous.material_sequence + int(material) if previous else 1,
                    material_hash=facts.material_fingerprint(), raw_hash=facts.source_sha256,
                    raw_payload=raw if received_at + timedelta(seconds=policy.raw_retention_seconds) > now else None,
                    raw_expires_at=min(_clock(policy.valid_until), received_at + timedelta(seconds=policy.raw_retention_seconds)),
                    normalized_hash=normalized_hash, normalized_payload=encoded,
                    normalized_expires_at=min(_clock(policy.valid_until), received_at + timedelta(seconds=policy.normalized_retention_seconds)),
                    received_at=received_at)
                session.add(row)
                session.flush()
            if head is None:
                session.add(TrademarkRegisterHead(permission_id=permission_id, record_key=key,
                    revision_id=row.id, generation=expected_generation, last_seen_at=received_at))
            else:
                head.revision_id, head.generation, head.last_seen_at = row.id, expected_generation, received_at
            changed = session.execute(update(TrademarkSourceSelection).where(
                TrademarkSourceSelection.source_key == policy.source_key,
                TrademarkSourceSelection.permission_id == permission_id,
                TrademarkSourceSelection.generation == expected_generation,
                TrademarkSourceSelection.cursor_version == expected_cursor_version).values(
                cursor_version=expected_cursor_version + 1, last_received_at=received_at)
                .execution_options(synchronize_session=False))
            if changed.rowcount != 1:
                _error("trademark_source_cursor_conflict")
            result = {"record_key": key, "revision_id": row.id, "sequence": row.sequence,
                "material_sequence": row.material_sequence, "material_changed": material,
                "change": "first_seen" if previous is None else "material" if material else "unchanged" if reusable else "evidence",
                "cursor_version": expected_cursor_version + 1}
            session.add(TrademarkSourceReceipt(permission_id=permission_id, record_key=key, revision_id=row.id,
                generation=expected_generation, cursor_version=expected_cursor_version + 1, request_key=request_key,
                request_hash=request_hash, received_at=received_at, change=result))
            session.flush()
            return result
    except IntegrityError:
        _error("trademark_source_cursor_conflict")


def read_revision(session, permission_id, revision_id, *, now, purpose="display"):
    now = _clock(now)
    require_permission(session, permission_id, now=now, purpose=purpose)
    row = session.scalar(select(TrademarkRegisterRevision).where(TrademarkRegisterRevision.id == revision_id,
        TrademarkRegisterRevision.permission_id == permission_id).execution_options(populate_existing=True))
    if row is None or _utc(row.normalized_expires_at) <= now:
        _error("trademark_evidence_unavailable")
    return _restore(row)


def read_current(session, source_key, *, now, purpose="display", limit=50, after=None):
    now = _clock(now)
    if type(limit) is not int or not 1 <= limit <= 100 or after is not None and (
            not isinstance(after, str) or len(after) != 64 or any(c not in "0123456789abcdef" for c in after)):
        _error("trademark_source_page_invalid", 422)
    selected = _selection(session, source_key, lock=False)
    if selected is None:
        _error("trademark_source_not_selected")
    permission_id, generation = selected.permission_id, selected.generation
    _, policy = require_permission(session, permission_id, now=now, purpose=purpose)
    # Same permission-before-selection lock order as acquisition and activation.
    selected = _selection(session, source_key)
    if selected.permission_id != permission_id or selected.generation != generation:
        _error("trademark_source_selection_conflict")
    query = select(TrademarkRegisterHead, TrademarkRegisterRevision).outerjoin(TrademarkRegisterRevision,
        (TrademarkRegisterRevision.id == TrademarkRegisterHead.revision_id)
        & (TrademarkRegisterRevision.permission_id == TrademarkRegisterHead.permission_id)
        & (TrademarkRegisterRevision.record_key == TrademarkRegisterHead.record_key)).where(
            TrademarkRegisterHead.permission_id == selected.permission_id, TrademarkRegisterHead.generation == selected.generation)
    if after:
        query = query.where(TrademarkRegisterHead.record_key > after)
    items, next_cursor = [], None
    # The permission and selection remain locked for the whole page. Stream a
    # bounded group of payloads; do not reload that permission for every row.
    with session.execute(query.order_by(TrademarkRegisterHead.record_key).limit(limit + 1)
            .execution_options(populate_existing=True, yield_per=10)) as rows:
        for index, (head, revision) in enumerate(rows):
            if index == limit:
                next_cursor = items[-1]["record_key"]
                break
            item = {"record_key": head.record_key, "revision_id": head.revision_id}
            try:
                if now - _utc(head.last_seen_at) > timedelta(seconds=policy.max_age_seconds) or _utc(head.last_seen_at) > now:
                    _error("trademark_evidence_stale")
                if revision is None or _utc(revision.normalized_expires_at) <= now:
                    _error("trademark_evidence_unavailable")
                item.update(state="available", facts=_restore(revision))
            except DomainError as error:
                if error.code not in {"trademark_evidence_stale", "trademark_evidence_unavailable"}:
                    raise
                item.update(state="unavailable", reason=error.code)
            items.append(item)
    return {"permission_id": selected.permission_id, "generation": selected.generation,
        "cursor_version": selected.cursor_version, "items": items,
        "next_cursor": next_cursor, "coverage_verified": False}


def purge_content(session, *, now, permission_id=None):
    now = _clock(now)
    invalid = select(TrademarkSourcePermission.id).where(
        (TrademarkSourcePermission.revoked_at.is_not(None)) | (TrademarkSourcePermission.valid_until <= now))
    scope = [TrademarkRegisterRevision.permission_id == permission_id] if permission_id else []
    raw = session.execute(update(TrademarkRegisterRevision).where(*scope, TrademarkRegisterRevision.raw_payload.is_not(None),
        (TrademarkRegisterRevision.raw_expires_at <= now) | TrademarkRegisterRevision.permission_id.in_(invalid))
        .values(raw_payload=None).execution_options(synchronize_session=False))
    normalized = session.execute(update(TrademarkRegisterRevision).where(*scope, TrademarkRegisterRevision.normalized_payload.is_not(None),
        (TrademarkRegisterRevision.normalized_expires_at <= now) | TrademarkRegisterRevision.permission_id.in_(invalid))
        .values(normalized_payload=None).execution_options(synchronize_session=False))
    return {"raw_rows": raw.rowcount, "normalized_rows": normalized.rowcount}


def revoke_permission(session, permission_id, *, now):
    now = _clock(now)
    row = session.scalar(select(TrademarkSourcePermission).where(TrademarkSourcePermission.id == permission_id)
        .with_for_update().execution_options(populate_existing=True))
    if row is None:
        _error("trademark_permission_unavailable")
    if row.revoked_at is None:
        row.revoked_at = now
        session.flush()
    return purge_content(session, now=now, permission_id=permission_id)


def cleanup(database, *, now=None):
    """Retention remains enforced when feature/source switches are disabled."""
    from .ipi_acquisition import cleanup as cleanup_ipi
    with database.session(include_all_organizations=True) as session:
        instant = now or datetime.now(UTC)
        result = purge_content(session, now=instant)
        result["ipi"] = cleanup_ipi(session, now=instant)
        session.commit()
        return result
