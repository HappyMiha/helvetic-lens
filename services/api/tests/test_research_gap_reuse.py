"""Gap judgments depend on current statements, not their valid attachment layout."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_research_review_resilience import fixture, response

from helvetic_lens import research_final_review as review
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.research_synthesis_resume import completed_work


def setup():
    _, _, wire, parsed = fixture()
    wire.references[5] = {**wire.references[1], 'locator': 'p5'}
    calls = []

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            calls.append(payload)
            return response(payload)

    return wire, parsed.mission_checkpoint.answer, calls, SimpleNamespace(
        settings=Settings(_env_file=None), model_client=Model())


def reattach(wire, answer):
    answer.points[0].evidence[0] = type(answer.points[0].evidence[0])(
        **wire.references[5], role='support')


@pytest.mark.asyncio
async def test_completed_gap_survives_json_resume_and_valid_citation_only_change():
    wire, answer, calls, service = setup()
    cache = {}
    first = await review.reasoned_review(service, wire, answer, 60, checkpoints=cache)
    assert first['status'] == 'checked' and len(calls) == 4
    gap_request = deepcopy(calls[-1])
    cache = json.loads(json.dumps(cache))
    reattach(wire, answer)
    resumed = await review.reasoned_review(service, wire, answer, 60, checkpoints=cache)
    assert resumed['status'] == 'checked'
    assert [next(iter(call['final_claims_and_gaps'])) for call in calls[4:]] == ['P0']
    assert len([call for call in calls if 'L0' in call['final_claims_and_gaps']]) == 1
    assert gap_request['delivered_points'] == [
        {'point_id': f'P{i}', 'statement': point.statement} for i, point in enumerate(answer.points)]
    assert len(completed_work({'parts': {'final_reviews': cache}})) == 5, 'Only the changed point adds work'
    await review.reasoned_review(service, wire, answer, 60, checkpoints=json.loads(json.dumps(cache)))
    assert len(calls) == 5


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['statement', 'order', 'gap', 'source_context', 'question', 'withdrawn', 'forged'])
async def test_gap_reuse_never_skips_current_request_and_original_validation(change):
    wire, answer, calls, service = setup()
    cache = {}
    await review.reasoned_review(service, wire, answer, 60, checkpoints=cache)
    cache = json.loads(json.dumps(cache))
    if change == 'statement':
        answer.points[0].statement = 'North Survey is the registry operator.'
    elif change == 'order':
        answer.points.reverse()
    elif change == 'gap':
        answer.limitations[0] = 'The registry has no recorded earlier custodian.'
    elif change == 'source_context':
        wire.references[4] = {**wire.references[4], 'quote': 'Earlier archive custody is not recorded in this register.'}
    elif change == 'question':
        wire.input['original_question'] += ' Include earlier custody.'
    elif change == 'withdrawn':
        del wire.references[1]
    else:
        answer.points[0].evidence[0].quote = 'Forged text absent from every current original.'
    result = await review.reasoned_review(service, wire, answer, 60, checkpoints=cache)
    new_gap_calls = [call for call in calls[4:] if 'L0' in call['final_claims_and_gaps']]
    if change in {'withdrawn', 'forged'}:
        assert not new_gap_calls, 'Invalid current citations must fail before proof reuse or dispatch'
        assert {'item': 'L0', 'reason': 'unbound_original_reference'} in result['pending_checks']
        assert result['status'] == 'partial'
    else:
        assert len(new_gap_calls) == 1, 'A changed actual gap request requires a new judgment'


@pytest.mark.asyncio
async def test_exact_legacy_gap_proof_is_revalidated_without_renaming_completed_work():
    wire, answer, calls, service = setup()
    cache = {}
    await review.reasoned_review(service, wire, answer, 60, checkpoints=cache)
    payload = calls[-1]
    old = 'clauses:' + review.fingerprint({'policy': review.POLICY, 'kind': 'gap',
        'assertion': {'gap': answer.limitations[0]},
        'context': {key: value for key, value in payload.items() if key != 'final_claims_and_gaps'},
        'delivered_points': [point.model_dump() for point in answer.points]})
    new = next(key for key, value in cache.items() if isinstance(value, dict) and 'gap_resolution' in value)
    cache[old] = cache.pop(new)
    cache = json.loads(json.dumps(cache))
    before = completed_work({'parts': {'final_reviews': cache}})
    result = await review.reasoned_review(service, wire, answer, 60, checkpoints=cache)
    assert result['status'] == 'checked' and len(calls) == 4
    assert completed_work({'parts': {'final_reviews': cache}}) == before
    assert new not in cache and old in cache
    cache[old]['gap_resolution'] = []
    invalid = await review.reasoned_review(service, wire, answer, 60, checkpoints=cache)
    assert invalid['pending_checks'] == [{'item': 'L0', 'reason': 'invalid_response'}]
    assert old not in cache and len(calls) == 4


@pytest.mark.asyncio
async def test_exact_transient_gap_is_still_deferred_after_valid_attachment_change():
    wire, answer, calls, service = setup()
    real_complete = service.model_client.complete

    async def complete(system, text, **kwargs):
        payload = json.loads(text)
        if 'L0' in payload['final_claims_and_gaps']:
            calls.append(payload)
            raise DomainError('Synthetic gap timeout', 504, 'model_upstream_timeout')
        return await real_complete(system, text, **kwargs)

    service.model_client.complete = complete
    cache = {}
    first = await review.reasoned_review(service, wire, answer, 60, checkpoints=cache)
    assert first['pending_checks'] == [{'item': 'L0', 'reason': 'model_upstream_timeout'}]
    cache = json.loads(json.dumps(cache))
    reattach(wire, answer)
    resumed = await review.reasoned_review(service, wire, answer, 60, checkpoints=cache, defer_transient=True)
    assert resumed['pending_checks'] == first['pending_checks']
    assert len([call for call in calls if 'L0' in call['final_claims_and_gaps']]) == 1
    assert len(calls) == 5, 'Changed point attachments are checked independently; the exhausted gap is not retried'
