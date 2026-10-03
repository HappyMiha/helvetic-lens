"""Current cross-run reading of the existing ledger, not another truth database."""
from itertools import combinations

from sqlalchemy import or_, select

from . import product_entity_identity as identity
from . import product_professional_context as professional
from .product_claim_evolution import query as changes_query
from .product_claim_review import projection as claim_review
from .product_investigation_models import (
    ClaimChange,
    ClaimEvidence,
    DossierClaim,
    DossierEntity,
    Investigation,
    InvestigationSource,
)
from .product_operations import fingerprint
from .product_public_research import sources_visible
from .research_knowledge import captured_at

CONTRACT = "current-dossier-knowledge/v1"
SYSTEM = """current_dossier_knowledge groups cited identifiers and links earlier
claims to later evidence. Original records and human decisions remain separate.
Exact identifiers do not merge people by name. Same document hashes or repeated
origins are not independent confirmation; different publishers alone do not prove
independence. A machine update is a proposed relationship, not accepted supersession.
Use current and contested evidence together; preserve history and open review.
This context never authorizes a citation outside the supplied current source list.
Professional context consists of source quotations, not verified applicability.
"""


def project(session, run):
    runs = select(Investigation.id).where(Investigation.dossier_id == run.dossier_id,
        Investigation.organization_id == run.organization_id, Investigation.publication_id.is_(None),
        or_(Investigation.status == "completed", Investigation.id == run.id), sources_visible())
    run_ids = list(session.scalars(runs))
    source_rows = list(session.scalars(select(InvestigationSource).where(
        InvestigationSource.investigation_id.in_(run_ids), InvestigationSource.kind == "public_source",
        InvestigationSource.snapshot["allow_discovery"].as_boolean().is_not(False))
        .order_by(InvestigationSource.created_at.desc(), InvestigationSource.id).limit(601)))
    truncated, source_rows = len(source_rows) > 600, source_rows[:600]
    sources = {s.id: s for s in source_rows}
    candidates = list(session.scalars(select(DossierClaim).where(DossierClaim.investigation_id.in_(run_ids))
        .order_by(DossierClaim.created_at.desc(), DossierClaim.id).limit(121)))
    truncated = truncated or len(candidates) > 120
    claims = {}
    for claim in candidates[:120]:
        evidence = list(session.scalars(select(ClaimEvidence).where(ClaimEvidence.claim_id == claim.id)))
        if not evidence or any(e.source_id not in sources or not any(
                p["passage"] == e.locator and e.quote in p["text"]
                for p in sources[e.source_id].snapshot.get("excerpts", [])) for e in evidence):
            continue
        claims[claim.id] = {"id": claim.id, "investigation_id": claim.investigation_id,
            "statement": claim.statement, "revision": claim.revision, "status": claim.status,
            "reading_state": "superseded" if claim.status == "SUPERSEDED" else "contested" if claim.status == "CONTESTED" else "current",
            "human_status": claim_review(session, claim)["human_status"], "later_evidence": [],
            "evidence": [{"source_id": e.source_id, "sha256": sources[e.source_id].sha256,
                "quote": e.quote, "locator": e.locator, "relation": e.relation} for e in evidence[:6]]}
    for change in session.scalars(changes_query(run.dossier_id).where(
            ClaimChange.previous_claim_id.in_(claims), ClaimChange.claim_id.in_(claims), ClaimChange.status == "active")
            .order_by(ClaimChange.created_at.desc()).limit(240)):
        old, new = claims.get(change.previous_claim_id), claims.get(change.claim_id)
        if not old or not new or change.status != "active" or old["revision"] != change.previous_revision or old["status"] != change.previous_status:
            continue
        if not session.scalar(select(ClaimEvidence.id).where(ClaimEvidence.id == change.evidence_id,
                ClaimEvidence.claim_id == new["id"])):
            continue
        old["later_evidence"].append({"claim_id": new["id"], "kind": change.kind, "explanation": change.explanation,
            "reviewed": change.reviewed_by_user_id is not None})
        if change.kind == "CONTRADICTS":
            old["reading_state"] = "contested"
        elif change.kind == "UPDATES" and old["reading_state"] != "contested":
            old["reading_state"] = "superseded" if change.reviewed_by_user_id else "update_needs_review"
    entities = list(session.scalars(select(DossierEntity).where(DossierEntity.investigation_id.in_(run_ids))
        .order_by(DossierEntity.created_at.desc(), DossierEntity.id).limit(121)))
    mentions = [value for e in entities[:120] if (value := identity.mention(session, e)) and value["source"]["id"] in sources]
    decisions = {}
    for review in session.scalars(identity.reviews(run.dossier_id)):
        pair = identity.pair(session, session.get(DossierEntity, review.entity_id), session.get(DossierEntity, review.previous_entity_id))
        if pair["evidence_fingerprint"] == review.evidence_fingerprint:
            decisions[frozenset((review.entity_id, review.previous_entity_id))] = review.decision
    def compatible(a, b):
        decision = decisions.get(frozenset((a["id"], b["id"])))
        return decision == "same" or decision is None and a["identifier"] == b["identifier"]
    groups = []
    for mention in mentions:
        group = next((g for g in groups if all(compatible(mention, existing) for existing in g)), None)
        if group is None:
            groups.append([mention])
        else:
            group.append(mention)
    identities = [{"id": fingerprint(sorted(m["id"] for m in group)),
        "names": list(dict.fromkeys(m["name"] for m in group)), "mentions": group,
        "basis": "reviewed_pairs" if len(group) > 1 and all(
            decisions.get(frozenset((a["id"], b["id"]))) == "same" for a, b in combinations(group, 2)) else "cited_identifier"}
        for group in groups]
    origins = {}
    for source in source_rows:
        origins.setdefault(source.sha256, []).append({"id": source.id, "title": source.title,
            "url": source.url, "captured_at": captured_at(source)})
    context = professional.project(source_rows)
    context["facts"] = context["facts"][:60]
    return {"contract": CONTRACT, "claims": list(claims.values()), "identities": identities,
        "document_origins": [{"sha256": sha, "sources": values,
            "independence": "same_document" if len(values) > 1 else "not_established"} for sha, values in origins.items()],
        "professional_context": context,
        "scope": {"sources": len(source_rows), "claims": len(claims), "entities": len(mentions),
            "truncated": truncated or len(entities) > 120,
            "note": "Current permitted public research only; historical originals and human reviews are retained."}}


def prepare(session, run, work):
    from .product_research_mission import enabled

    if not enabled(run) or work["phase"] not in {"plan", "reflect", "brief"}:
        return
    value = project(session, run)
    work["knowledge_fingerprint"] = fingerprint(value)
    work["input"]["current_dossier_knowledge"] = {**value, "claims": value["claims"][:16],
        "identities": value["identities"][:8], "document_origins": value["document_origins"][:24]}


def input_current(session, run, work):
    return not work.get("knowledge_fingerprint") or work["knowledge_fingerprint"] == fingerprint(project(session, run))
