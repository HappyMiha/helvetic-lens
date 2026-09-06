"""Typed launch snapshots; execution pins and reusable identity are distinct."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ai_capabilities import RuntimeIdentity

Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class Snapshot(BaseModel):
    # Keep only known metadata; provider extensions must not enter provenance.
    model_config = ConfigDict(extra="ignore", frozen=True, strict=True)


class DeviceSnapshot(Snapshot):
    index: int = Field(ge=0, le=255)
    name: str = Field(max_length=200)
    vram_bytes: int = Field(ge=0)
    compute_capability: str | None = Field(default=None, max_length=30)


class HardwareSnapshot(Snapshot):
    cuda_devices: list[DeviceSnapshot] = Field(default_factory=list, max_length=16)
    ram_bytes: int | None = Field(default=None, ge=0)


class RuntimeSnapshot(Snapshot):
    schema_version: Literal["local-runtime-binding-v1"]
    available: Literal[True]
    deployment_id: Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
    binding_fingerprint: Digest
    model_id: str = Field(min_length=1, max_length=200)
    served_model_id: str = Field(min_length=1, max_length=200)
    model_revision: str = Field(min_length=1, max_length=200)
    artifact_sha256: Digest
    identity: RuntimeIdentity | None = None
    context_window_tokens: int = Field(ge=1, le=1048576)
    default_output_tokens: int = Field(ge=1, le=1048576)
    quantization: str | None = Field(default=None, max_length=60)
    runtime_image: str | None = Field(default=None, max_length=500)
    hardware_profile: str | None = Field(default=None, max_length=200)
    hardware: HardwareSnapshot = Field(default_factory=HardwareSnapshot)

    @field_validator("available", mode="before")
    @classmethod
    def explicit_ready(cls, value):
        if value is not True:
            raise ValueError("Only an explicitly available deployment can be bound.")
        return value

    @model_validator(mode="after")
    def consistent_identity(self):
        if self.identity is not None:
            for key in ("model_id", "model_revision", "artifact_sha256"):
                if getattr(self, key) != getattr(self.identity, key):
                    raise ValueError("The active model descriptor disagrees with its immutable identity.")
            if self.hardware_profile is not None and self.hardware_profile != self.identity.hardware_profile:
                raise ValueError("The active hardware profile disagrees with its immutable identity.")
        return self

    def identity_fingerprint(self) -> str | None:
        """Stable across restarts, but absent when immutable identity is unknown."""
        if self.identity is None:
            return None
        state = {
            "schema_version": "runtime-identity-v1",
            "identity": self.identity.model_dump(mode="json"),
            "served_model_id": self.served_model_id,
            "context_window_tokens": self.context_window_tokens,
            "default_output_tokens": self.default_output_tokens,
        }
        return hashlib.sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def cache_identity(self) -> dict[str, str]:
        """Reuse identical immutable inputs, or only this partially known launch."""
        identity = self.identity_fingerprint()
        return {
            "schema_version": "local-runtime-cache-v1",
            "scope": "immutable_identity" if identity else "deployment",
            "fingerprint": identity or self.binding_fingerprint,
        }
