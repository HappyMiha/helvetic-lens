from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# The source checkout and the API container have different directory depths.
ROOT = next(
    (parent for parent in Path(__file__).resolve().parents if (parent / "compose.yaml").is_file()),
    Path.cwd(),
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", populate_by_name=True)
    database_url: str = ""
    data_dir: Path = Field(default=ROOT / "data", alias="REGWATCH_DATA_DIR")
    apertus_base_url: str = ""
    apertus_model: str = "swiss-ai/Apertus-v1.5-8B"
    apertus_api_key: SecretStr = SecretStr("")
    apertus_timeout_seconds: int = Field(default=90, ge=5, le=300)
    apertus_context_chars: int = Field(default=24000, ge=1000, le=100000)
    apertus_json_mode: bool = False
    firecrawl_api_key: SecretStr = SecretStr("")
    firecrawl_api_url: str = "https://api.firecrawl.dev"
    allow_private_sources: bool = False
    max_document_bytes: int = Field(default=8388608, ge=1024, le=52428800)
    fetch_timeout_seconds: int = Field(default=25, ge=1, le=120)

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
