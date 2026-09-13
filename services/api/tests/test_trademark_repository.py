"""Tenant, ownership, revision and migration acceptance for private portfolios."""

from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from test_tender_repository import db as db
from test_tender_repository import template as template
from test_trademark_matching import portfolio

from alembic import command
from helvetic_lens import trademark_repository as repository
from helvetic_lens.config import DomainError
from helvetic_lens.db import Base
from helvetic_lens.models import OrganizationMembership
from helvetic_lens.trademark_models import TrademarkConfigurationRevision, TrademarkMonitor


def create(db, *, actor="owner", key="portfolio", payload=None):
    with db.session() as session:
        result = repository.create_monitor(session, actor, payload or portfolio().model_dump(mode="json"), key)
        session.commit()
        return result


def test_save_multiple_brands_replay_edit_history_archive_and_confirmed_delete(db):
    saved = create(db)
    assert saved["status"] == "draft" and create(db) == saved
    with pytest.raises(DomainError):
        create(db, payload=portfolio(name="Another").model_dump(mode="json"))
    changed = portfolio().model_dump(mode="json")
    changed["brands"].append({"key": "pulsanto", "name": "PULSANTO", "language": "it"})
    with db.session() as session:
        edited = repository.edit_monitor(session, "owner", saved["id"], 1, changed)
        assert edited["version"] == 2 and edited["revision"] == 2
        assert len(edited["configuration"]["brands"]) == 2
        with pytest.raises(DomainError):
            repository.edit_monitor(session, "owner", saved["id"], 1, changed)
        first = repository.revisions(session, "owner", saved["id"], limit=1)
        assert first["next_cursor"] == 2
        old = repository.revisions(session, "owner", saved["id"], before=2)["items"][0]
        assert len(old["configuration"]["brands"]) == 1 and old["configuration_hash"] == portfolio().fingerprint()
        with pytest.raises(DomainError):
            repository.delete_monitor(session, "owner", saved["id"], 2)
        archived = repository.archive_monitor(session, "owner", saved["id"], 2)
        assert archived["version"] == 3 and archived["status"] == "archived"
        assert repository.archive_monitor(session, "owner", saved["id"], 3) == archived
        repository.delete_monitor(session, "owner", saved["id"], 3)
        session.commit()
        assert session.scalar(select(func.count()).select_from(TrademarkConfigurationRevision)) == 0


def test_foreign_owner_cursors_and_revoked_membership_never_reveal_brands(db):
    first, other = create(db), create(db, actor="peer")
    with db.session() as session:
        for actor in ("peer", "viewer"):
            with pytest.raises(DomainError):
                repository.get_monitor(session, actor, first["id"])
        with pytest.raises(DomainError):
            repository.list_monitors(session, "owner", after_id=other["id"])
        assert [m["id"] for m in repository.list_monitors(session, "owner")["items"]] == [first["id"]]
    with db.organization_context("org-b"), db.session() as session:
        with pytest.raises(DomainError):
            repository.get_monitor(session, "owner", first["id"])
        assert session.scalars(select(TrademarkMonitor)).all() == []
    with db.session() as session:
        session.execute(update(OrganizationMembership).where(OrganizationMembership.user_id == "owner").values(role="viewer"))
        session.commit()
        assert repository.get_monitor(session, "owner", first["id"])["id"] == first["id"]
        with pytest.raises(DomainError):
            repository.archive_monitor(session, "owner", first["id"], 1)


def test_cross_organization_configuration_revision_is_rejected_by_database(db):
    saved = create(db)
    with db.session(include_all_organizations=True) as session:
        session.add(TrademarkConfigurationRevision(organization_id="org-b", monitor_id=saved["id"], revision=2,
            configuration=saved["configuration"], configuration_hash=portfolio().fingerprint()))
        with pytest.raises(IntegrityError):
            session.commit()


def test_pagination_limits_and_invalid_versions(db):
    first = create(db)
    create(db, key="second")
    with db.session() as session:
        page = repository.list_monitors(session, "owner", limit=1)
        following = repository.list_monitors(session, "owner", limit=1, after_id=page["next_cursor"])
        assert following["next_cursor"] is None and following["items"][0]["id"] != page["items"][0]["id"]
        for value in (True, 0, -1, "1"):
            with pytest.raises(DomainError):
                repository.archive_monitor(session, "owner", first["id"], value)
        for value in (0, True, 101):
            with pytest.raises(DomainError):
                repository.revisions(session, "owner", first["id"], limit=value)


def test_draft_preview_does_not_run_matching_or_claim_source_access(db):
    with db.session() as session:
        preview = repository.preview(session, "owner", portfolio().model_dump(mode="json"))
        assert preview["draft_available"] and not preview["start_available"] and not preview["live_results_checked"]
        assert "trademark_source_not_configured" in preview["blocking_reasons"]
        assert session.scalars(select(TrademarkMonitor)).all() == []


def test_migration_matches_metadata_and_preserves_other_directions(db):
    from test_hazard_repository import create as create_hazard

    from helvetic_lens.hazard_models import HazardMonitor
    retained = create_hazard(db)
    with db.engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"include_object":
            lambda obj, name, kind, reflected, compare_to: name.startswith("trademark_") if kind == "table" else True})
        assert compare_metadata(context, Base.metadata) == []
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "3ce8fa47ba3e")
        assert connection.execute(select(HazardMonitor.id).where(HazardMonitor.id == retained["id"])).scalar() == retained["id"]
        command.upgrade(config, "head")
        assert compare_metadata(context, Base.metadata) == []
