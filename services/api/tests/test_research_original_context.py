"""Sparse selected PDF lines cannot stand in for their original scope context."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens import product_document_analysis as analysis
from helvetic_lens.config import DomainError
from helvetic_lens.product_exploration import Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_answer_parts import answer_request, contextual_references, source_groups
from helvetic_lens.research_evidence_pack import _units, provider_sources, select_evidence
from helvetic_lens.research_model_transport import EvidenceWire
from helvetic_lens.research_original_context import expand_sources, provider_excerpts


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


@pytest.mark.asyncio
@pytest.mark.parametrize('separate_heading_portion', [False, True])
async def test_answer_request_keeps_page_heading_without_inventing_a_citation(separate_heading_portion):
    heading = ('page-5-text-1-char-1', 'Europe')
    observation = 'The regional measured total remained unchanged against its baseline.'
    qualification = 'The separate polar region was not measured by this comparison.'
    body = source('body', [('page-5-text-2-char-1', observation),
        ('page-5-text-3-char-1', qualification)])
    originals = [source('unrelated', [('page-1-text-1-char-1', 'A different original describes registry administration.')],
        sha='b' * 64, url='https://example.test/registry.pdf')]
    if separate_heading_portion:
        originals.append(source('heading', [heading]))
    else:
        body['excerpts'].insert(0, {'passage': heading[0], 'text': heading[1]})
    originals.append(body)
    wire = wire_for(originals)
    before = deepcopy(wire.__dict__)
    canonical = next(key for key, ref in wire.references.items() if ref['quote'] == observation)
    cache, calls = {}, []

    class Model:
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            groups = payload['sources']
            headings = [p for group in groups for p in group['passages'] if p['text'] == heading[1]]
            assert headings == [{'text': heading[1]}], 'The scope heading remains uncitable original context'
            props = options['response_schema']['properties']
            if 'citation_refs' in props:
                calls.append('select')
                allowed = props['citation_refs']['properties']
                assert {ref for spec in allowed.values() for ref in spec['items']['enum']} == set(wire.references)
                assert all(spec['items']['enum'] for spec in allowed.values()), 'Context-only portions need no empty routing enum'
                for group in groups:
                    refs = [p['citation_ref'] for p in group['passages'] if 'citation_ref' in p]
                    if refs:
                        assert allowed[group['selection_key']]['items']['enum'] == refs
                    else:
                        assert group.get('selection_key') not in allowed
                return json.dumps({'citation_refs': {key: [canonical] if canonical in spec['items']['enum'] else []
                    for key, spec in allowed.items()}})
            calls.append('write')
            supplied = {p['citation_ref']: p['text'] for group in groups for p in group['passages'] if 'citation_ref' in p}
            assert set(supplied.values()) == {observation, qualification}
            enum = props['points']['items']['properties']['evidence']['items']['properties']['citation_ref']['enum']
            assert enum == list(supplied) == [1, 2], 'Writer IDs bind only the selected canonical page windows'
            return json.dumps({'points': [{'statement': observation,
                'evidence': [{'citation_ref': 1, 'role': 'support'}]}], 'remaining_gap': ''})

    service = SimpleNamespace(model_client=Model())
    points, gap, receipt = await answer_request(service, wire, wire.input['original_question'], 60, checkpoints=cache)
    assert calls == ['select', 'write'] and receipt['status'] == 'proposed' and gap == ''
    assert points[0].evidence[0].model_dump() == {**wire.references[canonical], 'role': 'support'}
    assert points[0].statement == observation and wire.__dict__ == before
    resumed, _, resumed_receipt = await answer_request(service, wire, wire.input['original_question'], 0,
        checkpoints=json.loads(json.dumps(cache)))
    assert resumed == points and resumed_receipt['status'] == 'proposed' and calls == ['select', 'write']


def linked_originals():
    observed = source('observation', [('page-2-text-1-char-1',
        'The permit may be extended when the annual inspection has been completed.')])
    qualifier = source('qualifier', [('page-8-text-1-char-1', '2014'),
        ('page-8-text-2-char-1', 'This report describes the rules applicable to the earlier observation period.'),
        ('page-8-text-3-char-1', 'Later changes to the inspection requirements are outside this report.')])
    def binding(item, index):
        passage = item['excerpts'][index]
        return {'source_id': item['id'], 'sha256': item['sha256'],
            'locator': passage['passage'], 'quote': passage['text']}
    observed['source_context'] = [{'observation': binding(observed, 0),
        'anchors': [{'kind': 'time', **binding(qualifier, 1)}]}]
    return [observed, qualifier]


def test_linked_qualifier_preserves_full_page_and_remaps_local_writer_ids():
    originals = linked_originals()
    before = deepcopy(originals)
    wire = wire_for(originals)
    context = contextual_references(wire, [1])
    assert context == wire.references and len(context) == 3
    assert _units(wire)[0]['references'] == context
    # Targeted writers renumber refs. Associations must follow exact originals,
    # not accidentally point at the previous request's same integer.
    local = {index: ref for index, ref in enumerate(reversed(context.values()), 21)}
    passages = provider_excerpts(wire, local)
    assert passages['observation'][0]['citation_ref'] == 23
    assert passages['observation'][0]['context_anchors'] == [{'kind': 'time', 'citation_refs': [22]}]
    assert passages['qualifier'][0] == {'text': '2014', 'passage': 'page-8-text-1-char-1'}
    assert len([item for item in passages['qualifier'] if 'citation_ref' in item]) == 2
    assert all('role' not in item for group in passages.values() for item in group)
    assert originals == before and wire.references[2]['quote'] == originals[1]['excerpts'][1]['text']
    with pytest.raises(ValueError, match='missing a bound original anchor'):
        provider_excerpts(wire, {23: wire.references[1]})


def test_partial_primary_aliases_still_require_their_complete_anchor():
    wire = wire_for(linked_originals())
    # A review's bounded candidate wire can omit another alias of a primary
    # observation. Its supplied primary must still retain the entire qualifier.
    wire.source_context[0]['observation_refs'].append(999)
    assert provider_excerpts(wire, wire.references)['observation'][0]['context_anchors'] == [
        {'kind': 'time', 'citation_refs': [2]}]
    wire.references.pop(2)
    with pytest.raises(ValueError, match='missing a bound original anchor'):
        provider_excerpts(wire, wire.references)


@pytest.mark.parametrize('change', ['quotation', 'sha', 'withdrawal', 'different_original'])
def test_changed_or_foreign_context_cannot_be_rebound(change):
    originals = linked_originals()
    if change == 'quotation':
        originals[0]['source_context'][0]['anchors'][0]['quote'] = 'The authority says the permit has already been extended.'
    elif change == 'sha':
        originals[1]['sha256'] = 'b' * 64
    elif change == 'withdrawal':
        originals.pop()
    else:
        originals[1]['url'] = 'https://example.test/different-original.pdf'
    with pytest.raises(ValueError):
        wire_for(originals)


@pytest.mark.asyncio
async def test_required_linked_qualifier_cannot_be_clipped_to_fit():
    wire = wire_for(linked_originals())
    before = deepcopy(wire.__dict__)
    service = SimpleNamespace(settings=SimpleNamespace(apertus_context_chars=24000))
    with pytest.raises(DomainError) as caught:
        await select_evidence(service, wire, 'When may the permit be extended?', 0,
            required_refs=[1], fits=lambda refs: len(refs) <= 1)
    assert caught.value.code == 'research_evidence_group_too_large'
    assert wire.__dict__ == before
