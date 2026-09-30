"""The real final-request boundary keeps strict base/required output contracts."""

import json
from types import SimpleNamespace

import pytest

from helvetic_lens import product_iterative_steps as steps
from helvetic_lens import product_question_renewal as renewal


def briefing():
    return {
        "understanding": "A tentative source interpretation.",
        "findings": [
            {
                "source_id": "source",
                "statement": "The retained source states this.",
                "quote": "A retained passage",
                "locator": "p1",
                "basis": "direct",
            }
        ],
        "uncertainties": ["The remaining context is unclear."],
        "clarification": "",
        "directions": [],
    }


async def response(raw, *, selected=False, recover=True, targets=True):
    calls = []

    async def complete(system, user, **kwargs):
        calls.append(kwargs)
        assert "_renewal_unavailable" not in json.dumps(kwargs["response_schema"])
        return raw

    work = {"phase": "brief", "input": {}}
    if targets:
        work["input"]["question_renewal_targets"] = [{"question_id": "q"}]
    if recover:
        work["input"]["question_renewal_recovery"] = renewal.RECOVERY_CONTRACT
    if selected:
        work["input"]["assessment_question"] = {"question_id": "selected"}
    service = SimpleNamespace(
        model_client=SimpleNamespace(complete=complete),
        settings=SimpleNamespace(apertus_provider="scripted", apertus_model="fictional"),
    )
    try:
        return await steps.execute(service, work, 10)
    finally:
        assert len(calls) == 1
        assert calls[0]["budget"].max_requests == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("optional", [None, {}, "invalid", [False], [{"question_id": "q"}], [None] * 4])
async def test_only_invalid_optional_section_is_discarded(optional):
    value = {**briefing(), "question_renewals": optional}
    result = await response(json.dumps(value))
    assert result._renewal_unavailable and result.question_renewals == []
    assert result.findings[0].quote == "A retained passage"
    assert "_renewal_unavailable" not in result.model_dump()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode",
    [
        "malformed",
        "too_large",
        "extra_base",
        "missing_base",
        "forged_status",
        "missing_required",
        "invalid_required",
        "legacy",
        "no_targets",
        "non_json_number",
    ],
)
async def test_required_contracts_and_whole_response_bounds_still_reject(mode):
    value = {**briefing(), "question_renewals": "invalid"}
    if mode == "extra_base":
        value["unexpected"] = "must reject"
    if mode == "missing_base":
        value.pop("findings")
    if mode == "forged_status":
        value["_renewal_unavailable"] = True
    if mode == "invalid_required":
        value["assessment"] = {"question_id": "selected"}
    raw = json.dumps(value)
    if mode == "malformed":
        raw = raw[:-2]
    if mode == "too_large":
        raw = json.dumps({**value, "question_renewals": "x" * 30001})
    if mode == "non_json_number":
        raw = raw.replace('"invalid"', "NaN")
    with pytest.raises(ValueError):
        await response(
            raw,
            selected=mode in {"missing_required", "invalid_required"},
            recover=mode != "legacy",
            targets=mode != "no_targets",
        )


@pytest.mark.asyncio
async def test_absent_optional_and_fenced_json_preserve_normal_summary():
    result = await response("```json\n" + json.dumps(briefing()) + "\n```")
    assert not result._renewal_unavailable and result.question_renewals == []
