from __future__ import annotations

import httpx

from .config import DomainError, Settings


class ModelManagerClient:
    """Narrow client for the private allowlist-based model lifecycle API."""

    def __init__(self, settings: Settings):
        self.base_url = settings.model_manager_url.rstrip("/")
        self.timeout = httpx.Timeout(15, read=90)

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.request(method, self.base_url + path, **kwargs)
        except httpx.HTTPError as exc:
            raise DomainError(
                "The private local model manager is unavailable.",
                503,
                "model_manager_unavailable",
            ) from exc
        if response.status_code >= 400:
            try:
                error = response.json()
            except ValueError:
                error = {}
            raise DomainError(
                error.get("detail") or "The local model manager rejected this operation.",
                response.status_code,
                error.get("code") or "model_manager_error",
            )
        return response.json()

    async def inventory(self) -> dict:
        return await self._request("GET", "/v1/inventory")

    async def profile(self, profile_id: str) -> dict:
        return await self._request("GET", f"/v1/profiles/{profile_id}")

    async def probe(self) -> dict:
        return await self._request("POST", "/v1/hardware/probe")

    async def accept_license(self, model_id: str, accepted: bool) -> dict:
        return await self._request(
            "POST",
            f"/v1/models/{model_id}/license",
            json={"accepted": accepted},
        )

    async def command(self, model_id: str, action: str, **params) -> dict:
        allowed = {
            "download": ("POST", f"/v1/models/{model_id}/download"),
            "pause": ("POST", f"/v1/models/{model_id}/download/pause"),
            "cancel": ("POST", f"/v1/models/{model_id}/download/cancel"),
            "start": ("POST", f"/v1/models/{model_id}/start"),
            "stop": ("POST", f"/v1/models/{model_id}/stop"),
            "remove": ("DELETE", f"/v1/models/{model_id}"),
        }
        if action not in allowed:
            raise DomainError("Unsupported local model command.", 422, "model_command_invalid")
        method, path = allowed[action]
        return await self._request(method, path, params=params or None)
