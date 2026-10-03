"""An ordinary worker resume must not undo a final-review correction."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from research_pack_fixtures import atomic_pack_model
from test_research_answer_parts import selection_json

from helvetic_lens import research_answer_review as review
from helvetic_lens import research_gateway as gateway
from helvetic_lens.analysis import ModelClient
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_exploration import AssessmentPoint, Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_synthesis_resume import KEY


@pytest.fixture(autouse=True)
def isolated_advisory_points(monkeypatch):
    """Recovery tests exercise final checks without calling a live fast engine."""
    async def advisory(settings, work, wire, answer, seconds, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': [], 'points_checked': len(answer.points)}
    monkeypatch.setattr(review, 'audit_points', advisory)


@pytest.mark.asyncio
async def test_final_coverage_interruption_retains_flat_final_order_and_citations(monkeypatch):
    from helvetic_lens import research_final_coverage, research_final_review

    original = ['Published in 2001.', 'An earlier edition was published in 1999.']
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'When were the two editions published?', 'research_mission': {},
        'sources': [{'id': 'a', 'kind': 'public_source', 'title': 'Original registry',
            'excerpts': [{'passage': f'p{i + 1}', 'text': statement}
                for i, statement in enumerate(original)]}]}}
    initial = deepcopy(work)
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    schema = mission_schema(Briefing)
    raw = json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'points': [
        {'statement': statement, 'evidence': [{'citation_ref': i + 1, 'role': 'support'}]}
        for i, statement in enumerate(original)]}, 'next_action': 'finish'})
    calls, interrupted = [], [False]
    @atomic_pack_model
    async def complete(system, text, **options):
        data = json.loads(text)
        assert 'requested_part' not in data, 'A complete shared draft needs no request-pack rewrite'
        outcome = options['response_schema']['$defs']['AssessmentOutcome']['properties']
        assert 'points' in outcome and 'responses' not in outcome
        calls.append(data)
        return raw
    async def audit(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'question_coverage': 'covered'}
    async def final(service, work, wire, parsed, *args, **kwargs):
        assert wire.point_requests == [] and wire.request_keys == {}
        # A final correction can change the readable point order. Resume must
        # retain that corrected order and its citations, not restore the draft.
        answer = parsed.mission_checkpoint.answer
        if [p.statement for p in answer.points] == original:
            answer.points.reverse()
        return {'status': 'checked', 'hints': [], 'question_coverage': 'covered'}
    async def reconcile(settings, work, wire, answer, *args, **kwargs):
        assert wire.point_requests == [] and wire.request_keys == {}
        assert [p.statement for p in answer.points] == original[::-1]
        assert [p.evidence[0].quote for p in answer.points] == original[::-1]
        kwargs['on_progress']()
        if not interrupted[0]:
            interrupted[0] = True
            raise DomainError('Interrupted during complete-answer coverage', 503, 'model_upstream_timeout')
        return {'status': 'checked', 'removed_notices': 0}
    async def no_original(*args, **kwargs):
        return None
    monkeypatch.setattr(model, 'complete', complete)
    monkeypatch.setattr(review, 'audit', audit)
    monkeypatch.setattr(review, 'original_check', no_original)
    monkeypatch.setattr(research_final_review, 'finalize', final)
    monkeypatch.setattr(research_final_coverage, 'reconcile', reconcile)
    service = SimpleNamespace(settings=settings, model_client=model)
    with pytest.raises(DomainError):
        await gateway.complete(service, work, '', schema, 90)
    saved = json.loads(json.dumps(work[KEY]))
    points = json.loads(saved['raw'])['answer']['points']
    assert [p['statement'] for p in points] == original[::-1]
    assert [p['evidence'][0]['citation_ref'] for p in points] == [2, 1]
    before = len(calls)
    resumed = {**initial, KEY: saved}
    result = schema.model_validate_json(await gateway.complete(service, resumed, '', schema, 90))
    assert len(calls) == before == 1, 'Coverage resume must preserve the corrected answer without drafting again'
    assert [p.statement for p in result.mission_checkpoint.answer.points] == original[::-1]
    assert [p.evidence[0].quote for p in result.mission_checkpoint.answer.points] == original[::-1]


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
    raw = json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [],
        'points': [point(bad, 1), point(sibling, 2)]}, 'next_action': 'finish'})
    calls, interrupted = [], [False]

    @atomic_pack_model
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
        assert 'requested_part' not in value, 'Only the failed final assertion may be corrected'
        calls.append(('draft', ''))
        return raw

    async def unchanged(*args, **kwargs):
        assert args[2] == work['input']['original_question']
        assert kwargs['correction']['previous_statement'] == bad
        assert kwargs['max_points'] == 1
        assert [p['statement'] for p in kwargs['feedback']['already_answered']] == [sibling]
        calls.append(('correction', bad))
        return [AssessmentPoint(statement=bad, evidence=[{'source_id': 'a' * 36, 'locator': 'p1',
            'quote': good, 'role': 'support'}])], '', {'status': 'proposed'}
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
    with pytest.raises(DomainError) as failure:
        await gateway.complete(service, work, '', schema, 90)
    assert failure.value.code == 'model_upstream_timeout'
    saved = json.loads(json.dumps(work[KEY]))
    assert saved['stage'] == 'finalizing'
    assert json.loads(saved['raw'])['answer']['points'] == [point(good, 1), point(sibling, 2)]
    assert calls.count(('draft', '')) == 1 and calls.count(('correction', bad)) == 1
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
    @atomic_pack_model
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
            repair = bool(value.get('review_feedback'))
            assert repair, 'A complete shared draft needs no unconditional request packs'
            assert value['requested_part'] == value['original_question'] == work['input']['original_question']
            index = wrong.index(value['correction_target']['previous_statement'])
            assert index < 2, 'The valid sibling must never be rewritten'
            selection = 'citation_refs' in kwargs['response_schema']['properties']
            calls.append(('select' if selection else 'write', index, repair))
            if selection:
                return selection_json([index+1], kwargs)
            if repair and index == 1 and not interrupted[0]:
                interrupted[0] = True
                raise DomainError('Synthetic writer interruption', 503, 'model_rate_limited')
            if repair and index == 0 and first_result == 'unresolved':
                return json.dumps({'points': [], 'remaining_gap': ''})
            return json.dumps({'points': [point(index, source[index])], 'remaining_gap': ''})
        calls.append(('draft',))
        return json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [],
            'points': [point(i, wrong[i]) for i in range(3)]}, 'next_action': 'finish'})
    async def audit(settings, work, wire, answer, seconds, **kwargs):
        statements = {p.statement for p in answer.points}
        assert statements & {source[1], wrong[1]} and source[2] in statements
        operator_present = bool(statements & {source[0], wrong[0]})
        return {'status': 'checked', 'question_coverage': 'covered' if operator_present else 'missing',
            'hints': [] if operator_present else [{'path': ['answer'],
                'review_signal': 'requested_part_missing', 'user_request': 'Who operates the registry?',
                'instruction': 'The remaining answer does not identify the registry operator.'}], 'decisions': []}
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
    assert saved['stage'] == 'finalizing'
    assert plan['completed'] == 1 and len(plan['tasks']) == 2
    assert len(plan['receipts']) == 1
    assert calls.count(('draft',)) == 1
    assert [call for call in calls if call[0] == 'select'] == [('select', 0, True), ('select', 1, True)]
    saved_points = json.loads(saved['raw'])['answer']['points']
    assert saved_points == [point(0, source[0] if first_result == 'corrected' else wrong[0]),
        point(1, wrong[1]), point(2, source[2])]
    before = len(calls)
    resumed = {**initial, KEY: saved}
    result = schema.model_validate_json(await gateway.complete(service, resumed, '', schema, 90))
    later = calls[before:]
    assert later[0] == ('write', 1, True), 'Resume the saved selection before any new review or correction'
    assert not any(call[:1] in [('select',), ('draft',)] for call in later)
    assert [call for call in later if call[0] == 'write'] == [('write', 1, True)]
    assert result.mission_checkpoint.answer.points[-1].statement == source[2]
    assert [p.statement for p in result.mission_checkpoint.answer.points] == (source if first_result == 'corrected' else source[1:])
    assert [p.evidence[0].quote for p in result.mission_checkpoint.answer.points] == (source if first_result == 'corrected' else source[1:])
    answer = result.mission_checkpoint.answer
    if first_result == 'corrected':
        assert answer.status == 'possible_answer' and not answer.limitations
    else:
        assert answer.status == 'partial'
        assert answer.limitations == ['This answer has not resolved the requested part: Who operates the registry?']
    assert 'final_correction_round' not in json.dumps(resumed['model_route'])
    assert all('review_feedback' not in json.dumps(ref.model_dump()) for p in result.mission_checkpoint.answer.points for ref in p.evidence)
