"""A completed finding cannot silently stand in for another unresolved issue."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens.config import Settings
from helvetic_lens.product_exploration import AssessmentOutcome
from helvetic_lens.research_final_review import reasoned_review
from helvetic_lens.research_model_transport import shape_errors
from helvetic_lens.research_review_witnesses import (
    invalid_review,
    normalize_clause_witnesses,
    review_schema,
    witness_choices,
)


def raw_review(payload, ref, selection):
    gap = next(iter(payload['final_claims_and_gaps'])).startswith('L')
    judgment = {'verdict': 'contradicted' if gap else 'supported', 'reason': ''}
    value = {'overall': judgment, 'clauses': {key: {
        'verdict': judgment['verdict'], 'reason': '', 'witnesses': [
            {'key': next(iter(witness_choices({1: ref}))), 'scope_relation': 'compatible'}]}
        for key in payload['assertion_clauses']}}
    if gap and selection != 'missing':
        value['gap_resolution'] = selection
    return value


@pytest.mark.asyncio
@pytest.mark.parametrize('selection', [None, [], ['P9'], ['P0', 'P0'], 'answered', 'missing', {}, ['P0']])
async def test_answered_gap_requires_a_current_delivered_statement_binding(selection):
    ref = {'source_id': 'record', 'locator': 'p1', 'quote': 'North Reach Survey operates the registry.'}
    answer = AssessmentOutcome(status='partial', points=[{'statement': ref['quote'],
        'evidence': [{**ref, 'role': 'support'}]}], limitations=['The registry operator is unspecified.'])
    wire = SimpleNamespace(input={'original_question': 'Who operates the registry?'}, references={1: ref})
    cache, calls = {}, []

    class Model:
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            key = next(iter(payload['final_claims_and_gaps']))
            calls.append(key)
            if key.startswith('L'):
                assert payload['delivered_points'] == [{'point_id': 'P0', 'statement': ref['quote']}]
            return json.dumps(raw_review(payload, ref, selection))

    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    result = await reasoned_review(service, wire, answer, 60, checkpoints=cache)
    if selection == ['P0']:
        assert result['status'] == 'checked'
        assert result['hints'][-1]['review_signal'] == 'not_a_gap'
    else:
        assert result['status'] == 'partial'
        assert result['pending_checks'][0]['item'] == 'L0'
        assert not any(hint['review_signal'] == 'not_a_gap' for hint in result['hints'])
        before = len(calls)
        await reasoned_review(service, wire, answer, 60, checkpoints=cache)
        assert calls[before:] == ['L0'], 'A malformed gap approval is not cached; the valid point is reused'
    assert answer.limitations, 'This audit only supplies a bound disposition; finalization owns removal'


def test_no_delivered_answer_cannot_offer_answered_as_a_gap_resolution():
    schema = review_schema('The operator is unspecified.', {}, {}, point=False)
    assert schema['properties']['gap_resolution'] == {
        'type': 'string', 'enum': ['unresolved', 'answer_available', 'outside_request']}
    assert 'gap_status' not in schema['properties']
    assert 'answer_point_ids' not in schema['properties']


@pytest.mark.parametrize('delivered', [[], [{'point_id': 'P0', 'statement': 'The registry is operated by North Reach.'}]])
@pytest.mark.parametrize('resolution', ['unresolved', 'answer_available', 'outside_request'])
def test_unanswered_gap_resolutions_remain_representable_without_invented_point_binding(delivered, resolution):
    assertion = 'The registry operator is unspecified.'
    schema = review_schema(assertion, {}, {}, point=False, delivered=delivered)
    raw = {'clauses': {'S0': {'verdict': 'not_established', 'reason': '', 'witnesses': []}},
        'overall': {'verdict': 'not_established', 'reason': ''}, 'gap_resolution': resolution}
    before = deepcopy(raw)
    assert not shape_errors(raw, schema, {})
    normalized = normalize_clause_witnesses(raw, {})
    assert normalized['gap_status'] == resolution and normalized['answer_point_ids'] == []
    assert invalid_review(normalized, assertion, {}, point=False, delivered=delivered) is None
    assert raw == before and 'gap_status' not in raw


@pytest.mark.asyncio
async def test_gap_resolution_raw_cache_revalidated_and_policy_bound(monkeypatch):
    from helvetic_lens import research_final_review

    ref = {'source_id': 'record', 'locator': 'p1', 'quote': 'North Reach Survey operates the registry.'}
    answer = AssessmentOutcome(status='partial', points=[{'statement': ref['quote'],
        'evidence': [{**ref, 'role': 'support'}]}], limitations=['The registry operator is unspecified.'])
    wire = SimpleNamespace(input={'original_question': 'Who operates the registry?'}, references={1: ref})
    cache, calls = {}, []

    class Model:
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            calls.append(next(iter(payload['final_claims_and_gaps'])))
            return json.dumps(raw_review(payload, ref, ['P0']))

    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    first = await reasoned_review(service, wire, answer, 60, checkpoints=cache)
    assert first['status'] == 'checked' and calls == ['P0', 'L0']
    cache = json.loads(json.dumps(cache))
    binding, proof = next((key, value) for key, value in cache.items()
        if isinstance(value, dict) and value.get('gap_resolution') == ['P0'])
    assert 'gap_status' not in proof and 'answer_point_ids' not in proof
    await reasoned_review(service, wire, answer, 60, checkpoints=cache)
    assert calls == ['P0', 'L0']
    proof['gap_resolution'] = []
    invalid = await reasoned_review(service, wire, answer, 60, checkpoints=cache)
    assert invalid['pending_checks'] == [{'item': 'L0', 'reason': 'invalid_response'}]
    assert binding not in cache and calls == ['P0', 'L0']
    await reasoned_review(service, wire, answer, 60, checkpoints=cache)
    assert calls == ['P0', 'L0', 'L0']
    monkeypatch.setattr(research_final_review, 'POLICY', research_final_review.POLICY + ':changed-contract')
    revised = await reasoned_review(service, wire, answer, 60, checkpoints=cache)
    assert revised['status'] == 'checked' and calls[-2:] == ['P0', 'L0'] and len(calls) == 5
