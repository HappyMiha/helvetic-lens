"""Internal permission-bound CAP journal; no source accounts, network or delivery.

Callers own the transaction. A collector must prove transport against the reviewed
endpoint before calling accept_message. No public permission-write/raw-export API
exists. User ownership and email consent belong to the later private projection.
"""

import hashlib
import json
from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from .config import DomainError
from .hazard_cap import CAPMessage, decode_cap
from .hazard_contracts import Canton, Hazard
from .hazard_models import HazardEventRevision
from .hazard_reconciliation import (
    MAX_MESSAGES,
    MAX_RETAINED_BYTES,
    HazardHead,
    HazardSourceState,
    StoredHazard,
    reconcile_cap,
)
from .hazard_source_models import (
    HazardCurrentWarning,
    HazardMessageEvidence,
    HazardSourcePermission,
    HazardSourceReceipt,
    HazardSourceSelection,
)
from .monitoring_subjects import _savepoint

CODEC = TypeAdapter(CAPMessage)
MAX_EVIDENCE_ROWS = 100_000
MAX_RECEIPTS = 200_000
MAX_RAW_BYTES = 64 * 1024 * 1024


class HazardRule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    hazard: Hazard
    value_name: str = Field(min_length=1, max_length=256)
    value: str = Field(min_length=1, max_length=256)


class HazardSourcePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    source_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    reference: str = Field(min_length=1, max_length=500)
    attribution: str = Field(min_length=1, max_length=1000)
    endpoint: str = Field(min_length=1, max_length=2048)
    sender: str = Field(min_length=1, max_length=256)
    accepted_at: datetime
    valid_until: datetime
    min_poll_seconds: int = Field(ge=30, le=86400)
    max_age_seconds: int = Field(ge=1, le=86400)
    raw_retention_seconds: int = Field(ge=0, le=7 * 86400)
    normalized_retention_seconds: int = Field(ge=1, le=366 * 86400)
    store_full_message: bool
    retain_minimal_audit: bool
    matching_allowed: bool
    display_allowed: bool
    notifications_allowed: bool
    private_decisions_allowed: bool = False
    coverage: tuple["HazardCoverage", ...] = Field(default=(), max_length=6)
    covered_cantons: tuple[Canton, ...] = Field(min_length=1, max_length=26)
    geocode_version: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    rules: tuple[HazardRule, ...] = Field(min_length=1, max_length=32)
    importance: tuple[tuple[Literal["Extreme", "Severe", "Moderate", "Minor"],
                            Literal["information", "warning", "alarm"]], ...] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def reviewed_contract(self):
        if any(v.tzinfo is None or v.utcoffset() is None for v in (self.accepted_at, self.valid_until)):
            raise ValueError("Source contract timestamps require an explicit timezone")
        accepted, valid = _clock(self.accepted_at), _clock(self.valid_until)
        address = urlsplit(self.endpoint)
        if (valid <= accepted or self.raw_retention_seconds > self.normalized_retention_seconds
                or not self.store_full_message or not self.retain_minimal_audit
                or address.scheme != "https" or not address.hostname or address.username or address.password
                or address.port not in (None, 443) or address.query or address.fragment
                or any(c.isspace() for c in self.endpoint)
                or any(not v.strip() for v in (self.sender, self.reference, self.attribution))
                or len(set(self.covered_cantons)) != len(self.covered_cantons)
                or len({(r.value_name, r.value) for r in self.rules}) != len(self.rules)
                or len({name for name, _ in self.importance}) != len(self.importance)):
            raise ValueError("Invalid reviewed hazard source contract")
        if (len({entry.hazard for entry in self.coverage}) != len(self.coverage)
                or any(entry.hazard not in {rule.hazard for rule in self.rules}
                    or not set(entry.cantons) <= set(self.covered_cantons)
                    or entry.valid_until > self.valid_until for entry in self.coverage)):
            raise ValueError("Coverage must stay within the reviewed source contract")
        return self


class HazardCoverage(BaseModel):
    """Operator-reviewed publisher jurisdiction; a message's area is not coverage."""
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    hazard: Hazard
    cantons: tuple[Canton, ...] = Field(min_length=1, max_length=26)
    evidence_reference: str = Field(min_length=1, max_length=1000)
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    checked_at: datetime
    valid_until: datetime

    @model_validator(mode="after")
    def current_review(self):
        if (not self.evidence_reference.strip() or len(set(self.cantons)) != len(self.cantons)
                or any(value.tzinfo is None or value.utcoffset() is None for value in (self.checked_at, self.valid_until))
                or self.checked_at >= self.valid_until):
            raise ValueError("Invalid source coverage evidence")
        return self


def _error(code, status=409):
    raise DomainError("Official warning evidence or source permission is unavailable.", status, code) from None


def _clock(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        _error("hazard_source_clock_invalid", 422)
    return value.astimezone(UTC)


def _utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def record_permission(session, *, policy):
    policy = HazardSourcePolicy.model_validate(policy)
    payload = policy.model_dump(mode="json")
    row = HazardSourcePermission(policy=payload, policy_hash=_hash(_encoded(payload)),
        accepted_at=_clock(policy.accepted_at), valid_until=_clock(policy.valid_until))
    session.add(row)
    session.flush()
    return row.id


def require_permission(session, permission_id, *, now, purpose="storage"):
    now = _clock(now)
    row = session.scalar(select(HazardSourcePermission).where(HazardSourcePermission.id == permission_id)
        .with_for_update().execution_options(populate_existing=True))
    if row is None or row.revoked_at is not None or not _utc(row.accepted_at) <= now < _utc(row.valid_until):
        _error("hazard_permission_unavailable")
    try:
        encoded = _encoded(row.policy)
        policy = HazardSourcePolicy.model_validate_json(encoded, strict=True)
        if (_hash(encoded) != row.policy_hash or _clock(policy.accepted_at) != _utc(row.accepted_at)
                or _clock(policy.valid_until) != _utc(row.valid_until)):
            _error("hazard_permission_invalid", 503)
    except (ValueError, TypeError):
        _error("hazard_permission_invalid", 503)
    allowed = {"storage": policy.store_full_message, "matching": policy.matching_allowed,
               "display": policy.display_allowed, "notification": policy.notifications_allowed}
    if not allowed.get(purpose, False):
        _error("hazard_source_use_denied", 403)
    return row, policy


def _selection(session, key):
    return session.scalar(select(HazardSourceSelection).where(HazardSourceSelection.source_key == key)
        .with_for_update().execution_options(populate_existing=True))


def activate_permission(session, permission_id, *, expected_generation, now):
    _, policy = require_permission(session, permission_id, now=now)
    if type(expected_generation) is not int or expected_generation < 0:
        _error("hazard_generation_invalid", 422)
    try:
        with _savepoint(session):
            current = _selection(session, policy.source_key)
            if (current.generation if current else 0) != expected_generation:
                _error("hazard_source_selection_conflict")
            if current is None:
                current = HazardSourceSelection(source_key=policy.source_key, permission_id=permission_id,
                                                generation=1, cursor_version=0)
                session.add(current)
            else:
                updated = session.execute(update(HazardSourceSelection).where(
                    HazardSourceSelection.source_key == policy.source_key,
                    HazardSourceSelection.generation == expected_generation).values(
                    permission_id=permission_id, generation=expected_generation + 1, cursor_version=0,
                    last_received_at=None, last_poll_at=None, last_poll_hash=None,
                    poll_cursor_version=None).execution_options(synchronize_session=False))
                if updated.rowcount != 1:
                    _error("hazard_source_selection_conflict")
            session.flush()
            return expected_generation + 1
    except IntegrityError:
        _error("hazard_source_selection_conflict")


def purge_content(session, *, now, permission_id=None):
    now = _clock(now)
    invalid = select(HazardSourcePermission.id).where(
        (HazardSourcePermission.revoked_at.is_not(None)) | (HazardSourcePermission.valid_until <= now))
    scoped = [HazardMessageEvidence.permission_id == permission_id] if permission_id else []
    raw = session.execute(update(HazardMessageEvidence).where(*scoped,
        (HazardMessageEvidence.raw_expires_at <= now) | HazardMessageEvidence.permission_id.in_(invalid))
        .values(raw_payload=None).execution_options(synchronize_session=False))
    normalized = session.execute(update(HazardMessageEvidence).where(*scoped,
        (HazardMessageEvidence.normalized_expires_at <= now) | HazardMessageEvidence.permission_id.in_(invalid))
        .values(normalized_payload=None, classification={}).execution_options(synchronize_session=False))
    expired_evidence = select(HazardMessageEvidence.id).where(*scoped,
        (HazardMessageEvidence.normalized_payload.is_(None)) | (HazardMessageEvidence.normalized_expires_at <= now)
        | HazardMessageEvidence.permission_id.in_(invalid))
    private = session.execute(update(HazardEventRevision).where(HazardEventRevision.evidence_id.in_(expired_evidence))
        .values(decision={}, proof={}).execution_options(synchronize_session=False, include_all_organizations=True))
    return {"raw_rows": raw.rowcount, "normalized_rows": normalized.rowcount, "private_rows": private.rowcount}


def revoke_permission(session, permission_id, *, now):
    now = _clock(now)
    row = session.scalar(select(HazardSourcePermission).where(HazardSourcePermission.id == permission_id)
                         .with_for_update().execution_options(populate_existing=True))
    if row is None:
        _error("hazard_permission_unavailable")
    if row.revoked_at is None:
        row.revoked_at = now
        session.flush()
    return purge_content(session, now=now, permission_id=permission_id)


def _restore(row):
    payload = row.normalized_payload
    if payload is None or _hash(payload) != row.normalized_hash:
        _error("hazard_evidence_unavailable")
    try:
        message = CODEC.validate_json(payload)
    except ValueError:
        _error("hazard_evidence_invalid", 503)
    if message.identity.key != row.message_key or message.evidence_hash != row.raw_hash:
        _error("hazard_evidence_invalid", 503)
    return message


def _state(session, permission_id, sender, now):
    retained_filter = (
        HazardMessageEvidence.permission_id == permission_id, HazardMessageEvidence.normalized_payload.is_not(None),
        HazardMessageEvidence.normalized_expires_at > now)
    total_bytes = session.scalar(select(func.coalesce(func.sum(func.length(HazardMessageEvidence.normalized_payload)), 0))
                                 .where(*retained_filter))
    if total_bytes > MAX_RETAINED_BYTES:
        _error("hazard_history_byte_limit")
    rows = list(session.scalars(select(HazardMessageEvidence).where(*retained_filter).limit(MAX_MESSAGES + 1)
        .execution_options(populate_existing=True)))
    if len(rows) > MAX_MESSAGES:
        _error("hazard_history_limit")
    retained = {r.id: r for r in rows}
    entries = tuple(StoredHazard(_restore(r), r.development_key, r.material_sequence, _utc(r.last_seen_at),
                                len(r.normalized_payload)) for r in rows)
    current = list(session.scalars(select(HazardCurrentWarning).join(
        HazardMessageEvidence, HazardMessageEvidence.id == HazardCurrentWarning.evidence_id)
        .where(*retained_filter, HazardCurrentWarning.permission_id == permission_id)
        .execution_options(populate_existing=True)))
    heads = tuple(HazardHead(h.development_key, retained[h.evidence_id].message_key, h.material_sequence, h.state)
                  for h in current if h.evidence_id in retained)
    if ({e.development_id for e in entries} - {h.development_id for h in heads}
            or any(h.material_sequence != retained[h.evidence_id].material_sequence
                   or h.state != _restore(retained[h.evidence_id]).state for h in current if h.evidence_id in retained)):
        _error("hazard_history_head_unavailable")
    return HazardSourceState(sender, entries, heads)


def classify(message, policy):
    if not message.infos:
        return {"hazards": [], "importance": None, "complete": False}
    info = message.infos[0]
    rules = {(r.value_name, r.value): r.hazard for r in policy.rules}
    known_names = {name for name, _ in rules}
    relevant = {pair for pair in info.event_codes if pair[0] in known_names}
    hazards = sorted({rules[pair] for pair in relevant if pair in rules})
    importance = dict(policy.importance).get(info.severity)
    return {"hazards": hazards, "importance": importance,
            "complete": bool(hazards) and relevant <= rules.keys() and importance is not None}


def _accepted(row, replay):
    return {"evidence_id": row.evidence_id, "generation": row.generation, "cursor_version": row.cursor_version,
            "change": deepcopy(row.change), "replay": replay}


def accept_message(session, permission_id, payload, *, request_key, request_url,
                   expected_generation, expected_cursor_version, received_at, now):
    now, received_at = _clock(now), _clock(received_at)
    _, policy = require_permission(session, permission_id, now=now)
    if (received_at > now or received_at < _clock(policy.accepted_at) or request_url != policy.endpoint
            or not isinstance(request_key, str) or not 1 <= len(request_key) <= 100
            or any(ord(c) < 33 for c in request_key)
            or type(expected_generation) is not int or type(expected_cursor_version) is not int
            or expected_generation < 1 or expected_cursor_version < 0):
        _error("hazard_source_receipt_invalid", 422)
    selected = _selection(session, policy.source_key)
    if selected is None or selected.permission_id != permission_id or selected.generation != expected_generation:
        _error("hazard_source_selection_conflict")
    message = decode_cap(payload, received_at=received_at)
    if message.identity.sender != policy.sender:
        _error("hazard_source_sender_mismatch")
    replay = session.scalar(select(HazardSourceReceipt).where(HazardSourceReceipt.permission_id == permission_id,
        HazardSourceReceipt.generation == expected_generation, HazardSourceReceipt.request_key == request_key))
    if replay:
        if replay.request_hash != message.evidence_hash:
            _error("hazard_source_request_conflict")
        return _accepted(replay, True)
    if selected.cursor_version != expected_cursor_version:
        _error("hazard_source_cursor_conflict")
    receipt_age = (now - received_at).total_seconds()
    if receipt_age > policy.max_age_seconds or receipt_age >= policy.normalized_retention_seconds:
        _error("hazard_source_receipt_stale")
    if selected.last_received_at is not None and received_at < _utc(selected.last_received_at):
        _error("hazard_source_receipt_rollback")
    try:
        with _savepoint(session):
            purge_content(session, now=now, permission_id=permission_id)
            existing = session.scalar(select(HazardMessageEvidence).where(HazardMessageEvidence.permission_id == permission_id,
                HazardMessageEvidence.identifier == message.identity.identifier).execution_options(populate_existing=True))
            if existing and (existing.message_key != message.identity.key or existing.raw_hash != message.evidence_hash):
                _error("hazard_conflicting_identity")
            if existing and (existing.normalized_payload is None or _utc(existing.normalized_expires_at) <= now):
                _error("hazard_evidence_expired")
            state = _state(session, permission_id, policy.sender, now)
            next_state, change = reconcile_cap(state, message)
            if session.scalar(select(func.count()).select_from(HazardSourceReceipt).where(
                    HazardSourceReceipt.permission_id == permission_id)) >= MAX_RECEIPTS:
                _error("hazard_receipt_limit")
            if existing is None:
                if session.scalar(select(func.count()).select_from(HazardMessageEvidence).where(
                        HazardMessageEvidence.permission_id == permission_id)) >= MAX_EVIDENCE_ROWS:
                    _error("hazard_evidence_limit")
                raw_bytes = session.scalar(select(func.coalesce(func.sum(func.length(HazardMessageEvidence.raw_payload)), 0))
                    .where(HazardMessageEvidence.permission_id == permission_id))
                keep_raw = received_at + timedelta(seconds=policy.raw_retention_seconds) > now
                if keep_raw and raw_bytes + len(payload) > MAX_RAW_BYTES:
                    _error("hazard_raw_storage_limit")
                normalized = CODEC.dump_json(message)
                if len(normalized) + sum(entry.retained_bytes for entry in state.messages) > MAX_RETAINED_BYTES:
                    _error("hazard_history_byte_limit")
                classification = classify(message, policy)
                if message.message_type == "Cancel":
                    predecessor = next(e.message for e in state.messages if e.message.identity == message.references[0])
                    classification = classify(predecessor, policy)
                existing = HazardMessageEvidence(permission_id=permission_id, message_key=message.identity.key,
                    identifier=message.identity.identifier, development_key=change.development_id,
                    raw_hash=message.evidence_hash,
                    raw_payload=payload if keep_raw else None,
                    raw_expires_at=min(received_at + timedelta(seconds=policy.raw_retention_seconds), _clock(policy.valid_until)),
                    normalized_hash=_hash(normalized), normalized_payload=normalized,
                    normalized_expires_at=min(received_at + timedelta(seconds=policy.normalized_retention_seconds), _clock(policy.valid_until)),
                    first_received_at=received_at, last_seen_at=received_at, material_sequence=change.material_sequence,
                    kind=change.kind, material=change.material, classification=classification,
                    reference_keys=[r.key for r in message.references])
                session.add(existing)
                session.flush()
            else:
                existing.last_seen_at = received_at
            next_head = next(h for h in next_state.heads if h.development_id == change.development_id)
            if next_head.current_key == message.identity.key:
                head = session.get(HazardCurrentWarning, (permission_id, change.development_id), populate_existing=True)
                if head is None:
                    head = HazardCurrentWarning(permission_id=permission_id, development_key=change.development_id)
                    session.add(head)
                head.evidence_id, head.generation = existing.id, expected_generation
                head.material_sequence, head.state = next_head.material_sequence, next_head.state
            changed = session.execute(update(HazardSourceSelection).where(
                HazardSourceSelection.source_key == policy.source_key, HazardSourceSelection.permission_id == permission_id,
                HazardSourceSelection.generation == expected_generation, HazardSourceSelection.cursor_version == expected_cursor_version)
                .values(cursor_version=expected_cursor_version + 1, last_received_at=received_at)
                .execution_options(synchronize_session=False))
            if changed.rowcount != 1:
                _error("hazard_source_cursor_conflict")
            receipt = HazardSourceReceipt(permission_id=permission_id, evidence_id=existing.id, generation=expected_generation,
                cursor_version=expected_cursor_version + 1, request_key=request_key, request_hash=message.evidence_hash,
                received_at=received_at, change=json.loads(_encoded(asdict(change))))
            session.add(receipt)
            session.flush()
            return _accepted(receipt, False)
    except IntegrityError:
        _error("hazard_source_concurrent_change")


def read_message(session, permission_id, evidence_id, *, now, purpose="display", fresh=False):
    now = _clock(now)
    _, policy = require_permission(session, permission_id, now=now, purpose=purpose)
    row = session.scalar(select(HazardMessageEvidence).where(HazardMessageEvidence.id == evidence_id,
        HazardMessageEvidence.permission_id == permission_id).execution_options(populate_existing=True))
    if (row is None or row.normalized_payload is None or _utc(row.normalized_expires_at) <= now
            or _utc(row.first_received_at) > now or _utc(row.last_seen_at) > now):
        _error("hazard_evidence_unavailable")
    if fresh and (now - _utc(row.last_seen_at)).total_seconds() > policy.max_age_seconds:
        _error("hazard_evidence_stale")
    message = _restore(row)
    if fresh and message.infos and message.infos[0].expires is not None and message.infos[0].expires <= now:
        _error("hazard_warning_period_expired")
    return message


def read_current(session, source_key, *, now, purpose="matching", limit=50, after_key=None):
    now = _clock(now)
    if (type(limit) is not int or not 1 <= limit <= 100
            or after_key is not None and (not isinstance(after_key, str) or len(after_key) != 64
                                         or any(c not in "0123456789abcdef" for c in after_key))):
        _error("hazard_source_page_invalid", 422)
    snapshot = session.execute(select(HazardSourceSelection.permission_id, HazardSourceSelection.generation)
                              .where(HazardSourceSelection.source_key == source_key)).first()
    if snapshot is None:
        _error("hazard_source_unselected")
    # Every operation locks permission before selection, including reads. The
    # unlocked snapshot is checked again to avoid deadlocks with activation.
    _, policy = require_permission(session, snapshot.permission_id, now=now, purpose=purpose)
    selected = _selection(session, source_key)
    if selected is None or (selected.permission_id, selected.generation) != tuple(snapshot):
        _error("hazard_source_selection_conflict")
    if policy.source_key != source_key:
        _error("hazard_permission_invalid", 503)
    query = select(HazardCurrentWarning).where(HazardCurrentWarning.permission_id == selected.permission_id,
        HazardCurrentWarning.generation == selected.generation)
    if after_key is not None:
        query = query.where(HazardCurrentWarning.development_key > after_key)
    heads = list(session.scalars(query.order_by(HazardCurrentWarning.development_key).limit(limit + 1)
                                .execution_options(populate_existing=True)))
    items = []
    for head in heads[:limit]:
        try:
            message = read_message(session, selected.permission_id, head.evidence_id, now=now, purpose=purpose, fresh=True)
            items.append({"development_key": head.development_key, "evidence_id": head.evidence_id,
                          "material_sequence": head.material_sequence, "state": head.state, "message": message})
        except DomainError as exc:
            if exc.code not in {"hazard_evidence_unavailable", "hazard_evidence_stale", "hazard_warning_period_expired"}:
                raise
            items.append({"development_key": head.development_key, "evidence_id": head.evidence_id,
                          "state": "unavailable", "reason": exc.code})
    return {"permission_id": selected.permission_id, "generation": selected.generation,
            "cursor_version": selected.cursor_version, "items": items,
            "next_cursor": heads[limit - 1].development_key if len(heads) > limit else None,
            "coverage_verified": False}
