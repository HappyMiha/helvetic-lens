"""Scripted judgments prove completion routing, never semantic model accuracy."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_research_review_resilience import fixture, response

from helvetic_lens import research_answer_review as audit
from helvetic_lens import research_final_review as review
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_exploration import AssessmentOutcome
from helvetic_lens.research_synthesis_resume import completed_work, deferred_verification, made_progress


def native_fixture():
    texts, work, wire, parsed = fixture()
    work.update(run_id='current-run', generation=1)
    wire.work = work
    return texts, work, wire, parsed


def service(model):
    return SimpleNamespace(settings=Settings(_env_file=None), model_client=model)


@pytest.mark.asyncio
@pytest.mark.parametrize('target', ['P0', 'P1'])
@pytest.mark.parametrize('useful_sibling', [False, True])
async def test_length_at_deadline_resumes_untouched_checks_before_any_subset(monkeypatch, target, useful_sibling):
    _, work, wire, parsed = native_fixture()
    original = deepcopy(parsed.mission_checkpoint.answer.model_dump())
    clock, calls, saved = [0], [], {}

    async def points(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': []}

    async def coverage(*args, **kwargs):
        return {'status': 'checked', 'question_coverage': 'covered', 'hints': [], 'decisions': []}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            key = next(iter(payload['final_claims_and_gaps']))
            item = payload['final_claims_and_gaps'][key]
            calls.append(item.get('statement', item.get('gap')))
            if key == target and len(calls) == int(target[1:]) + 1:
                clock[0] += 85
                raise DomainError('Synthetic output length finish', 502, 'model_incomplete')
            data = json.loads(response(payload))
            if key.startswith('P') and not useful_sibling:
                data['overall']['verdict'] = 'not_established'
                for clause in data['clauses'].values():
                    clause['verdict'] = 'not_established'
            return json.dumps(data)

    monkeypatch.setattr(review, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(audit, 'audit_points', points)
    monkeypatch.setattr(audit, 'audit', coverage)
    client = service(Model())
    with pytest.raises(DomainError) as error:
        await review.finalize(client, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    assert error.value.code == 'research_review_yield'
    assert parsed.mission_checkpoint.answer.model_dump() == original
    assert 'deferred_final_review' not in saved and 'final_correction_round' not in saved
    assert not work.get('allow_checked_partial_delivery')
    assert work['unfinished_review_attempt'] == review.review_attempt(wire)
    assert len(saved['final_reviews']['incomplete_assertions']) == 1
    before = completed_work({'parts': saved})
    assert len(before) == int(target[1:]), 'A negative receipt is not completed progress'

    saved = json.loads(json.dumps(saved))
    failed_statement = original['points'][int(target[1:])]['statement']
    if useful_sibling:
        result = await review.finalize(client, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
        assert result['question_coverage'] == 'covered'
        assert result['deferred_checks'] == [{'item': target, 'reason': 'model_incomplete'}]
        assert failed_statement not in [point.statement for point in parsed.mission_checkpoint.answer.points]
    else:
        with pytest.raises(DomainError) as error:
            await review.finalize(client, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
        assert error.value.code == 'model_incomplete'
        assert parsed.mission_checkpoint.answer.model_dump() == original
        assert 'deferred_final_review' not in saved
    assert work.get('unfinished_review_attempt') is None
    for point in original['points']:
        assert calls.count(point['statement']) == 1, 'Neither failed target nor completed sibling is repurchased'
    assert original['limitations'][0] in calls, 'The untouched gap receives its ordinary check'
    assert made_progress(before, completed_work({'parts': saved}))


@pytest.mark.asyncio
@pytest.mark.parametrize('target', ['P1', 'L0'])
async def test_incomplete_target_continues_siblings_and_retries_only_in_new_generation(target):
    _, work, wire, parsed = native_fixture()
    calls, saved = [], {}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            key = next(iter(payload['final_claims_and_gaps']))
            calls.append(key)
            if key == target and work['generation'] == 1:
                raise DomainError('Synthetic incomplete review', 502, 'model_incomplete')
            return response(payload)

    client = service(Model())
    result = await review.reasoned_review(client, wire, parsed.mission_checkpoint.answer, 90, checkpoints=saved)
    assert calls == ['P0', 'P1', 'P2', 'L0']
    assert result['pending_checks'] == [{'item': target, 'reason': 'model_incomplete'}]
    assert result['status'] == 'partial'
    progress = completed_work({'parts': {'final_reviews': saved}})
    assert len(progress) == 3
    assert all(key.startswith('review:clauses:') for key in progress)
    assert len(saved['incomplete_assertions']) == 1
    saved = json.loads(json.dumps(saved))
    again = await review.reasoned_review(client, wire, parsed.mission_checkpoint.answer, 0, checkpoints=saved)
    assert again['pending_checks'] == result['pending_checks'] and len(calls) == 4
    assert not made_progress(progress, completed_work({'parts': {'final_reviews': saved}}))
    work['generation'] += 1  # Existing revision-checked native Retry boundary.
    recovered = await review.reasoned_review(client, wire, parsed.mission_checkpoint.answer, 90, checkpoints=saved)
    assert calls == ['P0', 'P1', 'P2', 'L0', target]
    assert recovered['status'] == 'checked' and recovered['pending_checks'] == []
    assert len(completed_work({'parts': {'final_reviews': saved}})) == 4


@pytest.mark.asyncio
async def test_duplicate_literal_target_shares_first_incomplete_receipt():
    _, _, wire, parsed = native_fixture()
    answer = parsed.mission_checkpoint.answer
    answer.points, answer.limitations = [answer.points[0], answer.points[0].model_copy(deep=True)], []
    calls, saved = [], {}

    class Model:
        async def complete(self, system, text, **kwargs):
            calls.append(json.loads(text))
            raise DomainError('Synthetic incomplete review', 502, 'model_incomplete')

    result = await review.reasoned_review(service(Model()), wire, answer, 90, checkpoints=saved)
    assert len(calls) == 1
    assert result['pending_checks'] == [{'item': key, 'reason': 'model_incomplete'} for key in ('P0', 'P1')]
    assert len(saved['incomplete_assertions']) == 1
    assert completed_work({'parts': {'final_reviews': saved}}) == {}


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['statement', 'original', 'policy', 'unbound'])
async def test_incomplete_skip_requires_exact_current_binding(monkeypatch, change):
    texts, _, wire, parsed = native_fixture()
    answer = parsed.mission_checkpoint.answer
    answer.points, answer.limitations = answer.points[:1], []
    calls, saved = [], {}

    class Model:
        async def complete(self, system, text, **kwargs):
            calls.append(json.loads(text))
            raise DomainError('Synthetic incomplete review', 502, 'model_incomplete')

    client = service(Model())
    await review.reasoned_review(client, wire, answer, 90, checkpoints=saved)
    if change == 'statement':
        answer.points[0].statement += ' It administers this registry.'
    elif change == 'original':
        wire.references[1]['quote'] = texts[0] + ' The record is current.'
        answer.points[0].evidence[0].quote = wire.references[1]['quote']
    elif change == 'policy':
        monkeypatch.setattr(review, 'POLICY', 'changed-review-policy')
    else:
        del wire.references[1]  # A stale/withdrawn exact citation is not a reusable failure.
    result = await review.reasoned_review(client, wire, answer, 90,
        checkpoints=json.loads(json.dumps(saved)))
    if change == 'unbound':
        assert len(calls) == 1
        assert result['pending_checks'] == [{'item': 'P0', 'reason': 'unbound_original_reference'}]
    else:
        assert len(calls) == 2
        assert result['pending_checks'] == [{'item': 'P0', 'reason': 'model_incomplete'}]
    assert result['positive_witnesses'] == {}


@pytest.mark.asyncio
@pytest.mark.parametrize('retry_while_pending', [False, True])
async def test_checked_subset_requires_current_coverage_and_restores_terminal_obligations_once(monkeypatch, retry_while_pending):
    texts, work, wire, parsed = native_fixture()
    original = deepcopy(parsed.mission_checkpoint.answer.model_dump())
    calls, coverages, saved, atomic = [], [], {}, {}
    coverage_ready = [False]

    async def points(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': []}

    async def coverage(settings, work, wire, answer, seconds, **kwargs):
        statements = [point.statement for point in answer.points]
        coverages.append(statements)
        ready = len(statements) == 3 or coverage_ready[0]
        return {'status': 'checked' if ready else 'partial', 'question_coverage': 'covered' if ready else None,
            'hints': [], 'decisions': []}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            item = next(iter(payload['final_claims_and_gaps'].values()))
            assertion = item.get('statement', item.get('gap'))
            calls.append((work['generation'], assertion))
            if work['generation'] == 1 and assertion in (texts[1], texts[3]):
                raise DomainError('Synthetic incomplete review', 502, 'model_incomplete')
            return response(payload)

    def retain():
        atomic.update(answer=deepcopy(parsed.mission_checkpoint.answer.model_dump()), parts=deepcopy(saved))

    monkeypatch.setattr(audit, 'audit_points', points)
    monkeypatch.setattr(audit, 'audit', coverage)
    client = service(Model())
    with pytest.raises(DomainError) as error:
        await review.finalize(client, work, wire, parsed, 90, checkpoints=saved,
            on_progress=retain, defer_pending=True)
    assert error.value.code == 'research_review_incomplete'
    assert len(calls) == 4
    assert saved['deferred_final_review']['status'] == 'pending'
    assert deferred_verification({'parts': saved}) is None
    assert coverages[-1] == [texts[0], texts[2]]
    assert saved['deferred_final_review']['retry_state']['answer'] == original

    saved = json.loads(json.dumps(atomic['parts']))
    parsed.mission_checkpoint.answer = AssessmentOutcome.model_validate(atomic['answer'])
    work['allow_checked_partial_delivery'] = False  # New ordinary worker dispatch.
    coverage_ready[0] = True
    if retry_while_pending:
        work['generation'] += 1
        result = await review.finalize(client, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
        assert parsed.mission_checkpoint.answer.model_dump() == original
        assert calls == [(1, text) for text in texts] + [(2, texts[1]), (2, texts[3])]
        assert 'deferred_final_review' not in saved and 'deferred_checks' not in result
        assert not work.get('allow_checked_partial_delivery')
        return
    result = await review.finalize(client, work, wire, parsed, 90, checkpoints=saved,
        on_progress=retain, defer_pending=True)
    assert len(calls) == 4, 'Neither incomplete targets nor completed siblings are repurchased'
    assert work['allow_checked_partial_delivery'] is True
    assert result['question_coverage'] == 'covered' and len(result['deferred_checks']) == 2
    assert [point.statement for point in parsed.mission_checkpoint.answer.points] == [texts[0], texts[2]]
    assert parsed.mission_checkpoint.answer.limitations == [review.DEFERRED_NOTICE]
    assert deferred_verification({'parts': saved})['reasons'] == ['model_incomplete']
    assert saved['deferred_final_review']['status'] == 'qualified_delivery'

    work['generation'] += 1
    work['allow_checked_partial_delivery'] = False
    result = await review.finalize(client, work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    assert parsed.mission_checkpoint.answer.model_dump() == original
    assert calls == [(1, text) for text in texts] + [(2, texts[1]), (2, texts[3])]
    assert 'deferred_final_review' not in saved
    assert 'deferred_checks' not in result
    assert deferred_verification({'parts': saved}) is None


@pytest.mark.asyncio
@pytest.mark.parametrize('blocker', ['all_incomplete', 'citation_attachment', 'real_concern'])
async def test_terminal_failure_cannot_qualify_an_unreviewed_or_objected_candidate(monkeypatch, blocker):
    texts, work, wire, parsed = native_fixture()
    answer = parsed.mission_checkpoint.answer
    answer.points, answer.limitations = answer.points[:2], []
    original = answer.model_dump()
    saved = {}

    async def points(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': []}

    async def coverage(*args, **kwargs):
        return {'status': 'checked', 'question_coverage': 'covered', 'hints': [], 'decisions': []}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            key = next(iter(payload['final_claims_and_gaps']))
            if key == 'P1' or blocker == 'all_incomplete':
                raise DomainError('Synthetic incomplete review', 502, 'model_incomplete')
            data = json.loads(response(payload))
            if blocker == 'citation_attachment':
                for clause in data['clauses'].values():
                    clause['witnesses'] = [{'key': f'2: {texts[1][:24]}', 'scope_relation': 'compatible'}]
            else:
                data['overall']['verdict'] = 'not_established'
                for clause in data['clauses'].values():
                    clause['verdict'] = 'not_established'
            return json.dumps(data)

    monkeypatch.setattr(audit, 'audit_points', points)
    monkeypatch.setattr(audit, 'audit', coverage)
    with pytest.raises(DomainError) as error:
        await review.finalize(service(Model()), work, wire, parsed, 90, checkpoints=saved, defer_pending=True)
    assert error.value.code == 'model_incomplete'
    assert sum(key.startswith('clauses:') for key in saved['final_reviews']) == (0 if blocker == 'all_incomplete' else 1)
    assert parsed.mission_checkpoint.answer.model_dump() == original
    assert 'deferred_final_review' not in saved
    assert not work.get('allow_checked_partial_delivery')
    assert deferred_verification({'parts': saved}) is None
