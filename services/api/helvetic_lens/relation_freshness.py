"""Read-time profile/configuration freshness without inference or archived-payload hydration."""

from sqlalchemy import String, cast, select

from . import relation_analysis
from .config import Settings
from .models import Profile, RelationImpactAnalysis
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


def current_profile_result(settings: Settings, prompts: PromptSettings):
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
        & (model.analysis_plan["execution"]["configuration_fingerprint"].as_string()
           == relation_analysis.configuration_fingerprint(settings))
        & (model.analysis_plan["execution"]["prompt_fingerprint"].as_string()
           == relation_analysis.relation_prompt_fingerprint(prompts))
    )
