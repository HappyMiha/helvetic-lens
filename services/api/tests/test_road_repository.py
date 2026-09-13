from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from test_road_catalog import TABLE, mapping, reference, topology
from test_road_feed import NOW
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens import road_repository as roads
from helvetic_lens.config import DomainError
from helvetic_lens.models import OrganizationMembership, User
from helvetic_lens.road_catalog import revoke_topology, set_reference_enabled
from helvetic_lens.road_models import RoadConfigurationRevision, RoadMonitor

db = _database_fixture
template = _template_fixture


def seeded(db):
    topo, ref = topology(db), reference(db)
    mapping(db, ref, topo)
    return {"name": "Private weekend trip", "corridor_reference_ids": [ref],
            "materiality": {"event_kinds": ["road_closure", "congestion"],
                            "minimum_delay_seconds": 900, "include_planned": True}}, topo


def create(db, payload, key="save"):
    with db.session() as session:
        result = roads.create_monitor(session, "owner", payload, key)
        session.commit()
        return result


def test_reload_idempotency_revisions_and_no_implicit_start(db):
    payload, _ = seeded(db)
    first = create(db, payload)
    db.engine.dispose()
    assert create(db, payload) == first
    assert first["status"] == "draft" and first["health"] == "not_started"
    with db.session() as session:
        preview = roads.preview(session, "owner", payload, table_key=TABLE, now=NOW)
        assert preview["corridors"][0]["id"] == payload["corridor_reference_ids"][0]
        assert not preview["start_available"] and not preview["live_results_checked"]
        assert roads.get_monitor(session, "owner", first["id"]) == first
        with pytest.raises(DomainError) as error:
            roads.command(session, "owner", first["id"], 1, "start")
        assert error.value.code == "road_source_not_ready"
        changed = roads.edit_monitor(session, "owner", first["id"], 1, {**payload, "name": "New private route name"})
        assert changed["version"] == changed["revision"] == 2
        with pytest.raises(DomainError):
            roads.edit_monitor(session, "owner", first["id"], 1, payload)
        assert roads.edit_monitor(session, "owner", first["id"], 2, changed["configuration"]) == changed
        assert roads.create_monitor(session, "owner", payload, "save") == changed
        with pytest.raises(DomainError) as error:
            roads.create_monitor(session, "owner", {**payload, "name": "Different original request"}, "save")
        assert error.value.code == "road_monitor_request_conflict"
        page = roads.revisions(session, "owner", first["id"], limit=1)
        assert page["items"][0]["configuration"]["name"] == payload["name"] and page["next_cursor"] == 1
        assert roads.revisions(session, "owner", first["id"], after_revision=1)["items"][0]["configuration"] == changed["configuration"]
        session.commit()


def test_owner_role_tenant_and_membership_are_rechecked_for_every_private_path(db):
    payload, _ = seeded(db)
    saved = create(db, payload)
    with db.session() as session:
        for actor in ("peer", "viewer"):
            assert roads.list_monitors(session, actor)["items"] == []
            calls = (
                lambda: roads.get_monitor(session, actor, saved["id"]),
                lambda: roads.revisions(session, actor, saved["id"]),
                lambda: roads.list_monitors(session, actor, after_id=saved["id"]),
                lambda: roads.edit_monitor(session, actor, saved["id"], 1, payload),
                lambda: roads.command(session, actor, saved["id"], 1, "archive"),
                lambda: roads.remove_monitor(session, actor, saved["id"], 1))
            for call in calls:
                with pytest.raises(DomainError):
                    call()
        with pytest.raises(DomainError):
            roads.create_monitor(session, "viewer", payload, "new")
    with db.organization_context("org-b"), db.session() as session:
        assert session.scalars(select(RoadMonitor)).all() == []
        assert session.scalars(select(RoadConfigurationRevision)).all() == []
        with pytest.raises(DomainError):
            roads.get_monitor(session, "owner", saved["id"])
    with db.session() as session:
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == "owner",
                                                            OrganizationMembership.organization_id == "org-a"))
        session.commit()
    with db.session() as session, pytest.raises(DomainError):
        roads.get_monitor(session, "owner", saved["id"])


def test_catalogue_redacts_revoked_labels_but_owners_can_still_edit_their_own_settings(db):
    payload, topo = seeded(db)
    saved = create(db, payload)
    with db.session() as session:
        assert roads.catalog_page(session, "owner", table_key=TABLE, now=NOW, query="northbound")["items"]
        revoke_topology(session, topo, now=NOW)
        session.commit()
    with db.session() as session:
        assert not roads.catalog_page(session, "owner", table_key=TABLE, now=NOW, query="northbound")["items"]
        preview = roads.preview(session, "owner", payload, table_key=TABLE, now=NOW)
        assert preview["corridors"] == [{"id": payload["corridor_reference_ids"][0], "state": "unavailable"}]
        assert "Synthetic corridor" not in str(preview)
        assert roads.get_monitor(session, "owner", saved["id"])["configuration"]["name"] == payload["name"]
        assert roads.edit_monitor(session, "owner", saved["id"], 1, {**payload, "name": "Edited draft"})["version"] == 2


def test_configuration_rejects_guesses_duplicates_boolean_thresholds_and_implicit_mail(db):
    payload, _ = seeded(db)
    bad = [{**payload, "corridor_reference_ids": ["A2 north"]},
           {**payload, "corridor_reference_ids": payload["corridor_reference_ids"] * 2},
           {**payload, "corridor_reference_ids": []}, {**payload, "template_version": True},
           {**payload, "delivery": {"email": "immediate"}}, {**payload, "name": " \n"}]
    for changes in ({"minimum_delay_seconds": True}, {"minimum_delay_seconds": "900"},
                    {"include_planned": "true"}, {"event_kinds": []}, {"event_kinds": ["road_closure", "road_closure"]}):
        bad.append({**payload, "materiality": {**payload["materiality"], **changes}})
    with db.session() as session:
        for invalid in bad:
            with pytest.raises(DomainError) as error:
                roads.create_monitor(session, "owner", invalid, str(uuid4()))
            assert error.value.code == "road_configuration_invalid"
        assert session.scalar(select(func.count()).select_from(RoadMonitor)) == 0


def test_unknown_unmapped_and_disabled_references_are_not_selectable(db):
    payload, _ = seeded(db)
    unmapped = reference(db, key="unmapped")
    with db.session() as session:
        set_reference_enabled(session, unmapped, enabled=True, expected_generation=0)
        session.commit()
    for ref in (str(uuid4()), unmapped):
        with pytest.raises(DomainError):
            create(db, {**payload, "corridor_reference_ids": [ref]})
    with db.session() as session:
        set_reference_enabled(session, payload["corridor_reference_ids"][0], enabled=False, expected_generation=1)
        session.commit()
    with pytest.raises(DomainError):
        create(db, payload)


def test_caller_rollback_and_delete_preserve_other_monitors_and_shared_catalogue(db):
    payload, _ = seeded(db)
    with db.session() as session:
        roads.create_monitor(session, "owner", payload, "rollback")
        session.rollback()
    with db.session() as session:
        assert roads.list_monitors(session, "owner")["items"] == []
    first, second = create(db, payload, "first"), create(db, payload, "second")
    with db.session() as session:
        with pytest.raises(DomainError):
            roads.remove_monitor(session, "owner", first["id"], 2)
        roads.remove_monitor(session, "owner", first["id"], 1)
        session.commit()
    with db.session() as session:
        assert [r["id"] for r in roads.list_monitors(session, "owner")["items"]] == [second["id"]]
        assert session.scalar(select(func.count()).select_from(RoadConfigurationRevision)) == 1
        assert roads.catalog_page(session, "owner", table_key=TABLE, now=NOW)["items"]


def test_archive_edit_conflicts_and_owner_pagination(db):
    payload, _ = seeded(db)
    rows = [create(db, payload, str(i)) for i in range(3)]
    with db.session() as session:
        page = roads.list_monitors(session, "owner", limit=2)
        last = roads.list_monitors(session, "owner", after_id=page["next_cursor"], limit=2)
        assert len({item["id"] for item in page["items"] + last["items"]}) == 3 and last["next_cursor"] is None
        archived = roads.command(session, "owner", rows[0]["id"], 1, "archive")
        assert archived["status"] == "archived" and archived["version"] == 2
        with pytest.raises(DomainError):
            roads.edit_monitor(session, "owner", rows[0]["id"], 2, payload)
        with pytest.raises(DomainError):
            roads.command(session, "owner", rows[1]["id"], True, "archive")


def test_inactive_users_and_expired_topology_cannot_read_catalogue_labels(db):
    payload, _ = seeded(db)
    create(db, payload)
    with db.session() as session:
        assert not roads.catalog_page(session, "owner", table_key=TABLE, now=NOW + timedelta(days=31))["items"]
        session.execute(update(User).where(User.id == "owner").values(active=False))
        session.commit()
    with db.session() as session:
        for call in (lambda: roads.catalog_page(session, "owner", table_key=TABLE, now=NOW),
                     lambda: roads.list_monitors(session, "owner")):
            with pytest.raises(DomainError):
                call()


def test_database_rejects_cross_tenant_configuration_binding(db):
    payload, _ = seeded(db)
    saved = create(db, payload)
    with db.session(include_all_organizations=True) as session, pytest.raises(IntegrityError):
        session.add(RoadConfigurationRevision(monitor_id=saved["id"], organization_id="org-b", revision=2,
            configuration=payload, configuration_hash="a" * 64))
        session.flush()


def test_bounded_empty_catalogue_pages_continue_without_skipping_references(db):
    topo = topology(db)
    refs = []
    for i in range(22):
        ref = reference(db, key=f"synthetic-{i}")
        mapping(db, ref, topo)
        refs.append(ref)
    with db.session() as session:
        first = roads.catalog_page(session, "owner", table_key=TABLE, now=NOW, query="absent", limit=100)
        assert first["items"] == [] and first["next_cursor"] is not None
        last = roads.catalog_page(session, "owner", table_key=TABLE, now=NOW, query="absent", limit=100,
                                  after_id=first["next_cursor"])
        assert last == {"items": [], "next_cursor": None, "complete_network": False}
        first = roads.catalog_page(session, "owner", table_key=TABLE, now=NOW, limit=100)
        last = roads.catalog_page(session, "owner", table_key=TABLE, now=NOW, limit=100, after_id=first["next_cursor"])
        assert {i["id"] for i in first["items"] + last["items"]} == set(refs)


def test_graph_read_budget_continues_before_the_unread_reference(db, monkeypatch):
    from helvetic_lens import road_catalog
    from helvetic_lens.road_models import RoadTopologyRevision

    ids = []
    for i in range(3):
        topo, ref = topology(db), reference(db, key=f"budget-{i}")
        mapping(db, ref, topo)
        ids.append(ref)
    with db.session() as session:
        size = session.scalar(select(RoadTopologyRevision.content_size).limit(1))
        monkeypatch.setattr(road_catalog, "MAX_READ_BYTES", size * 2)
        first = roads.catalog_page(session, "owner", table_key=TABLE, now=NOW)
        assert len(first["items"]) == 2 and first["next_cursor"]
        last = roads.catalog_page(session, "owner", table_key=TABLE, now=NOW, after_id=first["next_cursor"])
        assert len(last["items"]) == 1 and last["next_cursor"] is None
        assert {i["id"] for i in first["items"] + last["items"]} == set(ids)
