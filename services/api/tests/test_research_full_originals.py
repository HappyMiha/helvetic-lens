"""Reading notes cannot hide a captured passage from answer retrieval."""
import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_document_source_context import note, original
from test_research_original_context import source, wire_for

from helvetic_lens import evidence_embeddings, product_document_analysis, research_gateway
from helvetic_lens.analysis import ModelClient
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.decision_engines import DecisionUnavailable
from helvetic_lens.product_exploration import Briefing
from helvetic_lens.product_research_mission import schema
from helvetic_lens.research_evidence_pack import request_characters
from helvetic_lens.research_model_transport import EvidenceWire
from helvetic_lens.research_original_context import contextual_references


def retained_document(monkeypatch):
    run = SimpleNamespace(id=str(uuid4()), question='What condition governs archive renewals?')
    passages = [(f'page-{page}-text-1', f'Administrative archive entry {page}. Ordinary internal accounting information.')
        for page in range(1, 400)]
    decisive = 'Archive renewals are valid only when the original owner has given written approval.'
    passages.append(('page-400-text-1', decisive))
    row = original(run, passages, [note(passages[0][1], passages[0][0])])
    row.snapshot['page_count'] = 400
    before = deepcopy(row.snapshot)
    monkeypatch.setattr(product_document_analysis, 'rows', lambda *args: [])
    monkeypatch.setattr('helvetic_lens.product_document_reconciliation.compact_reviews', lambda *args: {})
    compacted = product_document_analysis.compact_sources(None, run, [row], retain_originals=True)
    assert row.snapshot == before
    return run, row, compacted, decisive


@pytest.mark.asyncio
async def test_hosted_answer_retrieves_unnoted_page400_without_sending_the_full_document(monkeypatch):
    run, row, compacted, decisive = retained_document(monkeypatch)
    assert len(compacted[0]['excerpts']) == 1
    assert len(compacted[0]['retrieval_originals']) == 400
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': run.question, 'research_mission': {},
        'sources': deepcopy(compacted), 'synthesis_sources': compacted}}
    before = deepcopy(work['input'])
    settings = Settings(_env_file=None, apertus_provider='swisscom', apertus_context_chars=24000)
    model = ModelClient(settings)
    calls = []

    async def unavailable(self, texts):
        raise DecisionUnavailable('Local encoder unavailable in this offline boundary case')

    async def receive(system, content, **options):
        payload = json.loads(content)
        calls.append(payload)
        assert 'retrieval_originals' not in content
        excerpts = [p for s in payload['sources'] for p in s['excerpts']]
        assert any(p['text'] == decisive and p['passage'] == 'page-400-text-1' for p in excerpts)
        assert len(excerpts) < 400
        assert payload['evidence_scope']['available_references'] == 400
        assert payload['evidence_scope']['all_originals_supplied'] is False
        assert request_characters(system, payload, options['response_schema'], provider='swisscom') <= 24000
        raise DomainError('Captured the bounded writer request without generating an answer.', 503, 'offline_capture')

    monkeypatch.setattr(evidence_embeddings.LocalEmbeddings, 'encode', unavailable)
    monkeypatch.setattr(model, 'complete', receive)
    with pytest.raises(DomainError) as caught:
        await research_gateway.complete(SimpleNamespace(settings=settings, model_client=model), work, '', schema(Briefing), 60)
    assert caught.value.code == 'offline_capture' and len(calls) == 1
    assert work['input'] == before
    assert row.snapshot['excerpts'][-1]['text'] == decisive


def test_nonpacking_wire_keeps_compact_view_and_never_exposes_private_originals(monkeypatch):
    run, _row, compacted, decisive = retained_document(monkeypatch)
    wire = EvidenceWire({'phase': 'brief', 'input': {'original_question': run.question,
        'sources': compacted, 'synthesis_sources': deepcopy(compacted), 'research_mission': {}}}, schema(Briefing), '')
    assert len(wire.references) == 1
    assert 'retrieval_originals' not in json.dumps(wire.input)
    assert all(ref['quote'] != decisive for ref in wire.references.values())
    assert compacted[0]['retrieval_originals'][-1]['text'] == decisive


@pytest.mark.asyncio
async def test_hosted_legacy_briefing_does_not_expand_originals_without_a_packing_path(monkeypatch):
    run, _row, compacted, decisive = retained_document(monkeypatch)
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model, calls = ModelClient(settings), []

    async def receive(system, content, **options):
        calls.append(json.loads(content))
        assert 'retrieval_originals' not in content and decisive not in content
        assert len(calls[0]['sources'][0]['excerpts']) == 1
        raise DomainError('Captured legacy request.', 503, 'offline_capture')

    monkeypatch.setattr(model, 'complete', receive)
    with pytest.raises(DomainError) as caught:
        await research_gateway.complete(SimpleNamespace(settings=settings, model_client=model),
            {'phase': 'brief', 'unmetered_research': True, 'input': {
                'original_question': run.question, 'sources': compacted}}, '', Briefing, 60)
    assert caught.value.code == 'offline_capture' and len(calls) == 1


@pytest.mark.parametrize('prefix', ['p000', 'paragraph-'])
def test_numbered_question_heading_keeps_its_answer_across_block_ordinals(prefix):
    original = source('faq', [
        (f'{prefix}64-block-64-char-1', 'What is required when an archive permission is renewed?'),
        (f'{prefix}65-block-65-char-1', 'The original owner must provide written approval for that renewal.'),
        (f'{prefix}70-block-70-char-1', 'A separate administrative section covers staff travel.')])
    wire = wire_for([original])
    context = contextual_references(wire, [1])
    assert set(context) == {1, 2}
    assert context[2]['quote'] == original['excerpts'][1]['text']
