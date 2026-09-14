"""Internal permitted auction journal. No accounts, HTTP, public write API or email.

A native collector must verify the transport and normalize the complete record
before calling accept_record. Callers own commits; each mutation is atomic in a
savepoint. Raw evidence must not contain private user profile queries.
Reading records is not evidence that complete auction listing coverage succeeded.
"""

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from urllib.parse import unquote, urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from .aste_contracts import AsteAccess
from .auction_contracts import CANTONS, AuctionFacts, Category, fingerprint, visible
from .auction_source_models import (
    AuctionSourcePermission,
    AuctionSourceReceipt,
    AuctionSourceRecordHead,
    AuctionSourceRecordRevision,
    AuctionSourceSelection,
)
from .config import DomainError
from .monitoring_subjects import _savepoint

MAX_RECORD_BYTES = 2 * 1024 * 1024
MAX_REVISIONS = 200_000
MAX_RECEIPTS = 500_000
MAX_RETAINED_BYTES = 2 * 1024 * 1024 * 1024


def _error(code, status=409):
    raise DomainError("Auction evidence or source permission is unavailable.", status, code) from None


def _clock(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        _error("auction_source_clock_invalid", 422)
    return value.astimezone(UTC)


def _utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def permitted_url(base, value):
    """A reviewed HTTPS path subtree, never a credential or arbitrary fetch URL."""
    try:
        root, target = urlsplit(base), urlsplit(value)
        decoded = unquote(target.path, errors="strict")
        return (root.scheme == target.scheme == "https" and root.hostname == target.hostname
            and root.port in (None, 443) and target.port in (None, 443)
            and not target.username and not target.password and not target.query and not target.fragment
            and root.path.endswith("/") and target.path.startswith(root.path) and decoded.startswith(root.path)
            and not any(segment in {".", ".."} for segment in decoded.split("/"))
            and "%" not in decoded and "\\" not in decoded
            and not any(ord(c) < 33 for c in value))
    except (ValueError, UnicodeError, TypeError):
        return False


class AuctionSourcePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    source_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    reference: str = Field(min_length=1, max_length=1000)
    attribution: str = Field(min_length=1, max_length=1000)
    endpoint: str = Field(min_length=1, max_length=2048)
    accepted_at: datetime
    valid_until: datetime
    cantons: tuple[str, ...] = Field(min_length=1, max_length=26)
    categories: tuple[Category, ...] = Field(min_length=1, max_length=8)
    min_poll_seconds: int = Field(ge=60, le=7 * 86400)
    max_age_seconds: int = Field(ge=1, le=86400)
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
    native_access: AsteAccess | None = None

    @model_serializer(mode="wrap")
    def preserve_existing_policies(self, handler):
        result = handler(self)
        if self.native_access is None:
            result.pop("native_access", None)
        return result

    @model_validator(mode="after")
    def reviewed(self):
        if self.native_access and (
                self.source_key != "aste-ti" or self.endpoint != "https://www.aste.ti.ch/"
                or self.cantons != ("TI",) or self.raw_retention_seconds < 120
                or not {v.category for v in self.native_access.category_mapping.values()}.issubset(self.categories)):
            raise ValueError("The native access plan must fit the reviewed source scope")
        for value in (self.reference, self.attribution):
            visible(value)
        address = urlsplit(self.endpoint)
        if (any(v.tzinfo is None or v.utcoffset() is None for v in (self.accepted_at, self.valid_until))
                or self.accepted_at >= self.valid_until
                or self.raw_retention_seconds > self.normalized_retention_seconds
                or not self.retain_minimal_audit or len(set(self.cantons)) != len(self.cantons)
                or not set(self.cantons).issubset(CANTONS) or len(set(self.categories)) != len(self.categories)
                or address.scheme != "https" or not address.hostname or address.username or address.password
                or address.query or address.fragment or address.port not in (None, 443)
                or any(c.isspace() for c in self.endpoint) or not permitted_url(self.endpoint, self.endpoint)):
            raise ValueError("Invalid reviewed auction source policy")
        return self


def record_permission(session, *, policy):
    policy = AuctionSourcePolicy.model_validate(policy)
    payload = policy.model_dump(mode="json")
    row = AuctionSourcePermission(policy=payload, policy_hash=fingerprint(payload),
        accepted_at=_clock(policy.accepted_at), valid_until=_clock(policy.valid_until))
    session.add(row)
    session.flush()
    return row.id


def require_permission(session, permission_id, *, now, purpose="storage"):
    now = _clock(now)
    row = session.scalar(select(AuctionSourcePermission).where(AuctionSourcePermission.id == permission_id)
        .with_for_update().execution_options(populate_existing=True))
    if row is None or row.revoked_at is not None or not _utc(row.accepted_at) <= now < _utc(row.valid_until):
        _error("auction_permission_unavailable")
    try:
        encoded = _encoded(row.policy)
        policy = AuctionSourcePolicy.model_validate_json(encoded, strict=True)
        if (_hash(encoded) != row.policy_hash or _clock(policy.accepted_at) != _utc(row.accepted_at)
                or _clock(policy.valid_until) != _utc(row.valid_until)):
            _error("auction_permission_invalid", 503)
    except (ValueError, TypeError):
        _error("auction_permission_invalid", 503)
    allowed = {"storage": policy.store_source_allowed, "acquisition": policy.automated_access_allowed,
        "matching": policy.matching_allowed, "display": policy.display_allowed,
        "notification": policy.notifications_allowed, "export": policy.export_allowed,
        "decision": policy.private_decisions_allowed}
    if not allowed.get(purpose, False):
        _error("auction_source_use_denied", 403)
    return row, policy


def _selection(session, source_key, *, lock=True):
    query = select(AuctionSourceSelection).where(AuctionSourceSelection.source_key == source_key)
    return session.scalar((query.with_for_update() if lock else query).execution_options(populate_existing=True))


def activate_permission(session, permission_id, *, expected_generation, now):
    _, policy = require_permission(session, permission_id, now=now, purpose="acquisition")
    require_permission(session, permission_id, now=now)
    if type(expected_generation) is not int or expected_generation < 0:
        _error("auction_generation_invalid", 422)
    try:
        with _savepoint(session):
            current = _selection(session, policy.source_key)
            if (current.generation if current else 0) != expected_generation:
                _error("auction_source_selection_conflict")
            if current is None:
                session.add(AuctionSourceSelection(source_key=policy.source_key, permission_id=permission_id,
                    generation=1, cursor_version=0))
            else:
                changed = session.execute(update(AuctionSourceSelection).where(
                    AuctionSourceSelection.source_key == policy.source_key,
                    AuctionSourceSelection.generation == expected_generation).values(
                    permission_id=permission_id, generation=expected_generation + 1,
                    cursor_version=0, last_received_at=None).execution_options(synchronize_session=False))
                if changed.rowcount != 1:
                    _error("auction_source_selection_conflict")
            session.flush()
    except IntegrityError:
        _error("auction_source_selection_conflict")
    return expected_generation + 1


def record_key(facts):
    return facts.identity()


def _restore(row):
    if row.normalized_payload is None or _hash(row.normalized_payload) != row.normalized_hash:
        _error("auction_evidence_unavailable")
    if row.raw_payload is not None and _hash(row.raw_payload) != row.raw_hash:
        _error("auction_evidence_unavailable")
    try:
        facts = AuctionFacts.model_validate_json(row.normalized_payload)
    except ValueError:
        _error("auction_evidence_unavailable")
    if (facts.state_hash() != row.state_hash or record_key(facts) != row.record_key
            or facts.raw_sha256 != row.raw_hash):
        _error("auction_evidence_unavailable")
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
        _error("auction_source_request_invalid", 422)
    if (received_at > now or now - received_at > timedelta(seconds=policy.max_age_seconds)
            or now - received_at >= timedelta(seconds=policy.normalized_retention_seconds)
            or received_at < _clock(policy.accepted_at)):
        _error("auction_source_time_invalid", 422)
    if not permitted_url(policy.endpoint, request_url):
        _error("auction_source_endpoint_denied", 403)
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_RECORD_BYTES:
        _error("auction_source_size_invalid", 422)
    facts = AuctionFacts.model_validate(facts)
    if (facts.raw_sha256 != _hash(raw) or facts.source_key != policy.source_key
            or facts.canton not in policy.cantons or facts.category is not None and facts.category not in policy.categories
            or facts.observed_at != received_at or not permitted_url(policy.endpoint, facts.source_url)):
        _error("auction_source_evidence_invalid", 422)
    encoded = _encoded(facts.model_dump(mode="json"))
    if len(encoded) > MAX_RECORD_BYTES:
        _error("auction_source_size_invalid", 422)
    key, normalized_hash = record_key(facts), _hash(encoded)
    request_hash = fingerprint({"record": normalized_hash, "endpoint": request_url,
        "cursor": expected_cursor_version, "received_at": received_at.isoformat()})
    try:
        with _savepoint(session):
            selected = _selection(session, policy.source_key)
            if not selected or selected.permission_id != permission_id or selected.generation != expected_generation:
                _error("auction_source_selection_conflict")
            replay = session.scalar(select(AuctionSourceReceipt).where(
                AuctionSourceReceipt.permission_id == permission_id,
                AuctionSourceReceipt.generation == expected_generation,
                AuctionSourceReceipt.request_key == request_key))
            if replay:
                if replay.request_hash != request_hash:
                    _error("auction_source_request_conflict")
                return deepcopy(replay.change)
            if (selected.cursor_version != expected_cursor_version
                    or selected.last_received_at and received_at < _utc(selected.last_received_at)):
                _error("auction_source_cursor_conflict")
            if session.scalar(select(func.count()).select_from(AuctionSourceReceipt).where(
                    AuctionSourceReceipt.permission_id == permission_id)) >= MAX_RECEIPTS:
                _error("auction_source_capacity")
            head = session.get(AuctionSourceRecordHead, (permission_id, key), populate_existing=True)
            previous = session.get(AuctionSourceRecordRevision, head.revision_id) if head else None
            if previous is not None and previous.normalized_payload is not None:
                _restore(previous)
            # Expired payload is never resurrected or given a new retention date.
            reusable = (previous is not None and previous.normalized_hash == normalized_hash
                and previous.normalized_payload is not None and previous.raw_payload is not None
                and _utc(previous.normalized_expires_at) > now and _utc(previous.raw_expires_at) > now)
            material = previous is None or previous.state_hash != facts.state_hash()
            row = previous
            if not reusable:
                count, retained = session.execute(select(func.count(),
                    func.coalesce(func.sum(func.coalesce(func.length(AuctionSourceRecordRevision.raw_payload), 0)
                        + func.coalesce(func.length(AuctionSourceRecordRevision.normalized_payload), 0)), 0))
                    .where(AuctionSourceRecordRevision.permission_id == permission_id)).one()
                if count >= MAX_REVISIONS or retained + len(raw) + len(encoded) > MAX_RETAINED_BYTES:
                    _error("auction_source_capacity")
                row = AuctionSourceRecordRevision(permission_id=permission_id, record_key=key,
                    sequence=previous.sequence + 1 if previous else 1,
                    state_sequence=previous.state_sequence + int(material) if previous else 1,
                    state_hash=facts.state_hash(), raw_hash=facts.raw_sha256,
                    raw_payload=raw if received_at + timedelta(seconds=policy.raw_retention_seconds) > now else None,
                    raw_expires_at=min(_clock(policy.valid_until), received_at + timedelta(seconds=policy.raw_retention_seconds)),
                    normalized_hash=normalized_hash, normalized_payload=encoded,
                    normalized_expires_at=min(_clock(policy.valid_until), received_at + timedelta(seconds=policy.normalized_retention_seconds)),
                    received_at=received_at)
                session.add(row)
                session.flush()
            if head is None:
                session.add(AuctionSourceRecordHead(permission_id=permission_id, record_key=key,
                    revision_id=row.id, generation=expected_generation, last_seen_at=received_at))
            else:
                head.revision_id, head.generation, head.last_seen_at = row.id, expected_generation, received_at
            changed = session.execute(update(AuctionSourceSelection).where(
                AuctionSourceSelection.source_key == policy.source_key,
                AuctionSourceSelection.permission_id == permission_id,
                AuctionSourceSelection.generation == expected_generation,
                AuctionSourceSelection.cursor_version == expected_cursor_version).values(
                cursor_version=expected_cursor_version + 1, last_received_at=received_at)
                .execution_options(synchronize_session=False))
            if changed.rowcount != 1:
                _error("auction_source_cursor_conflict")
            result = {"record_key": key, "revision_id": row.id, "sequence": row.sequence,
                "state_sequence": row.state_sequence, "state_changed": material,
                "change": "first_seen" if previous is None else "state" if material else "unchanged" if reusable else "evidence",
                "cursor_version": expected_cursor_version + 1}
            session.add(AuctionSourceReceipt(permission_id=permission_id, record_key=key, revision_id=row.id,
                generation=expected_generation, cursor_version=expected_cursor_version + 1, request_key=request_key,
                request_hash=request_hash, received_at=received_at, change=result))
            session.flush()
            return result
    except IntegrityError:
        _error("auction_source_cursor_conflict")


def read_revision(session, permission_id, revision_id, *, now, purpose="display"):
    now = _clock(now)
    require_permission(session, permission_id, now=now, purpose=purpose)
    row = session.scalar(select(AuctionSourceRecordRevision).where(AuctionSourceRecordRevision.id == revision_id,
        AuctionSourceRecordRevision.permission_id == permission_id).execution_options(populate_existing=True))
    if row is None or _utc(row.normalized_expires_at) <= now:
        _error("auction_evidence_unavailable")
    return _restore(row)


def read_original(session, permission_id, revision_id, *, now):
    """Exact bytes only where the current source policy permits export."""
    now = _clock(now)
    require_permission(session, permission_id, now=now, purpose="export")
    row = session.scalar(select(AuctionSourceRecordRevision).where(AuctionSourceRecordRevision.id == revision_id,
        AuctionSourceRecordRevision.permission_id == permission_id).execution_options(populate_existing=True))
    if row is None or row.raw_payload is None or _utc(row.raw_expires_at) <= now or _hash(row.raw_payload) != row.raw_hash:
        _error("auction_evidence_unavailable")
    return row.raw_payload


def read_current(session, source_key, *, now, purpose="display", limit=50, after=None):
    now = _clock(now)
    if type(limit) is not int or not 1 <= limit <= 100 or after is not None and (
            not isinstance(after, str) or len(after) != 64 or any(c not in "0123456789abcdef" for c in after)):
        _error("auction_source_page_invalid", 422)
    selected = _selection(session, source_key, lock=False)
    if selected is None:
        _error("auction_source_not_selected")
    permission_id, generation = selected.permission_id, selected.generation
    _, policy = require_permission(session, permission_id, now=now, purpose=purpose)
    # Same permission-before-selection lock order as acquisition and activation.
    selected = _selection(session, source_key)
    if selected.permission_id != permission_id or selected.generation != generation:
        _error("auction_source_selection_conflict")
    query = select(AuctionSourceRecordHead).where(AuctionSourceRecordHead.permission_id == selected.permission_id,
        AuctionSourceRecordHead.generation == selected.generation)
    if after:
        query = query.where(AuctionSourceRecordHead.record_key > after)
    heads = list(session.scalars(query.order_by(AuctionSourceRecordHead.record_key).limit(limit + 1)
        .execution_options(populate_existing=True)))
    items = []
    for head in heads[:limit]:
        item = {"record_key": head.record_key, "revision_id": head.revision_id}
        try:
            if now - _utc(head.last_seen_at) > timedelta(seconds=policy.max_age_seconds) or _utc(head.last_seen_at) > now:
                _error("auction_evidence_stale")
            facts = read_revision(session, selected.permission_id, head.revision_id, now=now, purpose=purpose)
            item.update(state="available", facts=facts)
        except DomainError as error:
            if error.code not in {"auction_evidence_stale", "auction_evidence_unavailable"}:
                raise
            item.update(state="unavailable", reason=error.code)
        items.append(item)
    return {"permission_id": selected.permission_id, "generation": selected.generation,
        "cursor_version": selected.cursor_version, "items": items,
        "next_cursor": heads[limit - 1].record_key if len(heads) > limit else None,
        "coverage_verified": False}


def purge_content(session, *, now, permission_id=None):
    now = _clock(now)
    invalid = select(AuctionSourcePermission.id).where(
        (AuctionSourcePermission.revoked_at.is_not(None)) | (AuctionSourcePermission.valid_until <= now))
    scope = [AuctionSourceRecordRevision.permission_id == permission_id] if permission_id else []
    raw = session.execute(update(AuctionSourceRecordRevision).where(*scope, AuctionSourceRecordRevision.raw_payload.is_not(None),
        (AuctionSourceRecordRevision.raw_expires_at <= now) | AuctionSourceRecordRevision.permission_id.in_(invalid))
        .values(raw_payload=None).execution_options(synchronize_session=False))
    normalized = session.execute(update(AuctionSourceRecordRevision).where(*scope, AuctionSourceRecordRevision.normalized_payload.is_not(None),
        (AuctionSourceRecordRevision.normalized_expires_at <= now) | AuctionSourceRecordRevision.permission_id.in_(invalid))
        .values(normalized_payload=None).execution_options(synchronize_session=False))
    return {"raw_rows": raw.rowcount, "normalized_rows": normalized.rowcount}


def revoke_permission(session, permission_id, *, now):
    now = _clock(now)
    row = session.scalar(select(AuctionSourcePermission).where(AuctionSourcePermission.id == permission_id)
        .with_for_update().execution_options(populate_existing=True))
    if row is None:
        _error("auction_permission_unavailable")
    if row.revoked_at is None:
        row.revoked_at = now
        session.flush()
    return purge_content(session, now=now, permission_id=permission_id)


def cleanup(database, *, now=None):
    """Retention remains enforced when feature/source switches are disabled."""
    with database.session(include_all_organizations=True) as session:
        result = purge_content(session, now=now or datetime.now(UTC))
        session.commit()
        return result
