"""Private saved cloud connections; saving never switches the active model."""

from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, Field

from .config import OPENAI_BASE_URL, SWISSCOM_WEEKS_BASE_URL, SWISSCOM_WEEKS_MODEL, DomainError
from .db import utcnow
from .interest_jobs import lock_organization
from .model_settings import ApertusSettingsInput, public_settings, resolved_settings
from .models import ApertusConfiguration, PartnerConfiguration

CloudProvider = Literal["openai", "swisscom"]
PROVIDERS = ("openai", "swisscom")


class ConnectionInput(ApertusSettingsInput):
    revision: int = Field(ge=0, strict=True)
    key_action: Literal["keep", "replace", "remove"] = "keep"


class ConnectionRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1, strict=True)


def connection_public(row, provider):
    values = row.values if row else {
        "provider": provider,
        "base_url": OPENAI_BASE_URL if provider == "openai" else SWISSCOM_WEEKS_BASE_URL,
        "model": "" if provider == "openai" else SWISSCOM_WEEKS_MODEL,
    }
    return {**values, "revision": row.revision if row else 0,
            "api_key_configured": bool(row and row.api_key),
            "updated_at": row.updated_at.isoformat() if row else None}


def inference_connections_router(service):
    router = APIRouter(prefix="/api/settings/inference-connections")

    def record(session, provider, revision=None):
        row = session.get(PartnerConfiguration, (service.organization_id, "inference_" + provider))
        if revision is not None:
            if not row or row.revision != revision:
                raise DomainError("The saved connection changed. Reload before using it.", 409, "connection_revision_conflict")
            if not row.api_key:
                raise DomainError("Save the provider's API key first.", 422, "connection_key_missing")
        return row

    def settings(row):
        return ApertusSettingsInput(**row.values, key_action="replace",
                                    api_key=service.credential_cipher.decrypt(row.api_key))

    @router.get("")
    def read(response: Response):
        response.headers["Cache-Control"] = "no-store"
        with service.db.session() as session:
            return {"items": [connection_public(record(session, p), p) for p in PROVIDERS]}

    @router.patch("/{provider}")
    def save(provider: CloudProvider, data: ConnectionInput, response: Response):
        response.headers["Cache-Control"] = "no-store"
        if data.provider != provider or not data.base_url:
            raise DomainError("Use the selected provider's complete connection settings.", 422, "connection_provider_mismatch")
        with service.write_guard, service.db.session() as session:
            lock_organization(session, service.organization_id)
            row = record(session, provider)
            if (row.revision if row else 0) != data.revision:
                raise DomainError("The saved connection changed. Reload before saving.", 409, "connection_revision_conflict")
            secret = row.api_key if row else None
            if data.key_action == "replace":
                secret = service.credential_cipher.encrypt(data.api_key.get_secret_value())
            elif data.key_action == "remove":
                secret = None
            elif secret and row.values.get("base_url") != data.base_url:
                raise DomainError("Replace the credential when changing its endpoint.", 422, "provider_key_required")
            if row is None:
                row = PartnerConfiguration(organization_id=service.organization_id, provider="inference_" + provider)
                session.add(row)
            row.values = data.public_values()
            row.api_key, row.enabled = secret, bool(secret)
            row.revision, row.updated_at = data.revision + 1, utcnow()
            session.commit()
            return connection_public(row, provider)

    @router.post("/{provider}/test")
    async def test(provider: CloudProvider, data: ConnectionRevision, response: Response):
        response.headers["Cache-Control"] = "no-store"
        with service.db.session() as session:
            draft = settings(record(session, provider, data.revision))
        # A bounded, non-sensitive technical prompt through the normal client.
        draft.max_tokens, draft.request_retries = 512, 0
        result = await service.test_model_settings(draft)
        return {**result, "saved": True, "activated": False, "revision": data.revision}

    @router.post("/{provider}/activate")
    def activate(provider: CloudProvider, data: ConnectionRevision, response: Response):
        response.headers["Cache-Control"] = "no-store"
        with service.write_guard, service.db.session() as session:
            lock_organization(session, service.organization_id)
            draft = settings(record(session, provider, data.revision))
            saved = session.get(ApertusConfiguration, service.tenant_record_id)
            effective = resolved_settings(service.environment_settings, saved, draft,
                                          decrypt_secret=service.credential_cipher.decrypt)
            if saved is None:
                saved = ApertusConfiguration(id=service.tenant_record_id)
                session.add(saved)
            saved.values, saved.key_source = draft.public_values(), "saved"
            saved.api_key = service.credential_cipher.encrypt(draft.api_key.get_secret_value())
            saved.updated_at = utcnow()
            session.commit()
            service.apply_model_settings(effective)
            return public_settings(effective, saved)

    return router
