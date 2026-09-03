from collections.abc import Callable
from datetime import UTC
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from .config import DomainError, Settings, infomaniak_base_url, local_docker_base_url
from .extraction import canonical_url
from .models import ApertusConfiguration

PUBLIC_FIELDS = (
    "provider",
    "product_id",
    "base_url",
    "model",
    "timeout_seconds",
    "request_retries",
    "batch_concurrency",
    "context_chars",
    "max_tokens",
    "temperature",
    "top_p",
    "presence_penalty",
    "reasoning_effort",
    "json_mode",
)

class ApertusSettingsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    provider: Literal["custom", "docker", "infomaniak"] = "custom"
    product_id: str = Field(default="", max_length=30, pattern=r"^\d*$")
    base_url: str = Field(default="", max_length=2000)
    model: str = Field(min_length=1, max_length=300)
    timeout_seconds: int = Field(default=90, ge=5, le=300)
    request_retries: int = Field(default=2, ge=0, le=5)
    batch_concurrency: int = Field(default=1, ge=1, le=4)
    context_chars: int = Field(default=24000, ge=1000, le=100000)
    max_tokens: int = Field(default=1600, ge=128, le=8192)
    temperature: float = Field(default=0.1, ge=0, le=2)
    top_p: float = Field(default=1.0, ge=0, le=1)
    presence_penalty: float = Field(default=0.0, gt=-2, lt=2)
    reasoning_effort: Literal["default", "none", "low", "medium", "high"] = "default"
    json_mode: bool = False
    key_action: Literal["keep", "replace", "remove", "environment"] = "keep"
    api_key: SecretStr = SecretStr("")

    @field_validator("base_url")
    @classmethod
    def valid_endpoint(cls, value):
        if not value:
            return ""
        parsed = urlsplit(value)
        if parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError("Use the API base URL without credentials, a query, or a fragment.")
        try:
            value = canonical_url(value).rstrip("/")
        except DomainError as exc:
            raise ValueError(
                "Enter a full HTTP or HTTPS API base URL, or leave it empty to disconnect."
            ) from exc
        if value.endswith("/chat/completions"):
            raise ValueError("Enter the API base URL, usually ending in /v1, without /chat/completions.")
        return value

    @model_validator(mode="after")
    def valid_configuration(self):
        if self.provider == "infomaniak":
            if not self.product_id:
                raise ValueError("Enter the Infomaniak AI Product ID.")
            self.base_url = infomaniak_base_url(self.product_id)
        elif self.provider == "docker":
            self.product_id = ""
            self.base_url = local_docker_base_url()
        else:
            self.product_id = ""
        key = self.api_key.get_secret_value().strip()
        if self.key_action == "replace" and not key:
            raise ValueError("Enter a new API key, or choose Keep existing key.")
        if len(key) > 4000 or "\n" in key or "\r" in key:
            raise ValueError("The API key must be a single value of at most 4,000 characters.")
        if key and self.key_action != "replace":
            raise ValueError("Choose Replace key to use the newly entered credential.")
        self.api_key = SecretStr(key)
        return self

    def public_values(self):
        return {name: getattr(self, name) for name in PUBLIC_FIELDS}


def resolve_key(
    environment: Settings,
    record: ApertusConfiguration | None,
    data: ApertusSettingsInput | None,
    decrypt_secret: Callable[[str | None], str] | None = None,
):
    source = record.key_source if record else "environment"
    stored_key = record.api_key if record else None
    if source == "saved" and stored_key and decrypt_secret:
        stored_key = decrypt_secret(stored_key)
    if data:
        if data.key_action == "replace":
            source, stored_key = "saved", data.api_key.get_secret_value()
        elif data.key_action in {"remove", "environment"}:
            source = "none" if data.key_action == "remove" else "environment"
            stored_key = None
    effective_key = (
        environment.apertus_api_key.get_secret_value() if source == "environment" else stored_key or ""
    )
    return source, stored_key, SecretStr(effective_key)


def resolved_settings(
    environment: Settings,
    record: ApertusConfiguration | None,
    data: ApertusSettingsInput | None = None,
    decrypt_secret: Callable[[str | None], str] | None = None,
) -> Settings:
    values = data.public_values() if data else record.values if record else {}
    _, _, key = resolve_key(environment, record, data, decrypt_secret)
    provider = values.get("provider", environment.apertus_provider)
    if provider == "docker":
        # The reachable address changes when the API moves between the host and Compose.
        # Derive it at runtime instead of trusting the address persisted by the other mode.
        values = {**values, "base_url": local_docker_base_url(), "product_id": ""}
        # Preserve a saved remote-provider token while never sending it to the local runner.
        key = SecretStr("")
    return environment.model_copy(
        update={
            **{f"apertus_{name}": values[name] for name in PUBLIC_FIELDS if name in values},
            "apertus_api_key": key,
        },
        deep=True,
    )


def public_settings(settings: Settings, record: ApertusConfiguration | None) -> dict:
    return {
        **{name: getattr(settings, f"apertus_{name}") for name in PUBLIC_FIELDS},
        "configured": settings.model_configured,
        "api_key_configured": bool(settings.apertus_api_key.get_secret_value()),
        "key_source": record.key_source if record else "environment",
        "source": "workspace" if record else "environment",
        "updated_at": (
            record.updated_at.replace(tzinfo=UTC).isoformat()
            if record and record.updated_at.tzinfo is None
            else record.updated_at.isoformat()
            if record
            else None
        ),
    }
