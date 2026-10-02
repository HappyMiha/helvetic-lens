"""An ordinary worker resume must not undo a final-review correction."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_research_answer_parts import selection_json

from helvetic_lens import research_answer_review as review
from helvetic_lens import research_gateway as gateway
from helvetic_lens.analysis import ModelClient
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_exploration import AssessmentPoint, Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_synthesis_resume import KEY


@pytest.mark.asyncio
async def test_multipart_narrowed_draft_survives_gateway_retry_with_same_citations_and_sibling(monkeypatch):
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    good = 'North Reach operates the registry.'
    bad = good + ' North Reach owns the archive.'
    sibling = 'The public archive is available.'
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'Who operates the registry? Is the archive available?', 'research_mission': {},
        'sources': [{'id': 'a' * 36, 'kind': 'public_source', 'url': 'https://example.org/registry',
            'excerpts': [{'passage': 'p1', 'text': good}, {'passage': 'p2', 'text': sibling}]}]}}
    initial = deepcopy(work)
    def point(statement, ref):
        return {'statement': statement, 'evidence': [{'citation_ref': ref, 'role': 'support'}]}
    raw = json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'responses': {
        'r1': {'disposition': 'answered', 'remaining_gap': '', 'points': [point(bad, 1)]},
        'r2': {'disposition': 'answered', 'remaining_gap': '', 'points': [point(sibling, 2)]}}}, 'next_action': 'finish'})
    calls, interrupted = [], [False]

    async def complete(system, user, **kwargs):
        value = json.loads(user)
        if 'final_claims_and_gaps' in value:
            statement = next(iter(value['final_claims_and_gaps'].values()))['statement']
            calls.append(('final', statement))
            def judgment(verdict, refs):
                return {'verdict': verdict, 'reason': '', 'citation_refs': refs}
            if statement == bad:
                return json.dumps({'overall': judgment('not_established', []),
                    'clauses': {'S0': judgment('supported', [1]), 'S1': judgment('not_established', [])},
                    **({'concern_checks': [{'id': key, 'outcome': 'remains', 'reason': '', 'citation_refs': [1]}
                        for key in value['prior_review_concerns']['concerns']]} if value.get('prior_review_concerns') else {})})
            assert statement in {good, sibling}
            if statement == good and not interrupted[0]:
                interrupted[0] = True
                raise DomainError('Synthetic interruption after narrowing', 503, 'model_upstream_timeout')
            verdict = judgment('supported', [1 if statement == good else 2])
            return json.dumps({'overall': verdict, 'clauses': {'S0': verdict},
                **({'concern_checks': [{'id': key, 'outcome': 'resolved', 'reason': '', 'citation_refs': [1]}
                    for key in value['prior_review_concerns']['concerns']]} if value.get('prior_review_concerns') else {})})
        if 'requested_part' in value:
            first = value['requested_part'] == 'Who operates the registry?'
            calls.append(('synthesis', value['requested_part']))
            if 'citation_refs' in kwargs['response_schema']['properties']:
                return selection_json([1 if first else 2], kwargs)
            return json.dumps({**point(bad if first else sibling, 1 if first else 2), 'remaining_gap': ''})
        calls.append(('draft', ''))
        return raw

    async def unchanged(*args, **kwargs):
        return AssessmentPoint(statement=bad, evidence=[{'source_id': 'a' * 36, 'locator': 'p1',
            'quote': good, 'role': 'support'}]), '', {'status': 'proposed'}
    async def audit(*args, **kwargs):
        return {'status': 'checked', 'question_coverage': 'covered', 'hints': [], 'decisions': []}
    async def original(*args, **kwargs):
        return None
    monkeypatch.setattr(model, 'complete', complete)
    monkeypatch.setattr(review, 'audit', audit)
    monkeypatch.setattr(review, 'original_check', original)
    monkeypatch.setattr('helvetic_lens.research_final_review.answer_request', unchanged)
    schema = mission_schema(Briefing)
    service = SimpleNamespace(settings=settings, model_client=model)
    with pytest.raises(DomainError, match='Synthetic interruption'):
        await gateway.complete(service, work, '', schema, 90)
    saved = json.loads(json.dumps(work[KEY]))
    assert saved['stage'] == 'finalizing'
    slots = json.loads(saved['raw'])['answer']['responses']
    assert slots['r1']['points'] == [point(good, 1)] and slots['r2']['points'] == [point(sibling, 2)]
    before = len(calls)
    resumed = {**initial, KEY: saved}
    result = schema.model_validate_json(await gateway.complete(service, resumed, '', schema, 90))
    answer = result.mission_checkpoint.answer
    assert calls[before:] == [('final', good)], 'Resume only the pending check, never restore the rejected draft'
    assert [p.statement for p in answer.points] == [good, sibling]
    assert [p.evidence[0].quote for p in answer.points] == [good, sibling]
    assert answer.status == 'possible_answer' and not answer.limitations
    assert resumed['model_route']['resumed_stage'] == 'finalizing'
    assert not gateway.answer_quantity_errors(answer)


@pytest.mark.asyncio
@pytest.mark.parametrize('first_result', ['corrected', 'unresolved'])
async def test_later_correction_resumes_writer_without_repeating_completed_request(monkeypatch, first_result):
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    source = ['North Reach operates the registry.', 'South Reach owns the archive.', 'The archive is public.']
    wrong = ['East Reach operates the registry.', 'West Reach owns the archive.', source[2]]
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'Who operates the registry? Who owns the archive? Is the archive public?',
        'research_mission': {}, 'sources': [{'id': 'a' * 36, 'kind': 'public_source',
            'url': 'https://example.org/registry', 'excerpts': [
                {'passage': f'p{i+1}', 'text': text} for i, text in enumerate(source)]}]}}
    initial = deepcopy(work)
    calls, interrupted = [], [False]
    def point(index, statement):
        return {'statement': statement, 'evidence': [{'citation_ref': index+1, 'role': 'support'}]}
    async def complete(system, user, **kwargs):
        value = json.loads(user)
        if 'final_claims_and_gaps' in value:
            item = next(iter(value['final_claims_and_gaps'].values()))
            statement = item.get('statement', item.get('gap'))
            calls.append(('review', statement))
            bad = statement in wrong[:2]
            ref = wrong.index(statement)+1 if bad else source.index(statement)+1
            verdict = {'verdict': 'contradicted' if bad else 'supported',
                'reason': 'The named operator differs from the original.' if bad else '', 'citation_refs': [ref]}
            return json.dumps({'overall': verdict, 'clauses': {'S0': verdict},
                **({'concern_checks': [{'id': key, 'outcome': 'remains' if bad else 'resolved',
                    'reason': '', 'citation_refs': [ref]} for key in value['prior_review_concerns']['concerns']]}
                    if value.get('prior_review_concerns') else {})})
        if 'requested_part' in value:
            index = ['Who operates the registry?', 'Who owns the archive?', 'Is the archive public?'].index(value['requested_part'])
            repair = bool(value.get('review_feedback'))
            selection = 'citation_refs' in kwargs['response_schema']['properties']
            calls.append(('select' if selection else 'write', index, repair))
            if selection:
                return selection_json([index+1], kwargs)
            if repair and index == 1 and not interrupted[0]:
                interrupted[0] = True
                raise DomainError('Synthetic writer interruption', 503, 'model_rate_limited')
            if repair and index == 0 and first_result == 'unresolved':
                return json.dumps({'statement': '', 'evidence': [], 'remaining_gap': ''})
            return json.dumps({**point(index, source[index] if repair else wrong[index]), 'remaining_gap': ''})
        calls.append(('draft',))
        return json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'responses': {
            f'r{i+1}': {'disposition': 'answered', 'remaining_gap': '', 'points': [point(i, wrong[i])]}
            for i in range(3)}}, 'next_action': 'finish'})
    async def audit(*args, **kwargs):
        return {'status': 'checked', 'question_coverage': 'covered', 'hints': [], 'decisions': []}
    async def original(*args, **kwargs):
        return None
    monkeypatch.setattr(model, 'complete', complete)
    monkeypatch.setattr(review, 'audit', audit)
    monkeypatch.setattr(review, 'original_check', original)
    schema, service = mission_schema(Briefing), SimpleNamespace(settings=settings, model_client=model)
    with pytest.raises(DomainError, match='Synthetic writer interruption'):
        await gateway.complete(service, work, '', schema, 90)
    saved = json.loads(json.dumps(work[KEY]))
    plan = saved['parts']['final_correction_round']
    assert plan['completed'] == 1 and len(plan['tasks']) == 2
    assert len(plan['receipts']) == 1
    before = len(calls)
    resumed = {**initial, KEY: saved}
    result = schema.model_validate_json(await gateway.complete(service, resumed, '', schema, 90))
    later = calls[before:]
    assert later[0] == ('write', 1, True), 'Resume the saved selection before any new review or correction'
    assert not any(call[:1] in [('select',), ('draft',)] for call in later)
    assert [call for call in later if call[0] == 'write'] == [('write', 1, True)]
    assert result.mission_checkpoint.answer.points[-1].statement == source[2]
    assert [p.statement for p in result.mission_checkpoint.answer.points] == (source if first_result == 'corrected' else source[1:])
    assert 'final_correction_round' not in json.dumps(resumed['model_route'])
    assert all('review_feedback' not in json.dumps(ref.model_dump()) for p in result.mission_checkpoint.answer.points for ref in p.evidence)
