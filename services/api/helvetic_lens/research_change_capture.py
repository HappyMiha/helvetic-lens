"""Skip repeated analysis only for an exact, still-permitted successful capture."""
from sqlalchemy import select

from .product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from .product_public_research import sources_visible


def unchanged(session, run, source):
    candidates = session.scalars(select(InvestigationSource).join(Investigation,
        Investigation.id == InvestigationSource.investigation_id).where(
            InvestigationSource.dossier_id == run.dossier_id, InvestigationSource.organization_id == run.organization_id,
            InvestigationSource.id != source.id, InvestigationSource.sha256 == source.sha256,
            InvestigationSource.kind == source.kind, InvestigationSource.url == source.url,
            Investigation.status == "completed", Investigation.publication_id.is_(None),
            Investigation.question == run.question, sources_visible())
        .order_by(InvestigationSource.created_at.desc(), InvestigationSource.id).limit(30))
    for previous in candidates:
        if previous.snapshot.get("excerpts") != source.snapshot.get("excerpts"):
            continue
        branches = session.scalars(select(InvestigationBranch).where(InvestigationBranch.investigation_id == previous.investigation_id))
        if not any(step.get("phase") == "extract" and step.get("source_id") == previous.id and step.get("status") == "completed"
                for branch in branches for step in branch.checkpoint.get("steps", [])):
            continue
        source.snapshot = {**source.snapshot, "unchanged_from": previous.id,
            "previous_analysed_source_id": previous.id, "capture_state": "unchanged",
            "analysis_reuse": "Exact extracted passages and source hash match a still-permitted successfully analysed capture for this question."}
        return True
    return False
