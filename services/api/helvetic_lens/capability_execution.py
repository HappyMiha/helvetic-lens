"""Captured approval decisions for an observed runtime, never a provider label."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .ai_capabilities import CapabilityDecision, CapabilityRegistry, load_registry, resolve_capability
from .config import DomainError, Settings
from .runtime_binding import PromptTokenMeasurement, RuntimeSnapshot

EXECUTION_VERSION = "capability-execution-v1"


@dataclass(frozen=True)
class CapabilityState:
    registry: CapabilityRegistry
    selected_profile: str | None
    runtime: RuntimeSnapshot | None
    fingerprint: str
    valid: bool

    def decision(self, task: str, locale: str) -> CapabilityDecision:
        decision = resolve_capability(
            self.registry, profile_id=self.selected_profile,
            identity=self.runtime.identity if self.runtime else None, task=task, locale=locale,
        )
        reason = None
        if not self.valid:
            reason = "registry_invalid"
        elif decision.mode == "generated_explanation" and (not self.runtime or not self.runtime.prompt_budget_schema):
            reason = "measurement_unavailable"
        if reason:
            decision = decision.model_copy(update={"mode": "selected_evidence", "reason": reason, "budget": None, "evaluation": None})
        fingerprint = hashlib.sha256(json.dumps({
            "execution": self.fingerprint, "decision": decision.model_dump(mode="json"),
        }, sort_keys=True).encode()).hexdigest()
        return decision.model_copy(update={"fingerprint": fingerprint})


def capture_capabilities(settings: Settings, runtime: RuntimeSnapshot | None) -> CapabilityState:
    try:
        registry = load_registry(settings.ai_capability_registry, settings.ai_capability_evidence_root)
        valid = True
    except (OSError, ValueError, TypeError):
        # An unreadable approval cannot authorize explanation or preserve its
        # old cache key. Saved records remain readable as historical evidence.
        registry = CapabilityRegistry(schema_version="ai-capability-registry-v1", profiles=())
        valid = False
    selected = settings.apertus_explanation_profile or None
    state = {
        "version": EXECUTION_VERSION, "valid": valid, "selected_profile": selected,
        "registry": registry.model_dump(mode="json"),
        "runtime": runtime.cache_identity() if runtime else None,
    }
    fingerprint = hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
    return CapabilityState(registry, selected, runtime, fingerprint, valid)


def check_capability_freshness(settings: Settings, captured: CapabilityState) -> None:
    current = capture_capabilities(settings, captured.runtime)
    if current.fingerprint != captured.fingerprint:
        raise DomainError(
            "The model capability approval changed during analysis. Start a new analysis; previous history remains available.",
            409, "capability_changed",
        )


def within_reviewed_budget(measured: PromptTokenMeasurement, decision: CapabilityDecision | None) -> bool:
    if not measured.fits:
        return False
    if decision is None or decision.budget is None:
        return True
    budget = decision.budget
    return (
        measured.input_tokens <= budget.input_tokens
        and measured.reserved_output_tokens <= budget.output_tokens
        and measured.input_tokens + measured.reserved_output_tokens + max(measured.safety_tokens, budget.safety_tokens)
        <= min(measured.context_window_tokens, budget.context_window_tokens)
    )


def public_capability_profiles(settings: Settings) -> dict:
    captured = capture_capabilities(settings, None)
    return {
        "explanation_registry_valid": captured.valid,
        "explanation_profiles": [{
            "id": profile.id, "revision": profile.revision, "status": profile.status,
            "model_id": profile.identity.model_id,
            "scopes": [{"task": grant.task, "locale": grant.locale} for grant in profile.grants],
        } for profile in captured.registry.profiles],
    }
