"""Source-backed private auction tracking. No HTTP, external bids or email.

Callers own the transaction. Monitor locks serialize lifecycle, configuration,
source projection and review. Source grants are locked before source selections.
Private rows retain references/codes, never a second copy of licensed payloads.
"""

from datetime import UTC, timedelta

from sqlalchemy import func, select

from . import auction_rules as rules
from . import auction_sources as sources
from .auction_contracts import AuctionProfile, clock, fingerprint
from .auction_models import AuctionMonitor
from .auction_repository import _fail, _version, get_monitor, owned
from .auction_source_models import (
    AuctionSourceRecordHead,
    AuctionSourceRecordRevision,
    AuctionSourceSelection,
)
from .auction_workflow_models import (
    AuctionDecision,
    AuctionItem,
    AuctionItemEvent,
    AuctionRuntime,
    AuctionSourceCursor,
)
from .business_monitor_access import collection_actor
from .config import DomainError
from .monitoring_subjects import _savepoint

MAX_SOURCES = 32
PAGE_SIZE = 50
MAX_ITEMS = 10_000
MAX_ITEM_EVENTS = 10_000
MAX_DECISIONS = 1000
MAX_REVISIONS_PER_ITEM = 100


def _monitor(session, user_id, monitor_id, *, write=False):
    row = owned(session, user_id, monitor_id, write=write)
    if write:
        row = session.scalar(select(AuctionMonitor).where(AuctionMonitor.id == row.id,
            AuctionMonitor.organization_id == row.organization_id).with_for_update().execution_options(populate_existing=True))
    return row


def _utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _profile(monitor):
    return AuctionProfile.model_validate(monitor.configuration)


def source_options(session, profile, *, now):
    """Read reviewed configured sources, without submitting private query terms."""
    now = clock(now)
    selected = list(session.scalars(select(AuctionSourceSelection).order_by(AuctionSourceSelection.source_key).limit(MAX_SOURCES + 1)))
    if len(selected) > MAX_SOURCES:
        _fail("auction_source_capacity")
    available, unavailable = [], []
    for candidate in selected:
        permission, generation, key = candidate.permission_id, candidate.generation, candidate.source_key
        try:
            _, policy = sources.require_permission(session, permission, now=now, purpose="matching")
            if not set(policy.cantons).intersection(profile.cantons) or not set(policy.categories).intersection(profile.categories):
                continue
            sources.require_permission(session, permission, now=now, purpose="display")
            current = session.scalar(select(AuctionSourceSelection).where(AuctionSourceSelection.source_key == key)
                .with_for_update().execution_options(populate_existing=True))
            if current.permission_id != permission or current.generation != generation:
                _fail("auction_source_selection_conflict")
            if current.last_received_at is None or not timedelta(0) <= now - _utc(current.last_received_at) <= timedelta(seconds=policy.max_age_seconds):
                _fail("auction_source_stale")
            # Validate the newest observation, not merely the scheduler timestamp.
            head = session.scalar(select(AuctionSourceRecordHead).where(
                AuctionSourceRecordHead.permission_id == permission, AuctionSourceRecordHead.generation == generation)
                .order_by(AuctionSourceRecordHead.last_seen_at.desc(), AuctionSourceRecordHead.record_key).limit(1))
            if head is None:
                _fail("auction_source_empty")
            sources.read_revision(session, permission, head.revision_id, now=now, purpose="matching")
            available.append((current, policy))
        except DomainError as error:
            unavailable.append({"source_key": key, "reason": error.code})
    return available, unavailable


def preview(session, user_id, payload, *, now):
    from .auction_repository import configuration
    from .monitoring_subjects import _actor
    _actor(session, user_id)
    profile = configuration(payload)
    options, unavailable = source_options(session, profile, now=now)
    covered = sorted({canton for _, policy in options for canton in policy.cantons if canton in profile.cantons})
    return {"configuration": profile.model_dump(mode="json"), "draft_available": True,
        "start_available": bool(options), "live_results_checked": bool(options), "coverage_verified": False,
        "source_attributions": [policy.attribution for _, policy in options], "available_cantons": covered,
        "unverified_cantons": sorted(set(profile.cantons) - set(covered)), "source_problems": unavailable,
        "blocking_reasons": [] if options else ["auction_source_not_configured"]}


def start(session, user_id, monitor_id, version, *, now):
    now = clock(now)
    with _savepoint(session):
        monitor = _monitor(session, user_id, monitor_id, write=True)
        collection_actor(session, monitor)
        _version(version)
        if monitor.version != version or monitor.status not in {"draft", "paused"}:
            _fail("auction_version_conflict")
        options, _ = source_options(session, _profile(monitor), now=now)
        if not options:
            _fail("auction_source_not_configured")
        monitor.status, monitor.version = "active", monitor.version + 1
        runtime = session.get(AuctionRuntime, monitor.id)
        if runtime is None:
            runtime = AuctionRuntime(monitor_id=monitor.id, organization_id=monitor.organization_id)
            session.add(runtime)
        runtime.health, runtime.next_check_at = "waiting", now
        session.flush()
    return get_monitor(session, user_id, monitor_id)


def pause(session, user_id, monitor_id, version):
    from .auction_email_preferences import cancel_email_work
    from .auction_reminders import invalidate
    with _savepoint(session):
        monitor = _monitor(session, user_id, monitor_id, write=True)
        _version(version)
        if monitor.version != version or monitor.status != "active":
            _fail("auction_version_conflict")
        monitor.status, monitor.version = "paused", monitor.version + 1
        invalidate(session, monitor.id)
        cancel_email_work(session, monitor)
        runtime = session.get(AuctionRuntime, monitor.id)
        if runtime:
            runtime.next_check_at = None
        session.flush()
    return get_monitor(session, user_id, monitor_id)


def _deadline(facts):
    # Cancellation/reopening and changed-away-and-back deadlines are new epochs.
    return fingerprint([facts.ends_at.isoformat() if facts.ends_at else None, facts.status])


def _event(session, monitor, item, revision, previous, *, kind, codes, notify, now):
    if item.material_sequence > MAX_ITEM_EVENTS:
        _fail("auction_item_event_capacity")
    session.add(AuctionItemEvent(organization_id=monitor.organization_id, item_id=item.id,
        sequence=item.material_sequence, source_revision_id=revision.id,
        previous_revision_id=previous.id if previous else None, profile_revision=monitor.revision,
        kind=kind, change_codes=sorted(set(codes)), notify=notify, created_at=now))


def _apply(session, monitor, item, revision, facts, selection, *, now, gap=False):
    profile = _profile(monitor)
    if item is None:
        assessment = rules.assessment(profile, facts)
        if assessment["status"] == "excluded":
            return None
        if session.scalar(select(func.count()).select_from(AuctionItem).where(AuctionItem.monitor_id == monitor.id)) >= MAX_ITEMS:
            _fail("auction_item_capacity")
        item = AuctionItem(monitor_id=monitor.id, organization_id=monitor.organization_id,
            record_key=revision.record_key, source_key=facts.source_key, permission_id=revision.permission_id,
            source_revision_id=revision.id, source_generation=selection.generation,
            profile_revision=monitor.revision, deadline_hash=_deadline(facts), created_at=now)
        session.add(item)
        session.flush()
        matched = assessment["status"] == "match"
        _event(session, monitor, item, revision, None, kind="new_match" if matched else "new_candidate",
            codes=["new_match" if matched else "candidate_unknown"], notify=profile.notify.new_match and matched, now=now)
        return item
    previous = session.get(AuctionSourceRecordRevision, item.source_revision_id)
    rebound = item.permission_id != selection.permission_id or item.source_generation != selection.generation
    config_changed = item.profile_revision != monitor.revision
    codes, notification = [], False
    if not rebound:
        try:
            before = sources.read_revision(session, previous.permission_id, previous.id, now=now, purpose="matching")
            changes = rules.changes(profile, before, facts)
            # A bid increment is retained in history but quiet unless opted in.
            material = [change for change in changes if change["code"] != "price_changed"
                or change["field"] != "prices.current_bid" or profile.notify.every_bid_change]
            codes = [change["code"] for change in material]
            notification = any(change["notify"] for change in material)
        except DomainError:
            gap = True
    if rebound or gap:
        codes.append("source_evidence_gap")
    if config_changed:
        codes.append("profile_changed")
    if _deadline(facts) != item.deadline_hash or rebound:
        item.deadline_generation += 1
        item.deadline_hash = _deadline(facts)
    if codes:
        item.material_sequence += 1
        _event(session, monitor, item, revision, previous, kind="material_change", codes=codes,
            notify=item.following and notification, now=now)
    if codes or previous.state_hash != revision.state_hash:
        item.version += 1
    item.permission_id, item.source_revision_id = revision.permission_id, revision.id
    item.source_generation, item.profile_revision = selection.generation, monitor.revision
    session.flush()
    return item


def _sync_head(session, monitor, selection, head, *, now):
    item = session.scalar(select(AuctionItem).where(AuctionItem.monitor_id == monitor.id,
        AuctionItem.record_key == head["record_key"]).with_for_update().execution_options(populate_existing=True))
    target = session.get(AuctionSourceRecordRevision, head["revision_id"])
    if item is None:
        _apply(session, monitor, None, target, head["facts"], selection, now=now)
        return False
    if item.source_revision_id == target.id and item.profile_revision == monitor.revision and item.source_generation == selection.generation:
        return False
    previous = session.get(AuctionSourceRecordRevision, item.source_revision_id)
    if item.permission_id != selection.permission_id or item.source_generation != selection.generation or previous.sequence >= target.sequence:
        _apply(session, monitor, item, target, head["facts"], selection, now=now)
        return False
    revisions = list(session.scalars(select(AuctionSourceRecordRevision).where(
        AuctionSourceRecordRevision.permission_id == selection.permission_id,
        AuctionSourceRecordRevision.record_key == item.record_key,
        AuctionSourceRecordRevision.sequence > previous.sequence, AuctionSourceRecordRevision.sequence <= target.sequence,
        AuctionSourceRecordRevision.normalized_payload.is_not(None), AuctionSourceRecordRevision.normalized_expires_at > now)
        .order_by(AuctionSourceRecordRevision.sequence).limit(MAX_REVISIONS_PER_ITEM + 1)))
    expected = previous.sequence + 1
    for revision in revisions[:MAX_REVISIONS_PER_ITEM]:
        try:
            facts = sources.read_revision(session, revision.permission_id, revision.id, now=now, purpose="matching")
        except DomainError:
            continue
        _apply(session, monitor, item, revision, facts, selection, now=now, gap=revision.sequence != expected)
        expected = revision.sequence + 1
    return len(revisions) > MAX_REVISIONS_PER_ITEM or item.source_revision_id != target.id


def refresh(session, user_id, monitor_id, *, now):
    from .auction_reminders import plan
    now = clock(now)
    with _savepoint(session):
        monitor = _monitor(session, user_id, monitor_id, write=True)
        collection_actor(session, monitor)
        if monitor.status != "active":
            _fail("auction_monitor_not_active")
        runtime = session.get(AuctionRuntime, monitor.id)
        if runtime is None:
            _fail("auction_runtime_unavailable")
        options, unavailable = source_options(session, _profile(monitor), now=now)
        pending, stale, examined = False, False, 0
        for selection, _ in options:
            cursor = session.get(AuctionSourceCursor, (monitor.id, selection.source_key))
            if cursor is None:
                cursor = AuctionSourceCursor(monitor_id=monitor.id, organization_id=monitor.organization_id,
                    source_key=selection.source_key, permission_id=selection.permission_id, generation=selection.generation)
                session.add(cursor)
                session.flush()
            if cursor.permission_id != selection.permission_id or cursor.generation != selection.generation:
                cursor.permission_id, cursor.generation, cursor.after_key = selection.permission_id, selection.generation, None
            if cursor.scan_unavailable_count is None or cursor.after_key is None:
                cursor.after_key, cursor.scan_unavailable_count = None, 0
            page = sources.read_current(session, selection.source_key, now=now, purpose="matching", limit=PAGE_SIZE, after=cursor.after_key)
            existing_keys = set(session.scalars(select(AuctionItem.record_key).where(
                AuctionItem.monitor_id == monitor.id, AuctionItem.organization_id == monitor.organization_id,
                AuctionItem.record_key.in_([head["record_key"] for head in page["items"]]))))
            profile = _profile(monitor)
            for head in page["items"]:
                examined += 1
                if head["state"] != "available":
                    cursor.scan_unavailable_count += 1
                    continue
                if head["record_key"] not in existing_keys and rules.assessment(profile, head["facts"])["status"] == "excluded":
                    continue
                item_pending = _sync_head(session, monitor, selection, head, now=now)
                pending |= item_pending
                if not item_pending:
                    item = session.scalar(select(AuctionItem).where(AuctionItem.monitor_id == monitor.id,
                        AuctionItem.record_key == head["record_key"]))
                    if item is not None:
                        plan(session, monitor, item, head["facts"], now=now)
            stale |= cursor.scan_unavailable_count > 0
            cursor.after_key = page["next_cursor"]
            pending |= cursor.after_key is not None
        runtime.health = "source_unavailable" if not options else "catching_up" if pending else "partial" if stale or unavailable else "current"
        runtime.last_check_at = now
        runtime.next_check_at = now + timedelta(seconds=15 if pending else 60)
        session.flush()
        from .auction_delivery import prepare_monitor
        prepare_monitor(session, monitor, now=now)
        return {"health": runtime.health, "examined": examined, "coverage_verified": False,
                "last_check_at": now.isoformat(), "next_check_at": runtime.next_check_at.isoformat()}


def _item(session, user_id, monitor_id, item_id, *, write=False):
    monitor = _monitor(session, user_id, monitor_id, write=write)
    row = session.scalar(select(AuctionItem).where(AuctionItem.id == item_id, AuctionItem.monitor_id == monitor.id,
        AuctionItem.organization_id == monitor.organization_id).execution_options(populate_existing=True))
    if row is None:
        _fail("auction_item_not_found", 404)
    return monitor, row


def _current(session, monitor, item, *, now, purpose="display"):
    _, policy = sources.require_permission(session, item.permission_id, now=now, purpose=purpose)
    selected = session.scalar(select(AuctionSourceSelection).where(AuctionSourceSelection.source_key == item.source_key)
        .with_for_update().execution_options(populate_existing=True))
    if selected is None or selected.permission_id != item.permission_id or selected.generation != item.source_generation:
        _fail("auction_source_selection_conflict")
    head = session.get(AuctionSourceRecordHead, (item.permission_id, item.record_key), populate_existing=True)
    if head is None or head.generation != selected.generation or not timedelta(0) <= now - _utc(head.last_seen_at) <= timedelta(seconds=policy.max_age_seconds):
        _fail("auction_source_stale")
    facts = sources.read_revision(session, item.permission_id, head.revision_id, now=now, purpose=purpose)
    applied = session.get(AuctionSourceRecordRevision, item.source_revision_id)
    if applied.state_hash != facts.state_hash() or item.profile_revision != monitor.revision:
        _fail("auction_item_refresh_required")
    return facts, head, policy


def item_view(session, monitor, item, *, now):
    result = {"id": item.id, "monitor_id": monitor.id, "version": item.version, "following": item.following,
        "decision": item.decision, "material_sequence": item.material_sequence,
        "needs_review": item.reviewed_sequence != item.material_sequence, "deadline_generation": item.deadline_generation,
        "state": "unavailable", "facts": None, "assessment": None, "can_review": False}
    try:
        facts, head, policy = _current(session, monitor, item, now=clock(now))
        sources.require_permission(session, item.permission_id, now=now, purpose="matching")
        result.update(state="available", facts=facts.model_dump(mode="json"), source_revision_id=head.revision_id,
            state_hash=facts.state_hash(), assessment=rules.assessment(_profile(monitor), facts),
            attribution=policy.attribution, can_review=policy.private_decisions_allowed and monitor.status != "archived")
    except DomainError as error:
        result["reason"] = error.code
    return result


def list_items(session, user_id, monitor_id, *, now, limit=20, after=None, following_only=False, assignment=None):
    from .business_item_work import assigned_filter
    monitor = _monitor(session, user_id, monitor_id)
    if type(limit) is not int or not 1 <= limit <= 100 or type(following_only) is not bool:
        _fail("auction_page_invalid", 422)
    query = select(AuctionItem).where(AuctionItem.monitor_id == monitor.id, AuctionItem.organization_id == monitor.organization_id)
    query = assigned_filter(query, AuctionItem, user_id, assignment)
    if after is not None:
        _item(session, user_id, monitor_id, after)
        query = query.where(AuctionItem.id > after)
    if following_only:
        query = query.where(AuctionItem.following.is_(True))
    rows = list(session.scalars(query.order_by(AuctionItem.id).limit(limit + 1)))
    runtime = session.get(AuctionRuntime, monitor.id)
    return {"items": [item_view(session, monitor, item, now=now) for item in rows[:limit]],
        "next_cursor": rows[limit - 1].id if len(rows) > limit else None,
        "health": runtime.health if runtime else "not_started", "coverage_verified": False}


def decide(session, user_id, monitor_id, item_id, *, expected_version, expected_state_hash, decision, now, work=None):
    if decision not in {"inspect", "bid", "no_bid", "monitor"}:
        _fail("auction_decision_invalid", 422)
    return _act(session, user_id, monitor_id, item_id, expected_version=expected_version,
        expected_state_hash=expected_state_hash, decision=decision, following=None, now=now, work=work)


def follow(session, user_id, monitor_id, item_id, *, expected_version, expected_state_hash, following, now):
    if type(following) is not bool:
        _fail("auction_follow_invalid", 422)
    return _act(session, user_id, monitor_id, item_id, expected_version=expected_version,
        expected_state_hash=expected_state_hash, decision=None, following=following, now=now)


def _act(session, user_id, monitor_id, item_id, *, expected_version, expected_state_hash, decision, following, now, work=None):
    from . import business_item_work
    from .auction_reminders import invalidate, plan
    now = clock(now)
    with _savepoint(session):
        monitor, item = _item(session, user_id, monitor_id, item_id, write=True)
        _version(expected_version)
        if item.version != expected_version or monitor.status == "archived":
            _fail("auction_version_conflict")
        # Stopping a private follow remains possible after source permission loss.
        if following is not False:
            sources.require_permission(session, item.permission_id, now=now, purpose="display")
            sources.require_permission(session, item.permission_id, now=now, purpose="matching")
            facts, head, _ = _current(session, monitor, item, now=now, purpose="decision")
            if facts.state_hash() != expected_state_hash:
                _fail("auction_item_refresh_required")
            item.source_revision_id = head.revision_id
        if work is None and ((decision is not None and item.decision == decision and item.reviewed_sequence == item.material_sequence)
                or following is not None and item.following == following):
            return item_view(session, monitor, item, now=now)
        if session.scalar(select(func.count()).select_from(AuctionDecision).where(AuctionDecision.item_id == item.id)) >= MAX_DECISIONS:
            _fail("auction_decision_capacity")
        comment = business_item_work.prepare(session, monitor, item, work)
        if decision is not None:
            item.decision, item.reviewed_sequence = decision, item.material_sequence
        if following is not None:
            item.following = following
        if following is False:
            invalidate(session, monitor.id, item_id=item.id)
        elif following is True:
            plan(session, monitor, item, facts, now=now)
        item.version += 1
        session.add(AuctionDecision(organization_id=monitor.organization_id, item_id=item.id, item_version=item.version,
            material_sequence=item.material_sequence, source_revision_id=item.source_revision_id,
            decision=item.decision, following=item.following, actor_user_id=user_id, created_at=now))
        session.flush()
        if decision is not None:
            business_item_work.record(session, "auctions", item, user_id, decision=decision, comment=comment, now=now)
        return item_view(session, monitor, item, now=now)


def history(session, user_id, monitor_id, item_id, *, now, before=None, limit=20):
    _, item = _item(session, user_id, monitor_id, item_id)
    if type(limit) is not int or not 1 <= limit <= 100:
        _fail("auction_page_invalid", 422)
    sources.require_permission(session, item.permission_id, now=now, purpose="display")
    query = select(AuctionSourceRecordRevision).where(AuctionSourceRecordRevision.permission_id == item.permission_id,
        AuctionSourceRecordRevision.record_key == item.record_key)
    if before is not None:
        _version(before)
        query = query.where(AuctionSourceRecordRevision.sequence < before)
    rows = list(session.scalars(query.order_by(AuctionSourceRecordRevision.sequence.desc()).limit(limit + 1)))
    items = []
    for row in rows[:limit]:
        value = {"id": row.id, "sequence": row.sequence, "observed_at": _utc(row.received_at).isoformat(), "state": "unavailable"}
        try:
            facts = sources.read_revision(session, item.permission_id, row.id, now=now)
            value.update(state="available", facts=facts.model_dump(mode="json"))
        except DomainError:
            pass
        items.append(value)
    return {"items": items, "next_cursor": rows[limit - 1].sequence if len(rows) > limit else None}
