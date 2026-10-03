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
            if value.get('prior_review_concerns') and (correction != 'missing_concern_check' or any(
                    item.get('statement') == bad for item in value['final_claims_and_gaps'].values())):
                data['concern_checks'] = [{'id': key, 'outcome': 'remains' if any(
                    rejected(item) for item in value['final_claims_and_gaps'].values()) else 'resolved',
                    'reason': 'The original says replaced, not ratified again.', 'citation_refs': value['selected_citation_refs']} for key in value['prior_review_concerns']['concerns']]
            if pending:
                data['clauses'][0]['citation_refs'] = []
            return review_json(data, gap=next(iter(value['final_claims_and_gaps'])).startswith('L'))
        if 'requested_part' not in value:
            # A single draft contains the defect; correction preserves its sibling.
            return json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [],
                'points': [point(0), point(1, bad)]}, 'next_action': 'finish'})
        index = 1 if value.get('correction_target') else 0 if value['requested_part'].startswith('Who') else 1
        if 'citation_refs' in options['response_schema']['properties']:
            return selection_json([index+1], options)
        statement = good[0] if index == 0 else bad
        if value.get('review_feedback'):
            assert index == 1, 'An independent valid answer must not be regenerated'
            assert value['requested_part'] == work['input']['original_question']
            assert value['correction_target']['previous_statement'] == bad
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
                choice = 'missing' if state['specific_request'].startswith('Distinguish') and len(state['answer_points']) < 2 else 'covered'
            elif 'statement' in state:
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
    assert bad in checks, 'The actual draft must receive an original-bound factual review'
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
        assert any((bad if correction == 'role_only' else 'Distinguish the old rule') in gap for gap in answer.limitations)
    assert len([value for value in calls if 'requested_part' not in value and 'final_claims_and_gaps' not in value]) == 1
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
    monkeypatch.setattr(review, 'audit_points', audit)
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
            choice = ('covered' if state['answer_points'] else 'missing') if 'specific_request' in state else 'supported' if 'statement' in state else 'L0'
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
                'evidence': [{'citation_ref': 1, 'role': 'support'}], 'replace_point': 'new'})
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
    monkeypatch.setattr(review, 'audit_points', unavailable)
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
    monkeypatch.setattr(review, 'audit_points', covered)
    service = SimpleNamespace(settings=settings, model_client=Model())
    def retain():
        checkpoint.save('reviewed', parsed.mission_checkpoint.answer.model_dump_json(), [], {})

    with pytest.raises(DomainError) as failure:
        await finalize(service, work, wire, parsed, 60, checkpoints=checkpoint.parts, on_progress=retain)
    assert failure.value.code == 'model_rate_limited'
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
@pytest.mark.parametrize('target,verdict', [
    ('overall', 'supported'), ('clause', 'supported'), ('overall', 'contradicted'),
    ('clause', 'contradicted'), ('concern', 'resolved'), ('concern', 'remains')])
async def test_compact_review_grammar_cannot_accept_or_cache_a_missing_witness(target, verdict):
    from helvetic_lens.product_exploration import AssessmentOutcome
    from helvetic_lens.research_final_review import reasoned_review

    ref = {'source_id': 'a', 'locator': 'p1', 'quote': 'The registry opened in 2040.'}
    answer = AssessmentOutcome(status='possible_answer', points=[{'statement': ref['quote'],
        'evidence': [{**ref, 'role': 'support'}]}], limitations=[])
    wire = SimpleNamespace(input={}, references={1: ref})
    calls = []

    class Model:
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            calls.append(payload)
            good = {'verdict': 'supported', 'reason': '', 'citation_refs': [1]}
            data = {'overall': deepcopy(good), 'clauses': {'S0': deepcopy(good)},
                'concern_checks': [{'id': 'C0', 'outcome': 'resolved', 'reason': '', 'citation_refs': [1]}]}
            item = data['overall'] if target == 'overall' else data['clauses']['S0'] if target == 'clause' else data['concern_checks'][0]
            item['verdict' if target != 'concern' else 'outcome'] = verdict
            item['citation_refs'] = []
            # Concern witnesses are now enforced in the provider grammar too;
            # the unchanged host fence independently rejects missing witnesses.
            from helvetic_lens.research_model_transport import shape_errors
            from helvetic_lens.research_review_witnesses import invalid_review
            assert bool(shape_errors(data, options['response_schema'], {})) == (target == 'concern')
            assert invalid_review(data, ref['quote'], {'C0': {}}, point=True) == (
                'missing_concern_witness' if target == 'concern' else 'missing_original_witness')
            return json.dumps(data)

    checkpoints = {}
    result = await reasoned_review(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()),
        wire, answer, 60, checkpoints=checkpoints,
        concerns={'P0': {'previous_statements': [], 'issues': [{'instruction': 'Verify the date.'}]}})
    assert len(calls) == 1
    assert result['status'] == 'partial' and not result['positive_witnesses']
    assert [hint['review_signal'] for hint in result['hints']] == ['review_unavailable']
    assert result['pending_checks'] == [{'item': 'P0',
        'reason': 'invalid_response' if target == 'concern' else 'missing_original_witness'}]
    assert not checkpoints


@pytest.mark.parametrize('point', [True, False])
def test_compact_review_grammar_cannot_offer_impossible_empty_context_verdicts(point):
    from helvetic_lens.research_model_transport import shape_errors
    from helvetic_lens.research_review_witnesses import review_schema

    schema = review_schema('A remains unknown.', {}, {'C0': {}}, point=point)
    verdicts = schema['properties']['overall']['properties']['verdict']['enum']
    assert verdicts == (['not_established'] if point else ['supported', 'not_established'])
    judgment = {'verdict': 'contradicted', 'reason': '', 'citation_refs': []}
    data = {'overall': judgment, 'clauses': {'S0': judgment},
        'concern_checks': [{'id': 'C0', 'outcome': 'resolved', 'reason': '', 'citation_refs': []}],
        **({} if point else {'gap_status': 'unresolved'})}
    assert shape_errors(data, schema, {})


@pytest.mark.parametrize('point,verdict', [(False, 'supported'), (False, 'not_established'), (True, 'not_established')])
def test_compact_review_preserves_valid_witness_free_gap_and_unresolved_concern(point, verdict):
    from helvetic_lens.research_model_transport import shape_errors
    from helvetic_lens.research_review_witnesses import invalid_review, review_schema

    assertion = 'A remains unknown.'
    concerns = {'C0': {}}
    judgment = {'verdict': verdict, 'reason': '', 'citation_refs': []}
    data = {'overall': judgment, 'clauses': {'S0': judgment},
        'concern_checks': [{'id': 'C0', 'outcome': 'cannot_assess', 'reason': '', 'citation_refs': []}],
        **({} if point else {'gap_status': 'unresolved'})}
    assert not shape_errors(data, review_schema(assertion, {}, concerns, point=point), {})
    assert invalid_review(data, assertion, concerns, point=point) is None


@pytest.mark.parametrize('metadata', [False, True])
@pytest.mark.parametrize('outcome,witnesses,accepted', [
    ('resolved', [], False), ('resolved', [1], True), ('remains', [], False),
    ('remains', [1], True), ('cannot_assess', [], True), ('cannot_assess', [1], True)])
def test_conditional_concern_grammar_matches_existing_host_witness_contract(metadata, outcome, witnesses, accepted):
    from helvetic_lens.research_final_review import scoped_review_schema
    from helvetic_lens.research_model_transport import shape_errors
    from helvetic_lens.research_review_witnesses import invalid_review

    assertion = 'The current scope needs verification.'
    refs = {1: {'source_id': 'report', 'locator': 'p1', 'quote': 'The report identifies the current scope.'}}
    wire = SimpleNamespace(references=refs, reference_uses={1: 'reference_metadata'} if metadata else {})
    concerns = {'C0': {}}
    schema = scoped_review_schema(wire, assertion, refs, concerns, point=True)
    variants = schema['properties']['concern_checks']['items']['anyOf']
    assert len(variants) == 2
    assert [variant['properties']['citation_refs']['minItems'] for variant in variants] == [1, 0]
    assert all(('assertion_scope' in variant['required']) == metadata for variant in variants)
    judgment = {'verdict': 'not_established', 'reason': '', 'citation_refs': [],
        **({'assertion_scope': 'reference_metadata'} if metadata else {})}
    item = {'id': 'C0', 'outcome': outcome, 'reason': '', 'citation_refs': witnesses,
        **({'assertion_scope': 'reference_metadata'} if metadata else {})}
    data = {'overall': deepcopy(judgment), 'clauses': {'S0': deepcopy(judgment)}, 'concern_checks': [item]}
    assert (not shape_errors(data, schema, {})) == accepted
    assert (invalid_review(data, assertion, concerns, point=True) is None) == accepted
    if metadata:
        del item['assertion_scope']
        assert shape_errors(data, schema, {}), 'Every alternative must retain the source-use boundary'


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
                    'evidence': [{'citation_ref': 1, 'role': 'support'}], 'replace_point': 'new'})
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
    monkeypatch.setattr(review, 'audit_points', covered)
    result = await finalize(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()),
        {'input': {'original_question': question}}, wire, SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer)), 60)
    assert calls == (['L0', 'P0'] if kind == 'answer_available' else ['P0', 'L0'])
    assert answer.points[0].statement == ref['quote'] and wire.point_requests == ['r1']
    assert answer.limitations == ([gaps[kind]] if kind == 'unresolved' else [])
    assert result['removed_nongaps'] == int(kind in {'answered', 'outside_request'})


@pytest.mark.asyncio
@pytest.mark.parametrize('verdict', ['contradicted', 'not_established'])
async def test_review_feedback_separates_fallible_comments_from_original_evidence(verdict):
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
    hint = result['hints'][0]
    assert '2050' not in hint['instruction']
    assert '2050' not in json.dumps(hint['original_windows'])
    if verdict == 'contradicted':
        assert hint['reviewer_notes'][0]['comment'] == 'Invented alternative authority acted in 2050.'
        assert hint['reviewer_notes'][0]['originals'] == [ref]
        assert 'Fallible reviewer objection' in hint['reviewer_notes'][0]['basis']
    else:
        assert 'reviewer_notes' not in hint, 'Unanchored commentary must not become a correction instruction'
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
        concerns={'P0': {'previous_statements': [], 'issues': [
            {'instruction': 'Recheck the operator.', 'original_text': [ref['quote']]}]}})
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


@pytest.mark.asyncio
async def test_semantic_point_corrections_preserve_shared_slot_siblings_and_gaps_across_retry(monkeypatch):
    from helvetic_lens.product_exploration import AssessmentOutcome
    from helvetic_lens.research_final_review import finalize

    question = 'Which changes were observed, who keeps the records, and what is still unknown?'
    good = 'North Survey operates the registry.'
    bad = ['Northbank closures increased.', 'Southbank closures increased.']
    fixed = ['Northbank closures decreased.', 'Southbank closures decreased.']
    gap = 'The future registry operator remains unspecified.'
    refs = {i: {'source_id': 'registry', 'locator': f'p{i}', 'quote': text}
        for i, text in enumerate([good, *fixed], 1)}
    answer = AssessmentOutcome(status='partial', points=[{'statement': text,
        'evidence': [{**refs[i], 'role': 'support'}]} for i, text in enumerate([good, *bad], 1)], limitations=[gap])
    wire = SimpleNamespace(input={'original_question': question}, references=refs,
        request_keys={'legacy': question}, point_requests=['legacy'] * 3,
        response_slots={'legacy': {'disposition': 'unresolved', 'remaining_gap': gap}})
    parsed = SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer))
    writes, selections, cache = [], [], {}

    class Model:
        async def complete(self, system, text, **options):
            value = json.loads(text)
            if 'final_claims_and_gaps' in value:
                item_key, item = next(iter(value['final_claims_and_gaps'].items()))
                assertion = item.get('statement', item.get('gap'))
                negative = assertion in bad
                data = {'clauses': [{'claim_as_written': assertion,
                    'verdict': 'contradicted' if negative else 'supported',
                    'reason': 'The original says closures decreased; the draft reverses that direction.' if negative else '',
                    'citation_refs': value.get('selected_citation_refs', [])}]}
                if value.get('prior_review_concerns'):
                    data['concern_checks'] = [{'id': concern, 'outcome': 'resolved', 'reason': '',
                        'citation_refs': value['selected_citation_refs']}
                        for concern in value['prior_review_concerns']['concerns']]
                return review_json(data, gap=item_key.startswith('L'))
            assert value['requested_part'] == value['original_question'] == question
            target = value['correction_target']
            index = bad.index(target['previous_statement'])
            assert value['review_feedback']['previous_statements'] == [bad[index]]
            notes = target['validation_errors'][0]['reviewer_notes']
            assert notes[0]['comment'] == 'The original says closures decreased; the draft reverses that direction.'
            assert notes[0]['originals'] == [refs[index + 2]]
            assert 'Fallible reviewer objection' in notes[0]['basis']
            assert 'draft is not the requested answer' in system
            if 'citation_refs' in options['response_schema']['properties']:
                selections.append(index)
                return selection_json([index + 2], options)
            assert options['response_schema']['properties']['points']['maxItems'] == 1
            assert options['response_schema']['properties']['remaining_gap']['enum'] == ['']
            writes.append(index)
            if index == 1 and writes.count(index) == 1:
                raise DomainError('Synthetic temporary outage', 503, 'model_rate_limited')
            citation_ref = next(p['citation_ref'] for group in value['sources'] for p in group['passages']
                if p['text'] == refs[index + 2]['quote'])
            return json.dumps({'points': [{'statement': fixed[index],
                'evidence': [{'citation_ref': citation_ref, 'role': 'support'}]}], 'remaining_gap': ''})

    async def covered(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': [], 'question_coverage': 'covered'}

    monkeypatch.setattr(review, 'audit', covered)
    monkeypatch.setattr(review, 'audit_points', covered)
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    work = {'input': {'original_question': question}}
    with pytest.raises(DomainError, match='Synthetic temporary outage'):
        await finalize(service, work, wire, parsed, 60, checkpoints=cache, defer_pending=True)
    assert [point.statement for point in answer.points] == [good, fixed[0], bad[1]]
    assert answer.limitations == [gap] and wire.response_slots['legacy']['remaining_gap'] == gap
    assert cache['final_correction_round']['completed'] == 1
    result = await finalize(service, work, wire, parsed, 60,
        checkpoints=json.loads(json.dumps(cache)), defer_pending=True)
    assert [point.statement for point in answer.points] == [good, *fixed]
    assert len(answer.points) == 3 and wire.point_requests == ['legacy'] * 3
    assert answer.limitations == [gap] and wire.response_slots['legacy']['remaining_gap'] == gap
    assert result['rejected_points'] == []
    assert selections == [0, 1] and writes == [0, 1, 1]


@pytest.mark.asyncio
@pytest.mark.parametrize('signal', ['fast_contradicted', 'fast_not_established'])
async def test_review_transports_large_originals_once_with_bound_concern_witnesses(signal):
    from helvetic_lens.product_exploration import AssessmentOutcome
    from helvetic_lens.research_answer_parts import source_groups
    from helvetic_lens.research_evidence_pack import request_characters
    from helvetic_lens.research_final_review import FOCUS, REVIEW, reasoned_review, scoped_review_schema
    from helvetic_lens.research_original_context import POLICY as ORIGINAL_CONTEXT_POLICY
    from helvetic_lens.research_review_witnesses import assertion_clauses

    refs = {i: {'source_id': 'report', 'locator': f'p{i}',
        'quote': (f'Original section {i}: ' + 'The registry retained its scope and exception. ' * 11).rstrip()} for i in range(1, 17)}
    selected = [(1, 'support'), (3, 'context'), (5, 'counterevidence'),
        (9, 'support'), (11, 'context'), (13, 'support')]
    statement = 'The registry retained its scope. An explicit exception still applies.'
    answer = AssessmentOutcome(status='possible_answer', points=[{'statement': statement, 'evidence': [
        {**refs[i], 'role': role} for i, role in selected]}], limitations=[])
    wire = SimpleNamespace(input={'original_question': 'What changed in the registry?',
        'sources': [{'id': 'report', 'original_context': {
            'policy': ORIGINAL_CONTEXT_POLICY, 'captured_complete': True}}]}, references=refs)
    concern = {'previous_statements': [statement], 'issues': [{'target': 'points', 'signal': signal,
        'instruction': 'Compare the cited scope and exception with the corrected statement.',
        'original_text': [refs[i]['quote'] for i, _ in selected],
        'reviewer_notes': [{'assertion': statement, 'comment': 'The exception may have been lost.',
            'basis': 'Fallible reviewer objection.', 'originals': [refs[7]]}]}]}
    host_before = deepcopy((answer.model_dump(), concern, refs))
    old_payload = {'final_claims_and_gaps': {'P0': {'statement': statement,
        'passages': [ref.model_dump() for ref in answer.points[0].evidence]}},
        'original_question': wire.input['original_question'], 'source_context': source_groups(wire, refs),
        'selected_citation_refs': [i for i, _ in selected], 'assertion_clauses': assertion_clauses(statement),
        'prior_review_concerns': {'previous_statements': [statement], 'concerns': {'C0': concern['issues'][0]}}}
    old_schema = scoped_review_schema(wire, statement, refs, {'C0': concern['issues'][0]}, point=True)
    assert request_characters(REVIEW + FOCUS + json.dumps(statement), old_payload, old_schema) > 24000
    calls, cache = [], {}

    class Model:
        async def complete(self, system, text, **options):
            value = json.loads(text)
            calls.append(value)
            assert request_characters(system, value, options['response_schema']) <= 24000
            assert value['final_claims_and_gaps']['P0']['passages'] == [
                {'citation_ref': i, 'role': role} for i, role in selected]
            supplied = {p['citation_ref']: p['text'] for source in value['source_context'] for p in source['passages']}
            assert supplied == {i: ref['quote'] for i, ref in refs.items()}
            assert all(text.count(ref['quote']) == 1 for ref in refs.values())
            issue = value['prior_review_concerns']['concerns']['C0']
            assert issue['original_refs'] == [i for i, _ in selected] and 'original_text' not in issue
            assert issue['reviewer_notes'][0]['original_refs'] == [7]
            assert 'originals' not in issue['reviewer_notes'][0]
            return review_json({'clauses': [{'claim_as_written': statement, 'verdict': 'supported',
                'reason': '', 'citation_refs': [1]}], 'concern_checks': [{'id': 'C0', 'outcome': 'resolved',
                'reason': 'The exception remains explicit.', 'citation_refs': [7]}]})

    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    first = await reasoned_review(service, wire, answer, 60, checkpoints=cache, concerns={'P0': concern})
    resumed = await reasoned_review(service, wire, answer, 60,
        checkpoints=json.loads(json.dumps(cache)), concerns={'P0': concern})
    assert first['status'] == resumed['status'] == 'checked' and not first['hints']
    assert len(calls) == 1, 'An unchanged exact review must resume without a new model request'
    assert (answer.model_dump(), concern, refs) == host_before


@pytest.mark.asyncio
@pytest.mark.parametrize('unbound', ['point', 'concern_text', 'concern_note', 'context_ref'])
async def test_unbound_review_original_stays_pending_without_model_dispatch(unbound):
    from helvetic_lens.product_exploration import AssessmentOutcome
    from helvetic_lens.research_final_review import reasoned_review

    ref = {'source_id': 'registry', 'locator': 'p1', 'quote': 'North Survey operates the registry.'}
    answer = AssessmentOutcome(status='possible_answer', points=[{'statement': ref['quote'],
        'evidence': [{**ref, 'role': 'support'}]}], limitations=[])
    concern = {'previous_statements': [ref['quote']], 'issues': [{'signal': 'not_established',
        'instruction': 'Check the responsible operator.', 'original_text': [ref['quote']]}]}
    if unbound == 'point':
        answer.points[0].evidence[0].locator = 'not-in-the-wire'
    elif unbound == 'concern_text':
        concern['issues'][0]['original_text'] = ['An original no longer in this authorized source collection.']
    elif unbound == 'concern_note':
        concern['issues'][0]['reviewer_notes'] = [{'comment': 'Check this alternative.',
            'originals': [{**ref, 'source_id': 'another-tenant'}]}]
    else:
        concern['context_refs'] = [99]

    class Model:
        async def complete(self, *args, **kwargs):
            pytest.fail('Unknown original identity must not reach the reviewer')

    cache = {}
    result = await reasoned_review(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()),
        SimpleNamespace(input={}, references={1: ref}), answer, 60, checkpoints=cache, concerns={'P0': concern})
    assert result['status'] == 'partial' and cache == {}
    assert result['pending_checks'] == [{'item': 'P0', 'reason': 'unbound_original_reference'}]
    assert result['hints'][0]['review_signal'] == 'review_unavailable'


@pytest.mark.asyncio
@pytest.mark.parametrize('prior_concern', [False, True])
async def test_gap_review_retrieves_complete_originals_without_mandating_all_delivered_sources(monkeypatch, prior_concern):
    from helvetic_lens import research_active_retrieval, research_evidence_pack
    from helvetic_lens.product_exploration import AssessmentOutcome
    from helvetic_lens.research_final_review import reasoned_review

    refs, sources, pages, points = {}, [], [], []
    for index in range(5):
        source_id, page = f'sibling-{index}', []
        for line in range(15):
            key = len(refs) + 1
            refs[key] = {'source_id': source_id, 'locator': f'page-1-text-{line}',
                'quote': (f'Registry {index}, record {line}: ' + 'The operator retains the recorded responsibility. ' * 8).rstrip()}
            page.append(key)
        pages.append(page)
        sources.append({'id': source_id, 'title': source_id, 'excerpts': [
            {'passage': refs[key]['locator'], 'text': refs[key]['quote']} for key in page]})
        points.append({'statement': f'Registry {index} retains its operator.',
            'evidence': [{**refs[page[0]], 'role': 'support'}]})
    for source_id, texts in [('transfer', ['The transfer date has not been determined.',
            'The successor must be elected before a transfer can be scheduled.']),
            ('objection', ['The earlier timetable was withdrawn.', 'That timetable cannot establish a current transfer date.'])]:
        page = []
        for line, text in enumerate(texts):
            key = len(refs) + 1
            refs[key] = {'source_id': source_id, 'locator': f'page-1-text-{line}', 'quote': text}
            page.append(key)
        pages.append(page)
        sources.append({'id': source_id, 'title': source_id, 'excerpts': [
            {'passage': refs[key]['locator'], 'text': refs[key]['quote']} for key in page]})
    relevant, objection = pages[-2:]
    answer = AssessmentOutcome(status='partial', points=points, limitations=['The transfer date remains unknown.'])
    wire = SimpleNamespace(input={'original_question': 'Who operates these registries, and when is the transfer?',
        'sources': sources}, references=refs)
    concerns = {'L0': {'previous_statements': [], 'issues': [{'instruction': 'Check the withdrawn timetable.',
        'original_refs': [objection[0]]}]}} if prior_concern else None
    before = deepcopy((answer.model_dump(), refs, sources, concerns))
    calls, selections, cache = [], [], {}
    real_select = research_evidence_pack.select_evidence

    async def select(service, candidate, question, seconds, **options):
        assert candidate.references == refs, 'Gap retrieval must consider originals beyond the current answer'
        assert options['required_refs'] == (objection[:1] if prior_concern else [])
        siblings = {key: refs[key] for page in pages[:5] for key in page}
        assert not options['fits'](siblings), 'The old all-sibling mandatory pack would overflow'
        selected = await real_select(service, candidate, question, seconds, **options)
        assert set(relevant) <= set(selected)
        if prior_concern:
            assert set(objection) <= set(selected), 'A prior objection keeps its whole original page'
        assert not set(siblings) <= set(selected)
        for page in pages:
            assert not set(page).intersection(selected) or set(page) <= set(selected), 'Never crop an original page'
        selections.append(selected)
        return selected

    async def rank(service, candidate, question, seconds, **options):
        assert candidate.references == refs
        return {'rankings': [{'query': 'transfer date', 'references': [*relevant,
            *(key for key in refs if key not in relevant)]}],
            'coverage': {'method': 'test_ranked_originals', 'semantic_status': 'test_fixture'}}

    class Model:
        async def complete(self, system, text, **options):
            value = json.loads(text)
            assert research_evidence_pack.request_characters(system, value, options['response_schema']) <= 24000
            key, item = next(iter(value['final_claims_and_gaps'].items()))
            calls.append(key)
            if key == 'L0':
                assert value['delivered_points'] == [{'statement': point.statement} for point in answer.points]
                supplied = {p['citation_ref']: p['text'] for group in value['sources'] for p in group['passages']}
                assert supplied == {key: ref['quote'] for key, ref in selections[-1].items()}
                witnesses = relevant[:1]
            else:
                assert [{**refs[ref], 'role': 'support'} for ref in value['selected_citation_refs']] == [
                    ref.model_dump() for ref in answer.points[int(key[1:])].evidence]
                witnesses = value['selected_citation_refs']
            data = {'clauses': [{'claim_as_written': item.get('statement', item.get('gap')),
                'verdict': 'supported', 'reason': '', 'citation_refs': witnesses}]}
            if key == 'L0' and prior_concern:
                data['concern_checks'] = [{'id': 'C0', 'outcome': 'resolved',
                    'reason': 'The withdrawn timetable is not used as a current date.', 'citation_refs': objection[:1]}]
            return review_json(data, gap=key == 'L0')

    monkeypatch.setattr(research_evidence_pack, 'select_evidence', select)
    monkeypatch.setattr(research_active_retrieval, 'rank_evidence', rank)
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    result = await reasoned_review(service, wire, answer, 60, checkpoints=cache, concerns=concerns)
    assert result['status'] == 'checked' and calls == ['P0', 'P1', 'P2', 'P3', 'P4', 'L0']
    assert (answer.model_dump(), refs, sources, concerns) == before
    cache = json.loads(json.dumps(cache))
    await reasoned_review(service, wire, answer, 60, checkpoints=cache, concerns=concerns)
    assert len(calls) == 6, 'Exact checked points and the gap resume without new inference'
    answer.points[0].evidence[0].locator = refs[pages[0][1]]['locator']
    answer.points[0].evidence[0].quote = refs[pages[0][1]]['quote']
    await reasoned_review(service, wire, answer, 60, checkpoints=cache, concerns=concerns)
    assert calls[6:] == ['P0', 'L0'], 'Changed private citations invalidate gap proof without rechecking unchanged siblings'


@pytest.mark.asyncio
async def test_unbound_delivered_original_keeps_gap_pending_without_dispatch():
    from helvetic_lens.product_exploration import AssessmentOutcome
    from helvetic_lens.research_final_review import reasoned_review

    ref = {'source_id': 'registry', 'locator': 'p1', 'quote': 'North Survey operates the registry.'}
    answer = AssessmentOutcome(status='partial', points=[{'statement': ref['quote'],
        'evidence': [{**ref, 'source_id': 'another-tenant', 'role': 'support'}]}],
        limitations=['The transfer date remains unknown.'])

    class Model:
        async def complete(self, *args, **kwargs):
            pytest.fail('An unbound delivered original must not reach either point or gap review')

    cache = {}
    result = await reasoned_review(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()),
        SimpleNamespace(input={}, references={1: ref}), answer, 60, checkpoints=cache)
    assert result['status'] == 'partial' and cache == {}
    assert result['pending_checks'] == [{'item': key, 'reason': 'unbound_original_reference'} for key in ('P0', 'L0')]
