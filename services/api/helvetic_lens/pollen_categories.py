"""Versioned category comparison. No built-in medical scale or inferred cutoffs."""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import Field, model_validator

from .pollen_contracts import ContractModel, PollenAllergen, PollenPeriod
from .pollen_thresholds import PollenSample, Sha256, _hash, _source_order


class CategoryBand(ContractModel):
    id: Literal["none", "low", "moderate", "high", "very_high"]
    at_or_above: Decimal = Field(ge=0, allow_inf_nan=False, max_digits=12, decimal_places=6)


class CategoryScale(ContractModel):
    version: str = Field(min_length=1, max_length=128)
    review_sha256: Sha256
    source_id: str = Field(min_length=1, max_length=128)
    method_version: str = Field(min_length=1, max_length=128)
    allergen: PollenAllergen
    period: PollenPeriod
    unit: Literal["number/m3"] = "number/m3"
    status: Literal["approved", "unverified", "revoked"] = "unverified"
    bands: tuple[CategoryBand, ...] = Field(min_length=2, max_length=5)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.bands[0].at_or_above != 0 or len({b.id for b in self.bands}) != len(self.bands):
            raise ValueError("Category bands must start at zero with unique identifiers")
        if any(after.at_or_above <= before.at_or_above for before, after in zip(self.bands, self.bands[1:])):
            raise ValueError("Category band cutoffs must strictly increase")
        ranks = {name: rank for rank, name in enumerate(("none", "low", "moderate", "high", "very_high"))}
        if any(ranks[after.id] <= ranks[before.id] for before, after in zip(self.bands, self.bands[1:])):
            raise ValueError("Category labels must follow increasing concentration")
        return self

    def matches(self, series):
        return (self.source_id == series.source_id and self.method_version == series.method_version
                and self.allergen == series.allergen and self.period == series.period and self.unit == series.unit)


def evaluate_category(scale: CategoryScale, sample: PollenSample, *, now: datetime, prior: dict | None):
    if now.tzinfo is None or sample.fetched_at > now or not scale.matches(sample.series):
        raise ValueError("Category comparison requires the exact retrieved source series and clock")
    previous = PollenSample.model_validate(prior["sample"]) if prior else None
    if previous and previous.series != sample.series:
        raise ValueError("Category history must belong to the same exact source series")
    scale_hash = _hash(scale.model_dump())
    if prior and now < datetime.fromisoformat(prior["evaluated_at"]):
        raise ValueError("Category evaluation clock cannot move backwards")
    order = _source_order(sample, previous) if previous else "new"
    if order == "history_required":
        return {"state": prior, "disposition": "history_required", "changed": False}
    available = scale.status == "approved" and sample.rights == "approved" and sample.quality == "usable" and now < sample.fresh_until
    current = next((band.id for band in reversed(scale.bands) if sample.value >= band.at_or_above), None) if available else None
    previous_category = prior["category"] if prior else None
    kind = "unavailable"
    if available:
        if prior is None or previous_category is None:
            kind = "baseline"
        elif not prior["available"] or now >= previous.fresh_until:
            kind = "recovered"
        elif order == "revised" or prior.get("scale_sha256") != scale_hash or previous.policy_version != sample.policy_version:
            kind = "revision"
        elif current != previous_category:
            kind = "changed"
        else:
            kind = "stable"
    return {"state": {"category": current if available else previous_category, "available": available,
                       "scale_version": scale.version, "scale_sha256": scale_hash, "sample": sample.model_dump(mode="json"), "evaluated_at": now.isoformat()},
            "previous": previous_category, "current": current, "disposition": kind, "changed": kind == "changed"}
