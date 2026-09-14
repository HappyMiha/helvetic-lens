"""Read actual private domain evidence; never accept browser-supplied source facts."""
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from .config import DomainError
from .hazard_events import read_event
from .hazard_models import HazardDevelopment, HazardEventRevision, HazardMonitor
from .related_contracts import AuthorityReference, EventFact, EventReference, fingerprint
from .related_repository import clock, fail
from .river_delivery import current_condition, latest
from .river_models import RiverChange, RiverMeasurement, RiverMonitor, RiverSourceCache
from .river_runtime import station
from .road_events import event_view, version_view
from .road_models import RoadCorridorMap, RoadDevelopment, RoadEventVersion, RoadMonitor
from .road_sources import read_version


def instant(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Unknown source time")
    return value.astimezone(UTC)


class RelatedReader:
    def __init__(self, settings, boundaries, bindings=None):
        self.settings, self.boundaries, self.bindings = settings, boundaries, bindings

    def load(self, session, user_id, domain, monitor_id, event_id, *, now, revision=None, geographic_evidence=False):
        from .monitoring_subjects import _actor
        now = clock(now)
        organization = _actor(session, user_id)
        models = {"river": (RiverMonitor, RiverChange, self.settings.river_watch_enabled),
            "warnings": (HazardMonitor, HazardDevelopment, self.settings.hazard_watch_enabled),
            "traffic": (RoadMonitor, RoadDevelopment, self.settings.road_watch_enabled)}
        if domain not in models:
            fail("related_domain_invalid", 422)
        monitor_type, event_type, enabled = models[domain]
        if not enabled:
            fail("related_domain_disabled", 404)
        monitor = session.scalar(select(monitor_type).where(monitor_type.id == str(monitor_id),
            monitor_type.organization_id == organization, monitor_type.owner_user_id == user_id)
            .execution_options(populate_existing=True))
        if monitor is None:
            fail("related_event_not_found", 404)
        event = session.scalar(select(event_type).where(event_type.id == str(event_id),
            event_type.monitor_id == monitor.id, event_type.organization_id == organization)
            .execution_options(populate_existing=True))
        if event is None:
            fail("related_event_not_found", 404)
        if domain == "river" and revision is None:
            event = session.scalar(select(RiverChange).where(RiverChange.monitor_id == monitor.id,
                RiverChange.organization_id == organization, RiverChange.development_id == event.development_id,
                latest()).execution_options(populate_existing=True))
        if revision is not None and (type(revision) is not int or revision < 1):
            fail("related_revision_invalid", 422)
        try:
            result = getattr(self, "_" + domain)(session, user_id, monitor, event, revision, now)
        except (KeyError, TypeError, ValueError, AttributeError):
            # Malformed or expired retained evidence is unavailable, never a
            # partial source fact or a server traceback exposed to the reader.
            fail("related_evidence_invalid")
        fact = result["fact"]
        geography = result.pop("geographic_evidence", None)
        if geographic_evidence:
            result["geographic_evidence"] = geography
        if self.bindings is not None and fact.availability == "available":
            place = self.bindings(session, fact, now=now)
            fact = fact.model_copy(update={"place": place})
        return {**result, "fact": fact, "reference": fact.reference.model_dump(mode="json"),
            "monitor_name": monitor.configuration["name"], "source_state": fact.source_state,
            "authority": fact.authority.model_dump(mode="json"),
            "availability": "available" if fact.availability == "available" else "historical",
            "source_at": fact.starts_at.isoformat() if fact.starts_at else None,
            "source_until": fact.ends_at.isoformat() if fact.ends_at else None,
            "time_kind": fact.time_kind,
            "geography": fact.place.model_dump(mode="json") if fact.place else None}

    def resolve(self, session, user_id, ref, *, now):
        result = self.load(session, user_id, ref.domain, ref.monitor_id, ref.event_id, revision=ref.revision, now=now)
        if result["fact"].reference != ref:
            fail("related_event_changed")
        return result

    def candidates(self, session, user_id, domain, *, now, after=None, limit=20):
        from .monitoring_subjects import _actor
        organization = _actor(session, user_id)
        models = {"warnings": (HazardMonitor, HazardDevelopment),
                  "river": (RiverMonitor, RiverChange), "traffic": (RoadMonitor, RoadDevelopment)}
        if domain not in models or type(limit) is not int or not 1 <= limit <= 50:
            fail("related_page_invalid", 422)
        monitor, event = models[domain]
        query = select(event).join(monitor, event.monitor_id == monitor.id).where(
            monitor.organization_id == organization, monitor.owner_user_id == user_id,
            event.organization_id == organization)
        if domain == "river":
            query = query.where(latest())
        if after is not None:
            if session.scalar(query.where(event.id == str(after))) is None:
                fail("related_event_not_found", 404)
            query = query.where(event.id > str(after))
        rows = list(session.scalars(query.order_by(event.id).limit(limit + 1)))
        items = []
        for row in rows[:limit]:
            try:
                result = self.load(session, user_id, domain, row.monitor_id, row.id, now=now)
                items.append({k: v for k, v in result.items() if k != "fact"})
            except DomainError:
                items.append({"id": row.id, "domain": domain, "availability": "unavailable", "href": None})
        return {"items": items, "next": rows[limit - 1].id if len(rows) > limit else None}

    def _river(self, session, user_id, monitor, event, revision, now):
        if revision is not None and event.sequence != revision:
            fail("related_event_changed")
        sample = event.evidence.get("sample")
        if not sample or sample.get("station_id") != event.evidence.get("station_id"):
            fail("related_evidence_invalid")
        observed = instant(sample["timestamp"])
        if observed > now:
            fail("related_evidence_unavailable")
        current = monitor.status == "active" and event.revision == monitor.revision and current_condition(session, monitor, event, now=now) == "eligible"
        measured = session.scalar(select(RiverMeasurement).where(RiverMeasurement.station_id == sample["station_id"],
            RiverMeasurement.metric == sample["metric"], RiverMeasurement.measured_at == observed))
        fields = ("station_id", "metric", "timestamp", "value", "unit", "datum", "aggregation", "quality")
        current = current and measured is not None and all(measured.evidence.get(key) == sample.get(key) for key in fields)
        catalog = session.get(RiverSourceCache, "catalog", populate_existing=True)
        if catalog is None or catalog.error or catalog.fetched_at is None:
            current = False
        selected = station(session, sample["station_id"])
        feature = AuthorityReference(namespace="bafu:station", identifier=sample["station_id"])
        ref = EventReference(domain="river", monitor_id=UUID(monitor.id), event_id=UUID(event.id),
            revision=event.sequence, evidence_hash=fingerprint(event.evidence))
        fact = EventFact(reference=ref, authority=AuthorityReference(namespace="bafu:observation",
                identifier=f"{sample['station_id']}:{sample['metric']}:{observed.isoformat()}"),
            source_feature=feature, source_revision=fingerprint({key: selected.get(key) for key in ("id", "latitude", "longitude")}),
            availability="available" if current else "unavailable", source_state=event.kind,
            time_kind="instant", starts_at=observed, ends_at=None, place=None)
        return {"fact": fact, "href": f"/river-watch?monitor={monitor.id}&change={event.id}",
                "reviewed": event.decision is not None,
                "geographic_evidence": {key: selected.get(key) for key in ("id", "latitude", "longitude")}}

    def _warnings(self, session, user_id, monitor, event, revision, now):
        if not self.settings.hazard_source_enabled:
            fail("related_source_disabled")
        number = event.revision if revision is None else revision
        current = read_event(session, user_id, monitor.id, event.id, store=self.boundaries, now=now)
        selected = read_event(session, user_id, monitor.id,
            event.id, store=self.boundaries, now=now, revision=number)
        if selected.get("state") == "unavailable" or "source" not in selected:
            fail("related_evidence_unavailable")
        record = session.scalar(select(HazardEventRevision).where(HazardEventRevision.development_id == event.id,
            HazardEventRevision.organization_id == monitor.organization_id, HazardEventRevision.revision == number))
        message = selected["source"]["message"]
        areas = [{key: area[key] for key in ("polygons", "circles", "geocodes")}
                 for info in message["infos"] for area in info["areas"]]
        identity = message["identity"]
        decision = selected["decision"]
        starts = instant(decision["effective"]) if decision.get("effective") else None
        ends = instant(decision["expires"]) if decision.get("expires") else None
        # A CAP Cancel with no area cannot acquire invented geography from its title.
        known = bool(areas) and number == event.revision and current.get("state") != "unavailable" and monitor.status == "active"
        fact = EventFact(reference=EventReference(domain="warnings", monitor_id=UUID(monitor.id), event_id=UUID(event.id),
                revision=number, evidence_hash=record.fingerprint),
            authority=AuthorityReference(namespace="cap:message", identifier=fingerprint(identity)),
            source_feature=AuthorityReference(namespace="cap:area-set", identifier=fingerprint(areas)),
            source_revision=selected["proof"]["boundary"]["sha256"],
            availability="available" if known else "unavailable", source_state=selected["state"],
            time_kind="interval" if starts and ends and starts < ends else "unknown",
            starts_at=starts if starts and ends and starts < ends else None,
            ends_at=ends if starts and ends and starts < ends else None, place=None)
        return {"fact": fact, "href": f"/hazard-watch?monitor={monitor.id}&event={event.id}&revision={number}",
            "geographic_evidence": {"areas": areas, "boundary": selected["proof"]["boundary"]},
            "source_identity": {**identity, "sent": instant(identity["sent"]).isoformat()},
            "reviewed": selected["reviewed"], "current_source_state": current.get("state", "unavailable")}

    def _traffic(self, session, user_id, monitor, event, revision, now):
        if not self.settings.road_source_enabled:
            fail("related_source_disabled")
        number = event.sequence if revision is None else revision
        selected = session.scalar(select(RoadEventVersion).where(RoadEventVersion.development_id == event.id,
            RoadEventVersion.organization_id == monitor.organization_id, RoadEventVersion.sequence == number))
        if selected is None:
            fail("related_event_not_found", 404)
        value = version_view(session, event, selected, now=now)
        current = event_view(session, event, now=now)
        if value["availability"] != "available":
            fail("related_evidence_unavailable")
        source = read_version(session, event.permission_id, selected.proof["source_version_id"], now=now,
            fields=("event_kind", "validity", "location"))
        locations = [asdict(record.location) for record in source.records if record.location is not None]
        mappings = list(session.scalars(select(RoadCorridorMap).where(RoadCorridorMap.id.in_(selected.proof["mapping_ids"]))))
        payload = value["payload"]
        facts = [item for corridor in payload.get("corridors", {}).values() for item in corridor.get("facts", [])]
        windows = [(instant(item["valid_from"]), instant(item["valid_until"])) for item in facts
                   if item.get("valid_from") and item.get("valid_until")]
        starts = max((a for a, _ in windows), default=None)
        ends = min((b for _, b in windows), default=None)
        # Multiple disjoint source windows never become one invented long window.
        known = bool(windows) and len(windows) == len(facts) and starts < ends
        if not known:
            starts = ends = None
        usable = (bool(locations) and current["availability"] == "available" and number == event.sequence
            and monitor.status == "active" and monitor.revision == event.configuration_revision
            and selected.proof["mapping_ids"] == event.proof["mapping_ids"])
        if usable and selected.proof["source_version_id"] != event.proof["source_version_id"]:
            live_source = read_version(session, event.permission_id, event.proof["source_version_id"], now=now,
                fields=("event_kind", "validity", "location"))
            live_locations = [asdict(record.location) for record in live_source.records if record.location is not None]
            usable = sorted(locations, key=fingerprint) == sorted(live_locations, key=fingerprint)
        fact = EventFact(reference=EventReference(domain="traffic", monitor_id=UUID(monitor.id), event_id=UUID(event.id),
                revision=number, evidence_hash=fingerprint({"payload": selected.payload_hash, "proof": selected.proof_hash})),
            authority=AuthorityReference(namespace="astra:situation", identifier=source.source_id),
            source_feature=AuthorityReference(namespace="astra:tmc-location-set", identifier=fingerprint(sorted(locations, key=fingerprint))),
            source_revision=fingerprint(sorted(mapping.binding_hash for mapping in mappings)),
            availability="available" if usable else "unavailable", source_state=payload["state"],
            time_kind="interval" if known else "unknown", starts_at=starts, ends_at=ends, place=None)
        return {"fact": fact, "href": f"/road-watch?monitor={monitor.id}&event={event.id}&sequence={number}",
                "geographic_evidence": {"tmc_locations": locations,
                    "corridor_mappings": [{"id": mapping.id, "binding_hash": mapping.binding_hash} for mapping in mappings]},
                "reviewed": event.reviewed_sequence >= number,
                "current_source_state": (current.get("payload") or {}).get("state", "unavailable")}
