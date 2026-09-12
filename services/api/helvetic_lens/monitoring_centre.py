"""Owner-private inventory; reuses domain readers, never collects or activates."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import and_, or_, select

from . import air_runtime, monitoring_runtime, river_runtime
from .air_models import AirMonitor
from .auth import Identity
from .config import DomainError
from .models import MonitoringSubject
from .monitoring_contracts import ReaderMode
from .monitoring_live_models import MonitoringRuntime
from .monitoring_subjects import _actor, _view
from .river_contracts import utc
from .river_models import RiverMonitor

MODELS = {"air": AirMonitor, "pollen": MonitoringSubject, "river": RiverMonitor}
Domain = Literal["air", "pollen", "river"]
Status = Literal["draft", "active", "paused", "archived"]


def capabilities(settings, organization):
    mode = monitoring_runtime._mode(settings, organization)
    pollen = settings.deployment_instance in {"main", "monitoring-v2"} and mode in {
        ReaderMode.ENABLED,
        ReaderMode.SHADOW,
    }
    return [
        {"id": "warnings", "group": "personal", "availability": "blocked", "href": None},
        {"id": "commute", "group": "personal", "availability": "blocked", "href": None},
        {"id": "traffic", "group": "personal", "availability": "blocked", "href": None},
        {
            "id": "pollen",
            "group": "personal",
            "availability": (
                "preview_only"
                if pollen and mode == ReaderMode.SHADOW
                else "available"
                if pollen
                else "disabled"
            ),
            "href": "/pollen-watch" if pollen else None,
        },
        {
            "id": "river",
            "group": "personal",
            "availability": "available" if settings.river_watch_enabled else "disabled",
            "href": "/river-watch" if settings.river_watch_enabled else None,
        },
        {
            "id": "air",
            "group": "personal",
            "availability": "available" if settings.air_watch_enabled else "disabled",
            "href": "/air-watch" if settings.air_watch_enabled else None,
        },
        {"id": "tenders", "group": "business", "availability": "blocked", "href": None},
        {"id": "ip", "group": "business", "availability": "blocked", "href": None},
        {"id": "auctions", "group": "business", "availability": "blocked", "href": None},
    ]


def scoped(model, organization, user):
    query = select(model).where(model.organization_id == organization, model.owner_user_id == user)
    if model is MonitoringSubject:
        query = query.where(model.template_id == "pollen-watch", model.template_version == 1)
    return query


def inventory(session, settings, user_id, *, domain=None, status=None, cursor=None, limit=30):
    organization = _actor(session, user_id)
    templates = capabilities(settings, organization)
    available = {item["id"]: item for item in templates}
    anchor = None
    if cursor:
        try:
            kind, identifier = cursor.split(":")
            model = MODELS[kind]
            identifier = str(UUID(identifier))
        except (ValueError, KeyError) as error:
            raise DomainError("Invalid monitor cursor.", 422, "monitor_cursor_invalid") from error
        row = session.scalar(scoped(model, organization, user_id).where(model.id == identifier))
        if row is None:
            raise DomainError("Refresh the monitor list.", 422, "monitor_cursor_invalid")
        anchor = (utc(row.created_at), kind, row.id)
    rows = []
    for kind, model in MODELS.items():
        if domain and domain != kind:
            continue
        query = scoped(model, organization, user_id)
        if status:
            query = query.where(model.status == status)
        if anchor:
            clock, anchor_kind, identifier = anchor
            # Newest time first, then ascending domain and UUID for stable ties.
            tie = model.id > identifier if kind == anchor_kind else kind > anchor_kind
            query = query.where(or_(model.created_at < clock, and_(model.created_at == clock, tie)))
        rows.extend(
            (kind, row)
            for row in session.scalars(query.order_by(model.created_at.desc(), model.id).limit(limit + 1))
        )
    rows.sort(key=lambda entry: (-utc(entry[1].created_at).timestamp(), entry[0], entry[1].id))
    items = [summary(session, settings, kind, row, available[kind]) for kind, row in rows[:limit]]
    return {
        "templates": templates,
        "items": items,
        "next_cursor": f"{rows[limit - 1][0]}:{rows[limit - 1][1].id}" if len(rows) > limit else None,
    }


def summary(session, settings, kind, row, capability):
    enabled = capability["href"] is not None
    now = datetime.now(UTC)
    runtime = row
    observation = None
    if kind == "pollen":
        config = _view(session, row)["configuration"]
        runtime = session.get(MonitoringRuntime, row.id)
        health = "waiting"
        if enabled and row.status == "active":
            current = monitoring_runtime.state(
                session, settings=settings, user_id=row.owner_user_id, subject_id=row.id, now=now
            )
            health = current["runtime"]["health"]
            if health == "unavailable" and any(
                item["availability"] == "stale" for item in current["current"]
            ):
                health = "stale"
            observation = max(
                (
                    item["sample"]["valid_at"]
                    for item in current["current"]
                    if item["availability"] == "usable"
                    and item["sample"]["series"]["period"] != "forecast_instant"
                ),
                default=None,
                key=utc,
            )
        href = f"/pollen-watch#draft={row.id}"
    else:
        config = row.configuration
        value = (air_runtime.view(row) if kind == "air" else river_runtime.view(row)) if enabled else {}
        health = value.get("health", "disabled")
        observation = max(
            (
                item["sample"]["timestamp"]
                for item in value.get("state", {}).get("coverage", {}).values()
                if item.get("status") == "current" and item.get("sample")
            ),
            default=None,
            key=utc,
        )
        href = f"/{kind}-watch?monitor={row.id}"
    health = "disabled" if not enabled else "not_started" if row.status == "draft" else health
    # Metadata remains manageable/discoverable when a source is disabled. Never
    # expose source values or read its runtime evidence through the kill switch.
    return {
        "id": row.id,
        "domain": kind,
        "name": config.get("name"),
        "station_id": config["station_id"],
        "status": row.status,
        "health": health,
        "href": href if enabled else None,
        "metrics": config.get("metrics", [item["allergen"] for item in config.get("selections", [])]),
        "last_observation_at": observation if row.status == "active" and enabled else None,
        "last_check_at": utc(runtime.last_poll_at).isoformat()
        if enabled and runtime and runtime.last_poll_at
        else None,
        "next_check_at": utc(runtime.next_poll_at).isoformat()
        if enabled and runtime and row.status == "active"
        else None,
    }


def centre_router(service, settings):
    def identity(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        actor = getattr(request.state, "identity", None)
        if actor is None:
            raise DomainError("Sign in to continue.", 401, "authentication_required")
        return actor

    router = APIRouter(prefix="/api/monitoring-centre", tags=["monitoring-centre"])

    @router.get("")
    def listing(
        domain: Domain | None = None,
        status: Status | None = None,
        cursor: str | None = Query(default=None, max_length=64),
        limit: int = Query(default=30, ge=1, le=50),
        actor: Identity = Depends(identity),
    ):
        with service.db.session() as session:
            return inventory(
                session, settings, actor.user_id, domain=domain, status=status, cursor=cursor, limit=limit
            )

    return router
