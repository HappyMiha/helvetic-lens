"""Interrupted checked-subset delivery resumes its candidate, not its old proposal."""
import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_research_review_resilience import fixture, response

from helvetic_lens import research_answer_review as audit
from helvetic_lens import research_final_review as review
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_exploration import AssessmentOutcome


def audits(monkeypatch):
    async def points(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': []}

    async def coverage(*args, **kwargs):
        return {'status': 'checked', 'question_coverage': 'covered', 'hints': [], 'decisions': []}

    monkeypatch.setattr(audit, 'audit_points', points)
    monkeypatch.setattr(audit, 'audit', coverage)


@pytest.mark.asyncio
@pytest.mark.parametrize('second_outage', [False, True, 'unresolved_concern'])
async def test_pending_qualification_retains_completed_repair_and_narrowed_candidate(monkeypatch, second_outage):
    texts, work, wire, parsed = fixture()
    bad = texts[2] + ' It is always open.'
    parsed.mission_checkpoint.answer.points[2].statement = bad
    later_gap = 'The archive opening history is not recorded.'
    if second_outage == 'unresolved_concern':
        parsed.mission_checkpoint.answer.limitations.append(later_gap)
    original = deepcopy(parsed.mission_checkpoint.answer.model_dump())
    work['allow_checked_partial_delivery'] = True
    saved, atomic, writers, calls = {}, {}, [], []
    interrupt = [True]
    audits(monkeypatch)

    async def invalid_correction(*args, **kwargs):
        writers.append(kwargs['correction']['previous_statement'])
        return [], '', {'status': 'invalid_answer'}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            item = next(iter(payload['final_claims_and_gaps'].values()))
            assertion = item.get('statement', item.get('gap'))
            calls.append(assertion)
            if assertion == texts[3]:
                raise DomainError('Synthetic exhausted original check', 504, 'model_upstream_timeout')
            if assertion == later_gap and all(point['statement'] != bad for point in payload['delivered_points']):
                raise DomainError('Synthetic later gap check outage', 504, 'model_upstream_timeout')
            if assertion == bad:
                return json.dumps({'overall': {'verdict': 'not_established', 'reason': '', 'citation_refs': []},
                    'clauses': {'S0': {'verdict': 'supported', 'reason': '', 'citation_refs': [3]},
                        'S1': {'verdict': 'not_established', 'reason': '', 'citation_refs': []}}})
            if assertion == texts[2]:
                if interrupt[0]:
                    interrupt[0] = False
                    raise asyncio.CancelledError('Synthetic worker interruption after retained narrowing')
                if second_outage == 'unresolved_concern':
                    value = json.loads(response(payload))
                    for concern in value['concern_checks']:
                        concern.update(outcome='cannot_assess', citation_refs=[])
                    return json.dumps(value)
                if second_outage:
                    raise DomainError('Synthetic later check outage', 504, 'model_upstream_timeout')
            return response(payload)

    def retain():
        atomic.update(answer=deepcopy(parsed.mission_checkpoint.answer.model_dump()), parts=deepcopy(saved))

    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    monkeypatch.setattr(review, 'answer_request', invalid_correction)
    with pytest.raises(asyncio.CancelledError):
        await review.finalize(service, work, wire, parsed, 90, checkpoints=saved,
            on_progress=retain, defer_pending=True)
    assert atomic['parts']['deferred_final_review']['answer'] == original
    assert atomic['parts']['deferred_final_review']['status'] == 'pending'
    assert atomic['parts']['final_correction_round']['completed'] == 1
    assert atomic['answer']['points'][2]['statement'] == texts[2]
    assert len(atomic['parts']['narrowing_attempts']) == 2
    saved = json.loads(json.dumps(atomic['parts']))
    parsed.mission_checkpoint.answer = AssessmentOutcome.model_validate(atomic['answer'])
    result = await review.finalize(service, work, wire, parsed, 90, checkpoints=saved,
        on_progress=retain, defer_pending=True)
    assert writers == [bad], 'The invalid correction task was already completed before the interruption'
    assert calls.count(bad) == 1 and calls.count(texts[0]) == calls.count(texts[1]) == 1
    assert calls.count(texts[3]) == 1, 'The initial exhausted obligation must stay private, not be retried'
    assert saved['deferred_final_review']['status'] == 'qualified_delivery'
    assert saved['deferred_final_review']['answer'] == original, 'Original deferred snapshot is not overwritten'
    expected = texts[:2] if second_outage else texts[:3]
    assert [point.statement for point in parsed.mission_checkpoint.answer.points] == expected
    assert len(result['deferred_checks']) == (2 if second_outage else 1)
    retry = saved['deferred_final_review']['retry_state']
    if second_outage == 'unresolved_concern':
        assert len(retry['answer']['points']) == 2, 'The unresolved objection cannot certify a finding'
        assert later_gap in retry['answer']['limitations'], 'A separate outage remains a private retry obligation'
    else:
        assert retry['answer']['points'][2]['statement'] == texts[2], 'Keep the exact changed candidate for deferred retry'
    assert bad not in [point['statement'] for point in retry['answer']['points']]
    assert bad in json.dumps(retry['repair_concerns']), 'The earlier objection remains private review context'
    assert review.DEFERRED_NOTICE not in retry['answer']['limitations']
    assert texts[3] in retry['answer']['limitations']
    AssessmentOutcome.model_validate(retry['answer'])


@pytest.mark.asyncio
async def test_later_gap_outage_joins_deferred_obligations_and_explicit_restore_is_consumed(monkeypatch):
    texts, work, wire, parsed = fixture()
    original = deepcopy(parsed.mission_checkpoint.answer.model_dump())
    work['allow_checked_partial_delivery'] = True
    saved, calls = {}, []
    stage = ['qualify']
    audits(monkeypatch)

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            item = next(iter(payload['final_claims_and_gaps'].values()))
            assertion = item.get('statement', item.get('gap'))
            calls.append((stage[0], assertion))
            if stage[0] == 'qualify' and (assertion == texts[1] or
                    assertion == texts[3] and len(payload['delivered_points']) == 2):
                raise DomainError('Synthetic provider failure', 504, 'model_upstream_timeout')
            if stage[0] == 'restore' and assertion == texts[1]:
                raise asyncio.CancelledError('Synthetic interruption after explicit restore')
            return response(payload)

    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    result = await review.finalize(service, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    assert len(result['deferred_checks']) == 2
    assert [point.statement for point in parsed.mission_checkpoint.answer.points] == [texts[0], texts[2]]
    assert saved['deferred_final_review']['retry_state']['answer'] == original
    assert len({item['item'] for item in result['deferred_checks']}) == 2
    work['retry_deferred_review'] = True
    stage[0] = 'restore'
    atomic = {}

    def retain():
        atomic.update(answer=deepcopy(parsed.mission_checkpoint.answer.model_dump()), parts=deepcopy(saved))

    with pytest.raises(asyncio.CancelledError):
        await review.finalize(service, work, wire, parsed, 90, checkpoints=saved,
            on_progress=retain, defer_pending=True)
    assert atomic['parts']['deferred_final_review']['status'] == 'checking'
    # A later worker step still carries the explicit retry flag, but must not
    # reinstall the old proposal or overwrite a newer completed correction plan.
    saved = json.loads(json.dumps(atomic['parts']))
    parsed.mission_checkpoint.answer = AssessmentOutcome.model_validate(atomic['answer'])
    saved['final_correction_round'] = {'contract': 'literal-request-repair/v1', 'tasks': [],
        'observations': [], 'completed': 0, 'receipts': [{'status': 'retained_after_restore'}]}
    stage[0] = 'finish'
    result = await review.finalize(service, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    assert result['repairs'] == [{'status': 'retained_after_restore'}]
    assert parsed.mission_checkpoint.answer.model_dump() == original
    assert review.DEFERRED_NOTICE not in parsed.mission_checkpoint.answer.limitations
    assert 'deferred_final_review' not in saved
