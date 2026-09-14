"""Explicit private exports; only references and a digest persist, never licensed documents."""

import hashlib
import hmac
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import delete, func, select

from . import trademark_sources as sources
from .monitoring_subjects import _savepoint
from .trademark_export_document import render
from .trademark_history import event_detail
from .trademark_repository import _fail, _version
from .trademark_source_models import TrademarkRegisterRevision
from .trademark_sources import _clock, _utc
from .trademark_workflow import candidate_for, current
from .trademark_workflow_models import TrademarkCandidateEvent, TrademarkExportPreparation

MAX_PREPARATIONS = 20
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
LOCALES = {"de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"}


def _source(session, candidate, revision_id, *, now):
    revision = session.get(TrademarkRegisterRevision, revision_id)
    if revision is None or revision.record_key != candidate.record_key:
        _fail("trademark_export_evidence_invalid", 503)
    _, policy = sources.require_permission(session, revision.permission_id, now=now, purpose="export")
    sources.require_permission(session, revision.permission_id, now=now, purpose="display")
    facts = sources.read_revision(session, revision.permission_id, revision.id, now=now, purpose="matching")
    return {"facts": facts.model_dump(mode="json"), "attribution": policy.attribution,
        "source_revision": revision.id, "received_at": _utc(revision.received_at).isoformat()}


def document(session, monitor, candidate, preparation, *, now):
    # Current() acquires calibration locks before source locks, as at review.
    facts, assessment, _, _, deadline = current(session, monitor, candidate, now=now, with_deadline=True)
    if candidate.version != preparation.candidate_version or candidate.source_revision_id != preparation.source_revision_id:
        _fail("trademark_export_changed")
    source = _source(session, candidate, candidate.source_revision_id, now=now)
    change = None
    if preparation.event_id:
        event = session.scalar(select(TrademarkCandidateEvent).where(TrademarkCandidateEvent.id == preparation.event_id,
            TrademarkCandidateEvent.candidate_id == candidate.id, TrademarkCandidateEvent.organization_id == monitor.organization_id))
        if event is None:
            _fail("trademark_event_not_found", 404)
        after = _source(session, candidate, event.source_revision_id, now=now)
        before = _source(session, candidate, event.previous_revision_id, now=now) if event.previous_revision_id else None
        historical = event_detail(session, monitor.owner_user_id, monitor.id, candidate.id, event.id, now=now)
        change = {"id": event.id, "sequence": event.sequence, "detected_at": historical["detected_at"],
            "profile_revision": event.profile_revision, "change_codes": event.change_codes,
            "after": after, "before": before, "assessment": historical["assessment"],
            "newer_available": historical["newer_available"], "deadline_context": historical.get("deadline_context")}
    brand = next(b for b in monitor.configuration["brands"] if b["key"] == candidate.brand_key)
    packet = {"schema": "helvetic-lens-trademark-evidence-v1", "prepared_at": _utc(preparation.created_at).isoformat(),
        "monitor_id": monitor.id, "candidate_id": candidate.id, "profile_revision": monitor.revision,
        "portfolio_name": monitor.configuration["name"], "brand": brand, "source": source, "assessment": assessment,
        "candidate_sequence": candidate.sequence, "decision": candidate.decision, "needs_review": candidate.sequence > candidate.reviewed_sequence,
        "selected_change": change, "evaluation_hash": candidate.evaluation_hash,
        "deadline_context": deadline,
        "coverage_verified": False, "legal_conflict_confirmed": False}
    content = render(packet, preparation.locale)
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_DOCUMENT_BYTES:
        _fail("trademark_export_too_large", 413)
    return content, hashlib.sha256(encoded).hexdigest()


def _response(preparation, content):
    return {"id": preparation.id, "document": content, "content_sha256": preparation.content_hash,
        "filename": f"trademark-evidence-{preparation.id}.html", "media_type": "text/html;charset=utf-8",
        "expires_at": _utc(preparation.expires_at).isoformat(), "verification_required": True}


def prepare(session, user_id, monitor_id, candidate_id, *, expected_version, expected_evaluation_hash, request_key,
            event_id=None, locale="en-CH", now):
    now = _clock(now)
    if locale not in LOCALES or not isinstance(request_key, str) or not 1 <= len(request_key) <= 36:
        _fail("trademark_export_invalid", 422)
    with _savepoint(session):
        monitor, candidate = candidate_for(session, user_id, monitor_id, candidate_id, write=True)
        _version(expected_version)
        if candidate.version != expected_version or candidate.evaluation_hash != expected_evaluation_hash:
            _fail("trademark_version_conflict")
        existing = session.scalar(select(TrademarkExportPreparation).where(TrademarkExportPreparation.candidate_id == candidate.id,
            TrademarkExportPreparation.request_key == request_key))
        if existing:
            if (existing.candidate_version != expected_version or existing.event_id != event_id or existing.locale != locale):
                _fail("trademark_export_request_conflict")
            return read(session, user_id, monitor_id, candidate_id, existing.id, now=now)
        session.execute(delete(TrademarkExportPreparation).where(TrademarkExportPreparation.candidate_id == candidate.id,
            TrademarkExportPreparation.expires_at <= now))
        if session.scalar(select(func.count()).select_from(TrademarkExportPreparation).where(
                TrademarkExportPreparation.candidate_id == candidate.id)) >= MAX_PREPARATIONS:
            _fail("trademark_export_capacity")
        row = TrademarkExportPreparation(id=str(uuid4()), organization_id=monitor.organization_id, candidate_id=candidate.id,
            request_key=request_key, candidate_version=candidate.version, source_revision_id=candidate.source_revision_id,
            event_id=event_id, locale=locale, created_at=now, expires_at=now + timedelta(minutes=15))
        content, row.content_hash = document(session, monitor, candidate, row, now=now)
        session.add(row)
        session.flush()
        return _response(row, content)


def read(session, user_id, monitor_id, candidate_id, preparation_id, *, now, download_hash=None):
    now = _clock(now)
    # The parent lock serializes source projections, review and download validation.
    monitor, candidate = candidate_for(session, user_id, monitor_id, candidate_id, write=True)
    preparation = session.scalar(select(TrademarkExportPreparation).where(TrademarkExportPreparation.id == preparation_id,
        TrademarkExportPreparation.candidate_id == candidate.id, TrademarkExportPreparation.organization_id == monitor.organization_id)
        .execution_options(populate_existing=True))
    if preparation is None:
        _fail("trademark_export_not_found", 404)
    if not _utc(preparation.created_at) <= now < _utc(preparation.expires_at):
        _fail("trademark_export_expired")
    content, digest = document(session, monitor, candidate, preparation, now=now)
    if not hmac.compare_digest(digest, preparation.content_hash):
        _fail("trademark_export_changed")
    if download_hash is not None:
        if not isinstance(download_hash, str) or not hmac.compare_digest(download_hash, digest):
            _fail("trademark_export_changed")
        preparation.downloaded_at = preparation.downloaded_at or now
        session.flush()
    return _response(preparation, content)
