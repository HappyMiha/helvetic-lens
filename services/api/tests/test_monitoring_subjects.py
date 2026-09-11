"""C01a persistence and tenant/owner boundaries on an isolated migrated database."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from alembic import command
from helvetic_lens import monitoring_subjects as subjects
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.db import Database
from helvetic_lens.models import (
    MonitoringSubject,
    MonitoringSubjectRevision,
    Organization,
    OrganizationMembership,
    User,
)


@pytest.fixture
def db(tmp_path):
    url = f"sqlite:///{(tmp_path / 'subjects.db').as_posix()}"
    postgres = os.environ.get("MV2_SUBJECT_TEST_DATABASE_URL")
    admin, schema = None, None
    if postgres:
        parsed = make_url(postgres)
        if parsed.host != "127.0.0.1" or parsed.database != "mv2_c01_test":
            raise ValueError("PostgreSQL rehearsal requires the explicit isolated local test database")
        admin = create_engine(parsed)
        schema = "mv2_c01_" + uuid4().hex
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        url = parsed.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    database = Database(Settings(_env_file=None, database_url=url,
                                 data_dir=tmp_path / "data"), organization_id="org-a")
    database.migrate()
    with database.session(include_all_organizations=True) as session:
        session.add_all([Organization(id="org-a", name="A", slug="a"), Organization(id="org-b", name="B", slug="b")])
        session.add_all([User(id=user, email=f"{user}@example.test", name=user, password_hash="synthetic-unused")
                         for user in ("owner", "peer", "viewer")])
        session.flush()
        session.add_all([OrganizationMembership(organization_id=org, user_id=user, role=role)
                         for org, user, role in (("org-a", "owner", "organization_admin"),
                                                 ("org-a", "peer", "organization_admin"),
                                                 ("org-a", "viewer", "viewer"),
                                                 ("org-b", "owner", "organization_admin"))])
        session.commit()
    yield database
    database.engine.dispose()
    if admin:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def config(station="PBS"):
    return {"station_id": station, "selections": [{"allergen": "birch"}, {"allergen": "grasses"}]}


def create(db, key="request-a"):
    with db.session() as session:
        result = subjects.create_draft(session, user_id="owner", request_key=key, configuration=config())
        session.commit()
        return result


def test_draft_survives_new_session_replay_and_keeps_revision_history(db):
    initial = create(db)
    with db.session() as session:
        replay = subjects.create_draft(session, user_id="owner", request_key="request-a", configuration=config())
        assert replay == initial
        revised = subjects.revise_draft(session, user_id="owner", subject_id=initial["id"],
                                        expected_revision=1, configuration=config("PZH"))
        session.commit()
    db.migrate()  # Repeated upgrade cannot drop stored drafts or revisions.
    with db.session() as session:
        assert subjects.get_subject(session, user_id="owner", subject_id=initial["id"]) == revised
        history = subjects.subject_history(session, user_id="owner", subject_id=initial["id"])
        assert [row["configuration"]["station_id"] for row in history] == ["PZH", "PBS"]
        replay = subjects.create_draft(session, user_id="owner", request_key="request-a", configuration=config())
        assert replay["revision"] == 2  # Retry original creation never reverts a later edit.
        assert len(subjects.list_subjects(session, user_id="owner")) == 1
        with pytest.raises(DomainError, match="different settings"):
            subjects.create_draft(session, user_id="owner", request_key="request-a", configuration=config("PZH"))


def test_owner_and_organization_scope_also_apply_to_history_and_delete(db):
    record = create(db)
    with db.session() as session:
        assert subjects.list_subjects(session, user_id="peer") == []
        for read in (subjects.get_subject, subjects.subject_history):
            with pytest.raises(DomainError) as denied:
                read(session, user_id="peer", subject_id=record["id"])
            assert denied.value.status == 404
        with pytest.raises(DomainError) as denied:
            subjects.delete_draft(session, user_id="peer", subject_id=record["id"], expected_revision=1)
        assert denied.value.status == 404
        # Reusing another owner's key produces a different private draft.
        peer = subjects.create_draft(session, user_id="peer", request_key="request-a", configuration=config())
        assert peer["id"] != record["id"]
        session.commit()
    with db.organization_context("org-b"), db.session() as session:
        assert subjects.list_subjects(session, user_id="owner") == []
        assert list(session.scalars(select(MonitoringSubject))) == []
        assert list(session.scalars(select(MonitoringSubjectRevision))) == []
        with pytest.raises(DomainError) as denied:
            subjects.get_subject(session, user_id="owner", subject_id=record["id"])
        assert denied.value.status == 404


def test_revocation_and_inactive_user_are_checked_again_after_cached_read(db):
    record = create(db)
    with db.session() as session:
        subjects.get_subject(session, user_id="owner", subject_id=record["id"])
        with db.engine.begin() as connection:
            connection.execute(update(OrganizationMembership).where(
                OrganizationMembership.user_id == "owner", OrganizationMembership.organization_id == "org-a",
            ).values(role="viewer"))
        assert subjects.get_subject(session, user_id="owner", subject_id=record["id"])["revision"] == 1
        with pytest.raises(DomainError) as denied:
            subjects.revise_draft(session, user_id="owner", subject_id=record["id"], expected_revision=1,
                                  configuration=config("PZH"))
        assert denied.value.status == 403
        with db.engine.begin() as connection:
            connection.execute(update(User).where(User.id == "owner").values(active=False))
        with pytest.raises(DomainError) as denied:
            subjects.get_subject(session, user_id="owner", subject_id=record["id"])
        assert denied.value.status == 403
    with db.session() as session, pytest.raises(DomainError):
        subjects.create_draft(session, user_id="viewer", request_key="blocked", configuration=config())


def test_stale_editor_cannot_overwrite_or_delete_a_newer_revision(db):
    record = create(db)
    with db.session() as first, db.session() as second:
        subjects.get_subject(second, user_id="owner", subject_id=record["id"])
        subjects.revise_draft(first, user_id="owner", subject_id=record["id"], expected_revision=1,
                              configuration=config("PZH"))
        first.commit()
        with pytest.raises(DomainError) as conflict:
            subjects.revise_draft(second, user_id="owner", subject_id=record["id"], expected_revision=1,
                                  configuration=config("PGE"))
        assert conflict.value.status == 409
        with pytest.raises(DomainError) as conflict:
            subjects.delete_draft(second, user_id="owner", subject_id=record["id"], expected_revision=1)
        assert conflict.value.status == 409
        second.commit()
    with db.session() as session:
        assert len(subjects.subject_history(session, user_id="owner", subject_id=record["id"])) == 2
        assert subjects.get_subject(session, user_id="owner", subject_id=record["id"])["configuration"]["station_id"] == "PZH"


def test_caller_rollback_cancels_creation_and_revision_atomically(db):
    with db.session() as session:
        subjects.create_draft(session, user_id="owner", request_key="rolled-back", configuration=config())
        session.rollback()
    with db.session() as session:
        assert subjects.list_subjects(session, user_id="owner") == []
    record = create(db)
    with db.session() as session:
        subjects.revise_draft(session, user_id="owner", subject_id=record["id"], expected_revision=1,
                              configuration=config("PZH"))
        session.rollback()
    with db.session() as session:
        assert subjects.get_subject(session, user_id="owner", subject_id=record["id"])["revision"] == 1
        assert len(subjects.subject_history(session, user_id="owner", subject_id=record["id"])) == 1


def test_delete_removes_private_history_and_cross_org_fk_is_rejected(db):
    record = create(db)
    with db.session() as session:
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(MonitoringSubjectRevision(subject_id=record["id"], organization_id="org-b", revision=2,
                                                  configuration_json=config(), configuration_hash="0" * 64))
            session.flush()
        subjects.delete_draft(session, user_id="owner", subject_id=record["id"], expected_revision=1)
        session.commit()
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(MonitoringSubjectRevision)) == 0
        assert subjects.list_subjects(session, user_id="owner") == []


def test_invalid_configuration_does_not_create_rows_or_disclose_private_input(db):
    with db.session() as session:
        with pytest.raises(DomainError) as invalid:
            subjects.create_draft(session, user_id="owner", request_key="bad", configuration={
                **config(), "home_address": "PRIVATE VALUE",
            })
        assert invalid.value.status == 422
        assert "PRIVATE VALUE" not in str(invalid.value)
        assert subjects.list_subjects(session, user_id="owner") == []


def test_simultaneous_creation_has_one_subject_and_one_revision(db):
    barrier = Barrier(2)

    def attempt():
        with db.session() as session:
            barrier.wait(timeout=10)
            result = subjects.create_draft(session, user_id="owner", request_key="simultaneous", configuration=config())
            session.commit()
            return result["id"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(attempt), pool.submit(attempt)
        assert first.result(timeout=20) == second.result(timeout=20)
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(MonitoringSubject)) == 1
        assert session.scalar(select(func.count()).select_from(MonitoringSubjectRevision)) == 1


def test_draft_operations_cannot_modify_an_active_subject(db):
    record = create(db)
    with db.session() as session:
        session.execute(update(MonitoringSubject).where(MonitoringSubject.id == record["id"]).values(status="active"))
        session.commit()
        with pytest.raises(DomainError) as denied:
            subjects.revise_draft(session, user_id="owner", subject_id=record["id"], expected_revision=1,
                                  configuration=config("PZH"))
        assert denied.value.status == 409
        with pytest.raises(DomainError) as denied:
            subjects.delete_draft(session, user_id="owner", subject_id=record["id"], expected_revision=1)
        assert denied.value.status == 409


def test_upgrade_from_previous_schema_preserves_existing_identity_rows(db):
    migration = Config()
    migration.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    with db.engine.begin() as connection:
        migration.attributes["connection"] = connection
        command.downgrade(migration, "ef5169a0c32d")  # New subject tables are empty in this fixture.
        before = {model.__tablename__: connection.execute(select(model.__table__).order_by(model.id)).all()
                  for model in (Organization, User, OrganizationMembership)}
        command.upgrade(migration, "head")
        for model in (Organization, User, OrganizationMembership):
            assert connection.execute(select(model.__table__).order_by(model.id)).all() == before[model.__tablename__]
    record = create(db)
    assert record["status"] == "draft"
