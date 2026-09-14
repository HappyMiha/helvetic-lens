"""Additive schema checks; application ownership and source adapters remain separate."""
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from alembic import command
from helvetic_lens.db import Base
from helvetic_lens.models import User
from helvetic_lens.related_models import RelatedStory, RelatedStoryRevision

db = _database_fixture
template = _template_fixture


def story(organization):
    return RelatedStory(id=str(uuid4()), organization_id=organization, owner_user_id="owner",
        request_key=str(uuid4()), request_hash="a" * 64, title="Private location story")


def revision(row, *, organization=None, number=1):
    return RelatedStoryRevision(story_id=row.id, organization_id=organization or row.organization_id,
        revision=number, request_key=str(uuid4()), request_hash="b" * 64, action="create",
        snapshot={"members": []}, fingerprint="c" * 64)


def test_schema_matches_orm_and_round_trip_preserves_existing_accounts(db):
    with db.engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True,
            "include_object": lambda obj, name, kind, reflected, compare: kind != "table" or name.startswith("related_")})
        assert compare_metadata(context, Base.metadata) == []
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "2b08e9a24acd")
        assert not any(name.startswith("related_") for name in inspect(connection).get_table_names())
        command.upgrade(config, "head")
        assert {"related_stories", "related_story_revisions", "related_place_bindings"} <= set(inspect(connection).get_table_names())
    with db.session() as session:
        assert session.get(User, "owner").email == "owner@example.test"


def test_story_and_revision_are_in_central_tenant_policy(db):
    first, other = story("org-a"), story("org-b")
    with db.session(include_all_organizations=True) as session:
        session.add_all((first, other))
        session.flush()
        session.add_all((revision(first), revision(other)))
        session.commit()
    with db.session() as session:
        assert [row.id for row in session.scalars(select(RelatedStory))] == [first.id]
        assert [row.story_id for row in session.scalars(select(RelatedStoryRevision))] == [first.id]
    with db.session(include_all_organizations=True) as session:
        assert len(list(session.scalars(select(RelatedStory)))) == 2


def test_composite_foreign_key_rejects_cross_tenant_revision(db):
    row = story("org-a")
    with db.session(include_all_organizations=True) as session:
        session.add(row)
        session.commit()
        session.add(revision(row, organization="org-b"))
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_database_rejects_duplicate_revisions_and_invalid_lifecycle(db):
    row = story("org-a")
    with db.session() as session:
        session.add(row)
        session.flush()
        session.add(revision(row))
        session.commit()
        session.add(revision(row))
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
        saved = session.get(RelatedStory, row.id)
        saved.status = "resolved"
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
