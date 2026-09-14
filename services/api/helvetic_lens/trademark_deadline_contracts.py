"""Reviewed legal-rule inputs; no built-in approval or inferred holiday jurisdiction."""

from datetime import date, datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ENGINE = "ch-opposition-months-v1"


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DeadlinePreference(Contract):
    calendar_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    domicile_basis: Literal["party", "representative"]


class Citation(Contract):
    url: str = Field(min_length=1, max_length=2048)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    section: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def safe_reference(self):
        parsed = urlsplit(self.url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or any(ord(c) < 32 for c in self.url + self.section)):
            raise ValueError("Use an exact HTTPS evidence reference")
        return self


class Reviewed(Contract):
    reviewed_at: datetime
    review_expires_at: datetime
    reviewer_reference: str = Field(min_length=1, max_length=500)
    citations: tuple[Citation, ...] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def valid_review(self):
        if (any(d.tzinfo is None or d.utcoffset() is None for d in (self.reviewed_at, self.review_expires_at))
                or self.reviewed_at >= self.review_expires_at
                or not self.reviewer_reference.strip() or any(ord(c) < 32 for c in self.reviewer_reference)):
            raise ValueError("A bounded, dated review is required")
        return self


class DeadlineRule(Reviewed):
    engine: Literal["ch-opposition-months-v1"]
    source_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    origin: Literal["national_ch", "international_designating_ch"]
    basis: Literal["swissreg_registration_publication", "wipo_ch_extension_publication"]
    publication_category: str = Field(min_length=1, max_length=300)
    publication_office: Literal["CH", "WO"]
    publication_from: date
    publication_until: date
    mapping_reference: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def applicable(self):
        if (self.publication_from >= self.publication_until
                or (self.origin == "national_ch") != (self.basis == "swissreg_registration_publication")
                or (self.origin == "national_ch") != (self.publication_office == "CH")
                or not self.publication_category.strip() or not self.mapping_reference.strip()
                or any(ord(c) < 32 for c in self.publication_category + self.mapping_reference)):
            raise ValueError("The reviewed publication mapping must match the rule origin")
        return self


class DeadlineCalendar(Reviewed):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    name: str = Field(min_length=1, max_length=150)
    jurisdiction: str = Field(min_length=1, max_length=200)
    covers_from: date
    covers_until: date
    recognized_holidays: tuple[date, ...] = Field(max_length=1500)
    coverage_confirmed: Literal[True]

    @field_validator("coverage_confirmed", mode="before")
    @classmethod
    def explicit_coverage(cls, value):
        if value is not True:
            raise ValueError("Calendar coverage needs explicit confirmation")
        return value

    @model_validator(mode="after")
    def complete(self):
        if (self.covers_from > self.covers_until or (self.covers_until - self.covers_from).days > 3660
                or len(set(self.recognized_holidays)) != len(self.recognized_holidays)
                or any(not self.covers_from <= d <= self.covers_until for d in self.recognized_holidays)
                or not self.name.strip() or not self.jurisdiction.strip()
                or any(ord(c) < 32 for c in self.name + self.jurisdiction)):
            raise ValueError("Use a complete bounded calendar for the named jurisdiction")
        return self
