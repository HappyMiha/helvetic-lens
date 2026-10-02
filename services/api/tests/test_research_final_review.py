"""Final delivery cannot inherit a factual check of a different earlier draft."""
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
from helvetic_lens.decision_engines import Decision, DecisionUnavailable
from helvetic_lens.product_exploration import Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_synthesis_resume import KEY


def review_json(data, *, gap=False):
    """A complete synthetic reviewer response with an explicit overall verdict."""
    clause = data['clauses'][0]
    data.setdefault('overall', {key: clause[key] for key in ('verdict', 'reason', 'citation_refs')})
    if gap:
        data.setdefault('gap_status', 'unresolved')
    from helvetic_lens.research_review_witnesses import assertion_clauses
    judgments = [
        {key: value for key, value in clause.items() if key != 'claim_as_written'}
        for clause in data['clauses'] for _ in assertion_clauses(clause['claim_as_written'])]
    data['clauses'] = {f'S{i}': value for i, value in enumerate(judgments)}
    return json.dumps(data)


@pytest.mark.asyncio
@pytest.mark.parametrize('correction', ['correct', 'unresolved', 'unchanged', 'rate_limit', 'role_only', 'paraphrase', 'missing_concern_check', 'malformed_review', 'uncited_objection'])
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
    paraphrase = 'The old rule from 2001 was reconfirmed in 2003.'
    calls, checks, failed = [], [], [False]

    def point(index, statement=None):
        return {'statement': statement or good[index], 'evidence': [{'citation_ref': index+1, 'role': 'support'}]}

    @atomic_pack_model
    async def complete(system, text, **options):
        value = json.loads(text)
        calls.append(value)
        if 'final_claims_and_gaps' in value:
            checks.extend(item['statement'] for item in value['final_claims_and_gaps'].values() if 'statement' in item)
            if correction == 'role_only' and failed[0]:
                return '{}'
            pending = correction in {'malformed_review', 'uncited_objection'} and not failed[0] and any(
                item.get('statement') == bad for item in value['final_claims_and_gaps'].values())
            if pending:
                failed[0] = True
                if correction == 'malformed_review':
                    return '{"clauses": ['
            def rejected(item):
                return item.get('statement') == bad or (item.get('statement') == paraphrase and bool(value.get('prior_review_concerns')))
            data = {'clauses': [{'claim_as_written': item.get('statement', item.get('gap')),
                'verdict': 'contradicted' if rejected(item) else 'supported',
                'reason': 'The original says replaced, not ratified again.' if rejected(item) else '',
                'citation_refs': value.get('selected_citation_refs', [])}
                for key, item in value['final_claims_and_gaps'].items()]}
            if value.get('prior_review_concerns') and correction != 'missing_concern_check':
                data['concern_checks'] = [{'id': key, 'outcome': 'remains' if any(
                    rejected(item) for item in value['final_claims_and_gaps'].values()) else 'resolved',
                    'reason': 'The original says replaced, not ratified again.', 'citation_refs': value['selected_citation_refs']} for key in value['prior_review_concerns']['concerns']]
            if pending:
                data['clauses'][0]['citation_refs'] = []
            return review_json(data, gap=next(iter(value['final_claims_and_gaps'])).startswith('L'))
        if 'requested_part' not in value:
            return json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'responses': {
                f'r{i+1}': {'disposition': 'answered', 'points': [point(i)], 'remaining_gap': ''} for i in (0, 1)}},
                'next_action': 'finish'})
        index = 0 if value['requested_part'].startswith('Who') else 1
        if 'citation_refs' in options['response_schema']['properties']:
            return selection_json([index+1], options)
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
            if correction == 'paraphrase':
                statement = paraphrase
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
    if correction in {'rate_limit', 'malformed_review', 'uncited_objection'}:
        with pytest.raises(DomainError):
            await gateway.complete(service, work, '', schema, 90)
        assert 'final_reviews' in work[KEY]['parts']
        before = len(checks)
        work = {**initial, KEY: json.loads(json.dumps(work[KEY]))}
        result = await gateway.complete(service, work, '', schema, 90)
        assert checks[before:] == (good[1:] if correction == 'rate_limit' else [bad, good[1]]), 'Unchanged exact claim reviews must not be bought again'
    elif correction in {'role_only', 'missing_concern_check'}:
        with pytest.raises(DomainError) as failure:
            await gateway.complete(service, work, '', schema, 90)
        assert failure.value.code == 'research_review_incomplete'
        from helvetic_lens.research_model_transport import EvidenceWire
        result = EvidenceWire(work, schema, '').decode(work[KEY]['raw'])
    else:
        result = await gateway.complete(service, work, '', schema, 90)
    answer = schema.model_validate_json(result).mission_checkpoint.answer
    assert answer.points[0].statement == good[0]
    assert bad in checks, 'The bad final rewrite was absent from the earlier draft'
    assert all(p.statement not in {bad, paraphrase} for p in answer.points)
    assert not gateway.answer_quantity_errors(answer)
    if correction in {'correct', 'rate_limit', 'malformed_review', 'uncited_objection'}:
        assert [p.statement for p in answer.points] == good
        assert answer.status == 'possible_answer' and answer.limitations == []
    elif correction == 'missing_concern_check':
        assert [p.statement for p in answer.points] == good  # Private pending draft, never returned by gateway.
        assert answer.status == 'partial' and any('review was unavailable' in gap for gap in answer.limitations)
    else:
        assert len(answer.points) == 1 and answer.status == 'partial'
        assert any('Distinguish the old rule' in gap for gap in answer.limitations)
    assert len([value for value in calls if 'requested_part' not in value and 'final_claims_and_gaps' not in value]) == 2
    assert 'previous_statements' not in json.dumps(work['model_route'])


@pytest.mark.asyncio
async def test_single_question_resumes_corrected_private_point_after_incomplete_concern_review(monkeypatch):
    from helvetic_lens.research_model_transport import EvidenceWire

    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    service = SimpleNamespace(settings=settings, model_client=model)
    source = 'The old rule was replaced in 2042, not reaffirmed.'
    wrong = 'The old rule was reaffirmed in 2042.'
    right = 'The old rule was replaced in 2042.'
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'What happened to the old rule?', 'research_mission': {},
        'sources': [{'id': 'a' * 36, 'kind': 'public_source', 'url': 'https://example.org/rule',
            'excerpts': [{'passage': 'p1', 'text': source}]}]}}
    initial, calls = deepcopy(work), []
    schema = mission_schema(Briefing)
    assert EvidenceWire(work, schema, '').request_keys == {}

    @atomic_pack_model
    async def complete(system, text, **options):
        value = json.loads(text)
        if 'final_claims_and_gaps' in value:
            statement = next(iter(value['final_claims_and_gaps'].values()))['statement']
            calls.append(statement)
            if statement == right and calls.count(right) == 1:
                return '{"clauses": ['
            data = {'clauses': [{'claim_as_written': statement, 'verdict': 'contradicted' if statement == wrong else 'supported',
                'reason': '', 'citation_refs': [1]}]}
            if value.get('prior_review_concerns'):
                data['concern_checks'] = [{'id': key, 'outcome': 'resolved', 'reason': '', 'citation_refs': [1]}
                    for key in value['prior_review_concerns']['concerns']]
            return review_json(data)
        if 'requested_part' in value:
            if 'citation_refs' in options['response_schema']['properties']:
                calls.append('select')
                return selection_json([1], options)
            calls.append('repair')
            return json.dumps({'statement': right, 'remaining_gap': '', 'evidence': [{'citation_ref': 1, 'role': 'support'}]})
        calls.append('draft')
        return json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [],
            'points': [{'statement': wrong, 'evidence': [{'citation_ref': 1, 'role': 'support'}]}]}, 'next_action': 'finish'})

    async def audit(*args, **kwargs):
        return {'status': 'checked', 'question_coverage': 'covered', 'hints': [], 'decisions': []}

    async def original(*args, **kwargs):
        return None

    monkeypatch.setattr(model, 'complete', complete)
    monkeypatch.setattr(review, 'audit', audit)
    monkeypatch.setattr(review, 'original_check', original)
    with pytest.raises(DomainError) as failure:
        await gateway.complete(service, work, '', schema, 90)
    assert failure.value.code == 'research_review_incomplete'
    retained = json.loads(json.dumps(work[KEY]))
    private = schema.model_validate_json(EvidenceWire(work, schema, '').decode(retained['raw']))
    assert [point.statement for point in private.mission_checkpoint.answer.points] == [right]
    before = len(calls)
    resumed = {**initial, KEY: retained}
    result = schema.model_validate_json(await gateway.complete(service, resumed, '', schema, 90))
    assert calls[before:] == [right], 'Only the unfinished concern check should be repeated'
    assert [point.statement for point in result.mission_checkpoint.answer.points] == [right]
    assert result.mission_checkpoint.answer.limitations == []


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
        @atomic_pack_model
        async def complete(self, system, text, **options):
            value = json.loads(text)
            if 'final_claims_and_gaps' in value:
                if corrected[0]:
                    return '{}'
                return review_json({'clauses': [{'claim_as_written': item.get('statement', item.get('gap')),
                    'verdict': 'contradicted' if 'gap' in item else 'supported',
                    'reason': 'The original explicitly supplies the opening date.' if 'gap' in item else '', 'citation_refs': [1]}
                    for key, item in value['final_claims_and_gaps'].items()]},
                    gap=next(iter(value['final_claims_and_gaps'])).startswith('L'))
            if 'citation_refs' in options['response_schema']['properties']:
                return selection_json([1], options)
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
        @atomic_pack_model
        async def complete(self, system, text, **options):
            assert 'question' not in json.loads(text)
            return json.dumps({'overall': {'verdict': 'supported', 'reason': '', 'citation_refs': []},
                'clauses': {'unrelated': {'verdict': 'supported', 'reason': '', 'citation_refs': []}}, 'gap_status': 'unresolved'})
    retained = {}
    result = await reasoned_review(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()),
        wire, answer, 60, checkpoints=retained)
    assert result['status'] == 'partial' and result['hints'] == [] and retained == {}


@pytest.mark.asyncio
async def test_only_host_registered_workflow_notices_are_exempt_from_factual_gap_review():
    from helvetic_lens.product_exploration import AssessmentOutcome
    from helvetic_lens.research_final_review import reasoned_review
    gap = 'A cited answer could not be validated for: Compare the definitions.'
    answer = AssessmentOutcome(status='not_found', points=[], limitations=[gap])
    wire = SimpleNamespace(input={}, references={}, workflow_gaps={gap})
    class Model:
        calls = 0
        @atomic_pack_model
        async def complete(self, system, text, **options):
            self.calls += 1
            return '{}'
    model = Model()
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=model)
    result = await reasoned_review(service, wire, answer, 60)
    assert result['status'] == 'checked' and model.calls == 0
    wire.workflow_gaps.clear()  # The same model-authored text has no exemption.
    result = await reasoned_review(service, wire, answer, 60)
    assert result['status'] == 'partial' and model.calls == 1


@pytest.mark.asyncio
async def test_private_resume_preserves_exact_host_notice_provenance(monkeypatch):
    from helvetic_lens.product_exploration import AssessmentOutcome
    from helvetic_lens.research_final_review import finalize
    from helvetic_lens.research_synthesis_resume import DraftCheckpoint

    host_gap = 'A cited answer could not be validated for: Compare the definitions.'
    model_gap = host_gap + ' The replacement date is absent.'
    ref = {'source_id': 'a', 'locator': 'p1', 'quote': 'North Reach Survey operates the registry.', 'role': 'support'}
    answer = AssessmentOutcome(status='partial', points=[{'statement': ref['quote'], 'evidence': [ref]}],
        limitations=[host_gap, model_gap])
    wire = SimpleNamespace(input={}, references={1: ref}, point_requests=[], request_keys={}, response_slots={},
        workflow_gaps={host_gap, 'An obsolete workflow notice.'})
    parsed = SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer))
    settings, work, assertions = Settings(_env_file=None), {}, []
    args = (settings, 'system', 'review', {}, 'exact input', {})
    checkpoint = DraftCheckpoint(work, *args)

    async def covered(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': [], 'question_coverage': None}

    class Model:
        interrupted = False
        @atomic_pack_model
        async def complete(self, system, text, **options):
            item = next(iter(json.loads(text)['final_claims_and_gaps'].values()))
            assertion = item.get('statement', item.get('gap'))
            assertions.append(assertion)
            if assertion == model_gap and not self.interrupted:
                self.interrupted = True
                raise DomainError('Synthetic temporary rate limit', 503, 'model_rate_limited')
            return review_json({'clauses': [{'claim_as_written': assertion, 'verdict': 'supported', 'reason': '', 'citation_refs': [1]}]}, gap='gap' in item)

    monkeypatch.setattr(review, 'audit', covered)
    service = SimpleNamespace(settings=settings, model_client=Model())
    def retain():
        checkpoint.save('reviewed', parsed.mission_checkpoint.answer.model_dump_json(), [], {})

    with pytest.raises(DomainError, match='Synthetic temporary'):
        await finalize(service, work, wire, parsed, 60, checkpoints=checkpoint.parts, on_progress=retain)
    restored_work = json.loads(json.dumps(work))
    checkpoint = DraftCheckpoint(restored_work, *args)
    parsed.mission_checkpoint.answer = AssessmentOutcome.model_validate_json(checkpoint.value['raw'])
    del wire.workflow_gaps
    result = await finalize(service, restored_work, wire, parsed, 60, checkpoints=checkpoint.parts, on_progress=retain)
    assert result['status'] == 'checked'
    assert assertions == [ref['quote'], model_gap, model_gap]
    assert parsed.mission_checkpoint.answer.limitations == [host_gap, model_gap]
    assert checkpoint.parts['workflow_gaps'] == [host_gap]


@pytest.mark.asyncio
@pytest.mark.parametrize('missing_direct_support', [False, True, None])
async def test_final_review_reads_cited_original_context_without_borrowing_other_sources(missing_direct_support):
    from helvetic_lens.product_exploration import AssessmentOutcome
    from helvetic_lens.research_final_review import reasoned_review
    refs = {1: {'source_id': 'a', 'locator': 'p1', 'quote': 'The Council decides to replace the earlier rule.'},
        2: {'source_id': 'a', 'locator': 'p2', 'quote': 'The replacement is defined as follows: the unit equals three pulses.'},
        3: {'source_id': 'b', 'locator': 'p1', 'quote': 'An unrelated actor made a different decision.'}}
    answer = AssessmentOutcome(status='possible_answer', points=[{'statement': 'The Council defined the unit as three pulses.',
        'evidence': [{**refs[2], 'role': 'support'}]}], limitations=[])
    wire = SimpleNamespace(input={}, references=refs)
    class Model:
        @atomic_pack_model
        async def complete(self, system, text, **options):
            value = json.loads(text)
            assert [p['text'] for group in value['source_context'] for p in group['passages']] == [refs[1]['quote'], refs[2]['quote']]
            assert len(value['final_claims_and_gaps']['P0']['passages']) == 1
            return review_json({'clauses': [{'claim_as_written': answer.points[0].statement,
                'citation_refs': [1, 2] if missing_direct_support else [] if missing_direct_support is None else [2],
                'verdict': 'supported', 'reason': 'The original identifies the subject of this definition.'}]})
    result = await reasoned_review(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()), wire, answer, 60)
    assert result['status'] == ('partial' if missing_direct_support is None else 'checked')
    if missing_direct_support:
        assert result['hints'][0]['path'] == ['answer', 'points', 0]
        assert result['hints'][0]['review_signal'] == 'not_established'
        assert result['hints'][0]['candidate_windows'] == [{'text': refs[1]['quote']}]
    else:
        assert result['hints'] == []
    assert len(answer.points[0].evidence) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['uncited_negative', 'foreign_reference', 'different_assertion', 'missing_overall', 'duplicate_reference', 'malformed'])
async def test_invalid_negative_is_pending_and_only_its_check_is_repeated(failure):
    from helvetic_lens.product_exploration import AssessmentOutcome
    from helvetic_lens.research_final_review import reasoned_review
    refs = {
        1: {'source_id': 'a', 'locator': 'p1', 'quote': 'The old standard was adopted in 2040 and published in 2041.'},
        2: {'source_id': 'b', 'locator': 'p1', 'quote': 'The digital standard was adopted in 2042 and published in 2044.'},
        3: {'source_id': 'foreign', 'locator': 'p1', 'quote': 'Unrelated evidence must not be borrowed.'},
    }
    answer = AssessmentOutcome(status='possible_answer', points=[{'statement': refs[i]['quote'],
        'evidence': [{**refs[i], 'role': 'support'}]} for i in (1, 2)], limitations=[])
    wire = SimpleNamespace(input={}, references=refs)
    calls = []
    class Model:
        @atomic_pack_model
        async def complete(self, system, text, **options):
            value = json.loads(text)
            key, item = next(iter(value['final_claims_and_gaps'].items()))
            calls.append(key)
            clause = {'claim_as_written': item['statement'], 'verdict': 'supported',
                'reason': '', 'citation_refs': value['selected_citation_refs']}
            if key == 'P1' and calls.count(key) == 1:
                if failure == 'malformed':
                    return '{"clauses": ['
                clause.update(verdict='contradicted', reason='A later authority adopted it in 2050.')
                if failure == 'uncited_negative':
                    clause['citation_refs'] = []
                if failure == 'foreign_reference':
                    clause['citation_refs'] = [3]
                if failure == 'different_assertion':
                    return json.dumps({'overall': {k: clause[k] for k in ('verdict', 'reason', 'citation_refs')},
                        'clauses': {'unrelated': {k: clause[k] for k in ('verdict', 'reason', 'citation_refs')}}})
                if failure == 'missing_overall':
                    return json.dumps({'clauses': [clause]})
                if failure == 'duplicate_reference':
                    clause['citation_refs'] = [2, 2]
            return review_json({'clauses': [clause]})
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    cache = {}
    pending = await reasoned_review(service, wire, answer, 60, checkpoints=cache)
    assert pending['status'] == 'partial' and pending['points_checked'] == 1
    assert [c['item'] for c in pending['pending_checks']] == ['P1']
    assert pending['hints'] == [] and len(cache) == 1
    assert '2050' not in json.dumps(cache)
    complete = await reasoned_review(service, wire, answer, 60, checkpoints=json.loads(json.dumps(cache)))
    assert complete['status'] == 'checked' and complete['pending_checks'] == []
    assert calls == ['P0', 'P1', 'P1']


def test_sentence_registry_preserves_all_literal_text_and_shared_relationships():
    from helvetic_lens.research_review_witnesses import assertion_clauses, invalid_review

    assertion = 'A was adopted; the newer B replaced A. These actions are distinct.'
    registry = assertion_clauses(assertion)
    assert ''.join(registry.values()) == assertion and len(registry) == 2
    assert 'the newer B' in registry['S0']
    many = ' '.join(f'Sentence {i}.' for i in range(12))
    assert len(assertion_clauses(many)) == 8 and ''.join(assertion_clauses(many).values()) == many
    verdict = {'verdict': 'supported', 'citation_refs': [1]}
    data = {'overall': verdict, 'clauses': dict.fromkeys(registry, verdict)}
    assert invalid_review(data, assertion, {}, point=True) is None
    del data['clauses']['S1']
    assert invalid_review(data, assertion, {}, point=True) == 'incomplete_assertion_check'


@pytest.mark.asyncio
@pytest.mark.parametrize('overall', ['supported', 'contradicted', 'not_established'])
async def test_whole_assertion_judgment_checks_relationships_without_requiring_connective_spans(overall):
    from helvetic_lens.product_exploration import AssessmentOutcome
    from helvetic_lens.research_final_review import reasoned_review

    statement = 'A was adopted in 2040, while B replaced A in 2042.'
    ref = {'source_id': 'a', 'locator': 'p1', 'quote': 'A adopted in 2040. B replaced A in 2042.'}
    answer = AssessmentOutcome(status='possible_answer', points=[{'statement': statement,
        'evidence': [{**ref, 'role': 'support'}]}], limitations=[])
    wire = SimpleNamespace(input={}, references={1: ref})
    class Model:
        @atomic_pack_model
        async def complete(self, *args, **kwargs):
            return review_json({'overall': {'verdict': overall, 'reason': '', 'citation_refs': [1]},
                'clauses': [{'claim_as_written': span, 'verdict': 'supported', 'reason': '', 'citation_refs': [1]}
                    for span in (statement,)]})
    result = await reasoned_review(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()), wire, answer, 60)
    assert result['status'] == 'checked' and result['pending_checks'] == []
    if overall == 'supported':
        assert result['hints'] == []
    else:
        assert result['hints'][0]['review_signal'] == overall
        assert statement in result['hints'][0]['instruction']
        assert result['hints'][0]['original_windows'] == [{'text': ref['quote']}]


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['answered', 'outside_request', 'unresolved', 'answer_available'])
async def test_only_real_requested_gaps_remain_without_rewriting_completed_answer(monkeypatch, kind):
    from helvetic_lens.product_exploration import AssessmentOutcome
    from helvetic_lens.research_final_review import finalize

    ref = {'source_id': 'a', 'locator': 'p1', 'quote': 'North Reach Survey operates the registry.'}
    gaps = {'answered': ref['quote'], 'outside_request': 'Economic impacts remain unknown.',
        'unresolved': 'The future operator after the transfer is unspecified.', 'answer_available': 'The operator is unspecified.'}
    question = 'Who operates the registry now and after the planned transfer?'
    answer = AssessmentOutcome(status='partial', points=[{'statement': ref['quote'], 'evidence': [{**ref, 'role': 'support'}]}],
        limitations=[gaps[kind]])
    wire = SimpleNamespace(input={'original_question': question}, references={1: ref}, request_keys={'r1': question},
        point_requests=['r1'], response_slots={'r1': {'disposition': 'unresolved', 'remaining_gap': gaps[kind]}})
    if kind == 'answer_available':
        answer.points, wire.point_requests = [], []
    calls = []
    class Model:
        @atomic_pack_model
        async def complete(self, system, text, **kwargs):
            value = json.loads(text)
            if 'requested_part' in value and kind == 'answer_available':
                if 'citation_refs' in kwargs['response_schema']['properties']:
                    return selection_json([1], kwargs)
                return json.dumps({'statement': ref['quote'], 'remaining_gap': '',
                    'evidence': [{'citation_ref': 1, 'role': 'support'}]})
            assert 'final_claims_and_gaps' in value, 'Do not regenerate a completed independent finding'
            key, item = next(iter(value['final_claims_and_gaps'].items()))
            calls.append(key)
            is_gap = 'gap' in item
            if is_gap:
                assert value['research_question'] == question
                assert bool(value['delivered_points']) == (kind != 'answer_available')
            return review_json({'clauses': [{'claim_as_written': item.get('statement', item.get('gap')),
                'verdict': 'supported', 'reason': '', 'citation_refs': [1]}],
                **({'gap_status': kind} if is_gap else {})}, gap=is_gap)
    async def covered(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': [], 'question_coverage': 'covered'}
    monkeypatch.setattr(review, 'audit', covered)
    result = await finalize(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()),
        {'input': {'original_question': question}}, wire, SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer)), 60)
    assert calls == (['L0', 'P0'] if kind == 'answer_available' else ['P0', 'L0'])
    assert answer.points[0].statement == ref['quote'] and wire.point_requests == ['r1']
    assert answer.limitations == ([gaps[kind]] if kind == 'unresolved' else [])
    assert result['removed_nongaps'] == int(kind in {'answered', 'outside_request'})


@pytest.mark.asyncio
@pytest.mark.parametrize('verdict', ['contradicted', 'not_established'])
async def test_review_feedback_contains_only_literal_claims_and_original_witnesses(verdict):
    from helvetic_lens.product_exploration import AssessmentOutcome
    from helvetic_lens.research_final_review import reasoned_review
    ref = {'source_id': 'a', 'locator': 'p1', 'quote': 'The old rule was repealed in 2042.'}
    answer = AssessmentOutcome(status='possible_answer', points=[{'statement': 'The old rule was reaffirmed in 2042.',
        'evidence': [{**ref, 'role': 'support'}]}], limitations=[])
    class Model:
        @atomic_pack_model
        async def complete(self, system, text, **options):
            return review_json({'clauses': [{'claim_as_written': answer.points[0].statement, 'verdict': verdict,
                'citation_refs': [1] if verdict == 'contradicted' else [], 'reason': 'Invented alternative authority acted in 2050.'}]})
    result = await reasoned_review(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()),
        SimpleNamespace(input={}, references={1: ref}), answer, 60)
    assert result['status'] == 'checked' and result['pending_checks'] == []
    assert result['hints'][0]['review_signal'] == verdict
    assert '2050' not in json.dumps(result['hints'])
    assert result['hints'][0]['original_windows'] == ([{'text': ref['quote']}] if verdict == 'contradicted' else [])


@pytest.mark.asyncio
async def test_deadline_yield_is_distinct_from_an_unresolved_review_concern():
    from helvetic_lens.product_exploration import AssessmentOutcome
    from helvetic_lens.research_final_review import reasoned_review
    ref = {'source_id': 'a', 'locator': 'p1', 'quote': 'A operates the registry.'}
    answer = AssessmentOutcome(status='possible_answer', points=[{'statement': ref['quote'],
        'evidence': [{**ref, 'role': 'support'}]}], limitations=[])
    class Model:
        @atomic_pack_model
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            assert payload['original_question'] == 'Who operates it?'
            assert payload['assertion_clauses'] == {'S0': ref['quote']}
            return review_json({'clauses': [{'claim_as_written': ref['quote'], 'verdict': 'supported',
                'reason': '', 'citation_refs': [1]}], 'concern_checks': [
                    {'id': 'C0', 'outcome': 'cannot_assess', 'reason': '', 'citation_refs': []}]})
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    wire = SimpleNamespace(input={'original_question': 'Who operates it?'}, references={1: ref})
    deferred = await reasoned_review(service, wire, answer, 0)
    assert deferred['pending_checks'] == [{'item': 'P0', 'reason': 'step_deadline'}]
    unresolved = await reasoned_review(service, wire, answer, 60,
        concerns={'P0': {'previous_statements': [], 'issues': ['Recheck the operator.']}})
    assert unresolved['pending_checks'] == [{'item': 'P0', 'reason': 'unresolved_concern'}]


@pytest.mark.asyncio
async def test_inserting_or_reordering_siblings_reuses_exact_checks_but_changed_question_does_not():
    from helvetic_lens.product_exploration import AssessmentOutcome, AssessmentPoint
    from helvetic_lens.research_final_review import reasoned_review
    refs = {i: {'source_id': str(i), 'locator': 'p1', 'quote': name + ' operates the named registry.'}
        for i, name in enumerate(['North Reach Survey', 'Lake Survey', 'Mountain Survey'], 1)}
    points = [AssessmentPoint(statement=ref['quote'], evidence=[{**ref, 'role': 'support'}]) for ref in refs.values()]
    answer = AssessmentOutcome(status='possible_answer', points=points[:2], limitations=[])
    wire = SimpleNamespace(input={'original_question': 'Who operates these registries?'}, references=refs)
    calls, cache = [], {}
    class Model:
        @atomic_pack_model
        async def complete(self, system, text, **options):
            value = json.loads(text)
            item = next(iter(value['final_claims_and_gaps'].values()))
            calls.append(item['statement'])
            verdict = {'verdict': 'supported', 'reason': '', 'citation_refs': value['selected_citation_refs']}
            return json.dumps({'overall': verdict, 'clauses': dict.fromkeys(value['assertion_clauses'], verdict)})
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    assert (await reasoned_review(service, wire, answer, 60, checkpoints=cache))['status'] == 'checked'
    answer.points = list(reversed(answer.points))
    await reasoned_review(service, wire, answer, 60, checkpoints=cache)
    assert len(calls) == 2
    answer.points.insert(0, points[2])
    await reasoned_review(service, wire, answer, 60, checkpoints=cache)
    assert len(calls) == 3
    wire.input['original_question'] = 'Who operated those registries before the transfer?'
    await reasoned_review(service, wire, answer, 60, checkpoints=cache)
    assert len(calls) == 6
