"""Exact parsed document comparisons for MV2-044, with no inferred requirements.

The source/private store must validate current read rights on every loader call.
This module does not download content, grant rights, or trust a cached comparison
as permission to reveal either version. All text is source data, never instructions.
"""

import hashlib
import json
import re
from collections.abc import Callable
from difflib import SequenceMatcher
from typing import Literal
from uuid import UUID

from pydantic import Field, ValidationError, field_validator, model_validator

from .document_sets import Contract, DocumentDelta, Manifest, ManifestState, Reconciliation, reconcile

MAX_PASSAGES = 2000
MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_CHANGES = 100
MAX_EXCERPT = 2000


class Passage(Contract):
    locator: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=20000)
    page: int | None = Field(default=None, strict=True, ge=1)

    @field_validator("locator", "text")
    @classmethod
    def nonblank(cls, value):
        if not value.strip() or "\x00" in value:
            raise ValueError("Passages require nonblank text and a source locator")
        return value


def text_fingerprint(passages):
    """Hash the exact parsed projection, including order and original locators."""
    payload = [item.model_dump(mode="json") for item in passages]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


class ParsedDocument(Contract):
    snapshot_id: UUID
    access_scope_id: UUID
    source_id: str = Field(min_length=1, max_length=100)
    dossier_id: str = Field(min_length=1, max_length=256)
    item_id: str = Field(min_length=1, max_length=256)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    extractor_version: str = Field(min_length=1, max_length=100)
    language: str = Field(min_length=2, max_length=20)
    # Partial/failed extraction cannot establish removed or unchanged text.
    parse_status: Literal["complete", "partial", "failed"]
    passages: tuple[Passage, ...] = Field(default=(), max_length=MAX_PASSAGES)

    @model_validator(mode="after")
    def integrity(self):
        if len({item.locator for item in self.passages}) != len(self.passages):
            raise ValueError("Source passage locators must be unique within a snapshot")
        if sum(len(item.text.encode()) for item in self.passages) > MAX_TEXT_BYTES:
            raise ValueError("Parsed document exceeds the supported comparison bound")
        if text_fingerprint(self.passages) != self.text_sha256:
            raise ValueError("Parsed content does not match its stored fingerprint")
        if self.parse_status == "complete" and not self.passages:
            raise ValueError("Empty extraction cannot establish complete document text")
        return self


class Excerpt(Contract):
    snapshot_id: UUID
    locator: str
    page: int | None
    # Exact original substring; no model rewrite, normalization or invented locator.
    text: str
    truncated: bool


class TextChange(Contract):
    kind: Literal["added", "removed", "replaced"]
    before: tuple[Excerpt, ...]
    after: tuple[Excerpt, ...]


class Comparison(Contract):
    schema_version: Literal[1] = 1
    item_id: str
    status: Literal["changed", "unchanged", "unavailable"]
    reason: Literal["text_compared", "read_unavailable", "parse_incomplete", "extractor_changed", "language_changed", "evidence_mismatch"]
    before_snapshot_id: UUID | None
    after_snapshot_id: UUID | None
    changes: tuple[TextChange, ...] = ()
    # Counts are complete even when the bounded reader payload omits later hunks.
    total_changes: int = 0
    truncated: bool = False


def _key(passage):
    # Only whitespace is cosmetic. Case, punctuation, negation, numbers, product
    # identifiers and leading labels may all affect procurement requirements.
    return re.sub(r"\s+", " ", passage.text).strip()


def _excerpt(document, passage):
    return Excerpt(snapshot_id=document.snapshot_id, locator=passage.locator,
                   page=passage.page, text=passage.text[:MAX_EXCERPT],
                   truncated=len(passage.text) > MAX_EXCERPT)


def compare_documents(delta: DocumentDelta, manifest: Manifest,
                      load: Callable[[UUID], ParsedDocument | None]) -> Comparison:
    """Load both exact originals through a scope-bound current-rights reader.

    None from the reader means unavailable. Storage/network exceptions propagate
    so callers cannot persist a successful comparison after an operational error.
    Retained comparison output must be rights-rechecked again before any response.
    """
    base = dict(item_id=delta.item_id, before_snapshot_id=delta.before_snapshot_id,
                after_snapshot_id=delta.after_snapshot_id)

    def unavailable(reason):
        return Comparison(**base, status="unavailable", reason=reason)

    if not delta.parsed_comparison_available or not delta.before_snapshot_id or not delta.after_snapshot_id:
        return unavailable("parse_incomplete")
    before, after = load(delta.before_snapshot_id), load(delta.after_snapshot_id)
    if before is None or after is None:
        return unavailable("read_unavailable")
    for document, snapshot, content, parsed_hash in (
        (before, delta.before_snapshot_id, delta.before_content_sha256, delta.before_text_sha256),
        (after, delta.after_snapshot_id, delta.after_content_sha256, delta.after_text_sha256),
    ):
        if (document.snapshot_id != snapshot or document.content_sha256 != content
                or document.access_scope_id != manifest.access_scope_id
                or document.source_id != manifest.source_id
                or document.dossier_id != manifest.dossier_id
                or document.item_id != delta.item_id or document.text_sha256 != parsed_hash):
            return unavailable("evidence_mismatch")
        # model_copy/store deserialization must not bypass bounds or integrity.
        try:
            ParsedDocument.model_validate(document.model_dump())
        except ValidationError:
            return unavailable("evidence_mismatch")
        if document.parse_status != "complete":
            return unavailable("parse_incomplete")
    if before.extractor_version != after.extractor_version:
        return unavailable("extractor_changed")
    if before.language != after.language:
        return unavailable("language_changed")
    changes, total, truncated = [], 0, False
    for kind, i, j, k, m in SequenceMatcher(
        None, [_key(p) for p in before.passages], [_key(p) for p in after.passages],
        autojunk=False,
    ).get_opcodes():
        if kind == "equal":
            continue
        total += 1
        if len(changes) >= MAX_CHANGES:
            truncated = True
            continue
        # One huge replaced section cannot bypass the response payload bound.
        left = tuple(_excerpt(before, p) for p in before.passages[i:min(j, i + 10)])
        right = tuple(_excerpt(after, p) for p in after.passages[k:min(m, k + 10)])
        truncated |= j - i > 10 or m - k > 10 or any(p.truncated for p in (*left, *right))
        changes.append(TextChange(kind={"replace": "replaced", "insert": "added", "delete": "removed"}[kind],
                                  before=left, after=right))
    return Comparison(**base, status="changed" if total else "unchanged", reason="text_compared",
                      changes=tuple(changes), total_changes=total, truncated=truncated)


class ComparedObservation(Contract):
    reconciliation: Reconciliation
    comparisons: tuple[Comparison, ...]


def reconcile_documents(previous: ManifestState | None, current: Manifest,
                        load: Callable[[UUID], ParsedDocument | None]) -> ComparedObservation:
    """Reconcile the set and compare changed bytes without weakening its deltas.

    A changed binary with equal text is still a file replacement. A failed/denied
    comparison never means requirements are unchanged. Source readers supply
    listings; do not call this with an individual page of a paginated listing.
    """
    result = reconcile(previous, current)
    return ComparedObservation(reconciliation=result, comparisons=tuple(
        compare_documents(delta, current, load) for delta in result.deltas if delta.kind == "replaced"
    ))
