"""Sparse selected PDF lines cannot stand in for their original scope context."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens import product_document_analysis as analysis
from helvetic_lens.config import DomainError
from helvetic_lens.product_exploration import Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_answer_parts import contextual_references, source_groups
from helvetic_lens.research_evidence_pack import _units, provider_sources, select_evidence
from helvetic_lens.research_model_transport import EvidenceWire
from helvetic_lens.research_original_context import expand_sources


def source(identifier, passages, *, sha='a' * 64, url='https://example.test/report.pdf'):
    return {'id': identifier, 'sha256': sha, 'url': url, 'title': 'Original report',
        'excerpts': [{'passage': locator, 'text': text} for locator, text in passages]}


def wire_for(sources):
    return EvidenceWire({'phase': 'brief', 'input': {'original_question': 'Compare the scope and period.',
        'sources': sources, 'research_mission': {}}}, mission_schema(Briefing), '', shared_answer=True)


def test_compaction_restores_pdf_page_framing_before_ranking_or_review(monkeypatch):
    page = [(f'page-5-text-{i}-char-1', text) for i, text in enumerate([
        'Europe', 'The following comparison concerns the continental observations.',
        *[f'The original page contains measured regional detail {i}.' for i in range(20)],
        'The baseline was the average of the previous observation period.',
        'The measured total remained unchanged against that baseline.',
        'This does not measure the separate polar region.'], 1)]
    original = source('source-a', [*page,
        ('page-7-text-1-char-1', 'Unrelated retained appendix. ' * 400)])
    before = deepcopy(original)
    row = SimpleNamespace(id=original['id'], sha256=original['sha256'], url=original['url'],
        title=original['title'], snapshot={'excerpts': original['excerpts']})
    monkeypatch.setattr(analysis, 'rows', lambda *args: [])
    monkeypatch.setattr(analysis, 'section', lambda *args: {'observations': [
        {'locator': page[-2][0]}], 'cross_references': []})
    monkeypatch.setattr('helvetic_lens.product_document_reconciliation.compact_reviews', lambda *args: {})
    compacted = analysis.compact_sources(None, None, [row])
    assert compacted[0]['excerpts'] == before['excerpts'][:-1]
    assert compacted[0]['original_context']['captured_complete'] is False
    wire = wire_for(compacted)
    selected = next(key for key, ref in wire.references.items() if ref['locator'] == page[-2][0])
    context = contextual_references(wire, [selected])
    assert context == wire.references
    assert _units(wire)[0]['references'] == context and len(_units(wire)) == 1
    excerpts = provider_sources(wire, context)[0]['excerpts']
    assert excerpts[0] == {'text': 'Europe', 'passage': page[0][0]}
    assert [p['text'] for p in excerpts] == [text for _, text in page]
    assert [p['text'] for p in source_groups(wire, context)[0]['passages']] == [text for _, text in page]
    assert original == before


def test_page_context_crosses_only_matching_original_portions_and_preserves_tags():
    heading = source('heading', [('page-5-text-1-char-1', 'Europe')])
    body = source('body', [('page-5-text-2-char-1', 'The original measured this regional period.')])
    end = source('end', [('page-5-text-3-char-1', 'The next line qualifies that measured result.')])
    changed = source('new-version', [('page-5-text-4-char-1', 'Different captured content is not this page.')], sha='b' * 64)
    foreign = source('different-url', [('page-5-text-5-char-1', 'Another source is not this physical page.')], url='https://example.test/other.pdf')
    originals = [heading, body, end, changed, foreign]
    before = deepcopy(originals)
    selected = [{**s, 'excerpts': s['excerpts'] if s['id'] == 'body' else []} for s in originals]
    expanded = expand_sources(selected, originals)
    assert [bool(s['excerpts']) for s in expanded] == [True, True, True, False, False]
    wire = wire_for(expanded)
    context = contextual_references(wire, [1])
    assert {p['source_id'] for p in context.values()} == {'body', 'end'}
    projected = provider_sources(wire, context)
    assert [p['id'] for p in projected] == ['heading', 'body', 'end']
    assert projected[0]['excerpts'] == [{'text': 'Europe', 'passage': 'page-5-text-1-char-1'}]
    assert originals == before


def test_sparse_pdf_list_is_neither_whole_short_source_nor_adjacent_context():
    wire = wire_for([source('sparse', [(f'page-{page}-text-{line}-char-1', f'Exact retained passage {page}-{line}.')
        for page, line in [(1, 70), (5, 21), (5, 25), (7, 27)]])])
    assert set(contextual_references(wire, [2])) == {2, 3}
    assert [unit['primary'] for unit in _units(wire)] == [[1], [2, 3], [4]]


def test_structured_paragraph_portions_keep_exact_long_text_and_metadata():
    text = 'A long original paragraph with its own qualifications. ' * 35
    original = source('s', [('paragraph-3-block-3-char-1', text[:1200]),
        ('paragraph-3-block-3-char-1201', text[1200:]),
        ('paragraph-9-block-9-char-1', 'A distant paragraph cannot become adjacent.')])
    original['excerpts'][1]['host_annotation'] = {'unchanged': True}
    expanded = expand_sources([{**original, 'excerpts': [original['excerpts'][1]]}], [original])
    assert expanded[0]['excerpts'] == original['excerpts'][:2]
    wire = wire_for(expanded)
    selected = next(key for key, ref in wire.references.items() if ref['locator'].endswith('1201'))
    assert contextual_references(wire, [selected]) == wire.references
    assert all(ref['quote'] in text for ref in wire.references.values())


@pytest.mark.asyncio
async def test_mandatory_page_larger_than_envelope_is_not_silently_cropped():
    wire = wire_for([source('s', [(f'page-5-text-{i}-char-1', f'Exact original page line {i}.')
        for i in range(1, 21)])])
    before = deepcopy(wire.references)
    service = SimpleNamespace(settings=SimpleNamespace(apertus_context_chars=24000))
    with pytest.raises(DomainError) as caught:
        await select_evidence(service, wire, 'Compare the originals.', 0,
            required_refs=[12], fits=lambda refs: len(refs) <= 3)
    assert caught.value.code == 'research_evidence_group_too_large'
    assert wire.references == before
