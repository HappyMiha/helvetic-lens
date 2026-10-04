"""A provider quota stops fresh review calls without fabricating failed checks."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_research_review_resilience import fixture, response

from helvetic_lens import research_final_review as review
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.research_synthesis_resume import completed_work


@pytest.mark.asyncio
async def test_rate_limit_retains_only_attempted_work_and_resumes_without_rebuying_checks():
    _, _, wire, parsed = fixture()
    answer = parsed.mission_checkpoint.answer
    original = deepcopy(answer.model_dump())
    calls, checkpoints, retained = [], {}, []

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            key = next(iter(payload['final_claims_and_gaps']))
            calls.append(key)
            if key == 'P1' and calls.count(key) == 1:
                raise DomainError('Synthetic provider quota', 503, 'model_rate_limited')
            return response(payload)

    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    with pytest.raises(DomainError) as failure:
        await review.reasoned_review(service, wire, answer, 60, checkpoints=checkpoints,
            on_progress=lambda: retained.append(json.loads(json.dumps(checkpoints))))
    assert failure.value.code == 'model_rate_limited'
    assert calls == ['P0', 'P1'], 'A confirmed quota must stop before fresh sibling calls'
    assert retained[-1] == checkpoints, 'The exact failed receipt is retained before native backoff'
    proofs = {key: deepcopy(value) for key, value in checkpoints.items() if key.startswith('clauses:')}
    assert len(proofs) == len(completed_work({'parts': {'final_reviews': checkpoints}})) == 1
    failures = list(checkpoints['transient_assertions'].values())
    assert len(failures) == 1, 'Unattempted P2 and L0 must not acquire failure receipts'
    assert failures[0]['reason'] == 'model_rate_limited'
    assert failures[0]['policy_fingerprint'] == review.POLICY
    assert failures[0]['input_fingerprint'].startswith('clauses:')
    assert failures[0]['input_fingerprint'] not in proofs
    assert answer.model_dump() == original, 'Quota failure cannot approve, remove or rewrite an answer'

    resumed = json.loads(json.dumps(retained[-1]))
    result = await review.reasoned_review(service, wire, answer, 60, checkpoints=resumed)
    assert calls == ['P0', 'P1', 'P2', 'L0', 'P1']
    assert result['status'] == 'checked' and result['points_checked'] == 3
    assert result['pending_checks'] == [] and not resumed['transient_assertions']
    assert all(resumed[key] == value for key, value in proofs.items())
    assert len(completed_work({'parts': {'final_reviews': resumed}})) == 4
    before = list(calls)
    assert await review.reasoned_review(service, wire, answer, 60, checkpoints=resumed) == result
    assert calls == before, 'All completed exact checks remain reusable'


@pytest.mark.asyncio
async def test_target_specific_504_still_allows_other_assertions_to_complete():
    _, _, wire, parsed = fixture()
    calls, checkpoints = [], {}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            key = next(iter(payload['final_claims_and_gaps']))
            calls.append(key)
            if key == 'P1':
                raise DomainError('Synthetic target timeout', 504, 'model_upstream_timeout')
            return response(payload)

    result = await review.reasoned_review(
        SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()),
        wire, parsed.mission_checkpoint.answer, 60, checkpoints=checkpoints)
    assert calls == ['P0', 'P1', 'P2', 'L0']
    assert result['status'] == 'partial' and result['points_checked'] == 2
    assert result['pending_checks'] == [{'item': 'P1', 'reason': 'model_upstream_timeout'}]
    assert len(completed_work({'parts': {'final_reviews': checkpoints}})) == 3
    assert len(checkpoints['transient_assertions']) == 1
