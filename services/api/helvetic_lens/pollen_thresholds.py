"""C02a pure threshold component; no authorization, source approval or dispatch.

Inputs come from a future gated adapter. Callers must atomically persist returned
state/evidence and deduplicate transition IDs before any downstream side effect.
"""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, field_validator, model_validator

from helvetic_lens.pollen_contracts import ContractModel, PollenAllergen, PollenPeriod, PollenRule

Identifier = Annotated[str, Field(min_length=1, max_length=128)]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
SourceValue = Annotated[Decimal, Field(ge=0, allow_inf_nan=False, max_digits=60, decimal_places=40)]


class ForecastSeries(ContractModel):
    model: Identifier
    grid: Identifier
    member: Identifier
    layer: Identifier
    cell: int = Field(ge=0, strict=True)
    issue_at: AwareDatetime

    @field_validator("issue_at")
    @classmethod
    def utc_issue(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class PollenSeries(ContractModel):
    source_id: Identifier
    method_version: Identifier
    station_id: str = Field(pattern=r"^[A-Z]{3}$")
    allergen: PollenAllergen
    period: PollenPeriod
    unit: Literal["number/m3"] = "number/m3"
    forecast: ForecastSeries | None = None

    @model_validator(mode="after")
    def forecast_matches_period(self) -> Self:
        if (self.period == PollenPeriod.FORECAST_INSTANT) != (self.forecast is not None):
            raise ValueError("Forecast period requires model/grid/member/layer/cell/issue identity")
        return self


class PollenSample(ContractModel):
    contract_version: Literal[1] = 1
    series: PollenSeries
    valid_at: AwareDatetime
    source_revision: int = Field(ge=1, strict=True)
    value: SourceValue | None
    quality: Literal["usable", "missing", "stale", "unavailable"]
    rights: Literal["approved", "unverified", "revoked"]
    policy_version: Identifier
    parser_version: Identifier
    artifact_hashes: tuple[Sha256, ...] = Field(min_length=1, max_length=8)
    fetched_at: AwareDatetime
    fresh_until: AwareDatetime

    @field_validator("value", mode="before")
    @classmethod
    def lossless_value(cls, value):
        if isinstance(value, (float, bool)):
            raise ValueError("Source values require Decimal, decimal text or an integer")
        return value

    @field_validator("valid_at", "fetched_at", "fresh_until")
    @classmethod
    def utc_time(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def valid_sample(self) -> Self:
        if self.quality == "usable" and self.value is None:
            raise ValueError("A usable sample requires a finite nonnegative concentration")
        freshness_origin = self.series.forecast.issue_at if self.series.forecast else self.valid_at
        if self.fresh_until < freshness_origin:
            raise ValueError("Freshness deadline cannot precede source observation/issue time")
        if self.series.forecast:
            if min(self.valid_at, self.fetched_at) < self.series.forecast.issue_at:
                raise ValueError("Forecast validity/retrieval cannot precede issue time")
        elif self.valid_at > self.fetched_at:
            raise ValueError("Observation cannot be measured after retrieval")
        if len(set(self.artifact_hashes)) != len(self.artifact_hashes):
            raise ValueError("Evidence artifact hashes must be unique")
        return self


class ThresholdBinding(ContractModel):
    contract_version: Literal[1] = 1
    organization_id: Identifier
    owner_id: Identifier
    subject_id: Identifier
    configuration_revision: int = Field(ge=1, strict=True)
    series: PollenSeries
    rule: PollenRule

    @model_validator(mode="after")
    def threshold_only(self) -> Self:
        if self.rule.period != self.series.period or self.rule.unit != self.series.unit:
            raise ValueError("Rule and source series must have the same period and unit")
        if self.rule.threshold is None or self.rule.rapid_increase or self.rule.category_change:
            raise ValueError("C02a supports threshold-only rules; other rules require another evaluator")
        return self


class ThresholdState(ContractModel):
    contract_version: Literal[1] = 1
    binding: ThresholdBinding
    latest: PollenSample
    last_good: PollenSample | None
    active: bool | None
    available: bool
    evaluated_at: AwareDatetime

    @model_validator(mode="after")
    def coherent_state(self) -> Self:
        if self.latest.series != self.binding.series or (
            self.last_good and self.last_good.series != self.binding.series
        ):
            raise ValueError("State samples must belong to the bound series")
        if (self.last_good is None) != (self.active is None):
            raise ValueError("Threshold state requires a last-good baseline")
        if self.last_good and self.last_good.valid_at > self.latest.valid_at:
            raise ValueError("Last-good state cannot be newer than the latest input")
        if self.last_good and (self.last_good.quality != "usable" or self.last_good.rights != "approved"):
            raise ValueError("Last-good evidence must have been usable and approved")
        if self.latest.fetched_at > self.evaluated_at:
            raise ValueError("State evaluation cannot precede retrieval")
        if self.available and (self.last_good != self.latest or self.evaluated_at >= self.latest.fresh_until):
            raise ValueError("Available state requires current, unexpired last-good evidence")
        return self


class ThresholdDecision(ContractModel):
    state: ThresholdState
    disposition: Literal["baseline", "stable", "triggered", "reset", "unavailable", "recovered",
                         "revised", "policy_rebaseline", "duplicate", "history_required"]
    previous: PollenSample | None
    current: PollenSample
    transition_id: Sha256 | None = None


def _decimal_text(value: Decimal) -> str:
    # Decimal.normalize() would round to the ambient context precision.
    if value == 0:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _hash(value) -> str:
    def encode(item):
        if isinstance(item, Decimal):
            return _decimal_text(item)
        if isinstance(item, datetime):
            return item.astimezone(UTC).isoformat()
        raise TypeError("Unsupported transition identity component")
    return hashlib.sha256(json.dumps(value, default=encode, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _content(sample: PollenSample) -> dict:
    # Retrieval/quality/rights can change without revising the provider's values.
    payload = sample.model_dump(mode="json", exclude={"fetched_at", "fresh_until", "quality", "rights", "policy_version"})
    if sample.value is not None:
        payload["value"] = _decimal_text(sample.value)
    return payload


def evaluate_threshold(
    binding: ThresholdBinding, sample: PollenSample, *, as_of: datetime,
    prior: ThresholdState | None = None,
) -> ThresholdDecision:
    """Evaluate one ordered series. Return history-required for older input.

    First state, recovery, latest corrections and policy changes rebaseline
    silently. Transition IDs are candidate evidence identities, never mail consent.
    """
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("Evaluation time must be timezone aware")
    as_of = as_of.astimezone(UTC)
    if sample.series != binding.series or (prior and prior.binding != binding):
        raise ValueError("State, input and private configuration binding must match")
    if sample.fetched_at > as_of or (prior and as_of < prior.evaluated_at):
        raise ValueError("Evaluation cannot precede retrieval or move its clock backwards")
    previous = prior.last_good if prior else None
    revised = duplicate = False
    if prior:
        latest = prior.latest
        if sample.valid_at < latest.valid_at or (
            sample.valid_at == latest.valid_at and sample.source_revision < latest.source_revision
        ):
            return ThresholdDecision(state=prior, disposition="history_required", previous=previous, current=sample)
        if sample.valid_at == latest.valid_at:
            duplicate = sample.source_revision == latest.source_revision
            revised = not duplicate
            if duplicate and _content(sample) != _content(latest):
                raise ValueError("Conflicting content for the same source time and revision")
            if duplicate and sample.policy_version == latest.policy_version and sample.fresh_until != latest.fresh_until:
                raise ValueError("Freshness deadline cannot change without a source or policy revision")
            if duplicate and sample.fetched_at < latest.fetched_at:
                return ThresholdDecision(state=prior, disposition="history_required", previous=previous, current=sample)

    available = sample.quality == "usable" and sample.rights == "approved" and as_of < sample.fresh_until
    active = prior.active if prior else None
    disposition = "unavailable"
    if available:
        threshold = binding.rule.threshold
        if sample.value >= threshold.trigger_at_or_above:
            next_active = True
        elif sample.value <= threshold.reset_at_or_below:
            next_active = False
        else:
            next_active = bool(active)
        if previous is None:
            disposition = "baseline"
        elif not prior.available or as_of >= prior.latest.fresh_until:
            disposition = "recovered"
        elif revised:
            disposition = "revised"
        elif sample.policy_version != prior.latest.policy_version:
            disposition = "policy_rebaseline"
        elif duplicate:
            disposition = "duplicate"
        elif next_active != active:
            disposition = "triggered" if next_active else "reset"
        else:
            disposition = "stable"
        active = next_active
    state = ThresholdState(binding=binding, latest=sample, last_good=sample if available else previous,
                           active=active, available=available, evaluated_at=as_of)
    transition_id = None
    if disposition in {"triggered", "reset"}:
        transition_id = _hash({"binding": binding.model_dump(), "sample": _content(sample),
                               "disposition": disposition})
    return ThresholdDecision(state=state, disposition=disposition, previous=previous,
                             current=sample, transition_id=transition_id)
