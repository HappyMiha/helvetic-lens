"""A human ledger on existing findings, bound to retained evidence and comparisons."""
from sqlalchemy import func, or_, select

from .product_api import iso
from .product_claim_evolution import query as comparisons
from .product_claim_interpretation import recorded
from .product_entity_identity import audience, digest
from .product_investigation_models import (
    ClaimChange,
    ClaimEvidence,
    ClaimReview,
    DossierClaim,
    Investigation,
    InvestigationBranch,
    InvestigationSource,
)
from .product_source_authority import options as source_options
from .product_source_authority import recorded as source_recorded
from .research_knowledge import captured_at
from .research_read_view import read_once, read_query

PAGE_SIZE = 10
EVIDENCE_LIMIT = 100
COMPARISON_LIMIT = 20
STATES = {"accepted": "ACCEPTED", "dismissed": "REJECTED", "needs_more_evidence": "UNRESOLVED"}
BOUNDARY = "Human review applies to the displayed captured evidence. It does not verify truth or change the machine evidence assessment. New evidence requires review again."


def claims(dossier_id, publication=None):
    return select(DossierClaim).join(Investigation, Investigation.id == DossierClaim.investigation_id).where(
        DossierClaim.dossier_id == dossier_id, Investigation.status == "completed", audience(Investigation, publication))


def source_query(dossier_id, publication=None):
    return select(InvestigationSource).join(Investigation, Investigation.id == InvestigationSource.investigation_id).where(
        InvestigationSource.dossier_id == dossier_id, Investigation.status == "completed", audience(Investigation, publication))


def evidence(session, row):
    source = session.get(InvestigationSource, row.source_id)
    excerpts = source.snapshot.get("excerpts", [])
    valid = bool(row.quote.strip() and any(part.get("passage") == row.locator and row.quote in part.get("text", "") for part in excerpts))
    saved = source.snapshot.get("saved_page")
    version = None
    if isinstance(saved, dict) and saved.get("version_id"):
        from .models import Version

        retained = session.execute(select(Version.evidence_revision, Version.content_hash)
            .where(Version.id == saved["version_id"])).first()
        version = {"id": saved["version_id"], "recorded_revision": saved.get("revision"),
            "current_revision": retained.evidence_revision if retained else None,
            "content_hash": retained.content_hash if retained else None}
        valid = valid and bool(retained and retained.evidence_revision == saved.get("revision")
            and retained.content_hash == saved.get("content_hash"))
    return {"id": row.id, "claim_id": row.claim_id, "relation": row.relation, "quote": row.quote,
        "locator": row.locator, "valid": valid,
        "source": {"id": source.id, "investigation_id": source.investigation_id, "title": source.title,
            "url": source.url, "kind": source.kind, "sha256": source.sha256, "captured_at": captured_at(source),
            "capture_fingerprint": digest(source.snapshot), "saved_version": version}}


def claim_pin(row):
    return {"id": row.id, "investigation_id": row.investigation_id, "revision": row.revision,
        "statement_hash": digest(row.statement), "evidence_status": row.status}


def provenance(session, run_id):
    routes = []
    for branch in session.scalars(select(InvestigationBranch).where(InvestigationBranch.investigation_id == run_id)
            .order_by(InvestigationBranch.id)):
        for route in branch.checkpoint.get("model_routes", []):
            routes.append({"branch_id": branch.id, **{key: route.get(key) for key in
                ("step_id", "phase", "provider", "model", "version")}})
    return {"investigation_id": run_id, "recorded_model_routes": routes,
        "extraction_version": None, "basis": "Only recorded metadata is retained; missing model or skill versions are unknown."}


def context(session, claim, publication=None):
    own = list(session.scalars(select(ClaimEvidence).where(ClaimEvidence.claim_id == claim.id)
        .order_by(ClaimEvidence.id).limit(EVIDENCE_LIMIT + 1)))
    query = read_query(session, (comparisons, claim.dossier_id,
        publication.id if publication else None, publication.revision if publication else None),
        lambda: comparisons(claim.dossier_id, publication))
    links = list(session.scalars(query.where(
        or_(ClaimChange.previous_claim_id == claim.id, ClaimChange.claim_id == claim.id),
        ClaimChange.investigation_id.in_(select(Investigation.id).where(Investigation.status == "completed")),
        ClaimChange.previous_investigation_id.in_(select(Investigation.id).where(Investigation.status == "completed")))
        .order_by(ClaimChange.id).limit(COMPARISON_LIMIT + 1)))
    complete = len(own) <= EVIDENCE_LIMIT and len(links) <= COMPARISON_LIMIT
    own_evidence = [evidence(session, row) for row in own[:EVIDENCE_LIMIT]]
    related, pins, citations = [], [claim_pin(claim)], list(own_evidence)
    run_ids = {claim.investigation_id}
    for change in links[:COMPARISON_LIMIT]:
        other_id = change.claim_id if change.previous_claim_id == claim.id else change.previous_claim_id
        other = session.get(DossierClaim, other_id)
        paired = [evidence(session, session.get(ClaimEvidence, key)) for key in
            (change.previous_evidence_id, change.evidence_id)]
        related.append({"id": change.id, "kind": change.kind, "status": change.status,
            "revision": change.revision, "direction": "later" if change.previous_claim_id == claim.id else "earlier",
            "claim": {**claim_pin(other), "statement": other.statement}, "evidence": paired})
        pins.append(claim_pin(other))
        citations.extend(paired)
        run_ids.add(other.investigation_id)
    processing = [provenance(session, identifier) for identifier in sorted(run_ids)]
    reviewable = complete and bool(own_evidence) and all(value["valid"] for value in citations)
    snapshot = {"claim": {**claim_pin(claim), "statement": claim.statement}, "evidence": own_evidence,
        "comparisons": related, "provenance": processing,
        "publication_id": publication.id if publication else None,
        "publication_revision": publication.revision if publication else None}
    source_pins = {value["source"]["id"]: {key: value["source"][key] for key in
        ("id", "investigation_id", "sha256", "capture_fingerprint", "saved_version")} for value in citations}
    basis = {"schema_version": 1, "claims": pins, "sources": sorted(source_pins.values(), key=lambda value: value["id"]),
        "comparisons": [{key: value[key] for key in ("id", "kind", "status", "revision")} for value in related],
        "provenance": processing, "publication_id": snapshot["publication_id"], "publication_revision": snapshot["publication_revision"]}
    return {**snapshot, "complete": complete, "reviewable": reviewable,
        "evidence_fingerprint": digest(snapshot) if reviewable else None, "basis": basis,
        "limits": {"citations": EVIDENCE_LIMIT, "comparisons": COMPARISON_LIMIT}}


def history_visible(session, review, publication):
    # The reason may discuss a related source that has since been withdrawn.
    pins = review.basis.get("sources", [])
    if (review.basis.get("schema_version") != 1 or not pins
            or review.basis.get("publication_id") != (publication.id if publication else None)
            or review.basis.get("publication_revision") != (publication.revision if publication else None)):
        return False
    ids = {value["id"] for value in pins}
    visible = set(session.scalars(source_query(review.dossier_id, publication).with_only_columns(InvestigationSource.id)
        .where(InvestigationSource.id.in_(ids))))
    return visible == ids


def decision_state(latest, latest_visible, current):
    """One human-state contract for the review reader and retrieval projections."""
    stale = bool(latest and (not latest_visible or latest.evidence_fingerprint != current["evidence_fingerprint"]))
    decision = latest.decision if latest_visible else None
    return {"revision": latest.revision if latest else 0, "decision": decision, "stale": stale,
        "human_status": "UNRESOLVED" if stale else STATES.get(decision, "PROPOSED"),
        "finding_status": "PENDING_REVIEW" if stale or not decision else decision.upper()}


@read_once
def projection(session, claim, *, current=None):
    """Current private search metadata; no reviewer identity, reason or history."""
    current = current or context(session, claim)
    latest = session.scalar(select(ClaimReview).where(ClaimReview.claim_id == claim.id)
        .order_by(ClaimReview.revision.desc()).limit(1))
    visible = bool(latest and history_visible(session, latest, None))
    state = decision_state(latest, visible, current)
    return {**state, **recorded(latest, visible), **source_recorded(latest, visible, compact=True), "complete": current["complete"], "reviewable": current["reviewable"],
        "context_fingerprint": digest({key: value for key, value in current.items() if key != "basis"}),
        "has_conflicting_evidence": any(row["relation"] == "CONTRADICTS" for row in current["evidence"])
            or any(row["kind"] == "CONTRADICTS" and row["status"] == "active" for row in current["comparisons"])}


def payload(session, claim, publication=None, *, current=None):
    current = current or context(session, claim, publication)
    history = list(session.scalars(select(ClaimReview).where(ClaimReview.claim_id == claim.id)
        .order_by(ClaimReview.revision).limit(100)))
    latest = history[-1] if history else None
    visible = [row for row in history if history_visible(session, row, publication)]
    latest_visible = latest in visible if latest else False
    return {key: value for key, value in current.items() if key != "basis"} | {
        "id": claim.id, **decision_state(latest, latest_visible, current), **recorded(latest, latest_visible), **source_recorded(latest, latest_visible),
        "history_unavailable": len(visible) != len(history),
        "history": [{"revision": row.revision, "decision": row.decision, "reason": row.reason,
            "at": iso(row.created_at), "reviewer": "Dossier editor" if row.reviewed_by_user_id else "Former dossier editor",
            "evidence_fingerprint": row.evidence_fingerprint, "basis": row.basis} for row in visible]}


def page(session, dossier_id, publication=None, *, offset=0):
    from .domain_packs import for_product
    from .product_claim_interpretation import options
    from .product_models import ProductDossier

    pack = for_product(session.get(ProductDossier, dossier_id).product)
    query = claims(dossier_id, publication)
    return {"items": [payload(session, row, publication) for row in session.scalars(query
        .order_by(DossierClaim.created_at.desc(), DossierClaim.id).offset(offset).limit(PAGE_SIZE))],
        "total": session.scalar(select(func.count()).select_from(query.subquery())),
        "offset": offset, "page_size": PAGE_SIZE, "publication_revision": publication.revision if publication else None,
        "boundary": BOUNDARY, "interpretation_options": options(pack), "source_assessment_options": source_options(pack)}
