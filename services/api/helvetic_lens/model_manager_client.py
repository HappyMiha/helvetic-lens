from __future__ import annotations

import re

import httpx

from .config import DomainError, Settings


class ModelManagerClient:
    """Narrow client for the private allowlist-based model lifecycle API."""

    def __init__(self, settings: Settings):
        self.base_url = settings.model_manager_url.rstrip("/")
        self.timeout = httpx.Timeout(15, read=90)

    async def _request(
        self, method: str, path: str, *, expected_runtime_binding: str | None = None, **kwargs,
    ) -> dict:
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
        if expected_runtime_binding is not None and response.headers.get("x-helvetic-runtime-binding") != expected_runtime_binding:
            raise DomainError(
                "The local runner response does not match the requested deployment.",
                409, "runtime_binding_changed",
            )
        return response.json()

    async def inventory(self) -> dict:
        return await self._request("GET", "/v1/inventory")

    async def runtime(self) -> dict:
        """Read the active deployment binding without starting or selecting a model."""
        return await self._request("GET", "/v1/runtime")

    async def profile(self, profile_id: str) -> dict:
        return await self._request("GET", f"/v1/profiles/{profile_id}")

    async def complete_profile(
        self,
        profile_id: str,
        organization_id: str,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        response_schema: dict | None = None,
    ) -> dict:
        profile = await self.profile(profile_id)
        if not profile.get("ready"):
            selected = profile.get("selected_model") or {}
            raise DomainError(
                "The local assistant model is not running.",
                503,
                "assistant_local_unavailable",
                {"state": profile.get("state"), "model": selected.get("display_name")},
            )
        runtime = await self.runtime()
        runtime = runtime if isinstance(runtime, dict) else {}
        binding = runtime.get("binding_fingerprint")
        deployment_id = runtime.get("deployment_id")
        if (
            runtime.get("schema_version") != "local-runtime-binding-v1"
            or runtime.get("available") is not True
            or not isinstance(binding, str) or not re.fullmatch(r"[a-f0-9]{64}", binding)
            or not isinstance(deployment_id, str) or not re.fullmatch(r"[a-f0-9]{32}", deployment_id)
        ):
            raise DomainError(
                "The local assistant deployment cannot be verified. Refresh its runtime before retrying.",
                503, "assistant_local_unavailable",
            )
        selected = profile.get("selected_model") or {}
        expected_model = {
            "served_model_id": selected.get("served_model_id"),
            "model_id": selected.get("id"),
            "model_revision": selected.get("immutable_revision"),
            "artifact_sha256": selected.get("artifact_sha256"),
        }
        if any(not isinstance(value, str) or not value or runtime.get(key) != value for key, value in expected_model.items()):
            raise DomainError(
                "The local assistant model changed. Refresh its runtime before retrying.",
                409, "runtime_binding_changed",
            )
        generation = profile.get("generation") or {}
        payload = {
            "model": profile["selected_model"]["served_model_id"],
            "messages": messages,
            "temperature": generation.get("temperature", 0.35),
            "max_tokens": min(int(max_tokens or generation.get("max_tokens", 384)), 384),
            "stream": False,
        }
        if response_schema:
            payload["response_format"] = {
                "type": "json_object",
                "schema": response_schema,
            }
        response = await self._request(
            "POST",
            "/openai/v1/chat/completions",
            expected_runtime_binding=binding,
            headers={
                "X-Helvetic-Organization": organization_id,
                "X-Helvetic-Priority": profile.get("policy", {}).get("priority", "interactive"),
                "X-Helvetic-Runtime-Binding": binding,
            },
            json=payload,
        )
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise DomainError(
                "The local assistant returned an unusable response.",
                502,
                "assistant_response_invalid",
            ) from exc
        if not isinstance(content, str):
            raise DomainError(
                "The local assistant returned an unusable response.",
                502,
                "assistant_response_invalid",
            )
        return {"content": content, "profile": profile, "runtime_binding": binding}

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
