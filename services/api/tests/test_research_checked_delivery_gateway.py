"""Only exact native exhausted-input intent enables checked-subset delivery."""
import json
from types import SimpleNamespace

import pytest

from helvetic_lens import research_final_review, research_gateway
from helvetic_lens.analysis import ModelClient
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_exploration import Briefing
from helvetic_lens.product_operations import fingerprint
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_model_transport import EvidenceWire
from helvetic_lens.research_synthesis_resume import EXHAUSTED_REVIEW, KEY


@pytest.mark.asyncio
@pytest.mark.parametrize('automatic', [False, True])
@pytest.mark.parametrize('intent', ['absent', 'changed', 'stale_binding', 'invalid_checkpoint', 'preparing', 'stale_request', 'exact'])
async def test_gateway_requires_current_input_before_qualified_delivery(monkeypatch, intent, automatic):
    text = 'The public registry identifies Alpine Foundation as the responsible operator.'
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'Who operates the public registry?', 'research_mission': {},
        'sources': [{'id': 'source', 'kind': 'public_source', 'url': 'https://example.org/registry',
            'excerpts': [{'passage': 'p1', 'text': text}]}]}}
    schema = mission_schema(Briefing)
    wire = EvidenceWire(work, schema, '')
    # An untrusted/free-standing flag cannot substitute for the native marker.
    work['allow_checked_partial_delivery'] = True
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    calls, drafts = [], []

    async def complete(*args, **kwargs):
        drafts.append(True)
        return json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [],
            'points': [{'statement': text, 'evidence': [{'citation_ref': 1, 'role': 'support'}]}]},
            'next_action': 'finish'})

    async def finalize(service, supplied, wire, parsed, seconds, **kwargs):
        assert supplied['allow_checked_partial_delivery'] is (bool(calls) and intent == 'exact')
        calls.append(True)
        assert kwargs['defer_pending'] is True
        raise DomainError('End of isolated gateway contract test', 503, 'research_review_incomplete')

    monkeypatch.setattr(model, 'complete', complete)
    monkeypatch.setattr(research_final_review, 'finalize', finalize)
    service = SimpleNamespace(settings=settings, model_client=model)
    with pytest.raises(DomainError, match='End of isolated gateway'):
        await research_gateway.complete(service, work, '', schema, 90)
    assert work[KEY]['stage'] == 'finalizing'
    if intent != 'absent':
        work[EXHAUSTED_REVIEW] = {'reason': 'model_upstream_timeout',
            'input_fingerprint': 'stale-evidence' if intent == 'changed' else wire.receipt['input_fingerprint'],
            'checkpoint_binding': 'old-policy' if intent == 'stale_binding' else work[KEY]['binding']}
    if intent == 'invalid_checkpoint':
        work[KEY]['fingerprint'] = 'invalid'
    elif intent == 'preparing':
        work[KEY]['stage'] = 'preparing'
        work[KEY]['fingerprint'] = fingerprint({k: v for k, v in work[KEY].items() if k != 'fingerprint'})
    elif intent == 'stale_request':
        work[KEY]['request_binding'] = 'different-selected-originals'
        work[KEY]['fingerprint'] = fingerprint({k: v for k, v in work[KEY].items() if k != 'fingerprint'})
    work['automatic_review_handoff'] = automatic
    with pytest.raises(DomainError, match='automatic checked delivery' if automatic and intent != 'exact' else 'End of isolated gateway'):
        await research_gateway.complete(service, work, '', schema, 90)
    assert len(calls) == (1 if automatic and intent != 'exact' else 2)
    if automatic:
        assert len(drafts) == 1, 'An automatic handoff cannot purchase a replacement draft'
    assert (EXHAUSTED_REVIEW in work) is (intent == 'exact')
    if intent == 'invalid_checkpoint':
        assert work['synthesis_checkpoint_invalidated'] is True
    if intent in {'changed', 'stale_binding', 'invalid_checkpoint', 'preparing', 'stale_request'}:
        assert work['exhausted_review_invalidated'] is True
