"""Atomic native IPI acquisition. Callers commit leases before performing HTTP."""

import re
import xml.etree.ElementTree as ET
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, select, update

from . import trademark_sources as source
from .ipi_models import IPIAlias, IPIIdentity, IPIPageEvidence, IPISeenIdentity, IPITokenCache, IPITraversal
from .ipi_protocol import IPIProtocolError, decode_response, initial_request, parse_xml
from .ipi_trademarks import decode_trademark
from .monitoring_subjects import _savepoint
from .trademark_source_models import TrademarkSourcePermission

ENDPOINT = "https://www.swissreg.ch/public/api/v1"
ORIGINS = {"national_ch", "international_designating_ch"}
LEASE_SECONDS = 120
PAGE_INTERVAL_SECONDS = 2
MAX_PAGES = 100_000
MAX_PARENT_BYTES = 512 * 1024**2
MAX_ALIASES = 4_000_000


def _scope(session, permission_id, now, *, generation=None, purpose="acquisition"):
    _, policy = source.require_permission(session, permission_id, now=now, purpose=purpose)
    if purpose == "acquisition":
        source.require_permission(session, permission_id, now=now)
        if policy.endpoint != ENDPOINT or set(policy.origins) != ORIGINS:
            source._error("ipi_source_scope_unavailable")
        if policy.raw_retention_seconds <= LEASE_SECONDS:
            source._error("ipi_checkpoint_retention_unavailable")
    selected = source._selection(session, policy.source_key)
    if not selected or selected.permission_id != permission_id or generation is not None and selected.generation != generation:
        source._error("trademark_source_selection_conflict")
    return policy, selected


def _scan(session, scan_id):
    row = session.scalar(select(IPITraversal).where(IPITraversal.id == scan_id)
        .with_for_update().execution_options(populate_existing=True))
    if row is None:
        source._error("ipi_traversal_unavailable")
    return row


def summary(row):
    return {"traversal_id": row.id, "state": row.state, "page_count": row.page_count,
        "received_count": row.next_offset, "unique_count": row.unique_count,
        "duplicate_count": row.duplicate_count, "last_reported_total": row.last_total,
        "totals_changed": row.totals_changed, "coverage_verified": False,
        "started_at": source._utc(row.started_at).isoformat(),
        "completed_at": source._utc(row.completed_at).isoformat() if row.completed_at else None,
        "next_attempt_at": source._utc(row.next_attempt_at).isoformat(), "last_error": row.last_error}


def _request(raw, scan_id, page_index):
    root = parse_xml(raw)
    request_id = f"{scan_id}-{page_index}"
    root.set("uuid", request_id)
    return request_id, ET.tostring(root, encoding="utf-8", xml_declaration=True)


def claim(session, permission_id, *, now):
    """One durable source-wide request lease, independent of private monitors."""
    now = source._clock(now)
    with _savepoint(session):
        policy, selected = _scope(session, permission_id, now)
        row = session.scalar(select(IPITraversal).where(IPITraversal.source_key == policy.source_key)
            .order_by(IPITraversal.started_at.desc(), IPITraversal.id.desc()).limit(1)
            .with_for_update().execution_options(populate_existing=True))
        if row is not None and row.lease_expires_at and source._utc(row.lease_expires_at) > now:
            return {"state": "busy"}
        # A new local permission is not a new publisher account or quota window.
        if row is not None and row.last_error and source._utc(row.next_attempt_at) > now:
            return {"state": "waiting", "next_attempt_at": source._utc(row.next_attempt_at).isoformat()}
        if row is not None and (row.permission_id != permission_id or row.generation != selected.generation):
            if row.state == "running":
                row.state, row.next_request, row.lease_token = "abandoned", None, None
                row.last_error = "trademark_source_selection_conflict"
            row = None
        if row is not None and row.state == "running":
            if row.lease_expires_at and source._utc(row.lease_expires_at) > now:
                return {"state": "busy"}
            if source._utc(row.next_attempt_at) > now:
                return {"state": "waiting", "next_attempt_at": source._utc(row.next_attempt_at).isoformat()}
            if row.next_request is None or source._utc(row.request_expires_at) <= now:
                row.state, row.next_request = "abandoned", None
                row.last_error = "ipi_continuation_expired"
                row.next_attempt_at = now + timedelta(seconds=policy.min_poll_seconds)
                return summary(row)
        if row is not None and row.state != "running":
            due = max(source._utc(row.next_attempt_at),
                source._utc(row.completed_at or row.started_at) + timedelta(seconds=policy.min_poll_seconds))
            if due > now:
                return {"state": "waiting", "next_attempt_at": due.isoformat()}
            row = None
        if row is None:
            raw = initial_request()
            row = IPITraversal(source_key=policy.source_key, permission_id=permission_id,
                generation=selected.generation, started_at=now, next_request=raw,
                next_request_hash=source._hash(raw),
                request_expires_at=min(source._clock(policy.valid_until), now + timedelta(seconds=policy.raw_retention_seconds)),
                next_attempt_at=now)
            session.add(row)
            session.flush()
        if source._hash(row.next_request) != row.next_request_hash:
            source._error("ipi_continuation_integrity")
        row.lease_token, row.lease_expires_at = str(uuid4()), now + timedelta(seconds=LEASE_SECONDS)
        row.next_attempt_at = now + timedelta(seconds=PAGE_INTERVAL_SECONDS)
        request_id, raw = _request(row.next_request, row.id, row.page_count)
        session.flush()
        return {"state": "claimed", "traversal_id": row.id, "permission_id": permission_id,
            "generation": selected.generation, "page_index": row.page_count,
            "request_hash": row.next_request_hash, "request_uuid": request_id, "request": raw,
            "lease_token": row.lease_token}


def _leased(session, ticket, now, *, allow_expired=False):
    policy, selected = _scope(session, ticket["permission_id"], now, generation=ticket["generation"])
    row = _scan(session, ticket["traversal_id"])
    if (row.permission_id != ticket["permission_id"] or row.generation != ticket["generation"]
            or row.state != "running" or row.lease_token != ticket["lease_token"]
            or row.lease_expires_at is None or not allow_expired and source._utc(row.lease_expires_at) <= now
            or row.page_count != ticket["page_index"] or row.next_request_hash != ticket["request_hash"]
            or row.next_request is None or source._hash(row.next_request) != row.next_request_hash
            or not allow_expired and source._utc(row.request_expires_at) <= now):
        source._error("ipi_request_lease_lost")
    expected_uuid, expected_body = _request(row.next_request, row.id, row.page_count)
    if ticket["request_uuid"] != expected_uuid or ticket["request"] != expected_body:
        source._error("ipi_request_integrity")
    return policy, selected, row


def validate_ticket(session, ticket, *, now):
    _leased(session, ticket, source._clock(now))


def _identity(session, source_key, native):
    aliases = {source._hash(alias.encode()): alias for alias in native.aliases}
    known = list(session.scalars(select(IPIAlias).where(IPIAlias.source_key == source_key,
        IPIAlias.alias_hash.in_(aliases))))
    identities = {row.canonical_hash for row in known}
    if len(identities) > 1:
        source._error("ipi_identity_conflict")
    if identities:
        canonical, = identities
        if canonical not in aliases:
            source._error("ipi_canonical_alias_missing")
    else:
        alias = sorted(native.aliases, key=lambda value: ("/application/" not in value, value))[0]
        canonical = source._hash(alias.encode())
    facts = native.facts(official_id=aliases[canonical])
    identity = session.get(IPIIdentity, (source_key, canonical))
    if identity is not None and identity.origin != facts.origin:
        source._error("ipi_identity_conflict")
    if identity is None:
        session.add(IPIIdentity(source_key=source_key, canonical_hash=canonical, origin=facts.origin))
        session.flush()
    known_hashes = {row.alias_hash for row in known}
    missing = set(aliases) - known_hashes
    if missing:
        count = session.scalar(select(func.count()).select_from(IPIAlias).where(IPIAlias.source_key == source_key))
        if count + len(missing) > MAX_ALIASES:
            source._error("ipi_identity_capacity")
        session.add_all(IPIAlias(source_key=source_key, alias_hash=value, canonical_hash=canonical) for value in missing)
        session.flush()
    return canonical, facts


def admit(session, ticket, *, status, headers, payload, received_at, now):
    """All items, identities, journal receipts and next-page evidence commit together."""
    now, received_at = source._clock(now), source._clock(received_at)
    with _savepoint(session):
        policy, selected = _scope(session, ticket["permission_id"], now, generation=ticket["generation"])
        row = _scan(session, ticket["traversal_id"])
        if row.permission_id != ticket["permission_id"] or row.generation != ticket["generation"]:
            source._error("ipi_request_lease_lost")
        prior = session.get(IPIPageEvidence, (row.id, ticket["page_index"]))
        if prior:
            if prior.request_hash != ticket["request_hash"] or prior.response_hash != source._hash(payload):
                source._error("ipi_page_replay_conflict")
            return {"state": "accepted", "replayed": True, "page_index": prior.page_index,
                "journal_cursor": prior.journal_cursor, "coverage_verified": False}
        policy, selected, row = _leased(session, ticket, now)
        page = decode_response(status, headers, payload, now=now, expected_request_uuid=ticket["request_uuid"])
        if page.offset != row.next_offset or page.count == 0 and page.next_request:
            source._error("ipi_page_continuity_invalid")
        if (received_at > now or received_at < source._utc(row.started_at)
                or now - received_at > timedelta(seconds=policy.max_age_seconds)):
            source._error("trademark_source_time_invalid")
        if row.page_count >= MAX_PAGES:
            source._error("ipi_traversal_capacity")
        next_hash = source._hash(page.next_request) if page.next_request else None
        if next_hash and (next_hash == ticket["request_hash"] or session.scalar(select(IPIPageEvidence.page_index).where(
                IPIPageEvidence.traversal_id == row.id, IPIPageEvidence.request_hash == next_hash)) is not None):
            source._error("ipi_continuation_cycle")
        # Expired parent bytes are purged before enforcing the separate parent budget.
        session.execute(update(IPIPageEvidence).where(IPIPageEvidence.raw_expires_at <= now).values(raw_payload=None))
        retained = session.scalar(select(func.coalesce(func.sum(func.length(IPIPageEvidence.raw_payload)), 0))
            .join(IPITraversal, IPITraversal.id == IPIPageEvidence.traversal_id)
            .where(IPITraversal.permission_id == ticket["permission_id"]))
        if retained + len(payload) > MAX_PARENT_BYTES:
            source._error("ipi_parent_evidence_capacity")
        cursor, unique, duplicates = selected.cursor_version, 0, 0
        for index, item in enumerate(page.items):
            native = decode_trademark(item.xml, source_url="https://www.swissreg.ch/", source_document_sha256=page.xml_sha256)
            canonical, facts = _identity(session, policy.source_key, native)
            seen = session.get(IPISeenIdentity, (row.id, canonical))
            if seen is None:
                session.add(IPISeenIdentity(traversal_id=row.id, canonical_hash=canonical))
                unique += 1
            else:
                duplicates += 1
            source.accept_record(session, ticket["permission_id"], native.raw_xml, facts,
                request_key=f"{row.id}-{row.page_count}-{index}", request_url=policy.endpoint,
                expected_generation=row.generation, expected_cursor_version=cursor, received_at=received_at, now=now)
            cursor += 1
        expiry = min(source._clock(policy.valid_until), received_at + timedelta(seconds=policy.raw_retention_seconds))
        session.add(IPIPageEvidence(traversal_id=row.id, page_index=row.page_count,
            request_hash=ticket["request_hash"], response_hash=page.response_sha256, xml_hash=page.xml_sha256,
            raw_payload=payload if expiry > now else None, raw_expires_at=expiry, received_at=received_at,
            item_offset=page.offset, item_count=page.count, total_count=page.total, journal_cursor=cursor))
        row.totals_changed = row.totals_changed or row.last_total is not None and row.last_total != page.total
        row.last_total, row.next_offset = page.total, page.offset + page.count
        row.unique_count, row.duplicate_count = row.unique_count + unique, row.duplicate_count + duplicates
        row.page_count += 1
        row.next_request, row.next_request_hash, row.request_expires_at = page.next_request, next_hash, expiry
        row.lease_token, row.lease_expires_at, row.last_error = None, None, None
        if page.next_request is None:
            row.state, row.completed_at = "completed", now
            row.next_attempt_at = now + timedelta(seconds=policy.min_poll_seconds)
        else:
            row.next_attempt_at = now + timedelta(seconds=PAGE_INTERVAL_SECONDS)
        session.flush()
        return {"state": "accepted", "replayed": False, "page_index": row.page_count - 1,
            "journal_cursor": cursor, "traversal": summary(row), "coverage_verified": False}


def fail(session, ticket, *, code, now, retry_after_seconds=None):
    """Store only a bounded error code, never transport bodies or credentials."""
    now = source._clock(now)
    with _savepoint(session):
        _, _, row = _leased(session, ticket, now, allow_expired=True)
        if not isinstance(code, str) or not re.fullmatch(r"[a-z0-9_]{1,100}", code):
            code = "ipi_collection_failed"
        delay = max(900, retry_after_seconds or 0)
        if type(delay) is not int or not 0 <= delay <= 9_999_999_999:
            raise IPIProtocolError("ipi_retry_delay_invalid")
        row.last_error, row.next_attempt_at = code, now + timedelta(seconds=delay)
        row.lease_token, row.lease_expires_at = None, None
        session.flush()
        return summary(row)


def read_status(session, permission_id, *, now):
    now = source._clock(now)
    policy, selected = _scope(session, permission_id, now, purpose="display")
    row = session.scalar(select(IPITraversal).where(IPITraversal.permission_id == permission_id,
        IPITraversal.source_key == policy.source_key, IPITraversal.generation == selected.generation)
        .order_by(IPITraversal.started_at.desc(), IPITraversal.id.desc()).limit(1))
    return summary(row) if row else {"state": "not_started", "coverage_verified": False}


def cleanup(session, *, now):
    """Erase licensed response/checkpoint bytes; retain minimal identity/count hashes."""
    now = source._clock(now)
    denied = select(TrademarkSourcePermission.id).where(
        (TrademarkSourcePermission.revoked_at.is_not(None)) | (TrademarkSourcePermission.valid_until <= now))
    scans = select(IPITraversal.id).where(IPITraversal.permission_id.in_(denied))
    pages = session.execute(update(IPIPageEvidence).where(
        IPIPageEvidence.raw_payload.is_not(None),
        (IPIPageEvidence.raw_expires_at <= now) | IPIPageEvidence.traversal_id.in_(scans)).values(raw_payload=None))
    checkpoints = session.execute(update(IPITraversal).where(
        IPITraversal.next_request.is_not(None),
        (IPITraversal.request_expires_at <= now) | IPITraversal.permission_id.in_(denied)).values(next_request=None))
    tokens = session.execute(update(IPITokenCache).where(IPITokenCache.expires_at <= now,
        IPITokenCache.encrypted_payload.is_not(None),
        (IPITokenCache.lease_expires_at.is_(None)) | (IPITokenCache.lease_expires_at <= now)).values(encrypted_payload=None))
    return {"pages": pages.rowcount, "checkpoints": checkpoints.rowcount, "tokens": tokens.rowcount}
