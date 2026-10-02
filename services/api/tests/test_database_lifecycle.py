"""Release transient migration/engine graphs without weakening tenant filters."""

import gc
import weakref

import pytest
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Column, Integer, MetaData, Table, select, text

from helvetic_lens.config import Settings
from helvetic_lens.db import Database


def test_warm_sql_filters_keep_tenants_aliases_and_new_rows_current(tmp_path):
    from sqlalchemy import func
    from sqlalchemy.orm import aliased

    from helvetic_lens.models import Law, Organization, Source

    db = database(tmp_path)
    db.migrate()
    tenant_a, tenant_b = 'filter-tenant-a', 'filter-tenant-b'
    try:
        with db.session(include_all_organizations=True) as session:
            session.add_all([Organization(id=key, name=key, slug=key) for key in (tenant_a, tenant_b)])
            session.commit()
            session.add_all([Source(organization_id=key, name=key, url='https://example.test/' + key)
                for key in (tenant_a, tenant_b)])
            session.add_all([Law(name=key, owner_organization_id=key,
                url='https://example.test/law/' + key) for key in (tenant_a, tenant_b)])
            session.add(Law(name='public', url='https://fedlex.admin.ch/eli/shared'))
            session.commit()
        source_alias, law_alias = aliased(Source), aliased(Law)
        with db.organization_context(tenant_a), db.session() as session:
            # Warming one tenant must not bind subsequent aliases or tenants to it.
            for key in (tenant_a, tenant_b, tenant_a):
                session.info['organization_id'] = key
                assert list(session.scalars(select(source_alias.name))) == [key]
                assert session.scalar(select(func.count()).select_from(Source)) == 1
                assert set(session.scalars(select(law_alias.name))) == {'public', key}
                assert set(session.scalars(select(Source.name).execution_options(include_all_organizations=True))) == {tenant_a, tenant_b}
                assert list(session.scalars(select(Source.name))) == [key]
            session.add(Source(name='new-after-warmup', url='https://example.test/new'))
            session.commit()
            assert set(session.scalars(select(source_alias.name))) == {tenant_a, 'new-after-warmup'}
            session.info['organization_id'] = tenant_b
            assert list(session.scalars(select(Source.name))) == [tenant_b]
        with db.organization_context(tenant_b), db.session() as session:
            assert set(session.scalars(select(Law.name))) == {'public', tenant_b}
    finally:
        db.engine.dispose()


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
