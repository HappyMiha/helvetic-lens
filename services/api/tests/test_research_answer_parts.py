"""Request synthesis preserves unknowns, canonical states and resumable originals."""
import json
from types import SimpleNamespace

import pytest
from research_pack_fixtures import atomic_pack_model

from helvetic_lens.product_exploration import AssessmentOutcome, Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_answer_parts import answer_request, recover_requests
from helvetic_lens.research_answer_review import repair_points
from helvetic_lens.research_model_transport import EvidenceWire


def selection_json(refs, options):
    sources = options['response_schema']['properties']['citation_refs']['properties']
    return json.dumps({'citation_refs': {key: [ref for ref in refs if ref in value['items']['enum']]
        for key, value in sources.items()}})


def fixture(count=2):
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': ' '.join(f'When was record {i} published?' for i in range(1, count+1)),
        'research_mission': {}, 'sources': [{'id': 'a', 'kind': 'public_source', 'title': 'Original registry',
            'excerpts': [{'passage': 'p1', 'text': 'The records were published in 2001.'},
                {'passage': 'p2', 'text': 'An earlier edition was published in 1999.'}]}]}}
    schema = mission_schema(Briefing)
    wire = EvidenceWire(work, schema, '', shared_answer=False)
    raw = json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'responses': {
        key: {'disposition': 'answered', 'remaining_gap': '', 'points': [{'statement': 'Published in 2001.',
            'evidence': [{'citation_ref': 1, 'role': 'support'}]}]} for key in wire.request_keys}}, 'next_action': 'finish'})
    parsed = schema.model_validate_json(wire.decode(raw))
    return wire, parsed, schema


@pytest.mark.asyncio
@pytest.mark.parametrize('extra', ['point', 'gap'])
async def test_point_correction_cannot_expand_into_more_answers_or_a_gap(extra):
    wire, _, _ = fixture()
    class Model:
        async def complete(self, system, text, **options):
            value = json.loads(text)
            assert value['requested_part'] == wire.input['original_question']
            assert value['correction_target']['previous_statement'] == 'Published in 2009.'
            if 'citation_refs' in options['response_schema']['properties']:
                return selection_json([1], options)
            assert options['response_schema']['properties']['points']['maxItems'] == 1
            point = {'statement': 'Published in 2001.', 'evidence': [{'citation_ref': 1, 'role': 'support'}]}
            return json.dumps({'points': [point] * (2 if extra == 'point' else 1),
                'remaining_gap': 'An unrelated issue remains.' if extra == 'gap' else ''})
    points, gap, receipt = await answer_request(SimpleNamespace(model_client=Model()), wire,
        wire.input['original_question'], 60, max_points=8,
        correction={'previous_statement': 'Published in 2009.', 'validation_errors': []})
    assert points == [] and gap == '' and receipt['status'] == 'invalid_answer'


@pytest.mark.asyncio
async def test_point_repair_with_eight_requests_preserves_an_existing_gap_and_round_trips():
    wire, parsed, schema = fixture(8)
    answer = parsed.mission_checkpoint.answer
    answer.points[-1].statement = 'Published in 2009.'
    from helvetic_lens.research_answer_parts import update_gap
    update_gap(wire, answer, 'r8', 'The edition date is unknown.')
    class Model:
        @atomic_pack_model
        async def complete(self, system, text, **options):
            if 'citation_refs' in options['response_schema']['properties']:
                return selection_json([1], options)
            assert options['response_schema']['properties']['remaining_gap']['enum'] == ['']
            return json.dumps({'statement': 'Published in 2001.', 'remaining_gap': '',
                'evidence': [{'citation_ref': 1, 'role': 'support'}]})
    await repair_points(SimpleNamespace(model_client=Model()), wire, answer, 60)
    encoded = wire.encode_checkpoint(parsed)
    assert json.loads(encoded)['answer']['remaining_gaps'] == []
    decoded = schema.model_validate_json(wire.decode(encoded)).mission_checkpoint.answer
    assert decoded.points[-1].statement == 'Published in 2001.'
    assert decoded.status == 'partial' and decoded.limitations == ['The edition date is unknown.']
    assert wire.response_slots['r8']['disposition'] == 'unresolved'


@pytest.mark.asyncio
async def test_explicit_unknown_does_not_leave_previous_slot_answered():
    wire, parsed, schema = fixture()
    class Model:
        @atomic_pack_model
        async def complete(self, system, text, **options):
            if 'citation_refs' in options['response_schema']['properties']:
                return selection_json([1], options)
            return json.dumps({'statement': '', 'evidence': [], 'remaining_gap': 'The original does not identify this edition.'})
    await recover_requests(SimpleNamespace(model_client=Model()), wire, parsed.mission_checkpoint.answer,
        [wire.request_keys['r2']], 60)
    assert wire.response_slots['r2']['disposition'] == 'unresolved'
    answer = schema.model_validate_json(wire.decode(wire.encode_checkpoint(parsed))).mission_checkpoint.answer
    assert answer.status == 'partial' and answer.limitations == ['The original does not identify this edition.']
    assert answer.points[0].statement == 'Published in 2001.'


@pytest.mark.asyncio
async def test_invalid_proposal_never_poisons_a_resumed_selected_pack():
    wire, _, _ = fixture()
    checkpoints, calls = {}, []
    good = [False]
    class Model:
        @atomic_pack_model
        async def complete(self, system, text, **options):
            if 'citation_refs' in options['response_schema']['properties']:
                calls.append('select')
                return selection_json([1], options)
            calls.append('write')
            return json.dumps({'statement': 'Published in 2001.' if good[0] else 'Published in 2099.',
                'remaining_gap': '', 'evidence': [{'citation_ref': 1, 'role': 'support'}]})
    service = SimpleNamespace(model_client=Model())
    first, _, receipt = await answer_request(service, wire, wire.request_keys['r1'], 60, checkpoints=checkpoints)
    assert not first and receipt['status'] == 'unsupported_precision'
    assert all('proposal' not in part for part in checkpoints.values())
    good[0] = True
    fixed, _, _ = await answer_request(service, wire, wire.request_keys['r1'], 60,
        checkpoints=json.loads(json.dumps(checkpoints)))
    assert fixed[0].statement == 'Published in 2001.' and calls == ['select', 'write', 'write', 'write']


@pytest.mark.asyncio
@pytest.mark.parametrize('initial, role, expected', [('conflicting', 'support', 'possible_answer'),
    ('possible_answer', 'context', 'partial')])
async def test_replacing_a_part_reconciles_the_answer_status(initial, role, expected):
    wire, parsed, _ = fixture()
    answer = parsed.mission_checkpoint.answer
    answer.points = answer.points[:1]
    wire.point_requests = ['r1']
    answer.status = initial
    wire.response_slots['r2'].update(disposition='unresolved', remaining_gap='The second record remains unknown.')
    answer.limitations = ['The second record remains unknown.']
    class Model:
        @atomic_pack_model
        async def complete(self, system, text, **options):
            if 'citation_refs' in options['response_schema']['properties']:
                return selection_json([1], options)
            return json.dumps({'statement': 'Published in 2001.', 'remaining_gap': '',
                'evidence': [{'citation_ref': 1, 'role': role}]})
    answer.points[0].evidence[0].role = role
    await recover_requests(SimpleNamespace(model_client=Model()), wire, answer, list(wire.request_keys.values()), 60)
    assert answer.status == expected and not answer.limitations
    AssessmentOutcome.model_validate(answer.model_dump())


@pytest.mark.asyncio
@pytest.mark.parametrize('same_source', [True, False])
async def test_citation_correction_preserves_needed_prior_context_only_within_the_same_source(same_source):
    refs = {1: {'source_id': 'a', 'locator': 'p1', 'quote': 'The earlier record was published in 2012.'},
        2: {'source_id': 'a', 'locator': 'p2', 'quote': 'The current record was published in 2013.'},
        3: {'source_id': 'a' if same_source else 'b', 'locator': 'p3', 'quote': 'The current record took effect in 2015.'}}
    wire = SimpleNamespace(references=refs, input={})
    calls = []
    class Model:
        @atomic_pack_model
        async def complete(self, system, text, **options):
            if 'citation_refs' in options['response_schema']['properties']:
                return selection_json([1, 2, 3], options)
            calls.append(json.loads(text))
            return json.dumps({'statement': 'The current record was published in 2013 and took effect in 2015.',
                'remaining_gap': '', 'evidence': [{'citation_ref': key, 'role': 'support'}
                    for key in ([1, 3] if len(calls) == 1 else [2])]})
    point, _, _ = await answer_request(SimpleNamespace(model_client=Model()), wire, 'Compare the dates.', 60)
    assert len(calls) == 2
    if same_source:
        assert [ref.quote for ref in point[0].evidence] == [refs[2]['quote'], refs[3]['quote']]
        assert point[0].evidence[-1].role == 'context'
    else:
        assert not point


@pytest.mark.asyncio
@pytest.mark.parametrize('order', [[1, 2, 3], [3, 2, 1]])
async def test_last_citation_slot_retains_context_covering_the_missing_comparison(order):
    quotes = ['The record was adopted in 2001.', 'Adopted in 2001; published in 2003.',
        'The earlier record was published in 1999.', 'The current record belongs to the registry.',
        'The adopted record was subsequently published.', 'The proceedings retain the decision.',
        'The document identifies the responsible authority.', 'This is the current record.',
        'The document is available in the official collection.', 'This is an original publication.']
    refs = {i+1: {'source_id': 'a', 'locator': f'p{i+1}', 'quote': quote} for i, quote in enumerate(quotes)}
    wire = SimpleNamespace(references=refs, input={})
    class Model:
        writes = 0
        @atomic_pack_model
        async def complete(self, system, text, **options):
            if 'citation_refs' in options['response_schema']['properties']:
                return selection_json(list(refs), options)
            self.writes += 1
            statement = 'The record was adopted in 2001 and published in 2003.'
            return json.dumps({'statement': statement + (' Another copy was published in 2099.' if self.writes == 1 else ''),
                'remaining_gap': '', 'evidence': [{'citation_ref': key, 'role': 'support'}
                    for key in (order if self.writes == 1 else range(4, 11))]})
    point, gap, _ = await answer_request(SimpleNamespace(model_client=Model()), wire, 'Compare adoption and publication.', 60)
    assert bool(point) and gap == '' and len(point[0].evidence) == 8
    assert point[0].evidence[-1].quote == quotes[1] and point[0].evidence[-1].role == 'context'


@pytest.mark.asyncio
@pytest.mark.parametrize('same_source,long_context', [(True, False), (False, False), (True, True)])
async def test_uncited_short_context_can_complete_only_an_already_selected_original(same_source, long_context):
    refs = {1: {'source_id': 'a', 'locator': 'p1', 'quote': 'The record was adopted and then published.'},
        2: {'source_id': 'a' if same_source else 'b', 'locator': 'p2',
            'quote': 'Meeting: 2001; proceedings: 2003.' + (' Extra context.' * 30 if long_context else '')}}
    class Model:
        @atomic_pack_model
        async def complete(self, system, text, **options):
            if 'citation_refs' in options['response_schema']['properties']:
                return selection_json([1], options)
            return json.dumps({'statement': 'The record was adopted in 2001 and published in 2003.',
                'remaining_gap': '', 'evidence': [{'citation_ref': 1, 'role': 'support'}]})
    point, _, _ = await answer_request(SimpleNamespace(model_client=Model()),
        SimpleNamespace(references=refs, input={}), 'Compare adoption and publication.', 60)
    if same_source and not long_context:
        assert point[0].evidence[-1].quote == refs[2]['quote'] and point[0].evidence[-1].role == 'context'
    else:
        assert not point


@pytest.mark.asyncio
async def test_unavailable_part_retains_existing_evidence_but_cannot_claim_completed_synthesis():
    wire, parsed, schema = fixture()
    original = parsed.mission_checkpoint.answer.points[0].model_copy(deep=True)
    class Model:
        @atomic_pack_model
        async def complete(self, *args, **options):
            return selection_json([], options)
    await recover_requests(SimpleNamespace(model_client=Model()), wire, parsed.mission_checkpoint.answer,
        [wire.request_keys['r1']], 60)
    answer = schema.model_validate_json(wire.decode(wire.encode_checkpoint(parsed))).mission_checkpoint.answer
    assert answer.points[0] == original and answer.status == 'partial'
    assert answer.limitations == ['A cited answer could not be completed for: When was record 1 published?']


def test_combined_answer_cannot_be_projected_as_one_direct_legacy_quote():
    wire, parsed, schema = fixture()
    point = parsed.mission_checkpoint.answer.points[0]
    point.statement = 'The earlier edition was published in 1999 and the later records in 2001.'
    point.evidence.append(point.evidence[0].model_copy(update={**wire.references[2], 'role': 'support'}))
    result = schema.model_validate_json(wire.decode(wire.encode_checkpoint(parsed)))
    assert result.mission_checkpoint.answer.points[0].statement == point.statement
    assert {ref.quote for ref in result.mission_checkpoint.answer.points[0].evidence} == {
        'The records were published in 2001.', 'An earlier edition was published in 1999.'}
    assert len(result.findings) == 1  # Only the independent single-citation sibling.


def test_selected_citation_labels_are_not_factual_numbers_but_unknown_labels_and_dates_still_fail():
    from helvetic_lens.research_answer_parts import remove_citation_labels
    from helvetic_lens.research_gateway import answer_quantity_errors
    data = {'statement': 'It was published in 2001 (citation_ref 77).', 'evidence': [{'citation_ref': 77, 'role': 'support'}]}
    remove_citation_labels(data)
    assert data['statement'] == 'It was published in 2001.'
    answer = AssessmentOutcome(status='possible_answer', limitations=[], points=[{'statement': data['statement'],
        'evidence': [{'source_id': 'a', 'locator': 'p1', 'quote': 'Published in 2001.', 'role': 'support'}]}])
    assert not answer_quantity_errors(answer)
    data['statement'] = 'It was published in 2099 (citation_ref 78).'
    remove_citation_labels(data)
    assert data['statement'] == 'It was published in 2099 (citation_ref 78).'
    answer.points[0].statement = data['statement']
    assert answer_quantity_errors(answer)


@pytest.mark.asyncio
@pytest.mark.parametrize('selection', ['valid', 'missing_source', 'foreign_source'])
async def test_later_original_reaches_writer_despite_repetitive_early_summary(selection):
    refs = {i: {'source_id': 'summary', 'locator': f'p{i}', 'quote': 'A summary of the former operator.'}
        for i in range(1, 12)}
    refs[12] = {'source_id': 'old', 'locator': 'p1', 'quote': 'The previous review did not identify the successor.'}
    refs[13] = {'source_id': 'new', 'locator': 'p1', 'quote': 'The replacement operator is North Reach Survey.'}
    wire = SimpleNamespace(references=refs, input={'original_question': 'Who operates the registry now?'})
    calls, cache = [], {}
    class Model:
        @atomic_pack_model
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            selecting = 'citation_refs' in options['response_schema']['properties']
            calls.append('select' if selecting else 'write')
            if selecting:
                data = json.loads(selection_json(list(refs), options))
                if selection == 'missing_source':
                    del data['citation_refs']['S2']
                if selection == 'foreign_source':
                    data['citation_refs']['S0'] = [13]
                return json.dumps(data)
            evidence = [ref for source in payload['sources'] for ref in source['passages']]
            late = next(ref for ref in evidence if ref['text'] == refs[13]['quote'])
            assert len(evidence) >= 13, 'An early summary must not crowd out the later direct original'
            return json.dumps({'statement': refs[13]['quote'], 'remaining_gap': '',
                'evidence': [{'citation_ref': late['citation_ref'], 'role': 'support'}]})
    service = SimpleNamespace(model_client=Model())
    point, _, receipt = await answer_request(service, wire, wire.input['original_question'], 60, checkpoints=cache)
    if selection != 'valid':
        assert not point and receipt['status'] == 'invalid_selection' and calls == ['select']
        return
    assert point[0].evidence[0].source_id == 'new' and point[0].evidence[0].quote == refs[13]['quote']
    await answer_request(service, wire, wire.input['original_question'], 60, checkpoints=cache)
    assert calls == ['select', 'write']
    refs[14] = {'source_id': 'addendum', 'locator': 'p1', 'quote': 'The replacement appointment remains current.'}
    await answer_request(service, wire, wire.input['original_question'], 60, checkpoints=cache)
    assert calls == ['select', 'write', 'select', 'write'], 'A newly authorized original invalidates the previous selection'


@pytest.mark.asyncio
async def test_many_sources_keep_their_complete_schema_with_a_supported_transport_allowance():
    refs = {i+1: {'source_id': str(i // 12), 'locator': str(i % 12), 'quote': 'An available original passage.'}
        for i in range(65 * 12)}
    class Model:
        @atomic_pack_model
        async def complete(self, system, text, **options):
            if not 128 <= options['max_output_tokens'] <= 8192:
                raise ValueError('Invalid per-request output allowance')
            payload = json.loads(text)
            assert len(payload['sources']) == 65
            assert sum(len(source['passages']) for source in payload['sources']) == len(refs)
            assert len(options['response_schema']['properties']['citation_refs']['required']) == 65
            return selection_json([], options)
    point, _, receipt = await answer_request(SimpleNamespace(model_client=Model()),
        SimpleNamespace(references=refs, input={}), 'Which originals establish the requested appointment?', 60)
    assert not point and receipt['status'] == 'no_selection'
