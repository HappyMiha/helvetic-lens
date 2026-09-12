"""C6 v1: station-bound measurements; official danger is never inferred."""
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

METRICS = {"W": ("m", "station_elevation"), "Q": ("m3/s", "discharge"), "WT": ("°C", "temperature")}
SOURCE_URL = "https://data.bafu.admin.ch/dataproduct-water-observations"
DANGER_URL = "https://www.bafu.admin.ch/de/aktuelle-hydrologische-daten-beziehen"


def utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class RiverRule(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    metric: Literal["W", "Q", "WT"]
    kind: Literal["absolute", "rise"] = "absolute"
    threshold: Decimal = Field(ge=-10000, le=1000000)
    unit: Literal["m", "cm", "m3/s", "°C"]
    window_minutes: int | None = Field(default=None, strict=True, ge=10, le=1440)

    @model_validator(mode="after")
    def validate_binding(self):
        if self.unit != METRICS[self.metric][0] and not (self.metric == "W" and self.kind == "rise" and self.unit == "cm"):
            raise ValueError("Use the station metric unit; centimetres apply only to water-level rises.")
        if self.kind == "absolute" and self.window_minutes is not None:
            raise ValueError("An absolute threshold has no change window.")
        if self.kind == "rise" and (self.window_minutes is None or self.window_minutes % 10 or self.threshold <= 0):
            raise ValueError("A rise requires a positive threshold and a whole 10-minute window.")
        return self


class RiverConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_id: Literal["river-lake-watch"] = "river-lake-watch"
    template_version: Literal[1] = 1
    name: str = Field(min_length=1, max_length=100)
    station_id: str = Field(pattern=r"^2[0-9]{3}$")
    metrics: list[Literal["W", "Q", "WT"]] = Field(min_length=1, max_length=3)
    official_danger: bool = Field(default=True, strict=True)
    rules: list[RiverRule] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def validate_selection(self):
        self.name = self.name.strip()
        if not self.name or len(set(self.metrics)) != len(self.metrics):
            raise ValueError("Use a non-empty name and distinct metrics.")
        keys = [(r.metric, r.kind, r.window_minutes) for r in self.rules]
        if len(set(keys)) != len(keys) or any(r.metric not in self.metrics for r in self.rules):
            raise ValueError("Rules must be distinct and use selected metrics.")
        return self
