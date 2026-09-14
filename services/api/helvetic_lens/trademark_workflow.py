"""Private IP review from permitted journal records; no HTTP, filing or outreach."""

from datetime import timedelta

from sqlalchemy import func, select

from . import trademark_calibrations as calibrations
from . import trademark_deadlines as deadlines
from . import trademark_matching as matching
from . import trademark_sources as sources
from .config import DomainError
from .monitoring_subjects import _actor, _savepoint
from .trademark_contracts import TrademarkPortfolio
from .trademark_models import TrademarkMonitor
from .trademark_repository import _fail, _version, configuration, get_monitor, owned
from .trademark_source_models import (
    TrademarkRegisterHead,
    TrademarkRegisterRevision,
    TrademarkSourceSelection,
)
from .trademark_sources import _clock, _utc
from .trademark_workflow_models import (
    TrademarkCandidate,
    TrademarkCandidateEvent,
    TrademarkProjectionCursor,
    TrademarkReview,
    TrademarkRuntime,
)

MAX_SOURCES, PAGE_SIZE, MAX_REVISIONS = 32, 10, 20
MAX_CANDIDATES, MAX_EVENTS, MAX_REVIEWS = 10000, 10000, 1000
DECISIONS = {"reviewed", "relevant", "not_relevant", "monitor", "counsel"}


def monitor_for(session, user_id, monitor_id, *, write=False):
    row = owned(session, user_id, monitor_id, write=write)
    if write:
        row = session.scalar(select(TrademarkMonitor).where(TrademarkMonitor.id == row.id,
            TrademarkMonitor.organization_id == row.organization_id).with_for_update().execution_options(populate_existing=True))
    return row


def source_options(session, *, now):
    now = _clock(now)
    selected = list(session.scalars(select(TrademarkSourceSelection).order_by(TrademarkSourceSelection.source_key).limit(MAX_SOURCES + 1)))
    if len(selected) > MAX_SOURCES:
        _fail("trademark_source_capacity")
    options, problems = [], []
    for candidate in selected:
        permission, generation, key = candidate.permission_id, candidate.generation, candidate.source_key
        try:
            _, policy = sources.require_permission(session, permission, now=now, purpose="matching")
            sources.require_permission(session, permission, now=now, purpose="display")
            selected = sources._selection(session, key)
            if selected.permission_id != permission or selected.generation != generation:
                _fail("trademark_source_selection_conflict")
            head = session.scalar(select(TrademarkRegisterHead).where(TrademarkRegisterHead.permission_id == permission,
                TrademarkRegisterHead.generation == generation).order_by(TrademarkRegisterHead.last_seen_at.desc()).limit(1))
            if head is None or not timedelta(0) <= now - _utc(head.last_seen_at) <= timedelta(seconds=policy.max_age_seconds):
                _fail("trademark_evidence_stale")
            sources.read_revision(session, permission, head.revision_id, now=now, purpose="matching")
            options.append((selected, policy))
        except DomainError as error:
            problems.append({"source_key": key, "reason": error.code})
    return options, problems


def preview(session, user_id, payload, *, now):
    _actor(session, user_id)
    portfolio = configuration(payload)
    deadlines.guard(session)
    values, missing = calibrations.current(session, portfolio, now=now)
    options, problems = source_options(session, now=now)
    usable = any(b.exact_name or b.owners_of_interest or b.language in {c.language for c in values} for b in portfolio.brands)
    return {"configuration": portfolio.model_dump(mode="json"), "draft_available": True,
        "start_available": bool(options) and usable, "live_results_checked": bool(options), "coverage_verified": False,
        "source_attributions": [policy.attribution for _, policy in options], "source_problems": problems,
        "similarity_unavailable_languages": missing,
        "blocking_reasons": (["trademark_source_not_configured"] if not options else [])
            + (["trademark_similarity_calibration_unavailable"] if not usable else [])}


def start(session, user_id, monitor_id, version, *, now):
    now = _clock(now)
    with _savepoint(session):
        monitor = monitor_for(session, user_id, monitor_id, write=True)
        _version(version)
        if monitor.version != version or monitor.status not in {"draft", "paused"}:
            _fail("trademark_version_conflict")
        checked = preview(session, user_id, monitor.configuration, now=now)
        if not checked["start_available"]:
            _fail(checked["blocking_reasons"][0])
        monitor.status, monitor.version = "active", monitor.version + 1
        runtime = session.get(TrademarkRuntime, monitor.id)
        if runtime is None:
            runtime = TrademarkRuntime(monitor_id=monitor.id, organization_id=monitor.organization_id)
            session.add(runtime)
        runtime.health, runtime.next_check_at = "waiting", now
        session.flush()
    return get_monitor(session, user_id, monitor_id)


def pause(session, user_id, monitor_id, version):
    from .trademark_email_preferences import cancel_email_work
    with _savepoint(session):
        monitor = monitor_for(session, user_id, monitor_id, write=True)
        _version(version)
        if monitor.version != version or monitor.status != "active":
            _fail("trademark_version_conflict")
        monitor.status, monitor.version = "paused", monitor.version + 1
        cancel_email_work(session, monitor)
        runtime = session.get(TrademarkRuntime, monitor.id)
        if runtime:
            runtime.next_check_at = None
        session.flush()
    return get_monitor(session, user_id, monitor_id)


def assess(portfolio, facts, values, *, now):
    result = matching.assess(portfolio, facts, calibrations=values, now=now)
    identifiers = [v.fingerprint() for v in values]
    return [(item, calibrations.evaluation_hash(portfolio, facts, item, identifiers)) for item in result["results"]], identifiers


def _apply(session, monitor, portfolio, selection, revision, facts, values, *, now, gap=False):
    _, deadline_binding = deadlines.evaluate(session, selection.source_key, facts, portfolio.deadline_context, now=now)
    assessments, identifiers = assess(portfolio, facts, values, now=now)
    unknown = 0
    for result, evaluation in assessments:
        evaluation = deadlines.evaluation_hash(evaluation, deadline_binding)
        row = session.scalar(select(TrademarkCandidate).where(TrademarkCandidate.monitor_id == monitor.id,
            TrademarkCandidate.source_key == selection.source_key, TrademarkCandidate.record_key == revision.record_key,
            TrademarkCandidate.brand_key == result["brand_key"]))
        unknown += result["state"] == "unavailable"
        if row is None:
            if result["state"] != "candidate":
                continue
            if session.scalar(select(func.count()).select_from(TrademarkCandidate).where(TrademarkCandidate.monitor_id == monitor.id)) >= MAX_CANDIDATES:
                _fail("trademark_candidate_capacity")
            row = TrademarkCandidate(organization_id=monitor.organization_id, monitor_id=monitor.id,
                source_key=selection.source_key, record_key=revision.record_key, brand_key=result["brand_key"],
                permission_id=revision.permission_id, source_generation=selection.generation, source_revision_id=revision.id,
                profile_revision=monitor.revision, evaluation_hash=evaluation, calibration_ids=identifiers,
                deadline_binding=deadline_binding, created_at=now)
            session.add(row)
            session.flush()
            codes, previous = ["new_candidate"], None
        else:
            previous = session.get(TrademarkRegisterRevision, row.source_revision_id)
            rebound = row.permission_id != revision.permission_id or row.source_generation != selection.generation
            if not rebound and previous.sequence > revision.sequence:
                continue
            codes = []
            if rebound:
                codes.append("source_changed")
            if row.profile_revision != monitor.revision:
                codes.append("portfolio_changed")
            if row.calibration_ids != identifiers:
                codes.append("evaluation_changed")
            if row.deadline_binding != deadline_binding:
                codes.append("deadline_changed")
            if previous.material_hash != revision.material_hash:
                try:
                    before = sources.read_revision(session, previous.permission_id, previous.id, now=now, purpose="matching")
                    codes.extend("changed_" + field for field in type(before).model_fields if field not in {
                        "source_url", "source_sha256", "source_document_sha256"} and getattr(before, field) != getattr(facts, field))
                except DomainError:
                    gap = True
                codes.append("register_changed")
            if gap:
                codes.append("evidence_gap")
            if row.evaluation_hash != evaluation and not codes:
                codes.append("evaluation_changed")
            if codes:
                row.sequence, row.version = row.sequence + 1, row.version + 1
            row.permission_id, row.source_generation, row.source_revision_id = revision.permission_id, selection.generation, revision.id
            row.profile_revision, row.evaluation_hash, row.calibration_ids = monitor.revision, evaluation, identifiers
            row.deadline_binding = deadline_binding
        if codes:
            if row.sequence > MAX_EVENTS:
                _fail("trademark_event_capacity")
            session.add(TrademarkCandidateEvent(organization_id=monitor.organization_id, candidate_id=row.id,
                sequence=row.sequence, source_revision_id=revision.id, previous_revision_id=previous.id if previous else None,
                deadline_binding=deadline_binding,
                profile_revision=monitor.revision, evaluation_hash=evaluation, calibration_ids=identifiers,
                change_codes=sorted(set(codes)), created_at=now))
        session.flush()
    return unknown


def _sync_head(session, monitor, portfolio, selection, head, values, *, now):
    target = session.get(TrademarkRegisterRevision, head["revision_id"])
    existing = list(session.scalars(select(TrademarkCandidate).where(TrademarkCandidate.monitor_id == monitor.id,
        TrademarkCandidate.source_key == selection.source_key, TrademarkCandidate.record_key == head["record_key"],
        TrademarkCandidate.brand_key.in_([brand.key for brand in portfolio.brands]))))
    if not existing or any(row.permission_id != selection.permission_id or row.source_generation != selection.generation
            or row.profile_revision != monitor.revision for row in existing):
        return False, _apply(session, monitor, portfolio, selection, target, head["facts"], values, now=now)
    previous = [session.get(TrademarkRegisterRevision, row.source_revision_id) for row in existing]
    oldest = min(row.sequence for row in previous)
    if oldest >= target.sequence:
        return False, _apply(session, monitor, portfolio, selection, target, head["facts"], values, now=now)
    revisions = list(session.scalars(select(TrademarkRegisterRevision).where(TrademarkRegisterRevision.permission_id == selection.permission_id,
        TrademarkRegisterRevision.record_key == head["record_key"], TrademarkRegisterRevision.sequence > oldest,
        TrademarkRegisterRevision.sequence <= target.sequence, TrademarkRegisterRevision.normalized_payload.is_not(None),
        TrademarkRegisterRevision.normalized_expires_at > now).order_by(TrademarkRegisterRevision.sequence).limit(MAX_REVISIONS + 1)))
    expected, unknown = oldest + 1, 0
    for revision in revisions[:MAX_REVISIONS]:
        facts = sources.read_revision(session, selection.permission_id, revision.id, now=now, purpose="matching")
        unknown = _apply(session, monitor, portfolio, selection, revision, facts, values, now=now, gap=revision.sequence != expected)
        expected = revision.sequence + 1
    if not revisions:
        return False, _apply(session, monitor, portfolio, selection, target, head["facts"], values, now=now, gap=True)
    return revisions[min(len(revisions), MAX_REVISIONS) - 1].id != target.id, unknown


def refresh(session, user_id, monitor_id, *, now):
    now = _clock(now)
    with _savepoint(session):
        monitor = monitor_for(session, user_id, monitor_id, write=True)
        if monitor.status != "active":
            _fail("trademark_monitor_not_active")
        portfolio = TrademarkPortfolio.model_validate(monitor.configuration)
        deadlines.guard(session)
        values, missing = calibrations.current(session, portfolio, now=now)
        options, problems = source_options(session, now=now)
        pending, unknown, examined = False, 0, 0
        for selection, _ in options:
            cursor = session.get(TrademarkProjectionCursor, (monitor.id, selection.source_key))
            if cursor is None:
                cursor = TrademarkProjectionCursor(monitor_id=monitor.id, organization_id=monitor.organization_id,
                    source_key=selection.source_key, permission_id=selection.permission_id, generation=selection.generation)
                session.add(cursor)
            if cursor.permission_id != selection.permission_id or cursor.generation != selection.generation:
                cursor.permission_id, cursor.generation, cursor.after_key = selection.permission_id, selection.generation, None
            page = sources.read_current(session, selection.source_key, now=now, purpose="matching", limit=PAGE_SIZE, after=cursor.after_key)
            for head in page["items"]:
                examined += 1
                if head["state"] != "available":
                    unknown += 1
                    continue
                item_pending, unavailable = _sync_head(session, monitor, portfolio, selection, head, values, now=now)
                pending |= item_pending
                unknown += unavailable
            cursor.after_key = page["next_cursor"]
            pending |= cursor.after_key is not None
        runtime = session.get(TrademarkRuntime, monitor.id)
        runtime.health = "source_unavailable" if not options else "catching_up" if pending else "partial" if unknown or missing or problems else "current"
        runtime.last_check_at, runtime.next_check_at = now, now + timedelta(seconds=15 if pending else 60)
        runtime.unavailable_count = unknown
        session.flush()
        from .trademark_delivery import prepare_monitor
        prepare_monitor(session, monitor, now=now)
        return {"health": runtime.health, "examined": examined, "unavailable_count": unknown, "similarity_unavailable_languages": missing,
            "coverage_verified": False, "last_check_at": now.isoformat(), "next_check_at": runtime.next_check_at.isoformat()}


def candidate_for(session, user_id, monitor_id, candidate_id, *, write=False):
    monitor = monitor_for(session, user_id, monitor_id, write=write)
    row = session.scalar(select(TrademarkCandidate).where(TrademarkCandidate.id == candidate_id,
        TrademarkCandidate.monitor_id == monitor.id, TrademarkCandidate.organization_id == monitor.organization_id)
        .execution_options(populate_existing=True))
    if row is None:
        _fail("trademark_candidate_not_found", 404)
    return monitor, row


def current(session, monitor, row, *, now, purpose="display", with_deadline=False):
    now = _clock(now)
    portfolio = TrademarkPortfolio.model_validate(monitor.configuration)
    deadlines.guard(session)
    values, missing = calibrations.current(session, portfolio, now=now)
    _, policy = sources.require_permission(session, row.permission_id, now=now, purpose=purpose)
    sources.require_permission(session, row.permission_id, now=now, purpose="matching")
    selected = sources._selection(session, row.source_key)
    if selected is None or selected.permission_id != row.permission_id or selected.generation != row.source_generation:
        _fail("trademark_source_selection_conflict")
    head = session.get(TrademarkRegisterHead, (row.permission_id, row.record_key), populate_existing=True)
    if head is None or head.generation != selected.generation or not timedelta(0) <= now - _utc(head.last_seen_at) <= timedelta(seconds=policy.max_age_seconds):
        _fail("trademark_evidence_stale")
    facts = sources.read_revision(session, row.permission_id, head.revision_id, now=now, purpose=purpose)
    deadline, deadline_binding = deadlines.evaluate(session, row.source_key, facts, portfolio.deadline_context, now=now)
    assessments, identifiers = assess(portfolio, facts, values, now=now)
    found = next(((result, deadlines.evaluation_hash(key, deadline_binding)) for result, key in assessments if result["brand_key"] == row.brand_key), None)
    applied = session.get(TrademarkRegisterRevision, row.source_revision_id)
    if (found is None or row.profile_revision != monitor.revision or found[1] != row.evaluation_hash
            or identifiers != row.calibration_ids or applied.material_sequence != session.get(TrademarkRegisterRevision, head.revision_id).material_sequence):
        _fail("trademark_candidate_refresh_required")
    result = (facts, found[0], policy, missing)
    return (*result, deadline) if with_deadline else result


def candidate_view(session, monitor, row, *, now):
    result = {"id": row.id, "monitor_id": monitor.id, "brand_key": row.brand_key, "version": row.version,
        "sequence": row.sequence, "reviewed_sequence": row.reviewed_sequence, "needs_review": row.sequence > row.reviewed_sequence,
        "decision": row.decision, "state": "unavailable", "facts": None, "assessment": None, "can_review": False,
        "legal_conflict_confirmed": False, "coverage_verified": False}
    try:
        facts, assessment, policy, missing, deadline = current(session, monitor, row, now=now, with_deadline=True)
        result.update(state="available", facts=facts.model_dump(mode="json"), assessment=assessment,
            evaluation_hash=row.evaluation_hash, attribution=policy.attribution, similarity_unavailable_languages=missing,
            can_review=monitor.status != "archived" and policy.private_decisions_allowed, deadline_context=deadline)
    except DomainError as error:
        result["reason"] = error.code
    return result


def list_candidates(session, user_id, monitor_id, *, now, after=None, limit=20):
    monitor = monitor_for(session, user_id, monitor_id)
    if type(limit) is not int or not 1 <= limit <= 100:
        _fail("trademark_page_invalid", 422)
    query = select(TrademarkCandidate).where(TrademarkCandidate.monitor_id == monitor.id)
    if after:
        candidate_for(session, user_id, monitor_id, after)
        query = query.where(TrademarkCandidate.id > after)
    rows = list(session.scalars(query.order_by(TrademarkCandidate.id).limit(limit + 1)))
    return {"items": [candidate_view(session, monitor, row, now=now) for row in rows[:limit]],
        "next_cursor": rows[limit - 1].id if len(rows) > limit else None, "coverage_verified": False}


def review(session, user_id, monitor_id, candidate_id, *, expected_version, expected_evaluation_hash, decision, now):
    now = _clock(now)
    if decision not in DECISIONS:
        _fail("trademark_decision_invalid", 422)
    with _savepoint(session):
        monitor, row = candidate_for(session, user_id, monitor_id, candidate_id, write=True)
        _version(expected_version)
        if monitor.status == "archived" or row.version != expected_version:
            _fail("trademark_version_conflict")
        current(session, monitor, row, now=now)
        sources.require_permission(session, row.permission_id, now=now, purpose="decision")
        if row.evaluation_hash != expected_evaluation_hash:
            _fail("trademark_candidate_refresh_required")
        if row.reviewed_sequence == row.sequence and row.decision == decision:
            return candidate_view(session, monitor, row, now=now)
        if session.scalar(select(func.count()).select_from(TrademarkReview).where(TrademarkReview.candidate_id == row.id)) >= MAX_REVIEWS:
            _fail("trademark_review_capacity")
        row.version, row.reviewed_sequence, row.decision = row.version + 1, row.sequence, decision
        session.add(TrademarkReview(organization_id=monitor.organization_id, candidate_id=row.id,
            candidate_version=row.version, sequence=row.sequence, source_revision_id=row.source_revision_id,
            profile_revision=monitor.revision, evaluation_hash=row.evaluation_hash, decision=decision, actor_user_id=user_id, created_at=now))
        session.flush()
        return candidate_view(session, monitor, row, now=now)
