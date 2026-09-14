"""Actual CAP, FOEN and DATEX repository paths; synthetic licensed fixtures only."""
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_hazard_events import GeometryFixture, active_fixture, project
from test_hazard_sources import accept as hazard_accept
from test_hazard_sources import grant as hazard_grant
from test_hazard_sources import revised
from test_river_watch import config, sample, store
from test_road_jobs import NOW, feed, record, refresh
from test_road_jobs import setup as road_setup
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens import related_repository as stories
from helvetic_lens import river_runtime
from helvetic_lens.config import DomainError
from helvetic_lens.hazard_models import HazardDevelopment
from helvetic_lens.models import User
from helvetic_lens.related_bindings import BindingStore
from helvetic_lens.related_contracts import PlaceBinding, story_associations
from helvetic_lens.related_readers import RelatedReader
from helvetic_lens.river_models import RiverChange, RiverMonitor, RiverSourceCache
from helvetic_lens.road_models import RoadDevelopment
from helvetic_lens.road_sources import revoke_permission

db, template = _database_fixture, _template_fixture


class Boundaries(GeometryFixture):
    def municipality_identity(self, code, *, now):
        return {"state": "verified" if self.available and code in {"2701", "2702"} else "unavailable",
            "version": self.version, "sha256": self.sha256, "expires_on": "2026-10-01"}


def river_setup(db, actor="owner"):
    before = NOW - timedelta(minutes=10)
    with db.session() as session:
        for key in ("catalog", "2289", "danger"):
            session.add(RiverSourceCache(key=key, data={"stations": [{"id": "2289", "name": "Basel",
                "latitude": 47.56, "longitude": 7.59, "waterbody": "Rhine"}]} if key == "catalog" else {},
                fetched_at=before, next_fetch_at=NOW, failures=0))
        store(session, sample(before))
        store(session, sample(before, "danger", "1"))
        session.flush()
        monitor = river_runtime.create(session, actor, config(metrics=["W"]), str(uuid4()))["id"]
        river_runtime.command(session, actor, monitor, 1, "start", before)
        river_runtime.evaluate(session, session.get(RiverMonitor, monitor), before)
        store(session, sample(NOW, value="2.6"))
        store(session, sample(NOW, "danger", "1"))
        for key in ("catalog", "2289", "danger"):
            session.get(RiverSourceCache, key).fetched_at = NOW
        river_runtime.evaluate(session, session.get(RiverMonitor, monitor), NOW)
        session.commit()
        event = session.scalar(select(RiverChange).where(RiverChange.monitor_id == monitor))
        return monitor, event.id


def seed_sources(db, actor="owner"):
    boundaries = Boundaries()
    warning = active_fixture(db, actor=actor)
    grant = hazard_grant(db, private_decisions_allowed=True)
    receipt = hazard_accept(db, grant)
    warning_event = project(db, warning, grant, receipt, boundaries, actor=actor)["development_id"]
    road, permission, _, settings = road_setup(db, xml=feed(record(
        validity_extra="<overallEndTime>2026-09-13T18:00:00Z</overallEndTime>")), user_id=actor)
    refresh(db, road, settings)
    settings.hazard_watch_enabled = settings.hazard_source_enabled = settings.river_watch_enabled = True
    with db.session() as session:
        road_event = session.scalar(select(RoadDevelopment.id))
        session.get(User, actor).platform_admin = True
        session.commit()
    river, river_event = river_setup(db, actor)
    bindings = BindingStore(boundaries)
    reader = RelatedReader(settings, boundaries, bindings.select)
    return reader, bindings, permission, [
        ("warnings", warning, warning_event), ("river", river, river_event), ("traffic", road["id"], road_event)]


@pytest.fixture
def sources(db):
    return seed_sources(db)


def bind(session, reader, bindings, triple, *, place="2701"):
    member = reader.load(session, "owner", *triple, now=NOW)
    fact = member["fact"]
    binding = PlaceBinding(id=uuid4(), source_feature=fact.source_feature, source_revision=fact.source_revision,
        place_namespace="swisstopo:bfs_municipality", place_id=place, boundary_version="2026-01", boundary_hash="a" * 64,
        evidence_hash="b" * 64, accepted_at=NOW - timedelta(seconds=1), valid_until=NOW + timedelta(days=1))
    bindings.publish(session, "owner", reader=reader, reference=fact.reference, binding=binding, now=NOW)
    return reader.load(session, "owner", *triple, now=NOW)


def test_actual_three_source_story_revalidates_rights_and_keeps_separate_authorities(db, sources):
    reader, bindings, permission, triples = sources
    with db.session() as session:
        members = [bind(session, reader, bindings, triple) for triple in triples]
        assert all(member["availability"] == "available" for member in members)
        assert members[1]["time_kind"] == "instant"
        links = story_associations(tuple(m["fact"] for m in members), now=NOW)
        assert all(link.state == "possible" for link in links), ([link.reason for link in links],
            [(m["time_kind"], m["source_at"], m["source_until"]) for m in members])
        row = stories.create(session, "owner", "Possible local relationship", [m["reference"] for m in members],
            "create", resolve=reader.resolve, now=NOW)
        session.commit()
        detail = stories.view(session, "owner", row.id, resolve=reader.resolve, now=NOW)
        assert detail["association_state"] == "possible" and len(detail["links"]) == 3
        assert {m["authority"]["namespace"] for m in detail["members"]} == {"cap:message", "bafu:observation", "astra:situation"}
        assert all(m["href"].startswith("/") for m in detail["members"])
        revoke_permission(session, permission, now=NOW)
        session.commit()
        revoked = stories.view(session, "owner", row.id, resolve=reader.resolve, now=NOW)
        assert revoked["association_state"] == "unverified" and revoked["links"] == []
        traffic = next(m for m in revoked["members"] if m["reference"]["domain"] == "traffic")
        assert traffic["href"] is None and "authority" not in traffic
        assert sum(m["availability"] == "available" for m in revoked["members"]) == 2


def test_nearby_place_unknown_binding_and_revoked_boundary_never_link(db, sources):
    reader, bindings, _, triples = sources
    with db.session() as session:
        members = [reader.load(session, "owner", *triple, now=NOW) for triple in triples]
        assert all(m["geography"] is None for m in members)
        with pytest.raises(DomainError, match="Reload"):
            stories.create(session, "owner", "Time alone", [m["reference"] for m in members], "unknown", resolve=reader.resolve, now=NOW)
        members = [bind(session, reader, bindings, triple, place="2702" if triple[0] == "traffic" else "2701") for triple in triples]
        with pytest.raises(DomainError):
            stories.create(session, "owner", "Nearby", [m["reference"] for m in members], "nearby", resolve=reader.resolve, now=NOW)
        reader.boundaries.available = False
        assert reader.load(session, "owner", *triples[1], now=NOW)["geography"] is None


def test_candidates_pagination_foreign_owners_and_fail_closed_evidence(db, sources):
    reader, _, _, triples = sources
    with db.session() as session:
        for domain, _, identifier in triples:
            page = reader.candidates(session, "owner", domain, now=NOW, limit=1)
            assert len(page["items"]) == 1
            assert reader.candidates(session, "peer", domain, now=NOW)["items"] == []
            with pytest.raises(DomainError):
                reader.candidates(session, "peer", domain, now=NOW, after=identifier)
        river = session.get(RiverChange, triples[1][2])
        river.evidence = {**river.evidence, "sample": {"station_id": "2289", "timestamp": "broken"}}
        session.flush()
        value = reader.candidates(session, "owner", "river", now=NOW)["items"][0]
        assert value["availability"] == "unavailable" and "authority" not in value


def test_binding_review_requires_admin_exact_evidence_and_revocation_takes_effect(db, sources):
    reader, bindings, _, triples = sources
    with db.session() as session:
        member = bind(session, reader, bindings, triples[1])
        binding = PlaceBinding.model_validate_json(json.dumps(member["geography"]))
        session.get(User, "owner").platform_admin = False
        session.flush()
        with pytest.raises(DomainError):
            bindings.publish(session, "owner", reader=reader, reference=member["fact"].reference, binding=binding, now=NOW)
        session.get(User, "owner").platform_admin = True
        session.flush()
        bindings.revoke(session, "owner", binding.id, now=NOW)
        assert reader.load(session, "owner", *triples[1], now=NOW)["geography"] is None


def test_cancelled_warning_does_not_clear_other_sources_and_history_keeps_original_reference(db, sources):
    reader, bindings, _, triples = sources
    with db.session() as session:
        members = [bind(session, reader, bindings, triple) for triple in triples]
        row = stories.create(session, "owner", "Separate authorities", [m["reference"] for m in members],
            "save", resolve=reader.resolve, now=NOW)
        identifier = row.id
        permission = session.get(HazardDevelopment, triples[0][2]).permission_id
        session.commit()
    receipt = hazard_accept(db, permission, revised(kind="Cancel", infos=""), second=1, cursor=1)
    project(db, triples[0][1], permission, receipt, reader.boundaries, second=1)
    with db.session() as session:
        result = stories.view(session, "owner", identifier, resolve=reader.resolve, now=NOW + timedelta(seconds=1))
        assert result["association_state"] == "unverified"
        warning = next(member for member in result["members"] if member["reference"]["domain"] == "warnings")
        assert warning["reference"]["revision"] == 1 and warning["current_source_state"] == "cancelled"
        assert sum(member["availability"] == "available" for member in result["members"]) == 2


def test_river_correction_refreshes_reference_but_does_not_rewrite_saved_story(db, sources):
    reader, bindings, _, triples = sources
    with db.session() as session:
        members = [bind(session, reader, bindings, triple) for triple in triples]
        row = stories.create(session, "owner", "Correction", [m["reference"] for m in members], "save", resolve=reader.resolve, now=NOW)
        original = members[1]["reference"]
        store(session, sample(NOW, value="2.3"))
        river_runtime.evaluate(session, session.get(RiverMonitor, triples[1][1]), NOW)
        session.commit()
        current = reader.load(session, "owner", *triples[1], now=NOW)
        assert current["reference"]["event_id"] != original["event_id"] and current["reference"]["revision"] > original["revision"]
        old = stories.view(session, "owner", row.id, resolve=reader.resolve, now=NOW)
        assert old["association_state"] == "unverified" and any(m["reference"] == original for m in old["members"])
        replacement = [m["reference"] if m["reference"]["domain"] != "river" else current["reference"] for m in members]
        stories.change(session, "owner", row.id, 1, "refresh", label="Correction", values=replacement, resolve=reader.resolve, now=NOW)
        assert stories.view(session, "owner", row.id, resolve=reader.resolve, now=NOW)["association_state"] == "possible"
        assert len(reader.candidates(session, "owner", "river", now=NOW)["items"]) == 1


def test_official_danger_observation_links_without_inventing_level_from_water_height(db, sources):
    reader, bindings, _, triples = sources
    with db.session() as session:
        store(session, sample(NOW, "danger", "3"))
        river_runtime.evaluate(session, session.get(RiverMonitor, triples[1][1]), NOW)
        danger = session.scalar(select(RiverChange).where(RiverChange.monitor_id == triples[1][1], RiverChange.kind == "danger_escalation"))
        assert danger.evidence["sample"]["metric"] == "danger"
        session.flush()
        selected = [triples[0], ("river", triples[1][1], danger.id), triples[2]]
        members = [bind(session, reader, bindings, triple) for triple in selected]
        row = stories.create(session, "owner", "Official danger and independent warnings", [m["reference"] for m in members],
            "danger-story", resolve=reader.resolve, now=NOW)
        result = stories.view(session, "owner", row.id, resolve=reader.resolve, now=NOW)
        assert result["association_state"] == "possible"
        assert any(":danger:" in m["authority"]["identifier"] for m in result["members"])
