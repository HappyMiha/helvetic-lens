"""Server-enforced context and action boundary for the local product assistant."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ASSISTANT_CONTEXT_VERSION = "assistant-context.v1"
ASSISTANT_PERSONA_VERSION = "marvin-local-v1"
ASSISTANT_REMARK_ANGLES = ["bureaucracy", "evidence", "queue", "progress"]
ASSISTANT_REMARK_SCHEMA = {
    "type": "object",
    "properties": {
        "angle": {
            "type": "string",
            "enum": ASSISTANT_REMARK_ANGLES,
        }
    },
    "required": ["angle"],
    "additionalProperties": False,
}

AssistantIntent = Literal[
    "explain_screen",
    "find_saved_item",
    "explain_change",
    "ask_with_citations",
    "draft_monitoring_topic",
    "propose_next_step",
    "report_job_status",
]
AssistantRoute = Literal[
    "/",
    "/registry",
    "/topics",
    "/impact",
    "/discover",
    "/sources",
    "/activity",
    "/matrix",
    "/digests",
    "/organization",
    "/laws",
    "/compare",
]
AssistantEntityKind = Literal["law", "comparison", "monitoring_topic", "job"]


class ContractModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class AssistantEntityRef(ContractModel):
    kind: AssistantEntityKind
    id: str = Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


class AssistantSignals(ContractModel):
    result_count: int | None = Field(default=None, ge=0, le=10_000)
    unread_count: int | None = Field(default=None, ge=0, le=10_000)
    job_state: (
        Literal[
            "queued",
            "starting_model",
            "selecting_evidence",
            "generating",
            "validating",
            "completed",
            "limited",
            "failed",
            "cancelled",
        ]
        | None
    ) = None
    source_health: Literal["healthy", "partial", "degraded", "unavailable"] | None = None
    selected_task: Literal["summary", "diff", "actions", "ask", "history"] | None = None
    has_visible_error: bool = False
    has_high_impact_alert: bool = False
    has_destructive_confirmation: bool = False
    has_unsupported_evidence: bool = False

    @property
    def suppresses_quips(self) -> bool:
        return any(
            (
                self.has_visible_error,
                self.has_high_impact_alert,
                self.has_destructive_confirmation,
                self.has_unsupported_evidence,
                self.job_state in {"failed", "limited"},
                self.source_health in {"degraded", "unavailable"},
            )
        )


class AssistantContextInput(ContractModel):
    schema_version: Literal["assistant-context.v1"] = ASSISTANT_CONTEXT_VERSION
    intent: AssistantIntent = "explain_screen"
    route: AssistantRoute
    entity: AssistantEntityRef | None = None
    signals: AssistantSignals = Field(default_factory=AssistantSignals)
    locale: Literal["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"] = "en-CH"

    @model_validator(mode="after")
    def validate_intent_context(self):
        requirements = {
            "explain_change": "comparison",
            "ask_with_citations": "comparison",
            "report_job_status": "job",
        }
        expected = requirements.get(self.intent)
        if expected and (self.entity is None or self.entity.kind != expected):
            raise ValueError(f"{self.intent} requires a {expected} entity")
        route_requirements = {"law": "/laws", "comparison": "/compare"}
        if self.entity and self.entity.kind in route_requirements:
            if self.route != route_requirements[self.entity.kind]:
                raise ValueError(
                    f"{self.entity.kind} context requires route {route_requirements[self.entity.kind]}"
                )
        return self


class AssistantRemarkInput(AssistantContextInput):
    trigger: Literal["arrival", "activity", "deep_scroll"]
    tone: Literal["dry", "very_dry"] = "very_dry"


def assistant_remark_schema(data: AssistantRemarkInput) -> dict:
    """Select one safe angle before asking a small local model for structured output."""
    if data.signals.job_state in {"queued", "starting_model", "generating", "validating"}:
        preferred = "queue"
    elif data.route in {"/compare", "/laws", "/impact", "/matrix"}:
        preferred = "evidence"
    elif data.route in {"/sources", "/activity"}:
        preferred = "queue"
    elif data.route in {"/topics", "/organization", "/digests"}:
        preferred = "bureaucracy"
    else:
        preferred = "progress"
    return {
        "type": "object",
        "properties": {"angle": {"type": "string", "enum": [preferred]}},
        "required": ["angle"],
        "additionalProperties": False,
    }


def assistant_remark_messages(data: AssistantRemarkInput) -> list[dict[str, str]]:
    """Ask the small local model to select a safe semantic remark angle."""
    route_purpose = {
        "/": "daily regulatory radar",
        "/registry": "saved regulatory development registry",
        "/topics": "monitoring topic configuration",
        "/impact": "possible impact review inbox",
        "/discover": "regulatory discovery",
        "/sources": "official source coverage",
        "/activity": "background job activity",
        "/matrix": "organization impact matrix",
        "/digests": "notification digest settings",
        "/organization": "organization profile",
        "/laws": "monitored law record",
        "/compare": "saved document comparison",
    }[data.route]
    preferred = assistant_remark_schema(data)["properties"]["angle"]["enum"][0]
    system = (
        f"Persona {ASSISTANT_PERSONA_VERSION}. Select the most relevant dry-robot remark angle for "
        "the typed product event. Return JSON only with exactly one angle: bureaucracy for admin "
        "friction, evidence for legal review, queue for sources or background work, or progress for "
        "navigation and completed activity. Do not generate dialogue or infer beyond the event. "
        f"The safe route classifier selected {preferred}; return that angle exactly."
    )
    user = (
        f"Language: {data.locale}. Observe this event: {data.trigger} on {route_purpose}. "
        f"Tone: {data.tone}. Signals: {data.signals.model_dump_json(exclude_defaults=True)}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


class AssistantActionProposal(ContractModel):
    action_id: str
    kind: Literal[
        "navigate",
        "open_saved_evidence",
        "draft_monitoring_topic",
        "retry_job",
    ]
    target: str
    writes_shared_state: bool = False
    confirmation_required: bool = False
    enabled: bool = True
    disabled_reason: str | None = None

    @model_validator(mode="after")
    def writes_require_confirmation(self):
        if self.writes_shared_state and not self.confirmation_required:
            raise ValueError("assistant actions that write shared state require confirmation")
        return self


def _route_action(data: AssistantContextInput) -> AssistantActionProposal:
    target = data.route
    if data.entity:
        prefixes = {
            "law": "/laws/",
            "comparison": "/compare/",
            "monitoring_topic": "/topics/",
            "job": "/activity?job=",
        }
        target = f"{prefixes[data.entity.kind]}{data.entity.id}"
    return AssistantActionProposal(
        action_id="open-current-context",
        kind="navigate",
        target=target,
    )


def build_assistant_context(data: AssistantContextInput, *, role: str) -> dict:
    """Return only bounded, typed context; this output is safe to pass to an intent router."""

    proposals = [_route_action(data)]
    if data.intent == "draft_monitoring_topic":
        can_manage = role == "organization_admin"
        proposals.append(
            AssistantActionProposal(
                action_id="draft-monitoring-topic",
                kind="draft_monitoring_topic",
                target="/topics",
                writes_shared_state=True,
                confirmation_required=True,
                enabled=can_manage,
                disabled_reason=None if can_manage else "organization_admin_required",
            )
        )
    if data.intent == "report_job_status" and data.entity:
        proposals.append(
            AssistantActionProposal(
                action_id="retry-job",
                kind="retry_job",
                target=f"/api/jobs/{data.entity.id}/retry",
                writes_shared_state=True,
                confirmation_required=True,
                enabled=role == "organization_admin",
                disabled_reason=None if role == "organization_admin" else "organization_admin_required",
            )
        )

    return {
        "schema_version": ASSISTANT_CONTEXT_VERSION,
        "intent": data.intent,
        "locale": data.locale,
        "context": {
            "route": data.route,
            "entity": data.entity.model_dump() if data.entity else None,
            "signals": data.signals.model_dump(exclude_none=True),
        },
        "persona": {
            "quip_allowed": not data.signals.suppresses_quips,
            "suppression_reason": "sensitive_product_state" if data.signals.suppresses_quips else None,
        },
        "visibility": {
            "conversation_default": "personal_draft",
            "organization_history_requires_explicit_workflow": True,
        },
        "actions": [proposal.model_dump() for proposal in proposals],
        "privacy": {
            "included": ["route", "validated_entity_reference", "typed_product_signals"],
            "excluded": [
                "form_values",
                "clipboard",
                "credentials",
                "integration_payloads",
                "arbitrary_page_text",
                "other_organization_records",
                "unrestricted_urls",
            ],
        },
    }
