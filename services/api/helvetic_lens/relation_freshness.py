"""Read-time assessment freshness without inference or archived-payload hydration."""

from sqlalchemy import String, cast, func, select

from . import relation_analysis
from .config import Settings
from .models import OrganizationRelationCandidate, Profile, RelationCandidate, RelationImpactAnalysis
from .prompt_settings import PromptSettings


def uses_profile(plan: dict | None, revision: int | None) -> bool:
    execution = plan.get("execution") if isinstance(plan, dict) else None
    saved = execution.get("profile_revision") if isinstance(execution, dict) else None
    # Match SQL JSON text extraction. Missing/malformed provenance fails closed.
    return revision is not None and str(saved) == str(revision)


def uses_configuration(plan: dict | None, settings: Settings) -> bool:
    execution = plan.get("execution") if isinstance(plan, dict) else None
    saved = execution.get("configuration_fingerprint") if isinstance(execution, dict) else None
    return saved == relation_analysis.configuration_fingerprint(settings)


def uses_prompts(plan: dict | None, prompts: PromptSettings) -> bool:
    execution = plan.get("execution") if isinstance(plan, dict) else None
    saved = execution.get("prompt_fingerprint") if isinstance(execution, dict) else None
    return saved == relation_analysis.relation_prompt_fingerprint(prompts)


def uses_versions(plan: dict | None, source_version_id: str | None, target_version_id: str | None) -> bool:
    execution = plan.get("execution") if isinstance(plan, dict) else None
    binding = execution.get("version_binding") if isinstance(execution, dict) else None
    expected = relation_analysis.version_binding(source_version_id, target_version_id)
    return isinstance(binding, dict) and all(binding.get(key) == value for key, value in expected.items())


def current_analysis_predicate(settings: Settings, prompts: PromptSettings):
    """A correlated scalar predicate keeps tenant identity inside the SQL check."""
    model = RelationImpactAnalysis
    matching_profile = select(Profile.id).where(
        Profile.organization_id == model.organization_id,
        cast(Profile.revision, String) == model.analysis_plan["execution"]["profile_revision"].as_string(),
    ).correlate(model).exists()
    candidate, delivery = RelationCandidate, OrganizationRelationCandidate
    matching_versions = select(candidate.id).join(delivery, delivery.candidate_id == candidate.id).where(
        delivery.id == model.organization_candidate_id,
        delivery.organization_id == model.organization_id,
        candidate.id == model.candidate_id,
        func.coalesce(candidate.source_version_id, "") == model.analysis_plan["execution"]["version_binding"]["source"].as_string(),
        func.coalesce(candidate.target_version_id, "") == model.analysis_plan["execution"]["version_binding"]["target"].as_string(),
    ).correlate(model).exists()
    return (
        (model.status == "succeeded")
        & (model.result["schema_version"].as_string() == relation_analysis.SCHEMA_VERSION)
        & matching_profile
        & matching_versions
        & (model.analysis_plan["execution"]["configuration_fingerprint"].as_string()
           == relation_analysis.configuration_fingerprint(settings))
        & (model.analysis_plan["execution"]["prompt_fingerprint"].as_string()
           == relation_analysis.relation_prompt_fingerprint(prompts))
    )
