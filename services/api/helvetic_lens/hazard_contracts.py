"""Private C1 draft selections; a location declaration is not verified geography."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .hazard_cap import digest

Canton = Literal["AG", "AI", "AR", "BE", "BL", "BS", "FR", "GE", "GL", "GR", "JU", "LU", "NE",
                 "NW", "OW", "SG", "SH", "SO", "SZ", "TG", "TI", "UR", "VD", "VS", "ZG", "ZH"]
Hazard = Literal["flood", "storm", "forest_fire", "heavy_snow", "power_outage", "civil_protection_warning"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PointLocation(Contract):
    kind: Literal["point"]
    country: Literal["CH"] = "CH"
    canton: Canton
    latitude: float = Field(strict=True, ge=44, le=49)
    longitude: float = Field(strict=True, ge=4, le=12)
    radius_km: float = Field(default=0, strict=True, ge=0, le=50)


class MunicipalityLocation(Contract):
    kind: Literal["municipality"]
    country: Literal["CH"] = "CH"
    canton: Canton
    municipality_code: str = Field(pattern=r"^[1-9][0-9]{0,3}$")


class HazardConfiguration(Contract):
    template_id: Literal["hazard-watch"] = "hazard-watch"
    template_version: Literal[1] = 1
    name: str = Field(min_length=1, max_length=100)
    location: Annotated[PointLocation | MunicipalityLocation, Field(discriminator="kind")]
    hazards: list[Hazard] = Field(min_length=1, max_length=6)
    minimum_importance: Literal["information", "warning", "alarm"] = "warning"

    @field_validator("template_version", mode="before")
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int:
            raise ValueError("Use a supported integer contract version")
        return value

    @model_validator(mode="after")
    def distinct_selection(self):
        self.name = self.name.strip()
        if not self.name or any(ord(c) < 32 for c in self.name):
            raise ValueError("Name the saved place")
        if len(set(self.hazards)) != len(self.hazards):
            raise ValueError("Select each hazard once")
        self.hazards = sorted(self.hazards)
        return self

    def fingerprint(self):
        return digest(self.model_dump(mode="json"))
