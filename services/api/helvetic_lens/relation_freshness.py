"""Read-time profile freshness without inference or archived-payload hydration."""

from sqlalchemy import String, cast, select

from . import relation_analysis
from .models import Profile, RelationImpactAnalysis


def uses_profile(plan: dict | None, revision: int | None) -> bool:
    execution = plan.get("execution") if isinstance(plan, dict) else None
    saved = execution.get("profile_revision") if isinstance(execution, dict) else None
    # Match SQL JSON text extraction. Missing/malformed provenance fails closed.
    return revision is not None and str(saved) == str(revision)


def current_profile_result():
    """A correlated scalar predicate keeps tenant identity inside the SQL check."""
    model = RelationImpactAnalysis
    matching_profile = select(Profile.id).where(
        Profile.organization_id == model.organization_id,
        cast(Profile.revision, String) == model.analysis_plan["execution"]["profile_revision"].as_string(),
    ).correlate(model).exists()
    return (
        (model.status == "succeeded")
        & (model.result["schema_version"].as_string() == relation_analysis.SCHEMA_VERSION)
        & matching_profile
    )
