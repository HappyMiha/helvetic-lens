"""Ancestor context is required source material, not sibling membership or proof."""
from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_research_html_context import original, ref_with, wire_for
from test_research_retained_html import capture

from helvetic_lens.config import DomainError
from helvetic_lens.html_document_structure import HTML_STRUCTURE_VERSION
from helvetic_lens.research_evidence_pack import select_evidence
from helvetic_lens.research_html_structure import enrich
from helvetic_lens.research_original_context import (
    contextual_references,
    expand_sources,
    provider_excerpts,
    reference_units,
)

INTRO = 'This manual applies to laboratory operators working with research specimens.'
PARENT = 'For frozen specimens use the cold enclosure; other specimens use the standard enclosure.'
CHILD = 'Keep a dated measurement record with every specimen.'
SIBLING = 'Send maintenance invoices to the purchasing office.'


def manual():
    return original(f'<main><p>{INTRO}</p><h1>Specimen manual</h1>'
        '<p>Follow the protocol for the recorded specimen category.</p>'
        f'<h2>Measurement documentation</h2><p>{PARENT}</p>'
        f'<h3>Records</h3><p>{CHILD}</p>'
        f'<h3>Accounts</h3><p>{SIBLING}</p>'
        '<h2>Storage and disposal</h2><p>Dispose of expired specimens separately.</p></main>')


def test_selected_child_keeps_ancestor_direct_prose_without_sibling_or_ranking_votes():
    source = manual()
    before = deepcopy(source)
    wire = wire_for([source])
    child, intro, parent, sibling = [ref_with(wire, text) for text in (CHILD, INTRO, PARENT, SIBLING)]
    unit = next(unit for unit in reference_units(wire) if child in unit['primary'])
    assert unit['primary'] == [child]
    assert {intro, parent, child} <= set(unit['references'])
    assert sibling not in unit['references']
    assert {intro, parent}.isdisjoint(unit['ranking_refs'])
    projected = provider_excerpts(wire, unit['references'])['s1']
    assert 'Records' in {passage['text'] for passage in projected}  # short, uncitable heading
    assert not any('expired specimens' in passage['text'] for passage in projected)
    assert contextual_references(wire, [child]) == unit['references']
    selected = [{**source, 'excerpts': [source['excerpts'][6]]}]
    assert expand_sources(selected, [source])[0]['excerpts'] == source['excerpts'][:7]
    assert source == before


def test_repeated_and_skipped_heading_levels_keep_only_real_ancestors():
    source = original('<main><h1>Measurement protocol</h1><p>Only calibrated instruments are covered.</p>'
        '<h3>First measurement category</h3><p>The first category uses the earlier baseline.</p>'
        '<h3>Second measurement category</h3><p>The second category uses the dated baseline.</p>'
        '<h5>Reported results</h5><p>Report the result with the observation date.</p>'
        '<h3>Third measurement category</h3><p>The third category has separate limits.</p></main>')
    wire = wire_for([source])
    refs = contextual_references(wire, [ref_with(wire, 'Report the result with the observation date.')])
    texts = {ref['quote'] for ref in refs.values()}
    assert 'Only calibrated instruments are covered.' in texts
    assert 'The second category uses the dated baseline.' in texts
    assert 'The first category uses the earlier baseline.' not in texts
    assert 'The third category has separate limits.' not in texts


@pytest.mark.parametrize('boundary', ['article', 'section', 'details'])
def test_explicit_boundary_preamble_and_heading_stack_do_not_leak_to_siblings(boundary):
    source = original(f'<main><p>{INTRO}</p><h1>Protocol scope</h1><p>Use the dated protocol.</p>'
        f'<{boundary}><p>This section applies only to frozen specimens.</p>'
        '<h2>Local conditions</h2><p>Record the enclosure temperature.</p>'
        '<h3>Measurement procedure</h3><p>Measure after the stated conditioning period.</p>'
        f'</{boundary}><{boundary}><p>This section applies only to fresh specimens.</p>'
        '<h2>Other conditions</h2><p>Use the specified room-temperature procedure.</p>'
        f'</{boundary}></main>')
    wire = wire_for([source])
    frozen = contextual_references(wire, [ref_with(wire, 'Measure after the stated conditioning period.')])
    texts = {ref['quote'] for ref in frozen.values()}
    assert {INTRO, 'Use the dated protocol.', 'This section applies only to frozen specimens.',
        'Record the enclosure temperature.'} <= texts
    assert not any('fresh specimens' in text or 'room-temperature' in text for text in texts)
    fresh = contextual_references(wire, [ref_with(wire, 'Use the specified room-temperature procedure.')])
    assert not any('frozen specimens' in ref['quote'] or 'enclosure temperature' in ref['quote']
        for ref in fresh.values())


@pytest.mark.parametrize('changed', [None, 'sha', 'url', 'withdrawn'])
def test_directional_dependencies_only_use_available_same_original_portions(changed):
    source = manual()
    context = {**source, 'id': 'context', 'excerpts': source['excerpts'][:5]}
    child = {**source, 'id': 'child', 'excerpts': source['excerpts'][5:7]}
    if changed == 'sha':
        context['sha256'] = 'b' * 64
    elif changed == 'url':
        context['url'] = 'https://example.test/other-original'
    wire = wire_for([child] if changed == 'withdrawn' else [context, child])
    refs = contextual_references(wire, [ref_with(wire, CHILD)])
    assert ('context' in {ref['source_id'] for ref in refs.values()}) is (changed is None)
    assert all(ref == wire.references[key] for key, ref in refs.items())


@pytest.mark.asyncio
async def test_required_child_cost_includes_whole_inherited_context_before_selection(monkeypatch):
    wire = wire_for([manual()])
    child = ref_with(wire, CHILD)
    expected = contextual_references(wire, [child])
    service = SimpleNamespace(settings=SimpleNamespace(apertus_context_chars=24000))

    async def rank(*_args, **_kwargs):
        return {'rankings': [{'query': 'Explain the record requirements.', 'references': [child],
            'scores': {child: 1}}], 'coverage': {'method': 'fixture_exact_child'}}

    monkeypatch.setattr('helvetic_lens.research_active_retrieval.rank_evidence', rank)
    with pytest.raises(DomainError) as caught:
        await select_evidence(service, wire, 'Explain the record requirements.', 0,
            required_refs=[child], fits=lambda refs: len(refs) < len(expected))
    assert caught.value.code == 'research_evidence_group_too_large'
    supplied = await select_evidence(service, wire, 'Explain the record requirements.', 0,
        required_refs=[child], fits=lambda refs: len(refs) <= len(expected))
    assert supplied == expected


@pytest.mark.asyncio
@pytest.mark.parametrize('bytes_available', [True, False])
async def test_enrichment_upgrades_v1_only_from_exact_retained_bytes(tmp_path, monkeypatch, bytes_available):
    folder = tmp_path / 'artifacts'
    folder.mkdir()
    source, origin, path = capture(folder)
    source['excerpts'][0]['html_structure'] = {
        'version': 'html-structure/v1', 'kind': 'heading', 'group_ids': ['legacy-heading']}
    before = deepcopy(source), deepcopy(origin)
    wire = wire_for([source])
    wire.work['run_id'] = 'run-id'
    refs = deepcopy(wire.references)
    if not bytes_available:
        path.unlink()
    service = SimpleNamespace(db=SimpleNamespace(session=lambda: nullcontext(None)),
        settings=SimpleNamespace(storage_path=tmp_path))
    monkeypatch.setattr('helvetic_lens.research_html_structure.retained_originals',
        lambda _session, run_id, sources: [origin] if run_id == 'run-id' and sources else [])
    await enrich(service, wire)
    first = wire.input['sources'][0]['excerpts'][0]['html_structure']
    assert first['version'] == (HTML_STRUCTURE_VERSION if bytes_available else 'html-structure/v1')
    assert wire.receipt['retained_html_structure']['derived_sources'] == int(bytes_available)
    assert wire.references == refs and (source, origin) == before
    assert reference_units(wire)  # unavailable legacy bytes do not invalidate the saved capture
