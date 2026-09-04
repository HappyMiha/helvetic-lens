import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .locales import normalize_locale

# The source checkout and the API container have different directory depths.
ROOT = next(
    (parent for parent in Path(__file__).resolve().parents if (parent / "compose.yaml").is_file()),
    Path.cwd(),
)
INFOMANIAK_API_ROOT = "https://api.infomaniak.com"
LOCAL_DOCKER_HOST_URL = "http://127.0.0.1:12436/openai/v1"
LOCAL_DOCKER_CONTAINER_URL = "http://model-manager:8090/openai/v1"


def infomaniak_base_url(product_id: str) -> str:
    return f"{INFOMANIAK_API_ROOT}/2/ai/{product_id}/openai/v1"


def local_docker_base_url() -> str:
    override = os.getenv("LOCAL_APERTUS_BASE_URL", "").strip()
    if override:
        return override.rstrip("/")
    if Path("/.dockerenv").exists():
        return LOCAL_DOCKER_CONTAINER_URL
    return LOCAL_DOCKER_HOST_URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", populate_by_name=True)
    database_url: str = ""
    database_pool_size: int = Field(default=4, ge=1, le=32)
    database_max_overflow: int = Field(default=2, ge=0, le=32)
    database_pool_timeout_seconds: int = Field(default=15, ge=1, le=120)
    app_environment: Literal["development", "production", "test"] = "development"
    allow_anonymous_dev: bool = True
    session_cookie_secure: bool = False
    session_ttl_days: int = Field(default=14, ge=1, le=90)
    public_base_url: str = "http://127.0.0.1:3000"
    default_locale: str = "en-CH"
    auth_email_mode: Literal["disabled", "development", "smtp"] = "development"
    auth_email_from: str = ""
    auth_smtp_host: str = ""
    auth_smtp_port: int = Field(default=587, ge=1, le=65535)
    auth_smtp_username: str = ""
    auth_smtp_password: SecretStr = SecretStr("")
    auth_smtp_starttls: bool = True
    redis_url: str = "redis://127.0.0.1:6379/0"
    model_manager_url: str = "http://127.0.0.1:12436"
    job_execution_mode: Literal["celery", "inline"] = "celery"
    job_lease_seconds: int = Field(default=300, ge=30, le=3600)
    job_max_attempts: int = Field(default=3, ge=1, le=10)
    connector_max_active_jobs: int = Field(default=2, ge=1, le=16)
    connector_max_queue_depth: int = Field(default=20, ge=1, le=500)
    connector_min_free_megabytes: int = Field(default=512, ge=32, le=1_000_000)
    integration_log_retention_days: int = Field(default=30, ge=1, le=365)
    job_history_retention_days: int = Field(default=90, ge=7, le=730)
    digest_delivery_retention_days: int = Field(default=180, ge=7, le=3650)
    orphan_artifact_retention_hours: int = Field(default=24, ge=1, le=720)
    auth_mail_retention_hours: int = Field(default=48, ge=1, le=168)
    relation_candidates_per_event: int = Field(default=20, ge=1, le=100)
    relation_candidates_per_organization: int = Field(default=10, ge=1, le=50)
    relation_candidate_ttl_days: int = Field(default=30, ge=1, le=365)
    data_dir: Path = Field(
        default=ROOT / "data",
        validation_alias=AliasChoices("HELVETIC_LENS_DATA_DIR", "REGWATCH_DATA_DIR"),
    )
    deployment_state_dir: Path | None = Field(
        default=None,
        validation_alias="HELVETIC_LENS_DEPLOY_STATE_DIR",
    )
    credential_encryption_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices(
            "HELVETIC_LENS_CREDENTIAL_KEY",
            "CREDENTIAL_ENCRYPTION_KEY",
        ),
    )
    apertus_provider: Literal["custom", "docker", "infomaniak"] = "docker"
    apertus_product_id: str = Field(default="", pattern=r"^\d*$")
    apertus_base_url: str = ""
    apertus_model: str = "apertus-1.5b-q4km"
    apertus_api_key: SecretStr = SecretStr("")
    apertus_timeout_seconds: int = Field(default=90, ge=5, le=300)
    apertus_request_retries: int = Field(default=2, ge=0, le=5)
    apertus_batch_concurrency: int = Field(default=1, ge=1, le=4)
    apertus_context_chars: int = Field(default=24000, ge=1000, le=100000)
    apertus_max_tokens: int = Field(default=1600, ge=128, le=8192)
    apertus_temperature: float = Field(default=0.1, ge=0, le=2)
    apertus_top_p: float = Field(default=1.0, ge=0, le=1)
    apertus_presence_penalty: float = Field(default=0.0, gt=-2, lt=2)
    apertus_reasoning_effort: Literal["default", "none", "low", "medium", "high"] = "default"
    apertus_json_mode: bool = False
    firecrawl_api_key: SecretStr = SecretStr("")
    firecrawl_api_url: str = "https://api.firecrawl.dev"
    allow_private_sources: bool = False
    max_document_bytes: int = Field(default=8388608, ge=1024, le=52428800)
    fetch_timeout_seconds: int = Field(default=25, ge=1, le=120)

    @model_validator(mode="after")
    def infomaniak_endpoint(self):
        if self.app_environment == "production":
            if self.allow_anonymous_dev:
                raise ValueError("Production refuses to start while anonymous development access is enabled.")
            if not self.session_cookie_secure:
                raise ValueError("Production requires Secure session cookies.")
            if self.auth_email_mode == "development":
                raise ValueError("Production cannot write authentication emails to the development mailbox.")
            public_origin = urlsplit(self.public_base_url)
            if public_origin.scheme != "https" or not public_origin.hostname:
                raise ValueError("Production requires an HTTPS public base URL.")
            if self.allow_private_sources:
                raise ValueError("Production refuses private-network source fetching.")
            if self.job_execution_mode != "celery":
                raise ValueError("Production requires durable Celery job execution.")
            if len(self.credential_encryption_key.get_secret_value()) < 32:
                raise ValueError("Production requires a stable credential key of at least 32 characters.")
            if not self.database_url.startswith("postgresql"):
                raise ValueError("Production requires PostgreSQL.")
            if self.database_pool_size + self.database_max_overflow > 16:
                raise ValueError("Production limits each process to at most 16 database connections.")
            database_parts = urlsplit(self.database_url.replace("postgresql+psycopg", "postgresql", 1))
            database_password = database_parts.password or ""
            if len(database_password) < 24 or database_password == "helvetic_lens":
                raise ValueError("Production requires a strong database password of at least 24 characters.")
            if self.max_document_bytes > 20 * 1024 * 1024:
                raise ValueError("Production uploads cannot exceed the reverse proxy's 20 MiB limit.")
        self.public_base_url = self.public_base_url.rstrip("/")
        self.default_locale = normalize_locale(self.default_locale)
        if self.auth_email_mode == "smtp" and (not self.auth_smtp_host or not self.auth_email_from):
            raise ValueError("SMTP authentication email delivery requires host and from address.")
        product_id = self.apertus_product_id.strip()
        if self.apertus_provider == "infomaniak":
            if not product_id:
                raise ValueError("APERTUS_PRODUCT_ID is required for the Infomaniak provider.")
            self.apertus_product_id = product_id
            self.apertus_base_url = infomaniak_base_url(product_id)
        elif self.apertus_provider == "docker":
            self.apertus_product_id = ""
            self.apertus_base_url = local_docker_base_url()
        return self

    @property
    def storage_path(self) -> Path:
        return self.data_dir if self.data_dir.is_absolute() else ROOT / self.data_dir

    @property
    def deployment_status_path(self) -> Path:
        return self.deployment_state_dir or self.storage_path / "operations" / "deployments"

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        current = self.storage_path / "helvetic_lens.db"
        legacy = self.storage_path / "regwatch.db"
        database = legacy if legacy.exists() and not current.exists() else current
        return f"sqlite:///{database.as_posix()}"

    @property
    def model_configured(self) -> bool:
        return bool(self.apertus_base_url.strip() and self.apertus_model.strip())


class DomainError(Exception):
    def __init__(
        self,
        message: str,
        status: int = 422,
        code: str = "invalid_input",
        params: dict | None = None,
    ):
        super().__init__(message)
        self.message, self.status, self.code, self.params = message, status, code, params or {}
