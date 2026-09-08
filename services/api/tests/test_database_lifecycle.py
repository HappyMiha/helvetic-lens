"""Release transient migration/engine graphs without weakening tenant filters."""

import gc
import weakref

import pytest
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Column, Integer, MetaData, Table, select, text

from helvetic_lens.config import Settings
from helvetic_lens.db import Database


def database(tmp_path):
    return Database(Settings(_env_file=None, database_url="sqlite:///:memory:", data_dir=tmp_path))


def test_disposed_database_is_not_retained_by_session_event_registry(tmp_path):
    references = []
    for _ in range(3):
        db = database(tmp_path)
        with db.session() as session:
            assert session.scalar(text("SELECT 1")) == 1
        references.extend((weakref.ref(db), weakref.ref(db.engine), weakref.ref(db._session_factory.class_)))
        db.engine.dispose()
        del session, db
    gc.collect()
    assert all(reference() is None for reference in references)


def test_completed_migration_context_is_released_while_database_stays_open(tmp_path, monkeypatch):
    references = []
    configure = MigrationContext.configure

    def observe(*args, **kwargs):
        context = configure(*args, **kwargs)
        references.append(weakref.ref(context))
        return context

    monkeypatch.setattr(MigrationContext, "configure", observe)
    db = database(tmp_path)
    try:
        db.migrate()  # Real migration chain, not metadata.create_all or a skipped gate.
        gc.collect()
        assert references and all(reference() is None for reference in references)
        with db.session() as session:
            assert session.scalar(text("SELECT version_num FROM alembic_version"))
        db.migrate()  # Up-to-date startup remains valid.
        gc.collect()
        assert all(reference() is None for reference in references)
    finally:
        db.engine.dispose()


def test_failed_migration_does_not_leave_compiled_schema_or_connection_retained(tmp_path, monkeypatch):
    references = []
    configs = []

    def broken_upgrade(config, _revision):
        configs.append(config)
        connection = config.attributes["connection"]
        table = Table("synthetic_probe", MetaData(), Column("id", Integer, primary_key=True))
        table.create(connection)
        connection.execute(select(table)).all()
        references.extend((weakref.ref(table), weakref.ref(connection)))
        raise RuntimeError("Synthetic migration failure")

    monkeypatch.setattr("helvetic_lens.db.command.upgrade", broken_upgrade)
    db = database(tmp_path)
    try:
        # Do not retain exception tracebacks, which legitimately keep their locals.
        with pytest.raises(RuntimeError, match="Synthetic migration failure"):
            db.migrate()
        gc.collect()
        assert all(reference() is None for reference in references)
        assert "connection" not in configs[0].attributes
        with db.session() as session:
            assert session.scalar(text("SELECT 1")) == 1
    finally:
        db.engine.dispose()
