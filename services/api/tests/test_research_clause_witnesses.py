"""A reviewer selects evidence; the host binds each choice to the exact original.

Scripted verdicts exercise host contracts, not a model's semantic accuracy.
"""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens.config import Settings
from helvetic_lens.product_exploration import AssessmentOutcome
from helvetic_lens.research_final_review import reasoned_review
from helvetic_lens.research_review_witnesses import normalize_clause_witnesses, witness_choices


def fixture(*, statement='The coastal zone measurement rose.', cited=1):
    refs = {
        1: {'source_id': 'report', 'locator': 'p1',
            'quote': 'In the coastal zone, the measurement increased. Inland observations are outside this comparison.'},
        2: {'source_id': 'report', 'locator': 'p2',
            'quote': 'In the inland zone, the measurement decreased. Coastal observations are outside this comparison.'},
    }
    answer = AssessmentOutcome(status='possible_answer', points=[{'statement': statement,
        'evidence': [{**refs[cited], 'role': 'support'}]}], limitations=[])
    return SimpleNamespace(input={'original_question': 'How did the measurements change?'}, references=refs), answer


def response(payload, refs, *, relation='compatible', verdict='supported', cited=1):
    judgment = {'verdict': verdict, 'reason': 'The judgment retains the original population and comparison.',
        'citation_refs': [cited] if cited is not None else []}
    choices = {ref: key for key, ref in witness_choices(refs).items()}
    clause = {name: value for name, value in judgment.items() if name != 'citation_refs'}
    clause['witnesses'] = [] if cited is None else [{'key': choices[cited], 'scope_relation': relation}]
    value = {'overall': judgment, 'clauses': {key: deepcopy(clause) for key in payload['assertion_clauses']}}
    if 'gap' in next(iter(payload['final_claims_and_gaps'].values())):
        value['gap_status'] = 'unresolved'
    if payload.get('prior_review_concerns'):
        value['concern_checks'] = [{'id': key, 'outcome': 'resolved', 'reason': 'The source was rechecked.',
            'citation_refs': [cited]} for key in payload['prior_review_concerns']['concerns']]
    return value


@pytest.mark.asyncio
@pytest.mark.parametrize('defect', ['forged_key', 'duplicate_key', 'missing_witness', 'copied_quote', 'foreign_citation'])
async def test_invalid_choice_is_unavailable_not_a_negative_factual_verdict_and_cannot_be_cached(defect):
    wire, answer = fixture()
    calls, cache = [], {}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            calls.append(payload)
            value = response(payload, wire.references)
            clause = value['clauses']['S0']
            if len(calls) == 1:
                if defect == 'forged_key':
                    clause['witnesses'][0]['key'] = 'forged-original-choice'
                elif defect == 'duplicate_key':
                    clause['witnesses'] *= 2
                elif defect == 'copied_quote':
                    clause['witnesses'][0]['quote'] = wire.references[2]['quote']
                elif defect == 'foreign_citation':
                    clause['witnesses'][0]['citation_ref'] = 2
                else:
                    clause['witnesses'] = []
            return json.dumps(value)

    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    concerns = {'P0': {'previous_statements': [], 'issues': [{'instruction': 'Check the assertion against its exact original.'}]}}
    first = await reasoned_review(service, wire, answer, 60, checkpoints=cache, concerns=concerns)
    assert first['status'] == 'partial' and len(first['pending_checks']) == 1
    assert all(hint['review_signal'] == 'review_unavailable' for hint in first['hints'])
    assert first['positive_witnesses'] == {} and first['candidates'] == {}
    assert not any(key.startswith('clauses:') for key in cache), 'Invalid choices are not negative evidence either'
    second = await reasoned_review(service, wire, answer, 60, checkpoints=cache, concerns=concerns)
    assert second['status'] == 'checked' and second['pending_checks'] == [] and second['hints'] == []
    assert len(calls) == 2 and second['positive_witnesses']


@pytest.mark.asyncio
@pytest.mark.parametrize('relation', ['different', 'not_established'])
async def test_supported_overall_and_resolved_concern_cannot_override_declared_clause_scope_mismatch(relation):
    wire, answer = fixture(statement='The inland zone measurement rose.')
    cache, calls = {}, []

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            calls.append(payload)
            return json.dumps(response(payload, wire.references, relation=relation))

    result = await reasoned_review(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()),
        wire, answer, 60, checkpoints=cache, concerns={'P0': {'previous_statements': [], 'issues': [
            {'instruction': 'Check whether the source discusses the asserted zone.', 'original_text': [wire.references[1]['quote']]}]}})
    assert len(calls) == 1 and result['status'] == 'checked' and result['pending_checks'] == []
    assert result['positive_witnesses'] == {} and result['candidates'] == {}
    assert [hint['review_signal'] for hint in result['hints']] == ['not_established']
    assert answer.points[0].statement in result['hints'][0]['instruction']
    assert result['hints'][0]['original_windows'] == [{'text': wire.references[1]['quote']}]


@pytest.mark.asyncio
async def test_supported_paraphrase_selects_exact_host_original_and_revalidates_cached_choice():
    wire, answer = fixture()
    original = 'In the coastal zone,\n the non-recovery comparison in-\ncreased\u00a0over the recorded period; inland scope does not apply.'
    wire.references[1]['quote'] = original
    answer.points[0].evidence[0].quote = original
    calls, cache = [], {}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            calls.append(payload)
            clause_schema = kwargs['response_schema']['properties']['clauses']['properties']['S0']
            assert 'witnesses' in clause_schema['required'] and 'citation_refs' not in clause_schema['properties']
            assert clause_schema['properties']['reason']['maxLength'] >= 600
            witness_schema = clause_schema['properties']['witnesses']['items']['properties']
            assert set(witness_schema) == {'key', 'scope_relation'}
            assert set(witness_schema['key']['enum']) == set(witness_choices(wire.references))
            passage = next(p for g in payload['source_context'] for p in g['passages'] if p.get('citation_ref') == 1)
            assert passage['text'] == original
            assert witness_choices(wire.references)[passage['witness_key']] == 1
            return json.dumps(response(payload, wire.references))

    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    result = await reasoned_review(service, wire, answer, 60, checkpoints=cache)
    assert result['status'] == 'checked' and result['hints'] == [] and result['positive_witnesses']
    await reasoned_review(service, wire, answer, 60, checkpoints=json.loads(json.dumps(cache)))
    assert len(calls) == 1
    proof = next(value for key, value in cache.items() if key.startswith('clauses:'))
    assert set(proof['clauses']['S0']['witnesses'][0]) == {'key', 'scope_relation'}
    normalized = normalize_clause_witnesses(proof, wire.references)
    assert normalized['clauses']['S0']['citation_refs'] == [1]
    assert normalized['clauses']['S0']['witnesses'] == [
        {'citation_ref': 1, 'quote': original, 'scope_relation': 'compatible'}]
    assert 'citation_refs' not in proof['clauses']['S0'], 'Cache stays in the constrained raw contract'
    corrupted = json.loads(json.dumps(cache))
    key = next(key for key in corrupted if key.startswith('clauses:'))
    corrupted[key]['clauses']['S0']['witnesses'][0]['key'] = 'not-a-current-original'
    invalid = await reasoned_review(service, wire, answer, 60, checkpoints=corrupted)
    assert invalid['status'] == 'partial' and not invalid['positive_witnesses']
    assert key not in corrupted and len(calls) == 1, 'Stored choices must satisfy the current original registry'
    retried = await reasoned_review(service, wire, answer, 60, checkpoints=corrupted)
    assert retried['status'] == 'checked' and len(calls) == 2


def test_canonical_choice_does_not_copy_or_rewrite_source_text_or_trust_forged_keys():
    refs = {
        17: {'source_id': 'source-a', 'locator': 'p4', 'quote': 'The non-polar result is not a polar finding. Strato-\nspheric variation … remains.'},
        18: {'source_id': 'source-b', 'locator': 'p4', 'quote': 'The non-polar result is not a polar finding. Strato-\nspheric variation … remains.'},
    }
    choices = witness_choices(refs)
    assert len(choices) == 2 and set(choices.values()) == {17, 18}
    assert choices == witness_choices(deepcopy(refs))
    raw = {'clauses': {'S0': {'verdict': 'supported', 'reason': 'Scripted scope comparison.', 'witnesses': [
        {'key': next(key for key, ref in choices.items() if ref == 18), 'scope_relation': 'compatible'}]}}}
    before = deepcopy(raw)
    normalized = normalize_clause_witnesses(raw, refs)
    assert raw == before
    assert normalized['clauses']['S0']['citation_refs'] == [18]
    assert normalized['clauses']['S0']['witnesses'][0]['quote'] == refs[18]['quote']
    raw['clauses']['S0']['witnesses'][0]['key'] = 'invented-source-key'
    with pytest.raises(ValueError):
        normalize_clause_witnesses(raw, refs)


@pytest.mark.asyncio
async def test_changed_original_cannot_reuse_cached_canonical_choice():
    wire, answer = fixture()
    calls, cache = [], {}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            calls.append(payload)
            return json.dumps(response(payload, wire.references))

    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    await reasoned_review(service, wire, answer, 60, checkpoints=cache)
    wire.references[1]['quote'] += ' This comparison excludes the later survey.'
    answer.points[0].evidence[0].quote = wire.references[1]['quote']
    result = await reasoned_review(service, wire, answer, 60, checkpoints=cache)
    assert len(calls) == 2 and result['status'] == 'checked'
    assert calls[0]['source_context'] != calls[1]['source_context']


@pytest.mark.asyncio
async def test_context_witness_requires_explicit_citation_repair_instead_of_lending_support_to_selected_original():
    wire, answer = fixture(statement='The inland zone measurement fell.')

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            assert payload['selected_citation_refs'] == [1]
            return json.dumps(response(payload, wire.references, cited=2))

    result = await reasoned_review(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()), wire, answer, 60)
    assert result['status'] == 'checked' and result['pending_checks'] == []
    assert result['hints'][0]['review_signal'] == 'not_established'
    assert result['hints'][0]['candidate_windows'] == [{'text': wire.references[2]['quote']}]
    assert result['candidates']['P0']['evidence'] == [{**wire.references[2], 'role': 'support'}]
    assert answer.points[0].evidence[0].quote == wire.references[1]['quote'], 'Reviewer cannot silently rebind the actual answer'


@pytest.mark.asyncio
@pytest.mark.parametrize('point,verdict', [(False, 'supported'), (False, 'not_established'), (True, 'not_established')])
async def test_unresolved_gap_or_unestablished_point_can_honestly_return_no_source_witness(point, verdict):
    wire, answer = fixture()
    if not point:
        answer = AssessmentOutcome(status='not_found', points=[], limitations=['The measured inland change remains unresolved.'])
    wire.references = {} if not point else wire.references

    class Model:
        async def complete(self, system, text, **kwargs):
            return json.dumps(response(json.loads(text), wire.references, cited=None, verdict=verdict))

    result = await reasoned_review(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()), wire, answer, 60)
    assert result['status'] == 'checked' and result['pending_checks'] == []
    assert result['positive_witnesses'] == {}
    # This proves representability and fail-closed handling, not that a model
    # can infer global absence of knowledge from an incomplete corpus.
    assert all(hint['review_signal'] == 'not_established' for hint in result['hints'])


@pytest.mark.asyncio
@pytest.mark.parametrize('gap_status', ['answered', 'answer_available'])
async def test_scope_mismatch_cannot_remove_a_gap_via_positive_gap_disposition(gap_status):
    wire, answer = fixture()
    answer.status = 'partial'
    answer.limitations = ['The inland measurement change remains unresolved.']

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            key = next(iter(payload['final_claims_and_gaps']))
            value = response(payload, wire.references, relation='different' if key == 'L0' else 'compatible')
            if key == 'L0':
                value['gap_status'] = gap_status
            return json.dumps(value)

    result = await reasoned_review(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()), wire, answer, 60)
    assert result['status'] == 'checked' and result['pending_checks'] == []
    assert [hint['review_signal'] for hint in result['hints']] == ['not_established']
    assert result['hints'][0]['path'] == ['answer', 'limitations', 0]
