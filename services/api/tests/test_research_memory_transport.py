"""Deduplicate representation, never the underlying evidence or its authority."""
import json
from copy import deepcopy

import pytest

from helvetic_lens.product_exploration import EarlyOrientation
from helvetic_lens.research_model_transport import EvidenceWire


def work():
    original = 'The fictional source reports that the observation remains uncertain. ' * 30
    source = {'id': 'a' * 36, 'sha256': 'b' * 64, 'title': 'Original source', 'url': 'https://example.org/original',
        'kind': 'public_source', 'excerpts': [{'passage': 'page-1', 'text': original}, {'passage': 'page-2', 'text': 'A title'}]}
    saved = {**deepcopy(source), 'captured_at': '2026-01-02T00:00:00Z'}
    saved['excerpts'][0]['relevance'] = {'status': 'uncertain', 'human_note': 'Read the exception.'}
    return {'phase': 'orient', 'unmetered_research': True, 'input': {'original_question': 'What does the source establish?',
        'sources': [source], 'saved_knowledge': {'sources': [saved], 'claims': [
            {'statement': 'An earlier interpretation.', 'human_status': 'PROPOSED', 'claim_revision': 3,
                'review_requirement': 'Human review pending.', 'citations': [{'quote': original, 'locator': 'page-1'}]}]}}}


def test_duplicate_long_passage_alias_preserves_every_window_and_original_authority():
    data = work()
    before = deepcopy(data)
    wire = EvidenceWire(data, EarlyOrientation, '')
    saved = wire.input['saved_knowledge']['sources'][0]
    assert data == before, 'Only the copied provider input may change'
    assert 'text' not in saved['excerpts'][0]
    assert saved['excerpts'][0]['citation_refs'] == list(wire.references)
    assert len(wire.references) > 1
    assert saved['excerpts'][0]['relevance'] == before['input']['saved_knowledge']['sources'][0]['excerpts'][0]['relevance']
    assert saved['excerpts'][1] == before['input']['saved_knowledge']['sources'][0]['excerpts'][1]
    assert saved['captured_at'] == before['input']['saved_knowledge']['sources'][0]['captured_at']
    assert wire.input['saved_knowledge']['claims'] == before['input']['saved_knowledge']['claims']
    without_memory = deepcopy(before)
    without_memory['input'].pop('saved_knowledge')
    baseline = EvidenceWire(without_memory, EarlyOrientation, '')
    assert wire.references == baseline.references and wire.schema == baseline.schema
    assert wire.input['sources'] == baseline.input['sources']
    output = json.dumps({'interpretations': [{'citation_ref': 1, 'meaning': 'This source records uncertainty.',
        'why': 'The captured wording says it remains uncertain.', 'signal': 'possible'}], 'uncertainties': ['The source does not establish the cause.']})
    assert wire.decode(output) == baseline.decode(output)


@pytest.mark.parametrize('text', [
    'Evidence supports approval.' + ' ' * 600 + 'No.',
    'No.' + ' ' * 600 + 'Evidence supports approval.',
    'Evidence supports approval.' + ' ' * 600 + 'No.' + ' ' * 600 + 'A different observation remains uncertain.',
])
def test_short_qualifier_outside_citation_windows_keeps_complete_saved_text(text):
    data = work()
    for source in [data['input']['sources'][0], data['input']['saved_knowledge']['sources'][0]]:
        source['excerpts'][0]['text'] = text
    expected = deepcopy(data['input']['saved_knowledge']['sources'][0])
    wire = EvidenceWire(data, EarlyOrientation, '')
    assert wire.input['saved_knowledge']['sources'][0] == expected


@pytest.mark.parametrize('change', ['id', 'sha256', 'missing_hash', 'passage', 'text', 'saved_only', 'reserved_field'])
def test_inexact_or_unrepresented_saved_passages_are_never_removed(change):
    data = work()
    source = data['input']['saved_knowledge']['sources'][0]
    if change in {'id', 'sha256'}:
        source[change] = 'c' * len(source[change])
    elif change == 'missing_hash':
        source.pop('sha256')
    elif change in {'text', 'passage'}:
        source['excerpts'][0][change] += ' changed'
    elif change == 'saved_only':
        data['input']['sources'] = []
    else:
        source['excerpts'][0]['citation_refs'] = ['historical metadata']
    expected = deepcopy(source)
    wire = EvidenceWire(data, EarlyOrientation, '')
    assert wire.input['saved_knowledge']['sources'][0] == expected
    if change == 'saved_only':
        assert wire.references == {}, 'Saved-only material must not become new citation authority'
