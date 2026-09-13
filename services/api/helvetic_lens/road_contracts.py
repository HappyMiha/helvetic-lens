"""Private corridor selections. A saved draft neither starts polling nor grants email consent."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .road_evaluation import RoadMateriality
from .road_sources import _encoded, _hash


class RoadConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    template_id: Literal["road-watch"] = "road-watch"
    template_version: int = Field(default=1, strict=True, ge=1, le=1)
    name: str = Field(min_length=1, max_length=100)
    # The reference includes the reviewed direction; arbitrary road-name text or
    # a browser location cannot establish a supported northbound/southbound path.
    corridor_reference_ids: tuple[UUID, ...] = Field(min_length=1, max_length=8)
    materiality: RoadMateriality = Field(default_factory=RoadMateriality)

    @field_validator("materiality", mode="before")
    @classmethod
    def materiality_json(cls, value):
        if isinstance(value, dict):
            return RoadMateriality.model_validate_json(_encoded(value), strict=True)
        return value

    @model_validator(mode="after")
    def distinct_references(self):
        if not self.name.strip() or any(ord(c) < 32 for c in self.name):
            raise ValueError("Name the saved route")
        if len(set(self.corridor_reference_ids)) != len(self.corridor_reference_ids):
            raise ValueError("Select each corridor direction once")
        return self

    def fingerprint(self):
        return _hash(_encoded(self.model_dump(mode="json")))
