"""Authenticated C7 reader; ordinary auth, CSRF, rate and workspace gates apply."""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import aliased

from .air_contracts import AirConfiguration, utc
from .air_models import AirChange, AirMonitor, AirReadingVersion, AirRevision
from .air_runtime import change_view, command, create, edit, mute, owned, preview, remove, review, view
from .air_sources import catalogue, collect
from .auth import Identity
from .config import DomainError
from .monitoring_subjects import _actor


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfigurationBody(Input):
    configuration: AirConfiguration


class CreateBody(ConfigurationBody):
    request_key: UUID


class VersionBody(Input):
    expected_version: int = Field(strict=True, ge=1)


class EditBody(ConfigurationBody, VersionBody):
    pass


class CommandBody(VersionBody):
    action: Literal["start", "pause", "resume", "archive"]


class MuteBody(VersionBody):
    metric: Literal["O3", "NO2", "PM10", "PM25"]
    muted: bool = Field(strict=True)


class ReviewBody(Input):
    expected_version: int = Field(strict=True, ge=0)
    decision: Literal["reviewed", "not_relevant", "continue", "action_required"]


def air_router(service, settings):
    def identity(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        actor = getattr(request.state, "identity", None)
        if actor is None:
            raise DomainError("Sign in to continue.", 401, "authentication_required")
        if not settings.air_watch_enabled:
            raise DomainError("Air Quality Watch is unavailable.", 404, "air_disabled")
        with service.db.session() as session:
            _actor(session, actor.user_id)
        return actor

    router = APIRouter(prefix="/api/air-watch", tags=["air-watch"], dependencies=[Depends(identity)])

    @router.get("/today")
    def today(
        before: datetime | None = None, before_id: UUID | None = None, actor: Identity = Depends(identity)
    ):
        if bool(before) != bool(before_id):
            raise DomainError("Both history cursor fields are required.", 422, "air_cursor_invalid")
        with service.db.session() as session:
            newer = aliased(AirChange)
            query = (
                select(AirChange, AirMonitor)
                .join(AirMonitor, AirMonitor.id == AirChange.monitor_id)
                .where(
                    AirMonitor.owner_user_id == actor.user_id,
                    AirMonitor.status != "archived",
                    ~exists(
                        select(newer.id).where(
                            newer.development_id == AirChange.development_id,
                            newer.sequence > AirChange.sequence,
                        )
                    ),
                )
            )
            if before:
                query = query.where(
                    or_(
                        AirChange.created_at < utc(before),
                        and_(AirChange.created_at == utc(before), AirChange.id < str(before_id)),
                    )
                )
            rows = list(
                session.execute(query.order_by(AirChange.created_at.desc(), AirChange.id.desc()).limit(51))
            )
            items = [
                {
                    **change_view(event),
                    "monitor_id": monitor.id,
                    "monitor_name": monitor.configuration["name"],
                    "monitor_status": monitor.status,
                    "health": view(monitor)["health"],
                    "muted": event.evidence["sample"]["metric"] in monitor.configuration["muted_metrics"],
                }
                for event, monitor in rows[:50]
            ]
            return {
                "items": items,
                "next": {"before": utc(rows[49][0].created_at).isoformat(), "before_id": rows[49][0].id}
                if len(rows) > 50
                else None,
            }

    @router.get("/stations")
    def stations():
        collect(service.db, "catalog")
        with service.db.session() as session:
            return catalogue(session)

    @router.post("/preview")
    def preview_configuration(body: ConfigurationBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            _actor(session, actor.user_id, write=True)
        collect(service.db, "catalog")
        collect(service.db, body.configuration.station_id)
        with service.db.session() as session:
            _actor(session, actor.user_id, write=True)
            return preview(session, body.configuration.model_dump(mode="json"), datetime.now(UTC))

    @router.get("/monitors")
    def monitors(actor: Identity = Depends(identity)):
        with service.db.session() as session:
            rows = session.scalars(
                select(AirMonitor)
                .where(AirMonitor.owner_user_id == actor.user_id)
                .order_by(AirMonitor.created_at.desc())
                .limit(50)
            )
            return {"items": [view(row) for row in rows]}

    @router.post("/monitors", status_code=201)
    def create_monitor(body: CreateBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = create(
                session, actor.user_id, body.configuration.model_dump(mode="json"), str(body.request_key)
            )
            session.commit()
            return result

    @router.get("/monitors/{monitor_id}")
    def monitor_detail(monitor_id: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return view(owned(session, actor.user_id, str(monitor_id)))

    @router.patch("/monitors/{monitor_id}")
    def edit_monitor(monitor_id: UUID, body: EditBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = edit(
                session,
                actor.user_id,
                str(monitor_id),
                body.expected_version,
                body.configuration.model_dump(mode="json"),
            )
            session.commit()
            return result

    @router.post("/monitors/{monitor_id}/command")
    def transition(monitor_id: UUID, body: CommandBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = command(
                session, actor.user_id, str(monitor_id), body.expected_version, body.action, datetime.now(UTC)
            )
            session.commit()
            return result

    @router.delete("/monitors/{monitor_id}", status_code=204)
    def delete_monitor(monitor_id: UUID, body: VersionBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            remove(session, actor.user_id, str(monitor_id), body.expected_version)
            session.commit()
        return Response(status_code=204)

    @router.post("/monitors/{monitor_id}/mute")
    def mute_pollutant(monitor_id: UUID, body: MuteBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = mute(
                session,
                actor.user_id,
                str(monitor_id),
                body.expected_version,
                body.metric,
                body.muted,
                datetime.now(UTC),
            )
            session.commit()
            return result

    @router.get("/monitors/{monitor_id}/changes")
    def changes(
        monitor_id: UUID,
        before: int | None = Query(default=None, ge=1),
        limit: int = Query(default=50, ge=1, le=100),
        actor: Identity = Depends(identity),
    ):
        with service.db.session() as session:
            owned(session, actor.user_id, str(monitor_id))
            statement = select(AirChange).where(AirChange.monitor_id == str(monitor_id))
            if before:
                statement = statement.where(AirChange.sequence < before)
            rows = list(session.scalars(statement.order_by(AirChange.sequence.desc()).limit(limit + 1)))
            return {
                "items": [change_view(row) for row in rows[:limit]],
                "next_before": rows[limit - 1].sequence if len(rows) > limit else None,
            }

    @router.get("/monitors/{monitor_id}/measurements")
    def measurements(
        monitor_id: UUID,
        before: datetime | None = None,
        before_id: str | None = Query(default=None, pattern=r"^[a-f0-9]{64}$"),
        limit: int = Query(default=100, ge=1, le=200),
        actor: Identity = Depends(identity),
    ):
        if bool(before) != bool(before_id):
            raise DomainError("Both history cursor fields are required.", 422, "air_cursor_invalid")
        with service.db.session() as session:
            row = owned(session, actor.user_id, str(monitor_id))
            selected = row.configuration["metrics"]
            statement = select(AirReadingVersion).where(
                AirReadingVersion.station_id == row.configuration["station_id"],
                AirReadingVersion.metric.in_(selected),
                AirReadingVersion.measured_at >= datetime.now(UTC) - timedelta(days=30),
            )
            if before:
                statement = statement.where(
                    or_(
                        AirReadingVersion.measured_at < utc(before),
                        and_(AirReadingVersion.measured_at == utc(before), AirReadingVersion.id < before_id),
                    )
                )
            rows = list(
                session.scalars(
                    statement.order_by(
                        AirReadingVersion.measured_at.desc(), AirReadingVersion.id.desc()
                    ).limit(limit + 1)
                )
            )
            return {
                "items": [item.evidence for item in rows[:limit]],
                "next": {
                    "before": utc(rows[limit - 1].measured_at).isoformat(),
                    "before_id": rows[limit - 1].id,
                }
                if len(rows) > limit
                else None,
                "retention_days": 30,
            }

    @router.get("/monitors/{monitor_id}/revisions")
    def revisions(
        monitor_id: UUID, before: int | None = Query(default=None, ge=1), actor: Identity = Depends(identity)
    ):
        with service.db.session() as session:
            owned(session, actor.user_id, str(monitor_id))
            statement = select(AirRevision).where(AirRevision.monitor_id == str(monitor_id))
            if before:
                statement = statement.where(AirRevision.revision < before)
            rows = list(session.scalars(statement.order_by(AirRevision.revision.desc()).limit(51)))
            return {
                "items": [{"revision": r.revision, "configuration": r.configuration} for r in rows[:50]],
                "next_before": rows[49].revision if len(rows) > 50 else None,
            }

    @router.post("/monitors/{monitor_id}/changes/{change_id}/review")
    def review_change(
        monitor_id: UUID, change_id: UUID, body: ReviewBody, actor: Identity = Depends(identity)
    ):
        with service.db.session() as session:
            result = review(
                session, actor.user_id, str(monitor_id), str(change_id), body.expected_version, body.decision
            )
            session.commit()
            return result

    return router
