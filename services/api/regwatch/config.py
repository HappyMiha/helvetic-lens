from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The source checkout and the API container have different directory depths.
ROOT = next(
    (parent for parent in Path(__file__).resolve().parents if (parent / "compose.yaml").is_file()),
    Path.cwd(),
)
INFOMANIAK_API_ROOT = "https://api.infomaniak.com"


def infomaniak_base_url(product_id: str) -> str:
    return f"{INFOMANIAK_API_ROOT}/2/ai/{product_id}/openai/v1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", populate_by_name=True)
    database_url: str = ""
    data_dir: Path = Field(default=ROOT / "data", alias="REGWATCH_DATA_DIR")
    apertus_provider: Literal["custom", "infomaniak"] = "custom"
    apertus_product_id: str = Field(default="", pattern=r"^\d*$")
    apertus_base_url: str = ""
    apertus_model: str = "swiss-ai/Apertus-v1.5-8B"
    apertus_api_key: SecretStr = SecretStr("")
    apertus_timeout_seconds: int = Field(default=90, ge=5, le=300)
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
        return self

    @property
    def storage_path(self) -> Path:
        return self.data_dir if self.data_dir.is_absolute() else ROOT / self.data_dir

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{(self.storage_path / 'regwatch.db').as_posix()}"

    @property
    def model_configured(self) -> bool:
        return bool(self.apertus_base_url.strip() and self.apertus_model.strip())


class DomainError(Exception):
    def __init__(self, message: str, status: int = 422, code: str = "invalid_input"):
        super().__init__(message)
        self.message, self.status, self.code = message, status, code
