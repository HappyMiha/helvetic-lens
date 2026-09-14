"""Pure CAP predecessor ledger; durable acquisition and rights remain separate.

No missing-message or clock transition creates an all-clear. The caller must
persist each returned replacement atomically with its reviewed source permission.
Unresolved references, conflicting branches and unsupported mergers leave the
previous state intact; they cannot silently replace a known warning.
"""

import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime

from .hazard_cap import CAPMessage, material_change, reject

MAX_MESSAGES = 2000
MAX_RETAINED_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class StoredHazard:
    message: CAPMessage
    development_id: str
    material_sequence: int
    last_seen_at: datetime
    retained_bytes: int
    history_complete: bool = True


@dataclass(frozen=True)
class HazardHead:
    development_id: str
    current_key: str
    material_sequence: int
    state: str


@dataclass(frozen=True)
class HazardSourceState:
    sender: str
    messages: tuple[StoredHazard, ...]
    heads: tuple[HazardHead, ...]


@dataclass(frozen=True)
class HazardSourceChange:
    development_id: str
    message_key: str
    previous_keys: tuple[str, ...]
    kind: str
    material_sequence: int
    material: bool
    history_complete: bool = True


def reconcile_cap(previous: HazardSourceState | None, message: CAPMessage, *, allow_initial_update=False):
    """Return new state/change together; no database/network/owner side effects.

    Only an explicitly referenced current head may be replaced. Joining unrelated
    warning histories needs a separately supported source contract. Message expiry
    is a presentation freshness decision, never a synthetic resolved revision.
    """
    if message.unsupported:
        reject("hazard_unsupported_contract")
    if previous and previous.sender != message.identity.sender:
        reject("hazard_source_sender_changed")
    entries = {} if previous is None else {e.message.identity.key: e for e in previous.messages}
    heads = {} if previous is None else {h.development_id: h for h in previous.heads}
    current_key = message.identity.key
    old = entries.get(current_key)
    if old:
        # CAP IDs are immutable. A different byte-level publication reusing one
        # needs explicit operator/source resolution, not a hidden content rewrite.
        if old.message.evidence_hash != message.evidence_hash:
            reject("hazard_conflicting_identity")
        if message.received_at < old.last_seen_at:
            reject("hazard_receipt_rollback")
        entries[current_key] = replace(old, last_seen_at=message.received_at)
        change = HazardSourceChange(old.development_id, current_key,
            tuple(r.key for r in message.references), "refreshed", old.material_sequence, False, old.history_complete)
        return HazardSourceState(message.identity.sender, tuple(entries.values()), tuple(heads.values())), change
    if any(e.message.identity.identifier == message.identity.identifier for e in entries.values()):
        reject("hazard_identifier_reused")
    if any(ref.identifier == known.message.identity.identifier and ref.key != known.message.identity.key
           for ref in message.references for known in entries.values()):
        reject("hazard_reference_identity_conflict")
    if (allow_initial_update and any(message.identity in known.message.references for known in entries.values())):
        reject("hazard_late_missing_predecessor")
    if len(entries) >= MAX_MESSAGES:
        reject("hazard_history_limit")
    size = len(json.dumps(asdict(message), ensure_ascii=False, default=str, separators=(",", ":")).encode())
    if size + sum(e.retained_bytes for e in entries.values()) > MAX_RETAINED_BYTES:
        reject("hazard_history_byte_limit")
    history_complete = True
    if message.message_type == "Alert":
        development_id, sequence, kind = current_key, 1, "created"
    elif (allow_initial_update and message.profile == "meteoalarm-v2" and message.message_type == "Update"
          and message.references and all(r.key not in entries for r in message.references)):
        # An active-only feed can begin mid-history. Retain the exact Update and
        # its unresolved references; neither invent an Alert nor claim a diff.
        # A later receipt of older history never silently rewrites this root.
        development_id, sequence, kind, history_complete = current_key, 1, "imported", False
    else:
        if any(r.key not in entries for r in message.references):
            reject("hazard_predecessor_missing")
        referenced = [entries[r.key] for r in message.references]
        developments = {e.development_id for e in referenced}
        if len(developments) != 1:
            reject("hazard_unverified_history_merge")
        development_id = referenced[0].development_id
        head = heads[development_id]
        # Do not let a late sibling or a Cancel of an older ancestor close a
        # newer head. CAP replaces only the explicitly referenced message(s).
        if any(e.message.identity.key != head.current_key for e in referenced):
            reject("hazard_reference_superseded")
        if head.state == "cancelled":
            reject("hazard_cancelled_history_requires_new_alert")
        before = referenced[0].message
        history_complete = referenced[0].history_complete
        kind = material_change(before, message)
        if kind == "unavailable":
            reject("hazard_unsupported_contract")
        sequence = head.material_sequence + int(kind != "refreshed")
    entries[current_key] = StoredHazard(message, development_id, sequence, message.received_at, size, history_complete)
    heads[development_id] = HazardHead(development_id, current_key, sequence, message.state)
    change = HazardSourceChange(development_id, current_key, tuple(r.key for r in message.references),
                                kind, sequence, kind != "refreshed", history_complete)
    return HazardSourceState(message.identity.sender, tuple(entries.values()), tuple(heads.values())), change
