"""C02b1 exact-window comparison; a matched comparison is not an alert.

No source admission, authorization, persistence or dispatch happens here. A later
state coordinator must handle initial/recovery baselines and overlapping windows.
"""

from datetime import UTC, datetime, timedelta
from decimal import Context, Decimal, localcontext
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from helvetic_lens.pollen_contracts import ContractModel, PollenRule
from helvetic_lens.pollen_thresholds import Identifier, PollenSample, PollenSeries, Sha256, _content, _hash


class RapidBinding(ContractModel):
    contract_version: Literal[1] = 1
    organization_id: Identifier
    owner_id: Identifier
    subject_id: Identifier
    configuration_revision: int = Field(ge=1, strict=True)
    series: PollenSeries
    rule: PollenRule

    @model_validator(mode="after")
    def rapid_only(self) -> Self:
        if self.rule.period != self.series.period or self.rule.unit != self.series.unit:
            raise ValueError("Rule and source series must have the same period and unit")
        if self.rule.rapid_increase is None or self.rule.threshold or self.rule.category_change:
            raise ValueError("C02b1 supports rapid-only rules; combined rules require a coordinator")
        return self


class RapidComparison(ContractModel):
    evaluator_version: Literal["pollen-rapid-v1"] = "pollen-rapid-v1"
    binding: RapidBinding
    baseline: PollenSample | None
    current: PollenSample
    evaluated_at: AwareDatetime
    reason: Literal["matched", "below_minimum", "baseline_missing", "current_unavailable",
                    "current_rights", "current_expired", "baseline_unavailable", "baseline_rights",
                    "window_mismatch", "policy_mismatch", "parser_mismatch"]
    delta: Decimal | None = Field(default=None, allow_inf_nan=False)
    matches: bool | None = None
    comparison_id: Sha256 | None = None


def compare_rapid_increase(
    binding: RapidBinding, baseline: PollenSample | None, current: PollenSample, *, as_of: datetime,
) -> RapidComparison:
    """Compare exact source times; never substitute nearest/poll/zero baseline.

    Historical baseline quality/rights must be usable/approved now; its old live
    freshness deadline alone does not invalidate a historical comparison. Current
    data must still be fresh. Caller rechecks policy eligibility for BOTH inputs.
    """
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("Evaluation time must be timezone aware")
    as_of = as_of.astimezone(UTC)
    for sample in (baseline, current):
        if sample is None:
            continue
        if sample.series != binding.series:
            raise ValueError("Both samples must belong to the exact bound source series")
        if sample.fetched_at > as_of:
            raise ValueError("Evaluation cannot precede retrieval")

    def unavailable(reason):
        return RapidComparison(binding=binding, baseline=baseline, current=current, evaluated_at=as_of, reason=reason)

    if current.quality != "usable":
        return unavailable("current_unavailable")
    if current.rights != "approved":
        return unavailable("current_rights")
    if as_of >= current.fresh_until:
        return unavailable("current_expired")
    if baseline is None:
        return unavailable("baseline_missing")
    if baseline.quality != "usable":
        return unavailable("baseline_unavailable")
    if baseline.rights != "approved":
        return unavailable("baseline_rights")
    if current.valid_at - baseline.valid_at != timedelta(hours=binding.rule.rapid_increase.window_hours):
        return unavailable("window_mismatch")
    if current.policy_version != baseline.policy_version:
        return unavailable("policy_mismatch")
    if current.parser_version != baseline.parser_version:
        return unavailable("parser_mismatch")
    # Source values have at most 60 digits / 40 fractional places. A private
    # context preserves subtraction even if the caller uses low precision/traps.
    with localcontext(Context(prec=128)):
        delta = current.value - baseline.value
    matches = delta >= binding.rule.rapid_increase.minimum_increase
    identity = _hash({"evaluator_version": "pollen-rapid-v1", "binding": binding.model_dump(),
                      "baseline": _content(baseline), "current": _content(current),
                      "policy_version": current.policy_version})
    return RapidComparison(binding=binding, baseline=baseline, current=current,
                           evaluated_at=as_of,
                           reason="matched" if matches else "below_minimum", delta=delta,
                           matches=matches, comparison_id=identity)
