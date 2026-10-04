"""Completed reading guides exact whole-original selection, never claim approval."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_research_evidence_pack import ranking

from helvetic_lens.product_exploration import Briefing
from helvetic_lens.product_research_mission import schema
from helvetic_lens.research_evidence_pack import provider_sources, select_evidence
from helvetic_lens.research_model_transport import EvidenceWire
from helvetic_lens.research_reading_context import CONTRACT

QUESTION = 'Which renewal rules and cancellation rules apply?'


def source(index, *, role=None):
    identifier = f'source-{index}'
    passage = {'passage': 'page-1-text-1', 'text': f'Original {index}: the archive records its applicable rules and conditions.'}
    value = {'id': identifier, 'sha256': str(index) * 64, 'url': f'https://example.test/original-{index}',
        'title': f'Original {index}', 'excerpts': [passage]}
    if role:
        value['reading_context'] = {'contract': CONTRACT, 'question': QUESTION, 'investigation_id': 'run',
            'notes': [{'interpretation': f'Fallible reading of original {index}, requiring original verification.',
                'role': role, 'level': 'document', 'original': {'source_id': identifier, 'sha256': value['sha256'],
                    'locator': passage['passage'], 'quote': passage['text']}, 'anchors': []}]}
    return value


def wire_for(sources):
    return EvidenceWire({'phase': 'brief', 'run_id': 'run', 'input': {'original_question': QUESTION,
        'sources': sources, 'research_mission': {}}}, schema(Briefing), '', retrieve_originals=True)


def runtime(allowance):
    return SimpleNamespace(settings=SimpleNamespace(apertus_context_chars=allowance))


def test_wire_preserves_all_reading_roles_without_making_interpretations_citations():
    sources = [source(index, role=role) for index, role in enumerate(('support', 'counterevidence', 'context'), 1)]
    before = deepcopy(sources)
    wire = wire_for(sources)
    assert wire.reading_anchor_refs == [1, 2, 3]
    assert {note['role'] for notes in wire.reading_context.values() for note in notes} == {'support', 'counterevidence', 'context'}
    assert all('reading_context' not in original for original in wire.input['sources'])
    assert {ref['quote'] for ref in wire.references.values()} == {s['excerpts'][0]['text'] for s in before}
    assert sources == before
    groups = provider_sources(wire, wire.references)
    assert all(group['reading_notes'][0]['original_citation_refs'] == [index] for index, group in enumerate(groups, 1))
    assert all('pointers' in group['reading_scope'].lower() for group in groups)
    assert all('scope' not in note for group in groups for note in group['reading_notes'])
    assert all('Fallible reading' not in ref['quote'] for ref in wire.references.values())
    assert all('approval' not in group['reading_notes'][0] for group in groups)


@pytest.mark.asyncio
async def test_query_seeds_preserve_read_context_then_other_evidence_and_mandatory_originals(monkeypatch):
    wire = wire_for([source(1, role='context'), source(2, role='counterevidence'), *[source(i) for i in range(3, 7)]])
    before = deepcopy(wire.references)
    calls = ranking(monkeypatch, [
        {'query': 'Which renewal rules apply?', 'references': [3, 1, 4], 'scores': {3: 1, 1: .8, 4: .5}},
        {'query': 'Which cancellation rules apply?', 'references': [3, 2, 4], 'scores': {3: 1, 2: .8, 4: .5}}])
    attempts, saved = [], {}

    def fits(refs):
        attempts.append(set(refs))
        return len(refs) <= 4

    selected = await select_evidence(runtime(400), wire, QUESTION, 20, checkpoints=saved,
        fits=fits, request_size=lambda refs: len(refs) * 100, required_refs=[6])
    accepted = [item for item in attempts if 1 < len(item) <= 4]
    assert accepted[:2] == [{1, 6}, {1, 2, 6}]
    assert set(selected) == {1, 2, 3, 6}, 'Reading anchors do not exclude independent unannotated evidence'
    assert calls[0]['references'] == before == wire.references
    assert saved['retrieval_coverage']['absence_established'] is False


@pytest.mark.asyncio
async def test_oversized_reading_anchor_uses_next_feasible_whole_group_without_repeated_rejection(monkeypatch):
    original = source(1, role='context')
    original['excerpts'].append({'passage': 'page-1-text-2', 'text': 'The same page contains a required qualifying exception.'})
    wire = wire_for([original, source(2, role='counterevidence'), source(3), source(4)])
    # Canonical 1+2 are one physical page, 3 is the alternative reading, 5 mandatory.
    ranking(monkeypatch, [{'query': QUESTION, 'references': [1, 3, 4], 'scores': {1: 1, 3: .8, 4: .5}}])
    attempts, saved = [], {}

    def fits(refs):
        attempts.append(frozenset(refs))
        return len(refs) <= 2

    selected = await select_evidence(runtime(200), wire, QUESTION, 20, checkpoints=saved,
        fits=fits, request_size=lambda refs: len(refs) * 100, required_refs=[5])
    assert set(selected) == {3, 5}
    assert attempts.count(frozenset({1, 2, 5})) == 1
    assert saved['retrieval_coverage']['groups_not_fitting'] >= 1
    assert wire.references[2]['quote'] == original['excerpts'][1]['text'], 'An optional oversized page remains retained'


@pytest.mark.asyncio
async def test_reading_query_fairness_keeps_two_feasible_independent_requests(monkeypatch):
    wire = wire_for([source(index, role='context') for index in range(1, 4)] + [source(4)])
    ranking(monkeypatch, [
        {'query': 'Which renewal rules apply?', 'references': [1, 2], 'scores': {1: 1, 2: .8}},
        {'query': 'Which cancellation rules apply?', 'references': [3], 'scores': {3: 1}}])
    costs = {1: 75, 2: 20, 3: 50, 4: 100}

    def size(refs):
        return sum(costs[key] for key in refs)

    selected = await select_evidence(runtime(90), wire, QUESTION, 20,
        fits=lambda refs: size(refs) <= 90, request_size=size)
    assert set(selected) == {2, 3}, 'One large anchor must not spend the other literal request’s only feasible space'


@pytest.mark.asyncio
async def test_reading_qualification_keeps_whole_distant_original_unit(monkeypatch):
    original = source(1, role='context')
    qualifier = {'passage': 'page-9-text-1', 'text': 'The renewal rule applies only to deposits made after the recorded date.'}
    original['excerpts'].extend([qualifier, {'passage': 'page-9-text-2', 'text': 'Existing deposits retain their previously agreed renewal schedule.'}])
    original['reading_context']['notes'][0]['anchors'] = [{'kind': 'condition', 'source_id': original['id'],
        'sha256': original['sha256'], 'locator': qualifier['passage'], 'quote': qualifier['text']}]
    wire = wire_for([original, source(2), source(3)])
    assert wire.reading_anchor_refs == [1], 'A linked qualifier does not acquire its own relevance vote'
    ranking(monkeypatch, [{'query': QUESTION, 'references': [4, 1], 'scores': {4: 1, 1: .7}}])
    selected = await select_evidence(runtime(300), wire, QUESTION, 20,
        fits=lambda refs: len(refs) <= 3, request_size=lambda refs: len(refs) * 100)
    assert set(selected) == {1, 2, 3}, 'The distant qualifier travels with its complete page'
    assert provider_sources(wire, selected)[0]['reading_notes'][0]['context_anchors']


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['interpretation', 'membership'])
async def test_saved_packet_binds_reading_context_and_rechecks_access(monkeypatch, change):
    from helvetic_lens import research_active_retrieval as retrieval

    wire = wire_for([source(1, role='context'), source(2), source(3)])
    calls = ranking(monkeypatch, [{'query': QUESTION, 'references': [2, 1, 3], 'scores': {2: 1, 1: .8, 3: .5}}])
    checks = []

    async def current(service, candidate):
        checks.append(True)

    monkeypatch.setattr(retrieval, 'ensure_current', current)
    saved = {}
    options = {'checkpoints': saved, 'fits': lambda refs: len(refs) <= 1,
        'request_size': lambda refs: len(refs) * 100, 'envelope_binding': {'system': 'unchanged', 'schema': 'unchanged'}}
    first = await select_evidence(runtime(100), wire, QUESTION, 20, **options)
    assert set(first) == {1}
    assert await select_evidence(runtime(100), wire, QUESTION, 20, **options) == first
    assert len(calls) == 1 and len(checks) == 2
    if change == 'interpretation':
        wire.reading_context['source-1'][0]['interpretation'] = 'A revised fallible reading.'
    else:
        wire.reading_context, wire.reading_anchor_refs = {}, []
    updated = await select_evidence(runtime(100), wire, QUESTION, 20, **options)
    assert len(calls) == 2 and len(checks) == 3
    assert set(updated) == ({1} if change == 'interpretation' else {2})


def test_unannotated_legacy_corpus_keeps_its_original_projection():
    wire = wire_for([source(1)])
    assert wire.reading_context == {} and wire.reading_anchor_refs == []
    assert 'reading_notes' not in provider_sources(wire, wire.references)[0]
