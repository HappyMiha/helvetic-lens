"""Keep useful exact conclusions without laundering omitted qualifications."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens import research_answer_review
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_exploration import AssessmentOutcome, AssessmentPoint
from helvetic_lens.research_coverage import unresolved_questions
from helvetic_lens.research_final_review import finalize


@pytest.mark.asyncio
@pytest.mark.parametrize('case', ['supported', 'condition', 'counterevidence', 'interrupted', 'too_many_witnesses', 'coverage', 'too_short', 'missing_numeric', 'rewrite_after_resume'])
async def test_exact_candidate_is_rechecked_with_all_old_context(monkeypatch, case):
    refs = {i: {'source_id': str(i) * 36, 'locator': 'p1', 'quote': text} for i, text in enumerate([
        'North Reach operates the registry.',
        'The date of transfer is unknown.',
        'North Reach operates only while the emergency order remains active.',
        'The order has expired; South Reach now operates the registry.',
        *[f'Additional original qualification {i}.' for i in range(5)]], 1)}
    good = 'No.' if case == 'too_short' else 'North Reach operates 4 registries.' if case == 'missing_numeric' else refs[1]['quote']
    bad = good + (' The secondary archive is available.' if case == 'too_many_witnesses' else '') + ' The transfer occurred in 2044.'
    point = AssessmentPoint(statement=bad, evidence=[{**refs[1], 'role': 'support'}, {**refs[4], 'role': 'counterevidence'}])
    answer = AssessmentOutcome(status='possible_answer', points=[point], limitations=[])
    wire = SimpleNamespace(input={'original_question': 'Who operates the registry and when was it transferred?'}, references=refs,
        request_keys={'r1': 'Who operates the registry and when was it transferred?'}, point_requests=['r1'],
        response_slots={'r1': {'disposition': 'answered', 'remaining_gap': ''}})
    parsed = SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer))
    calls, persisted, interrupted = [], [], [False]
    cache = {}

    revised = 'The registry is operated by North Reach.'
    async def cannot_improve(*args, **kwargs):
        if case == 'rewrite_after_resume' and interrupted[0]:
            return AssessmentPoint(statement=revised, evidence=[{**refs[1], 'role': 'support'}]), '', {'status': 'proposed'}
        return point.model_copy(deep=True), '', {'status': 'proposed'}

    async def audit(*args, **kwargs):
        narrowed = answer.points and answer.points[0].statement == good
        return {'status': 'checked', 'hints': [{'user_request': 'When was it transferred?'}] if narrowed and case == 'coverage' else [],
            'question_coverage': 'checked'}

    class Model:
        async def complete(self, system, text, **kwargs):
            value = json.loads(text)
            item = next(iter(value['final_claims_and_gaps'].values()))
            calls.append(item['statement'])
            def judgment(verdict, citations):
                return {'verdict': verdict, 'reason': '', 'citation_refs': citations}
            if item['statement'] == bad:
                clauses = {'S0': judgment('supported', list(refs)[:8] if case == 'too_many_witnesses' else [1]),
                    'S1': judgment('not_established', [])}
                if case == 'too_many_witnesses':
                    clauses.update(S1=judgment('supported', [9]), S2=judgment('not_established', []))
                return json.dumps({'overall': judgment('not_established', []), 'clauses': clauses,
                    **({'concern_checks': [{'id': key, 'outcome': 'remains', 'reason': '', 'citation_refs': [1]}
                        for key in value['prior_review_concerns']['concerns']]} if value.get('prior_review_concerns') else {})})
            assert item['statement'] in {good, revised}
            assert bad in value['prior_review_concerns']['previous_statements']
            assert refs[4]['quote'] in json.dumps(value['source_context']), 'Rebinding must not hide counterevidence'
            if case in {'interrupted', 'rewrite_after_resume'} and not interrupted[0]:
                interrupted[0] = True
                raise DomainError('Temporary unavailability', 503, 'model_upstream_timeout')
            rejected = case in {'condition', 'counterevidence'} or case == 'rewrite_after_resume' and item['statement'] == good
            verdict = judgment('contradicted' if rejected else 'supported', [4] if rejected else [1])
            return json.dumps({'overall': verdict, 'clauses': {'S0': verdict}, 'concern_checks': [
                {'id': key, 'outcome': 'remains' if rejected else 'resolved', 'reason': '', 'citation_refs': [4] if rejected else [1]}
                for key in value['prior_review_concerns']['concerns']]})

    if case == 'too_many_witnesses':
        # Separate quotations of one short captured original keep all nine available.
        for ref in refs.values():
            ref['source_id'] = refs[1]['source_id']
        point = AssessmentPoint(statement=bad, evidence=[{**refs[1], 'role': 'support'}])
        answer.points = [point]
    monkeypatch.setattr('helvetic_lens.research_final_review.answer_request', cannot_improve)
    monkeypatch.setattr(research_answer_review, 'audit', audit)
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    def retain():
        persisted.append(deepcopy({'answer': answer.model_dump(), 'cache': cache}))
    args = (service, {'input': wire.input}, wire, parsed, 60)
    if case in {'interrupted', 'rewrite_after_resume'}:
        with pytest.raises(DomainError):
            await finalize(*args, checkpoints=cache, on_progress=retain, defer_pending=True)
        assert persisted[-1]['answer']['points'][0]['statement'] == good
        cache = json.loads(json.dumps(cache))
    result = await finalize(*args, checkpoints=cache, on_progress=retain, defer_pending=True)
    if case in {'condition', 'counterevidence', 'too_many_witnesses', 'too_short', 'missing_numeric'}:
        assert answer.points == [] and answer.status == 'not_found'
    else:
        assert answer.points[0].statement == (revised if case == 'rewrite_after_resume' else good)
        assert [ref.quote for ref in answer.points[0].evidence] == [refs[1]['quote']]
    if case == 'interrupted':
        assert calls == [bad, bad, good, good], 'Resume the same private candidate, never recursively narrow it'
    if case == 'rewrite_after_resume':
        assert calls == [bad, bad, good, good, revised]
    if case == 'coverage':
        assert result['hints'] == [{'user_request': 'When was it transferred?'}]
    assert 'candidates' not in result and 'candidates' not in result['factual_review']


def test_completed_searches_do_not_hide_final_unanswered_requests():
    run = SimpleNamespace(question='Who operates it?', research_state={'questions': [
        {'question': 'Check public registry', 'status': 'answered'}], 'mission': {'checkpoints': [
            {'answer': {'points': [], 'limitations': ['The operator could not be established.', ' The operator could not be established. ']}}]}})
    assert unresolved_questions(run, answer=run.research_state['mission']['checkpoints'][-1]['answer']) == [{'question': 'The operator could not be established.', 'status': 'unresolved',
        'reason': 'Unresolved in the current answer.'}]
    run.research_state['mission']['checkpoints'][-1]['answer']['limitations'] = []
    assert unresolved_questions(run, answer=run.research_state['mission']['checkpoints'][-1]['answer'])[0]['question'] == run.question
    run.research_state['mission']['checkpoints'][-1]['answer']['points'] = [{'statement': 'A cited answer.'}]
    assert unresolved_questions(run, answer=run.research_state['mission']['checkpoints'][-1]['answer']) == []


@pytest.mark.asyncio
async def test_missing_positive_witnesses_rebind_without_rewriting_facts(monkeypatch):
    from helvetic_lens.research_final_review import reasoned_review
    refs = {1: {'source_id': 'a' * 36, 'locator': 'p1', 'quote': 'The council adopted the new rule.'},
        2: {'source_id': 'a' * 36, 'locator': 'p2', 'quote': 'Decision B. Meeting held in 2042.'}}
    statement = 'The council adopted the new rule in 2042.'
    point = AssessmentPoint(statement=statement, evidence=[{**refs[1], 'role': 'support'}])
    answer = AssessmentOutcome(status='possible_answer', points=[point], limitations=[])
    wire = SimpleNamespace(input={'original_question': 'When was the rule adopted?'}, references=refs,
        request_keys={'r1': 'When was the rule adopted?'}, point_requests=['r1'],
        response_slots={'r1': {'disposition': 'answered', 'remaining_gap': ''}})
    seen = []
    class Model:
        async def complete(self, system, text, **kwargs):
            value = json.loads(text)
            seen.append(value['selected_citation_refs'])
            verdict = {'verdict': 'supported', 'reason': '', 'citation_refs': [1, 2]}
            return json.dumps({'overall': verdict, 'clauses': {'S0': verdict},
                **({'concern_checks': [{'id': key, 'outcome': 'resolved', 'reason': '', 'citation_refs': [1, 2]}
                    for key in value['prior_review_concerns']['concerns']]} if value.get('prior_review_concerns') else {})})
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    proposal = await reasoned_review(service, wire, answer, 60)
    assert proposal['candidates']['P0']['statement'] == statement
    assert [ref['quote'] for ref in proposal['candidates']['P0']['evidence']] == [ref['quote'] for ref in refs.values()]
    async def unchanged(*args, **kwargs):
        return point.model_copy(deep=True), '', {'status': 'proposed'}
    async def covered(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'question_coverage': 'covered'}
    monkeypatch.setattr('helvetic_lens.research_final_review.answer_request', unchanged)
    monkeypatch.setattr(research_answer_review, 'audit', covered)
    result = await finalize(service, {'input': wire.input}, wire, SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer)), 60)
    assert answer.points[0].statement == statement and len(answer.points[0].evidence) == 2
    assert seen[-1] == [1, 2] and result['rejected_points'] == []
