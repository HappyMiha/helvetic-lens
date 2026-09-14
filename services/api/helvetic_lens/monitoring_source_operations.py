"""Bounded platform diagnostics from public source metadata, without I/O or writes.

Permission-record validity and acquisition are separate facts. This reader never
grants coverage, rights, monitor activation or email consent.
"""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import case, exists, func, select

from .air_models import AirSourceCache
from .aste_models import AsteCollector
from .auction_source_models import AuctionSourcePermission, AuctionSourceSelection
from .commute_models import CommuteFeedState, CommuteSourcePermission, CommuteSourcePoll
from .config import DomainError
from .hazard_native_source import permission_id as hazard_permission_id
from .hazard_source_models import HazardSourcePermission, HazardSourcePoll, HazardSourceSelection
from .ipi_models import IPITraversal
from .monitoring_live_models import MonitoringSourceChannel
from .river_models import RiverSourceCache
from .road_models import RoadSourceHead, RoadSourcePermission, RoadSourcePoll
from .road_sources import SOURCE as ROAD_SOURCE
from .tender_models import TenderSourceLease
from .trademark_source_models import TrademarkSourcePermission, TrademarkSourceSelection
from .transport_feed import ALERTS, TRIPS

PACKS = ("safety_environment", "mobility", "business_opportunities", "intellectual_property")


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def stamp(value):
    return utc(value).isoformat() if value is not None else None


def age(value, now):
    return max(0, int((now - utc(value)).total_seconds())) if value is not None and utc(value) <= now else None


def permission(session, model, identifier, now):
    # Select timestamps only: policy JSON can contain endpoints, attribution and
    # operator references that are neither necessary nor safe diagnostics.
    columns = (model.accepted_at, model.valid_until, model.revoked_at)
    row = session.execute(select(*columns).where(model.id == identifier)).first() if identifier else None
    if row is None:
        return {"state": "missing", "expires_at": None}
    accepted, expires, revoked = row
    state = "revoked" if revoked is not None else "not_yet_valid" if utc(accepted) > now else "expired" if utc(expires) <= now else "record_current"
    return {"state": state, "expires_at": stamp(expires)}


def summary(session, model, *, success=None, error=None, next_at=None, observed=None, where=(), now):
    """A fixed-size aggregate, including old/failed channels rather than newest only."""
    fields = [func.count()]
    fields += [func.min(success), func.max(success), func.sum(case((success.is_(None), 1), else_=0))] if success is not None else [None, None, None]
    fields += [func.sum(case((error.is_not(None), 1), else_=0)) if error is not None else None,
               func.min(next_at) if next_at is not None else None,
               func.max(observed) if observed is not None else None]
    count, oldest, latest, never, errors, next_request, published = session.execute(select(*fields).select_from(model).where(*where)).one()
    # Count only clocks that purport to have already happened; a future scheduled
    # request is normal. Do not make a negative age look like zero delay.
    invalid = any(value is not None and utc(value) > now for value in (oldest, latest, published))
    return {"record_count": count, "never_succeeded_count": int(never or 0) if success is not None else None,
        "error_count": int(errors or 0) if error is not None else None,
        "oldest_success_at": stamp(oldest), "latest_success_at": stamp(latest),
        "oldest_success_age_seconds": age(oldest, now), "latest_success_age_seconds": age(latest, now),
        "source_published_at": stamp(published), "next_request_at": stamp(next_request),
        "invalid_clock": invalid,
        "state": "invalid_clock" if invalid else "errors" if errors else "unobserved" if not count else
                 "partial" if never else "recorded" if latest is not None else "unknown"}


def empty():
    return {"state": "unobserved", "record_count": 0, "never_succeeded_count": None,
        "error_count": None, "oldest_success_at": None, "latest_success_at": None,
        "oldest_success_age_seconds": None, "latest_success_age_seconds": None,
        "source_published_at": None, "next_request_at": None, "invalid_clock": False}


def snapshot(session, settings, *, now=None):
    now = now or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Use an aware diagnostic clock")
    now = now.astimezone(UTC)
    items = []

    def add(domain, pack, href, enabled, collector, access, acquisition, note):
        items.append({"id": domain, "pack": pack, "href": href, "section_enabled": enabled,
            "collector": collector, "access": access, "acquisition": acquisition, "note": note})

    current = [c for c in settings.pollen_source_policy.channels
               if c.status == "approved" and c.valid_from <= now < c.valid_until]
    all_expiries = [c.valid_until for c in current]
    channels = settings.pollen_source_policy.channels
    pollen_state = "partial" if current and len(current) != len(channels) else "record_current" if current else (
        "revoked" if any(c.status == "revoked" for c in channels) else
        "expired" if channels and all(c.valid_until <= now for c in channels) else
        "not_yet_valid" if channels and all(c.valid_from > now for c in channels) else "missing")
    pollen_access = {"state": pollen_state, "expires_at": stamp(min(all_expiries)) if all_expiries else None}
    add("pollen", PACKS[0], "/pollen-watch", settings.monitoring_rollout.enabled,
        "configured" if settings.monitoring_rollout.enabled else "disabled", pollen_access,
        summary(session, MonitoringSourceChannel, success=MonitoringSourceChannel.last_success_at,
            error=MonitoringSourceChannel.error_code, next_at=MonitoringSourceChannel.next_fetch_at, now=now), "channel_scope")

    for domain, model, enabled in (("river", RiverSourceCache, settings.river_watch_enabled),
                                  ("air", AirSourceCache, settings.air_watch_enabled)):
        add(domain, PACKS[0], f"/{domain}-watch", enabled, "configured" if enabled else "disabled",
            {"state": "public_contract", "expires_at": None},
            summary(session, model, success=model.fetched_at, error=model.error, next_at=model.next_fetch_at, now=now),
            "station_scope")

    identifier = hazard_permission_id(session, settings)
    protocol = session.scalar(select(HazardSourcePermission.policy["protocol"].as_string())
        .where(HazardSourcePermission.id == identifier)) if identifier else None
    native = protocol == "meteoalarm-v2"
    data = summary(session, HazardSourceSelection, success=HazardSourceSelection.last_poll_at,
        where=(HazardSourceSelection.permission_id == identifier,), now=now)
    if native:
        data = summary(session, HazardSourcePoll, success=HazardSourcePoll.last_success_at,
            next_at=HazardSourcePoll.next_request_at, where=(HazardSourcePoll.permission_id == identifier,), now=now)
        failures = session.scalar(select(HazardSourcePoll.failures).where(HazardSourcePoll.permission_id == identifier))
        data["error_count"] = int(bool(failures)) if failures is not None else None
        if failures and not data["invalid_clock"]:
            data["state"] = "errors"
    add("warnings", PACKS[0], "/hazard-watch", settings.hazard_watch_enabled,
        ("configured" if native else "channel_required") if settings.hazard_source_enabled else "disabled",
        permission(session, HazardSourcePermission, identifier, now), data, "warning_channel")

    feeds = []
    for source, identifier, key in ((TRIPS, settings.commute_gtfs_rt_permission_id, settings.commute_gtfs_rt_key),
                                   (ALERTS, settings.commute_gtfs_sa_permission_id, settings.commute_gtfs_sa_key)):
        access = permission(session, CommuteSourcePermission, identifier, now)
        data = summary(session, CommuteFeedState, success=CommuteFeedState.received_at,
            observed=CommuteFeedState.observed_at,
            where=(CommuteFeedState.source == source, CommuteFeedState.permission_id == identifier), now=now)
        poll = summary(session, CommuteSourcePoll, next_at=CommuteSourcePoll.next_request_at,
            where=(CommuteSourcePoll.source == source, CommuteSourcePoll.permission_id == identifier), now=now)
        data["next_request_at"] = poll["next_request_at"]
        # last_code includes successful outcomes; failures is the error signal.
        failures = session.scalar(select(CommuteSourcePoll.failures).where(CommuteSourcePoll.source == source,
            CommuteSourcePoll.permission_id == identifier))
        data["error_count"] = int(bool(failures)) if failures is not None else None
        if failures and not data["invalid_clock"]:
            data["state"] = "errors"
        feeds.append({"id": "trip_updates" if source == TRIPS else "service_alerts", "access": access,
            "collector": "disabled" if not settings.commute_source_enabled else "credentials_required" if not key.get_secret_value() else "configured",
            "acquisition": data})
    add("commute", PACKS[1], "/commute-watch", settings.commute_watch_enabled,
        "configured" if settings.commute_source_enabled else "disabled", {"state": "per_channel", "expires_at": None},
        empty(), "timetable_scope")
    items[-1]["channels"] = feeds

    identifier = settings.road_source_permission_id
    data = summary(session, RoadSourcePoll, success=RoadSourcePoll.last_success_at, next_at=RoadSourcePoll.next_request_at,
        where=(RoadSourcePoll.source == ROAD_SOURCE, RoadSourcePoll.permission_id == identifier), now=now)
    head = summary(session, RoadSourceHead, observed=RoadSourceHead.published_at,
        where=(RoadSourceHead.source == ROAD_SOURCE, RoadSourceHead.permission_id == identifier), now=now)
    data["source_published_at"] = head["source_published_at"]
    data["invalid_clock"] |= head["invalid_clock"]
    failures = session.scalar(select(RoadSourcePoll.failures).where(RoadSourcePoll.source == ROAD_SOURCE,
        RoadSourcePoll.permission_id == identifier))
    data["error_count"] = int(bool(failures)) if failures is not None else None
    if data["invalid_clock"] or failures:
        data["state"] = "invalid_clock" if data["invalid_clock"] else "errors"
    add("traffic", PACKS[1], "/road-watch", settings.road_watch_enabled,
        "disabled" if not settings.road_source_enabled else "credentials_required" if not settings.road_source_key.get_secret_value() else "configured",
        permission(session, RoadSourcePermission, identifier, now), data, "topology_scope")

    add("tenders", PACKS[2], "/tender-watch", settings.tender_watch_enabled,
        "configured" if settings.simap_public_source_enabled else "disabled",
        {"state": "public_contract", "expires_at": None},
        summary(session, TenderSourceLease, next_at=TenderSourceLease.next_request_at, now=now), "publications_only")

    identifier = settings.aste_source_permission_id
    auction_selected = exists(select(AuctionSourceSelection.source_key).where(
        AuctionSourceSelection.permission_id == identifier, AuctionSourceSelection.source_key == AsteCollector.source_key,
        AuctionSourceSelection.generation == AsteCollector.generation))
    add("auctions", PACKS[2], "/auction-watch", settings.auction_watch_enabled,
        "configured" if settings.aste_source_enabled else "disabled",
        permission(session, AuctionSourcePermission, identifier, now),
        summary(session, AsteCollector, success=AsteCollector.last_completed_at, error=AsteCollector.last_error,
            next_at=AsteCollector.next_request_at, where=(AsteCollector.permission_id == identifier, auction_selected), now=now), "auction_scope")

    identifier = settings.ipi_source_permission_id
    selected = select(TrademarkSourceSelection.source_key, TrademarkSourceSelection.generation).where(
        TrademarkSourceSelection.permission_id == identifier).subquery()
    # Historical generations do not make a replacement source look collected.
    scope = exists(select(selected.c.source_key).where(selected.c.source_key == IPITraversal.source_key,
        selected.c.generation == IPITraversal.generation))
    latest = select(IPITraversal.id).where(IPITraversal.permission_id == identifier, scope).order_by(
        IPITraversal.started_at.desc(), IPITraversal.id.desc()).limit(1).scalar_subquery()
    from .ipi_collector import readiness
    add("ip", PACKS[3], "/trademark-watch", settings.trademark_watch_enabled, readiness(settings),
        permission(session, TrademarkSourcePermission, identifier, now),
        summary(session, IPITraversal, success=IPITraversal.completed_at, error=IPITraversal.last_error,
            next_at=IPITraversal.next_attempt_at, where=(IPITraversal.id == latest,), now=now), "register_scope")
    return {"checked_at": now.isoformat(), "release": settings.deployment_release,
            "packs": list(PACKS), "items": items}


def source_operations_router(service, settings):
    def administrator(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        identity = getattr(request.state, "identity", None)
        if identity is None:
            raise DomainError("Sign in to continue.", 401, "authentication_required")
        if not identity.platform_admin:
            raise DomainError("Platform administration is required.", 403, "platform_admin_required")

    router = APIRouter(prefix="/api/admin/monitoring-sources", dependencies=[Depends(administrator)])

    @router.get("")
    def read():
        with service.db.session() as session:
            return snapshot(session, settings)

    return router
