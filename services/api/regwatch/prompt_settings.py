import hashlib
import json
from datetime import UTC
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import PromptConfiguration


class PromptSettings(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    impact_instructions: str = Field(
        default=(
            "Act as a careful regulatory change review assistant. Explain possible business impact "
            "and practical review actions without presenting the result as authoritative legal advice."
        ),
        min_length=20,
        max_length=12_000,
    )
    impact_synthesis_instructions: str = Field(
        default=(
            "Combine the validated batch reviews into one concise assessment. Prioritise material "
            "changes, preserve uncertainty, and keep every conclusion tied to cited saved evidence."
        ),
        min_length=20,
        max_length=12_000,
    )
    ask_instructions: str = Field(
        default=(
            "Answer the user's question in the user's language. Be direct, distinguish the earlier and "
            "current saved versions, and do not invent facts beyond the supplied evidence."
        ),
        min_length=20,
        max_length=12_000,
    )
    answer_synthesis_instructions: str = Field(
        default=(
            "Combine the validated batch answers into one clear answer in the user's language. Remove "
            "duplication and preserve the exact evidence needed to support the conclusion."
        ),
        min_length=20,
        max_length=12_000,
    )
    repair_instructions: str = Field(
        default=(
            "Correct the previous response so it matches the required JSON structure and citation rules. "
            "Do not add facts, identifiers, passages, or quotations that are absent from the evidence."
        ),
        min_length=20,
        max_length=12_000,
    )
    ask_context_mode: Literal["automatic", "changes_only"] = "automatic"


class PromptSettingsInput(PromptSettings):
    pass


def default_prompt_settings() -> PromptSettings:
    return PromptSettings()


def resolved_prompt_settings(record: PromptConfiguration | None) -> PromptSettings:
    defaults = default_prompt_settings().model_dump()
    if not record:
        return PromptSettings(**defaults)
    return PromptSettings(**{**defaults, **(record.values or {})})


def prompt_fingerprint(settings: PromptSettings) -> str:
    payload = json.dumps(settings.model_dump(), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def public_prompt_settings(
    settings: PromptSettings, record: PromptConfiguration | None
) -> dict:
    return {
        **settings.model_dump(),
        "source": "workspace" if record else "defaults",
        "revision": record.revision if record else 1,
        "fingerprint": prompt_fingerprint(settings),
        "updated_at": (
            record.updated_at.replace(tzinfo=UTC).isoformat()
            if record and record.updated_at.tzinfo is None
            else record.updated_at.isoformat()
            if record
            else None
        ),
    }
