"""C7 v1: explicit observation periods and personal numeric rules, no health index."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .river_contracts import utc  # Shared UTC normalization; no hydrological semantics.

__all__ = ["utc", "AirConfiguration", "AirRule", "METRICS", "SOURCE_URL", "STATION"]
METRICS = {"O3": "o3_ug_m3", "NO2": "no2_ug_m3", "PM10": "pm10_ug_m3", "PM25": "pm2_5_ug_m3"}
SOURCE_URL = "https://data.bs.ch/explore/dataset/100051/"
STATION = {
    "id": "BAS",
    "name": "Basel-Binningen",
    "area": "Basel / Binningen",
    "representativeness": "suburban_station",
    "source_url": SOURCE_URL,
}
Metric = Literal["O3", "NO2", "PM10", "PM25"]


class AirRule(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    metric: Metric
    period: Literal["hourly_mean", "rolling_24h_mean"] = "hourly_mean"
    threshold: Decimal = Field(gt=0, le=10000)
    hysteresis: Decimal = Field(default=Decimal("0"), ge=0, le=10000)
    cooldown_hours: int = Field(default=6, strict=True, ge=1, le=48)

    @model_validator(mode="after")
    def validate_rule(self):
        if self.hysteresis >= self.threshold:
            raise ValueError("The improvement margin must be smaller than the threshold.")
        return self


class AirConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_id: Literal["air-quality-watch"] = "air-quality-watch"
    template_version: Literal[1] = 1
    name: str = Field(min_length=1, max_length=100)
    station_id: Literal["BAS"]
    metrics: list[Metric] = Field(min_length=1, max_length=4)
    muted_metrics: list[Metric] = Field(default_factory=list, max_length=4)
    rules: list[AirRule] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_selection(self):
        self.name = self.name.strip()
        if not self.name or len(set(self.metrics)) != len(self.metrics):
            raise ValueError("Choose a name and distinct pollutants.")
        if len(set(self.muted_metrics)) != len(self.muted_metrics) or not set(self.muted_metrics) <= set(
            self.metrics
        ):
            raise ValueError("Only selected pollutants can be muted.")
        keys = [(r.metric, r.period) for r in self.rules]
        if len(set(keys)) != len(keys) or any(r.metric not in self.metrics for r in self.rules):
            raise ValueError("Rules must be distinct by pollutant and period and use selected pollutants.")
        return self
