from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import delete, inspect, select, update
from sqlalchemy.exc import IntegrityError
from test_commute_contracts import DAY, NOW, configuration, leg
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from alembic import command
from helvetic_lens import commute_repository as commutes
from helvetic_lens.commute_catalog import catalog_page, publish_legs, resolve_configuration
from helvetic_lens.commute_models import (
    CommuteConfigurationRevision,
    CommuteDatedLeg,
    CommuteLegReference,
    CommuteMonitor,
)
from helvetic_lens.config import DomainError
from helvetic_lens.db import Base
from helvetic_lens.models import OrganizationMembership, User

db = _database_fixture
template = _template_fixture


def seeded(db):
    with db.session() as session:
        reference_id, = publish_legs(session, (replace(leg(), stop_sequences=(10, 20, 30)),))
        session.commit()
    return configuration().model_copy(update={"leg_reference_ids": (UUID(reference_id),)}).model_dump(mode="json")


def create(db, *, key="save", payload=None):
    with db.session() as session:
        result = commutes.create_monitor(session, "owner", payload or seeded(db), key)
        session.commit()
        return result


def test_catalog_and_configuration_survive_reload_and_never_start_implicitly(db):
    payload = seeded(db)
    row = create(db, payload=payload)
    with db.session() as session:
        assert commutes.get_monitor(session, "owner", row["id"]) == row
        assert row["status"] == "draft" and row["health"] == "not_started"
        catalog = catalog_page(session, "owner", service_day=DAY, query="Basel")
        assert [item["id"] for item in catalog["items"]] == payload["leg_reference_ids"]
        assert not catalog["complete_network"]
        preview = commutes.preview(session, "owner", payload, service_day=DAY, static_version="20260909")
        assert preview["legs"][0]["departure"] == leg().departure.isoformat()
        assert preview["start_available"] is False and preview["live_results_checked"] is False
        for action in ("start", "resume"):
            with pytest.raises(DomainError) as error:
                commutes.command(session, "owner", row["id"], 1, action)
            assert error.value.code == ("commute_source_not_ready" if action == "start" else "commute_action_invalid")
        assert commutes.get_monitor(session, "owner", row["id"])["status"] == "draft"


def test_idempotent_create_and_edit_preserve_immutable_revisions(db):
    payload = seeded(db)
    first = create(db, payload=payload)
    assert create(db, payload=payload) == first
    updated = {**payload, "name": "Updated private trip"}
    with db.session() as session:
        with pytest.raises(DomainError):
            commutes.create_monitor(session, "owner", updated, "save")
        edited = commutes.edit_monitor(session, "owner", first["id"], 1, updated)
        assert edited["version"] == edited["revision"] == 2
        assert commutes.edit_monitor(session, "owner", first["id"], 2, updated) == edited
        with pytest.raises(DomainError):
            commutes.edit_monitor(session, "owner", first["id"], 1, payload)
        history = commutes.revisions(session, "owner", first["id"], limit=1)
        assert history["items"][0]["configuration"] == payload and history["next_cursor"] == 1
        assert commutes.revisions(session, "owner", first["id"], after_revision=1)["items"][0]["configuration"] == updated
        session.commit()


def test_owner_membership_role_and_organization_isolation(db):
    payload = seeded(db)
    row = create(db, payload=payload)
    with db.session() as session:
        assert commutes.list_monitors(session, "peer")["items"] == []
        for actor in ("peer", "viewer"):
            with pytest.raises(DomainError):
                commutes.get_monitor(session, actor, row["id"])
            with pytest.raises(DomainError):
                commutes.list_monitors(session, actor, after_id=row["id"])
        with pytest.raises(DomainError):
            commutes.create_monitor(session, "viewer", payload, "viewer")
    with db.organization_context("org-b"), db.session() as session:
        with pytest.raises(DomainError):
            commutes.get_monitor(session, "owner", row["id"])
        assert session.scalars(select(CommuteMonitor)).all() == []
        assert session.scalars(select(CommuteConfigurationRevision)).all() == []
    with db.session() as session:
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == "owner",
                                                            OrganizationMembership.organization_id == "org-a"))
        session.commit()
    with db.session() as session:
        with pytest.raises(DomainError):
            commutes.get_monitor(session, "owner", row["id"])


def test_deactivated_user_loses_catalog_and_monitor_access(db):
    row = create(db)
    with db.session() as session:
        session.execute(update(User).where(User.id == "owner").values(active=False))
        session.commit()
    with db.session() as session:
        with pytest.raises(DomainError):
            catalog_page(session, "owner", service_day=DAY)
        with pytest.raises(DomainError):
            commutes.get_monitor(session, "owner", row["id"])


def test_rollback_does_not_publish_catalog_or_monitor(db):
    with db.session() as session:
        publish_legs(session, (replace(leg(), stop_sequences=(10, 20, 30)),))
        session.rollback()
    with db.session() as session:
        assert session.scalars(select(CommuteLegReference)).all() == []
    payload = seeded(db)
    with db.session() as session:
        commutes.create_monitor(session, "owner", payload, "rollback")
        session.rollback()
    with db.session() as session:
        assert commutes.list_monitors(session, "owner")["items"] == []
        assert session.scalars(select(CommuteConfigurationRevision)).all() == []


def test_catalog_reimport_is_idempotent_and_pinned_conflicts_rollback(db):
    payload = seeded(db)
    with db.session() as session:
        assert list(publish_legs(session, (replace(leg(), stop_sequences=(10, 20, 30)),))) == payload["leg_reference_ids"]
        with pytest.raises(DomainError):
            publish_legs(session, (replace(leg(), stop_sequences=(10, 20, 30), archive_sha256="b" * 64),))
        assert len(session.scalars(select(CommuteDatedLeg)).all()) == 1


def test_catalog_maps_recurring_reference_to_exact_dates_and_versions(db):
    payload = seeded(db)
    tomorrow = replace(leg(), reference=replace(leg().reference, service_day=DAY + timedelta(days=1), trip_id="next-day-trip"),
                       departure=leg().departure + timedelta(days=1), arrival=leg().arrival + timedelta(days=1),
                       stop_sequences=(40, 50, 60))
    with db.session() as session:
        ids = publish_legs(session, (tomorrow,))
        assert list(ids) == payload["leg_reference_ids"]
        resolved = resolve_configuration(session, commutes.configuration(payload), service_day=DAY + timedelta(days=1), static_version="20260909")
        assert resolved[ids[0]].reference.trip_id == "next-day-trip"
        assert resolved[ids[0]].stop_sequences == (40, 50, 60)
        with pytest.raises(DomainError):
            resolve_configuration(session, commutes.configuration(payload), service_day=DAY, static_version="newest-but-unmapped")


def test_unverified_disabled_and_tampered_catalog_cannot_be_used(db):
    payload = seeded(db)
    with db.session() as session:
        for invalid in ({**payload, "leg_reference_ids": [str(uuid4())]}, {**payload, "delay_threshold_minutes": True}):
            with pytest.raises(DomainError):
                commutes.create_monitor(session, "owner", invalid, "invalid")
        reference = session.get(CommuteLegReference, payload["leg_reference_ids"][0])
        reference.enabled = False
        session.flush()
        assert catalog_page(session, "owner", service_day=DAY)["items"] == []
        with pytest.raises(DomainError):
            commutes.create_monitor(session, "owner", payload, "disabled")
        reference.enabled = True
        dated = session.scalars(select(CommuteDatedLeg)).one()
        dated.resolved_hash = "f" * 64
        session.flush()
        with pytest.raises(DomainError) as error:
            commutes.preview(session, "owner", payload, service_day=DAY, static_version="20260909")
        assert error.value.code == "commute_catalog_invalid"


def test_pause_today_uses_zurich_date_and_edit_requires_pause(db):
    row = create(db)
    with db.session() as session:
        # Synthetic active state only; live start remains gated.
        session.execute(update(CommuteMonitor).where(CommuteMonitor.id == row["id"]).values(status="active"))
        now = NOW.replace(hour=23, minute=30)
        paused = commutes.command(session, "owner", row["id"], 1, "pause_today", now=now)
        assert paused["paused_on"] == "2026-09-15" and paused["status"] == "active"
        assert paused["notification_pause_until"] == "2026-09-15T22:00:00+00:00"
        assert commutes.get_monitor(session, "owner", row["id"], now=now)["notification_pause_until"] == paused["notification_pause_until"]
        assert commutes.get_monitor(session, "owner", row["id"], now=now + timedelta(days=1))["notification_pause_until"] is None
        with pytest.raises(DomainError):
            commutes.edit_monitor(session, "owner", row["id"], 2, {**row["configuration"], "name": "edited"})
        paused = commutes.command(session, "owner", row["id"], 2, "pause")
        assert paused["status"] == "paused" and paused["paused_on"] is None
        assert paused["notification_pause_until"] is None
        edited = commutes.edit_monitor(session, "owner", row["id"], 3, {**row["configuration"], "name": "edited"})
        assert edited["status"] == "draft" and edited["version"] == 4


def test_archive_cas_delete_and_revision_cascade_preserve_public_catalog(db):
    row = create(db)
    with db.session() as session:
        archived = commutes.command(session, "owner", row["id"], 1, "archive")
        assert archived["status"] == "archived"
        with pytest.raises(DomainError):
            commutes.remove_monitor(session, "owner", row["id"], 1)
        commutes.remove_monitor(session, "owner", row["id"], 2)
        session.commit()
    with db.session() as session:
        assert session.scalars(select(CommuteConfigurationRevision)).all() == []
        assert len(session.scalars(select(CommuteLegReference)).all()) == 1


def test_composite_revision_scope_cannot_cross_organizations(db):
    row = create(db)
    with db.session(include_all_organizations=True) as session:
        session.add(CommuteConfigurationRevision(monitor_id=row["id"], organization_id="org-b", revision=2,
                                                configuration=row["configuration"], configuration_hash="a" * 64))
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_monitors_paginate_without_exposing_other_owner_cursor(db):
    payload = seeded(db)
    ids = {create(db, payload=payload, key=str(i))["id"] for i in range(3)}
    with db.session() as session:
        seen, cursor = set(), None
        while True:
            page = commutes.list_monitors(session, "owner", limit=1, after_id=cursor)
            seen.update(row["id"] for row in page["items"])
            cursor = page["next_cursor"]
            if not cursor:
                break
        assert seen == ids
        assert catalog_page(session, "owner", service_day=date(2026, 9, 15))["items"] == []
        assert catalog_page(session, "owner", service_day=DAY, query="%")["items"] == []


def test_migration_has_all_four_tables_and_indexes(db):
    inspector = inspect(db.engine)
    for table in ("commute_leg_references", "commute_dated_legs", "commute_monitors", "commute_configuration_revisions"):
        assert table in inspector.get_table_names()
    assert {tuple(index["column_names"]) for index in inspector.get_indexes("commute_monitors")} == {("organization_id",), ("owner_user_id",), ("next_poll_at",)}


def test_commute_migration_round_trip_preserves_accounts_and_tender_schema(db):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "e5b7cf26098d")
        tables = inspect(connection).get_table_names()
        assert "commute_monitors" not in tables and "tender_monitors" in tables
        command.upgrade(config, "head")
        assert "commute_dated_legs" in inspect(connection).get_table_names()
    with db.session() as session:
        assert session.get(User, "owner").email == "owner@example.test"


def test_migration_matches_commute_orm_metadata(db):
    with db.engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True,
            "include_object": lambda obj, name, kind, reflected, compare: kind != "table" or name.startswith("commute_")})
        assert compare_metadata(context, Base.metadata) == []


def test_rehashed_wrong_route_cannot_replace_catalog_reference(db):
    from helvetic_lens.commute_catalog import encode_leg
    from helvetic_lens.commute_contracts import digest

    payload = seeded(db)
    with db.session() as session:
        row = session.scalars(select(CommuteDatedLeg)).one()
        changed = replace(leg(), reference=replace(leg().reference, route_id="wrong-route"), stop_sequences=(10, 20, 30))
        row.resolved = encode_leg(changed)
        row.resolved_hash = digest(row.resolved)
        session.flush()
        with pytest.raises(DomainError) as error:
            resolve_configuration(session, commutes.configuration(payload), service_day=DAY, static_version="20260909")
        assert error.value.code == "commute_catalog_invalid"


def test_automatic_preview_version_never_guesses_latest_or_uses_revoked_feed(db):
    from test_commute_jobs import capture, source_grants
    from test_transport_feed import trip_feed

    from helvetic_lens.commute_models import CommuteSourcePermission
    from helvetic_lens.transport_feed import TRIPS

    payload = seeded(db)
    other = replace(leg(), reference=replace(leg().reference, static_version="20990101"), stop_sequences=(10, 20, 30))
    with db.session() as session:
        assert commutes.preview(session, "owner", payload, service_day=DAY, now=NOW)["legs"][0]["static_version"] == "20260909"
        publish_legs(session, (other,))
        session.commit()
        with pytest.raises(DomainError, match="reliably") as error:
            commutes.preview(session, "owner", payload, service_day=DAY, now=NOW)
        assert error.value.code == "commute_timetable_ambiguous"
    grants = source_grants(db)
    capture(db, grants[TRIPS], trip_feed())
    with db.session() as session:
        chosen = commutes.preview(session, "owner", payload, service_day=DAY, now=NOW)
        assert chosen["legs"][0]["static_version"] == "20260909"
        session.get(CommuteSourcePermission, grants[TRIPS]).revoked_at = NOW
        session.commit()
        with pytest.raises(DomainError) as error:
            commutes.preview(session, "owner", payload, service_day=DAY, now=NOW)
        assert error.value.code == "commute_timetable_ambiguous"
