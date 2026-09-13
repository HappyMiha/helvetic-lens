from datetime import timedelta

import pytest
from sqlalchemy import func, select
from test_road_feed import NOW
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens import road_catalog as catalog
from helvetic_lens.config import DomainError
from helvetic_lens.road_acquisition import cleanup
from helvetic_lens.road_models import RoadCorridorMap, RoadCorridorReference, RoadTopologyRevision
from helvetic_lens.road_topology import CorridorFlow, TmcPoint, TopologyDefinition

db = _database_fixture
template = _template_fixture
TABLE = ("ch", "test", "synthetic-v1")


def definition(version=TABLE[2]):
    return TopologyDefinition(country=TABLE[0], table=TABLE[1], version=version, points=(
        TmcPoint(code=90, positive=10, distance_to_positive_m=1000),
        TmcPoint(code=10, negative=90, positive=50, distance_to_positive_m=2000),
        TmcPoint(code=50, negative=10)))


def policy(**updates):
    return catalog.TopologyPolicy(**{
        "reference": "synthetic-topology-rights", "attribution": "Synthetic reviewed table",
        "review_reference": "synthetic-operator-review", "accepted_at": NOW - timedelta(days=1),
        "valid_until": NOW + timedelta(days=30), "matching_allowed": True, "display_allowed": True,
        "notifications_allowed": False, **updates})


def topology(db, *, version=TABLE[2], **updates):
    with db.session() as session:
        result = catalog.publish_topology(session, definition=definition(version), asset_hash="a" * 64,
                                          policy=policy(**updates), now=NOW)
        session.commit()
        return result


def reference(db, key="synthetic-a2-north"):
    with db.session() as session:
        result = catalog.create_reference(session, identity=catalog.CorridorIdentity(
            key=key, name="Synthetic corridor northbound", flow_key="northbound"))
        session.commit()
        return result


def mapping(db, reference_id, topology_id, *, generation=0, **updates):
    with db.session() as session:
        result = catalog.publish_mapping(session, reference_id, topology_id=topology_id,
            expected_generation=generation, flow=CorridorFlow(key="northbound", points=(90, 10, 50)),
            review_reference="synthetic-flow-review", now=NOW, **updates)
        session.commit()
        return result


def read(db, ref, *, table=TABLE, **updates):
    with db.session() as session:
        return catalog.resolve_reference(session, ref, table_key=table, now=NOW, **updates)


def test_reviewed_reference_survives_reload_and_projects_only_permitted_labels(db):
    topo, ref = topology(db), reference(db)
    map_id = mapping(db, ref, topo)
    db.engine.dispose()
    resolved = read(db, ref)
    assert (resolved.reference_id, resolved.mapping_id, resolved.topology_id, resolved.generation) == (ref, map_id, topo, 1)
    assert resolved.corridor.points == (90, 10, 50)
    assert [part.end_m for part in resolved.corridor.slices] == [1000, 2000]
    with db.session() as session:
        description = catalog.describe_reference(session, ref, table_key=TABLE, now=NOW)
        assert description == {"id": ref, "name": "Synthetic corridor northbound", "flow": "northbound",
                               "generation": 1, "attribution": "Synthetic reviewed table"}
    assert "points" not in repr(resolved)


def test_renewal_keeps_identity_and_does_not_guess_unpublished_table_versions(db):
    ref = reference(db)
    first = mapping(db, ref, topology(db))
    second = mapping(db, ref, topology(db, version="synthetic-v2"), generation=1)
    assert read(db, ref).mapping_id == first
    assert read(db, ref, table=("ch", "test", "synthetic-v2")).mapping_id == second
    for table in (("ch", "other", TABLE[2]), ("other", "test", TABLE[2]), ("ch", "test", "missing")):
        with pytest.raises(DomainError) as error:
            read(db, ref, table=table)
        assert error.value.code == "road_corridor_mapping_unavailable"


@pytest.mark.parametrize("denial", ["revoked", "expired", "no_matching"])
def test_latest_denied_grant_never_falls_back_to_old_permitted_map(db, denial):
    ref = reference(db)
    old = topology(db)
    mapping(db, ref, old)
    new = topology(db, valid_until=NOW + timedelta(seconds=1)) if denial == "expired" else topology(db)
    mapping(db, ref, new, generation=1)
    with db.session() as session:
        if denial == "revoked":
            catalog.revoke_topology(session, new, now=NOW)
        elif denial == "no_matching":
            # Simulate an explicitly reviewed narrower grant at the same table key.
            new = catalog.publish_topology(session, definition=definition(), asset_hash="b" * 64,
                policy=policy(matching_allowed=False), now=NOW)
            with pytest.raises(DomainError) as error:
                catalog.publish_mapping(session, ref, topology_id=new, expected_generation=2,
                    flow=CorridorFlow(key="northbound", points=(90, 10)), review_reference="review", now=NOW)
            assert error.value.code == "road_topology_use_denied"
            return
        session.commit()
    with db.session() as session, pytest.raises(DomainError) as error:
        catalog.resolve_reference(session, ref, table_key=TABLE, now=NOW + timedelta(seconds=2))
    assert error.value.code == "road_topology_permission_unavailable"
    # Still-valid old grants can only be selected by an explicit new map review.
    restored = mapping(db, ref, old, generation=2)
    assert read(db, ref).mapping_id == restored


@pytest.mark.parametrize("use", ["display", "notification"])
def test_match_display_and_notification_rights_are_separate(db, use):
    ref = reference(db)
    mapping(db, ref, topology(db, display_allowed=False))
    assert read(db, ref).reference_id == ref
    with pytest.raises(DomainError) as error:
        read(db, ref, **{use: True})
    assert error.value.code == "road_topology_use_denied"


def test_disabled_reference_and_stale_edits_do_not_change_mappings(db):
    topo, ref = topology(db), reference(db)
    first = mapping(db, ref, topo)
    with pytest.raises(DomainError) as error:
        mapping(db, ref, topo)
    assert error.value.code == "road_corridor_generation_conflict"
    with db.session() as session:
        assert catalog.set_reference_enabled(session, ref, enabled=False, expected_generation=1) == 2
        session.commit()
    with pytest.raises(DomainError) as error:
        read(db, ref)
    assert error.value.code == "road_corridor_disabled"
    with db.session() as session:
        catalog.set_reference_enabled(session, ref, enabled=True, expected_generation=2)
        session.commit()
    assert read(db, ref).mapping_id == first
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(RoadCorridorMap)) == 1


@pytest.mark.parametrize("points,key", [((90, 50), "northbound"), ((50, 10, 90), "southbound"),
                                        ((90, 99), "northbound"), ((90, 10, 90), "northbound")])
def test_invalid_or_relabelled_geometry_does_not_publish(db, points, key):
    topo, ref = topology(db), reference(db)
    with db.session() as session, pytest.raises(DomainError):
        catalog.publish_mapping(session, ref, topology_id=topo, flow=CorridorFlow(key=key, points=points),
            review_reference="review", expected_generation=0, now=NOW)
    with db.session() as session:
        assert session.get(RoadCorridorReference, ref).generation == 0
        assert session.scalar(select(func.count()).select_from(RoadCorridorMap)) == 0


@pytest.mark.parametrize("kind", ["policy", "asset", "topology", "projection", "size", "identity", "map", "review"])
def test_changed_bindings_are_rejected_without_disclosing_raw_data(db, kind):
    topo, ref = topology(db), reference(db)
    map_id = mapping(db, ref, topo)
    with db.session() as session:
        revision = session.get(RoadTopologyRevision, topo)
        if kind == "policy":
            revision.policy = {**revision.policy, "notifications_allowed": True}
        elif kind == "asset":
            revision.asset_hash = "b" * 64
        elif kind == "topology":
            revision.topology_hash = "c" * 64
        elif kind == "projection":
            revision.content = b"private licensed bytes"
        elif kind == "size":
            revision.content_size += 1
        elif kind == "identity":
            session.get(RoadCorridorReference, ref).name = "Different road"
        elif kind == "map":
            session.get(RoadCorridorMap, map_id).content = b"private flow bytes"
        else:
            session.get(RoadCorridorMap, map_id).review_reference = "Unreviewed replacement"
        session.commit()
    with pytest.raises(DomainError) as error:
        read(db, ref)
    assert error.value.status == 503
    assert "private" not in str(error.value)


def test_rollback_covers_new_topology_map_and_reference_generation(db):
    topo, ref = topology(db), reference(db)
    with db.session() as session:
        catalog.publish_mapping(session, ref, topology_id=topo, flow=CorridorFlow(key="northbound", points=(90, 10)),
            review_reference="review", expected_generation=0, now=NOW)
        catalog.publish_topology(session, definition=definition("not-committed"), asset_hash="a" * 64,
                                 policy=policy(), now=NOW)
        session.rollback()
    with db.session() as session:
        assert session.get(RoadCorridorReference, ref).generation == 0
        assert session.scalar(select(func.count()).select_from(RoadCorridorMap)) == 0
        assert session.scalar(select(func.count()).select_from(RoadTopologyRevision)) == 1


@pytest.mark.parametrize("revoked", [False, True])
def test_cleanup_removes_graph_and_flow_bytes_without_deleting_private_reference_ids(db, revoked):
    topo, ref = topology(db, valid_until=NOW + timedelta(seconds=1)), reference(db)
    map_id = mapping(db, ref, topo)
    with db.session() as session:
        if revoked:
            catalog.revoke_topology(session, topo, now=NOW)
            session.commit()
    cleanup(db, now=lambda: NOW + timedelta(seconds=2))
    cleanup(db, now=lambda: NOW + timedelta(seconds=3))
    with db.session() as session:
        assert session.get(RoadTopologyRevision, topo).content is None
        assert session.get(RoadCorridorMap, map_id).content is None
        assert session.get(RoadCorridorReference, ref).generation == 1
        assert session.get(RoadCorridorMap, map_id).binding_hash
    with pytest.raises(DomainError):
        read(db, ref)


def test_quota_rejects_projection_without_partial_rows(db, monkeypatch):
    monkeypatch.setattr(catalog, "MAX_PROJECTION_BYTES", 20)
    with pytest.raises(DomainError) as error:
        topology(db)
    assert error.value.code == "road_topology_capacity"
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(RoadTopologyRevision)) == 0


@pytest.mark.parametrize("updates", [{"reference": " "}, {"accepted_at": NOW + timedelta(seconds=1)},
                                     {"valid_until": NOW}, {"attribution": "line\nbreak"}])
def test_invalid_or_future_review_does_not_store_projection(db, updates):
    with pytest.raises(DomainError):
        topology(db, **updates)


def test_request_local_graph_reuse_rechecks_revocation_and_corruption(db):
    topo, ref = topology(db), reference(db)
    mapping(db, ref, topo)
    budget = catalog.CatalogReadBudget()
    with db.session() as session:
        first = catalog.resolve_reference(session, ref, table_key=TABLE, now=NOW, read_budget=budget)
        second = catalog.resolve_reference(session, ref, table_key=TABLE, now=NOW, read_budget=budget)
        assert first.topology is second.topology
        assert budget.used_bytes == session.get(RoadTopologyRevision, topo).content_size
        catalog.revoke_topology(session, topo, now=NOW)
        with pytest.raises(DomainError) as error:
            catalog.resolve_reference(session, ref, table_key=TABLE, now=NOW, read_budget=budget)
        assert error.value.code == "road_topology_permission_unavailable"
        session.rollback()
        session.get(RoadTopologyRevision, topo).content = b"corrupted after previous read"
        session.flush()
        with pytest.raises(DomainError) as error:
            catalog.resolve_reference(session, ref, table_key=TABLE, now=NOW, read_budget=budget)
        assert error.value.code == "road_topology_projection_invalid"
