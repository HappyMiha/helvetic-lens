"""Operator-reviewed road references, separate from traffic-feed permissions.

There is no native ASTRA importer or HTTP grant-write endpoint here. Publishing
attests review of a licensed asset and its normalized projection. Callers own
transactions. Private configurations store reference UUIDs, never TMC graphs.
"""

from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, or_, select, update

from .config import DomainError
from .monitoring_subjects import _savepoint
from .road_models import RoadCorridorMap, RoadCorridorReference, RoadTopologyRevision
from .road_sources import _clock, _encoded, _hash, _utc
from .road_topology import CorridorFlow, ResolvedCorridor, TmcTopology, TopologyDefinition, TopologyError

MAX_PROJECTION_BYTES = 16 * 1024**2
MAX_FLOW_BYTES = 256 * 1024
MAX_CATALOG_BYTES = 256 * 1024**2
MAX_READ_BYTES = 32 * 1024**2


@dataclass
class CatalogReadBudget:
    """Request-local parsed graph reuse; never a permission cache or global cache."""
    used_bytes: int = 0
    topologies: dict = field(default_factory=dict, repr=False)


class TopologyPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    reference: str = Field(min_length=1, max_length=500)
    attribution: str = Field(min_length=1, max_length=1000)
    review_reference: str = Field(min_length=1, max_length=500)
    accepted_at: datetime
    valid_until: datetime
    matching_allowed: bool
    display_allowed: bool
    notifications_allowed: bool


class CorridorIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    key: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    name: str = Field(min_length=1, max_length=200)
    flow_key: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")


@dataclass(frozen=True)
class ReviewedCorridor:
    reference_id: str
    generation: int
    mapping_id: str
    topology_id: str
    attribution: str
    topology: TmcTopology = field(repr=False)
    corridor: ResolvedCorridor = field(repr=False)


def _fail(code, status=409):
    raise DomainError("Reviewed road corridor data is unavailable.", status, code) from None


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip() and not any(ord(c) < 32 for c in value)


def _policy(value):
    policy = TopologyPolicy.model_validate_json(_encoded(value), strict=True)
    if (any(not _text(v) for v in (policy.reference, policy.attribution, policy.review_reference))
            or _clock(policy.valid_until) <= _clock(policy.accepted_at)):
        _fail("road_topology_policy_invalid", 422)
    return policy


def _binding(row):
    return _hash(_encoded({"id": row.id, "country": row.country, "table": row.table, "version": row.version,
        "asset_hash": row.asset_hash, "topology_hash": row.topology_hash, "content_hash": row.content_hash,
        "content_size": row.content_size, "policy": row.policy}))


def _rights(session, topology_id, *, now, matching=False, display=False, notification=False):
    now = _clock(now)
    row = session.scalar(select(RoadTopologyRevision).where(RoadTopologyRevision.id == topology_id)
                         .with_for_update().execution_options(populate_existing=True))
    if row is None or row.revoked_at is not None or not _utc(row.accepted_at) <= now < _utc(row.valid_until):
        _fail("road_topology_permission_unavailable")
    try:
        policy = _policy(row.policy)
        if (row.binding_hash != _binding(row) or _clock(policy.accepted_at) != _utc(row.accepted_at)
                or _clock(policy.valid_until) != _utc(row.valid_until)):
            _fail("road_topology_binding_invalid", 503)
    except (ValidationError, ValueError, TypeError):
        _fail("road_topology_binding_invalid", 503)
    if ((matching and not policy.matching_allowed) or (display and not policy.display_allowed)
            or (notification and not policy.notifications_allowed)):
        _fail("road_topology_use_denied", 403)
    return row, policy


def _projection(row, budget=None):
    if row.content is None:
        _fail("road_topology_projection_unavailable")
    if (len(row.content) > MAX_PROJECTION_BYTES or len(row.content) != row.content_size
            or _hash(row.content) != row.content_hash):
        _fail("road_topology_projection_invalid", 503)
    cache_key = (row.id, row.binding_hash, row.content_hash)
    if budget is not None:
        if cache_key in budget.topologies:
            return budget.topologies[cache_key]
        if budget.used_bytes + row.content_size > MAX_READ_BYTES:
            _fail("road_catalog_read_limit", 429)
    try:
        definition = TopologyDefinition.model_validate_json(row.content, strict=True)
        topology = TmcTopology(definition)
        if (topology.key != (row.country, row.table, row.version) or topology.sha256 != row.topology_hash
                or _encoded(definition.model_dump(mode="json")) != row.content):
            _fail("road_topology_projection_invalid", 503)
        if budget is not None:
            budget.used_bytes += row.content_size
            budget.topologies[cache_key] = topology
        return topology
    except (ValidationError, ValueError, TypeError):
        _fail("road_topology_projection_invalid", 503)


def publish_topology(session, *, definition: TopologyDefinition, asset_hash: str, policy: TopologyPolicy, now):
    """Internal attestation of an already reviewed asset, not automatic licence approval."""
    now = _clock(now)
    try:
        policy = _policy(policy.model_dump(mode="json"))
        definition = TopologyDefinition.model_validate_json(_encoded(definition.model_dump(mode="json")), strict=True)
        topology = TmcTopology(definition)
    except (ValidationError, ValueError, TypeError):
        _fail("road_topology_review_invalid", 422)
    if not _clock(policy.accepted_at) <= now < _clock(policy.valid_until):
        _fail("road_topology_review_not_current", 422)
    if not isinstance(asset_hash, str) or len(asset_hash) != 64 or any(c not in "0123456789abcdef" for c in asset_hash):
        _fail("road_topology_asset_hash_invalid", 422)
    # Canonical projection order keeps identical reviewed graphs reproducible.
    definition = definition.model_copy(update={"points": tuple(sorted(definition.points, key=lambda p: p.code))})
    content = _encoded(definition.model_dump(mode="json"))
    if len(content) > MAX_PROJECTION_BYTES:
        _fail("road_topology_capacity")
    count, size = session.execute(select(func.count(), func.coalesce(func.sum(func.length(RoadTopologyRevision.content)), 0))
                                 .select_from(RoadTopologyRevision)).one()
    if count >= 1000 or size + len(content) > MAX_CATALOG_BYTES:
        _fail("road_topology_capacity")
    with _savepoint(session):
        row = RoadTopologyRevision(country=definition.country, table=definition.table, version=definition.version,
            asset_hash=asset_hash, topology_hash=topology.sha256, policy=policy.model_dump(mode="json"), binding_hash="",
            content=content, content_hash=_hash(content), content_size=len(content),
            accepted_at=_clock(policy.accepted_at), valid_until=_clock(policy.valid_until))
        session.add(row)
        session.flush()
        row.binding_hash = _binding(row)
        session.flush()
        return row.id


def create_reference(session, *, identity: CorridorIdentity):
    try:
        identity = CorridorIdentity.model_validate_json(_encoded(identity.model_dump(mode="json")), strict=True)
    except (ValidationError, ValueError, TypeError):
        _fail("road_corridor_identity_invalid", 422)
    if not _text(identity.name):
        _fail("road_corridor_identity_invalid", 422)
    if session.scalar(select(RoadCorridorReference.id).where(RoadCorridorReference.key == identity.key)):
        _fail("road_corridor_key_exists")
    if session.scalar(select(func.count()).select_from(RoadCorridorReference)) >= 1000:
        _fail("road_corridor_capacity")
    row = RoadCorridorReference(**identity.model_dump(), identity_hash=_hash(_encoded(identity.model_dump(mode="json"))),
                               generation=0, enabled=True)
    session.add(row)
    session.flush()
    return row.id


def _reference(session, reference_id):
    row = session.scalar(select(RoadCorridorReference).where(RoadCorridorReference.id == reference_id)
                         .with_for_update().execution_options(populate_existing=True))
    if row is None:
        _fail("road_corridor_unavailable", 404)
    if _hash(_encoded({"key": row.key, "name": row.name, "flow_key": row.flow_key})) != row.identity_hash:
        _fail("road_corridor_identity_invalid", 503)
    return row


def _advance(session, ref, expected_generation):
    if type(expected_generation) is not int or ref.generation != expected_generation:
        _fail("road_corridor_generation_conflict")
    result = session.execute(update(RoadCorridorReference).where(RoadCorridorReference.id == ref.id,
        RoadCorridorReference.generation == expected_generation).values(generation=expected_generation + 1))
    if result.rowcount != 1:
        _fail("road_corridor_generation_conflict")
    return expected_generation + 1


def _map_hash(row, ref):
    return _hash(_encoded({"id": row.id, "reference_id": row.reference_id, "identity_hash": ref.identity_hash,
        "generation": row.generation, "topology_id": row.topology_id, "content_hash": _hash(row.content),
        "review_reference": row.review_reference, "reviewed_at": _utc(row.reviewed_at).isoformat()}))


def publish_mapping(session, reference_id, *, topology_id, flow: CorridorFlow, review_reference,
                    expected_generation, now):
    now = _clock(now)
    if not _text(review_reference) or len(review_reference) > 500:
        _fail("road_corridor_review_invalid", 422)
    # Fixed lock order: topology before reference. The same order applies to reads.
    topo, _ = _rights(session, topology_id, now=now, matching=True)
    topology = _projection(topo)
    try:
        flow = CorridorFlow.model_validate_json(_encoded(flow.model_dump(mode="json")), strict=True)
        topology.resolve_corridor(flow)
    except (ValidationError, TopologyError, ValueError, TypeError):
        _fail("road_corridor_geometry_invalid", 422)
    content = _encoded(flow.model_dump(mode="json"))
    if len(content) > MAX_FLOW_BYTES or session.scalar(select(func.count()).select_from(RoadCorridorMap)) >= 10_000:
        _fail("road_corridor_capacity")
    with _savepoint(session):
        ref = _reference(session, reference_id)
        if not ref.enabled or ref.flow_key != flow.key:
            _fail("road_corridor_flow_invalid", 422)
        generation = _advance(session, ref, expected_generation)
        row = RoadCorridorMap(reference_id=ref.id, generation=generation, topology_id=topology_id,
            content=content, binding_hash="", review_reference=review_reference, reviewed_at=now)
        session.add(row)
        session.flush()
        row.binding_hash = _map_hash(row, ref)
        session.flush()
        return row.id


def set_reference_enabled(session, reference_id, *, enabled, expected_generation):
    if type(enabled) is not bool:
        _fail("road_corridor_state_invalid", 422)
    with _savepoint(session):
        ref = _reference(session, reference_id)
        generation = _advance(session, ref, expected_generation)
        ref.enabled = enabled
        session.flush()
        return generation


def resolve_reference(session, reference_id, *, table_key: tuple[str, str, str], now,
                      display=False, notification=False, read_budget=None):
    """Internal exact mapping; latest denied revision never falls back to an older grant."""
    now = _clock(now)
    if (not isinstance(table_key, tuple) or len(table_key) != 3 or any(not _text(v) for v in table_key)):
        _fail("road_corridor_table_invalid", 422)
    row = session.scalar(select(RoadCorridorMap).join(RoadTopologyRevision).where(
        RoadCorridorMap.reference_id == reference_id,
        RoadTopologyRevision.country == table_key[0], RoadTopologyRevision.table == table_key[1],
        RoadTopologyRevision.version == table_key[2]).order_by(RoadCorridorMap.generation.desc()).limit(1)
        .execution_options(populate_existing=True))
    if row is None:
        _fail("road_corridor_mapping_unavailable")
    topo, policy = _rights(session, row.topology_id, now=now, matching=True, display=display, notification=notification)
    ref = _reference(session, reference_id)
    if not ref.enabled:
        _fail("road_corridor_disabled")
    # A publish that won the reference lock after our first SELECT must not allow
    # this reader to use an older map. Global generation includes other versions.
    latest = session.scalar(select(func.max(RoadCorridorMap.generation)).join(RoadTopologyRevision).where(
        RoadCorridorMap.reference_id == reference_id, RoadTopologyRevision.country == table_key[0],
        RoadTopologyRevision.table == table_key[1], RoadTopologyRevision.version == table_key[2]))
    if latest != row.generation or row.generation > ref.generation:
        _fail("road_corridor_generation_conflict")
    if row.content is None:
        _fail("road_corridor_mapping_unavailable")
    if len(row.content) > MAX_FLOW_BYTES or _map_hash(row, ref) != row.binding_hash or _utc(row.reviewed_at) > now:
        _fail("road_corridor_mapping_invalid", 503)
    topology = _projection(topo, read_budget)
    try:
        flow = CorridorFlow.model_validate_json(row.content, strict=True)
        if flow.key != ref.flow_key or _encoded(flow.model_dump(mode="json")) != row.content:
            _fail("road_corridor_mapping_invalid", 503)
        corridor = topology.resolve_corridor(flow)
    except (ValidationError, TopologyError, ValueError, TypeError):
        _fail("road_corridor_mapping_invalid", 503)
    return ReviewedCorridor(ref.id, ref.generation, row.id, topo.id, policy.attribution, topology, corridor)


def describe_reference(session, reference_id, *, table_key, now, read_budget=None):
    """Explicit permitted public projection: labels only, no location graph or asset."""
    result = resolve_reference(session, reference_id, table_key=table_key, now=now, display=True, read_budget=read_budget)
    ref = _reference(session, reference_id)
    return {"id": ref.id, "name": ref.name, "flow": ref.flow_key, "generation": result.generation,
            "attribution": result.attribution}


def revoke_topology(session, topology_id, *, now):
    now = _clock(now)
    row = session.scalar(select(RoadTopologyRevision).where(RoadTopologyRevision.id == topology_id).with_for_update()
                         .execution_options(populate_existing=True))
    if row is None:
        _fail("road_topology_permission_unavailable")
    if row.revoked_at is None:
        row.revoked_at = now
    session.flush()


def purge_catalog(session, *, now):
    """Drop denied graph/flow bytes, retain immutable identities and review hashes."""
    now = _clock(now)
    denied = select(RoadTopologyRevision.id).where(or_(RoadTopologyRevision.revoked_at.is_not(None),
                                                      RoadTopologyRevision.valid_until <= now))
    session.execute(update(RoadCorridorMap).where(RoadCorridorMap.topology_id.in_(denied),
        RoadCorridorMap.content.is_not(None)).values(content=None).execution_options(synchronize_session="fetch"))
    session.execute(update(RoadTopologyRevision).where(RoadTopologyRevision.id.in_(denied),
        RoadTopologyRevision.content.is_not(None)).values(content=None).execution_options(synchronize_session="fetch"))
    session.flush()
