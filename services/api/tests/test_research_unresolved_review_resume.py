"""Retain completed uncertainty without turning it into a factual approval."""
import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_research_clause_witnesses import fixture, response
from test_research_disputed_completion import cannot_assess
from test_research_review_resilience import fixture as multi_fixture
from test_research_review_resilience import response as multi_response

from helvetic_lens import research_active_retrieval as retrieval
from helvetic_lens import research_final_review as review
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_operations import fingerprint


def pending_response(payload, refs):
    value = response(payload, refs)
    for concern in value['concern_checks']:
        # Free prose cannot overrule the typed unresolved outcome.
        concern.update(outcome='cannot_assess', citation_refs=[], reason='The concern is resolved by the supplied evidence.')
    return value


def concerns_for(answer):
    return {'P0': {'previous_statements': [answer.points[0].statement], 'issues': [
        {'signal': 'fast_not_established', 'instruction': review.FAST_ADVISORY, 'original_refs': [1]}]}}


@pytest.mark.asyncio
async def test_cancelled_later_gap_resumes_after_saved_unresolved_and_checked_siblings():
    texts, _, wire, parsed = multi_fixture()
    answer = parsed.mission_checkpoint.answer
    concerns = {'P1': {'previous_statements': [texts[1]], 'issues': [
        {'instruction': review.FAST_ADVISORY, 'signal': 'fast_not_established', 'original_refs': [2]}]}}
    calls, checkpoints, retained = [], {}, []

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            key = next(iter(payload['final_claims_and_gaps']))
            calls.append(key)
            if key == 'L0' and calls.count(key) == 1:
                raise asyncio.CancelledError
            return json.dumps(cannot_assess(payload)) if key == 'P1' else multi_response(payload)

    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    original = deepcopy(answer.model_dump())
    with pytest.raises(asyncio.CancelledError):
        await review.reasoned_review(service, wire, answer, 60, checkpoints=checkpoints,
            concerns=concerns, on_progress=lambda: retained.append(deepcopy(checkpoints)))
    assert calls == ['P0', 'P1', 'P2', 'L0']
    assert len([key for key in checkpoints if key.startswith('clauses:')]) == 3
    assert any(any(c.get('outcome') == 'cannot_assess' for c in value.get('concern_checks', []))
        for value in retained[-1].values() if isinstance(value, dict))
    resumed = json.loads(json.dumps(checkpoints))
    result = await review.reasoned_review(service, wire, answer, 60, checkpoints=resumed, concerns=concerns)
    assert calls == ['P0', 'P1', 'P2', 'L0', 'L0'], 'Only the interrupted gap needs another model call'
    assert result['status'] == 'partial' and result['points_checked'] == 2
    assert result['pending_checks'] == [{'item': 'P1', 'reason': 'unresolved_concern'}]
    assert fingerprint(answer.points[1].model_dump()) not in result['positive_witnesses']
    assert 'P1' not in result['candidates'] and answer.model_dump() == original
    assert await review.reasoned_review(service, wire, answer, 60, checkpoints=resumed, concerns=concerns) == result
    assert calls == ['P0', 'P1', 'P2', 'L0', 'L0']


@pytest.mark.asyncio
@pytest.mark.parametrize('changed', ['assertion', 'uncited_original', 'concern', 'policy'])
async def test_changed_binding_rechecks_unresolved_receipt(monkeypatch, changed):
    wire, answer = fixture()
    concerns, calls, cache = concerns_for(answer), [], {}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            calls.append(payload)
            return json.dumps(pending_response(payload, wire.references))

    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    first = await review.reasoned_review(service, wire, answer, 60, checkpoints=cache, concerns=concerns)
    assert first['pending_checks'] == [{'item': 'P0', 'reason': 'unresolved_concern'}]
    cache = json.loads(json.dumps(cache))
    assert await review.reasoned_review(service, wire, answer, 60, checkpoints=cache, concerns=concerns) == first
    assert len(calls) == 1 and not first['positive_witnesses'] and not first['candidates']
    if changed == 'assertion':
        answer.points[0].statement = 'The coastal measurement increased during the observed period.'
    elif changed == 'uncited_original':
        wire.references[2]['quote'] += ' A later inland observation remained uncertain.'
    elif changed == 'concern':
        concerns['P0']['issues'][0]['instruction'] = 'Check whether the observation concerns the stated period.'
    else:
        monkeypatch.setattr(review, 'POLICY', 'changed-review-policy')
    result = await review.reasoned_review(service, wire, answer, 60, checkpoints=cache, concerns=concerns)
    assert len(calls) == 2 and result['pending_checks'] == first['pending_checks']
    assert not result['positive_witnesses'] and not result['candidates']


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['malformed_schema', 'forged_witness', 'scope', 'withdrawn'])
async def test_reused_unresolved_receipt_revalidates_shape_witness_scope_and_current_access(monkeypatch, change):
    wire, answer = fixture()
    concerns, calls, access, cache = concerns_for(answer), [], [], {}
    withdrawn = False

    async def current(service, current_wire):
        access.append(set(current_wire.references))
        if withdrawn:
            raise DomainError('Source withdrawn.', 409, 'research_evidence_scope_invalid')

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            calls.append(payload)
            return json.dumps(pending_response(payload, wire.references))

    monkeypatch.setattr(retrieval, 'ensure_current', current)
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    await review.reasoned_review(service, wire, answer, 60, checkpoints=cache, concerns=concerns)
    binding = next(key for key in cache if key.startswith('clauses:'))
    if change == 'malformed_schema':
        del cache[binding]['clauses']['S0']['reason']
    elif change == 'forged_witness':
        cache[binding]['clauses']['S0']['witnesses'][0]['key'] = 'unknown-original'
    elif change == 'scope':
        cache[binding]['clauses']['S0']['witnesses'][0]['scope_relation'] = 'different'
    else:
        withdrawn = True
    before = deepcopy(cache)
    if withdrawn:
        with pytest.raises(DomainError) as error:
            await review.reasoned_review(service, wire, answer, 60, checkpoints=cache, concerns=concerns)
        assert error.value.code == 'research_evidence_scope_invalid' and cache == before
    else:
        result = await review.reasoned_review(service, wire, answer, 60, checkpoints=cache, concerns=concerns)
        assert result['status'] == 'partial' and not result['positive_witnesses'] and not result['candidates']
        if change == 'scope':
            assert result['pending_checks'] == [{'item': 'P0', 'reason': 'unresolved_concern'}]
            assert any(hint['review_signal'] == 'not_established' for hint in result['hints'])
        else:
            assert result['pending_checks'] == [{'item': 'P0', 'reason': 'invalid_response'}]
            assert binding not in cache, 'An invalid retained response must be evicted'
    assert len(calls) == 1, 'Revalidation does not silently dispatch another review'
    assert access == [set(wire.references), set(wire.references)]
