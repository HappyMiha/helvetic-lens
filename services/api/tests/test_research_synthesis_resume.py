"""Resume an interrupted final answer without publishing intermediate proposals."""
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
from helvetic_lens.product_exploration import AssessmentOutcome, Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_synthesis_resume import KEY, DraftCheckpoint, completed_work, made_progress


@pytest.fixture(autouse=True)
def isolated_final_semantics(monkeypatch):
    """This module tests recovery/coverage; semantic review has its own suite."""
    from helvetic_lens import research_final_review
    async def checked(service, wire, answer, seconds, **kwargs):
        return {'status': 'checked', 'hints': [], 'points_checked': len(answer.points)}
    async def advisory(settings, work, wire, answer, seconds, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': [], 'points_checked': len(answer.points)}
    monkeypatch.setattr(research_final_review, 'reasoned_review', checked)
    monkeypatch.setattr(review, 'audit_points', advisory)


@pytest.mark.parametrize('verdict', ['supported', 'contradicted', 'not_established'])
def test_completed_advisory_decision_renews_progress_but_failed_attempts_do_not(verdict):
    receipt = {'choice': verdict, 'input_fingerprint': 'input-a',
        'policy_fingerprint': 'policy-a', 'configured_engine_fingerprint': 'engine-a'}
    checkpoint = {'parts': {'point_decisions': {'point-a': receipt}}}
    finished = completed_work(checkpoint)
    assert made_progress({}, finished), 'A completed exact check must survive worker-step continuation'
    restored = json.loads(json.dumps(checkpoint))
    assert not made_progress(finished, completed_work(restored)), 'Restoring the same check is not new work'
    restored['parts']['point_decisions'].update({
        'failed': {'choice': 'unavailable', 'input_fingerprint': 'input-b', 'policy_fingerprint': 'policy-a'},
        'unbound': {'choice': 'supported'},
        'noise': {'latency_ms': 200, 'fallback_errors': [{'code': 'timeout'}]},
    })
    assert completed_work(restored) == finished
    assert not made_progress(finished, completed_work(restored))
    restored['parts']['point_decisions']['failed']['fallback_errors'] = [{'code': 'another-timeout'}]
    assert not made_progress(finished, completed_work(restored)), 'Changing failure bookkeeping must not renew retries'
    restored['parts']['point_decisions']['point-b'] = {**receipt, 'input_fingerprint': 'input-b'}
    assert made_progress(finished, completed_work(restored))


@pytest.mark.parametrize('selected', [[], [2, 7]])
def test_only_completed_bound_evidence_selection_renews_progress(selected):
    receipt = {'status': 'complete', 'input_fingerprint': 'all-originals-a',
        'policy_fingerprint': 'selection-policy', 'selected': selected}
    checkpoint = {'parts': {'evidence_selection': {'batch-a': receipt}}}
    finished = completed_work(checkpoint)
    assert made_progress({}, finished), 'A checked batch with no relevant evidence is still completed work'
    restored = json.loads(json.dumps(checkpoint))
    restored['parts']['evidence_selection'].update({
        'pending': {**receipt, 'status': 'pending'},
        'failed': {**receipt, 'status': 'unavailable'},
        'unbound': {'status': 'complete', 'selected': [2]},
        'duplicate': {**receipt, 'selected': [2, 2]},
        'invalid': {**receipt, 'selected': [True]},
        'noise': {'duration_ms': 300},
    })
    assert completed_work(restored) == finished
    assert not made_progress(finished, completed_work(restored))
    restored['parts']['evidence_selection']['batch-b'] = {**receipt, 'input_fingerprint': 'all-originals-b'}
    assert made_progress(finished, completed_work(restored))


def test_final_review_selection_progress_survives_resume_without_counting_noise():
    receipt = {'status': 'complete', 'input_fingerprint': 'gap-originals',
        'policy_fingerprint': 'selection-policy', 'selected': [3]}
    checkpoint = {'parts': {'final_reviews': {'original_selection': {'evidence_selection': {'gap': receipt}}}}}
    finished = completed_work(checkpoint)
    assert made_progress({}, finished)
    restored = json.loads(json.dumps(checkpoint))
    assert not made_progress(finished, completed_work(restored))
    nodes = restored['parts']['final_reviews']['original_selection']['evidence_selection']
    nodes.update({'failed': {**receipt, 'status': 'unavailable'},
        'unbound': {'status': 'complete', 'selected': [4]}, 'noise': {'attempts': 5}})
    assert completed_work(restored) == finished
    nodes['point'] = {**receipt, 'input_fingerprint': 'point-originals', 'selected': []}
    assert made_progress(finished, completed_work(restored))


def test_preparation_survives_without_draft_but_selected_request_cannot_reuse_another_draft():
    settings = Settings(_env_file=None)
    work = {}
    args = ['prompt', 'review', {'type': 'object'}, 'all-originals', {}]
    checkpoint = DraftCheckpoint(work, settings, *args, preparation_policy='selection-v1')
    checkpoint.parts['evidence_selection'] = {'batch': {'status': 'complete', 'selected': [2],
        'input_fingerprint': 'input', 'policy_fingerprint': 'selection-v1'}}
    checkpoint.save('preparing', '', [], {})
    changed_policy = DraftCheckpoint(deepcopy(work), settings, *args, preparation_policy='selection-v2')
    assert changed_policy.value is None and not changed_policy.parts
    restored = DraftCheckpoint(json.loads(json.dumps(work)), settings, *args, preparation_policy='selection-v1')
    assert restored.value['stage'] == 'preparing' and not restored.value['raw']
    assert restored.parts == checkpoint.parts
    restored.bind_request({'citation_ref': {'enum': [2]}}, 'selected original two')
    restored.parts['final_reviews'] = {'clauses:old-answer': {'overall': {'verdict': 'supported'}}}
    restored.save('draft', 'PRIVATE DRAFT BASED ON TWO', [], {})
    same = DraftCheckpoint(restored.work, settings, *args, preparation_policy='selection-v1')
    same.bind_request({'citation_ref': {'enum': [2]}}, 'selected original two')
    assert same.value['raw'] == 'PRIVATE DRAFT BASED ON TWO'
    same.bind_request({'citation_ref': {'enum': [3]}}, 'different selected original')
    assert same.value is None and KEY not in same.work
    assert set(same.parts) == {'evidence_selection'}, 'Checks of the previous answer cannot validate a new input'


@pytest.mark.asyncio
@pytest.mark.parametrize('seconds,selection_elapsed,finished_batch', [(0, 0, False), (10, 12, True)])
async def test_exhausted_draft_time_yields_with_prepared_evidence(monkeypatch, seconds, selection_elapsed, finished_batch):
    from helvetic_lens import research_evidence_pack

    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'Who operates the registry?', 'research_mission': {},
        'sources': [{'id': 'a' * 36, 'kind': 'public_source',
            'excerpts': [{'passage': 'p1', 'text': 'North Reach operates the registry.'}]}]}}
    elapsed = [0]

    async def select(service, wire, question, seconds, *, checkpoints, on_progress):
        if finished_batch:
            checkpoints['evidence_selection'] = {'last': {'status': 'complete',
                'input_fingerprint': 'last-original-batch', 'policy_fingerprint': research_evidence_pack.POLICY,
                'selected': [1]}}
            on_progress()
        elapsed[0] = selection_elapsed
        return deepcopy(wire.references)

    async def no_draft(*args, **kwargs):
        pytest.fail('The drafting provider must not be called after the work step is exhausted')

    monkeypatch.setattr(gateway, 'monotonic', lambda: elapsed[0])
    monkeypatch.setattr(research_evidence_pack, 'select_evidence', select)
    monkeypatch.setattr(model, 'complete', no_draft)
    with pytest.raises(DomainError) as error:
        await gateway.complete(SimpleNamespace(settings=settings, model_client=model), work,
            '', mission_schema(Briefing), seconds)
    assert error.value.code == 'research_evidence_pack_incomplete'
    assert work[KEY]['stage'] == 'preparing' and work[KEY]['raw'] == ''
    assert bool(completed_work(work[KEY])) is finished_batch


@pytest.mark.asyncio
async def test_selection_interruption_resumes_before_one_draft_and_preserves_full_originals(monkeypatch):
    from helvetic_lens import research_evidence_pack, research_final_coverage, research_final_review

    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    service = SimpleNamespace(settings=settings, model_client=model)
    originals = ['The early register names the operator.',
        'The later amendment limits that authority to the northern district.',
        'The original archive remains available.']
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'Which limits apply to the registered authority?', 'research_mission': {},
        'sources': [{'id': 'a' * 36, 'kind': 'public_source', 'url': 'https://example.org/register',
            'discovery_links': [{'title': 'Related original', 'url': 'https://example.org/related',
                'context': 'Discovery is retained for routing.', 'kind': 'document'}],
            'excerpts': [{'passage': f'p{i + 1}', 'text': text} for i, text in enumerate(originals)]}]}}
    initial = deepcopy(work)
    calls, checked_batches, inspected_originals = [], [], []
    interrupted, final_interrupted = [False], [False]

    async def select(service, wire, question, seconds, *, checkpoints, on_progress):
        assert question == initial['input']['original_question'] and len(wire.references) == 3
        nodes = checkpoints.setdefault('evidence_selection', {})
        for batch, refs in [('early', [1]), ('later', [2])]:
            if batch not in nodes:
                checked_batches.append(batch)
                nodes[batch] = {'status': 'complete', 'input_fingerprint': batch,
                    'policy_fingerprint': research_evidence_pack.POLICY, 'selected': refs}
                on_progress()
                if not interrupted[0]:
                    interrupted[0] = True
                    raise DomainError('Selection interrupted', 503, 'model_rate_limited')
        return {2: wire.references[2]}

    async def complete(system, text, **options):
        data = json.loads(text)
        calls.append(data)
        assert 'discovery_links' not in data['sources'][0]
        assert data['sources'][0]['excerpts'] == [{'citation_ref': 2, 'text': originals[1], 'passage': 'p2'}]
        citation = options['response_schema']['$defs']['AssessmentEvidence']['properties']['citation_ref']
        assert citation['enum'] == [2]
        return json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'points': [
            {'statement': originals[1], 'evidence': [{'citation_ref': 2, 'role': 'support'}]}]},
            'next_action': 'finish'})

    async def final(service, work, wire, parsed, *args, **kwargs):
        assert len(wire.references) == 3 and len(wire.input['sources'][0]['excerpts']) == 3
        assert wire.input['sources'][0]['discovery_links']
        if not final_interrupted[0]:
            final_interrupted[0] = True
            # A later targeted correction may legitimately read another original.
            additional = parsed.mission_checkpoint.answer.points[0].model_copy(deep=True)
            additional.statement = additional.evidence[0].quote = originals[2]
            additional.evidence[0].locator = 'p3'
            parsed.mission_checkpoint.answer.points.append(additional)
            kwargs['on_progress']()
            raise DomainError('Final review interrupted', 503, 'model_upstream_timeout')
        return {'status': 'checked', 'hints': [], 'question_coverage': 'covered'}

    async def original(settings, work, wire, checkpoint, seconds):
        inspected_originals.extend(ref['quote'] for ref in wire.references.values())

    async def reconcile(*args, **kwargs):
        return {'status': 'checked', 'removed_notices': 0}

    monkeypatch.setattr(research_evidence_pack, 'select_evidence', select)
    monkeypatch.setattr(model, 'complete', complete)
    monkeypatch.setattr(research_final_review, 'finalize', final)
    monkeypatch.setattr(review, 'original_check', original)
    monkeypatch.setattr(research_final_coverage, 'reconcile', reconcile)
    schema = mission_schema(Briefing)
    with pytest.raises(DomainError, match='Selection interrupted'):
        await gateway.complete(service, work, '', schema, 90)
    saved = json.loads(json.dumps(work[KEY]))
    assert saved['stage'] == 'preparing' and not saved['raw'] and not calls
    assert set(saved['parts']['evidence_selection']) == {'early'}
    assert made_progress({}, completed_work(saved))
    resumed = {**deepcopy(initial), KEY: saved}
    with pytest.raises(DomainError, match='Final review interrupted'):
        await gateway.complete(service, resumed, '', schema, 90)
    assert resumed[KEY]['stage'] == 'finalizing' and len(calls) == 1
    resumed = {**deepcopy(initial), KEY: json.loads(json.dumps(resumed[KEY]))}
    result = schema.model_validate_json(await gateway.complete(service, resumed, '', schema, 90))
    assert checked_batches == ['early', 'later'] and len(calls) == 1
    assert inspected_originals == originals
    assert result.mission_checkpoint.answer.points[0].evidence[0].quote == originals[1]
    assert result.mission_checkpoint.answer.points[0].evidence[0].locator == 'p2'
    assert result.mission_checkpoint.answer.points[1].evidence[0].quote == originals[2]
    assert resumed['input'] == initial['input']
    assert resumed[KEY]['raw'] not in json.dumps(resumed['model_route'])


@pytest.mark.asyncio
@pytest.mark.parametrize('oversized_feedback', [False, True])
async def test_unsupplied_draft_reference_is_rejected_again_after_failed_format_repair_resume(monkeypatch, oversized_feedback):
    from helvetic_lens import research_evidence_pack, research_final_coverage, research_final_review

    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'Who operates the registry?', 'research_mission': {},
        'sources': [{'id': 'a' * 36, 'kind': 'public_source', 'excerpts': [
            {'passage': 'p1', 'text': 'North Reach owns the registry.'},
            {'passage': 'p2', 'text': 'South Reach operates the registry.'}]}]}}
    initial, calls = deepcopy(work), []

    async def select(service, wire, *args, **kwargs):
        return {2: wire.references[2]}

    async def complete(system, text, **options):
        data = json.loads(text)
        calls.append(data)
        citation = options['response_schema']['$defs']['AssessmentEvidence']['properties']['citation_ref']
        assert citation['enum'] == [2]
        assert research_evidence_pack.request_characters(system, data, options['response_schema']) <= settings.apertus_context_chars
        if len(calls) > 1:
            if oversized_feedback:
                assert data == calls[0], 'The bounded retry preserves all selected originals and omits the malformed draft'
            else:
                assert 'previous_invalid_response' in data
        ref = 1 if len(calls) <= 2 else 2
        return json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'points': [
            {'statement': 'South Reach operates the registry.',
                'evidence': [{'citation_ref': ref, 'role': 'support'}]}]}, 'next_action': 'finish',
            **({'unexpected_field': 'Malformed generated content. ' * 800} if oversized_feedback and ref == 1 else {})})

    async def final(service, work, wire, parsed, *args, **kwargs):
        assert parsed.mission_checkpoint.answer.points[0].evidence[0].locator == 'p2'
        assert len(wire.references) == 2
        return {'status': 'checked', 'hints': [], 'question_coverage': 'covered'}

    async def original(*args, **kwargs):
        return None

    async def reconcile(*args, **kwargs):
        return {'status': 'checked', 'removed_notices': 0}

    monkeypatch.setattr(research_evidence_pack, 'select_evidence', select)
    monkeypatch.setattr(model, 'complete', complete)
    monkeypatch.setattr(research_final_review, 'finalize', final)
    monkeypatch.setattr(review, 'original_check', original)
    monkeypatch.setattr(research_final_coverage, 'reconcile', reconcile)
    service, schema = SimpleNamespace(settings=settings, model_client=model), mission_schema(Briefing)
    with pytest.raises(ValueError):
        await gateway.complete(service, work, '', schema, 90)
    assert len(calls) == 2 and work[KEY]['stage'] == 'draft'
    resumed = {**initial, KEY: json.loads(json.dumps(work[KEY]))}
    result = schema.model_validate_json(await gateway.complete(service, resumed, '', schema, 90))
    assert len(calls) == 3, 'Resume must repair the saved invalid draft, never accept its unsupplied reference'
    assert result.mission_checkpoint.answer.points[0].evidence[0].quote == 'South Reach operates the registry.'
    assert resumed['model_route']['format_repair_mode'] == ('fresh_bounded_draft' if oversized_feedback else 'validation_feedback')


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
    @atomic_pack_model
    async def complete(system, user, **kwargs):
        value = json.loads(user)
        if 'requested_part' not in value:
            calls.append('draft_or_review')
            return raw
        number = int(value['correction_target']['previous_statement'].split()[1])
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
    assert calls == ['draft_or_review', 'select1', 1, 'select2', 2, 'select3', 3, 3]
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
    calls = []
    @atomic_pack_model
    async def complete(system, user, **kwargs):
        value = json.loads(user)
        if 'requested_part' in value:
            assert value['requested_part'] == 'Distinguish adoption from publication.'
            selection = 'citation_refs' in kwargs['response_schema']['properties']
            calls.append('select' if selection else 'correction')
            if selection:
                return selection_json([1], kwargs)
            return json.dumps({**point, 'remaining_gap': '', 'replace_point': 'P0'})
        calls.append('draft_or_review')
        return json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'points': [point]},
            'next_action': 'finish'})
    async def audit(*args, coverage_only=False, **kwargs):
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
    assert answer.points[0].statement == point['statement'] and not gateway.answer_quantity_errors(answer)
    assert all('2003' not in value.statement for value in answer.points)
    assert calls == ['draft_or_review', 'select', 'correction']


@pytest.mark.parametrize('change', ['source', 'prompt', 'schema', 'model', 'endpoint', 'temperature', 'tamper'])
@pytest.mark.parametrize('stage', ['reviewed', 'finalizing'])
def test_changed_generation_or_evidence_cannot_reuse_a_saved_proposal(change, stage):
    settings = Settings(_env_file=None)
    work = {}
    args = ['original prompt', 'review prompt', {'type': 'object'}, 'original evidence', {'max_output_tokens': 4096}]
    DraftCheckpoint(work, settings, *args).save(stage, 'PRIVATE CANDIDATE', [], {})
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
@pytest.mark.parametrize('invalid_first', [False, True])
async def test_one_invalid_point_cannot_rewrite_or_shift_valid_siblings(monkeypatch, invalid_first):
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'When was it adopted? When was it published? When did it expire?',
        'research_mission': {}, 'sources': [{'id': 'a' * 36, 'kind': 'public_source',
            'excerpts': [{'passage': 'p1', 'text': 'Adopted in 2001.'},
                {'passage': 'p2', 'text': 'Published in 2003.'}, {'passage': 'p3', 'text': 'Expiry is not specified.'}]}]}}
    valid = [
        {'statement': 'It was adopted in 2001.', 'evidence': [{'citation_ref': 1, 'role': 'support'}]},
        {'statement': 'It was published in 2003.', 'evidence': [{'citation_ref': 2, 'role': 'support'}]}]
    invalid = {'statement': 'It expired in 2015.', 'evidence': [{'citation_ref': 3, 'role': 'support'}]}
    points = [invalid, *valid] if invalid_first else [*valid, invalid]
    calls = []
    @atomic_pack_model
    async def complete(system, user, **kwargs):
        value = json.loads(user)
        calls.append(value)
        if 'previous_proposal' in value:
            assert value['previous_proposal']['statement'] == invalid['statement']
            assert not {'points', 'requested_part', 'remaining_gap'} & value.keys()
            assert kwargs['response_schema']['properties']['remaining_gap']['enum'] == ['']
            return json.dumps(value['previous_proposal'])
        if 'requested_part' in value:
            assert value['requested_part'] == work['input']['original_question']
            assert value['correction_target']['previous_statement'] == invalid['statement']
            assert value['correction_target']['validation_errors']
            refs = [ref for source in value['sources'] for ref in source['passages']]
            ref = next(ref for ref in refs if ref['text'] == 'Expiry is not specified.')
            if 'citation_refs' in kwargs['response_schema']['properties']:
                return selection_json([ref['citation_ref']], kwargs)
            return json.dumps({**invalid, 'remaining_gap': '',
                'evidence': [{'citation_ref': ref['citation_ref'], 'role': 'support'}]})
        assert 'previous_invalid_response' not in value, 'Valid siblings must never be regenerated'
        return json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'points': points},
            'next_action': 'finish'})
    async def audit(*args, **kwargs):
        return {'status': 'partial', 'question_coverage': None, 'hints': [], 'decisions': []}
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
    assert [point.statement for point in answer.points] == [point['statement'] for point in valid]
    assert [point.evidence[0].quote for point in answer.points] == ['Adopted in 2001.', 'Published in 2003.']
    assert answer.status == 'partial' and not gateway.answer_quantity_errors(answer)
    assert 'A finding could not be validated against its cited originals: It expired in 2015.' in answer.limitations
    retained = json.loads(work[KEY]['raw'])['answer']
    assert retained['points'] == valid and 'responses' not in retained
    assert len([call for call in calls if not {'requested_part', 'previous_proposal'} & call.keys()]) == 1
    assert len(calls) == 4  # One draft, selected correction, and one bounded invalid-precision retry.


@pytest.mark.asyncio
@pytest.mark.parametrize('coverage', ['missing', 'unavailable_after_repair', 'complete'])
async def test_missing_requested_distinction_is_repaired_without_rewriting_other_points(monkeypatch, coverage):
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'When was it adopted? Distinguish adoption from publication.',
        'research_mission': {}, 'sources': [{'id': 'a' * 36, 'kind': 'public_source',
            'excerpts': [{'passage': 'p1', 'text': 'Adopted in 2001.'}, {'passage': 'p2', 'text': 'Published in 2003.'}]}]}}
    point = {'statement': 'It was adopted in 2001.', 'evidence': [{'citation_ref': 1, 'role': 'support'}]}
    distinction = {'statement': 'It was adopted in 2001 and published in 2003.',
        'evidence': [{'citation_ref': ref, 'role': 'support'} for ref in (1, 2)]}
    calls = []
    @atomic_pack_model
    async def complete(system, user, **kwargs):
        value = json.loads(user)
        if 'requested_part' in value:
            assert coverage != 'complete', 'A complete shared draft must not invoke any request-pack writer'
            assert value['requested_part'] == 'Distinguish adoption from publication.'
            if 'retained_answer' in value and isinstance(value['retained_answer']['P0'], str):
                assert value['retained_answer']['P0'] == point['statement']
            else:
                assert value['review_feedback']['already_answered'][0]['statement'] == point['statement']
            refs = [ref for source in value['sources'] for ref in source['passages']]
            selection = 'citation_refs' in kwargs['response_schema']['properties']
            calls.append('select' if selection else 'correction')
            if selection:
                return selection_json([ref['citation_ref'] for ref in refs], kwargs)
            return json.dumps({**distinction, 'remaining_gap': '', 'replace_point': 'P0',
                'evidence': [{'citation_ref': ref['citation_ref'], 'role': 'support'} for ref in refs]})
        calls.append('draft_or_review')
        return json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [],
            'points': [point, distinction] if coverage == 'complete' else [point]}, 'next_action': 'finish'})
    async def audit(settings, work, wire, answer, seconds, *, coverage_only=False, **kwargs):
        missing = not any('2003' in point.statement for point in answer.points)
        known = missing or coverage != 'unavailable_after_repair'
        return {'status': 'checked' if known else 'partial',
            'question_coverage': 'missing' if missing else 'covered' if known else None,
            'hints': [{'user_request': 'Distinguish adoption from publication.', 'review_signal': 'requested_part_missing'}]
                if missing else [], 'decisions': []}
    async def original(*args, **kwargs):
        return None
    monkeypatch.setattr(model, 'complete', complete)
    monkeypatch.setattr(review, 'audit', audit)
    monkeypatch.setattr(review, 'original_check', original)
    schema = mission_schema(Briefing)
    result = schema.model_validate_json(await gateway.complete(
        SimpleNamespace(settings=settings, model_client=model), work, '', schema, 90))
    answer = result.mission_checkpoint.answer
    assert [point.statement for point in answer.points] == ([point['statement'], distinction['statement']]
        if coverage == 'complete' else [distinction['statement']])
    assert answer.points[0].evidence[0].quote == 'Adopted in 2001.'
    assert not gateway.answer_quantity_errors(answer)
    assert answer.status == ('partial' if coverage == 'unavailable_after_repair' else 'possible_answer')
    if coverage == 'unavailable_after_repair':
        assert answer.limitations and work['model_route']['answer_review']['final_coverage']['question_coverage'] is None
    else:
        assert not answer.limitations
    assert calls == ['draft_or_review'] + ([] if coverage == 'complete' else ['select', 'correction'])


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
async def test_source_pack_recovers_a_named_omission_without_claiming_unknown_review_is_covered(monkeypatch, available):
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'Who operates the station? When did it enter service? Start with https://example.org/registry',
        'research_mission': {}, 'sources': [{'id': 'a' * 36, 'kind': 'public_source',
            'title': 'Station registry', 'url': 'https://example.org/registry', 'excerpts': [
                {'passage': 'p1', 'text': 'Operator: North Reach Survey.'},
                {'passage': 'p2', 'text': 'The station entered service in 2019.'}]}]}}
    calls = []
    @atomic_pack_model
    async def complete(system, user, **kwargs):
        value = json.loads(user)
        calls.append(value)
        if 'requested_part' in value:
            assert value['requested_part'] == 'When did it enter service?'
            assert value['sources'][0]['title'] == 'Station registry'
            refs = [p for source in value['sources'] for p in source['passages'] if '2019' in p['text']]
            if 'citation_refs' in kwargs['response_schema']['properties']:
                return selection_json([refs[0]['citation_ref']], kwargs)
            return json.dumps({'statement': 'The station entered service in 2019.', 'remaining_gap': '', 'replace_point': 'new',
                'evidence': [{'citation_ref': refs[0]['citation_ref'], 'role': 'support'}]})
        assert 'reason' not in kwargs['response_schema']['properties']
        return json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'points': [
            {'statement': 'North Reach Survey operates the station.',
                'evidence': [{'citation_ref': 1, 'role': 'support'}]}]}, 'next_action': 'finish'})
    async def audit(settings, work, wire, answer, seconds, **kwargs):
        missing = not any('2019' in point.statement for point in answer.points)
        known = missing or available
        return {'status': 'checked' if known else 'partial', 'hints': [
            {'user_request': 'When did it enter service?', 'review_signal': 'requested_part_missing'}] if missing else [],
            'decisions': [], 'question_coverage': 'missing' if missing else 'covered' if known else None}
    async def original(*args, **kwargs):
        return None
    monkeypatch.setattr(model, 'complete', complete)
    monkeypatch.setattr(review, 'audit', audit)
    monkeypatch.setattr(review, 'original_check', original)
    schema = mission_schema(Briefing)
    result = schema.model_validate_json(await gateway.complete(
        SimpleNamespace(settings=settings, model_client=model), work, '', schema, 90))
    answer = result.mission_checkpoint.answer
    assert [point.statement for point in answer.points] == [
        'North Reach Survey operates the station.', 'The station entered service in 2019.']
    assert answer.status == ('possible_answer' if available else 'partial')
    if available:
        assert not answer.limitations
    else:
        from helvetic_lens.research_final_review import REVIEW_NOTICE
        assert answer.limitations == [REVIEW_NOTICE]
        assert work['model_route']['answer_review']['final_coverage']['question_coverage'] is None
        assert not any('When did it enter service?' in gap for gap in answer.limitations), 'A stale draft omission cannot erase the cited correction'
    assert 'Start with' not in str(answer.limitations)
    assert len(calls) == 3
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


@pytest.mark.parametrize('choice', ['covered', 'missing'])
def test_completed_request_coverage_is_progress_but_unavailable_retry_is_not(choice):
    receipt = {'choice': choice, 'input_fingerprint': 'answer-and-originals', 'policy_fingerprint': 'coverage-policy'}
    checkpoint = {'parts': {'delivered_coverage': {'request': receipt}}}
    progress = completed_work(checkpoint)
    assert made_progress({}, progress)
    checkpoint['parts']['delivered_coverage'].update({
        'failed': {**receipt, 'choice': 'unavailable'}, 'unbound': {'choice': 'covered'}})
    assert completed_work(checkpoint) == progress
    assert not made_progress(progress, completed_work(checkpoint))
