"""HTML retrieval uses addressed original bodies and their complete structure."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens.config import DomainError
from helvetic_lens.extraction import extract
from helvetic_lens.product_exploration import Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_evidence_pack import select_evidence
from helvetic_lens.research_model_transport import EvidenceWire
from helvetic_lens.research_original_context import (
    contextual_references,
    expand_sources,
    provider_excerpts,
    reference_units,
)


def original(body, *, identifier='s1', sha='a' * 64, url='https://example.test/manual'):
    return {'id': identifier, 'sha256': sha, 'url': url, 'title': 'Original manual',
        'excerpts': [{'passage': item['id'], 'text': item['text'],
            'html_structure': item['html_structure']} for item in extract(body.encode(), 'text/html').passages]}


def wire_for(sources):
    return EvidenceWire({'phase': 'brief', 'input': {'original_question': 'Which conditions govern measurement?',
        'sources': sources, 'research_mission': {}}}, mission_schema(Briefing), '', shared_answer=True)


def addressed_original():
    return original('<main><p><a href="#conditions">Measurement conditions</a></p>'
        '<h2 id="conditions">Conditions</h2><dl><dt>Q1:</dt>'
        '<dd>When can the specimen be measured?</dd><dt>A1:</dt>'
        '<dd>Only after calibration under every condition specified in the dated protocol.</dd>'
        '<dt>A2:</dt><dd>No.</dd></dl><h2>Other records</h2>'
        '<p>Retain the maintenance record separately.</p></main>')


def ref_with(wire, text):
    return next(key for key, ref in wire.references.items() if ref['quote'] == text)


def test_navigation_ranks_complete_body_while_short_labels_remain_uncitable_context():
    source = addressed_original()
    before = deepcopy(source)
    wire = wire_for([source])
    nav = ref_with(wire, 'Measurement conditions')
    heading = ref_with(wire, 'Conditions')
    question = ref_with(wire, 'When can the specimen be measured?')
    answer = ref_with(wire, 'Only after calibration under every condition specified in the dated protocol.')
    units = reference_units(wire)
    body = next(unit for unit in units if question in unit['primary'])
    assert set(body['primary']) == {question, answer}
    assert set(body['ranking_refs']) == {nav, heading, question, answer}
    assert set(body['references']) == {heading, question, answer}
    assert nav not in body['references']
    projected = provider_excerpts(wire, body['references'])['s1']
    assert [item['text'] for item in projected] == [p['text'] for p in source['excerpts'][1:8]]
    assert all('citation_ref' not in item for item in projected if item['text'] in {'Q1:', 'A1:', 'A2:', 'No.'})
    assert contextual_references(wire, [answer]) == body['references']
    mandatory = next(unit for unit in units if nav in unit['primary'])
    assert mandatory['ranking_refs'] == [] and set(mandatory['references']) == {nav, heading, question, answer}
    assert source == before


@pytest.mark.asyncio
async def test_selected_toc_hit_supplies_answer_originals_without_toc_citation(monkeypatch):
    wire = wire_for([addressed_original()])
    nav = ref_with(wire, 'Measurement conditions')
    answer = ref_with(wire, 'Only after calibration under every condition specified in the dated protocol.')
    unit = next(unit for unit in reference_units(wire) if answer in unit['primary'])

    async def rank(*args, **kwargs):
        return {'rankings': [{'query': 'Which conditions govern measurement?', 'references': [nav],
            'scores': {nav: 1}}], 'coverage': {'method': 'fixture_exact_navigation'}}

    monkeypatch.setattr('helvetic_lens.research_active_retrieval.rank_evidence', rank)
    service = SimpleNamespace(settings=SimpleNamespace(apertus_context_chars=24000))
    selected = await select_evidence(service, wire, wire.input['original_question'], 1,
        fits=lambda refs: len(refs) <= len(unit['references']))
    assert selected == unit['references'] and answer in selected and nav not in selected


@pytest.mark.parametrize('change', ['sha', 'url', 'withdrawal'])
def test_structure_cannot_cross_changed_original_or_withdrawn_portion(change):
    source = addressed_original()
    head = {**source, 'id': 'head', 'excerpts': source['excerpts'][:2]}
    body = {**source, 'id': 'body', 'excerpts': source['excerpts'][2:8]}
    valid = wire_for([head, body])
    answer = ref_with(valid, 'Only after calibration under every condition specified in the dated protocol.')
    assert {ref['source_id'] for ref in contextual_references(valid, [answer]).values()} == {'head', 'body'}
    changed = deepcopy(body)
    if change == 'sha':
        changed['sha256'] = 'b' * 64
    elif change == 'url':
        changed['url'] = 'https://example.test/another'
    wire = wire_for([head] if change == 'withdrawal' else [head, changed])
    nav = ref_with(wire, 'Measurement conditions')
    assert all(nav not in unit.get('ranking_refs', unit['primary']) for unit in reference_units(wire))
    assert {ref['source_id'] for ref in contextual_references(wire, [nav]).values()} == {'head'}


def test_structural_compaction_restores_exact_heading_body_and_nonadjacent_short_labels():
    source = addressed_original()
    selected = [{**source, 'excerpts': [source['excerpts'][3]]}]
    expanded = expand_sources(selected, [source])
    assert expanded[0]['excerpts'] == source['excerpts'][1:8]
    assert expanded[0]['original_context']['captured_complete'] is False
    nav_expanded = expand_sources([{**source, 'excerpts': source['excerpts'][:1]}], [source])
    assert nav_expanded[0]['excerpts'] == source['excerpts'][:8]


@pytest.mark.asyncio
async def test_mandatory_html_body_or_navigation_cannot_drop_complete_group_to_fit():
    wire = wire_for([addressed_original()])
    service = SimpleNamespace(settings=SimpleNamespace(apertus_context_chars=24000))
    before = deepcopy(wire.references)
    for text in ('Measurement conditions', 'Only after calibration under every condition specified in the dated protocol.'):
        with pytest.raises(DomainError) as caught:
            await select_evidence(service, wire, 'Explain the conditions.', 0,
                required_refs=[ref_with(wire, text)], fits=lambda refs: len(refs) <= 1)
        assert caught.value.code == 'research_evidence_group_too_large'
    assert wire.references == before


def test_local_writer_ids_keep_html_context_and_unresolved_navigation_cannot_rank():
    source = addressed_original()
    source['excerpts'][0]['html_structure']['target_group_ids'] = ['missing']
    wire = wire_for([source])
    answer = ref_with(wire, 'Only after calibration under every condition specified in the dated protocol.')
    unit = next(unit for unit in reference_units(wire) if answer in unit['primary'])
    local = {index: ref for index, ref in enumerate(reversed(unit['references'].values()), 41)}
    projected = provider_excerpts(wire, local)['s1']
    assert {item['citation_ref'] for item in projected if 'citation_ref' in item} == set(local)
    assert 'A1:' in {item['text'] for item in projected}
    nav = ref_with(wire, 'Measurement conditions')
    assert all(nav not in item.get('ranking_refs', item['primary']) for item in reference_units(wire))


def test_explicit_malformed_structure_fails_without_reinterpreting_it_as_legacy():
    source = addressed_original()
    source['excerpts'][0]['html_structure']['group_ids'] = 'a different group'
    with pytest.raises(ValueError, match='Invalid original HTML structure'):
        reference_units(wire_for([source]))
