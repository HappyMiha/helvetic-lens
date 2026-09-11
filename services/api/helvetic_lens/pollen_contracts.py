"""MV2-069 draft/configuration contract v1; validation never authorizes Start.

Station availability, source rights, category scales, tenant permissions and
delivery consent are separate runtime gates. This module has no I/O or writes.
"""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Concentration = Annotated[Decimal, Field(ge=0, allow_inf_nan=False, max_digits=12, decimal_places=6)]
PositiveConcentration = Annotated[Decimal, Field(gt=0, allow_inf_nan=False, max_digits=12, decimal_places=6)]
ClockTime = Annotated[str, Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PollenAllergen(StrEnum):
    ALDER = "alder"
    BIRCH = "birch"
    HAZEL = "hazel"
    BEECH = "beech"
    ASH = "ash"
    OAK = "oak"
    GRASSES = "grasses"
    RAGWEED = "ragweed"


class PollenPeriod(StrEnum):
    OBSERVATION_HOURLY = "observation_hourly"
    OBSERVATION_DAILY_00 = "observation_daily_00_24_utc"
    OBSERVATION_DAILY_06 = "observation_daily_06_06_utc"
    FORECAST_INSTANT = "forecast_instant"


class ThresholdRule(ContractModel):
    trigger_at_or_above: PositiveConcentration
    reset_at_or_below: Concentration

    @model_validator(mode="after")
    def reset_precedes_trigger(self) -> Self:
        if self.reset_at_or_below >= self.trigger_at_or_above:
            raise ValueError("Reset must be strictly below the trigger threshold")
        return self


class RapidIncreaseRule(ContractModel):
    minimum_increase: PositiveConcentration
    window_hours: int = Field(strict=True, ge=1, le=24)


class PollenRule(ContractModel):
    period: PollenPeriod
    unit: Literal["number/m3"] = "number/m3"
    threshold: ThresholdRule | None = None
    rapid_increase: RapidIncreaseRule | None = None
    category_change: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def has_material_change_rule(self) -> Self:
        if self.threshold is None and self.rapid_increase is None and not self.category_change:
            raise ValueError("Choose at least one material-change rule")
        if self.rapid_increase and self.period in {
            PollenPeriod.OBSERVATION_DAILY_00, PollenPeriod.OBSERVATION_DAILY_06,
        }:
            raise ValueError("Hourly rapid increase cannot compare daily aggregation periods")
        return self


class PollenSelection(ContractModel):
    allergen: PollenAllergen
    # Empty rules intentionally support current-state preview without alerts.
    rules: tuple[PollenRule, ...] = Field(default=(), max_length=4)

    @model_validator(mode="after")
    def unique_periods(self) -> Self:
        if len({rule.period for rule in self.rules}) != len(self.rules):
            raise ValueError("Configure each aggregation period only once per allergen")
        return self


class QuietHours(ContractModel):
    start: ClockTime
    end: ClockTime

    @model_validator(mode="after")
    def distinct_times(self) -> Self:
        if self.start == self.end:
            raise ValueError("Quiet hours must have different start and end times")
        return self


class PollenDelivery(ContractModel):
    email: Literal["off", "immediate", "daily_digest"] = "off"
    digest_at: ClockTime | None = None
    quiet_hours: QuietHours | None = None

    @model_validator(mode="after")
    def digest_time_matches_mode(self) -> Self:
        if (self.email == "daily_digest") != (self.digest_at is not None):
            raise ValueError("A digest time is required only for daily digest email")
        return self


class PollenConfiguration(ContractModel):
    contract_version: int = Field(default=1, strict=True, ge=1, le=1)
    template_id: Literal["pollen-watch"] = "pollen-watch"
    template_version: int = Field(default=1, strict=True, ge=1, le=1)
    station_id: str = Field(pattern=r"^[A-Z]{3}$")
    selections: tuple[PollenSelection, ...] = Field(min_length=1, max_length=8)
    timezone: str = Field(default="Europe/Zurich", min_length=1, max_length=64)
    delivery: PollenDelivery = Field(default_factory=PollenDelivery)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Timezone must be a known IANA name") from exc
        return value

    @model_validator(mode="after")
    def unique_allergens(self) -> Self:
        if len({selection.allergen for selection in self.selections}) != len(self.selections):
            raise ValueError("Each allergen must be selected only once")
        return self
