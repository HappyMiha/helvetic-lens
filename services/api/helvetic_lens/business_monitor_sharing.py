"""Explicit private/workspace transitions; caller owns commit and authenticated actor."""

from datetime import UTC

from sqlalchemy import select, update

from .auction_models import AuctionMonitor
from .business_monitor_access import visible_to
from .business_monitor_models import BusinessMonitorScopeEvent
from .config import DomainError
from .jobs import TERMINAL_STATES
from .models import Job, OrganizationMembership, User
from .monitoring_subjects import _actor, _savepoint
from .tender_models import TenderMonitor
from .trademark_models import TrademarkMonitor

MODELS = {"tenders": TenderMonitor, "ip": TrademarkMonitor, "auctions": AuctionMonitor}
PREFIXES = {"tenders": "tender", "ip": "trademark", "auctions": "auction"}


def _fail(code="business_scope_changed", status=409):
    raise DomainError("Business monitor access changed. Reload its current scope.", status, code)


def monitor_for(session, user_id, domain, monitor_id, *, write=False, personal_only=False):
    organization = _actor(session, user_id, write=write)
    model = MODELS.get(domain)
    if model is None:
        _fail("business_domain_invalid", 422)
    query = select(model).where(model.id == monitor_id, model.organization_id == organization,
        visible_to(model, user_id, personal_only=personal_only)).execution_options(populate_existing=True)
    row = session.scalar(query.with_for_update() if write else query)
    if row is None:
        _fail("business_monitor_not_found", 404)
    if write:
        # SQLite SELECT FOR UPDATE is a no-op; this acquires its writer lock.
        # PostgreSQL retains monitor-before-actor ordering used by email workers.
        session.execute(update(model).where(model.id == row.id, model.organization_id == organization,
            visible_to(model, user_id, personal_only=personal_only)).values(version=model.version)
            .execution_options(synchronize_session=False))
        session.refresh(row)
        if row.owner_user_id != user_id and (personal_only or row.visibility != "workspace"):
            _fail("business_monitor_not_found", 404)
        session.scalar(select(User).where(User.id == user_id).with_for_update())
        session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == organization).with_for_update())
    _actor(session, user_id, write=write)
    return row


def _person(session, organization, user_id):
    if user_id is None:
        return None
    value = session.execute(select(User.id, User.name, User.active, OrganizationMembership.role).outerjoin(
        OrganizationMembership, (OrganizationMembership.user_id == User.id)
        & (OrganizationMembership.organization_id == organization)).where(User.id == user_id)).first()
    return {"id": user_id, "name": value.name if value else None,
        "available": bool(value and value.active and value.role == "organization_admin")}


def read(session, user_id, domain, monitor_id, *, before_version=None, limit=30):
    row = monitor_for(session, user_id, domain, monitor_id)
    if type(limit) is not int or not 1 <= limit <= 50 or (before_version is not None and (type(before_version) is not int or before_version < 1)):
        _fail("business_page_invalid", 422)
    column = getattr(BusinessMonitorScopeEvent, PREFIXES[domain] + "_monitor_id")
    query = select(BusinessMonitorScopeEvent).where(column == row.id,
        BusinessMonitorScopeEvent.organization_id == row.organization_id)
    if before_version:
        query = query.where(BusinessMonitorScopeEvent.monitor_version < before_version)
    events = list(session.scalars(query.order_by(BusinessMonitorScopeEvent.monitor_version.desc()).limit(limit + 1)))
    return {"domain": domain, "monitor_id": row.id, "monitor_version": row.version, "status": row.status,
        "visibility": row.visibility, "creator": _person(session, row.organization_id, row.owner_user_id),
        "responsible": _person(session, row.organization_id, row.responsible_user_id),
        "can_change_scope": row.owner_user_id == user_id,
        "history": [{"version": event.monitor_version, "actor": _person(session, row.organization_id, event.actor_user_id),
            "action": event.action,
            "previous_owner": _person(session, row.organization_id, event.previous_owner_user_id),
            "owner": _person(session, row.organization_id, event.owner_user_id),
            "previous_scope": event.previous_scope, "scope": event.scope,
            "responsible": _person(session, row.organization_id, event.responsible_user_id),
            "created_at": event.created_at.replace(tzinfo=UTC).isoformat() if event.created_at.tzinfo is None else event.created_at.isoformat()}
            for event in events[:limit]],
        "next_before_version": events[limit - 1].monitor_version if len(events) > limit else None}


def members(session, user_id, *, after_id=None, limit=50):
    organization = _actor(session, user_id, write=True)
    if type(limit) is not int or not 1 <= limit <= 50:
        _fail("business_page_invalid", 422)
    query = select(User.id, User.name).join(OrganizationMembership, OrganizationMembership.user_id == User.id).where(
        OrganizationMembership.organization_id == organization, OrganizationMembership.role == "organization_admin", User.active.is_(True))
    if after_id:
        if session.execute(query.where(User.id == after_id)).first() is None:
            _fail("business_members_changed", 422)
        query = query.where(User.id > after_id)
    rows = list(session.execute(query.order_by(User.id).limit(limit + 1)))
    return {"items": [{"id": row.id, "name": row.name} for row in rows[:limit]],
        "next_cursor": rows[limit - 1].id if len(rows) > limit else None}


def _revoke_email(session, domain, monitor, now):
    from . import auction_email_preferences, tender_email_preferences, trademark_email_preferences
    from .auction_workflow_models import AuctionEmailPolicy
    from .tender_models import TenderDelivery, TenderEmailPolicy
    from .trademark_email_models import TrademarkEmailPolicy
    module, model = {"tenders": (tender_email_preferences, TenderEmailPolicy),
        "ip": (trademark_email_preferences, TrademarkEmailPolicy),
        "auctions": (auction_email_preferences, AuctionEmailPolicy)}[domain]
    old = module.policy(session, monitor)
    if old is not None:
        config = module.EmailConfiguration.model_validate(old.configuration)
        value = config.model_dump(mode="json")
        value["delivery"].update(email="off", digest_at=None)
        monitor.email_revision += 1
        session.add(model(monitor_id=monitor.id, organization_id=monitor.organization_id,
            revision=monitor.email_revision, configuration=value, recipient_email=None, created_at=now))
    if domain == "tenders":
        session.execute(update(TenderDelivery).where(TenderDelivery.monitor_id == monitor.id,
            TenderDelivery.organization_id == monitor.organization_id, TenderDelivery.state == "pending").values(state="suppressed"))
    else:
        module.cancel_email_work(session, monitor)


def configure(session, user_id, domain, monitor_id, *, expected_version, visibility,
              responsible_user_id, confirmed, now):
    if type(expected_version) is not int or expected_version < 1 or type(confirmed) is not bool or visibility not in {"private", "workspace"}:
        _fail("business_scope_invalid", 422)
    if now.tzinfo is None:
        _fail("business_clock_invalid", 422)
    with _savepoint(session):
        row = monitor_for(session, user_id, domain, monitor_id, write=True)
        if row.version != expected_version:
            _fail()
        changing_scope = visibility != row.visibility
        if changing_scope and row.owner_user_id != user_id:
            _fail("business_creator_required", 403)
        if changing_scope and visibility == "workspace" and not confirmed:
            _fail("business_sharing_confirmation_required", 422)
        if visibility == "private" and responsible_user_id is not None:
            _fail("business_private_assignment_invalid", 422)
        if responsible_user_id is not None:
            person = _person(session, row.organization_id, responsible_user_id)
            if not person or not person["available"]:
                _fail("business_responsible_unavailable", 422)
        if not changing_scope and row.responsible_user_id == responsible_user_id:
            return read(session, user_id, domain, monitor_id)
        previous_scope = row.visibility
        model = MODELS[domain]
        changed = session.execute(update(model).where(model.id == row.id, model.organization_id == row.organization_id,
            visible_to(model, user_id), model.version == expected_version).values(
                visibility=visibility, responsible_user_id=responsible_user_id, version=expected_version + 1,
                status="paused" if row.status == "active" else row.status).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            _fail()
        session.refresh(row)
        session.execute(update(Job).where(Job.organization_id == row.organization_id,
            Job.target_type == PREFIXES[domain] + "_monitor", Job.target_id == row.id,
            Job.state.not_in(TERMINAL_STATES)).values(cancel_requested=True))
        _revoke_email(session, domain, row, now)
        session.add(BusinessMonitorScopeEvent(organization_id=row.organization_id,
            **{PREFIXES[domain] + "_monitor_id": row.id}, monitor_version=row.version,
            actor_user_id=user_id, previous_scope=previous_scope, scope=visibility,
            responsible_user_id=responsible_user_id, created_at=now))
        session.flush()
        return read(session, user_id, domain, monitor_id)
