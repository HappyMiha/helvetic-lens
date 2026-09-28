"""Dossier-scoped coordinator state, capabilities and evidence validation."""
import hashlib
from types import SimpleNamespace
from typing import Literal

from pydantic import Field
from sqlalchemy import select, update

from . import domain_packs, jobs, legal_profiles
from .db import utcnow
from .product_api import dossier, fail, iso
from .product_investigation_models import (
    ClaimEvidence,
    DossierClaim,
    DossierEntity,
    DossierRelationship,
    Investigation,
    InvestigationBranch,
    InvestigationEvent,
    InvestigationPlan,
    InvestigationSource,
)
from .product_provenance import principal

TYPE = "product_investigation"
ACTIVE = {"queued", "running"}
MAX_BRANCHES = 3
MAX_SOURCES = 3


class Citation(legal_profiles.Input):
    quote: str = Field(min_length=10, max_length=600)
    locator: str = Field(min_length=1, max_length=100)


class Assertion(Citation):
    statement: str = Field(min_length=5, max_length=700)
    existing_claim_id: str | None = Field(default=None, max_length=36)
    relation: Literal["SUPPORTS", "CONTRADICTS", "CONTEXT"]


class Entity(Citation):
    name: str = Field(min_length=2, max_length=100)
    kind: str = Field(min_length=2, max_length=80)
    investigate: bool = False


class Relationship(Citation):
    subject: str = Field(min_length=2, max_length=100)
    object: str = Field(min_length=2, max_length=100)
    predicate: str = Field(min_length=2, max_length=120)


class Extraction(legal_profiles.Input):
    claims: list[Assertion] = Field(default_factory=list, max_length=6)
    entities: list[Entity] = Field(default_factory=list, max_length=5)
    relationships: list[Relationship] = Field(default_factory=list, max_length=5)


def scope(run):
    return {"investigation_id": run.id, "dossier_id": run.dossier_id, "organization_id": run.organization_id}


def rows(session, model, run):
    return list(session.scalars(select(model).where(model.investigation_id == run.id)
        .order_by(model.created_at, model.id)))


def access(session, identity, product, dossier_id, *, write=False, action="edit"):
    # Native account/session + current membership, then draft visibility.
    session.connection()
    from .membership_locks import lock_organization
    from .product_access import require

    if write:
        lock_organization(session, session.info["organization_id"])
    principal(session, identity, utcnow(), lock=write, dossier_id=dossier_id)
    row, profile = dossier(session, product, dossier_id, identity.user_id)
    require(session, row, profile, identity.user_id, action if write else "read")
    return row


def worker_access(session, run, product):
    from .product_web_research import trigger_for as web_trigger_for
    from .product_web_research import worker_access as web_access

    web_trigger = web_trigger_for(session, run)
    if web_trigger:
        return web_access(session, run, web_trigger)
    from .product_monitoring_research import trigger_for
    from .product_monitoring_research import worker_access as monitoring_access

    trigger = trigger_for(session, run)
    if trigger:
        return monitoring_access(session, run, trigger)
    if run.publication_id:
        from .product_public_research import worker_access as public_worker_access

        return public_worker_access(session, run)
    if not run.actor_user_id or not run.session_id:
        fail("An active member must resume this investigation.", 403)
    identity = SimpleNamespace(user_id=run.actor_user_id, session_id=run.session_id,
                               organization_id=run.session_organization_id or run.organization_id)
    return access(session, identity, product, run.dossier_id, write=True, action="contribute" if run.trigger_entry_id else "edit")


def record(session, identity, product, dossier_id, identifier, *, write=False):
    access(session, identity, product, dossier_id)
    run = session.get(Investigation, identifier)
    if not run or run.dossier_id != dossier_id:
        fail("Investigation not found.", 404, "not_found")
    if not page_result_visible(session, run):
        fail("This investigation's retained page evidence is no longer accessible.", 404)
    if write:
        if run.publication_id:
            from .product_models import ProductPublication
            from .product_public_research import public_run

            public_run(session, session.get(ProductPublication, run.publication_id), run.id)
        action = "contribute" if run.trigger_entry_id and run.created_by_user_id == identity.user_id else "edit"
        access(session, identity, product, dossier_id, write=True, action=action)
    return run


def event(session, run, kind, **detail):
    run.event_sequence += 1
    run.revision += 1
    run.updated_at = utcnow()
    session.add(InvestigationEvent(**scope(run), sequence=run.event_sequence, kind=kind, detail=detail))


def capabilities(settings, product):
    search = bool(settings.search1api_api_key.get_secret_value())
    pack = domain_packs.for_product(product)
    return [
        {"id": "public_web", "available": search, "description": "Search1API Google/Bing discovery across the public web"},
        {"id": "scientific_literature", "available": pack.scientific_literature, "description": "Europe PMC literature discovery"},
        {"id": "source_reader", "available": True, "description": "Permitted anonymous HTML, text and PDF excerpts; robots and size limits apply"},
        {"id": "saved_evidence", "available": True, "description": "Current dossier contributions and saved monitored extracts"},
        {"id": "evidence_analysis", "available": settings.model_configured, "description": "Configured workspace model; source-grounded proposals, availability checked during execution"},
        {"id": "evidence_comparison", "available": settings.model_configured, "description": "Compare independently captured findings with earlier claims in the same dossier audience"},
        {"id": "authenticated_sources", "available": False, "description": "No authenticated archive or paid database connector attached"},
        {"id": "ocr", "available": False, "description": "Scanned-image OCR is not available in this workflow"},
    ]


def plan(session, run, reason, *, trigger=None):
    session.flush()
    run.plan_version += 1
    document = {"branches": [{"id": b.id, "query": b.query, "phase": b.phase, "status": b.status}
                             for b in rows(session, InvestigationBranch, run)],
                "trigger": trigger, "budgets": {"public_branches": MAX_BRANCHES if run.external_discovery else 0,
                    "sources_per_branch": MAX_SOURCES, "saved_snapshots": MAX_SOURCES,
                    "comparison_requests": 1, "claims_per_comparison_side": 24},
                "stop_rule": "Stop when pending branches finish or the explicit evidence/query budgets are reached."}
    from .product_web_research import trigger_for as web_trigger_for

    if web_trigger_for(session, run):
        document["budgets"].update(public_branches=1, saved_snapshots=0)
    session.add(InvestigationPlan(**scope(run), version=run.plan_version, reason=reason, document=document))
    event(session, run, "plan_updated", version=run.plan_version, reason=reason, trigger=trigger)


def enqueue(session, run):
    job, _ = jobs.enqueue(session, job_type=TYPE, target_type=TYPE, target_id=run.id,
        queue="ai_background", idempotency_key=f"investigation:{run.id}:{run.generation}",
        payload={}, max_attempts=3, organization_id=run.organization_id)
    run.job_id = job.id
    return job


def snapshot(session, run, item, *, public=False, captured=False):
    # Search snippets never become evidence. Only verified reader excerpts or
    # access-scoped saved-text snapshots enter the claim ledger.
    data = item if public or captured else {"status": "complete", "sha256": item["sha256"],
        "excerpts": [{"text": item["text"], "passage": "saved-excerpt"}],
        "origin_key": item["key"], "captured_from": item["kind"], "origin_date": item["date"],
        "scope": "Bounded snapshot of saved dossier material; original author text is not a machine finding."}
    if item.get("page"):
        # Only the new-source excerpt enters extraction. The earlier text is
        # inspectable through the private trigger, not supplied to this model.
        data["saved_page"] = {key: item["page"][key] for key in (
            "document_id", "version_id", "revision", "content_hash", "excerpt_start", "partial")}
    key = hashlib.sha256((item.get("url", "") + item.get("key", "") + data["sha256"]).encode()).hexdigest()
    old = session.scalar(select(InvestigationSource).where(InvestigationSource.investigation_id == run.id,
                                                          InvestigationSource.source_key == key))
    if old:
        return old, False
    row = InvestigationSource(**scope(run), source_key=key, kind="public_source" if public else item["kind"],
        title=item.get("title", "Source")[:700], url=item.get("url", ""), sha256=data["sha256"], snapshot=data)
    session.add(row)
    session.flush()
    event(session, run, "source_captured", source_id=row.id, title=row.title, source_kind=row.kind)
    return row, True


def citation(source, value):
    passages = {p["passage"]: p["text"] for p in source.snapshot["excerpts"]}
    if value.locator not in passages or value.quote not in passages[value.locator]:
        fail("The proposed citation does not match the captured source.", 422, "invalid_evidence")
    return {"source_id": source.id, "quote": value.quote, "locator": value.locator,
            "sha256": source.sha256, "method": "machine_extraction", "independently_verified": False}


def apply_extraction(session, run, source, data):
    # Validate the entire response before writing any finding. Unknown IDs,
    # invented quotes or relationship endpoints reject the proposal as a whole.
    claims = {v.id: v for v in rows(session, DossierClaim, run)}
    names = {v.name for v in data.entities}
    for value in [*data.claims, *data.entities, *data.relationships]:
        citation(source, value)
    for value in data.claims:
        if value.existing_claim_id and value.existing_claim_id not in claims:
            fail("The proposed claim does not belong to this investigation.", 422, "invalid_evidence")
        if value.existing_claim_id and value.statement != claims[value.existing_claim_id].statement:
            fail("A citation cannot silently rewrite a stored claim.", 422, "invalid_evidence")
    for value in data.entities:
        if value.name not in value.quote:
            fail("The entity name is not present in its source quote.", 422, "invalid_evidence")
    for value in data.relationships:
        if value.subject not in names or value.object not in names:
            fail("The relationship must reference entities in this evidence.", 422, "invalid_evidence")
    for value in data.claims:
        claim = claims.get(value.existing_claim_id) or next((v for v in claims.values() if v.statement == value.statement), None)
        if not claim:
            claim = DossierClaim(**scope(run), statement=value.statement, status="UNVERIFIED", revision=0, history=[])
            session.add(claim)
            session.flush()
            claims[claim.id] = claim
        before = claim.status
        status = ("CONTESTED" if value.relation == "CONTRADICTS" else
                  "SUPPORTED" if value.relation == "SUPPORTS" and before in {"UNVERIFIED", "HYPOTHESIS"} else before)
        claim.revision += 1
        claim.status = status
        claim.history = [*claim.history, {"revision": claim.revision, "from": before, "to": status,
            "source_id": source.id, "relation": value.relation, "at": iso(utcnow()),
            "basis": "Machine-linked source evidence; independent factual verification remains open."}]
        session.add(ClaimEvidence(**scope(run), claim_id=claim.id, source_id=source.id,
            relation=value.relation, quote=value.quote, locator=value.locator))
        event(session, run, "claim_updated", claim_id=claim.id, status=status, source_id=source.id)
    entities = {}
    for value in data.entities:
        entity = DossierEntity(**scope(run), name=value.name, kind=value.kind,
            evidence={**citation(source, value), "identity": "unresolved_source_mention"})
        session.add(entity)
        session.flush()
        entities[value.name] = entity
        event(session, run, "entity_discovered", entity_id=entity.id, name=entity.name, source_id=source.id)
        if value.investigate and run.external_discovery and source.kind == "public_source" and source.snapshot.get("allow_discovery", True):
            branches = rows(session, InvestigationBranch, run)
            public = [b for b in branches if not b.checkpoint.get("saved")]
            # Only an exact public-source entity name may extend the user's
            # disclosed question. No private context or model-written query leaks.
            query = (run.question[:190] + " " + value.name)[:300]
            if len(public) < MAX_BRANCHES and not any(b.query.casefold() == query.casefold() for b in branches):
                reason = f"Investigate a newly observed entity: {value.name}."
                session.add(InvestigationBranch(**scope(run), query=query, reason=reason,
                    checkpoint={"trigger": citation(source, value)}))
                plan(session, run, reason, trigger={"entity_id": entity.id, **citation(source, value)})
    for value in data.relationships:
        session.add(DossierRelationship(**scope(run), subject_id=entities[value.subject].id,
            object_id=entities[value.object].id, predicate=value.predicate, evidence=citation(source, value)))


def summary(run):
    return {"id": run.id, "trigger_entry_id": run.trigger_entry_id, "external_discovery": run.external_discovery, "created_by_user_id": run.created_by_user_id, "question": run.question, "status": run.status, "revision": run.revision,
        "plan_version": run.plan_version, "event_sequence": run.event_sequence,
        "stop_reason": run.stop_reason, "created_at": iso(run.created_at), "updated_at": iso(run.updated_at)}


def page_result_visible(session, run):
    from .product_models import ProductDossier
    from .product_monitoring_research import trigger_for
    from .product_page_research import readable

    trigger = trigger_for(session, run)
    return not trigger or trigger.source_kind != "watched_page" or readable(
        session, session.get(ProductDossier, run.dossier_id), trigger.source_json)


def payload(session, run):
    from .product_claim_evolution import projection
    from .product_contributions import original
    from .product_monitoring_research import trigger_for, trigger_payload

    trigger = trigger_for(session, run)
    if not page_result_visible(session, run):
        return {**summary(run), "evidence_unavailable": True, "monitoring_trigger": trigger_payload(session, trigger),
            "original": None, "evidence_basis": "The retained page evidence is no longer accessible.", "coverage": "Unavailable",
            **{key: [] for key in ("plans", "branches", "sources", "claims", "evidence", "entities", "relationships", "activity")}}
    from .product_web_research import trigger_for as web_trigger_for

    web_trigger = web_trigger_for(session, run)
    changes = projection(session, run)
    return {**summary(run), "web_research_trigger": {
        "id": web_trigger.id, "policy_revision": web_trigger.policy_revision,
        "scheduled_for": iso(web_trigger.scheduled_for)} if web_trigger else None, "monitoring_trigger": trigger_payload(session, trigger) if trigger else None,
        "original": original(session, run.trigger_entry_id),
        "plans": [{"id": p.id, "version": p.version, "reason": p.reason, "document": p.document,
                   "created_at": iso(p.created_at)} for p in rows(session, InvestigationPlan, run)],
        "branches": [{"id": b.id, "query": b.query, "status": b.status, "phase": b.phase, "reason": b.reason,
            "steps": b.checkpoint.get("steps", []), "error": b.checkpoint.get("error"),
            "coverage": b.checkpoint.get("coverage")} for b in rows(session, InvestigationBranch, run)],
        "sources": [{"id": s.id, "kind": s.kind, "title": s.title, "url": s.url, "sha256": s.sha256,
                     "snapshot": s.snapshot, "original": original(session, s.snapshot.get("origin_entry_id")), "created_at": iso(s.created_at)} for s in rows(session, InvestigationSource, run)],
        "claims": [{"id": c.id, "statement": c.statement, "status": c.status, "revision": c.revision,
                    "history": c.history, "later_evidence": changes.get(c.id)} for c in rows(session, DossierClaim, run)],
        "evidence": [{"id": e.id, "claim_id": e.claim_id, "source_id": e.source_id, "relation": e.relation,
                      "quote": e.quote, "locator": e.locator} for e in rows(session, ClaimEvidence, run)],
        "entities": [{"id": e.id, "name": e.name, "kind": e.kind, "evidence": e.evidence}
                     for e in rows(session, DossierEntity, run)],
        "relationships": [{"id": e.id, "subject_id": e.subject_id, "object_id": e.object_id,
            "predicate": e.predicate, "evidence": e.evidence} for e in rows(session, DossierRelationship, run)],
        "activity": [{"sequence": e.sequence, "kind": e.kind, "detail": e.detail, "created_at": iso(e.created_at)}
                     for e in rows(session, InvestigationEvent, run)],
        "evidence_basis": "Supported means the linked source supports the statement, not independently established truth. "
            "Machine extraction may be wrong. Contradictions remain visible. Entity mentions are not resolved identities.",
        "coverage": "Bounded investigation of accessible sources, not exhaustive internet coverage. "
            "Submitted text and supported file excerpts can be analysed; OCR and authenticated archives are unavailable. "
            "Contribution reviews never perform public discovery; source reading and file extraction have explicit bounds."}


def worker_exhausted(session, job):
    """Fence the pause to this job; recovery holds job locks, not dossier locks.

    Do not append an event under a different lock order. Atomic revision/status
    changes are observable through the normal stream checkpoint and stored job.
    The next resume has its own regular dossier-locked activity record.
    """
    session.execute(update(Investigation).where(Investigation.id == job.target_id,
        Investigation.organization_id == job.organization_id, Investigation.job_id == job.id,
        Investigation.status.in_(ACTIVE)).values(status="paused",
            revision=Investigation.revision + 1, updated_at=utcnow(),
            stop_reason="The worker recovery limit was reached. Resume to continue from saved checkpoints.")
        .execution_options(synchronize_session=False))
