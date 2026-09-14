"""Retained private review explanations; source versions retain independent rights."""

from sqlalchemy import select

from . import trademark_calibrations as calibrations
from . import trademark_sources as sources
from .config import DomainError
from .trademark_contracts import TrademarkPortfolio
from .trademark_models import TrademarkConfigurationRevision
from .trademark_repository import _fail, _version
from .trademark_source_models import TrademarkRegisterRevision
from .trademark_sources import _clock, _utc
from .trademark_workflow import assess, candidate_for, candidate_view
from .trademark_workflow_models import TrademarkCandidateEvent, TrademarkReview


def snapshot(session, candidate, revision_id, *, now):
    if revision_id is None:
        return None
    row = session.get(TrademarkRegisterRevision, revision_id)
    if row is None or row.record_key != candidate.record_key:
        _fail("trademark_event_evidence_invalid", 503)
    try:
        facts = sources.read_revision(session, row.permission_id, row.id, now=now)
        return {"state": "available", "facts": facts.model_dump(mode="json"), "sequence": row.sequence}
    except DomainError:
        return {"state": "unavailable", "facts": None, "sequence": row.sequence}


def event_detail(session, user_id, monitor_id, candidate_id, event_id, *, now):
    now = _clock(now)
    monitor, candidate = candidate_for(session, user_id, monitor_id, candidate_id)
    event = session.scalar(select(TrademarkCandidateEvent).where(TrademarkCandidateEvent.id == event_id,
        TrademarkCandidateEvent.candidate_id == candidate.id, TrademarkCandidateEvent.organization_id == monitor.organization_id))
    if event is None:
        _fail("trademark_event_not_found", 404)
    # Current evaluation locks precede source locks, as at the review boundary.
    current = candidate_view(session, monitor, candidate, now=now)
    configuration = session.scalar(select(TrademarkConfigurationRevision).where(
        TrademarkConfigurationRevision.monitor_id == monitor.id, TrademarkConfigurationRevision.revision == event.profile_revision))
    if configuration is None:
        _fail("trademark_event_configuration_invalid", 503)
    portfolio = TrademarkPortfolio.model_validate(configuration.configuration)
    if portfolio.fingerprint() != configuration.configuration_hash:
        _fail("trademark_event_configuration_invalid", 503)
    after = snapshot(session, candidate, event.source_revision_id, now=now)
    explanation = None
    if after["facts"]:
        from .trademark_contracts import TrademarkFacts
        try:
            revision = session.get(TrademarkRegisterRevision, event.source_revision_id)
            sources.require_permission(session, revision.permission_id, now=now, purpose="matching")
            values = [calibrations.read(session, identifier, now=now, historical=True) for identifier in event.calibration_ids]
            assessments, _ = assess(portfolio, TrademarkFacts.model_validate(after["facts"]), values, now=_utc(event.created_at))
            explanation, key = next((result, key) for result, key in assessments if result["brand_key"] == candidate.brand_key)
            if key != event.evaluation_hash:
                explanation = None
        except (DomainError, ValueError, StopIteration):
            explanation = None
    return {"id": event.id, "candidate_id": candidate.id, "monitor_id": monitor.id, "sequence": event.sequence,
        "detected_at": _utc(event.created_at).isoformat(), "profile_revision": event.profile_revision,
        "current_configuration": event.profile_revision == monitor.revision, "newer_available": event.sequence < candidate.sequence,
        "change_codes": event.change_codes, "assessment": explanation, "snapshot": after,
        "previous": snapshot(session, candidate, event.previous_revision_id, now=now), "current": current,
        "legal_conflict_confirmed": False}


def history(session, user_id, monitor_id, candidate_id, *, now, before=None, limit=20):
    monitor, candidate = candidate_for(session, user_id, monitor_id, candidate_id)
    if type(limit) is not int or not 1 <= limit <= 100:
        _fail("trademark_page_invalid", 422)
    query = select(TrademarkCandidateEvent).where(TrademarkCandidateEvent.candidate_id == candidate.id,
        TrademarkCandidateEvent.organization_id == monitor.organization_id)
    if before is not None:
        _version(before)
        if before > candidate.sequence:
            _fail("trademark_history_cursor_invalid", 422)
        query = query.where(TrademarkCandidateEvent.sequence < before)
    rows = list(session.scalars(query.order_by(TrademarkCandidateEvent.sequence.desc()).limit(limit + 1)))
    return {"items": [{"id": row.id, "sequence": row.sequence, "detected_at": _utc(row.created_at).isoformat(),
        "change_codes": row.change_codes, "profile_revision": row.profile_revision,
        "href": f"/trademark-watch?monitor={monitor.id}&candidate={candidate.id}&event={row.id}"} for row in rows[:limit]],
        "next_cursor": rows[limit - 1].sequence if len(rows) > limit else None}


def reviews(session, user_id, monitor_id, candidate_id, *, before=None, limit=20):
    monitor, candidate = candidate_for(session, user_id, monitor_id, candidate_id)
    if type(limit) is not int or not 1 <= limit <= 100:
        _fail("trademark_page_invalid", 422)
    query = select(TrademarkReview).where(TrademarkReview.candidate_id == candidate.id,
        TrademarkReview.organization_id == monitor.organization_id)
    if before is not None:
        _version(before)
        if before > candidate.version:
            _fail("trademark_history_cursor_invalid", 422)
        query = query.where(TrademarkReview.candidate_version < before)
    rows = list(session.scalars(query.order_by(TrademarkReview.candidate_version.desc()).limit(limit + 1)))
    return {"items": [{"id": row.id, "version": row.candidate_version, "sequence": row.sequence, "decision": row.decision,
        "created_at": _utc(row.created_at).isoformat(), "profile_revision": row.profile_revision} for row in rows[:limit]],
        "next_cursor": rows[limit - 1].candidate_version if len(rows) > limit else None}
