"""C02b2 pure numeric coordinator; material updates are not delivery consent."""

from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from helvetic_lens.pollen_contracts import ContractModel, PollenRule
from helvetic_lens.pollen_rapid import RapidBinding, RapidComparison, compare_rapid_increase
from helvetic_lens.pollen_thresholds import (
    Identifier,
    PollenSample,
    PollenSeries,
    Sha256,
    ThresholdBinding,
    ThresholdDecision,
    ThresholdState,
    _content,
    _hash,
    _source_order,
    evaluate_threshold,
)


class NumericBinding(ContractModel):
    contract_version: Literal[1] = 1
    organization_id: Identifier
    owner_id: Identifier
    subject_id: Identifier
    configuration_revision: int = Field(ge=1, strict=True)
    series: PollenSeries
    rule: PollenRule

    @model_validator(mode="after")
    def numeric_rules(self) -> Self:
        if self.rule.period != self.series.period or self.rule.unit != self.series.unit:
            raise ValueError("Rule and source series must have the same period and unit")
        if self.rule.category_change or not (self.rule.threshold or self.rule.rapid_increase):
            raise ValueError("Only threshold and/or rapid rules are implemented")
        return self

    def threshold_binding(self) -> ThresholdBinding:
        rule = PollenRule(period=self.rule.period, threshold=self.rule.threshold)
        return ThresholdBinding(**self.model_dump(exclude={"rule"}), rule=rule)

    def rapid_binding(self) -> RapidBinding:
        rule = PollenRule(period=self.rule.period, rapid_increase=self.rule.rapid_increase)
        return RapidBinding(**self.model_dump(exclude={"rule"}), rule=rule)


class RapidCondition(ContractModel):
    comparison: RapidComparison
    last_good: RapidComparison | None
    matched: bool | None
    available: bool


class NumericState(ContractModel):
    contract_version: Literal[1] = 1
    binding: NumericBinding
    latest: PollenSample
    threshold: ThresholdState | None
    rapid: RapidCondition | None
    evaluated_at: AwareDatetime

    @model_validator(mode="after")
    def coherent_components(self) -> Self:
        if self.latest.series != self.binding.series or self.latest.fetched_at > self.evaluated_at:
            raise ValueError("Numeric state source/time mismatch")
        if bool(self.threshold) != bool(self.binding.rule.threshold) or bool(self.rapid) != bool(self.binding.rule.rapid_increase):
            raise ValueError("State components must match configured rules")
        if self.threshold and (self.threshold.binding != self.binding.threshold_binding()
                               or self.threshold.latest != self.latest or self.threshold.evaluated_at != self.evaluated_at):
            raise ValueError("Threshold component binding/input mismatch")
        if self.rapid:
            rapid = self.rapid
            if (rapid.comparison.binding != self.binding.rapid_binding() or rapid.comparison.current != self.latest
                    or rapid.comparison.evaluated_at != self.evaluated_at):
                raise ValueError("Rapid component binding/input mismatch")
            if (rapid.last_good is None) != (rapid.matched is None):
                raise ValueError("Rapid condition requires a last-good comparison")
            if rapid.last_good and (rapid.last_good.binding != rapid.comparison.binding or rapid.last_good.matches is None):
                raise ValueError("Rapid last-good comparison must be eligible and equally bound")
            if rapid.available and (rapid.last_good != rapid.comparison or rapid.matched != rapid.comparison.matches):
                raise ValueError("Available rapid state requires the current eligible comparison")
        return self


class NumericDecision(ContractModel):
    state: NumericState
    current: PollenSample
    baseline: PollenSample | None
    disposition: Literal["evaluated", "history_required"] = "evaluated"
    threshold: ThresholdDecision | None = None
    rapid: RapidComparison | None = None
    previous_rapid: RapidComparison | None = None
    rapid_disposition: Literal["unavailable", "baseline", "recovered", "policy_rebaseline", "revised",
                               "duplicate", "triggered", "reset", "stable"] | None = None
    reasons: tuple[Literal["threshold_triggered", "threshold_reset", "rapid_triggered", "rapid_reset"], ...] = ()
    material_id: Sha256 | None = None


def evaluate_numeric(
    binding: NumericBinding, current: PollenSample, *, as_of: datetime,
    baseline: PollenSample | None = None, prior: NumericState | None = None,
) -> NumericDecision:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("Evaluation time must be timezone aware")
    as_of = as_of.astimezone(UTC)
    if current.series != binding.series or (prior and prior.binding != binding):
        raise ValueError("Numeric state, input and private binding must match")
    if current.fetched_at > as_of or (prior and as_of < prior.evaluated_at):
        raise ValueError("Evaluation cannot precede retrieval or move backwards")
    if baseline and (not binding.rule.rapid_increase or baseline.series != binding.series or baseline.fetched_at > as_of):
        raise ValueError("Baseline must be a retrieved sample of the configured rapid series")
    order = _source_order(current, prior.latest) if prior else "new"
    baseline_revised = False
    if prior and prior.rapid and baseline:
        # Retain source revision integrity for endpoints already in this checkpoint.
        for known in (prior.rapid.comparison.baseline, prior.latest):
            if known and known.valid_at == baseline.valid_at:
                baseline_order = _source_order(baseline, known)
                if baseline_order == "history_required":
                    order = "history_required"
                baseline_revised |= baseline_order == "revised"
    if order == "history_required":
        return NumericDecision(state=prior, current=current, baseline=baseline, disposition="history_required")

    threshold = None
    reasons = []
    if binding.rule.threshold:
        threshold = evaluate_threshold(binding.threshold_binding(), current, as_of=as_of,
                                       prior=prior.threshold if prior else None)
        if threshold.transition_id:
            reasons.append("threshold_" + threshold.disposition)

    rapid = rapid_state = rapid_disposition = None
    if binding.rule.rapid_increase:
        rapid = compare_rapid_increase(binding.rapid_binding(), baseline, current, as_of=as_of)
        previous = prior.rapid if prior else None
        available = rapid.matches is not None
        matched = previous.matched if previous else None
        last_good = previous.last_good if previous else None
        rapid_disposition = "unavailable"
        if available:
            if last_good is None:
                rapid_disposition = "baseline"
            elif not previous.available or as_of >= previous.comparison.current.fresh_until:
                rapid_disposition = "recovered"
            elif current.policy_version != previous.comparison.current.policy_version:
                rapid_disposition = "policy_rebaseline"
            elif order == "revised" or baseline_revised or (
                order == "duplicate" and rapid.comparison_id != previous.comparison.comparison_id
            ):
                rapid_disposition = "revised"
            elif rapid.comparison_id == previous.comparison.comparison_id:
                rapid_disposition = "duplicate"
            elif rapid.matches != matched:
                rapid_disposition = "triggered" if rapid.matches else "reset"
                reasons.append("rapid_" + rapid_disposition)
            else:
                rapid_disposition = "stable"
            matched, last_good = rapid.matches, rapid
        rapid_state = RapidCondition(comparison=rapid, last_good=last_good, matched=matched, available=available)

    state = NumericState(binding=binding, latest=current, threshold=threshold.state if threshold else None,
                         rapid=rapid_state, evaluated_at=as_of)
    material_id = None
    if reasons:
        material_id = _hash({"coordinator_version": 1, "binding": binding.model_dump(), "current": _content(current),
                             "reasons": reasons, "rapid": rapid.comparison_id if any(r.startswith("rapid_") for r in reasons) else None})
    return NumericDecision(state=state, current=current, baseline=baseline, threshold=threshold,
                           rapid=rapid, previous_rapid=prior.rapid.last_good if prior and prior.rapid else None,
                           rapid_disposition=rapid_disposition, reasons=tuple(reasons), material_id=material_id)
