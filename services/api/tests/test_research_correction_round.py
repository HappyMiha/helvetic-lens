"""Durable review work must advance without losing task or source ownership."""
import json
from types import SimpleNamespace

import pytest

from helvetic_lens import research_answer_review as review
from helvetic_lens import research_final_review as final
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_exploration import AssessmentOutcome, AssessmentPoint


@pytest.mark.asyncio
@pytest.mark.parametrize('initial_pending', [False, True])
async def test_deadline_and_regrouped_points_resume_exact_pending_correction(monkeypatch, initial_pending):
    def point(name):
        return AssessmentPoint(statement=f'{name} operates the registry.', evidence=[{
            'source_id': 'a' * 36, 'locator': name, 'quote': f'{name} operates the registry.', 'role': 'support'}])
    answer = AssessmentOutcome(status='partial', points=[point('North'), point('South'), point('West')], limitations=[])
    wire = SimpleNamespace(input={'original_question': 'Which organisation operates each registry?'}, references={},
        request_keys={'r1': 'Northern registry?', 'r2': 'Southern registry?', 'r3': 'Western registry?'},
        point_requests=['r1', 'r2', 'r3'], response_slots={f'r{i}': {'disposition': 'answered', 'remaining_gap': ''} for i in range(1, 4)})
    parsed = SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer))
    service = SimpleNamespace(settings=Settings(_env_file=None))
    state, calls, snapshots = {}, [], []
    pending = [initial_pending]
    blocked = [False]
    async def audit(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'question_coverage': 'covered'}
    async def reasoned(*args, **kwargs):
        if pending[0]:
            pending[0] = False
            return {'status': 'partial', 'hints': [], 'pending_checks': [{'item': 'P1', 'reason': 'step_deadline'}]}
        hints = [{'path': ['answer', 'points', i], 'review_signal': 'not_established', 'instruction': 'Correct the operator.'}
            for i, p in enumerate(answer.points) if p.statement.startswith(('North ', 'South '))]
        return {'status': 'checked', 'hints': hints, 'pending_checks': []}
    async def correct(service, wire, request, seconds, **kwargs):
        calls.append(request)
        if request == 'Southern registry?' and not blocked[0]:
            blocked[0] = True
            return None, '', {'status': 'unavailable'}
        return point('Northern' if request == 'Northern registry?' else 'Southern'), '', {'status': 'proposed'}
    def persist():
        snapshots.append(json.loads(json.dumps(state)))
    monkeypatch.setattr(review, 'audit', audit)
    monkeypatch.setattr(final, 'reasoned_review', reasoned)
    monkeypatch.setattr(final, 'answer_request', correct)
    async def run():
        return await final.finalize(service, {'input': wire.input}, wire, parsed, 60,
            checkpoints=state, on_progress=persist, defer_pending=True)
    if initial_pending:
        with pytest.raises(DomainError) as error:
            await run()
        assert error.value.code == 'research_review_yield'
        assert 'final_correction_round' not in state and calls == []
    with pytest.raises(DomainError) as error:
        await run()
    assert error.value.code == 'research_review_yield'
    assert snapshots[-1]['final_correction_round']['completed'] == 1
    assert len(snapshots[-1]['final_correction_round']['receipts']) == 1
    state = json.loads(json.dumps(state))
    # Canonical response slots can regroup appended points on the next worker.
    answer.points = [answer.points[i] for i in (2, 0, 1)]
    wire.point_requests = ['r3', 'r1', 'r2']
    result = await run()
    assert calls == ['Northern registry?', 'Southern registry?', 'Southern registry?']
    assert [p.statement for p in answer.points] == [
        'West operates the registry.', 'Northern operates the registry.', 'Southern operates the registry.']
    assert result['rejected_points'] == []
    assert state['final_correction_round']['completed'] == 2
    assert len(state['final_correction_round']['receipts']) == 2
    assert len(state['repair_concerns']) == 2
