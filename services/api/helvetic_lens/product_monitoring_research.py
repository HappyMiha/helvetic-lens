"""Explicit standing authority for bounded, private native-monitoring follow-up."""
import hashlib
import json
from datetime import UTC, timedelta
from uuid import uuid4

from sqlalchemy import exists, func, select

from . import jobs, product_page_research, topic_matching
from .config import DomainError
from .db import utcnow
from .legal_profile_models import LegalMonitoringProfile
from .membership_locks import lock_organization
from .models import RegulatoryEventState, TopicEventMatch
from .product_access import require
from .product_api import fail, iso
from .product_investigation_models import (
    Investigation,
    InvestigationBranch,
)
from .product_investigation_models import (
    MonitoringResearchPolicy as Policy,
)
from .product_investigation_models import (
    MonitoringResearchTrigger as Trigger,
)
from .product_investigations import ACTIVE, enqueue, event, plan, scope, snapshot, summary
from .product_models import ProductDossier
from .product_operations import fingerprint
from .product_source_reviews import current_reviews

QUESTION = "What does this new monitoring signal support, and how does it compare with earlier dossier findings?"
DISCLOSURE = ("Analyse new saved topic-match metadata using the configured workspace model, then compare with earlier "
    "private findings. No public search or publication. Event metadata is not the full source document. "
    "Up to one extraction and one comparison request per start; failed paid work requires an explicit retry.")
PAGE_DISCLOSURE = ("Also analyse a bounded text excerpt around the first change in future retained page versions from linked "
    "active daily watches. Earlier and new excerpts stay inspectable. The same private audience and daily limit apply; "
    "no additional source fetching, public search or publication.")


def profile_key(parent, profile):
    return fingerprint({"profile_id": profile.id, "revision": profile.revision,
        "topics": sorted(profile.topic_ids_json), "audience": parent.monitoring_audience})


def authority(session, policy, parent):
    profile = session.get(LegalMonitoringProfile, parent.profile_id)
    if not policy.enabled or not policy.authorized_by_user_id:
        fail("Automatic research is off or its authorizing account is unavailable.", 409)
    require(session, parent, profile, policy.authorized_by_user_id, "monitor")
    if profile.status != "active" or not profile.topic_ids_json or policy.profile_fingerprint != profile_key(parent, profile):
        fail("Monitoring settings changed. Review and enable automatic research again.", 409)
    if policy.include_page_changes and parent.monitoring_audience == "team":
        fail("Workspace page research is unavailable in a members-only dossier.", 409)
    return profile


def trigger_for(session, run):
    return session.scalar(select(Trigger).where(Trigger.investigation_id == run.id))


def current_source(session, parent, profile, match_id, expected=None):
    match = session.scalar(select(TopicEventMatch).join(RegulatoryEventState,
        (RegulatoryEventState.event_id == TopicEventMatch.event_id)
        & (RegulatoryEventState.organization_id == TopicEventMatch.organization_id))
        .where(TopicEventMatch.id == match_id, TopicEventMatch.topic_id.in_(profile.topic_ids_json)))
    if not match:
        fail("The monitoring signal is no longer admitted to this dossier.", 409)
    described = topic_matching.describe_matches(session, [match])
    if (not described or not described[0]["is_current"] or not match.evaluation_fingerprint
            or (expected and match.evaluation_fingerprint != expected)):
        fail("The monitoring signal changed or is no longer current.", 409)
    value = described[0]
    if value["decision_is_current"] and value["decision"] in {"rejected", "muted"}:
        fail("This monitoring signal was rejected or muted.", 409)
    evidence = value["evidence"]
    url = evidence.get("source_url", "")
    review = current_reviews(session, parent.id).get(url)
    if review and review.data_json["decision"] == "exclude":
        fail("This source is excluded from dossier research.", 409)
    # Deterministic, bounded metadata capture. No source fetching and no private
    # query generation; quotations must match this exact retained excerpt.
    text = json.dumps({key: evidence.get(key) for key in (
        "work_title", "expression_title", "event_type", "detected_at", "source_evidence")},
        ensure_ascii=False, sort_keys=True)[:12000]
    return {"key": match.id + ":" + match.evaluation_fingerprint,
        "kind": "official_event_metadata", "title": str(evidence.get("work_title") or "Monitoring signal")[:700],
        "url": url, "text": text, "date": value["matched_at"],
        "sha256": hashlib.sha256(text.encode()).hexdigest()}


def trigger_source(session, parent, profile, policy, trigger):
    if trigger.source_kind == "watched_page":
        if not policy.include_page_changes:
            fail("The saved research policy does not authorize page text analysis.", 409)
        return product_page_research.capture(session, parent, trigger.source_identifier,
            trigger.source_revision, retained=trigger.source_json.get("page"))
    return current_source(session, parent, profile, trigger.match_id, trigger.evaluation_fingerprint)


def worker_access(session, run, trigger):
    parent = session.get(ProductDossier, run.dossier_id)
    policy = session.get(Policy, trigger.policy_id)
    if (not policy or trigger.policy_revision != policy.revision or run.publication_id
            or run.trigger_entry_id or run.external_discovery):
        fail("This standing research authorization changed. Start from the current policy.", 409)
    profile = authority(session, policy, parent)
    source = trigger_source(session, parent, profile, policy, trigger)
    if source != trigger.source_json:
        fail("The captured monitoring evidence changed.", 409)
    return parent


def seed(session, run, parent, settings, trigger):
    source, _ = snapshot(session, run, trigger.source_json)
    page = trigger.source_kind == "watched_page"
    session.add(InvestigationBranch(**scope(run), query="New monitoring evidence", phase="extract",
        reason="A linked page has a new retained text version." if page else "A new, current signal matched this dossier's enabled monitoring topics.",
        checkpoint={"saved": True, "source_ids": [source.id], "extract_index": 0}))
    run.status = "running"
    plan(session, run, "Investigate the exact saved monitoring signal, then compare independently extracted findings.",
        trigger={"monitoring_trigger_id": trigger.id, "source_id": source.id})
    event(session, run, "monitoring_update", trigger_id=trigger.id, source_id=source.id,
        policy_revision=trigger.policy_revision, source_kind=trigger.source_kind,
        disclosure=DISCLOSURE + (" " + PAGE_DISCLOSURE if page else ""))


def fence(session, policy, reason):
    for trigger in session.scalars(select(Trigger).where(Trigger.policy_id == policy.id, Trigger.state == "pending")):
        trigger.state, trigger.reason = "skipped", reason
    runs = session.scalars(select(Investigation).join(Trigger, Trigger.investigation_id == Investigation.id)
        .where(Trigger.policy_id == policy.id, Investigation.status.in_(ACTIVE | {"paused"})))
    for run in runs:
        if run.job_id:
            jobs.cancel(session, run.job_id)
        run.generation += 1
        run.status, run.stop_reason = "cancelled", reason
        event(session, run, "investigation_cancelled", reason=reason)


def history(policy, action, reason):
    policy.updated_at = utcnow()
    policy.reason = reason
    policy.history = [*policy.history[-99:], {"revision": policy.revision, "action": action,
        "at": iso(policy.updated_at), "daily_limit": policy.daily_limit,
        "include_page_changes": policy.include_page_changes, "reason": reason}]


def used_today(policy):
    return policy.budget_used if policy.budget_day == utcnow().date().isoformat() else 0


def reserve(policy):
    day = utcnow().date().isoformat()
    if policy.budget_day != day:
        policy.budget_day, policy.budget_used = day, 0
    if policy.budget_used >= policy.daily_limit:
        fail("The daily automatic-research limit has been reached. Pending signals wait until the next UTC day.", 409)
    policy.budget_used += 1


def retry_authority(session, run):
    trigger = trigger_for(session, run)
    if trigger:
        worker_access(session, run, trigger)
        reserve(session.get(Policy, trigger.policy_id))


def check_policy(session, policy, now):
    """Called under the organization lock; receipts, jobs and capacity commit together."""
    parent = session.get(ProductDossier, policy.dossier_id)
    policy.checked_at, policy.next_check_at = now, now + timedelta(minutes=1)
    try:
        profile = authority(session, policy, parent)
    except DomainError:
        policy.enabled = False
        policy.revision += 1
        reason = "Automatic research paused: monitoring settings or the authorizing member's access changed."
        fence(session, policy, reason)
        history(policy, "authority_paused", reason)
        return 0
    recorded = exists(select(Trigger.id).where(Trigger.dossier_id == parent.id,
        Trigger.source_kind == "topic_match", Trigger.source_identifier == TopicEventMatch.id,
        Trigger.source_revision == TopicEventMatch.evaluation_fingerprint))
    candidates = list(session.scalars(select(TopicEventMatch).join(RegulatoryEventState,
        (RegulatoryEventState.event_id == TopicEventMatch.event_id)
        & (RegulatoryEventState.organization_id == TopicEventMatch.organization_id))
        .where(TopicEventMatch.topic_id.in_(profile.topic_ids_json), TopicEventMatch.matched_at > policy.starts_on,
            TopicEventMatch.evaluation_fingerprint.is_not(None), ~recorded)
        .order_by(TopicEventMatch.matched_at, TopicEventMatch.id).limit(100)))
    for match in candidates:
        trigger = Trigger(dossier_id=parent.id, organization_id=parent.organization_id, policy_id=policy.id,
            policy_revision=policy.revision, match_id=match.id, evaluation_fingerprint=match.evaluation_fingerprint,
            source_kind="topic_match", source_identifier=match.id, source_revision=match.evaluation_fingerprint,
            matched_at=match.matched_at)
        session.add(trigger)
        try:
            trigger.source_json = current_source(session, parent, profile, match.id, match.evaluation_fingerprint)
        except DomainError as exc:
            trigger.state, trigger.reason = "skipped", exc.message
    if policy.include_page_changes:
        product_page_research.collect(session, parent, policy)
    session.flush()
    if session.scalar(select(Investigation.id).where(Investigation.dossier_id == parent.id,
            Investigation.status.in_(ACTIVE)).limit(1)):
        policy.reason = "Waiting for the active dossier investigation to finish."
        return 0
    if used_today(policy) >= policy.daily_limit:
        policy.reason = "Daily research limit reached. New signals remain queued until the next UTC day."
        return 0
    pending = list(session.scalars(select(Trigger).where(Trigger.policy_id == policy.id, Trigger.state == "pending")
        .order_by(Trigger.matched_at, Trigger.created_at, Trigger.id).limit(100)))
    for trigger in pending:
        try:
            if trigger.policy_revision != policy.revision:
                fail("The research policy changed after this signal was recorded.", 409)
            source = trigger_source(session, parent, profile, policy, trigger)
            if source != trigger.source_json:
                fail("The captured monitoring evidence changed.", 409)
        except DomainError as exc:
            trigger.state, trigger.reason = "skipped", exc.message
            continue
        reserve(policy)
        run = Investigation(dossier_id=parent.id, organization_id=parent.organization_id,
            request_key=str(uuid4()), question=QUESTION, external_discovery=False,
            created_by_user_id=policy.authorized_by_user_id, actor_user_id=policy.authorized_by_user_id)
        session.add(run)
        session.flush()
        trigger.investigation_id, trigger.state, trigger.started_at = run.id, "started", now
        trigger.reason = "New monitoring evidence started a private investigation under the saved policy."
        enqueue(session, run)
        event(session, run, "investigation_queued", trigger_id=trigger.id, question=run.question, disclosure=DISCLOSURE)
        policy.reason = "New monitoring evidence is being investigated."
        return 1
    policy.reason = "No new investigation started in this check. Further saved signals are checked in later batches."
    return 0


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
            started += check_policy(session, policy, now)
            checked += 1
            session.commit()
    return {"checked": checked, "started": started}


def trigger_payload(session, trigger):
    run = session.get(Investigation, trigger.investigation_id) if trigger.investigation_id else None
    source = trigger.source_json
    readable = product_page_research.readable(session, session.get(ProductDossier, trigger.dossier_id), source)
    if not readable:
        source = {}
    return {"id": trigger.id, "match_id": trigger.match_id, "evaluation_fingerprint": trigger.evaluation_fingerprint,
        "source_kind": trigger.source_kind, "source_identifier": trigger.source_identifier,
        "source_revision": trigger.source_revision, "page": product_page_research.page_payload(source),
        "policy_revision": trigger.policy_revision, "matched_at": iso(trigger.matched_at),
        "created_at": iso(trigger.created_at), "state": trigger.state,
        "reason": trigger.reason if readable else "The retained page evidence is no longer accessible in this dossier.",
        "source": {k: source.get(k, "") for k in ("title", "url", "sha256")},
        "investigation": summary(run) if run and readable else None}


def payload(session, parent, policy, can_manage, offset=0):
    query = select(Trigger).where(Trigger.dossier_id == parent.id)
    return {"dossier_id": parent.id, "can_manage": can_manage, "policy": {
        "enabled": policy.enabled if policy else False, "revision": policy.revision if policy else 0,
        "include_page_changes": policy.include_page_changes if policy else False,
        "page_readiness": product_page_research.readiness(session, parent), "page_disclosure": PAGE_DISCLOSURE,
        "daily_limit": policy.daily_limit if policy else 3, "used_today": used_today(policy) if policy else 0,
        "starts_on": iso(policy.starts_on) if policy else None,
        "checked_at": iso(policy.checked_at) if policy and policy.checked_at else None,
        "reason": policy.reason if policy else "Automatic research is off.", "history": policy.history if policy else [],
        "disclosure": DISCLOSURE},
        "items": [trigger_payload(session, t) for t in session.scalars(query.order_by(Trigger.created_at.desc(),
            Trigger.id).offset(offset).limit(20))],
        "total": session.scalar(select(func.count()).select_from(query.subquery())), "offset": offset, "page_size": 20}
