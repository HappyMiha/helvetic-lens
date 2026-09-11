"""Extension boundary and populated-copy characterization, without live data."""

import hashlib
import sqlite3
from datetime import UTC, datetime

import pytest
from conftest import add_law, import_old
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from test_regulatory_corpus import federal_act

from helvetic_lens.config import Settings
from helvetic_lens.db import Database
from helvetic_lens.models import RegulatoryWork
from helvetic_lens.monitoring_contracts import MonitoringRollout, ReaderMode, RolloutGrant


def mode(policy, **overrides):
    return policy.reader_mode(**{
        "workspace_id": "personal-a", "template_id": "pollen-watch",
        "template_version": 1, "source_ready": True, "implementation_ready": True,
        **overrides,
    })


def grant(**overrides):
    return RolloutGrant(**{
        "workspace_id": "personal-a", "template_id": "pollen-watch",
        "template_version": 1, "mode": "enabled", **overrides,
    })


def test_rollout_requires_explicit_exact_workspace_template_version_and_source():
    policy = MonitoringRollout(enabled=True, grants=(grant(),))
    assert mode(policy) == ReaderMode.ENABLED
    for mismatch in (
        {"workspace_id": "company-b"}, {"template_id": "river-watch"},
        {"template_version": 2}, {"source_ready": False}, {"implementation_ready": False},
    ):
        assert mode(policy, **mismatch) == ReaderMode.LEGACY
    assert mode(MonitoringRollout()) == ReaderMode.LEGACY
    assert mode(MonitoringRollout(grants=(grant(),))) == ReaderMode.LEGACY


def test_kill_switch_and_ambiguous_configuration_never_enable_delivery():
    for grants in ((grant(), grant()), (grant(), grant(mode="shadow"))):
        assert mode(MonitoringRollout(enabled=True, grants=grants)) == ReaderMode.LEGACY
    shadow = MonitoringRollout(enabled=True, grants=(grant(mode="shadow"),))
    assert mode(shadow, source_ready=False) == ReaderMode.SHADOW
    assert mode(shadow, implementation_ready=False) == ReaderMode.LEGACY


def test_populated_database_copy_preserves_legacy_ids_artifacts_and_legal_constraints(harness, tmp_path, monkeypatch):
    # Stable pagination capture time permits exact response comparison.
    monkeypatch.setattr("helvetic_lens.timeline_pages.utcnow", lambda: datetime(2026, 9, 11, 12, tzinfo=UTC))
    client, _, service, _ = harness
    law = add_law(client)
    import_old(client, law["id"])
    before_api = client.get(f"/api/laws/{law['id']}").json()
    with service.db.session() as session:
        merged = service.regulatory_corpus.merge_document(session, federal_act())
        work_id = merged.work.id
        session.commit()

    original = tmp_path / "test.db"
    copied = tmp_path / "characterization-copy.db"
    with sqlite3.connect(original) as source, sqlite3.connect(copied) as target:
        source.backup(target)
    # Snapshot all populated records, including private state and evidence hashes.
    def rows(path):
        with sqlite3.connect(path) as connection:
            tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            return {name: sorted(connection.execute(f'SELECT * FROM "{name}"').fetchall(), key=repr)
                    for (name,) in tables}

    before_rows = rows(copied)
    assert any(before_rows.values())
    artifacts = {p.relative_to(service.settings.storage_path): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in service.settings.storage_path.rglob("*") if p.is_file()}
    assert artifacts
    db = Database(Settings(_env_file=None, database_url="sqlite:///" + copied.as_posix(),
                           data_dir=tmp_path / "copy-artifacts"))
    try:
        db.migrate()
        db.migrate()
        assert rows(copied) == before_rows
        with db.session() as session:
            assert session.scalar(select(RegulatoryWork).where(RegulatoryWork.id == work_id)).kind == "act"
            session.add(RegulatoryWork(kind="pollen_observation", authority="test", canonical_key="station"))
            with pytest.raises(IntegrityError, match="ck_regulatory_work_kind"):
                session.commit()
            session.rollback()
        assert rows(copied) == before_rows
    finally:
        db.engine.dispose()
    assert client.get(f"/api/laws/{law['id']}").json() == before_api
    assert rows(original) == before_rows
    assert artifacts == {p.relative_to(service.settings.storage_path): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in service.settings.storage_path.rglob("*") if p.is_file()}
