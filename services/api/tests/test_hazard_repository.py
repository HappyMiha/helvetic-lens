from copy import deepcopy

import pytest
from sqlalchemy import delete, func, inspect, select, update
from sqlalchemy.exc import IntegrityError
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens import hazard_repository as hazards
from helvetic_lens.config import DomainError
from helvetic_lens.hazard_models import HazardConfigurationRevision, HazardMonitor
from helvetic_lens.models import Job, OrganizationMembership, User

db = _database_fixture
template = _template_fixture
CONFIG = {"name": "Home", "location": {"kind": "point", "country": "CH", "canton": "BS",
           "latitude": 47.56, "longitude": 7.59}, "hazards": ["storm", "flood"]}


def create(db, payload=None, key="save", actor="owner"):
    with db.session() as session:
        result = hazards.create_monitor(session, actor, deepcopy(CONFIG if payload is None else payload), key)
        session.commit()
        return result


def test_location_reload_idempotency_history_preview_and_no_implicit_work(db):
    first = create(db)
    db.engine.dispose()
    assert create(db) == first
    assert first["status"] == "draft"
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 0
        preview = hazards.preview(session, "owner", CONFIG)
        assert preview["draft_available"] and not preview["start_available"]
        assert not preview["live_results_checked"]
        changed = hazards.edit_monitor(session, "owner", first["id"], 1, {**CONFIG, "name": "Office"})
        assert changed["version"] == changed["revision"] == 2
        assert hazards.edit_monitor(session, "owner", first["id"], 2, changed["configuration"]) == changed
        assert hazards.create_monitor(session, "owner", CONFIG, "save") == changed
        history = hazards.revisions(session, "owner", first["id"], limit=1)
        assert history["items"][0]["configuration"]["name"] == "Office"
        prior = hazards.revisions(session, "owner", first["id"], before=history["next_cursor"])
        assert prior["items"][0]["configuration"]["name"] == "Home"
        with pytest.raises(DomainError, match="Saved warning"):
            hazards.edit_monitor(session, "owner", first["id"], 1, CONFIG)
        session.commit()
    assert create(db)["configuration"]["name"] == "Office"


@pytest.mark.parametrize("actor", ["peer", "viewer"])
def test_other_owners_cannot_read_edit_history_archive_delete_or_reuse_cursor(db, actor):
    saved = create(db)
    with db.session() as session:
        assert hazards.list_monitors(session, actor)["items"] == []
        for action in (
            lambda: hazards.get_monitor(session, actor, saved["id"]),
            lambda: hazards.revisions(session, actor, saved["id"]),
            lambda: hazards.edit_monitor(session, actor, saved["id"], 1, CONFIG),
            lambda: hazards.archive_monitor(session, actor, saved["id"], 1),
            lambda: hazards.delete_monitor(session, actor, saved["id"], 1),
            lambda: hazards.list_monitors(session, actor, after_id=saved["id"]),
        ):
            with pytest.raises(DomainError) as error:
                action()
            assert error.value.status in {403, 404}


def test_tenant_switch_and_membership_removal_recheck_access(db):
    saved = create(db)
    with db.organization_context("org-b"), db.session() as session:
        assert session.scalar(select(HazardMonitor)) is None
        assert session.scalar(select(HazardConfigurationRevision)) is None
        with pytest.raises(DomainError):
            hazards.get_monitor(session, "owner", saved["id"])
    with db.session() as session:
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.organization_id == "org-a",
                                                            OrganizationMembership.user_id == "owner"))
        session.commit()
    with db.session() as session, pytest.raises(DomainError):
        hazards.get_monitor(session, "owner", saved["id"])


def test_demotion_keeps_own_read_but_revokes_writes_and_disabled_account_revokes_read(db):
    saved = create(db)
    with db.session() as session:
        session.execute(update(OrganizationMembership).where(OrganizationMembership.user_id == "owner",
            OrganizationMembership.organization_id == "org-a").values(role="viewer"))
        session.commit()
    with db.session() as session:
        assert hazards.get_monitor(session, "owner", saved["id"]) == saved
        with pytest.raises(DomainError):
            hazards.edit_monitor(session, "owner", saved["id"], 1, CONFIG)
        session.execute(update(User).where(User.id == "owner").values(active=False))
        session.commit()
    with db.session() as session, pytest.raises(DomainError):
        hazards.get_monitor(session, "owner", saved["id"])


def test_archive_before_delete_cascades_private_history_and_rejects_stale_version(db):
    saved = create(db)
    with db.session() as session:
        with pytest.raises(DomainError):
            hazards.delete_monitor(session, "owner", saved["id"], 1)
        archived = hazards.archive_monitor(session, "owner", saved["id"], 1)
        assert archived["status"] == "archived" and archived["version"] == 2
        assert hazards.archive_monitor(session, "owner", saved["id"], 2) == archived
        with pytest.raises(DomainError):
            hazards.edit_monitor(session, "owner", saved["id"], 2, CONFIG)
        with pytest.raises(DomainError):
            hazards.delete_monitor(session, "owner", saved["id"], 1)
        hazards.delete_monitor(session, "owner", saved["id"], 2)
        session.commit()
    with db.session() as session:
        assert session.scalar(select(HazardConfigurationRevision)) is None
        assert hazards.list_monitors(session, "owner")["items"] == []


def test_caller_rollback_does_not_publish_create_or_edit_savepoint(db):
    with db.session() as session:
        hazards.create_monitor(session, "owner", CONFIG, "rollback")
        session.rollback()
    with db.session() as session:
        assert hazards.list_monitors(session, "owner")["items"] == []
    saved = create(db)
    with db.session() as session:
        hazards.edit_monitor(session, "owner", saved["id"], 1, {**CONFIG, "name": "Rolled back"})
        session.rollback()
    with db.session() as session:
        assert hazards.get_monitor(session, "owner", saved["id"]) == saved
        assert len(hazards.revisions(session, "owner", saved["id"])["items"]) == 1


@pytest.mark.parametrize("change", [
    {"name": " \n "}, {"template_version": True}, {"hazards": ["storm", "storm"]},
    {"hazards": ["unknown"]}, {"email_consent": True}, {"source_approved": True},
    {"owner_user_id": "peer"}, {"minimum_importance": "safe"},
    {"location": {**CONFIG["location"], "latitude": True}},
    {"location": {**CONFIG["location"], "latitude": "47.56"}},
    {"location": {**CONFIG["location"], "latitude": float("nan")}},
    {"location": {**CONFIG["location"], "longitude": 47.56}},
    {"location": {**CONFIG["location"], "country": "FR"}},
    {"location": {**CONFIG["location"], "radius_km": -1}},
    {"location": {**CONFIG["location"], "verified": True}},
])
def test_invalid_or_forged_configuration_has_no_private_error_values_or_rows(db, change):
    with db.session() as session:
        with pytest.raises(DomainError) as error:
            hazards.create_monitor(session, "owner", {**CONFIG, **change}, "invalid")
        assert error.value.code == "hazard_configuration_invalid"
        assert "47.56" not in str(error.value)
        assert session.scalar(select(HazardMonitor)) is None


def test_named_municipality_and_radius_are_drafts_until_geometry_verified(db):
    municipality = {**CONFIG, "location": {"kind": "municipality", "country": "CH", "canton": "BS", "municipality_code": "2701"}}
    saved = create(db, municipality)
    with db.session() as session:
        assert not hazards.preview(session, "owner", saved["configuration"])["start_available"]
        radius = {**CONFIG, "location": {**CONFIG["location"], "radius_km": 5.0}}
        assert not hazards.preview(session, "owner", radius)["start_available"]


def test_pagination_limits_idempotency_and_revision_capacity(db, monkeypatch):
    first, second = create(db), create(db, {**CONFIG, "name": "Office"}, "second")
    with db.session() as session:
        page = hazards.list_monitors(session, "owner", limit=1)
        next_page = hazards.list_monitors(session, "owner", limit=1, after_id=page["next_cursor"])
        assert {page["items"][0]["id"], next_page["items"][0]["id"]} == {first["id"], second["id"]}
        assert next_page["next_cursor"] is None
        for invalid in (True, 0, 101):
            with pytest.raises(DomainError):
                hazards.list_monitors(session, "owner", limit=invalid)
        with pytest.raises(DomainError):
            hazards.create_monitor(session, "owner", {**CONFIG, "name": "Different"}, "save")
        monkeypatch.setattr(hazards, "MAX_MONITORS", 2)
        assert hazards.create_monitor(session, "owner", CONFIG, "save") == first
        with pytest.raises(DomainError):
            hazards.create_monitor(session, "owner", CONFIG, "third")
        monkeypatch.setattr(hazards, "MAX_REVISIONS", 1)
        with pytest.raises(DomainError):
            hazards.edit_monitor(session, "owner", first["id"], 1, {**CONFIG, "name": "Overflow"})


def test_database_foreign_key_prevents_cross_tenant_private_revision(db):
    saved = create(db)
    assert {"hazard_monitors", "hazard_configuration_revisions"} <= set(inspect(db.engine).get_table_names())
    with db.session(include_all_organizations=True) as session:
        session.add(HazardConfigurationRevision(monitor_id=saved["id"], organization_id="org-b", revision=2,
                    configuration={}, configuration_hash="0" * 64))
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
