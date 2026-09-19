"""Explicit, bounded partner calls for a user-reviewed briefing.

No automatic fallback, background submission, document fetching or raw-content logs.
Provider contracts and participant-access boundaries: docs/hackathon/RESOURCES.md.
"""

import asyncio
import base64
import hashlib
import json
import time
from typing import Literal

import httpx
from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from .config import DomainError
from .db import utcnow
from .models import PartnerConfiguration

Partner = Literal["supertext", "elevenlabs"]
ROOTS = {"supertext": "https://api.supertext.com/v1", "elevenlabs": "https://api.elevenlabs.io/v1"}
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class PartnerSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    revision: int = Field(ge=0, strict=True)
    enabled: bool = Field(default=False, strict=True)
    key_action: Literal["keep", "replace", "remove"] = "keep"
    api_key: SecretStr = SecretStr("")
    voice_id: str = Field(default="", max_length=100, pattern=r"^[A-Za-z0-9_-]*$")
    model_id: str = Field(default="eleven_multilingual_v2", min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")

    @model_validator(mode="after")
    def credential(self):
        key = self.api_key.get_secret_value()
        if len(key) > 4000 or any(char in key for char in "\r\n"):
            raise ValueError("Use a single API key of at most 4,000 characters.")
        if bool(key) != (self.key_action == "replace"):
            raise ValueError("A replacement key is required only when Replace key is selected.")
        return self


class BriefingText(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=3000)
    consent: Literal[True]
    revision: int = Field(ge=1, strict=True)


class TranslationText(BriefingText):
    source_lang: str = Field(default="", max_length=20, pattern=r"^[A-Za-z-]*$")
    target_lang: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z-]+$")


def public_configuration(row, provider):
    return {"provider": provider, "revision": row.revision if row else 0,
        "enabled": row.enabled if row else False, "api_key_configured": bool(row and row.api_key),
        "voice_id": row.values.get("voice_id", "") if row else "",
        "model_id": row.values.get("model_id", "eleven_multilingual_v2") if row else "eleven_multilingual_v2"}


class PartnerClient:
    def __init__(self, provider, key, logger=None):
        self.provider, self.key, self.logger = provider, key, logger

    async def request(self, method, path, payload=None):
        url = ROOTS[self.provider] + path
        headers = ({"Authorization": f"Supertext-Auth-Key {self.key}"} if self.provider == "supertext"
            else {"xi-api-key": self.key})
        headers["User-Agent"] = "HelveticLens/0.1"
        started, response, outcome = time.monotonic(), None, "error"
        try:
            # Never replay a billable request after an ambiguous timeout or redirect.
            async with asyncio.timeout(45), httpx.AsyncClient(timeout=45, trust_env=False, follow_redirects=False) as client:
                async with client.stream(method, url, headers=headers, json=payload) as response:
                    if not 200 <= response.status_code < 300:
                        if response.status_code in {401, 403}:
                            code, message = "partner_access_denied", "The provider rejected access. Check the API key and its permissions."
                        elif response.status_code == 429:
                            code, message = "partner_rate_limited", "The provider quota or rate limit was reached. Check available credits."
                        else:
                            code, message = "partner_unavailable", "The provider could not complete this request. Check its service and configuration."
                        raise DomainError(message, 502, code)
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_RESPONSE_BYTES:
                            raise DomainError("The provider response exceeded the briefing limit.", 502, "partner_response_invalid")
                    outcome = "success"
                    return bytes(body), response.headers.get("content-type", "")
        except (httpx.HTTPError, TimeoutError) as exc:
            raise DomainError("The provider connection failed. The request was not automatically retried.", 502, "partner_unavailable") from exc
        finally:
            if self.logger:
                self.logger.record(provider=self.provider, operation="briefing" + path.split("?")[0].replace("/", "_")[:45],
                    method=method, url=url, status=outcome, duration_ms=(time.monotonic()-started)*1000,
                    request_body={"submitted_characters": sum(len(t) for t in payload.get("text", [])) if payload else 0},
                    response_status=response.status_code if response is not None else None)

    async def json(self, method, path, payload=None):
        body, _ = await self.request(method, path, payload)
        try:
            result = json.loads(body)
            if not isinstance(result, dict):
                raise ValueError("Expected object")
            return result
        except (ValueError, UnicodeError) as exc:
            raise DomainError("The provider returned an invalid response.", 502, "partner_response_invalid") from exc


def partner_router(service):
    router = APIRouter()

    def configuration(provider, revision=None, *, require_voice=False):
        with service.db.session() as session:
            row = session.get(PartnerConfiguration, (service.organization_id, provider))
            if not row or not row.enabled or not row.api_key:
                raise DomainError("Enable this provider and save its API key in Partner tools first.", 422, "partner_not_configured")
            if revision is not None and revision != row.revision:
                raise DomainError("Provider settings changed. Reload before submitting text.", 409, "partner_revision_conflict")
            if require_voice and not row.values.get("voice_id"):
                raise DomainError("Choose an ElevenLabs voice ID in Partner tools first.", 422, "partner_not_configured")
            return PartnerClient(provider, service.credential_cipher.decrypt(row.api_key), service.integration_logger), dict(row.values)

    @router.get("/api/settings/partners")
    def read(response: Response):
        response.headers["Cache-Control"] = "no-store"
        with service.db.session() as session:
            return {"items": [public_configuration(session.get(PartnerConfiguration, (service.organization_id, p)), p) for p in ROOTS]}

    @router.patch("/api/settings/partners/{provider}")
    def save(provider: Partner, data: PartnerSettings, response: Response):
        response.headers["Cache-Control"] = "no-store"
        with service.db.session() as session:
            row = session.get(PartnerConfiguration, (service.organization_id, provider))
            if (row.revision if row else 0) != data.revision:
                raise DomainError("Settings changed. Reload before saving.", 409, "partner_revision_conflict")
            secret = row.api_key if row else None
            if data.key_action == "replace":
                secret = service.credential_cipher.encrypt(data.api_key.get_secret_value())
            elif data.key_action == "remove":
                secret = None
            if data.enabled and (not secret or (provider == "elevenlabs" and not data.voice_id)):
                raise DomainError("An enabled provider needs an API key and, for speech, a voice ID.", 422, "partner_not_configured")
            values = {"voice_id": data.voice_id, "model_id": data.model_id} if provider == "elevenlabs" else {}
            new_values = dict(revision=data.revision+1, enabled=data.enabled, api_key=secret, values=values, updated_at=utcnow())
            if row:
                changed = session.execute(update(PartnerConfiguration).where(
                    PartnerConfiguration.organization_id == service.organization_id,
                    PartnerConfiguration.provider == provider, PartnerConfiguration.revision == data.revision
                ).values(**new_values))
                if changed.rowcount != 1:
                    raise DomainError("Settings changed. Reload before saving.", 409, "partner_revision_conflict")
            else:
                row = PartnerConfiguration(organization_id=service.organization_id, provider=provider, **new_values)
                session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                raise DomainError("Settings changed. Reload before saving.", 409, "partner_revision_conflict") from exc
            session.refresh(row)
            return public_configuration(row, provider)

    @router.post("/api/partner-tools/{provider}/test")
    async def test(provider: Partner, response: Response):
        response.headers["Cache-Control"] = "no-store"
        client, values = configuration(provider)
        payload = await client.json("GET", "/features" if provider == "supertext" else f"/voices/{values['voice_id']}")
        if provider == "elevenlabs" and payload.get("voice_id") != values["voice_id"]:
            raise DomainError("The provider did not return the configured voice.", 502, "partner_response_invalid")
        return {"status": "reachable", "provider": provider, "generation_verified": False}

    @router.post("/api/partner-tools/supertext/translate")
    async def translate(data: TranslationText, response: Response):
        response.headers["Cache-Control"] = "no-store"
        client, _ = configuration("supertext", data.revision)
        request = {"text": [data.text], "target_lang": data.target_lang}
        if data.source_lang:
            request["source_lang"] = data.source_lang
        result = await client.json("POST", "/translate/ai/text", request)
        segments = result.get("translated_text")
        if not isinstance(segments, list) or len(segments) != 1 or not isinstance(segments[0], str) or not segments[0].strip() or len(segments[0]) > 20000:
            raise DomainError("Supertext returned an incomplete translation.", 502, "partner_response_invalid")
        return {"text": segments[0], "provider": "supertext", "target_lang": data.target_lang,
            "source_sha256": hashlib.sha256(data.text.encode()).hexdigest(), "human_verified": False}

    @router.post("/api/partner-tools/elevenlabs/speech")
    async def speech(data: BriefingText, response: Response):
        response.headers["Cache-Control"] = "no-store"
        client, values = configuration("elevenlabs", data.revision, require_voice=True)
        body, content_type = await client.request("POST", f"/text-to-speech/{values['voice_id']}?output_format=mp3_44100_128",
            {"text": data.text, "model_id": values["model_id"]})
        if not body or not content_type.lower().startswith("audio/"):
            raise DomainError("ElevenLabs did not return audio.", 502, "partner_response_invalid")
        return {"audio_base64": base64.b64encode(body).decode(), "media_type": "audio/mpeg", "provider": "elevenlabs",
            "source_sha256": hashlib.sha256(data.text.encode()).hexdigest()}

    return router
