"""Compact reading refs may expand into many exact, bounded original quotes."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens import product_iterative_steps as steps
from helvetic_lens import research_gateway
from helvetic_lens.analysis import ModelClient
from helvetic_lens.config import Settings
from helvetic_lens.research_model_transport import EvidenceWire

pytestmark = pytest.mark.functional


def reading():
    source = {"id": "a" * 36, "excerpts": [
        {"passage": f"p{index:05}", "text": (f"Original passage {index}. " +
            "This condition applies only within the stated historical scope of the source. " * 6).rstrip()}
        for index in range(1, 25)]}
    work = {"phase": "extract", "unmetered_research": True, "source_id": source["id"],
        "input": {"question": "What conditions govern the original findings?", "source": source,
            "document_section": {"coverage_fingerprint": "b" * 64}}}
    response = {"source_class": None, "section_review": {
        "summary": "The original findings have explicit contextual conditions.",
        "observations": [{"citation_ref": index, "role": "support", "context_anchors": [
            {"citation_ref": anchor, "kind": "condition"} for anchor in range(17, 25)]}
            for index in range(1, 17)], "limitations": []}}
    return work, response


def service(monkeypatch, responses):
    settings = Settings(_env_file=None, apertus_provider="swisscom")
    client = ModelClient(settings)
    calls = []

    async def complete(system, content, **kwargs):
        calls.append({"system": system, "input": json.loads(content), **kwargs})
        assert len(calls) <= len(responses), "Only the existing format-repair dispatch is allowed."
        return responses[len(calls) - 1]

    monkeypatch.setattr(client, "complete", complete)
    return SimpleNamespace(settings=settings, model_client=client), calls


@pytest.mark.asyncio
async def test_compact_section_expands_beyond_wire_limit_without_losing_original_context(monkeypatch):
    work, response = reading()
    original_input = deepcopy(work["input"])
    compact = json.dumps(response)
    adapter, calls = service(monkeypatch, [compact])

    result = await steps.execute(adapter, work, 90)

    assert len(compact) < 30000 < len(result.model_dump_json()) <= 262144
    assert len(calls) == 1
    assert work["input"] == original_input
    assert work["model_route"]["evidence_transport"]["references"] == 24
    assert result.section_review.coverage_fingerprint == "b" * 64
    assert len(result.section_review.observations) == 16
    originals = original_input["source"]["excerpts"]
    for observation, original in zip(result.section_review.observations, originals, strict=False):
        assert observation.statement == observation.quote == original["text"]
        assert observation.locator == original["passage"]
        assert [anchor.model_dump() for anchor in observation.context_anchors] == [
            {"quote": item["text"], "locator": item["passage"], "kind": "condition"}
            for item in originals[16:]]
    assert not research_gateway.extraction_citation_errors(result, work)


@pytest.mark.asyncio
@pytest.mark.parametrize("presentation_padding", [False, True])
async def test_oversized_compact_section_is_rejected_before_parse_or_expansion(monkeypatch, presentation_padding):
    work, response = reading()
    if presentation_padding:
        raw = " " * 30000 + json.dumps(response)
    else:
        response["section_review"]["limitations"] = ["Untrusted text. " * 2200]
        raw = json.dumps(response)
    adapter, calls = service(monkeypatch, [raw])

    def unexpected_decode(*args):
        pytest.fail("An oversized wire response must not enter citation expansion.")

    monkeypatch.setattr(EvidenceWire, "decode", unexpected_decode)
    with pytest.raises(ValueError, match="Unbounded research response"):
        await steps.execute(adapter, work, 90)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_existing_format_repair_also_bounds_raw_section_output(monkeypatch):
    work, invalid = reading()
    invalid["section_review"]["observations"][0]["role"] = "invented"
    adapter, calls = service(monkeypatch, [json.dumps(invalid), " " * 30001])
    decoded = []
    original_decode = EvidenceWire.decode

    def decode(wire, raw):
        decoded.append(raw)
        return original_decode(wire, raw)

    monkeypatch.setattr(EvidenceWire, "decode", decode)
    with pytest.raises(ValueError, match="Unbounded research response"):
        await steps.execute(adapter, work, 90)
    assert len(calls) == 2 and len(decoded) == 1
    assert work["model_route"]["format_repair"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["foreign_anchor", "too_many_anchors", "too_many_observations"])
async def test_expanded_limit_does_not_relax_citation_or_section_schema(monkeypatch, invalid):
    work, response = reading()
    observation = response["section_review"]["observations"][0]
    if invalid == "foreign_anchor":
        observation["context_anchors"][0]["citation_ref"] = 999
    elif invalid == "too_many_anchors":
        observation["context_anchors"].append({"citation_ref": 1, "kind": "scope"})
    else:
        response["section_review"]["observations"].append(deepcopy(observation))
    raw = json.dumps(response)
    adapter, calls = service(monkeypatch, [raw, raw])
    with pytest.raises(ValueError):
        await steps.execute(adapter, work, 90)
    assert len(calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("unmetered", [False, True])
async def test_legacy_unexpanded_extraction_keeps_original_response_limit(unmetered):
    work, response = reading()
    work["unmetered_research"] = unmetered

    class LegacyClient:
        async def complete(self, *args, **kwargs):
            return json.dumps({**response, "untrusted": "x" * 30001})

    adapter = SimpleNamespace(settings=Settings(_env_file=None), model_client=LegacyClient())
    with pytest.raises(ValueError, match="Unbounded research response"):
        await steps.execute(adapter, work, 90)


@pytest.mark.asyncio
async def test_short_section_still_passes_the_same_gateway_and_canonical_validation(monkeypatch):
    work, response = reading()
    response["section_review"]["observations"] = response["section_review"]["observations"][:1]
    adapter, calls = service(monkeypatch, [json.dumps(response)])
    result = await steps.execute(adapter, work, 90)
    assert len(calls) == 1 and len(result.model_dump_json()) < 30000
    assert len(result.section_review.observations) == len(result.claims) == 1
