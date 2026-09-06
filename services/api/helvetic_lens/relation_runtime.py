"""Observed local runtime identity, scoped to one organization's configuration.

No network or inference here. Callers supply the bounded gateway observation;
inventory descriptions and saved job payloads cannot attest the running model.
"""

import hashlib
import json
from dataclasses import dataclass

from .config import DomainError, Settings
from .relation_analysis import configuration_fingerprint


@dataclass(frozen=True)
class RelationRuntimeObservation:
    organization_id: str
    configuration: str
    fingerprint: str | None


def observe_runtime(settings: Settings, organization_id: str, identity: dict | None) -> RelationRuntimeObservation:
    runtime = None
    if settings.apertus_provider == "docker":
        if not isinstance(identity, dict) or identity.get("schema_version") != "local-runtime-cache-v1" or not identity.get("fingerprint"):
            return RelationRuntimeObservation(organization_id, configuration_fingerprint(settings), None)
        runtime = identity
    value = {
        "schema": "relation-runtime-v2",
        "connection": [settings.apertus_provider, settings.apertus_base_url.rstrip("/"), settings.apertus_model],
        "runtime": runtime,
    }
    fingerprint = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
    return RelationRuntimeObservation(organization_id, configuration_fingerprint(settings), fingerprint)


def current_fingerprint(settings: Settings, organization_id: str, observation: RelationRuntimeObservation | None) -> str | None:
    if settings.apertus_provider != "docker":
        # Cloud freshness remains configuration-based; this is not an immutable
        # attestation of the remote weights behind a provider's model name.
        return observe_runtime(settings, organization_id, None).fingerprint
    if observation and observation.organization_id == organization_id and observation.configuration == configuration_fingerprint(settings):
        return observation.fingerprint
    return None


def require_fingerprint(settings: Settings, organization_id: str, observation: RelationRuntimeObservation | None) -> str:
    fingerprint = current_fingerprint(settings, organization_id, observation)
    if fingerprint is None:
        raise DomainError("The current local runtime could not be verified. Saved conclusions remain available in history; retry when Local models is ready.", 503, "model_runtime_unavailable")
    return fingerprint


def uses_runtime(plan: dict | None, settings: Settings, fingerprint: str | None) -> bool:
    if settings.apertus_provider != "docker":
        return True
    return fingerprint is not None and isinstance(plan, dict) and plan.get("runtime_fingerprint") == fingerprint
