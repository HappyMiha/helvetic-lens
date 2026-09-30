"""Explicit recurring public queries; durable private evidence and bounded spend."""
from datetime import UTC, timedelta
from uuid import uuid4

from sqlalchemy import func, select

from . import jobs
from .config import DomainError
from .db import utcnow
from .legal_profile_models import LegalMonitoringProfile
from .membership_locks import lock_organization
from .product_access import require
from .product_api import fail, iso
from .product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from .product_investigation_models import WebResearchPolicy as Policy
from .product_investigation_models import WebResearchTrigger as Trigger
from .product_investigations import ACTIVE, enqueue, event, plan, rows, scope, snapshot, summary
from .product_models import ProductDossier
from .product_operations import fingerprint

DAILY_LIMIT = 2
DISCLOSURE = ("Repeat only this public question after signout using Search1API and Jev/TypeSafe with Laya fallback; "
    "Pharma also searches Europe PMC. Read up to three permitted public sources, analyse new evidence with the "
    "configured workspace model and compare earlier private findings. No private text becomes a search query. "
    "Findings stay in this dossier's audience. No publication, email subscription or authenticated archive access. "
    "One query per start, at most two starts/retries per UTC day. Source reading still runs for unchanged pages. "
    "Request limits are not a monetary cap; unmetered costs remain unknown. Coverage is not exhaustive.")


def audience_key(parent, profile):
    return fingerprint({"team_managed": parent.team_managed, "audience": parent.monitoring_audience,
                        "draft": profile.status == "draft"})


def authority(session, policy, parent):
    if not policy or not parent or not policy.enabled or not policy.authorized_by_user_id:
        fail("Recurring public search is off or its authorizing account is unavailable.", 409)
    profile = session.get(LegalMonitoringProfile, parent.profile_id)
    require(session, parent, profile, policy.authorized_by_user_id, "edit")
    if policy.audience_fingerprint != audience_key(parent, profile):
        fail("The dossier audience changed. Review and enable recurring search again.", 409)


def readiness(settings, session):
    from .model_settings import resolved_settings
    from .models import ApertusConfiguration

    # The beat process has environment settings; an organization may have a
    # different saved model endpoint. Configuration inspection needs no key.
    record = session.scalar(select(ApertusConfiguration))
    configured_model = resolved_settings(settings, record, decrypt_secret=lambda value: "").model_configured
    decision = bool(settings.typesafe_api_key.get_secret_value() or (
        settings.laya_base_url and settings.laya_api_key.get_secret_value()))
    configured = bool(settings.search1api_api_key.get_secret_value() and decision and configured_model)
    return {"configured": configured, "reason": (
        "Search and analysis are configured. Live availability and source access are checked during each run."
        if configured else "Recurring research is waiting for configured search, decision and analysis providers.")}


def trigger_for(session, run):
    return session.scalar(select(Trigger).where(Trigger.investigation_id == run.id))


def worker_access(session, run, trigger):
    parent = session.get(ProductDossier, run.dossier_id)
    policy = session.get(Policy, trigger.policy_id)
    if (not policy or trigger.policy_revision != policy.revision or run.question != policy.question
            or trigger.question != policy.question or run.publication_id or run.trigger_entry_id or not run.external_discovery):
        fail("This recurring public-search authorization changed. Use the current settings.", 409)
    authority(session, policy, parent)
    return parent


def seed(session, run, trigger):
    # Deliberately exclude private saved material and automatic entity expansion.
    session.add(InvestigationBranch(**scope(run), query=trigger.question,
        reason="The explicitly authorized recurring public question is due.", checkpoint={"recurring_web": True}))
    run.status = "running"
    plan(session, run, "Search the saved public question once; read new evidence and compare earlier private findings.",
         trigger={"web_research_trigger_id": trigger.id, "policy_revision": trigger.policy_revision})
    event(session, run, "recurring_search", trigger_id=trigger.id,
          scheduled_for=iso(trigger.scheduled_for), disclosure=DISCLOSURE)


def capture(session, run, item):
    """Keep every observation, deduplicate only against the last successful analysis.

    A -> B -> A is new again. Failed extraction and unchanged observations never
    replace the successfully analysed baseline. Passage order/scores are not text.
    """
    question_key = fingerprint(run.question)
    content_key = fingerprint({"sha256": item["sha256"], "excerpts": sorted(
        [(p["passage"], p["text"]) for p in item["excerpts"]])})
    prior = session.scalar(select(InvestigationSource).join(Trigger,
        Trigger.investigation_id == InvestigationSource.investigation_id)
        .where(InvestigationSource.dossier_id == run.dossier_id, InvestigationSource.url == item["url"],
            InvestigationSource.investigation_id != run.id, Trigger.question == run.question,
            InvestigationSource.snapshot["analysis_completed"].as_boolean().is_(True))
        .order_by(InvestigationSource.created_at.desc(), InvestigationSource.id.desc()).limit(1))
    duplicate = prior if prior and prior.snapshot.get("web_content_fingerprint") == content_key else None
    source, fresh = snapshot(session, run, {**item, "allow_discovery": False,
        "web_question_fingerprint": question_key, "web_content_fingerprint": content_key,
        "analysis_completed": False, "unchanged_from": duplicate.id if duplicate else None}, public=True)
    if duplicate:
        event(session, run, "source_unchanged", source_id=source.id, previous_source_id=duplicate.id,
              reason="The same captured body and excerpts were already analysed for this question.")
    return source, fresh and not duplicate


def used_today(policy):
    return policy.budget_used if policy and policy.budget_day == utcnow().date().isoformat() else 0


def reserve_start(policy):
    day = utcnow().date().isoformat()
    if policy.budget_day != day:
        policy.budget_day, policy.budget_used = day, 0
    if policy.budget_used >= DAILY_LIMIT:
        fail("The recurring-search limit of two starts/retries per UTC day has been reached.", 409)
    policy.budget_used += 1


def retry_authority(session, run):
    trigger = trigger_for(session, run)
    if trigger:
        worker_access(session, run, trigger)
        reserve_start(session.get(Policy, trigger.policy_id))


def fence(session, policy, reason):
    for run in session.scalars(select(Investigation).join(Trigger, Trigger.investigation_id == Investigation.id)
            .where(Trigger.policy_id == policy.id, Investigation.status.in_(ACTIVE | {"paused"}))):
        if run.job_id:
            jobs.cancel(session, run.job_id)
        run.generation += 1
        run.status, run.stop_reason = "cancelled", reason
        event(session, run, "investigation_cancelled", reason=reason)


def history(policy, action, reason):
    policy.updated_at, policy.reason = utcnow(), reason
    policy.history = [*policy.history[-99:], {"revision": policy.revision, "action": action,
        "at": iso(policy.updated_at), "question": policy.question, "cadence_hours": policy.cadence_hours, "reason": reason}]


def check_policy(session, policy, settings, now):
    parent = session.get(ProductDossier, policy.dossier_id)
    policy.checked_at, policy.next_check_at = now, now + timedelta(minutes=1)
    try:
        authority(session, policy, parent)
    except DomainError:
        policy.enabled, policy.revision = False, policy.revision + 1
        reason = "Recurring search paused: the authorizing account, dossier role or audience changed."
        fence(session, policy, reason)
        history(policy, "authority_paused", reason)
        return 0
    ready = readiness(settings, session)
    if not ready["configured"]:
        policy.reason, policy.next_check_at = ready["reason"], now + timedelta(minutes=15)
        return 0
    if policy.next_run_at.replace(tzinfo=UTC) > now:
        policy.next_check_at = policy.next_run_at
        return 0
    if used_today(policy) >= DAILY_LIMIT:
        policy.reason = "Daily start limit reached. The next attempt waits until the next UTC day."
        policy.next_check_at = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return 0
    if session.scalar(select(Investigation.id).where(Investigation.dossier_id == parent.id,
            Investigation.status.in_(ACTIVE)).limit(1)):
        policy.reason = "Waiting for the active dossier investigation to finish."
        return 0
    reserve_start(policy)
    run = Investigation(dossier_id=parent.id, organization_id=parent.organization_id, request_key=str(uuid4()),
        question=policy.question, external_discovery=True, created_by_user_id=policy.authorized_by_user_id,
        actor_user_id=policy.authorized_by_user_id)
    session.add(run)
    session.flush()
    trigger = Trigger(dossier_id=parent.id, organization_id=parent.organization_id, policy_id=policy.id,
        policy_revision=policy.revision, investigation_id=run.id, question=policy.question, scheduled_for=policy.next_run_at)
    session.add(trigger)
    session.flush()
    enqueue(session, run)
    event(session, run, "investigation_queued", web_research_trigger_id=trigger.id, disclosure=DISCLOSURE)
    # No catch-up burst, even after downtime or long-running dossier work.
    policy.next_run_at = policy.next_check_at = now + timedelta(hours=policy.cadence_hours)
    policy.reason = "The scheduled question started a private investigation. Open its history for the actual outcome."
    return 1


def enqueue_due(database, settings):
    now = utcnow()
    with database.session(include_all_organizations=True) as session:
        due = list(session.execute(select(Policy.id, Policy.organization_id).where(Policy.enabled.is_(True),
            Policy.next_check_at <= now).order_by(Policy.next_check_at, Policy.id).limit(50)))
    started = checked = 0
    for identifier, organization_id in due:
        with database.organization_context(organization_id), database.session() as session:
            lock_organization(session, organization_id)
            policy = session.get(Policy, identifier, populate_existing=True)
            if not policy or not policy.enabled or policy.next_check_at.replace(tzinfo=UTC) > now:
                continue
            started += check_policy(session, policy, settings, now)
            checked += 1
            session.commit()
    return {"checked": checked, "started": started}


def trigger_payload(session, trigger):
    from .product_monitoring_outcomes import project

    run = session.get(Investigation, trigger.investigation_id)
    branches = rows(session, InvestigationBranch, run)
    return {"id": trigger.id, "policy_revision": trigger.policy_revision, "question": trigger.question,
        "scheduled_for": iso(trigger.scheduled_for), "created_at": iso(trigger.created_at),
        "investigation": summary(run), "outcome": project(session, run, trigger, branches),
        "analysed_sources": sum(b.checkpoint.get("analysed", 0) for b in branches),
        "unchanged_sources": sum(b.checkpoint.get("unchanged", 0) for b in branches),
        "coverage": [b.checkpoint["coverage"] for b in branches if b.checkpoint.get("coverage")]}


def payload(session, parent, policy, can_manage, settings, offset=0):
    query = select(Trigger).where(Trigger.dossier_id == parent.id)
    return {"dossier_id": parent.id, "can_manage": can_manage, "policy": {
        "enabled": policy.enabled if policy else False, "revision": policy.revision if policy else 0,
        "question": policy.question if policy else "", "cadence_hours": policy.cadence_hours if policy else 24,
        "daily_limit": DAILY_LIMIT, "used_today": used_today(policy), "readiness": readiness(settings, session),
        "next_run_at": iso(policy.next_run_at) if policy and policy.enabled else None,
        "checked_at": iso(policy.checked_at) if policy and policy.checked_at else None,
        "reason": policy.reason if policy else "Recurring public search is off.",
        "history": policy.history if policy else [], "disclosure": DISCLOSURE},
        "items": [trigger_payload(session, t) for t in session.scalars(query.order_by(Trigger.created_at.desc(), Trigger.id)
            .offset(offset).limit(20))],
        "total": session.scalar(select(func.count()).select_from(query.subquery())), "offset": offset, "page_size": 20}
