"""Authenticated category status and platform-only encrypted connector settings."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, update

from . import monitoring_connector_probe as probe
from . import monitoring_connector_settings as config
from .config import DomainError
from .monitoring_connector_models import MonitoringConnectorConfiguration as Configuration
from .monitoring_source_operations import snapshot


class Revision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    revision: int = Field(strict=True, ge=0)


class Change(Revision):
    values: dict[str, bool | int | str] = Field(default_factory=dict, max_length=20)
    secrets: dict[str, str] = Field(default_factory=dict, max_length=4)


def connector_router(service):
    router = APIRouter()

    def identity(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        actor = getattr(request.state, "identity", None)
        if actor is None:
            raise DomainError("Sign in to continue.", 401, "authentication_required")
        return actor

    def administrator(actor=Depends(identity)):
        if not actor.platform_admin:
            raise DomainError("Platform administration is required.", 403, "platform_admin_required")
        return actor

    @router.get("/api/monitoring-settings")
    def overview(actor=Depends(identity)):
        with service.db.session() as session:
            value = snapshot(session, service.settings)
            # User status does not disclose platform configuration or secret presence.
            return {"can_configure_connectors": actor.platform_admin,
                "items": [{"id": row["id"], "collector": row["collector"], "access": row["access"]["state"],
                    "acquisition": row["acquisition"]["state"]} for row in value["items"]]}

    @router.get("/api/admin/monitoring-connectors/{domain}")
    def read(domain: str, actor=Depends(administrator)):
        with service.db.session() as session:
            return config.read(session, service.environment_settings, service.credential_cipher, domain)

    @router.patch("/api/admin/monitoring-connectors/{domain}")
    def save(domain: str, body: Change, actor=Depends(administrator)):
        with service.db.session() as session:
            result = config.save(session, service.environment_settings, service.credential_cipher,
                domain, body.revision, body.values, body.secrets)
            session.commit()
            return result

    @router.post("/api/admin/monitoring-connectors/{domain}/check")
    def check(domain: str, body: Revision, actor=Depends(administrator)):
        config.domain_fields(domain)
        now = datetime.now(UTC)
        with service.db.session() as session:
            # One durable check per source per minute, shared by all administrators.
            current = session.get(Configuration, domain)
            if current is None or current.revision != body.revision:
                raise DomainError("Reload settings before checking access.", 409, "connector_revision_conflict")
            claimed = session.execute(update(Configuration).where(Configuration.domain == domain,
                Configuration.revision == body.revision,
                or_(Configuration.next_check_at.is_(None), Configuration.next_check_at <= now))
                .values(next_check_at=now + timedelta(seconds=60)).execution_options(synchronize_session=False))
            if claimed.rowcount != 1:
                raise DomainError("Wait one minute before checking again.", 429, "connector_check_rate_limited")
            effective = config.resolve(session, service.environment_settings, service.credential_cipher)
            session.commit()
        result = probe.check(domain, effective)
        with service.db.session() as session:
            stored = session.execute(update(Configuration).where(Configuration.domain == domain,
                Configuration.revision == body.revision).values(check_revision=body.revision, check_result=result))
            if stored.rowcount != 1:
                raise DomainError("Settings changed during the check. Reload before checking again.", 409, "connector_revision_conflict")
            session.commit()
        return result

    return router
