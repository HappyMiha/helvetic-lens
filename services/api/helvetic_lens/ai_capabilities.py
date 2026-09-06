"""Fail-closed, provider-independent contract for reviewed explanation profiles.

This is an approval/integrity gate, not a semantic evaluator or a runner probe.
Callers must obtain the identity from the serving runtime, not an editable model
label. No shipped profile is approved; HTTP/JSON success cannot create approval.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._/-]{0,199}$")]
Task = Literal["ask", "impact_report"]
Locale = Literal["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]
MAX_ARTIFACT_BYTES = 1024 * 1024


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RuntimeIdentity(Contract):
    """Actual immutable deployment inputs, independent of provider/transport."""

    model_id: Identifier
    model_revision: Annotated[str, Field(pattern=r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")]
    artifact_sha256: Digest
    tokenizer_sha256: Digest
    chat_template_sha256: Digest
    runtime_sha256: Digest
    hardware_profile: Identifier


class TokenBudget(Contract):
    context_window_tokens: int = Field(ge=512, le=1048576)
    input_tokens: int = Field(ge=1, le=1048576)
    output_tokens: int = Field(ge=128, le=8192)
    safety_tokens: int = Field(ge=128, le=8192)

    @model_validator(mode="after")
    def fits_window(self):
        if self.input_tokens + self.output_tokens + self.safety_tokens > self.context_window_tokens:
            raise ValueError("Input, output and safety reserves must fit the tested context window.")
        return self


class EvaluationReference(Contract):
    path: str = Field(min_length=1, max_length=240)
    sha256: Digest

    @model_validator(mode="after")
    def relative_path(self):
        parts = PurePosixPath(self.path).parts
        if (
            self.path.startswith("/") or "\\" in self.path or ":" in self.path
            or any(part in {".", ".."} for part in self.path.split("/"))
            or "" in self.path.split("/") or not parts or not self.path.endswith(".json")
        ):
            raise ValueError("Evaluation paths must be relative JSON paths without traversal.")
        return self


class CapabilityGrant(Contract):
    task: Task
    locale: Locale
    budget: TokenBudget
    evaluation: EvaluationReference


class CapabilityProfile(Contract):
    id: Identifier
    revision: int = Field(ge=1)
    status: Literal["candidate", "approved", "revoked"]
    identity: RuntimeIdentity
    grants: tuple[CapabilityGrant, ...] = Field(max_length=10)

    @model_validator(mode="after")
    def unique_scope(self):
        scopes = [(grant.task, grant.locale) for grant in self.grants]
        if len(set(scopes)) != len(scopes):
            raise ValueError("A profile cannot have two grants for the same task and locale.")
        if self.status == "approved" and not scopes:
            raise ValueError("Approved profiles need at least one reviewed task/locale grant.")
        return self


class CapabilityRegistry(Contract):
    schema_version: Literal["ai-capability-registry-v1"]
    profiles: tuple[CapabilityProfile, ...] = Field(max_length=256)

    @model_validator(mode="after")
    def unique_profiles(self):
        ids = [profile.id for profile in self.profiles]
        if len(set(ids)) != len(ids):
            raise ValueError("Profile IDs must be unique; retain earlier revisions in Git/history.")
        return self


class ReviewedEvaluation(Contract):
    """A signed-off assessment record, never inferred from transport benchmarks.

    The named reviewer and outcome are attestations to be independently checked
    during promotion. A hash protects integrity; it cannot establish truth.
    """

    schema_version: Literal["ai-explanation-review-v1"]
    profile_id: Identifier
    profile_revision: int = Field(ge=1)
    identity: RuntimeIdentity
    task: Task
    locale: Locale
    budget: TokenBudget
    dataset_sha256: Digest
    results_sha256: Digest
    evaluator_revision: Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")]
    reviewer: str = Field(min_length=1, max_length=160, pattern=r"\S")
    reviewed_at: AwareDatetime
    review_reference: str = Field(min_length=1, max_length=500, pattern=r"\S")
    independent_review: Literal[True]
    outcome: Literal["pass"]

    @field_validator("independent_review", mode="before")
    @classmethod
    def explicit_boolean_review(cls, value):
        # Literal[True] otherwise also accepts JSON 1 through Python equality.
        if value is not True:
            raise ValueError("Independent review must be the explicit JSON boolean true.")
        return value


def _read_bounded(path: Path) -> bytes:
    with path.open("rb") as stream:
        raw = stream.read(MAX_ARTIFACT_BYTES + 1)
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise ValueError("Capability artifact exceeds the one MiB limit.")
    return raw


def load_registry(path: Path, evidence_root: Path) -> CapabilityRegistry:
    """Load a trusted deployment registry and verify every approved grant.

    Missing/changed/out-of-root evidence raises, rather than silently approving
    a partial registry. This function never fetches a URL or writes a file.
    """

    registry = CapabilityRegistry.model_validate_json(_read_bounded(path))
    root = evidence_root.resolve(strict=True)
    for profile in registry.profiles:
        if profile.status != "approved":
            continue
        for grant in profile.grants:
            target = (root / grant.evaluation.path).resolve(strict=True)
            if not target.is_relative_to(root):
                raise ValueError("Evaluation artifact escapes the evidence root.")
            raw = _read_bounded(target)
            if hashlib.sha256(raw).hexdigest() != grant.evaluation.sha256:
                raise ValueError("Evaluation artifact checksum does not match its approval.")
            review = ReviewedEvaluation.model_validate_json(raw)
            expected = (profile.id, profile.revision, profile.identity, grant.task, grant.locale, grant.budget)
            actual = (
                review.profile_id, review.profile_revision, review.identity,
                review.task, review.locale, review.budget,
            )
            if actual != expected:
                raise ValueError("Evaluation does not match the exact profile, runtime, scope and budget.")
    return registry


class CapabilityDecision(Contract):
    mode: Literal["selected_evidence", "generated_explanation"]
    reason: Literal[
        "profile_not_selected", "profile_unknown", "profile_not_approved",
        "runtime_identity_unavailable", "runtime_identity_mismatch",
        "scope_not_reviewed", "reviewed_scope",
    ]
    profile_id: str | None
    profile_revision: int | None
    task: str
    locale: str
    budget: TokenBudget | None
    evaluation: EvaluationReference | None
    fingerprint: Digest


def resolve_capability(
    registry: CapabilityRegistry,
    *,
    profile_id: str | None,
    identity: RuntimeIdentity | None,
    task: str,
    locale: str,
) -> CapabilityDecision:
    """Resolve an explicitly selected profile after load_registry verification.

    No locale fallback, provider heuristic, best-profile search or model swap.
    A caller that constructs a registry directly is responsible for its trust.
    """

    profile = next((item for item in registry.profiles if item.id == profile_id), None)
    grant = None
    if not profile_id:
        reason = "profile_not_selected"
    elif profile is None:
        reason = "profile_unknown"
    elif profile.status != "approved":
        reason = "profile_not_approved"
    elif identity is None:
        reason = "runtime_identity_unavailable"
    elif profile.identity != identity:
        reason = "runtime_identity_mismatch"
    else:
        grant = next((item for item in profile.grants if (item.task, item.locale) == (task, locale)), None)
        reason = "reviewed_scope" if grant else "scope_not_reviewed"
    state = {
        "schema_version": registry.schema_version,
        "profile_id": profile_id,
        "profile": profile.model_dump(mode="json") if profile else None,
        "identity": identity.model_dump(mode="json") if identity else None,
        "task": task,
        "locale": locale,
        "reason": reason,
    }
    fingerprint = hashlib.sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return CapabilityDecision(
        mode="generated_explanation" if grant else "selected_evidence",
        reason=reason,
        profile_id=profile_id,
        profile_revision=profile.revision if profile else None,
        task=task,
        locale=locale,
        budget=grant.budget if grant else None,
        evaluation=grant.evaluation if grant else None,
        fingerprint=fingerprint,
    )
