"""Server-enforced context and action boundary for the local product assistant."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ASSISTANT_CONTEXT_VERSION = "assistant-context.v1"

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
