"""Resume an interrupted final answer without publishing intermediate proposals."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_research_answer_parts import selection_json

from helvetic_lens import research_answer_review as review
from helvetic_lens import research_gateway as gateway
from helvetic_lens.analysis import ModelClient
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_exploration import AssessmentOutcome, Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_synthesis_resume import KEY, DraftCheckpoint


@pytest.fixture(autouse=True)
def isolated_final_semantics(monkeypatch):
    """This module tests recovery/coverage; semantic review has its own suite."""
    from helvetic_lens import research_final_review
    async def checked(service, wire, answer, seconds, **kwargs):
        return {'status': 'checked', 'hints': [], 'points_checked': len(answer.points)}
    monkeypatch.setattr(research_final_review, 'reasoned_review', checked)


@pytest.mark.parametrize('page', ['p103', 'p.103', 'pp103–105', 'page 103'])
def test_bibliographic_page_numbers_ground_page_references_without_authorizing_other_numbers(page):
    answer = AssessmentOutcome(status='possible_answer', limitations=[], points=[{
        'statement': 'The decision was published in 2009, page 103.', 'evidence': [{
            'source_id': 'a', 'locator': 'p1', 'role': 'support',
            'quote': 'Proceedings of the meeting (2007), 2009, ' + page}]}])
    assert not gateway.answer_quantity_errors(answer)
    answer.points[0].statement = 'The decision was published in 2010, page 999.'
    assert gateway.answer_quantity_errors(answer)
    answer.points[0].statement = 'The record reports 103 participants.'
    answer.points[0].evidence[0].quote = 'Internal identifier: record103'
    assert gateway.answer_quantity_errors(answer)


@pytest.mark.asyncio
async def test_rate_limit_after_two_repairs_resumes_third_without_repeating_draft_or_review(monkeypatch):
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    service = SimpleNamespace(settings=settings, model_client=model)
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'Compare the three records.', 'research_mission': {'round': 1},
        'sources': [{'id': 'a' * 36, 'kind': 'public_source', 'url': 'https://example.org/original',
            'excerpts': [{'passage': 'p' + str(n), 'text': f'Record {n} was published in {2000+n}.'} for n in (1, 2, 3)]}]}}
    initial = deepcopy(work)
    schema = mission_schema(Briefing)
    calls, fail = [], [True]
    raw = json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'points': [
        {'statement': f'Record {n} was published in 1999.',
            'evidence': [{'citation_ref': n, 'role': 'support'}]} for n in (1, 2, 3)]},
        'next_action': 'finish', 'reason': 'The records establish their respective publication years.'})
    async def complete(system, user, **kwargs):
        value = json.loads(user)
        if 'requested_part' not in value:
            calls.append('draft_or_review')
            return raw
        number = int(value['requested_part'].split()[1])
        passages = [p for source in value['sources'] for p in source['passages']]
        ref = next(v for v in passages if v['text'].startswith(f'Record {number} '))
        if 'citation_refs' in kwargs['response_schema']['properties']:
            calls.append('select' + str(number))
            return selection_json([ref['citation_ref']], kwargs)
        calls.append(number)
        if number == 3 and fail[0]:
            fail[0] = False
            raise DomainError('Temporary synthetic rate limit', 503, 'model_rate_limited')
        return json.dumps({'statement': ref['text'], 'remaining_gap': '',
            'evidence': [{'citation_ref': ref['citation_ref'], 'role': 'support'}]})
    async def audit(*args, **kwargs):
        return {'status': 'checked', 'question_coverage': 'covered', 'hints': [], 'decisions': []}
    async def context(*args, **kwargs):
        return []
    async def original(*args, **kwargs):
        return None
    monkeypatch.setattr(model, 'complete', complete)
    monkeypatch.setattr(review, 'audit', audit)
    monkeypatch.setattr(review, 'complete_citation_context', context)
    monkeypatch.setattr(review, 'original_check', original)
    with pytest.raises(DomainError, match='Temporary synthetic rate limit'):
        await gateway.complete(service, work, '', schema, 90)
    # Round-trip through the actual private JSON representation between workers.
    retained = json.loads(json.dumps(work[KEY]))
    assert retained['stage'] == 'reviewed'
    assert '2001' in retained['raw'] and '2002' in retained['raw'] and '1999' in retained['raw']
    assert retained['raw'] not in json.dumps(work['model_route'])
    resumed = {**initial, KEY: retained}
    answer = schema.model_validate_json(await gateway.complete(service, resumed, '', schema, 90)).mission_checkpoint.answer
    assert calls == ['draft_or_review', 'draft_or_review', 'select1', 1, 'select2', 2, 'select3', 3, 3]
    assert not gateway.answer_quantity_errors(answer)
    assert [p.statement for p in answer.points] == [f'Record {n} was published in {2000+n}.' for n in (1, 2, 3)]
    assert resumed['model_route']['resumed_stage'] == 'reviewed'


@pytest.mark.asyncio
async def test_final_coverage_check_names_a_lost_request_instead_of_claiming_completion(monkeypatch):
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'When was it adopted? Distinguish adoption from publication.',
        'research_mission': {}, 'sources': [{'id': 'a' * 36, 'kind': 'public_source',
            'excerpts': [{'passage': 'p1', 'text': 'The meeting adopted the proposal in 2001.'}]}]}}
    point = {'statement': 'The proposal was adopted in 2001.', 'evidence': [{'citation_ref': 1, 'role': 'support'}]}
    async def complete(system, user, **kwargs):
        value = json.loads(user)
        if 'requested_part' in value:
            if 'citation_refs' in kwargs['response_schema']['properties']:
                return selection_json([1], kwargs)
            return json.dumps({**point, 'remaining_gap': ''})
        return json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'responses': {
            key: {'disposition': 'answered', 'points': [point], 'remaining_gap': ''} for key in ('r1', 'r2')}},
            'next_action': 'finish', 'reason': 'The adoption year is provided.'})
    async def audit(*args, coverage_only=False):
        return {'status': 'checked', 'question_coverage': 'missing', 'hints': [
            {'user_request': 'Distinguish adoption from publication.', 'review_signal': 'requested_part_missing'}], 'decisions': []}
    async def original(*args):
        return None
    monkeypatch.setattr(model, 'complete', complete)
    monkeypatch.setattr(review, 'audit', audit)
    monkeypatch.setattr(review, 'original_check', original)
    schema = mission_schema(Briefing)
    raw = await gateway.complete(SimpleNamespace(settings=settings, model_client=model), work, '', schema, 90)
    answer = schema.model_validate_json(raw).mission_checkpoint.answer
    assert answer.status == 'partial'
    assert answer.limitations == ['This answer has not resolved the requested part: Distinguish adoption from publication.']
    assert len(answer.points) == 2 and not gateway.answer_quantity_errors(answer)


@pytest.mark.parametrize('change', ['source', 'prompt', 'schema', 'model', 'endpoint', 'temperature', 'tamper'])
def test_changed_generation_or_evidence_cannot_reuse_a_saved_proposal(change):
    settings = Settings(_env_file=None)
    work = {}
    args = ['original prompt', 'review prompt', {'type': 'object'}, 'original evidence', {'max_output_tokens': 4096}]
    DraftCheckpoint(work, settings, *args).save('reviewed', 'PRIVATE CANDIDATE', [], {})
    if change == 'source':
        args[3] = 'changed evidence'
    elif change == 'prompt':
        args[1] = 'changed review prompt'
    elif change == 'schema':
        args[2] = {'type': 'array'}
    elif change == 'model':
        settings = settings.model_copy(update={'apertus_model': 'another-model'})
    elif change == 'endpoint':
        settings = settings.model_copy(update={'apertus_base_url': 'https://another.example'})
    elif change == 'temperature':
        settings = settings.model_copy(update={'apertus_temperature': 1.0})
    else:
        work[KEY]['raw'] = 'Changed saved proposal'
    assert DraftCheckpoint(work, settings, *args).value is None and KEY not in work


@pytest.mark.asyncio
@pytest.mark.parametrize('earlier_empty', [False, True])
async def test_one_invalid_point_cannot_rewrite_valid_siblings_or_shift_request_bindings(monkeypatch, earlier_empty):
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'When was it adopted? When was it published? When did it expire?',
        'research_mission': {}, 'sources': [{'id': 'a' * 36, 'kind': 'public_source',
            'excerpts': [{'passage': 'p1', 'text': 'Adopted in 2001.'},
                {'passage': 'p2', 'text': 'Published in 2003.'}, {'passage': 'p3', 'text': 'Expiry is not specified.'}]}]}}
    points = [
        {'statement': 'It was adopted in 2001.', 'evidence': [{'citation_ref': 1, 'role': 'support'}]},
        {'statement': 'It was published in 2003.', 'evidence': [{'citation_ref': 2, 'role': 'support'}]},
        {'statement': 'It expired in 2015.', 'evidence': [{'citation_ref': 3, 'role': 'support'}]}]
    calls = []
    async def complete(system, user, **kwargs):
        value = json.loads(user)
        calls.append(value)
        if 'requested_part' in value:
            refs = [ref for source in value['sources'] for ref in source['passages']]
            if value['requested_part'] != 'When did it expire?':
                index = 0 if value['requested_part'] == 'When was it adopted?' else 1
                ref = next(ref for ref in refs if ('Adopted' if index == 0 else 'Published') in ref['text'])
                if 'citation_refs' in kwargs['response_schema']['properties']:
                    return selection_json([ref['citation_ref']], kwargs)
                return json.dumps({**points[index], 'evidence': [{'citation_ref': ref['citation_ref'], 'role': 'support'}], 'remaining_gap': ''})
            ref = next(ref for ref in refs if ref['text'] == 'Expiry is not specified.')
            if 'citation_refs' in kwargs['response_schema']['properties']:
                return selection_json([ref['citation_ref']], kwargs)
            return json.dumps({'statement': 'It expired in 2015.', 'remaining_gap': '',
                'evidence': [{'citation_ref': ref['citation_ref'], 'role': 'support'}]})
        assert 'previous_invalid_response' not in value, 'Valid siblings must never be regenerated'
        return json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'responses': {
            f'r{i+1}': ({'disposition': 'unresolved', 'points': [], 'remaining_gap': 'Adoption has not been answered.'}
                if earlier_empty and i == 0 else {'disposition': 'answered', 'points': [point], 'remaining_gap': ''})
            for i, point in enumerate(points)}}, 'next_action': 'finish', 'reason': 'Everything is answered.'})
    async def audit(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': []}
    async def context(*args, **kwargs):
        return []
    async def original(*args, **kwargs):
        return None
    monkeypatch.setattr(model, 'complete', complete)
    monkeypatch.setattr(review, 'audit', audit)
    monkeypatch.setattr(review, 'complete_citation_context', context)
    monkeypatch.setattr(review, 'original_check', original)
    schema = mission_schema(Briefing)
    result = schema.model_validate_json(await gateway.complete(
        SimpleNamespace(settings=settings, model_client=model), work, '', schema, 90))
    answer = result.mission_checkpoint.answer
    assert [point.statement for point in answer.points] == [point['statement'] for point in points[:2]]
    assert answer.status == 'partial' and not gateway.answer_quantity_errors(answer)
    assert answer.limitations == ['A cited answer could not be validated for: When did it expire?']
    assert result.mission_checkpoint.reason != 'Everything is answered.'
    retained = json.loads(work[KEY]['raw'])['answer']['responses']
    assert retained['r1']['points'] == [points[0]] and retained['r2']['points'] == [points[1]]
    assert retained['r3']['points'] == [] and retained['r3']['disposition'] == 'unresolved'
    assert len(calls) == 9  # draft/review, three independent packs and one invalid-precision correction


@pytest.mark.asyncio
@pytest.mark.parametrize('review_available', [True, False, 'covered_but_wrong'])
async def test_missing_requested_distinction_is_repaired_without_rewriting_other_points(monkeypatch, review_available):
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'When was it adopted? Distinguish adoption from publication.',
        'research_mission': {}, 'sources': [{'id': 'a' * 36, 'kind': 'public_source',
            'excerpts': [{'passage': 'p1', 'text': 'Adopted in 2001.'}, {'passage': 'p2', 'text': 'Published in 2003.'}]}]}}
    point = {'statement': 'It was adopted in 2001.', 'evidence': [{'citation_ref': 1, 'role': 'support'}]}
    async def complete(system, user, **kwargs):
        value = json.loads(user)
        if 'requested_part' in value:
            refs = [ref for source in value['sources'] for ref in source['passages']]
            if 'citation_refs' in kwargs['response_schema']['properties']:
                return selection_json([ref['citation_ref'] for ref in refs], kwargs)
            if value['requested_part'] == 'When was it adopted?':
                return json.dumps({**point, 'remaining_gap': ''})
            return json.dumps({'statement': 'It was adopted in 2001 and published in 2003.', 'remaining_gap': '',
                'evidence': [{'citation_ref': ref['citation_ref'], 'role': 'support'} for ref in refs]})
        return json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'responses': {
            key: {'disposition': 'answered', 'points': [point], 'remaining_gap': ''} for key in ('r1', 'r2')}},
            'next_action': 'finish', 'reason': 'The available records address the question.'})
    async def audit(settings, work, wire, answer, seconds, *, coverage_only=False):
        missing = review_available != 'covered_but_wrong' and '2003' not in answer.points[1].statement
        return {'status': 'checked', 'question_coverage': 'missing' if missing else 'covered' if review_available else None,
            'hints': [{'user_request': 'Distinguish adoption from publication.', 'review_signal': 'requested_part_missing'}] if missing else [], 'decisions': []}
    async def original(*args, **kwargs):
        return None
    monkeypatch.setattr(model, 'complete', complete)
    monkeypatch.setattr(review, 'audit', audit)
    monkeypatch.setattr(review, 'original_check', original)
    schema = mission_schema(Briefing)
    result = schema.model_validate_json(await gateway.complete(
        SimpleNamespace(settings=settings, model_client=model), work, '', schema, 90))
    answer = result.mission_checkpoint.answer
    assert answer.status == ('possible_answer' if review_available else 'partial')
    assert answer.limitations == ([] if review_available else [
        'This answer has not resolved the requested part: Distinguish adoption from publication.'])
    assert answer.points[0].statement == point['statement']
    assert answer.points[1].statement == 'It was adopted in 2001 and published in 2003.'
    assert not gateway.answer_quantity_errors(answer)


def test_rejected_finding_gap_survives_a_full_single_request_limitations_list():
    answer = AssessmentOutcome(status='possible_answer', limitations=[f'Existing gap {i}' for i in range(8)], points=[
        {'statement': 'The record is available.', 'evidence': [{'source_id': 'a', 'locator': 'p1',
            'quote': 'The record is available.', 'role': 'support'}]},
        {'statement': 'It expired in 2015.', 'evidence': [{'source_id': 'a', 'locator': 'p2',
            'quote': 'Expiry is not specified.', 'role': 'support'}]}])
    parsed = SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer, reason='Everything answered.'))
    wire = SimpleNamespace(point_requests=[], request_keys={}, response_slots={})
    gateway.retain_answer_points(parsed, wire, gateway.answer_quantity_errors(answer))
    assert len(answer.limitations) == 8 and 'It expired in 2015.' in answer.limitations[0]
    assert answer.status == 'partial' and len(answer.points) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('available', [True, False])
async def test_source_pack_recovers_an_empty_request_slot_without_claiming_unknown_review_is_covered(monkeypatch, available):
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'Who operates the station? When did it enter service? Start with https://example.org/registry',
        'research_mission': {}, 'sources': [{'id': 'a' * 36, 'kind': 'public_source',
            'title': 'Station registry', 'url': 'https://example.org/registry', 'excerpts': [
                {'passage': 'p1', 'text': 'Operator: North Reach Survey.'},
                {'passage': 'p2', 'text': 'The station entered service in 2019.'}]}]}}
    calls = []
    async def complete(system, user, **kwargs):
        value = json.loads(user)
        calls.append(value)
        if 'requested_part' in value:
            if value['requested_part'] == 'Who operates the station?':
                if 'citation_refs' in kwargs['response_schema']['properties']:
                    return selection_json([1], kwargs)
                return json.dumps({'statement': 'North Reach Survey operates the station.', 'remaining_gap': '',
                    'evidence': [{'citation_ref': 1, 'role': 'support'}]})
            assert value['sources'][0]['title'] == 'Station registry'
            refs = [p for source in value['sources'] for p in source['passages'] if '2019' in p['text']]
            if 'citation_refs' in kwargs['response_schema']['properties']:
                return selection_json([refs[0]['citation_ref']], kwargs)
            return json.dumps({'statement': 'The station entered service in 2019.', 'remaining_gap': '',
                'evidence': [{'citation_ref': refs[0]['citation_ref'], 'role': 'support'}]})
        assert 'reason' not in kwargs['response_schema']['properties']
        return json.dumps({'answer': {'status': 'partial', 'remaining_gaps': [], 'responses': {
            'r1': {'disposition': 'answered', 'points': [{'statement': 'North Reach Survey operates the station.',
                'evidence': [{'citation_ref': 1, 'role': 'support'}]}], 'remaining_gap': ''},
            'r2': {'disposition': 'unresolved', 'points': [], 'remaining_gap': 'The commissioning date is not established.'}}},
            'next_action': 'finish'})
    async def audit(*args, **kwargs):
        return {'status': 'checked' if available else 'partial', 'hints': ([] if available or kwargs.get('coverage_only') else
            [{'user_request': 'When did it enter service?', 'review_signal': 'requested_part_missing'}]), 'decisions': [],
            'question_coverage': 'covered' if available else None}
    async def original(*args, **kwargs):
        return None
    monkeypatch.setattr(model, 'complete', complete)
    monkeypatch.setattr(review, 'audit', audit)
    monkeypatch.setattr(review, 'original_check', original)
    schema = mission_schema(Briefing)
    result = schema.model_validate_json(await gateway.complete(
        SimpleNamespace(settings=settings, model_client=model), work, '', schema, 90))
    answer = result.mission_checkpoint.answer
    assert answer.points[1].statement == 'The station entered service in 2019.'
    assert answer.status == ('possible_answer' if available else 'partial')
    assert not answer.limitations if available else any('When did it enter service?' in gap for gap in answer.limitations)
    assert 'Start with' not in str(answer.limitations)
    assert len(calls) == 6
    assert work[KEY]['parts'] and 'parts' not in work['model_route']


def test_removing_obsolete_progress_never_renews_provider_retries():
    from helvetic_lens.research_synthesis_resume import completed_work, made_progress
    previous = completed_work({'parts': {'final_reviews': {'clauses:old': {'overall': {'verdict': 'supported'}}}}})
    empty = completed_work(None)
    assert not empty and not made_progress(previous, empty)
    same = completed_work({'parts': {'final_reviews': {'clauses:old': {'overall': {'verdict': 'supported'}}},
        'workflow_gaps': ['new notice'], 'empty': {}}, 'raw': 'new wording'})
    assert not made_progress(previous, same)
    saved = completed_work({'parts': {'final_reviews': {'clauses:new': {'overall': {'verdict': 'supported'}}}}})
    assert made_progress(previous, saved)
