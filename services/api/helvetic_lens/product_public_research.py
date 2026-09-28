"""Public consent scope for the shared durable dossier coordinator.

This module never reads private dossier entries as evidence. Native source
exclusions are consulted only as an access gate, never exposed as public text.
"""
import hashlib
from datetime import UTC, timedelta
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import and_, exists, func, select
from sqlalchemy.orm import aliased

from . import jobs
from .db import utcnow
from .models import OrganizationMembership, User, UserSession
from .product_api import fail, iso
from .product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from .product_investigations import ACTIVE, MAX_SOURCES, enqueue, event, plan, scope, snapshot
from .product_models import DossierEntry, ProductPublication, PublicContribution


def sources_visible(run=Investigation):
    """The same latest source exclusions apply to every derived evidence reader."""
    from .product_page_research import results_visible, retained_visible

    source = aliased(InvestigationSource)
    review, newer = aliased(DossierEntry), aliased(DossierEntry)
    has_newer = exists(select(newer.id).where(newer.dossier_id == review.dossier_id,
        newer.kind == "source_review", newer.url == review.url,
        (newer.data_json["revision"].as_integer() > review.data_json["revision"].as_integer()) |
        ((newer.data_json["revision"].as_integer() == review.data_json["revision"].as_integer()) & (newer.id > review.id))))
    excluded = exists(select(source.id).join(review, and_(review.dossier_id == source.dossier_id,
        review.url == source.url, review.kind == "source_review"))
        .where(source.investigation_id == run.id, review.data_json["decision"].as_string() == "exclude", ~has_newer))
    page = source.snapshot["saved_page"]
    unavailable_page = exists(select(source.id).where(source.investigation_id == run.id,
        page["version_id"].as_string().is_not(None), ~retained_visible(source.dossier_id, source.organization_id,
            page["document_id"].as_string(), page["version_id"].as_string())))
    return and_(~excluded, ~unavailable_page, results_visible(run))


def eligible(run=Investigation):
    """SQL predicate: apply before anonymous counts, pagination and search."""
    visible = exists(select(PublicContribution.id).join(ProductPublication,
        ProductPublication.id == PublicContribution.publication_id).join(User, User.id == PublicContribution.author_user_id)
        .where(PublicContribution.id == run.public_contribution_id,
            PublicContribution.revision == run.public_contribution_revision,
            PublicContribution.status == "visible", ProductPublication.id == run.publication_id,
            ProductPublication.revision == run.publication_revision,
            ProductPublication.status == "published", ProductPublication.living_research.is_(True),
            User.active.is_(True), User.email_verified_at.is_not(None)))
    return and_(run.publication_id.is_not(None), visible, sources_visible(run))


def public_run(session, publication, identifier):
    run = session.scalar(select(Investigation).where(Investigation.id == identifier,
        Investigation.publication_id == publication.id, eligible()).execution_options(populate_existing=True))
    if not run:
        fail("This public investigation is not available.", 404)
    return run


def public_identity(session, identity, *, lock=False):
    """Check exactly the original login binding, without granting host access."""
    query = select(User).where(User.id == identity.user_id).execution_options(populate_existing=True)
    user = session.scalar(query.with_for_update() if lock else query)
    login_query = select(UserSession).where(UserSession.id == identity.session_id)
    member_query = select(OrganizationMembership).where(OrganizationMembership.user_id == identity.user_id,
        OrganizationMembership.organization_id == identity.organization_id)
    login = session.scalar((login_query.with_for_update() if lock else login_query)
        .execution_options(include_all_organizations=True, populate_existing=True))
    member = session.scalar((member_query.with_for_update() if lock else member_query)
        .execution_options(include_all_organizations=True, populate_existing=True))
    if (not user or not user.active or not user.email_verified_at or not member or not login
            or login.user_id != user.id or login.organization_id != identity.organization_id
            or login.revoked_at or login.expires_at.replace(tzinfo=UTC) <= utcnow()):
        fail("A current verified account is required for public research.", 403)
    return user


def can_control(session, run, identity):
    from .legal_profile_models import LegalMonitoringProfile
    from .product_access import RANK, role
    from .product_models import ProductDossier

    if identity.user_id == run.created_by_user_id:
        return True
    parent = session.get(ProductDossier, run.dossier_id)
    profile = session.get(LegalMonitoringProfile, parent.profile_id) if parent else None
    return bool(parent and RANK.get(role(session, parent, profile, identity.user_id), -1) >= 2)


def worker_access(session, run):
    publication = session.get(ProductPublication, run.publication_id, populate_existing=True)
    if not publication:
        fail("Public research is no longer available.", 403)
    public_run(session, publication, run.id)
    identity = SimpleNamespace(user_id=run.actor_user_id, session_id=run.session_id,
                               organization_id=run.session_organization_id)
    public_identity(session, identity, lock=True)
    if not can_control(session, run, identity):
        fail("The research editor's access changed.", 403)


def queue(session, publication, contribution, identity, *, external=False):
    if not publication.living_research or contribution.status != "visible":
        return None
    public_identity(session, identity)
    session.flush()
    count = session.scalar(select(func.count()).select_from(Investigation).where(
        Investigation.publication_id == publication.id,
        Investigation.created_by_user_id == identity.user_id,
        Investigation.created_at >= utcnow() - timedelta(days=1)))
    if count >= 30:
        fail("You have reached this dossier's daily limit of 30 public research requests. Try again later.", 429)
    run = Investigation(dossier_id=publication.dossier_id, organization_id=publication.organization_id,
        request_key=str(uuid4()), publication_id=publication.id, publication_revision=publication.revision,
        public_contribution_id=contribution.id, public_contribution_revision=contribution.revision,
        external_discovery=external, question=contribution.body[:300] if external else
            "Review this public contribution against the published dossier and its sources.",
        created_by_user_id=identity.user_id, actor_user_id=identity.user_id,
        session_id=identity.session_id, session_organization_id=identity.organization_id)
    session.add(run)
    session.flush()
    enqueue(session, run)
    event(session, run, "public_contribution_queued", contribution_id=contribution.id,
        reason="Analyse the explicitly public contribution. Private workspace material is excluded.")
    return run


def invalidate(session, publication_id, *, contribution_id=None):
    query = select(Investigation).where(Investigation.publication_id == publication_id,
        Investigation.status.in_(ACTIVE | {"paused"}))
    if contribution_id:
        query = query.where(Investigation.public_contribution_id == contribution_id)
    for run in session.scalars(query):
        if run.job_id:
            jobs.cancel(session, run.job_id)
        run.generation += 1
        run.status, run.stop_reason = "cancelled", "The public contribution or publication changed. Previous research is no longer public."
        event(session, run, "public_scope_changed", reason=run.stop_reason)


def capture_text(session, run, text, title, key, kind):
    return snapshot(session, run, {"kind": kind, "title": title, "key": key,
        "status": "complete", "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "excerpts": [{"passage": f"public-char-{i + 1}", "text": text[i:i + 1200]}
                     for i in range(0, min(len(text), 30000), 1200)],
        "scope": "Exact publicly submitted text; authorship is not independent verification.",
        "allow_discovery": False}, captured=True)[0]


def seed(session, run, parent, settings):
    from .product_investigations import capabilities

    publication = session.get(ProductPublication, run.publication_id)
    item = session.get(PublicContribution, run.public_contribution_id)
    sources = [capture_text(session, run, item.body, "Public contribution by " + item.author_label,
                           item.id, "public_contribution"),
               capture_text(session, run, publication.summary + "\n\n" + publication.body,
                            publication.title, publication.id, "public_publication")]
    session.add(InvestigationBranch(**scope(run), query="Review published material", phase="extract",
        reason="Only the current public publication and this consented contribution enter the analysis.",
        checkpoint={"saved": True, "source_ids": [s.id for s in sources], "extract_index": 0}))
    links = list({s["url"]: s for s in [*item.sources_json, *publication.sources_json]}.values())[:MAX_SOURCES]
    if links:
        session.add(InvestigationBranch(**scope(run), query="Read contributed public sources", phase="read",
            reason="Inspect accessible published links with current access and source exclusions.",
            checkpoint={"items": links}))
    if item.artifact_key:
        session.add(InvestigationBranch(**scope(run), query="Read public original file", phase="read",
            reason="Extract the exact original explicitly submitted for public analysis.",
            checkpoint={"public_file_id": item.id, "items": [{"url": "", "title": item.file_name}]}))
    available = capabilities(settings, parent.product)
    for capability in available:
        if capability["id"] == "saved_evidence":
            capability["description"] = "Only this published revision and explicitly public contribution; private material excluded"
    if run.external_discovery and any(c["available"] and c["id"] in {"public_web", "scientific_literature"} for c in available):
        session.add(InvestigationBranch(**scope(run), query=run.question,
            reason="Discover public sources for the explicitly submitted public question.", checkpoint={}))
    run.status = "running"
    plan(session, run, "Public research of an explicitly published revision and consented contribution.",
         trigger={"contribution_id": item.id})
    event(session, run, "capabilities_resolved", capabilities=available)


def original(session, run):
    item = session.get(PublicContribution, run.public_contribution_id)
    return {"id": item.id, "kind": item.kind, "title": item.file_name or "Public contribution",
        "body": item.body, "url": "", "byte_size": item.byte_size, "sha256": item.sha256,
        "author": item.author_label, "created_at": iso(item.created_at)}


def summary(session, run):
    from .product_investigations import summary as native_summary

    result = native_summary(run)
    result.pop("created_by_user_id", None)
    result.pop("trigger_entry_id", None)
    result.update(publication_id=run.publication_id, contribution_id=run.public_contribution_id)
    return result


def payload(session, run):
    from .product_investigations import payload as native_payload

    result = native_payload(session, run)
    result.pop("created_by_user_id", None)
    result.pop("trigger_entry_id", None)
    result.update(summary(session, run), original=original(session, run))
    for source in result["sources"]:
        source["original"] = result["original"] if source["kind"] == "public_file" else None
        source["snapshot"] = {key: source["snapshot"].get(key) for key in ("scope", "excerpts")}
    result["coverage"] = ("Research of this public revision and contribution only. Private workspace material is excluded. "
        "Discovery is bounded to accessible sources; absence of evidence does not establish a fact. "
        "Updating or withdrawing the publication, contribution or source removes affected findings from public readers.")
    return result
