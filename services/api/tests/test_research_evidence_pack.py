"""Bounded provider views retain exact originals and durable all-corpus selection."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens.config import DomainError
from helvetic_lens.research_evidence_pack import (
    POLICY,
    bounded_schema,
    provider_input,
    provider_sources,
    request_characters,
    select_evidence,
)
from helvetic_lens.research_original_context import POLICY as ORIGINAL_CONTEXT_POLICY


def corpus(count=10, quote=None):
    references = {i: {'source_id': f's{i}', 'locator': 'p1',
        'quote': quote or f'Original {i}. ' + 'Station capacity context. ' * 60}
        for i in range(1, count + 1)}
    sources = [{'id': f's{i}', 'title': f'Original {i}', 'sha256': f'hash-{i}',
        'original_context': {'policy': ORIGINAL_CONTEXT_POLICY, 'captured_complete': True},
        'url': f'https://example.test/{i}', 'discovery_links': [{'url': 'https://example.test/next'}]}
        for i in range(1, count + 1)]
    point = {'type': 'object', 'properties': {
        'evidence': {'type': 'array', 'minItems': 1, 'items': {'type': 'object',
            'properties': {'citation_ref': {'type': 'integer', 'minimum': 1, 'maximum': count}},
            'required': ['citation_ref']}}, 'statement': {'type': 'string'}},
        'required': ['evidence', 'statement']}
    schema = {'type': 'object', 'properties': {
        'points': {'type': 'array', 'minItems': 1, 'items': point},
        'remaining_gaps': {'type': 'array', 'items': {'type': 'string'}}}}
    return SimpleNamespace(references=references,
        input={'original_question': 'Explain station capacity and its limits.', 'sources': sources},
        schema=schema, system='Write the answer using exact original references.')


class Selector:
    def __init__(self, _choose):
        self.calls = []

    async def complete(self, *args, **kwargs):
        pytest.fail('Local retrieval must not invoke a generative provider')


def service(model, allowance=9000):
    return SimpleNamespace(model_client=model, settings=SimpleNamespace(
        apertus_context_chars=allowance, apertus_model='fictional-model'))


@pytest.mark.asyncio
async def test_small_complete_pack_needs_no_selection_and_keeps_host_links():
    wire, model = corpus(2), Selector(lambda *_: True)
    original = deepcopy(wire.__dict__)
    result = await select_evidence(service(model), wire, wire.input['original_question'], 60)
    assert result == wire.references and result is not wire.references and not model.calls
    assert wire.__dict__ == original
    assert all('discovery_links' not in item for item in provider_sources(wire, result))
    selected_schema = bounded_schema(wire.schema, {2: result[2]})
    assert selected_schema['properties']['points']['items']['properties']['evidence']['items']['properties']['citation_ref'] == {
        'type': 'integer', 'enum': [2]}


def test_provider_metadata_keeps_every_unfinished_warning_and_discovery_obligation():
    wire = corpus(2)
    clean = {'title': 'A completed original', 'url': 'https://example.test/complete',
        'read_complete': True, 'analysis_complete': True, 'unread_reason': None,
        'warnings': [], 'unresolved_references': []}
    outstanding = [{**clean, **change} for change in (
        {'read_complete': False}, {'analysis_complete': False}, {'unread_reason': 'OCR needed'},
        {'warnings': ['Table extraction was incomplete.']}, {'unresolved_references': ['Annex B']},
        {'error': 'A retained partial reader failure'})]
    wire.input['research_mission'] = {'question': wire.input['original_question'],
        'completion_policy': 'A host-enforced workflow policy.', 'documents': [clean, *outstanding],
        'unvalidated_proposals': [], 'attempted_queries': ['An earlier exact query'],
        'discovery_frontiers': [{'query': 'A pending query', 'more': True}]}
    original = deepcopy(wire.input)
    result = provider_input(wire, wire.references)
    mission = result['research_mission']
    assert mission['documents'] == outstanding
    assert mission['document_counts'] == {'total': 7, 'read_complete': 6, 'analysis_complete': 6}
    assert mission['attempted_queries'] == original['research_mission']['attempted_queries']
    assert mission['discovery_frontiers'] == original['research_mission']['discovery_frontiers']
    assert not {'question', 'completion_policy', 'unvalidated_proposals'} & mission.keys()
    assert wire.input == original
    assert list(result) == list(wire.input), 'The compact view preserves provider field order'
    mission['documents'][0]['warnings'].append('Provider-view-only change')
    assert wire.input == original, 'Compacting metadata must not share mutable host state'
    wire.input['research_mission'].update(question='A distinct earlier obligation.', unvalidated_proposals=['Unverified proposal'])
    different = provider_input(wire, {})['research_mission']
    assert different['question'] == 'A distinct earlier obligation.'
    assert different['unvalidated_proposals'] == ['Unverified proposal']


def test_reflection_preserves_only_selected_exact_source_leads_and_honest_scope():
    wire = corpus(2)
    wire.work = {'phase': 'reflect'}
    wire.input['sources'][0]['section_review'] = {'summary': 'Repeated derived synopsis' * 100}
    wire.input['sources'][0]['discovery_links'] = [
        {'title': 'Read the original', 'url': 'https://example.test/original',
            'context': wire.references[1]['quote'], 'kind': 'reference'},
        {'title': 'Unrelated', 'url': 'https://example.test/unrelated', 'context': 'Other material'},
        {'title': 'Navigation', 'url': 'https://example.test/home', 'context': wire.references[1]['quote'], 'kind': 'navigation'}]
    wire.input['sources'][1]['discovery_links'] = [{'title': 'Unselected', 'url': 'https://example.test/other',
        'context': wire.references[2]['quote'], 'kind': 'reference'}]
    before = deepcopy(wire.__dict__)
    selected = {1: wire.references[1]}
    result = provider_input(wire, selected)
    assert result['discovery_leads'] == [{'citation_ref': 1, 'url': 'https://example.test/original', 'title': 'Read the original'}]
    assert result['evidence_scope']['all_originals_supplied'] is False
    assert result['evidence_scope']['absence_established'] is False
    assert 'section_review' not in result['sources'][0] and 'discovery_links' not in result['sources'][0]
    assert wire.__dict__ == before
    empty = bounded_schema({'properties': {'gaps': {'type': 'array', 'items': {'type': 'object'}}}}, {})
    assert empty['properties']['gaps']['maxItems'] == 0


def test_brief_selected_packet_is_not_evidence_of_absence():
    wire = corpus(2)
    wire.work = {'phase': 'brief'}
    before = deepcopy(wire.__dict__)
    result = provider_input(wire, {1: wire.references[1]})
    assert result['evidence_scope']['available_references'] == 2
    assert result['evidence_scope']['selected_references'] == 1
    assert result['evidence_scope']['all_originals_supplied'] is False
    assert result['evidence_scope']['absence_established'] is False
    assert wire.__dict__ == before


@pytest.mark.parametrize('phase', ['brief', 'reflect'])
def test_only_brief_projects_history_counts_without_losing_live_obligations(phase):
    wire = corpus(2)
    document = {'title': 'Unread annex', 'read_complete': False, 'analysis_complete': False,
        'unread_reason': 'The remaining pages must be read.', 'unresolved_references': ['Annex B']}
    frontier = {'branch_id': 'saved-branch', 'query': 'Current original annex', 'remaining_candidates': 2}
    wire.input['research_mission'] = {
        'attempted_queries': ['Repeated prior search', 'Repeated prior search'],
        'attempted_questions': [{'question': 'An obsolete model premise?', 'status': 'evidence_found'},
            {'question': 'An optional historical extension?', 'status': 'open'},
            {'question': 'A completed verification?', 'status': 'evidence_found'}],
        'documents': [document], 'discovery_frontiers': [frontier]}
    wire.work = {'phase': phase, 'input': wire.input}
    before = deepcopy(wire.__dict__)
    result = provider_input(wire, wire.references)
    mission = result['research_mission']
    assert result['original_question'] == before['input']['original_question']
    assert mission['documents'] == [document]
    assert mission['discovery_frontiers'] == [frontier]
    if phase == 'brief':
        assert not {'attempted_queries', 'attempted_questions'} & mission.keys()
        assert mission['attempted_query_count'] == 2 and mission['attempted_question_count'] == 3
        assert 'An obsolete model premise?' not in json.dumps(result)
    else:
        assert mission['attempted_queries'] == before['input']['research_mission']['attempted_queries']
        assert mission['attempted_questions'] == before['input']['research_mission']['attempted_questions']
        assert not {'attempted_query_count', 'attempted_question_count'} & mission.keys()
    mission['documents'][0]['unresolved_references'].append('Provider-only mutation')
    mission['discovery_frontiers'][0]['query'] = 'Provider-only mutation'
    assert wire.__dict__ == before  # Host routing/deduplication still sees the full history.


@pytest.mark.asyncio
async def test_brief_history_projection_frees_space_for_complete_originals():
    wire, model = corpus(3), Selector(None)
    wire.input['research_mission'] = {
        'attempted_queries': ['An obsolete search premise. ' * 100] * 3,
        'attempted_questions': [{'question': 'Optional historical extension. ' * 100,
            'status': 'evidence_found'}] * 3,
        'documents': [{'title': 'Pending original', 'read_complete': False,
            'analysis_complete': False, 'unread_reason': 'Remaining annex'}],
        'discovery_frontiers': [{'branch_id': 'saved-branch', 'query': 'Read annex', 'remaining_candidates': 1}]}
    wire.work = {'phase': 'brief', 'input': wire.input}
    before = deepcopy(wire.__dict__)
    projected = provider_input(wire, wire.references)
    old_payload = deepcopy(projected)
    old_payload['research_mission'].update({key: deepcopy(value) for key, value in
        wire.input['research_mission'].items() if key in {'attempted_queries', 'attempted_questions'}})
    old_payload['research_mission'].pop('attempted_query_count')
    old_payload['research_mission'].pop('attempted_question_count')
    assert request_characters(wire.system, old_payload, bounded_schema(wire.schema, wire.references)) > 9000
    assert request_characters(wire.system, projected, bounded_schema(wire.schema, wire.references)) <= 9000
    saved = {}
    selected = await select_evidence(service(model), wire, wire.input['original_question'], 60, checkpoints=saved)
    assert selected == wire.references and not model.calls
    assert saved['retrieval_coverage']['all_originals_supplied'] is True
    assert wire.__dict__ == before


@pytest.mark.asyncio
async def test_completed_document_metadata_does_not_displace_a_whole_short_original():
    wire, model = corpus(1, 'An exact qualified observation. ' * 40), Selector(lambda *_: True)
    wire.references = {i: {'source_id': 's1', 'locator': f'p{i}',
        'quote': f'Exact context {i}. ' + 'Original qualification. ' * 15} for i in range(1, 15)}
    wire.input['research_mission'] = {'documents': [{'title': 'Completed title ' * 30,
        'read_complete': True, 'analysis_complete': True, 'warnings': [],
        'unresolved_references': [], 'unread_reason': None} for _ in range(30)]}
    assert request_characters(wire.system, {**wire.input, 'sources': provider_sources(wire, wire.references)},
        wire.schema) > 12000
    result = await select_evidence(service(model, 12000), wire, wire.input['original_question'], 60)
    assert result == wire.references and not model.calls
    assert len(wire.input['research_mission']['documents']) == 30


def ranking(monkeypatch, rows=None, *, semantic_status='ready'):
    from helvetic_lens import research_active_retrieval
    seen = []

    async def rank(service, wire, question, seconds, **kwargs):
        seen.append({'question': question, 'references': deepcopy(wire.references)})
        return {'rankings': rows if rows is not None else [{'query': question, 'references': list(wire.references)}],
            'coverage': {'method': 'hybrid_e5_bm25' if semantic_status == 'ready' else 'bm25_graph',
                'semantic_status': semantic_status, 'examined_records': len(wire.references)}}
    monkeypatch.setattr(research_active_retrieval, 'rank_evidence', rank)
    return seen


@pytest.mark.asyncio
async def test_late_qualifier_and_all_originals_survive_local_ranking(monkeypatch):
    wire, checkpoints = corpus(12), {}
    wire.references[13] = {'source_id': 's12', 'locator': 'p2', 'quote': 'A late exception limits the published total.'}
    original = deepcopy(wire.__dict__)
    seen = ranking(monkeypatch, [{'query': 'capacity and limits', 'references': [12, 1, *range(2, 12)]}])
    result = await select_evidence(service(Selector(None)), wire, wire.input['original_question'], 60,
        fits=lambda refs: len(refs) <= 3, checkpoints=checkpoints)
    assert set(result) == {1, 12, 13} and result[13] == wire.references[13]
    assert seen[0]['references'] == wire.references and wire.__dict__ == original
    assert checkpoints['retrieval_coverage']['examined_records'] == 13
    assert not checkpoints['retrieval_coverage']['all_originals_supplied']
    assert checkpoints['retrieval_coverage']['absence_established'] is False


@pytest.mark.asyncio
async def test_complete_paragraph_and_adjacent_qualification_are_not_sliced(monkeypatch):
    wire = corpus(1)
    wire.references = {i: {'source_id': 's1', 'locator': f'p{i}' if i < 28 else 'p28',
        'quote': f'Exact window {i}. ' + 'Original context. ' * 24} for i in range(1, 31)}
    ranking(monkeypatch, [{'query': 'qualification', 'references': [29, *range(1, 29), 30],
        'scores': {key: 1 if key == 29 else .1 for key in wire.references}}])
    result = await select_evidence(service(Selector(None)), wire, 'Explain the qualification.', 60,
        fits=lambda refs: len(refs) <= 4)
    assert set(result) == {27, 28, 29, 30}
    assert result == {key: wire.references[key] for key in result}


@pytest.mark.asyncio
async def test_question_parts_and_source_diversity_share_the_pack(monkeypatch):
    wire, checkpoints = corpus(4), {}
    ranking(monkeypatch, [{'query': 'whole question', 'references': [1, 2, 3, 4]},
        {'query': 'distinct requested qualification', 'references': [4, 3, 2, 1]}])
    result = await select_evidence(service(Selector(None)), wire, wire.input['original_question'], 60,
        fits=lambda refs: len(refs) <= 2, checkpoints=checkpoints)
    assert set(result) == {1, 4}
    wire.references = {i: {'source_id': 'a' if i <= 17 else str(i), 'locator': f'p{i}',
        'quote': f'Original passage {i}.'} for i in range(1, 20)}
    ranking(monkeypatch)
    result = await select_evidence(service(Selector(None)), wire, 'Compare the sources.', 60,
        fits=lambda refs: len(refs) <= 4)
    assert {1, 2} <= set(result) and set(result).intersection({18, 19})
    assert len({ref['source_id'] for ref in result.values()}) >= 2, 'Independent sources retain a chance despite one long source'


@pytest.mark.asyncio
async def test_literal_query_seed_prevents_crowded_topics_and_composite_vote_from_displacing_a_rare_group(monkeypatch):
    wire, checkpoints = corpus(6), {}
    before = deepcopy(wire.__dict__)
    ranking(monkeypatch, [
        {'query': wire.input['original_question'], 'references': [1, 2, 3, 4, 5, 6],
            'scores': {1: 1, 2: .99, 3: .98, 4: .97, 5: .96, 6: .05}},
        {'query': 'A zero-score query', 'references': [6], 'scores': {6: 0}},
        {'query': 'What capacity is available?', 'references': [2, 3, 1, 4, 5, 6],
            'scores': {2: 1, 3: .99, 1: .98, 4: .97, 5: .96, 6: .05}},
        {'query': 'An empty query', 'references': []},
        {'query': 'Which exception limits operation?', 'references': [6, 2, 3, 1, 4, 5],
            'scores': {6: 1, 2: .95, 3: .95, 1: .95, 4: .95, 5: .95}},
    ])
    attempted = []

    def fits(refs):
        attempted.append(tuple(refs))
        return len(refs) <= 2

    result = await select_evidence(service(Selector(None)), wire, wire.input['original_question'], 60,
        fits=fits, checkpoints=checkpoints)
    assert result == {key: wire.references[key] for key in (2, 6)}
    assert len(attempted) == len(set(attempted)), 'A rejected group is not yielded again for another query or refinement'
    assert wire.__dict__ == before
    assert checkpoints['retrieval_coverage']['all_originals_supplied'] is False
    assert checkpoints['retrieval_coverage']['absence_established'] is False


@pytest.mark.asyncio
async def test_query_seed_tries_next_whole_feasible_group_and_preserves_mandatory_context(monkeypatch):
    wire, checkpoints = corpus(5), {}
    wire.references[6] = {'source_id': 's1', 'locator': 'p2', 'quote': 'A mandatory qualification to the first observation.'}
    wire.references[2]['locator'] = 'page-2-text-1'
    wire.references[7] = {'source_id': 's2', 'locator': 'page-2-text-2', 'quote': 'The middle of this indivisible original page.'}
    wire.references[8] = {'source_id': 's2', 'locator': 'page-2-text-3', 'quote': 'The final qualification on the same original page.'}
    ranking(monkeypatch, [
        {'query': 'The main observation?', 'references': [1, 4, 2, 3, 5],
            'scores': {1: 1, 4: .8, 2: .1, 3: .1, 5: .01}},
        {'query': 'The independent exception?', 'references': [2, 3, 1, 4, 5],
            'scores': {2: 1, 3: .9, 1: .1, 4: .1, 5: .01}},
    ])
    attempts = []

    def fits(refs):
        attempts.append(set(refs))
        return len(refs) <= 4

    result = await select_evidence(service(Selector(None)), wire, wire.input['original_question'], 60,
        fits=fits, required_refs=(1,), checkpoints=checkpoints)
    assert result == {key: wire.references[key] for key in (1, 3, 4, 6)}
    assert {1, 2, 6, 7, 8} in attempts, 'The highest-ranked complete page is attempted without clipping'
    assert {1, 3, 6} in attempts, 'The next strongest feasible original can seed the unanswered query'
    assert not {2, 7, 8} & result.keys()
    assert checkpoints['retrieval_coverage']['required_references'] == 1
    assert checkpoints['retrieval_coverage']['absence_established'] is False


@pytest.mark.asyncio
async def test_single_query_keeps_a_second_relevant_opposing_original(monkeypatch):
    wire = corpus(3)
    wire.references[1]['quote'] = 'The reported effect increased in the first observation.'
    wire.references[2]['quote'] = 'An independent observation did not reproduce the reported increase.'
    wire.references[3]['quote'] = 'An unrelated publication heading.'
    ranking(monkeypatch, [{'query': 'Is the reported effect consistent?', 'references': [1, 2, 3],
        'scores': {1: 1, 2: .85, 3: .01}}])
    result = await select_evidence(service(Selector(None)), wire, wire.input['original_question'], 60,
        fits=lambda refs: len(refs) <= 2)
    assert set(result) == {1, 2}
    assert result[2]['quote'] == wire.references[2]['quote']


@pytest.mark.asyncio
async def test_splitting_one_pdf_page_into_more_lines_does_not_increase_its_relevance(monkeypatch):
    body = 'A complete passage with its original qualifications and conditions. ' * 10
    selected_sources = []
    for fragments in (1, 8):
        wire = corpus(2)
        offsets = [len(body) * index // fragments for index in range(fragments + 1)]
        wire.references = {index + 1: {'source_id': 's1', 'locator': f'page-1-text-{index + 1}-char-1',
            'quote': body[offsets[index]:offsets[index + 1]]} for index in range(fragments)}
        wire.references[100] = {'source_id': 's2', 'locator': 'page-2-text-1-char-1', 'quote': body}
        ranking(monkeypatch, [{'query': 'The requested finding and conditions', 'references': [100, *range(1, fragments + 1)],
            'scores': {key: .8 if key == 100 else .7 for key in wire.references}}])

        def measured(refs):
            return 10 + sum(len(ref['quote']) for ref in refs.values())

        result = await select_evidence(service(Selector(None), 10 + len(body)), wire, wire.input['original_question'], 60,
            request_size=measured)
        selected_sources.append({ref['source_id'] for ref in result.values()})
        assert result == {key: wire.references[key] for key in result}
    assert selected_sources == [{'s2'}, {'s2'}]


@pytest.mark.asyncio
async def test_a_second_relevant_passage_beats_unrelated_source_diversity(monkeypatch):
    wire = corpus(4)
    wire.references[2].update(source_id='s1', locator='separate-section')
    wire.input['sources'][0]['original_context']['captured_complete'] = False
    ranking(monkeypatch, [
        {'query': 'Observed change', 'references': [1, 3, 4, 2], 'scores': {1: 1, 3: .2, 4: .1, 2: 0}},
        {'query': 'Remaining uncertainty', 'references': [2, 3, 4, 1], 'scores': {2: 1, 3: .2, 4: .1, 1: 0}}])
    result = await select_evidence(service(Selector(None)), wire, wire.input['original_question'], 60,
        fits=lambda refs: len(refs) <= 2)
    assert set(result) == {1, 2}
    assert result == {key: wire.references[key] for key in result}


@pytest.mark.asyncio
@pytest.mark.parametrize('fragments', [1, 8])
async def test_a_long_general_guide_does_not_displace_distinct_requested_evidence(monkeypatch, fragments):
    wire = corpus(4)
    guide = 'General operating background. ' * 100
    offsets = [len(guide) * index // fragments for index in range(fragments + 1)]
    wire.references = {index + 1: {'source_id': 's1', 'locator': 'page-1-text-1-char-1',
        'quote': guide[offsets[index]:offsets[index + 1]]} for index in range(fragments)}
    for key, text in ((101, 'The permitted operating mode.'), (102, 'The notice required when equipment is changed.'),
            (103, 'The exception to the operating permission.')):
        wire.references[key] = {'source_id': f's{key - 99}', 'locator': 'p1', 'quote': text}
    rankings = [{'query': question, 'references': [key, *range(1, fragments + 1),
        *[other for other in (101, 102, 103) if other != key]],
        'scores': {ref: 1 if ref == key else .35 if ref < 100 else 0 for ref in wire.references}}
        for key, question in ((101, 'What operation is permitted?'), (102, 'Which notice is required?'),
            (103, 'When does the permission not apply?'))]
    ranking(monkeypatch, rankings)

    def measured(refs):
        # The guide and each requested clause are complete originals. Either
        # the guide or all three clauses fit; adding volume must not win a
        # larger share of the user's independently requested distinctions.
        return 100 + sum(700 / fragments if key < 100 else 250 for key in refs)

    before = deepcopy(wire.__dict__)
    checkpoints = {}
    selected = await select_evidence(service(Selector(None), 1000), wire, 'Explain the permission, notice and exception.',
        60, request_size=measured, checkpoints=checkpoints)
    assert set(selected) == {101, 102, 103}
    assert selected == {key: wire.references[key] for key in selected} and wire.__dict__ == before
    assert checkpoints['retrieval_coverage']['absence_established'] is False
    assert not checkpoints['retrieval_coverage']['all_originals_supplied']


@pytest.mark.asyncio
async def test_navigation_relevance_retrieves_the_bound_original_body(monkeypatch):
    from helvetic_lens import research_evidence_pack
    wire = corpus(3)
    wire.references[1]['quote'] = 'When does the authorization end?'
    wire.references[2].update(source_id='s1', locator='p2',
        quote='The authorization ends only if the listed triggering event occurs.')
    wire.references[3]['quote'] = 'An independently relevant background paragraph.'
    units = [
        {'primary': [1], 'ranking_refs': [], 'references': {1: wire.references[1]}, 'source_id': 's1'},
        {'primary': [2], 'ranking_refs': [1, 2], 'references': {key: wire.references[key] for key in (1, 2)}, 'source_id': 's1'},
        {'primary': [3], 'references': {3: wire.references[3]}, 'source_id': 's3'}]
    monkeypatch.setattr(research_evidence_pack, '_units', lambda current: units)
    ranking(monkeypatch, [{'query': 'When does the authorization end?', 'references': [1, 3],
        'scores': {1: 1, 3: .2}}])
    result = await select_evidence(service(Selector(None)), wire, wire.input['original_question'], 60,
        fits=lambda refs: len(refs) <= 2)
    assert result == {key: wire.references[key] for key in (1, 2)}
    assert result[2]['quote'].startswith('The authorization ends only if')


@pytest.mark.asyncio
@pytest.mark.parametrize('required', [(), (1,)])
async def test_unrankable_navigation_is_only_retained_when_explicitly_required(monkeypatch, required):
    from helvetic_lens import research_evidence_pack
    wire = corpus(2)
    units = [{'primary': [1], 'ranking_refs': [], 'references': {1: wire.references[1]}, 'source_id': 's1'},
        {'primary': [2], 'references': {2: wire.references[2]}, 'source_id': 's2'}]
    monkeypatch.setattr(research_evidence_pack, '_units', lambda current: units)
    ranking(monkeypatch, [{'query': 'The requested distinction', 'references': [1, 2], 'scores': {1: 1, 2: .2}}])
    result = await select_evidence(service(Selector(None)), wire, wire.input['original_question'], 60,
        fits=lambda refs: len(refs) <= 1, required_refs=required)
    expected = 1 if required else 2
    assert result == {expected: wire.references[expected]}


@pytest.mark.asyncio
@pytest.mark.parametrize('require_navigation', [False, True])
async def test_small_structured_wire_preserves_body_without_ordinary_navigation_citations(monkeypatch, require_navigation):
    from helvetic_lens.extraction import extract
    from helvetic_lens.product_exploration import Briefing
    from helvetic_lens.product_research_mission import schema as mission_schema
    from helvetic_lens.research_model_transport import EvidenceWire

    html = b'<main><p><a href="#conditions">See operating conditions</a></p><h2 id="conditions">Operating conditions</h2><p>Operation is permitted only after inspection.</p></main>'
    source = {'id': 's1', 'sha256': 'a' * 64, 'url': 'https://example.test/manual', 'title': 'Manual',
        'excerpts': [{'passage': p['id'], 'text': p['text'], 'html_structure': p['html_structure']}
            for p in extract(html, 'text/html').passages]}
    wire = EvidenceWire({'phase': 'brief', 'input': {'original_question': 'When is operation permitted?',
        'sources': [source], 'research_mission': {}}}, mission_schema(Briefing), '')
    nav = next(key for key, ref in wire.references.items() if ref['quote'] == 'See operating conditions')
    original = deepcopy(wire.references)

    async def unexpected(*args, **kwargs):
        pytest.fail('A complete eligible structural packet needs no ranking or encoder call')
    monkeypatch.setattr('helvetic_lens.research_active_retrieval.rank_evidence', unexpected)
    checkpoints = {}
    selected = await select_evidence(service(Selector(None), 24000), wire, wire.input['original_question'], 0,
        required_refs=[nav] if require_navigation else [], checkpoints=checkpoints)
    expected = original if require_navigation else {key: ref for key, ref in original.items() if key != nav}
    assert selected == expected and wire.references == original
    projected = provider_input(wire, selected)
    supplied_ids = {p['citation_ref'] for source in projected['sources'] for p in source['excerpts'] if 'citation_ref' in p}
    assert (nav in supplied_ids) is require_navigation
    assert any(ref['quote'] == 'Operation is permitted only after inspection.' for ref in selected.values())
    assert checkpoints['retrieval_coverage']['all_originals_supplied'] is require_navigation
    assert checkpoints['retrieval_coverage']['absence_established'] is False


@pytest.mark.asyncio
@pytest.mark.parametrize('required', [(), (1,)])
async def test_actual_envelope_cost_preserves_complementary_question_evidence_and_mandatory_units(monkeypatch, required):
    wire = corpus(3)
    ranking(monkeypatch, [
        {'query': 'Observed change', 'references': [1, 2, 3], 'scores': {1: 1, 2: .95, 3: 0}},
        {'query': 'Remaining uncertainty', 'references': [3, 1, 2], 'scores': {3: 1, 1: 0, 2: 0}}])
    costs = {1: 75, 2: 20, 3: 50}
    calls = []

    def measured(refs):
        calls.append(tuple(refs))
        return 10 + sum(costs[key] for key in refs)

    result = await select_evidence(service(Selector(None), 100), wire, wire.input['original_question'], 60,
        request_size=measured, required_refs=required)
    assert set(result) == ({1} if required else {2, 3})
    assert measured(result) <= 100
    assert all(ref == wire.references[key] for key, ref in result.items())
    assert len(calls) < 12, 'Priority ordering must not serialize every candidate union repeatedly'


@pytest.mark.asyncio
async def test_completed_pack_resumes_after_pause_without_reranking(monkeypatch):
    wire, checkpoints = corpus(), {}
    seen = ranking(monkeypatch)
    def pause():
        raise RuntimeError('Native pause after persisted pack')
    with pytest.raises(RuntimeError, match='Native pause'):
        await select_evidence(service(Selector(None)), wire, wire.input['original_question'], 60,
            checkpoints=checkpoints, on_progress=pause, fits=lambda refs: len(refs) <= 2)
    saved = next(value for value in checkpoints['evidence_selection'].values() if value['policy_fingerprint'] == POLICY)
    assert saved['status'] == 'complete' and len(saved['selected']) == 2
    result = await select_evidence(service(Selector(None)), wire, wire.input['original_question'], 0,
        checkpoints=json.loads(json.dumps(checkpoints)), fits=lambda refs: len(refs) <= 2)
    assert list(result) == saved['selected'] and len(seen) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('changed', ['question', 'quote', 'hash', 'retrieval_policy', 'packing_policy', 'required', 'cost'])
async def test_cache_binds_current_originals_scope_policy_and_actual_cost(monkeypatch, changed):
    from helvetic_lens import research_active_retrieval, research_evidence_pack
    wire, checkpoints = corpus(), {}
    seen = ranking(monkeypatch)
    question, required, overhead = wire.input['original_question'], (), 5000
    def measured(refs):
        return overhead + sum(len(ref['quote']) for ref in refs.values())
    await select_evidence(service(Selector(None)), wire, question, 60, checkpoints=checkpoints, request_size=measured)
    if changed == 'question':
        question = 'A different requested distinction.'
    elif changed == 'quote':
        wire.references[1]['quote'] += ' A newly captured qualification.'
    elif changed == 'hash':
        wire.input['sources'][0]['sha256'] = 'new-original-capture'
    elif changed == 'retrieval_policy':
        monkeypatch.setattr(research_active_retrieval, 'POLICY', 'changed-local-retrieval-policy')
    elif changed == 'packing_policy':
        monkeypatch.setattr(research_evidence_pack, 'POLICY', 'changed-structural-packing-policy')
    elif changed == 'required':
        required = (10,)
    else:
        overhead = 6000
    await select_evidence(service(Selector(None)), wire, question, 60, checkpoints=checkpoints,
        request_size=measured, required_refs=required)
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_cached_pack_cannot_lose_a_complete_context_group(monkeypatch):
    wire, checkpoints = corpus(10), {}
    wire.references[11] = {'source_id': 's1', 'locator': 'exception', 'quote': 'The original has an exception.'}
    seen = ranking(monkeypatch)
    first = await select_evidence(service(Selector(None)), wire, 'The original and its exception.', 60,
        checkpoints=checkpoints, fits=lambda refs: len(refs) <= 2)
    assert set(first) == {1, 11}
    node = next(iter(checkpoints['evidence_selection'].values()))
    node['selected'].remove(11)
    second = await select_evidence(service(Selector(None)), wire, 'The original and its exception.', 60,
        checkpoints=checkpoints, fits=lambda refs: len(refs) <= 2)
    assert second == first and len(seen) == 2


@pytest.mark.asyncio
async def test_required_witnesses_precede_ranking_and_keep_all_their_context(monkeypatch):
    wire, checkpoints = corpus(40), {}
    wire.references[41] = {'source_id': 's40', 'locator': 'p2', 'quote': 'This late exception qualifies the earlier result.'}
    ranking(monkeypatch, [{'query': 'whole question', 'references': list(range(2, 40))}])
    def measured(refs):
        return 5000 + sum(len(ref['quote']) + 100 for ref in refs.values())
    result = await select_evidence(service(Selector(None), 11000), wire, wire.input['original_question'], 60,
        request_size=measured, required_refs=(1, 40), checkpoints=checkpoints)
    assert {1, 40, 41} <= set(result) and measured(result) <= 11000
    assert all(ref == wire.references[key] for key, ref in result.items())
    assert checkpoints['retrieval_coverage']['required_references'] == 2


@pytest.mark.asyncio
async def test_mandatory_context_cannot_be_dropped_to_fit(monkeypatch):
    wire = corpus(4)
    seen = ranking(monkeypatch)
    with pytest.raises(DomainError) as error:
        await select_evidence(service(Selector(None)), wire, 'Compare originals.', 60,
            fits=lambda refs: len(refs) <= 1, required_refs=(1, 4))
    assert error.value.code == 'research_evidence_group_too_large' and not seen


@pytest.mark.asyncio
@pytest.mark.parametrize('invalid', [0, 9999, True, 1.0, '1'])
async def test_foreign_or_noninteger_local_rank_ids_are_not_accepted(monkeypatch, invalid):
    wire, checkpoints = corpus(), {}
    ranking(monkeypatch, [{'query': 'whole question', 'references': [invalid]}])
    with pytest.raises(DomainError) as error:
        await select_evidence(service(Selector(None)), wire, wire.input['original_question'], 60, checkpoints=checkpoints)
    assert (error.value.status, error.value.code) == (503, 'research_evidence_pack_incomplete')
    assert not checkpoints['evidence_selection']


@pytest.mark.asyncio
async def test_oversized_optional_group_is_named_and_retained_without_blocking_useful_pack(monkeypatch):
    wire, checkpoints = corpus(), {}
    wire.references[1]['quote'] = 'An indivisible exact original. ' * 2000
    ranking(monkeypatch)
    result = await select_evidence(service(Selector(None)), wire, wire.input['original_question'], 60, checkpoints=checkpoints)
    assert 1 not in result and wire.references[1]['quote'].endswith('original. ')
    assert result and checkpoints['retrieval_coverage']['groups_not_fitting'] > 0
    assert checkpoints['retrieval_coverage']['absence_established'] is False


@pytest.mark.asyncio
async def test_lexical_fallback_and_empty_rankings_never_claim_semantic_or_absence(monkeypatch):
    wire, checkpoints = corpus(), {}
    ranking(monkeypatch, [], semantic_status='unavailable')
    assert await select_evidence(service(Selector(None)), wire, 'Find a missing distinction.', 60, checkpoints=checkpoints) == {}
    coverage = checkpoints['retrieval_coverage']
    assert coverage['method'] == 'bm25_graph' and coverage['semantic_status'] == 'unavailable'
    assert coverage['examined_records'] == len(wire.references) and coverage['absence_established'] is False
    empty_schema = bounded_schema(wire.schema, {})
    assert empty_schema['properties']['points']['maxItems'] == 0
    assert empty_schema['properties']['points']['minItems'] == 0
    assert wire.schema['properties']['points']['minItems'] == 1


@pytest.mark.asyncio
async def test_adapter_deadline_keeps_private_preparation_receipts_without_final_pack(monkeypatch):
    from helvetic_lens import research_active_retrieval
    wire, checkpoints = corpus(), {}
    async def interrupted(service, wire, question, seconds, *, checkpoints, on_progress):
        checkpoints['evidence_selection']['prepared'] = {'status': 'complete', 'input_fingerprint': 'input',
            'policy_fingerprint': research_active_retrieval.POLICY, 'selected': [1]}
        if on_progress:
            on_progress()
        raise DomainError('Local preparation remains incomplete.', 503, 'research_evidence_pack_incomplete')
    monkeypatch.setattr(research_active_retrieval, 'rank_evidence', interrupted)
    progress = []
    with pytest.raises(DomainError) as error:
        await select_evidence(service(Selector(None)), wire, wire.input['original_question'], 60,
            checkpoints=checkpoints, on_progress=lambda: progress.append(True))
    assert error.value.code == 'research_evidence_pack_incomplete' and progress == [True]
    assert set(checkpoints['evidence_selection']) == {'prepared'} and 'retrieval_coverage' not in checkpoints


@pytest.mark.asyncio
@pytest.mark.parametrize('path', ['complete', 'cached', 'new_pack'])
async def test_access_is_rechecked_before_every_return(monkeypatch, path):
    from helvetic_lens import research_active_retrieval
    wire, checkpoints = corpus(2 if path == 'complete' else 10), {}
    seen = ranking(monkeypatch)
    if path == 'cached':
        await select_evidence(service(Selector(None)), wire, wire.input['original_question'], 60, checkpoints=checkpoints)
    calls = len(seen)

    async def withdrawn(service, wire):
        raise DomainError('Current source access was withdrawn.', 409, 'evidence_changed')
    monkeypatch.setattr(research_active_retrieval, 'ensure_current', withdrawn)
    with pytest.raises(DomainError) as error:
        await select_evidence(service(Selector(None)), wire, wire.input['original_question'], 60, checkpoints=checkpoints)
    assert error.value.code == 'evidence_changed'
    assert len(seen) == calls + int(path == 'new_pack')
