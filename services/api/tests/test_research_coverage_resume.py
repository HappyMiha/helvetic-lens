"""Unavailable actual-subset coverage must preserve its real recovery reason."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_research_review_resilience import fixture, response

from helvetic_lens import research_answer_review as audit
from helvetic_lens import research_final_coverage as coverage
from helvetic_lens import research_final_review as final
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.decision_engines import Decision, DecisionUnavailable
from helvetic_lens.product_exploration import AssessmentOutcome
from helvetic_lens.research_synthesis_resume import completed_work


@pytest.mark.asyncio
@pytest.mark.parametrize(('failure', 'expected'), [
    ('step_deadline', 'research_review_yield'),
    ('timeout', 'model_temporarily_unavailable'),
    ('unavailable', 'model_temporarily_unavailable'),
    ('quota', 'model_rate_limited'),
    ('credentials', 'research_review_incomplete'),
    ('invalid_response', 'research_review_incomplete'),
    ('unknown', 'research_review_incomplete'),
])
async def test_actual_subset_coverage_preserves_failure_and_resumes_only_missing_decisions(monkeypatch, failure, expected):
    texts, work, wire, parsed = fixture()
    work['input']['original_question'] = 'Who operates the registry? Who maintains the archive? Is the registry public?'
    parsed.mission_checkpoint.answer.limitations = []
    work['allow_checked_partial_delivery'] = True
    clock, phase, requests, model_calls = [0.0], ['first'], [], []
    saved, atomic = {}, {}

    async def points(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': []}

    class Engine:
        async def choose(self, state, instructions, criteria):
            assert instructions == coverage.SYSTEM and criteria == coverage.CRITERIA
            request, point_count = state['specific_request'], len(state['answer_points'])
            requests.append((phase[0], request, point_count))
            if point_count == 2 and phase[0] == 'first':
                if failure == 'step_deadline':
                    clock[0] = 79.0  # The next literal request cannot safely start in this step.
                else:
                    raise DecisionUnavailable(failure)
            missing = point_count == 2 and request == 'Who maintains the archive?'
            return Decision('jev', 'fixture', 'missing' if missing else 'covered', {}, 1, 1, 0, 1, 1)

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            item = next(iter(payload['final_claims_and_gaps'].values()))
            model_calls.append(item['statement'])
            if item['statement'] == texts[1]:
                raise DomainError('Synthetic exhausted factual check', 504, 'model_upstream_timeout')
            return response(payload)

    def retain():
        atomic.update(answer=deepcopy(parsed.mission_checkpoint.answer.model_dump()), parts=deepcopy(saved))

    monkeypatch.setattr(audit, 'audit_points', points)
    monkeypatch.setattr(audit.decision, 'engines', lambda settings: {'jev': Engine()})
    for module in (audit, coverage, final):
        monkeypatch.setattr(module, 'monotonic', lambda: clock[0])
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    with pytest.raises(DomainError) as exc:
        await final.finalize(service, work, wire, parsed, 90, checkpoints=saved, on_progress=retain, defer_pending=True)
    assert exc.value.code == expected
    assert [point.statement for point in parsed.mission_checkpoint.answer.points] == [texts[0], texts[2]]
    assert saved['deferred_final_review']['status'] == 'pending'
    recorded = saved['coverage_interruption']['decisions']
    assert any(error['code'] == failure for receipt in recorded for error in receipt.get('fallback_errors', []))
    assert all(receipt['point_ids'] in ([], ['P0', 'P1']) for receipt in recorded)
    assert not any('coverage_interruption' in key for key in completed_work({'parts': saved}))
    assert model_calls == texts[:3]
    if failure != 'step_deadline':
        return  # Configuration/invalid responses stay fail-closed; transient classification is explicit.

    # Resume the actual reduced candidate and its private checkpoint. The first
    # completed coverage choice is a reusable proof; the interrupted receipt is not.
    saved = json.loads(json.dumps(atomic['parts']))
    parsed.mission_checkpoint.answer = AssessmentOutcome.model_validate(atomic['answer'])
    clock[0], phase[0] = 0.0, 'resume'
    result = await final.finalize(service, work, wire, parsed, 90, checkpoints=saved, on_progress=retain, defer_pending=True)
    assert model_calls == texts[:3], 'No completed factual review or deferred assertion is purchased again'
    resumed = [request for stage, request, size in requests if stage == 'resume']
    assert resumed == ['Who maintains the archive?', 'Is the registry public?']
    assert result['question_coverage'] == 'missing'
    assert saved['deferred_final_review']['status'] == 'qualified_delivery'
    assert 'coverage_interruption' not in saved
