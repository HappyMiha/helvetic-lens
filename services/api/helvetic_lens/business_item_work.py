"""Native business decisions and notes share one evidence-bound transaction."""

from datetime import UTC
from uuid import uuid4

from sqlalchemy import func, select, update

from .business_item_models import BusinessItemWorkEvent as Event
from .business_monitor_sharing import _person, monitor_for
from .config import DomainError
from .models import OrganizationMembership, User
from .monitoring_subjects import _actor, _savepoint

TARGETS = {"tenders": "tender_dossier_id", "ip": "trademark_candidate_id", "auctions": "auction_item_id"}
DECISIONS = {"tenders": ["bid", "no_bid", "monitor"],
    "ip": ["reviewed", "relevant", "not_relevant", "monitor", "counsel"],
    "auctions": ["inspect", "bid", "no_bid", "monitor"]}
MAX_EVENTS = 10000


def fail(code="business_item_changed", status=409):
    raise DomainError("Reload this item's current evidence and work history.", status, code)


def _clock(now):
    if now.tzinfo is None:
        fail("business_clock_invalid", 422)
    return now.astimezone(UTC)


def _target(session, user_id, domain, monitor_id, item_id, *, write=False):
    monitor = monitor_for(session, user_id, domain, monitor_id, write=write)
    if domain == "tenders":
        from .tender_models import TenderDossier as Model
    elif domain == "ip":
        from .trademark_workflow_models import TrademarkCandidate as Model
    else:
        from .auction_workflow_models import AuctionItem as Model
    query = select(Model).where(Model.id == item_id, Model.monitor_id == monitor.id,
        Model.organization_id == monitor.organization_id).execution_options(populate_existing=True)
    row = session.scalar(query.with_for_update() if write else query)
    if row is None:
        fail("business_item_not_found", 404)
    return monitor, row


def binding(session, domain, row):
    if domain == "tenders":
        from .tender_models import TenderDossierVersion
        evidence = session.scalar(select(TenderDossierVersion).where(
            TenderDossierVersion.dossier_id == row.id, TenderDossierVersion.organization_id == row.organization_id,
            TenderDossierVersion.sequence == row.latest_sequence))
        if evidence is None:
            fail("business_item_evidence_unavailable", 409)
        return {"sequence": row.latest_sequence, "revision_id": evidence.id,
            "profile_revision": evidence.profile_revision, "fingerprint": evidence.source_hash}
    if domain == "ip":
        return {"sequence": row.sequence, "revision_id": row.source_revision_id,
            "profile_revision": row.profile_revision, "fingerprint": row.evaluation_hash}
    # The material sequence is preserved for non-material source refreshes.
    return {"sequence": row.material_sequence, "revision_id": row.source_revision_id,
        "profile_revision": row.profile_revision, "fingerprint": row.deadline_hash}


def _view(session, user_id, domain, monitor, row, now):
    if domain == "tenders":
        from .tender_repository import dossier_view
        view = dossier_view(session, row, now, user_id=user_id)
        view.update(state="available", can_review=monitor.status != "archived")
        return view
    if domain == "ip":
        from .trademark_workflow import candidate_view
        return candidate_view(session, monitor, row, now=now)
    from .auction_workflow import item_view
    return item_view(session, monitor, row, now=now)


def prepare(session, monitor, row, work):
    """Internal native-command hook, called only with locked scope/actor/item."""
    if work is None:
        return ""
    if not isinstance(work, dict) or set(work) != {"assigned_user_id", "comment"}:
        fail("business_item_input_invalid", 422)
    assignee, comment = work["assigned_user_id"], work["comment"]
    if not isinstance(comment, str) or len(comment) > 4000 or any(ord(c) < 32 and c not in "\n\r\t" for c in comment):
        fail("business_item_comment_invalid", 422)
    if assignee is not None:
        if not isinstance(assignee, str) or not assignee or len(assignee) > 36:
            fail("business_item_assignee_invalid", 422)
        if monitor.visibility == "private" and assignee != monitor.owner_user_id:
            fail("business_item_private_assignee", 422)
        # Retain the active member through commit; no assignment to a departed
        # colleague can race the checked value. Never move personal email.
        session.scalar(select(User).where(User.id == assignee).with_for_update())
        session.scalar(select(OrganizationMembership).where(
            OrganizationMembership.organization_id == monitor.organization_id,
            OrganizationMembership.user_id == assignee).with_for_update())
        person = _person(session, monitor.organization_id, assignee)
        if not person or not person["available"]:
            fail("business_item_assignee_unavailable", 422)
    row.assigned_user_id = assignee
    return comment.strip()


def record(session, domain, row, user_id, *, decision, comment, now):
    """Append within the native command's savepoint; no own commit or source copy."""
    column = getattr(Event, TARGETS[domain])
    count = session.scalar(select(func.count()).select_from(Event).where(
        column == row.id, Event.organization_id == row.organization_id))
    if count >= MAX_EVENTS:
        fail("business_item_history_capacity")
    session.add(Event(organization_id=row.organization_id, **{TARGETS[domain]: row.id},
        item_version=row.version, actor_user_id=user_id, assigned_user_id=row.assigned_user_id,
        decision=decision, comment=comment, evidence_binding=binding(session, domain, row), created_at=now))
    session.flush()


def _event_readable(session, user_id, domain, row, evidence, now):
    if domain == "tenders":
        from .tender_models import TenderDossierVersion
        from .tender_repository import source_readable
        version = session.get(TenderDossierVersion, evidence["revision_id"])
        if version is None or version.dossier_id != row.id or version.organization_id != row.organization_id:
            fail("business_item_evidence_unavailable", 409)
        source_readable(version, now, user_id=user_id)
    elif domain == "ip":
        from . import trademark_sources
        from .trademark_source_models import TrademarkRegisterRevision
        version = session.get(TrademarkRegisterRevision, evidence["revision_id"])
        if version is None or version.record_key != row.record_key:
            fail("business_item_evidence_unavailable", 409)
        trademark_sources.require_permission(session, version.permission_id, now=now, purpose="matching")
        trademark_sources.read_revision(session, version.permission_id, version.id, now=now)
    else:
        from . import auction_sources
        from .auction_source_models import AuctionSourceRecordRevision
        version = session.get(AuctionSourceRecordRevision, evidence["revision_id"])
        if version is None or version.record_key != row.record_key:
            fail("business_item_evidence_unavailable", 409)
        auction_sources.require_permission(session, version.permission_id, now=now, purpose="matching")
        auction_sources.read_revision(session, version.permission_id, version.id, now=now)


def read(session, user_id, domain, monitor_id, item_id, *, now, before_version=None, limit=20):
    now = _clock(now)
    if type(limit) is not int or not 1 <= limit <= 50 or (before_version is not None and (type(before_version) is not int or before_version < 1)):
        fail("business_page_invalid", 422)
    monitor, row = _target(session, user_id, domain, monitor_id, item_id)
    result = {"domain": domain, "monitor_id": monitor.id, "item_id": row.id, "version": row.version,
        "visibility": monitor.visibility, "creator_user_id": monitor.owner_user_id,
        "assigned": None,
        "state": "unavailable", "can_write": False, "binding": None, "decisions": [],
        "history": [], "next_before_version": None}
    try:
        view = _view(session, user_id, domain, monitor, row, now)
        if view["state"] != "available":
            result["reason"] = view.get("reason", "business_item_evidence_unavailable")
            return result
    except DomainError as error:
        result["reason"] = error.code
        return result
    role = session.scalar(select(OrganizationMembership.role).where(
        OrganizationMembership.user_id == user_id, OrganizationMembership.organization_id == monitor.organization_id))
    current = binding(session, domain, row)
    result.update(state="available", can_write=role == "organization_admin" and view["can_review"],
        assigned=_person(session, monitor.organization_id, row.assigned_user_id),
        binding=current, decisions=DECISIONS[domain], decision=row.decision,
        needs_review=view.get("needs_review", view.get("review_state") != "reviewed"))
    column = getattr(Event, TARGETS[domain])
    query = select(Event).where(column == row.id, Event.organization_id == row.organization_id)
    if before_version is not None:
        query = query.where(Event.item_version < before_version)
    events = list(session.scalars(query.order_by(Event.item_version.desc()).limit(limit + 1)))
    for event in events[:limit]:
        entry = {"id": event.id, "version": event.item_version, "state": "unavailable"}
        try:
            _event_readable(session, user_id, domain, row, event.evidence_binding, now)
            entry.update(state="available", binding=event.evidence_binding,
                older_evidence=event.evidence_binding != current or event.evidence_binding["profile_revision"] != monitor.revision,
                actor=_person(session, row.organization_id, event.actor_user_id),
                assigned=_person(session, row.organization_id, event.assigned_user_id),
                comment=event.comment, decision=event.decision,
                created_at=(event.created_at.replace(tzinfo=UTC) if event.created_at.tzinfo is None else event.created_at).isoformat())
        except DomainError:
            pass
        result["history"].append(entry)
    result["next_before_version"] = events[limit - 1].item_version if len(events) > limit else None
    return result


def act(session, user_id, domain, monitor_id, item_id, *, expected_version, expected_binding,
        assigned_user_id, comment, decision=None, now):
    now = _clock(now)
    if type(expected_version) is not int or expected_version < 1 or not isinstance(expected_binding, dict):
        fail("business_item_input_invalid", 422)
    with _savepoint(session):
        monitor, row = _target(session, user_id, domain, monitor_id, item_id, write=True)
        if row.version != expected_version or monitor.status == "archived":
            fail()
        view = _view(session, user_id, domain, monitor, row, now)
        if view["state"] != "available" or not view["can_review"]:
            fail("business_item_evidence_unavailable")
        if binding(session, domain, row) != expected_binding:
            fail()
        work = {"assigned_user_id": assigned_user_id, "comment": comment}
        if decision is not None:
            if decision not in DECISIONS[domain]:
                fail("business_item_decision_invalid", 422)
            if domain == "tenders":
                from .tender_repository import record_decision
                record_decision(session, user_id, item_id, version=expected_version,
                    sequence=row.latest_sequence, decision=decision, key=str(uuid4()), now=now, work=work)
            elif domain == "ip":
                from .trademark_workflow import review
                review(session, user_id, monitor_id, item_id, expected_version=expected_version,
                    expected_evaluation_hash=row.evaluation_hash, decision=decision, now=now, work=work)
            else:
                from .auction_workflow import decide
                decide(session, user_id, monitor_id, item_id, expected_version=expected_version,
                    expected_state_hash=view["state_hash"], decision=decision, now=now, work=work)
        else:
            text = prepare(session, monitor, row, work)
            # CAS the same version used by native decisions and source updates;
            # notes/assignment never touch reviewed_sequence or following.
            model = type(row)
            changed = session.execute(update(model).where(model.id == row.id,
                model.organization_id == row.organization_id, model.version == expected_version)
                .values(version=expected_version + 1).execution_options(synchronize_session=False))
            if changed.rowcount != 1:
                fail()
            session.refresh(row)
            record(session, domain, row, user_id, decision=None, comment=text, now=now)
        _actor(session, user_id, write=True)
        return read(session, user_id, domain, monitor_id, item_id, now=now)


def assigned_filter(query, model, user_id, assignment):
    if assignment == "mine":
        return query.where(model.assigned_user_id == user_id)
    if assignment == "unassigned":
        return query.where(model.assigned_user_id.is_(None))
    if assignment is not None:
        fail("business_item_assignment_filter_invalid", 422)
    return query
