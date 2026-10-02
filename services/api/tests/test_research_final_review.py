"""Final delivery cannot inherit a factual check of a different earlier draft."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens import research_answer_review as review
from helvetic_lens import research_gateway as gateway
from helvetic_lens.analysis import ModelClient
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.decision_engines import Decision, DecisionUnavailable
from helvetic_lens.product_exploration import Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_synthesis_resume import KEY


@pytest.mark.asyncio
@pytest.mark.parametrize('correction', ['correct', 'unresolved', 'unchanged', 'rate_limit', 'role_only'])
async def test_final_semantic_rewrite_is_checked_repaired_and_resumable(monkeypatch, correction):
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    service = SimpleNamespace(settings=settings, model_client=model)
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'Who operates the registry? Distinguish the old rule from its replacement.',
        'research_mission': {}, 'sources': [{'id': 'a' * 36, 'kind': 'public_source',
            'title': 'Fictional registry', 'url': 'https://example.org/registry', 'excerpts': [
                {'passage': 'p1', 'text': 'North Reach Survey operates the registry.'},
                {'passage': 'p2', 'text': 'The rule adopted in 2001 was abrogated in 2003; a new rule replaced it in 2003.'}]}]}}
    initial = deepcopy(work)
    good = ['North Reach Survey operates the registry.', 'The old rule from 2001 was replaced by a new rule in 2003.']
    bad = 'The rule adopted in 2001 was ratified again in 2003.'
    calls, checks, failed = [], [], [False]

    def point(index, statement=None):
        return {'statement': statement or good[index], 'evidence': [{'citation_ref': index+1, 'role': 'support'}]}

    async def complete(system, text, **options):
        value = json.loads(text)
        calls.append(value)
        if 'final_claims_and_gaps' in value:
            checks.extend(item['statement'] for item in value['final_claims_and_gaps'].values() if 'statement' in item)
            if correction == 'role_only' and failed[0]:
                return '{}'
            return json.dumps({'clauses': [{'claim_as_written': item.get('statement', item.get('gap')),
                'verdict': 'contradicted' if item.get('statement') == bad else 'supported',
                'reason': 'The original says replaced, not ratified again.' if item.get('statement') == bad else ''}
                for key, item in value['final_claims_and_gaps'].items()]})
        if 'requested_part' not in value:
            return json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'responses': {
                f'r{i+1}': {'disposition': 'answered', 'points': [point(i)], 'remaining_gap': ''} for i in (0, 1)}},
                'next_action': 'finish'})
        index = 0 if value['requested_part'].startswith('Who') else 1
        if 'citation_refs' in options['response_schema']['properties']:
            return json.dumps({'citation_refs': [index+1]})
        statement = good[0] if index == 0 else bad
        if value.get('review_feedback'):
            assert index == 1, 'An independent valid answer must not be regenerated'
            assert value['review_feedback']['previous_statements'] == [bad]
            if correction == 'rate_limit' and not failed[0]:
                failed[0] = True
                raise DomainError('Synthetic temporary rate limit', 503, 'model_rate_limited')
            if correction == 'unresolved':
                return json.dumps({'statement': '', 'evidence': [], 'remaining_gap': 'The relationship remains unresolved.'})
            if correction == 'role_only':
                failed[0] = True
                return json.dumps({'statement': bad, 'remaining_gap': '',
                    'evidence': [{'citation_ref': 2, 'role': 'context'}]})
            statement = bad if correction == 'unchanged' else good[1]
        return json.dumps({**point(index, statement), 'remaining_gap': ''})

    class Engine:
        async def choose(self, state, instructions, criteria):
            if correction == 'role_only' and failed[0]:
                raise DecisionUnavailable('quota')
            if 'specific_request' in state:
                choice = 'covered'
            elif 'statement' in state:
                checks.append(state['statement'])
                choice = 'contradicted' if state['statement'] == bad else 'supported'
            else:
                choice = 'none'
            return Decision('jev', 'test', choice, {choice: 1}, 1, 1, 1, 1, 1)

    monkeypatch.setattr(model, 'complete', complete)
    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': Engine(), 'laya': Engine()})
    schema = mission_schema(Briefing)
    if correction == 'rate_limit':
        with pytest.raises(DomainError, match='Synthetic temporary'):
            await gateway.complete(service, work, '', schema, 90)
        assert 'final_reviews' in work[KEY]['parts']
        before = len(checks)
        work = {**initial, KEY: json.loads(json.dumps(work[KEY]))}
        result = await gateway.complete(service, work, '', schema, 90)
        assert checks[before:] == good[1:], 'Unchanged exact claim reviews must not be bought again'
    else:
        result = await gateway.complete(service, work, '', schema, 90)
    answer = schema.model_validate_json(result).mission_checkpoint.answer
    assert answer.points[0].statement == good[0]
    assert bad in checks, 'The bad final rewrite was absent from the earlier draft'
    assert all(p.statement != bad for p in answer.points)
    assert not gateway.answer_quantity_errors(answer)
    if correction in {'correct', 'rate_limit'}:
        assert [p.statement for p in answer.points] == good
        assert answer.status == 'possible_answer' and answer.limitations == []
    else:
        assert len(answer.points) == 1 and answer.status == 'partial'
        assert any('Distinguish the old rule' in gap for gap in answer.limitations)
    assert len([value for value in calls if 'requested_part' not in value and 'final_claims_and_gaps' not in value]) == 2
    assert 'previous_statements' not in json.dumps(work['model_route'])


@pytest.mark.asyncio
@pytest.mark.parametrize('single_empty', [False, True])
async def test_final_counterexample_corrects_its_own_gap_and_unavailable_review_stays_explicit(monkeypatch, single_empty):
    from helvetic_lens.product_exploration import AssessmentOutcome
    from helvetic_lens.research_final_review import finalize

    ref = {'source_id': 'a', 'locator': 'p1', 'quote': 'The station opened in 2019.'}
    answer = AssessmentOutcome(status='partial', points=[{'statement': ref['quote'], 'evidence': [{**ref, 'role': 'support'}]}],
        limitations=['The opening date is not supplied.'])
    wire = SimpleNamespace(input={'sources': [{'id': 'a', 'kind': 'public_source'}]}, references={1: ref},
        request_keys={'r1': 'When did the station open?'}, point_requests=['r1'],
        response_slots={'r1': {'disposition': 'unresolved', 'remaining_gap': answer.limitations[0]}})
    work = {'input': {'sources': [{'kind': 'public_source'}], 'original_question': wire.request_keys['r1']}}
    if single_empty:
        answer.points = []
        answer.status = 'not_found'
        wire.point_requests, wire.request_keys, wire.response_slots = [], {}, {}
    parsed = SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer, reason=''))
    corrected = [False]
    class Engine:
        async def choose(self, state, instructions, criteria):
            if corrected[0]:
                raise DecisionUnavailable('quota')
            choice = 'covered' if 'specific_request' in state else 'supported' if 'statement' in state else 'L0'
            return Decision('jev', 'test', choice, {choice: 1}, 1, 1, 1, 1, 1)
    class Model:
        async def complete(self, system, text, **options):
            value = json.loads(text)
            if 'final_claims_and_gaps' in value:
                if corrected[0]:
                    return '{}'
                return json.dumps({'clauses': [{'claim_as_written': item.get('statement', item.get('gap')),
                    'verdict': 'contradicted' if 'gap' in item else 'supported',
                    'reason': 'The original explicitly supplies the opening date.' if 'gap' in item else ''}
                    for key, item in value['final_claims_and_gaps'].items()]})
            if 'citation_refs' in options['response_schema']['properties']:
                return json.dumps({'citation_refs': [1]})
            corrected[0] = True
            return json.dumps({'statement': ref['quote'], 'remaining_gap': '',
                'evidence': [{'citation_ref': 1, 'role': 'support'}]})
    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': Engine(), 'laya': Engine()})
    result = await finalize(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()), work, wire, parsed, 90)
    assert result['status'] == 'partial'
    assert answer.points[0].statement == ref['quote']
    assert 'The opening date is not supplied.' not in answer.limitations
    assert answer.status == 'partial' and any('review was unavailable' in gap for gap in answer.limitations)


@pytest.mark.asyncio
async def test_unavailable_review_fits_eight_request_slots_without_losing_findings(monkeypatch):
    from test_research_answer_parts import fixture

    from helvetic_lens.research_final_review import finalize
    wire, parsed, schema = fixture(8)
    original = deepcopy(parsed.mission_checkpoint.answer.points)
    async def unavailable(*args, **kwargs):
        return {'status': 'partial', 'hints': [], 'decisions': [], 'question_coverage': None}
    monkeypatch.setattr(review, 'audit', unavailable)
    monkeypatch.setattr('helvetic_lens.research_final_review.reasoned_review', unavailable)
    await finalize(SimpleNamespace(settings=None), {}, wire, parsed, 60)
    answer = schema.model_validate_json(wire.decode(wire.encode_checkpoint(parsed))).mission_checkpoint.answer
    assert answer.status == 'partial' and answer.points == original
    assert any('review was unavailable' in gap for gap in answer.limitations)


@pytest.mark.asyncio
async def test_final_private_pack_never_leaves_its_synthesis_boundary(monkeypatch):
    from helvetic_lens.product_exploration import AssessmentOutcome
    from helvetic_lens.research_final_review import finalize
    monkeypatch.setattr(review.decision, 'engines', lambda settings: pytest.fail('Unauthorized private egress'))
    answer = AssessmentOutcome(status='not_found', points=[], limitations=['Private review is pending.'])
    wire = SimpleNamespace(input={}, references={}, point_requests=[], request_keys={}, response_slots={})
    parsed = SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer))
    result = await finalize(SimpleNamespace(settings=Settings(_env_file=None)),
        {'input': {'sources': [{'kind': 'uploaded_file'}]}}, wire, parsed, 60)
    assert result['status'] == 'not_applicable' and answer.limitations == ['Private review is pending.']


@pytest.mark.asyncio
async def test_review_of_an_unrelated_assertion_cannot_decide_the_actual_gap():
    from helvetic_lens.product_exploration import AssessmentOutcome
    from helvetic_lens.research_final_review import reasoned_review
    answer = AssessmentOutcome(status='not_found', points=[], limitations=['The adoption date is not supplied.'])
    wire = SimpleNamespace(input={'sources': []}, references={})
    class Model:
        async def complete(self, system, text, **options):
            assert 'question' not in json.loads(text)
            return json.dumps({'clauses': [{'claim_as_written': 'The document was published in 2003.',
                'verdict': 'supported', 'reason': 'This discusses a different assertion.'}]})
    retained = {}
    result = await reasoned_review(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()),
        wire, answer, 60, checkpoints=retained)
    assert result['status'] == 'partial' and result['hints'] == [] and retained == {}
