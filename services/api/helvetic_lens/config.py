import os
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The source checkout and the API container have different directory depths.
ROOT = next(
    (parent for parent in Path(__file__).resolve().parents if (parent / "compose.yaml").is_file()),
    Path.cwd(),
)
INFOMANIAK_API_ROOT = "https://api.infomaniak.com"
LOCAL_DOCKER_HOST_URL = "http://127.0.0.1:12435/v1"
LOCAL_DOCKER_CONTAINER_URL = "http://model-manager:8080/v1"


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
    redis_url: str = "redis://127.0.0.1:6379/0"
    model_manager_url: str = "http://127.0.0.1:12436"
    job_execution_mode: Literal["celery", "inline"] = "celery"
    job_lease_seconds: int = Field(default=300, ge=30, le=3600)
    job_max_attempts: int = Field(default=3, ge=1, le=10)
    data_dir: Path = Field(
        default=ROOT / "data",
        validation_alias=AliasChoices("HELVETIC_LENS_DATA_DIR", "REGWATCH_DATA_DIR"),
    )
    apertus_provider: Literal["custom", "docker", "infomaniak"] = "custom"
    apertus_product_id: str = Field(default="", pattern=r"^\d*$")
    apertus_base_url: str = ""
    apertus_model: str = "swiss-ai/Apertus-v1.5-8B"
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
    def __init__(self, message: str, status: int = 422, code: str = "invalid_input"):
        super().__init__(message)
        self.message, self.status, self.code = message, status, code
