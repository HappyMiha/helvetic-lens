"""Admit every feed version to each linked dossier's ordinary research engine."""
from copy import deepcopy
from uuid import uuid4

from sqlalchemy import exists, select

from .config import DomainError
from .db import utcnow
from .feed_models import Feed, FeedDossierLink, FeedImport, FeedUpdate
from .feed_operations import require_owner
from .legal_profile_models import LegalMonitoringProfile
from .membership_locks import lock_organization
from .product_access import require
from .product_api import fail
from .product_investigation_models import Investigation, InvestigationBranch
from .product_investigations import ACTIVE, enqueue, event, scope, snapshot
from .product_models import ProductDossier

CONTRACT = "feed-dossier-history/v1"


def authority(session, link):
    if not link or link.status != "active" or not link.created_by_user_id:
        fail("This feed is no longer linked to the dossier.", 403, "feed_link_changed")
    feed = require_owner(session, session.get(Feed, link.feed_id), link.created_by_user_id, write=True)
    parent = session.get(ProductDossier, link.dossier_id)
    if not parent or parent.organization_id != feed.organization_id:
        fail("Linked dossier not found.", 404, "not_found")
    profile = session.get(LegalMonitoringProfile, parent.profile_id)
    require(session, parent, profile, link.created_by_user_id, "edit")
    return feed, parent, profile


def attach_history(session, link):
    """No first-N cutoff: persist one receipt for every version absent from this link."""
    authority(session, link)
    admitted = exists(select(FeedImport.id).where(FeedImport.link_id == link.id,
        FeedImport.update_id == FeedUpdate.id))
    for row in session.scalars(select(FeedUpdate).where(FeedUpdate.feed_id == link.feed_id, ~admitted)
            .order_by(FeedUpdate.sequence).execution_options(yield_per=100)):
        session.add(FeedImport(organization_id=link.organization_id, link_id=link.id, update_id=row.id))
    session.flush()


def detach_work(session, link):
    from . import jobs

    for run in session.scalars(select(Investigation).where(
            Investigation.research_state["feed_origin"]["link_id"].as_string() == link.id)):
        if run.status in {*ACTIVE, "paused"}:
            run.status, run.stop_reason = "cancelled", "The source feed was detached. Captured history is retained."
            run.revision += 1
            if run.job_id:
                jobs.cancel(session, run.job_id)
            event(session, run, "investigation_cancelled", reason=run.stop_reason)


def recover_history(session, link):
    """An explicit reattachment readmits interrupted versions, retaining old receipts."""
    authority(session, link)
    for item in session.scalars(select(FeedImport).where(FeedImport.link_id == link.id)):
        run = session.get(Investigation, item.investigation_id) if item.investigation_id else None
        if run and run.status != "completed":
            item.status, item.investigation_id = "pending", None


def origin(run):
    value = (run.research_state or {}).get("feed_origin")
    return value if isinstance(value, dict) and value.get("contract") == CONTRACT else None


def worker_access(session, run):
    saved = origin(run)
    link = session.get(FeedDossierLink, saved["link_id"], populate_existing=True)
    _, parent, _ = authority(session, link)
    if (link.revision != saved["link_revision"] or parent.id != run.dossier_id
            or link.organization_id != run.organization_id or link.created_by_user_id != run.actor_user_id):
        fail("The feed link changed. Retained research remains available; this work cannot continue.", 403, "feed_link_changed")
    return parent


def previous_public(session, dossier_id):
    return session.scalar(select(Investigation).where(Investigation.dossier_id == dossier_id,
        Investigation.external_discovery.is_(True), Investigation.trigger_entry_id.is_(None),
        Investigation.publication_id.is_(None)).order_by(Investigation.created_at.desc(), Investigation.id.desc()).limit(1))


def start_pending(session, link, *, force=False, public_question=None):
    from . import product_exploration as exploration
    from .product_research_admission import policy

    feed, parent, profile = authority(session, link)
    if session.scalar(select(Investigation.id).where(Investigation.dossier_id == parent.id,
            Investigation.status.in_(ACTIVE)).limit(1)):
        return None
    if session.scalar(select(Investigation.id).where(
            Investigation.research_state["feed_origin"]["link_id"].as_string() == link.id,
            Investigation.research_state["feed_origin"]["link_revision"].as_integer() == link.revision,
            Investigation.status.in_({"failed", "paused", "cancelled"})).limit(1)):
        return None  # Explicit recovery comes before newer observations; never override a user's pause.
    pending = select(FeedImport).where(FeedImport.link_id == link.id,
        FeedImport.status == "pending", FeedImport.investigation_id.is_(None))
    if not force and not session.scalar(pending.limit(1)):
        return None
    previous = previous_public(session, parent.id)
    question = public_question or (previous.question if previous else link.public_question)
    run = Investigation(dossier_id=parent.id, organization_id=parent.organization_id,
        request_key=str(uuid4()), question=question[:300], actor_user_id=link.created_by_user_id,
        created_by_user_id=link.created_by_user_id, external_discovery=True,
        research_state={**exploration.initial(previous={"investigation_id": previous.id, "origin": CONTRACT} if previous else None), "admission": policy(parent.id),
            "feed_origin": {"contract": CONTRACT, "link_id": link.id, "link_revision": link.revision,
                "feed_id": feed.id, "previous_investigation_id": previous.id if previous else None}})
    session.add(run)
    session.flush()
    count = 0
    for item in session.scalars(pending.execution_options(yield_per=100)):
        item.investigation_id = run.id
        count += 1
    enqueue(session, run)
    event(session, run, "investigation_queued", origin=CONTRACT, feed_id=feed.id,
        history_records=count, question=run.question,
        disclosure="Read all admitted feed versions and assess their relevance to this dossier's question. Independent research remains available.")
    return run


def retry_authority(session, run, user_id):
    if not origin(run):
        return
    worker_access(session, run)
    link = session.get(FeedDossierLink, origin(run)["link_id"])
    require_owner(session, session.get(Feed, link.feed_id), user_id, write=True)
    if link.created_by_user_id != user_id:
        fail("Only the current feed owner can resume linked research.", 403, "feed_access_required")


def retry_link(session, link, run_id, expected_revision):
    from .product_contributions import retry

    _, parent, _ = authority(session, link)
    if session.scalar(select(Investigation.id).where(Investigation.dossier_id == parent.id,
            Investigation.status.in_(ACTIVE)).limit(1)):
        fail("Another investigation is active. Wait for it to finish before retrying.", 409, "feed_research_active")
    run = session.get(Investigation, run_id, populate_existing=True)
    saved = origin(run) if run else None
    if (not saved or saved["link_id"] != link.id or saved["link_revision"] != link.revision
            or run.status not in {"failed", "paused", "cancelled"}):
        fail("This feed research is no longer available to retry.", 409, "feed_research_unavailable")
    if run.revision != expected_revision:
        fail("The research changed. Refresh before retrying.", 409, "feed_research_changed")
    worker_access(session, run)
    if run.status == "failed":
        retry(session, run)
    run.generation += 1
    run.status, run.stop_reason = "queued", ""
    enqueue(session, run)
    event(session, run, "investigation_retry", origin=CONTRACT, status=run.status)
    return run


def seed(session, run, parent, settings):
    from . import product_iterative_research as research

    worker_access(session, run)
    saved = origin(run)
    link = session.get(FeedDossierLink, saved["link_id"])
    from . import feed_assessments
    from .feed_intelligence import spec
    feed = session.get(Feed, link.feed_id)
    specification = spec(session, feed)
    if not run.plan_version:
        from . import research_recall
        research.seed(session, run)
        research_recall.seed(session, run, parent.product)
    imports = session.execute(select(FeedImport, FeedUpdate).join(FeedUpdate, FeedUpdate.id == FeedImport.update_id)
        .where(FeedImport.link_id == link.id, FeedImport.investigation_id == run.id)
        .order_by(FeedUpdate.sequence).execution_options(yield_per=100))
    for admitted, update in imports:
        # Each receipt owns exactly one branch. A retry cannot duplicate earlier ones.
        if admitted.status == "seeded":
            continue
        original = update.snapshot_json.get("retained_document")
        provenance = {"feed_id": link.feed_id, "feed_update_id": update.id,
            "feed_sequence": update.sequence, "feed_content_hash": update.content_hash,
            "feed_relevance": feed_assessments.projection(feed_assessments.latest_assessment(session, feed, update, specification))}
        if original:
            if original.get("sha256") != update.content_hash:
                fail("The feed original changed after admission.", 409, "feed_original_changed")
            state = {**provenance, "items": [{"url": update.url, "title": update.title}],
                "read_index": 0, "document_reads": {"0": {"sha256": update.content_hash,
                    "retained_document": deepcopy(original)}}}
            phase = "read"
        else:
            # Older/imported observations keep their honest partial text scope.
            # They never fabricate a complete-reading receipt or replace original fetching.
            item = {"kind": "feed_source_text", "title": update.title, "url": update.url,
                "sha256": update.content_hash, "key": update.id, "date": update.published_at,
                "text": update.source_text}
            source, _ = snapshot(session, run, item)
            source.snapshot = {**source.snapshot, **provenance,
                "scope": "Saved feed text. Full-document reading was not recorded for this observation."}
            state = {**provenance, "saved": True, "source_ids": [source.id], "extract_index": 0}
            phase = "extract"
        session.add(InvestigationBranch(**scope(run), query=f"Feed source: {update.title}"[:300], phase=phase,
            reason="Read this immutable feed version against the dossier question, retaining earlier and changed versions.",
            checkpoint=state))
        admitted.status = "seeded"
        link.cursor_sequence = max(link.cursor_sequence, update.sequence)
    link.updated_at = utcnow()


def enqueue_pending(database, settings):
    with database.session(include_all_organizations=True) as session:
        links = list(session.execute(select(FeedDossierLink.id, FeedDossierLink.organization_id)
            .where(FeedDossierLink.status == "active", exists(select(FeedImport.id).where(
                FeedImport.link_id == FeedDossierLink.id, FeedImport.status == "pending",
                FeedImport.investigation_id.is_(None))))))
    started = 0
    for identifier, organization in links:
        with database.organization_context(organization), database.session() as session:
            lock_organization(session, organization)
            try:
                run = start_pending(session, session.get(FeedDossierLink, identifier))
                started += int(run is not None)
                session.commit()
            except DomainError:
                session.rollback()  # Current access is required again on every attempt.
    return {"feed_investigations_started": started}
