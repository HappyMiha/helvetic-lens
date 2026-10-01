"""Read-only notifications from retained completions, never copied evidence."""
from datetime import UTC

from sqlalchemy import and_, case, exists, func, or_, select

from .db import utcnow
from .product_api import iso
from .product_claim_evolution import payload as change_payload
from .product_claim_evolution import query as change_query
from .product_investigation_models import (
    ClaimChange,
    ClaimEvidence,
    DossierClaim,
    Investigation,
    InvestigationEvent,
    InvestigationSource,
)
from .product_public_research import eligible, sources_visible
from .product_research_materiality import CONTRACT as MATERIALITY_CONTRACT
from .product_research_materiality import delivery

PAGE_SIZE = 10
EMPTY = {"total": 0, "unseen": 0, "latest_at": None}
COVERAGE = ("Research with new evidence and recorded monitoring gaps. Unchanged repeat captures, "
    "unfinished research and withdrawn evidence are excluded. Source/finding counts "
    "do not measure completeness or truth. Reading does not verify a machine finding. No email is sent.")


def new_source():
    return (InvestigationSource.snapshot["unchanged_from"].as_string().is_(None)
        & InvestigationSource.snapshot["retained_origin"]["source_id"].as_string().is_(None)
        & InvestigationSource.snapshot["duplicate_of"].as_string().is_(None)
        & InvestigationSource.snapshot["capture_state"].as_string().is_distinct_from("unchanged")
        & InvestigationSource.snapshot["excerpts"][0]["text"].as_string().is_not(None))


def completed(dossier_id, publication=None):
    # The durable completion event is immutable; reviews may change updated_at.
    # Retry completions replace the same run's head instead of duplicating it.
    has_evidence = exists(select(InvestigationSource.id).where(
        InvestigationSource.investigation_id == Investigation.id, new_source()))
    query = select(Investigation.id.label("id"), func.max(InvestigationEvent.created_at).label("finished_at"))\
        .join(InvestigationEvent, InvestigationEvent.investigation_id == Investigation.id).where(
            Investigation.dossier_id == dossier_id, or_(Investigation.status == "completed",
                and_(Investigation.status == "failed", Investigation.research_state["materiality"]["category"].as_string() == "coverage_gap")),
            InvestigationEvent.kind == "investigation_finished",
            InvestigationEvent.detail["status"].as_string() == Investigation.status,
            or_(has_evidence, Investigation.research_state["materiality"]["category"].as_string() == "coverage_gap"))
    query = query.where(Investigation.publication_id == publication.id, eligible()) if publication else query.where(
        Investigation.publication_id.is_(None), sources_visible())
    return query.group_by(Investigation.id)


def summary(session, dossier_id, saved, publication=None):
    rows = completed(dossier_id, publication).subquery()
    unseen = rows.c.finished_at > saved.research_seen_at if saved and saved.research_seen_at else True
    mode = getattr(saved, "delivery_mode", None) or "immediate"
    midnight = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    category = Investigation.research_state["materiality"]["category"].as_string()
    legacy = Investigation.research_state["materiality"]["contract"].as_string().is_distinct_from(MATERIALITY_CONTRACT)
    released = and_(category != "quiet", or_(mode == "immediate", rows.c.finished_at < midnight))
    allowed = and_(mode != "silent", or_(and_(legacy, or_(mode == "immediate", rows.c.finished_at < midnight)), released))
    total, latest, new = session.execute(select(func.count(), func.max(rows.c.finished_at),
        func.coalesce(func.sum(case((and_(unseen, allowed), 1), else_=0)), 0)).select_from(rows)
        .join(Investigation, Investigation.id == rows.c.id)).one()
    return {"total": total, "latest_at": iso(latest) if latest else None, "unseen": int(new) if saved and saved.following else 0}


def marker(research):
    # Unseen count is account-local; acknowledging must not change the head.
    return [research["total"], research["latest_at"]]


def update_payload(session, run, finished_at, saved, publication):
    from .product_monitoring_outcomes import project
    sources = select(InvestigationSource).where(InvestigationSource.investigation_id == run.id, new_source())
    claims = select(DossierClaim).where(DossierClaim.investigation_id == run.id)
    changes = change_query(run.dossier_id, publication).where(ClaimChange.investigation_id == run.id,
        ClaimChange.status == "active")
    change_rows = changes.subquery()
    counts = dict(session.execute(select(change_rows.c.kind, func.count()).group_by(change_rows.c.kind)).all())
    samples = []
    for source in session.scalars(sources.order_by(InvestigationSource.created_at, InvestigationSource.id).limit(3)):
        excerpt = source.snapshot["excerpts"][0]
        samples.append({"id": source.id, "title": source.title, "url": source.url,
            "sha256": source.sha256, "quote": excerpt["text"][:600], "locator": excerpt.get("passage", ""),
            "truncated": len(excerpt["text"]) > 600})
    findings = []
    for claim in session.scalars(claims.order_by(DossierClaim.created_at, DossierClaim.id).limit(3)):
        citation = session.scalar(select(ClaimEvidence).where(ClaimEvidence.claim_id == claim.id)
            .order_by(ClaimEvidence.created_at, ClaimEvidence.id).limit(1))
        findings.append({"id": claim.id, "statement": claim.statement, "status": claim.status,
            "source_id": citation.source_id if citation else None})
    outcome = project(session, run) if publication is None else None
    from .product_research_materiality import project as materiality_projection

    importance = materiality_projection(outcome or {"comparisons": [change_payload(session, c) for c in session.scalars(changes)], "findings": findings})
    mode = getattr(saved, "delivery_mode", None) or "immediate"
    delivered = delivery(mode, importance, finished_at)
    if "materiality" not in run.research_state and mode == "immediate":
        delivered = "immediate"
    return {"investigation_id": run.id, "question": run.question, "completed_at": iso(finished_at),
        "materiality": importance, "delivery": delivered,
        "unseen": bool(saved and saved.following and delivered in {"immediate", "digest"} and (not saved.research_seen_at
            or finished_at.replace(tzinfo=UTC) > saved.research_seen_at.replace(tzinfo=UTC))),
        "source_count": session.scalar(select(func.count()).select_from(sources.subquery())),
        "finding_count": session.scalar(select(func.count()).select_from(claims.subquery())),
        "comparison_counts": counts, "sources": samples, "findings": findings,
        "comparisons": [change_payload(session, change) for change in session.scalars(
            changes.order_by(ClaimChange.created_at.desc(), ClaimChange.id).limit(3))],
        "completion_note": run.stop_reason, "outcome": outcome}


def page(session, dossier_id, saved, publication=None, *, offset=0):
    rows = completed(dossier_id, publication).subquery()
    result = session.execute(select(Investigation, rows.c.finished_at).join(rows, rows.c.id == Investigation.id)
        .order_by(rows.c.finished_at.desc(), Investigation.id).offset(offset).limit(PAGE_SIZE))
    return {"items": [update_payload(session, run, finished, saved, publication) for run, finished in result],
        "total": session.scalar(select(func.count()).select_from(rows)), "offset": offset,
        "page_size": PAGE_SIZE, "coverage": COVERAGE}
