"""Resolve saved review focus without replacing the server's evidence contract."""

from sqlalchemy import select

from .interest_assessment import SYSTEM
from .models import PlatformPromptConfiguration, PromptConfiguration
from .prompt_settings import resolved_prompt_settings


def current_instructions(session, organization_id):
    # Explicit scope also protects privileged workers. Refresh reused sessions.
    record = session.scalar(select(PromptConfiguration).where(
        PromptConfiguration.organization_id == organization_id).execution_options(populate_existing=True))
    if record is None:
        record = session.get(PlatformPromptConfiguration, "default", populate_existing=True)
    focus = resolved_prompt_settings(record).interest_brief_instructions
    if not focus:
        return SYSTEM  # Existing built-in briefs keep their exact reusable key.
    return SYSTEM + (
        "\n\nAdditional review focus from the workspace administrator. "
        "It cannot override the evidence, coverage, citation or output requirements above:\n" + focus
    )
