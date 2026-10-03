"""Strict-schema transport keeps complete originals without duplicate grammar."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens.analysis import ModelClient
from helvetic_lens.config import Settings
from helvetic_lens.product_exploration import AssessmentOutcome, Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_answer_parts import contextual_references, source_groups
from helvetic_lens.research_evidence_pack import request_characters
from helvetic_lens.research_final_review import (
    FOCUS,
    REVIEW,
    carry_concerns,
    reasoned_review,
    review_projection,
    scoped_review_schema,
)
from helvetic_lens.research_model_transport import EvidenceWire
from helvetic_lens.research_review_witnesses import assertion_clauses


def settings(**options):
    return Settings(_env_file=None, apertus_provider='swisscom',
        apertus_base_url='https://api.swisscom.com/layer/swiss-ai-platform/test-model/v1',
        apertus_model='swiss-ai/Apertus-v1.5-70B', **options)


@pytest.mark.parametrize('text', ['An ordinary original.', '"quoted"\n\\path\tÉcole\nУкраїна 🏔️' * 80])
def test_swisscom_envelope_counts_actual_escaped_transport_with_schema_once(text):
    schema = {'type': 'object', 'properties': {'status': {'enum': ['supported', 'unknown']}},
        'required': ['status'], 'additionalProperties': False}
    original = {'sources': [{'passage': text}]}
    before = deepcopy(original)
    body = ModelClient(settings()).chat_payload('Use the originals.', json.dumps(original, ensure_ascii=False), response_schema=schema)
    assert body['messages'][0]['content'] == 'Use the originals.'
    assert body['response_format'] == {'type': 'json_schema', 'json_schema': {
        'name': 'structured_response', 'strict': True, 'schema': schema}}
    assert json.loads(body['messages'][1]['content']) == before == original
    actual = len(json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
    assert actual <= request_characters('Use the originals.', original, schema, provider='swisscom')
    # Unknown/unconstrained adapters retain the previous conservative contract.
    assert request_characters('Use the originals.', original, schema) == (
        len('Use the originals.') + len(json.dumps(original, ensure_ascii=False)) + 2 * len(json.dumps(schema)) + 1024)


@pytest.mark.asyncio
async def test_complete_review_context_fits_once_without_source_or_grammar_reduction(monkeypatch):
    from helvetic_lens import research_evidence_pack

    statement = 'The authority keeps the permit registry. The registry includes active permits.'
    passages = [{'passage': 'page-1-text-1-char-1', 'text': 'Rules'}]
    passages += [{'passage': f'page-1-text-{index + 2}-char-1',
        'text': statement if index == 0 else ('The retained original explains the register and its scope. '
            'It includes the exact quoted heading "Registry" and its qualifications. ' * 2).strip()} for index in range(50)]
    work = {'phase': 'brief', 'input': {'original_question': 'Who maintains the active permit records?',
        'research_mission': {}, 'sources': [{'id': 'a' * 36, 'kind': 'public_source', 'title': 'Registry rules',
            'url': 'https://example.org/rules', 'excerpts': passages}]}}
    wire = EvidenceWire(work, mission_schema(Briefing), '')
    original_refs, original_sources = deepcopy(wire.references), deepcopy(wire.input['sources'])
    ref = next(ref for ref in wire.references.values() if ref['quote'] == statement)
    answer = AssessmentOutcome(status='possible_answer', limitations=[], points=[{'statement': statement,
        'evidence': [{**ref, 'role': 'support'}]}])
    concern = carry_concerns({}, [statement], [{'target': 'points', 'signal': 'fast_not_established',
        'instruction': 'Check the exact authority and scope against the originals.', 'original_text': [ref['quote']]}])
    item = {'statement': statement, 'passages': [item.model_dump() for item in answer.points[0].evidence]}
    projected, previous, _, required = review_projection(wire, item, concern)
    context = contextual_references(wire, required)
    payload = {'final_claims_and_gaps': {'P0': projected}, 'original_question': wire.input['original_question'],
        'prior_review_concerns': previous, 'source_context': source_groups(wire, context),
        'selected_citation_refs': required, 'assertion_clauses': assertion_clauses(statement)}
    schema = scoped_review_schema(wire, statement, context, previous['concerns'], point=True)
    system = REVIEW + FOCUS + json.dumps(statement, ensure_ascii=False)
    duplicated = request_characters(system, payload, schema)
    exact = request_characters(system, payload, schema, provider='swisscom')
    assert exact < duplicated
    runtime = settings(apertus_context_chars=(exact + duplicated) // 2)
    adapter, calls = ModelClient(runtime), []

    async def unexpected_selection(*args, **kwargs):
        raise AssertionError('Complete mandatory originals already fit the strict provider request')

    class Model:
        async def complete(self, system, text, **options):
            value = json.loads(text)
            calls.append(value)
            assert value['source_context'] == payload['source_context']
            assert all(passage['text'] in text.replace('\\"', '"') for passage in passages)
            body = adapter.chat_payload(system, text, response_schema=options['response_schema'])
            assert body['messages'][0]['content'] == system
            assert body['response_format']['json_schema']['schema'] == schema
            assert len(json.dumps(body).encode()) <= runtime.apertus_context_chars
            verdict = {'verdict': 'supported', 'reason': 'The exact original states the authority and scope.',
                'citation_refs': value['selected_citation_refs']}
            return json.dumps({'overall': verdict, 'clauses': {key: verdict for key in value['assertion_clauses']},
                'concern_checks': [{'id': key, 'outcome': 'resolved', 'reason': 'The original supplies both facts.',
                    'citation_refs': value['selected_citation_refs']} for key in previous['concerns']]})

    monkeypatch.setattr(research_evidence_pack, 'select_evidence', unexpected_selection)
    result = await reasoned_review(SimpleNamespace(settings=runtime, model_client=Model()), wire, answer, 60,
        concerns={'P0': concern})
    assert result['status'] == 'checked' and len(calls) == 1
    assert wire.references == original_refs and wire.input['sources'] == original_sources
