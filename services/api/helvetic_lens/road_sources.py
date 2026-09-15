"""Permission-bound internal Road Watch storage. Callers own commit/rollback.

There is no permission-write HTTP API and no public raw-data export. Recording a
policy attests an operator's completed source review; account registration is not
that review. Network acquisition must finish before entering this repository.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError
from sqlalchemy import delete, func, or_, select, update

from .config import DomainError
from .monitoring_subjects import _savepoint
from .road_feed import RoadSituation, decode_road_feed
from .road_models import (
    RoadCurrentSituation,
    RoadSituationVersion,
    RoadSourceChange,
    RoadSourceEvidence,
    RoadSourceHead,
    RoadSourcePermission,
)
from .road_reconciliation import RoadSourceState, StoredRoadSituation, reconcile_road_snapshot

SOURCE = "fedro_traffic_situations"
MAX_STORED_BYTES = 2 * 1024**3
MAX_STATE_BYTES = 64 * 1024**2
MAX_SITUATION_BYTES = 2 * 1024**2
MAX_EVIDENCE_ROWS = 50_000
MAX_VERSION_ROWS = 100_000
MAX_CHANGE_ROWS = 100_000
SITUATION_CODEC = TypeAdapter(RoadSituation)
DerivedField = Literal["event_kind", "validity", "location", "delay", "lanes", "public_text", "source_reference"]


class RoadPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    reference: str = Field(min_length=1, max_length=500)
    attribution: str = Field(min_length=1, max_length=1000)
    supplier: tuple[str, str]
    accepted_at: datetime
    valid_until: datetime
    max_age_seconds: int = Field(ge=1, le=3600)
    raw_retention_seconds: int = Field(ge=0, le=7 * 86400)
    derived_retention_seconds: int = Field(ge=1, le=366 * 86400)
    allowed_fields: tuple[DerivedField, ...]
    notifications_allowed: bool


@dataclass(frozen=True)
class RoadAcceptance:
    evidence_id: str
    generation: int
    replay: bool
    change_ids: tuple[str, ...]


def _error(code, *, status=409):
    raise DomainError("Road source evidence or permission is unavailable.", status, code) from None


def _utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _clock(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        _error("road_clock_invalid", status=422)
    return value.astimezone(UTC)


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def record_permission(session, *, policy: RoadPolicy) -> str:
    """Internal reviewed configuration, never a source-account registration action."""
    accepted, valid = _clock(policy.accepted_at), _clock(policy.valid_until)
    if (valid <= accepted or policy.raw_retention_seconds > policy.derived_retention_seconds
            or not policy.reference.strip() or not policy.attribution.strip()
            or len(set(policy.allowed_fields)) != len(policy.allowed_fields)
            or any(not v.strip() or len(v) > 256 for v in policy.supplier)):
        _error("road_policy_invalid", status=422)
    payload = policy.model_dump(mode="json")
    row = RoadSourcePermission(policy=payload, policy_hash=_hash(_encoded(payload)), accepted_at=accepted,
                               valid_until=valid)
    session.add(row)
    session.flush()
    return row.id


def require_permission(session, permission_id, *, now, fields=(), notification=False):
    now = _clock(now)
    row = session.scalar(select(RoadSourcePermission).where(RoadSourcePermission.id == permission_id)
                         .with_for_update().execution_options(populate_existing=True))
    if row is None or row.revoked_at is not None or not _utc(row.accepted_at) <= now < _utc(row.valid_until):
        _error("road_permission_unavailable")
    try:
        encoded = _encoded(row.policy)
        policy = RoadPolicy.model_validate_json(encoded, strict=True)
        if (_hash(encoded) != row.policy_hash or _clock(policy.accepted_at) != _utc(row.accepted_at)
                or _clock(policy.valid_until) != _utc(row.valid_until)):
            _error("road_permission_invalid", status=503)
    except (ValueError, TypeError):
        _error("road_permission_invalid", status=503)
    if not set(fields) <= set(policy.allowed_fields) or (notification and not policy.notifications_allowed):
        _error("road_derived_use_denied", status=403)
    return row, policy


def _head(session):
    return session.scalar(select(RoadSourceHead).where(RoadSourceHead.source == SOURCE)
                          .with_for_update().execution_options(populate_existing=True))


def activate_permission(session, permission_id, *, expected_generation, now):
    """Explicit operator selection. Renewal starts a new full baseline, not a data transfer."""
    require_permission(session, permission_id, now=now)
    with _savepoint(session):
        head = _head(session)
        if (0 if head is None else head.generation) != expected_generation:
            _error("road_generation_conflict")
        if head and head.permission_id == permission_id:
            return head.generation
        if head is None:
            head = RoadSourceHead(source=SOURCE, permission_id=permission_id, generation=1)
            session.add(head)
        else:
            head.permission_id = permission_id
            head.generation += 1
            head.published_at = head.received_at = head.last_full_at = head.snapshot_hash = None
        # Selecting an earlier, still-valid permission also needs a new baseline.
        # Remove only its mutable current index, preserving immutable history.
        session.execute(delete(RoadCurrentSituation).where(RoadCurrentSituation.permission_id == permission_id))
        session.flush()
        return head.generation


def revoke_permission(session, permission_id, *, now):
    now = _clock(now)
    row = session.scalar(select(RoadSourcePermission).where(RoadSourcePermission.id == permission_id)
                         .with_for_update().execution_options(populate_existing=True))
    if row is None:
        _error("road_permission_unavailable")
    if row.revoked_at is None:
        row.revoked_at = now
    session.flush()


def _encode_situation(situation):
    from .road_recurrence import canonical_periods

    encoded = _encoded(canonical_periods(SITUATION_CODEC.dump_python(situation, mode="json")))
    if len(encoded) > MAX_SITUATION_BYTES:
        _error("road_situation_storage_limit")
    return encoded


def _read_version(row, *, now):
    if row.content is None or now >= _utc(row.expires_at):
        _error("road_evidence_expired")
    if len(row.content) != row.content_size or len(row.content) > MAX_SITUATION_BYTES or _hash(row.content) != row.content_hash:
        _error("road_evidence_invalid", status=503)
    try:
        value = SITUATION_CODEC.validate_json(row.content, strict=True)
        if (_encode_situation(value) != row.content or value.source_id != row.source_id
                or value.semantic_hash != row.semantic_hash or value.version_at != _utc(row.version_at)):
            _error("road_evidence_invalid", status=503)
    except (ValidationError, ValueError, TypeError):
        _error("road_evidence_invalid", status=503)
    return value


def _load_state(session, head, policy, *, now):
    if head.published_at is None:
        return None, {}
    evidence = session.scalar(select(RoadSourceEvidence).where(RoadSourceEvidence.permission_id == head.permission_id,
                              RoadSourceEvidence.generation == head.generation))
    if (evidence is None or evidence.content_hash != head.snapshot_hash
            or _utc(evidence.published_at) != _utc(head.published_at)
            or _utc(evidence.received_at) != _utc(head.received_at) or now >= _utc(evidence.expires_at)):
        _error("road_state_evidence_invalid", status=503)
    query = select(RoadCurrentSituation, RoadSituationVersion).join(RoadSituationVersion,
        (RoadCurrentSituation.version_id == RoadSituationVersion.id)
        & (RoadCurrentSituation.permission_id == RoadSituationVersion.permission_id)
        & (RoadCurrentSituation.source_id == RoadSituationVersion.source_id)).where(
            RoadCurrentSituation.permission_id == head.permission_id).order_by(RoadCurrentSituation.source_id)
    # Count/size before fetching blobs. This also catches a damaged current binding
    # by comparing the number of join rows to the current-index count below.
    bound = select(RoadSituationVersion.id, RoadSituationVersion.content_size).join(RoadCurrentSituation,
        RoadCurrentSituation.version_id == RoadSituationVersion.id).where(
            RoadCurrentSituation.permission_id == head.permission_id).subquery()
    total, size = session.execute(select(func.count(), func.coalesce(func.sum(bound.c.content_size), 0))
                                  .select_from(bound)).one()
    count = session.scalar(select(func.count()).select_from(RoadCurrentSituation).where(
        RoadCurrentSituation.permission_id == head.permission_id))
    if total != count or count > 20_000 or size > MAX_STATE_BYTES:
        _error("road_state_storage_limit")
    entries, rows = [], {}
    for current, version in session.execute(query).all():
        situation = _read_version(version, now=now)
        if _utc(current.seen_at) > _utc(head.published_at):
            _error("road_state_clock_invalid", status=503)
        entries.append(StoredRoadSituation(situation, _utc(current.seen_at), current.present))
        rows[current.source_id] = (current, version)
    if len(entries) != count:
        _error("road_state_binding_invalid", status=503)
    return RoadSourceState(policy.supplier, _utc(head.published_at), head.snapshot_hash, tuple(entries)), rows


def read_state(session, permission_id, *, now, require_fresh=True):
    """Internal normalized state; user projections must separately request allowed fields."""
    now = _clock(now)
    _, policy = require_permission(session, permission_id, now=now)
    head = _head(session)
    if head is None or head.permission_id != permission_id or head.published_at is None:
        _error("road_full_baseline_required")
    if now < _utc(head.published_at) or now < _utc(head.received_at):
        _error("road_source_future")
    if require_fresh and (now - _utc(head.published_at)).total_seconds() > policy.max_age_seconds:
        _error("road_source_stale")
    state, _ = _load_state(session, head, policy, now=now)
    return state


def read_version(session, permission_id, version_id, *, now, fields=(), notification=False):
    """Internal historical evidence; a new permission cannot revive old versions."""
    now = _clock(now)
    require_permission(session, permission_id, now=now, fields=fields, notification=notification)
    row = session.scalar(select(RoadSituationVersion).where(RoadSituationVersion.id == version_id,
                         RoadSituationVersion.permission_id == permission_id).execution_options(populate_existing=True))
    if row is None:
        _error("road_version_unavailable", status=404)
    return _read_version(row, now=now)


def _capacity(session, *, raw_bytes, version_bytes, versions, changes):
    sizes = 0
    for model, extra, limit in ((RoadSourceEvidence, 1, MAX_EVIDENCE_ROWS),
                                (RoadSituationVersion, versions, MAX_VERSION_ROWS),
                                (RoadSourceChange, changes, MAX_CHANGE_ROWS)):
        if session.scalar(select(func.count()).select_from(model)) + extra > limit:
            _error("road_source_storage_limit")
        if model is not RoadSourceChange:
            sizes += session.scalar(select(func.coalesce(func.sum(func.length(model.content)), 0)))
    if sizes + raw_bytes + version_bytes > MAX_STORED_BYTES:
        _error("road_source_storage_limit")


def accept_snapshot(session, permission_id, payload, *, request_id, expected_generation, mode, continuous,
                    received_at, now=None):
    """Publish a bounded response, immutable versions and changes in one savepoint."""
    received = _clock(received_at)
    now = _clock(datetime.now(UTC) if now is None else now)
    if received > now:
        _error("road_receipt_future")
    if type(expected_generation) is not int or expected_generation < 1 or type(continuous) is not bool:
        _error("road_request_context_invalid", status=422)
    try:
        if str(UUID(request_id)) != request_id:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        _error("road_request_id_invalid", status=422)
    _, policy = require_permission(session, permission_id, now=now)
    snapshot = decode_road_feed(payload, received_at=received)
    if snapshot.supplier != policy.supplier:
        _error("road_supplier_unapproved")
    if snapshot.published_at > now or (now - snapshot.published_at).total_seconds() > policy.max_age_seconds:
        _error("road_source_not_current")
    with _savepoint(session):
        head = _head(session)
        if head is None or head.permission_id != permission_id:
            _error("road_permission_not_selected")
        replay = session.scalar(select(RoadSourceEvidence).where(RoadSourceEvidence.permission_id == permission_id,
                                RoadSourceEvidence.request_id == request_id))
        if replay:
            if (replay.content_hash != snapshot.sha256 or replay.mode != mode or replay.continuous != continuous
                    or replay.previous_generation != expected_generation or _utc(replay.received_at) != received):
                _error("road_request_conflict")
            ids = tuple(session.scalars(select(RoadSourceChange.id).where(
                RoadSourceChange.evidence_id == replay.id).order_by(RoadSourceChange.source_id)))
            return RoadAcceptance(replay.id, replay.generation, True, ids)
        if head.generation != expected_generation:
            _error("road_generation_conflict")
        previous, current_rows = _load_state(session, head, policy, now=now)
        replacement, changes = reconcile_road_snapshot(previous, snapshot, mode=mode, continuous=continuous)
        encoded = {entry.situation.source_id: _encode_situation(entry.situation) for entry in replacement.situations}
        if sum(map(len, encoded.values())) > MAX_STATE_BYTES:
            _error("road_state_storage_limit")
        observed = {situation.source_id for situation in snapshot.situations}
        changed = {key: value for key, value in encoded.items()
                   if key not in current_rows or current_rows[key][1].content_hash != _hash(value)
                   or (key in observed and snapshot.published_at > _utc(current_rows[key][0].seen_at))}
        developments = tuple(change for change in changes if change.kind != "source_refreshed")
        raw = payload if received + timedelta(seconds=policy.raw_retention_seconds) > now else None
        _capacity(session, raw_bytes=len(raw or b""), version_bytes=sum(map(len, changed.values())),
                  versions=len(changed), changes=len(developments))
        expiry = min(received + timedelta(seconds=policy.derived_retention_seconds), policy.valid_until)
        if expiry <= now:
            _error("road_evidence_expired")
        evidence = RoadSourceEvidence(permission_id=permission_id, request_id=request_id,
            previous_generation=head.generation, generation=head.generation + 1, mode=mode, continuous=continuous,
            published_at=snapshot.published_at, received_at=received, content_hash=snapshot.sha256,
            content=raw, content_size=len(payload), raw_expires_at=min(
                received + timedelta(seconds=policy.raw_retention_seconds), expiry), expires_at=expiry)
        session.add(evidence)
        session.flush()
        versions = {}
        for entry in replacement.situations:
            value, key = entry.situation, entry.situation.source_id
            pair = current_rows.get(key)
            if key in changed:
                version = RoadSituationVersion(permission_id=permission_id, source_id=key, evidence_id=evidence.id,
                    semantic_hash=value.semantic_hash, content_hash=_hash(encoded[key]), content=encoded[key],
                    content_size=len(encoded[key]), version_at=value.version_at, expires_at=expiry)
                session.add(version)
                session.flush()
            else:
                version = pair[1]
            versions[key] = version
            if pair:
                current = pair[0]
                current.version_id, current.seen_at, current.present = version.id, entry.seen_at, entry.present
            else:
                session.add(RoadCurrentSituation(permission_id=permission_id, source_id=key, version_id=version.id,
                                                seen_at=entry.seen_at, present=entry.present))
        ids = []
        for change in developments:
            version = versions[change.source_id]
            row = RoadSourceChange(permission_id=permission_id, generation=evidence.generation,
                source_id=change.source_id, development_id=change.development_id, evidence_id=evidence.id,
                version_id=version.id, kind=change.kind, previous_hash=change.previous_hash,
                current_hash=change.current_hash, expires_at=min(expiry, _utc(version.expires_at)))
            session.add(row)
            session.flush()
            ids.append(row.id)
        head.generation = evidence.generation
        head.published_at, head.received_at, head.snapshot_hash = snapshot.published_at, received, snapshot.sha256
        if mode == "full":
            head.last_full_at = received
        session.flush()
        return RoadAcceptance(evidence.id, evidence.generation, False, tuple(ids))


def purge_expired(session, *, now):
    """Internal retention job; purge denied bytes without needing a usable grant.

    Expired current evidence invalidates the complete baseline and increments its
    generation, preventing an in-flight writer from restoring purged data.
    """
    now = _clock(now)
    # Match the writer's permission -> head lock order, including renewal/revoke.
    permissions = session.scalars(select(RoadSourcePermission).order_by(RoadSourcePermission.id)
                                 .with_for_update().execution_options(populate_existing=True)).all()
    denied = [row.id for row in permissions if row.revoked_at is not None or _utc(row.valid_until) <= now]
    with _savepoint(session):
        head = _head(session)
        expired_versions = select(RoadSituationVersion.id).where(or_(RoadSituationVersion.expires_at <= now,
                                                                   RoadSituationVersion.permission_id.in_(denied)))
        affected = set(session.scalars(select(RoadCurrentSituation.permission_id).where(
            RoadCurrentSituation.version_id.in_(expired_versions))))
        latest = None if head is None else session.scalar(select(RoadSourceEvidence).where(
            RoadSourceEvidence.permission_id == head.permission_id, RoadSourceEvidence.generation == head.generation))
        if head and (head.permission_id in affected or (head.published_at is not None and (
                head.permission_id in denied or (latest is not None and _utc(latest.expires_at) <= now)))):
            head.generation += 1
            head.published_at = head.received_at = head.last_full_at = head.snapshot_hash = None
            session.execute(delete(RoadCurrentSituation).where(RoadCurrentSituation.permission_id == head.permission_id))
        session.execute(delete(RoadCurrentSituation).where(RoadCurrentSituation.version_id.in_(expired_versions)))
        session.execute(delete(RoadSourceChange).where(or_(RoadSourceChange.expires_at <= now,
            RoadSourceChange.permission_id.in_(denied))).execution_options(synchronize_session="fetch"))
        session.execute(delete(RoadSituationVersion).where(RoadSituationVersion.id.in_(expired_versions)))
        session.execute(update(RoadSourceEvidence).where(or_(RoadSourceEvidence.raw_expires_at <= now,
            RoadSourceEvidence.permission_id.in_(denied))).values(content=None)
            .execution_options(synchronize_session="fetch"))
        session.execute(delete(RoadSourceEvidence).where(or_(RoadSourceEvidence.expires_at <= now,
            RoadSourceEvidence.permission_id.in_(denied))).execution_options(synchronize_session="fetch"))
        session.flush()
