"""Completed disputes cannot hold independently checked findings behind a retry gate."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_research_review_resilience import fixture, response

from helvetic_lens import research_answer_review as audit
from helvetic_lens import research_final_review as review
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_exploration import AssessmentPoint


def bind_audits(monkeypatch, disputed, coverage):
    async def points(settings, work, wire, answer, *args, **kwargs):
        return {'status': 'checked', 'decisions': [], 'hints': [
            {'path': ['answer', 'points', index], 'review_signal': 'not_established'}
            for index, point in enumerate(answer.points) if point.statement in disputed]}

    async def request_coverage(settings, work, wire, answer, *args, **kwargs):
        statements = [point.statement for point in answer.points]
        coverage.append(statements)
        missing = not any(text in statements for text in disputed)
        return {'status': 'checked', 'question_coverage': 'missing' if missing else 'covered',
            'decisions': [], 'hints': [{'review_signal': 'requested_part_missing',
                'user_request': work['input']['original_question']}] if missing else []}

    monkeypatch.setattr(audit, 'audit_points', points)
    monkeypatch.setattr(audit, 'audit', request_coverage)


def cannot_assess(payload):
    data = json.loads(response(payload))
    for concern in data.get('concern_checks', []):
        concern.update(outcome='cannot_assess', citation_refs=[])
    return data


@pytest.mark.asyncio
@pytest.mark.parametrize('slots', [False, True])
@pytest.mark.parametrize('correctable', [False, True])
async def test_native_dispute_reaches_existing_correction_or_withholding_without_rebuying_siblings(
        monkeypatch, slots, correctable):
    texts, work, wire, parsed = fixture(slots=slots)
    original = deepcopy(parsed.mission_checkpoint.answer.model_dump())
    corrected = 'The archive is maintained by South Survey.'
    calls, coverage, writers, checkpoints = [], [], [], {}
    bind_audits(monkeypatch, {texts[1]}, coverage)

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            item = next(iter(payload['final_claims_and_gaps'].values()))
            assertion = item.get('statement', item.get('gap'))
            calls.append(assertion)
            if assertion == texts[1]:
                data = cannot_assess(payload)
                if correctable:
                    data['overall'].update(verdict='not_established')
                    for clause in data['clauses'].values():
                        clause.update(verdict='not_established', witnesses=[])
                return json.dumps(data)
            return response(payload)

    async def correction(service, current_wire, request, seconds, **kwargs):
        assert correctable, 'An unassessed objection is not a fabricated factual correction'
        writers.append(kwargs['correction']['previous_statement'])
        return [AssessmentPoint(statement=corrected,
            evidence=[{**current_wire.references[2], 'role': 'support'}])], '', {'status': 'proposed'}

    monkeypatch.setattr(review, 'answer_request', correction)
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    result = await review.finalize(service, work, wire, parsed, 90,
        checkpoints=checkpoints, defer_pending=True)
    answer = parsed.mission_checkpoint.answer
    expected = [texts[0], corrected, texts[2]] if correctable else [texts[0], texts[2]]
    assert [point.statement for point in answer.points] == expected
    assert answer.points[0].model_dump() == original['points'][0]
    assert answer.points[-1].model_dump() == original['points'][2]
    assert answer.limitations == [texts[3]], 'A genuine source-based gap must survive'
    assert result['factual_review']['pending_checks'] == []
    assert calls.count(texts[1]) == 1, 'Unchanged cannot_assess is withheld, not repeatedly purchased'
    assert calls.count(texts[0]) == calls.count(texts[2]) == 1
    assert writers == ([texts[1]] if correctable else [])
    assert coverage[-1] == expected, 'Coverage describes the exact retained answer'
    if not correctable:
        assert result['factual_review']['withheld_checks'] == [{'item': 'P1', 'reason': 'unresolved_concern'}]
        assert result['question_coverage'] == 'missing'
        assert result['rejected_points'] == [1]
    if slots:
        assert wire.point_requests == ['R0'] * len(expected)
        assert wire.response_slots['R0']['remaining_gap'] == texts[3]


@pytest.mark.asyncio
async def test_all_disputed_findings_cannot_become_a_successful_answer(monkeypatch):
    texts, work, wire, parsed = fixture()
    coverage = []
    bind_audits(monkeypatch, set(texts[:3]), coverage)

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            return json.dumps(cannot_assess(payload))

    result = await review.finalize(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()),
        work, wire, parsed, 90, defer_pending=True)
    assert parsed.mission_checkpoint.answer.points == []
    assert parsed.mission_checkpoint.answer.status == 'not_found'
    assert result['question_coverage'] == 'missing' and coverage[-1] == []
    assert len(result['factual_review']['withheld_checks']) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize('interruption,code', [
    ('deadline', 'research_review_yield'), ('timeout', 'model_upstream_timeout'),
    ('malformed', 'research_review_incomplete')])
async def test_dispute_does_not_erase_an_unfinished_check_and_resume_reuses_bound_siblings(
        monkeypatch, interruption, code):
    texts, work, wire, parsed = fixture()
    original = deepcopy(parsed.mission_checkpoint.answer.model_dump())
    coverage, calls, saved, clock, resume = [], [], {}, [0], [False]
    bind_audits(monkeypatch, {texts[1]}, coverage)
    monkeypatch.setattr(review, 'monotonic', lambda: clock[0])

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            item = next(iter(payload['final_claims_and_gaps'].values()))
            assertion = item.get('statement', item.get('gap'))
            calls.append(assertion)
            if assertion == texts[1]:
                if not resume[0] and interruption == 'deadline':
                    clock[0] = 100
                return json.dumps(cannot_assess(payload))
            if assertion == texts[2] and not resume[0]:
                if interruption == 'timeout':
                    raise DomainError('Synthetic provider interruption', 504, 'model_upstream_timeout')
                if interruption == 'malformed':
                    return '{'
            return response(payload)

    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    with pytest.raises(DomainError) as error:
        await review.finalize(service, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    assert error.value.code == code
    assert parsed.mission_checkpoint.answer.model_dump() == original
    assert 'final_correction_round' not in saved
    assert not saved.get('deferred_final_review'), 'No checked-partial eligibility was supplied'
    resume[0], clock[0] = True, 0
    result = await review.finalize(service, work, wire, parsed, 90,
        checkpoints=json.loads(json.dumps(saved)), defer_pending=True)
    assert calls.count(texts[0]) == 1, 'Saved valid sibling proof remains bound and reusable'
    assert calls.count(texts[1]) == 1, 'A valid unresolved judgment is reused without approving the disputed point'
    assert [point.statement for point in parsed.mission_checkpoint.answer.points] == [texts[0], texts[2]]
    assert result['factual_review']['pending_checks'] == []
    assert coverage[-1] == [texts[0], texts[2]]
