"""The retained corpus stays searchable during corrections and missing-answer checks."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens.config import Settings
from helvetic_lens.product_exploration import AssessmentOutcome, Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_answer_parts import answer_request
from helvetic_lens.research_evidence_pack import request_characters
from helvetic_lens.research_final_review import reasoned_review
from helvetic_lens.research_model_transport import EvidenceWire


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['correction', 'gap'])
async def test_late_original_is_considered_in_bounded_correction_and_gap_review(mode):
    sources = [{'id': f'{index:036d}', 'kind': 'public_source', 'title': f'Earlier source {index}',
        'excerpts': [{'passage': 'p1', 'text': ('The registry provides background about applications and published notices. ' * 16)}]}
        for index in range(40)]
    original = 'The permit takes effect only after the registry signs it. An unsigned permit has no effect.'
    sources.append({'id': 'z' * 36, 'kind': 'public_source', 'title': 'Late original',
        'excerpts': [{'passage': 'p1', 'text': original}]})
    wire = EvidenceWire({'phase': 'brief', 'input': {'original_question': 'Does a permit take effect automatically?',
        'research_mission': {}, 'sources': sources}}, mission_schema(Briefing), '')
    before = deepcopy(wire.references)
    settings = Settings(_env_file=None, apertus_provider='swisscom', apertus_context_chars=18000)
    seen, dispatched = set(), []

    class Model:
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            assert request_characters(system, payload, options['response_schema']) <= settings.apertus_context_chars
            dispatched.append(payload)
            if payload.get('phase') in {'select', 'consolidate'}:
                seen.update(source['id'] for source in payload['sources'])
                return json.dumps({'citation_refs': {source['selection_key']:
                    source['selectable_refs'] if source['id'] == 'z' * 36 else []
                    for source in payload['sources']}})
            assert original in text
            if mode == 'correction':
                assert payload['correction_target']['previous_statement'] == 'A permit takes effect automatically.'
                ref = next(passage['citation_ref'] for source in payload['sources'] for passage in source['passages']
                    if passage['text'] == original)
                return json.dumps({'points': [{'statement': 'The permit takes effect only after the registry signs it.',
                    'evidence': [{'citation_ref': ref, 'role': 'support'}]}], 'remaining_gap': ''})
            ref = next(passage['citation_ref'] for source in payload['sources'] for passage in source['passages']
                if passage['text'] == original)
            verdict = {'verdict': 'not_established', 'reason': 'The original establishes the signature requirement.',
                'citation_refs': [ref]}
            return json.dumps({'overall': verdict, 'clauses': {key: verdict for key in payload['assertion_clauses']},
                'gap_status': 'answer_available'})

    service = SimpleNamespace(settings=settings, model_client=Model())
    if mode == 'correction':
        points, gap, _ = await answer_request(service, wire, wire.input['original_question'], 60,
            correction={'previous_statement': 'A permit takes effect automatically.', 'validation_errors': []})
        assert len(points) == 1 and points[0].evidence[0].quote == original and gap == ''
    else:
        answer = AssessmentOutcome(status='partial', points=[], limitations=['It is unknown when a permit takes effect.'])
        result = await reasoned_review(service, wire, answer, 60)
        assert result['status'] == 'checked'
        assert result['hints'][0]['original_windows'] == [{'text': original}]
    assert seen == {source['id'] for source in sources}
    assert len(dispatched) > 2 and wire.references == before
