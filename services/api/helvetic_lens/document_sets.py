"""MV2-044 document observations; source adapters and private readers enforce rights.

No downloads, permission grants, OCR guesses or user-visible URLs are synthesized.
Reconcile only complete observations of one dossier in one access scope. Partial
listings retain missing entries as unavailable, never as proven removals.
"""

from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Access = Literal["available", "denied", "unavailable"]
Lifecycle = Literal["present", "withdrawn", "removed", "unknown"]
ParseStatus = Literal["complete", "failed", "not_attempted"]
Kind = Literal["document", "qa", "conditions"]
DeltaKind = Literal[
    "added", "discovered", "replaced", "removed", "withdrawn", "reinstated",
    "access_unavailable", "access_restored", "parse_degraded", "parse_recovered",
]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DocumentItem(Contract):
    item_id: str = Field(min_length=1, max_length=256)
    kind: Kind
    title: str = Field(min_length=1, max_length=1000)
    # Stable official landing page. Temporary download URLs belong in the
    # downloader only; signed query credentials must not enter persisted history.
    official_url: str = Field(max_length=2000)
    access: Access
    lifecycle: Literal["present", "withdrawn", "unknown"] = "present"
    content_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    snapshot_id: UUID | None = None
    parse_status: ParseStatus = "not_attempted"
    text_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    source_revision: str | None = Field(default=None, min_length=1, max_length=256)

    @field_validator("item_id", "title")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Document identity and title cannot be blank")
        return value

    @field_validator("official_url")
    @classmethod
    def landing_page(cls, value):
        url = urlsplit(value)
        if (
            url.scheme != "https" or not url.hostname or url.username or url.password
            or url.query or url.fragment or any(ord(c) < 33 for c in value)
        ):
            raise ValueError("Use a stable HTTPS evidence page without credentials, queries or fragments")
        return value

    @model_validator(mode="after")
    def evidence_binding(self):
        if self.access == "available":
            if self.content_sha256 is None or self.snapshot_id is None:
                raise ValueError("Available content requires a permitted exact stored snapshot")
            if (self.parse_status == "complete") != (self.text_sha256 is not None):
                raise ValueError("Parsed text fingerprint requires successful complete parsing")
        elif (
            self.content_sha256 is not None or self.snapshot_id is not None
            or self.text_sha256 is not None or self.parse_status != "not_attempted"
        ):
            raise ValueError("Unavailable observations cannot claim retrieved content")
        return self


class Manifest(Contract):
    contract_version: Literal[1] = 1
    observation_id: UUID
    source_id: str = Field(min_length=1, max_length=100)
    dossier_id: str = Field(min_length=1, max_length=256)
    access_scope_id: UUID
    observed_at: datetime
    coverage: Literal["complete", "partial", "unavailable"]
    items: tuple[DocumentItem, ...] = Field(default=(), max_length=2000)

    @field_validator("observed_at")
    @classmethod
    def aware_utc(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Manifest observation time must be timezone aware")
        return value.astimezone(UTC)

    @field_validator("source_id", "dossier_id")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Source and dossier identity must be explicit")
        return value

    @model_validator(mode="after")
    def unique_items(self):
        ids = [item.item_id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate document identity in manifest")
        if self.coverage == "unavailable" and self.items:
            raise ValueError("An unavailable listing cannot establish item observations")
        return self


class DocumentState(Contract):
    item_id: str
    kind: Kind
    access: Access
    lifecycle: Lifecycle
    current: DocumentItem | None
    last_available: DocumentItem | None
    first_seen_at: datetime
    last_seen_at: datetime


class ManifestState(Contract):
    observation: Manifest
    last_complete_at: datetime | None
    documents: tuple[DocumentState, ...]


class DocumentDelta(Contract):
    item_id: str
    item_kind: Kind
    kind: DeltaKind
    material: bool
    before_snapshot_id: UUID | None
    after_snapshot_id: UUID | None
    before_content_sha256: str | None
    after_content_sha256: str | None
    before_text_sha256: str | None = None
    after_text_sha256: str | None = None
    # True says exact parsed versions are available for a separate comparison;
    # it does NOT itself assert which requirement, sentence or deadline changed.
    parsed_comparison_available: bool


class Reconciliation(Contract):
    state: ManifestState
    deltas: tuple[DocumentDelta, ...]
    baseline: bool


def _delta(old, new, kind, *, item_id, item_kind):
    previous = old.last_available if old else None
    current = new if new and new.access == "available" else None
    return DocumentDelta(
        item_id=item_id, item_kind=item_kind, kind=kind,
        material=kind in {"added", "replaced", "removed", "withdrawn", "reinstated"},
        before_snapshot_id=previous.snapshot_id if previous else None,
        after_snapshot_id=current.snapshot_id if current else None,
        before_content_sha256=previous.content_sha256 if previous else None,
        after_content_sha256=current.content_sha256 if current else None,
        before_text_sha256=previous.text_sha256 if previous else None,
        after_text_sha256=current.text_sha256 if current else None,
        parsed_comparison_available=bool(
            previous and current and previous.parse_status == current.parse_status == "complete"
        ),
    )


def _canonical(manifest):
    data = manifest.model_dump(mode="json")
    data["items"] = sorted(data["items"], key=lambda item: item["item_id"])
    return data


def reconcile(previous: ManifestState | None, current: Manifest) -> Reconciliation:
    """Fold an observation while preserving identity through temporary loss.

    Callers atomically persist the state/history with source rights and ownership
    checks. Never share this scope's snapshots with a different organization's
    manifest. Old exact snapshots remain subject to current retention/read rights.
    """
    if previous:
        prior = previous.observation
        if (prior.source_id, prior.dossier_id, prior.access_scope_id) != (
            current.source_id, current.dossier_id, current.access_scope_id
        ):
            raise ValueError("Cannot reconcile different source, dossier or private access scopes")
        if current.observation_id == prior.observation_id:
            if _canonical(current) != _canonical(prior):
                raise ValueError("Conflicting payload for manifest observation identity")
            return Reconciliation(state=previous, deltas=(), baseline=False)
        if current.observed_at <= prior.observed_at:
            raise ValueError("Manifest observation must advance; do not replace current state with a replay")
    known = {item.item_id: item for item in previous.documents} if previous else {}
    incoming = {item.item_id: item for item in current.items}
    # Prevent unbounded union growth across partial pages/outages. A source adapter
    # must provide a reconciled listing, not feed each pagination page as a set.
    if len(known.keys() | incoming.keys()) > 4000:
        raise ValueError("Document history set exceeded supported bound")
    states, deltas = [], []
    for item_id in sorted(known.keys() | incoming.keys()):
        old, item = known.get(item_id), incoming.get(item_id)
        kind = item.kind if item else old.kind
        if old and item and old.kind != item.kind:
            raise ValueError("Document kind changed under the same provider identity")
        changes = []
        if item is None:
            access = "unavailable"
            if old.lifecycle in {"withdrawn", "removed"}:
                lifecycle = old.lifecycle
            elif current.coverage == "complete":
                lifecycle = "removed"
                changes.append("removed")
            else:
                lifecycle = old.lifecycle
                if old.access == "available":
                    changes.append("access_unavailable")
        else:
            access = item.access
            lifecycle = item.lifecycle if item.lifecycle != "unknown" else old.lifecycle if old else "unknown"
            if old is None:
                if previous:
                    # A complete earlier listing proves prior absence; first
                    # visibility after incomplete coverage only proves discovery.
                    changes.append(
                        "withdrawn" if item.lifecycle == "withdrawn"
                        else "added" if previous.last_complete_at and item.lifecycle == "present"
                        else "discovered"
                    )
            else:
                if lifecycle == "withdrawn" and old.lifecycle != "withdrawn":
                    changes.append("withdrawn")
                elif lifecycle == "present" and old.lifecycle in {"removed", "withdrawn"}:
                    changes.append("reinstated")
                if item.access == "available" and old.access != "available":
                    changes.append("access_restored")
                elif item.access != "available" and old.access == "available":
                    changes.append("access_unavailable")
                if item.access == "available" and old.last_available and old.last_available.content_sha256 != item.content_sha256:
                    changes.append("replaced")
                if item.access == "available" and old.current and old.current.access == "available" and old.current.content_sha256 == item.content_sha256:
                    if old.current.parse_status == "complete" and item.parse_status != "complete":
                        changes.append("parse_degraded")
                    elif old.current.parse_status != "complete" and item.parse_status == "complete":
                        changes.append("parse_recovered")
        last_available = item if item and item.access == "available" else old.last_available if old else None
        states.append(DocumentState(
            item_id=item_id, kind=kind, access=access, lifecycle=lifecycle, current=item,
            last_available=last_available, first_seen_at=old.first_seen_at if old else current.observed_at,
            last_seen_at=current.observed_at if item else old.last_seen_at,
        ))
        for change in changes:
            deltas.append(_delta(old, item, change, item_id=item_id, item_kind=kind))
    return Reconciliation(
        state=ManifestState(
            observation=current,
            last_complete_at=current.observed_at if current.coverage == "complete" else previous.last_complete_at if previous else None,
            documents=tuple(states),
        ),
        deltas=tuple(deltas), baseline=previous is None,
    )
