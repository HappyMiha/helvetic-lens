"""Explicit owner handover without transferring personal consent/source access."""

from sqlalchemy import select, update

from .business_monitor_models import BusinessMonitorScopeEvent
from .business_monitor_sharing import MODELS, PREFIXES, _fail, _revoke_email, read
from .jobs import TERMINAL_STATES
from .models import Job, OrganizationMembership, User
from .monitoring_subjects import _actor, _savepoint


def handover(session, user_id, domain, monitor_id, *, expected_version, successor_user_id, confirmed, now):
    if domain not in MODELS or type(expected_version) is not int or expected_version < 1 or confirmed is not True:
        _fail("business_handover_confirmation_required", 422)
    if now.tzinfo is None or successor_user_id == user_id:
        _fail("business_handover_target_invalid", 422)
    organization = _actor(session, user_id, write=True)
    model = MODELS[domain]
    with _savepoint(session):
        # Monitor-before-people lock ordering matches native email writers. Lock
        # both people in a deterministic order for opposing concurrent handovers.
        query = select(model).where(model.id == monitor_id, model.organization_id == organization,
            model.owner_user_id == user_id).execution_options(populate_existing=True)
        row = session.scalar(query.with_for_update())
        if row is None:
            _fail("business_creator_required", 403)
        session.execute(update(model).where(model.id == monitor_id, model.organization_id == organization)
                        .values(version=model.version).execution_options(synchronize_session=False))
        session.refresh(row)
        if row.owner_user_id != user_id or row.version != expected_version or row.visibility != "workspace":
            _fail()
        people = {person.id: person for person in session.scalars(select(User).where(
            User.id.in_(sorted([user_id, successor_user_id]))).order_by(User.id).with_for_update()
            .execution_options(populate_existing=True))}
        members = {member.user_id: member for member in session.scalars(select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization,
            OrganizationMembership.user_id.in_(sorted([user_id, successor_user_id])))
            .order_by(OrganizationMembership.user_id).with_for_update().execution_options(populate_existing=True))}
        if any(person not in people or not people[person].active or person not in members
               or members[person].role != "organization_admin" for person in (user_id, successor_user_id)):
            _fail("business_handover_target_unavailable", 409)
        row.owner_user_id, row.responsible_user_id = successor_user_id, successor_user_id
        row.version += 1
        if row.status == "active":
            row.status = "paused"
        session.execute(update(Job).where(Job.organization_id == organization,
            Job.target_type == PREFIXES[domain] + "_monitor", Job.target_id == row.id,
            Job.state.not_in(TERMINAL_STATES)).values(cancel_requested=True))
        _revoke_email(session, domain, row, now)
        if domain == "tenders":
            from .tender_models import TenderDocumentAccess, TenderDossier
            dossiers = select(TenderDossier.id).where(TenderDossier.monitor_id == row.id,
                TenderDossier.organization_id == organization)
            # Existing authenticated originals remain governed by their retention
            # record, but are not readable under a successor's personal identity.
            session.execute(update(TenderDocumentAccess).where(
                TenderDocumentAccess.organization_id == organization,
                TenderDocumentAccess.dossier_id.in_(dossiers), TenderDocumentAccess.revoked_at.is_(None))
                .values(revoked_at=now))
        session.add(BusinessMonitorScopeEvent(organization_id=organization,
            **{PREFIXES[domain] + "_monitor_id": row.id}, monitor_version=row.version,
            actor_user_id=user_id, action="handover", previous_owner_user_id=user_id,
            owner_user_id=successor_user_id, previous_scope="workspace", scope="workspace",
            responsible_user_id=successor_user_id, created_at=now))
        session.flush()
        return read(session, user_id, domain, monitor_id)
