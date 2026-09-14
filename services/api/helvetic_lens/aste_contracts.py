"""Explicit native request budget and category mapping within a reviewed source policy."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .auction_contracts import Category, visible


class CategoryMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    label: str = Field(min_length=1, max_length=200)
    category: Category


class AsteAccess(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    adapter_version: str = Field(pattern=r"^aste-public-v1$")
    request_interval_seconds: int = Field(ge=1, le=3600)
    document_download_allowed: bool
    category_mapping: dict[str, CategoryMapping] = Field(max_length=100)

    @model_validator(mode="after")
    def reviewed(self):
        import re
        if not self.document_download_allowed:
            raise ValueError("The native document acquisition scope requires explicit permission")
        for identifier, value in self.category_mapping.items():
            if not re.fullmatch(r"[1-9][0-9]{0,8}", identifier):
                raise ValueError("Use official category identifiers")
            visible(value.label)
        return self
