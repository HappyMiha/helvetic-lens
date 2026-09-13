"""Pure full/delta reconciliation before the permitted source store commits.

No notification or road-safety inference: revocation ends a source notice, not
necessarily the physical closure. Absence, stale observations and explicit end
are different facts. This state must be persisted atomically by its future
collector alongside source permission, continuity and original evidence hashes.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal

from .road_feed import RoadFeedError, RoadSituation, RoadSnapshot

MAX_RETAINED_SITUATIONS = 20_000


@dataclass(frozen=True)
class StoredRoadSituation:
    situation: RoadSituation
    seen_at: datetime
    present: bool


@dataclass(frozen=True)
class RoadSourceState:
    supplier: tuple[str, str]
    published_at: datetime
    snapshot_hash: str
    situations: tuple[StoredRoadSituation, ...]


@dataclass(frozen=True)
class RoadSourceChange:
    development_id: str
    source_id: str
    kind: Literal["created", "material_changed", "revoked", "source_refreshed", "source_unavailable", "source_restored"]
    previous_hash: str | None
    current_hash: str


def reconcile_road_snapshot(
    previous: RoadSourceState | None,
    snapshot: RoadSnapshot,
    *,
    mode: Literal["full", "delta"],
    continuous: bool,
) -> tuple[RoadSourceState, tuple[RoadSourceChange, ...]]:
    """Return a replacement and changes together; errors leave prior state intact.

    `continuous` comes from validated retrieval history, never from XML claims.
    A delta needs an existing full baseline. A lost delta window invalidates
    unseen situations until explicit evidence returns; it cannot cancel them.
    Historical entries are bounded and cannot be silently dropped to make room.
    """
    if mode not in {"full", "delta"} or type(continuous) is not bool:
        raise RoadFeedError("road_reconciliation_mode")
    if previous is None and mode != "full":
        raise RoadFeedError("road_full_baseline_required")
    if previous and previous.supplier != snapshot.supplier:
        raise RoadFeedError("road_reconciliation_supplier")
    if previous and snapshot.published_at < previous.published_at:
        raise RoadFeedError("road_publication_rollback")
    entries = {} if previous is None else {entry.situation.source_id: entry for entry in previous.situations}
    changes, seen = [], set()
    for current in snapshot.situations:
        old = entries.get(current.source_id)
        seen.add(current.source_id)
        current_hash = current.semantic_hash
        old_hash = None if old is None else old.situation.semantic_hash
        if old:
            before = old.situation
            if current.development_id != before.development_id:
                raise RoadFeedError("road_development_identity_changed")
            if current.version_at < before.version_at or current.source_version < before.source_version:
                raise RoadFeedError("road_situation_rollback")
            if current.version_at == before.version_at and current.source_version == before.source_version and current_hash != old_hash:
                raise RoadFeedError("road_conflicting_revision")
            old_records = {record.source_id: record for record in before.records}
            for record in current.records:
                prior_record = old_records.get(record.source_id)
                if prior_record is None:
                    continue
                if record.created_at != prior_record.created_at:
                    raise RoadFeedError("road_record_identity_reused")
                if record.version_at < prior_record.version_at or record.source_version < prior_record.source_version:
                    raise RoadFeedError("road_record_rollback")
                if (record.version_at == prior_record.version_at and record.source_version == prior_record.source_version
                        and record.semantic_hash != prior_record.semantic_hash):
                    raise RoadFeedError("road_conflicting_record_revision")
        if current.cancelled and (old is None or not old.situation.cancelled):
            kind = "revoked"
        elif old is None:
            kind = "created"
        elif current_hash != old_hash:
            kind = "material_changed"
        elif not old.present:
            kind = "source_restored"
        else:
            kind = "source_refreshed"
        entries[current.source_id] = StoredRoadSituation(current, snapshot.published_at, True)
        changes.append(RoadSourceChange(current.development_id, current.source_id, kind, old_hash, current_hash))
    if mode == "full" or not continuous:
        for source_id, entry in tuple(entries.items()):
            if source_id not in seen and entry.present:
                entries[source_id] = replace(entry, present=False)
                identity = entry.situation
                changes.append(RoadSourceChange(identity.development_id, source_id, "source_unavailable",
                    identity.semantic_hash, identity.semantic_hash))
    if len(entries) > MAX_RETAINED_SITUATIONS:
        raise RoadFeedError("road_retained_situation_limit")
    return RoadSourceState(snapshot.supplier, snapshot.published_at, snapshot.sha256,
        tuple(entries[key] for key in sorted(entries))), tuple(sorted(changes, key=lambda c: c.source_id))
