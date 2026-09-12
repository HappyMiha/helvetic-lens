"""MV2-001 versioned extension boundary; no source activation or database writes.

Consumers must authorize the workspace before consulting a rollout policy. A
policy grants a reader mode, never membership, source rights, or delivery consent.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_VERSION = 1


class ReaderMode(StrEnum):
    LEGACY = "legacy"
    SHADOW = "shadow"
    ENABLED = "enabled"


class RolloutGrant(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    template_version: int = Field(ge=1, strict=True)
    mode: ReaderMode


class MonitoringRollout(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    grants: tuple[RolloutGrant, ...] = ()

    def reader_mode(
        self, *, workspace_id: str, template_id: str, template_version: int,
        source_ready: bool, implementation_ready: bool,
    ) -> ReaderMode:
        """Fail closed, including ambiguous grants and unsupported implementations.

        Shadow may inspect retained fixtures without a live source. It must not
        enter user feeds, send notifications, or change authoritative legal data.
        """
        if not self.enabled or not implementation_ready:
            return ReaderMode.LEGACY
        matches = [grant for grant in self.grants if (
            grant.workspace_id == workspace_id
            and grant.template_id == template_id
            and grant.template_version == template_version
        )]
        # An exact workspace decision (including revocation or ambiguity) wins.
        # "*" is an explicit grant for current and future authenticated workspaces;
        # callers must still enforce membership and private subject ownership.
        if not matches:
            matches = [grant for grant in self.grants if (
                grant.workspace_id == "*"
                and grant.template_id == template_id
                and grant.template_version == template_version
            )]
        if len(matches) != 1:
            return ReaderMode.LEGACY
        mode = matches[0].mode
        if mode == ReaderMode.ENABLED and not source_ready:
            return ReaderMode.LEGACY
        return mode


def public_pollen_rollout() -> MonitoringRollout:
    """General Pollen availability; never grants source rights or email consent."""
    return MonitoringRollout(enabled=True, grants=(
        RolloutGrant(workspace_id="*", template_id="pollen-watch",
                     template_version=1, mode=ReaderMode.ENABLED),
    ))
