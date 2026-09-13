"""Bound public payload growth without expiring decision or comparison evidence.

The byte quota measures canonical UTF-8 JSON, not PostgreSQL/WAL/disk usage.
Private version counts are separately bounded per monitor. All referenced source
and field snapshots are pinned; only unreferenced public payloads expire.
"""

import json
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.exc import IntegrityError

from .config import DomainError
from .monitoring_subjects import _savepoint
from .tender_models import (
    TenderDossier,
    TenderDossierVersion,
    TenderMaterialSection,
    TenderPublicationSnapshot,
    TenderStorageState,
    TenderVersionSection,
)


@dataclass(frozen=True)
class StorageLimits:
    public_bytes: int = 2 * 1024**3
    monitor_versions: int = 10_000

    def __post_init__(self):
        if type(self.public_bytes) is not int or type(self.monitor_versions) is not int:
            raise ValueError("Storage limits must be integer application budgets")
        if self.public_bytes < 1 or self.monitor_versions < 1:
            raise ValueError("Storage limits must be positive")

    @classmethod
    def from_settings(cls, settings):
        return cls(
            getattr(settings, "tender_public_storage_max_bytes", cls.public_bytes),
            getattr(settings, "tender_monitor_max_versions", cls.monitor_versions),
        )


class StorageCapacity(DomainError):
    def __init__(self):
        super().__init__(
            "Tender storage is full. Existing evidence is preserved; collection is waiting.",
            503,
            "tender_storage_capacity",
        )


def payload_size(value):
    return len(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    )


def storage_lock(session):
    if session.get(TenderStorageState, "public") is None:
        try:
            with _savepoint(session):
                session.add(TenderStorageState(id="public", used_bytes=0))
                session.flush()
        except IntegrityError:
            pass
    # A real write serializes SQLite as well as PostgreSQL. Hold the same mutex
    # through inserts/deletes and their accounting until the outer commit.
    session.execute(
        update(TenderStorageState)
        .where(TenderStorageState.id == "public")
        .values(used_bytes=TenderStorageState.used_bytes)
        .execution_options(synchronize_session=False)
    )


def reserve(session, amount, limits):
    changed = session.execute(
        update(TenderStorageState)
        .where(
            TenderStorageState.id == "public",
            TenderStorageState.used_bytes + amount <= limits.public_bytes,
        )
        .values(used_bytes=TenderStorageState.used_bytes + amount)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        raise StorageCapacity()


def check_version_capacity(session, monitor, limits):
    # The caller holds the monitor lock, including all lots in one observation.
    count = session.scalar(
        select(func.count(TenderDossierVersion.id))
        .join(TenderDossier, TenderDossier.id == TenderDossierVersion.dossier_id)
        .where(
            TenderDossier.monitor_id == monitor.id,
            TenderDossier.organization_id == monitor.organization_id,
            TenderDossierVersion.organization_id == monitor.organization_id,
        )
    )
    if count >= limits.monitor_versions:
        raise StorageCapacity()


def collect_unreferenced(session, *, now, limit=100):
    """Bounded public-only GC. Core references deliberately span ALL tenants.

    No private evidence, dossier, decision or delivery row is deleted here.
    Foreign keys remain the final protection against concurrent reference use.
    """
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Invalid cleanup batch size")
    storage_lock(session)
    released, removed = 0, 0
    pairs = (
        (TenderPublicationSnapshot.__table__, TenderDossierVersion.__table__, "source_hash"),
        (TenderMaterialSection.__table__, TenderVersionSection.__table__, "section_id"),
    )
    for table, references, reference_key in pairs:
        available = ~exists(select(1).where(references.c[reference_key] == table.c.id))
        rows = session.execute(
            select(table.c.id, table.c.payload_bytes)
            .where(table.c.created_at < now - timedelta(days=7), available)
            .order_by(table.c.created_at, table.c.id)
            .limit(limit - removed)
        ).all()
        for identifier, size in rows:
            result = session.execute(delete(table).where(table.c.id == identifier, available))
            if result.rowcount == 1:
                released += size
                removed += 1
    session.execute(
        update(TenderStorageState)
        .where(TenderStorageState.id == "public")
        .values(used_bytes=TenderStorageState.used_bytes - released)
        .execution_options(synchronize_session=False)
    )
    return {"removed_public_payloads": removed, "released_payload_bytes": released}
