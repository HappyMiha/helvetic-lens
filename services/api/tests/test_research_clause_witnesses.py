"""A structured review must bind its quoted evidence to the same exact original.

Scripted verdicts exercise host contracts, not a model's semantic accuracy.
"""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens.config import Settings
from helvetic_lens.product_exploration import AssessmentOutcome
from helvetic_lens.research_final_review import reasoned_review


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


def response(payload, refs, *, quote=None, relation='compatible', verdict='supported', cited=1):
    judgment = {'verdict': verdict, 'reason': 'The judgment retains the original population and comparison.',
        'citation_refs': [cited] if cited is not None else []}
    clause = {**judgment, 'witnesses': [] if cited is None else [
        {'citation_ref': cited, 'quote': refs[cited]['quote'] if quote is None else quote, 'scope_relation': relation}]}
    value = {'overall': judgment, 'clauses': {key: deepcopy(clause) for key in payload['assertion_clauses']}}
    if 'gap' in next(iter(payload['final_claims_and_gaps'].values())):
        value['gap_status'] = 'unresolved'
    if payload.get('prior_review_concerns'):
        value['concern_checks'] = [{'id': key, 'outcome': 'resolved', 'reason': 'The source was rechecked.',
            'citation_refs': [cited]} for key in payload['prior_review_concerns']['concerns']]
    return value


@pytest.mark.asyncio
@pytest.mark.parametrize('defect', ['mispaired_original', 'changed_words', 'ref_set_mismatch', 'missing_witness'])
async def test_unbound_clause_quote_is_unavailable_not_a_negative_factual_verdict_and_cannot_be_cached(defect):
    wire, answer = fixture()
    calls, cache = [], {}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            calls.append(payload)
            value = response(payload, wire.references)
            clause = value['clauses']['S0']
            if len(calls) == 1:
                if defect == 'mispaired_original':
                    clause['witnesses'][0]['quote'] = wire.references[2]['quote']
                elif defect == 'changed_words':
                    clause['witnesses'][0]['quote'] = wire.references[1]['quote'].replace('increased', 'decreased')
                elif defect == 'ref_set_mismatch':
                    clause['witnesses'][0] = {'citation_ref': 2, 'quote': wire.references[2]['quote'], 'scope_relation': 'compatible'}
                else:
                    clause['witnesses'] = []
            return json.dumps(value)

    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    concerns = {'P0': {'previous_statements': [], 'issues': [{'instruction': 'Check the assertion against its exact original.'}]}}
    first = await reasoned_review(service, wire, answer, 60, checkpoints=cache, concerns=concerns)
    assert first['status'] == 'partial' and len(first['pending_checks']) == 1
    assert all(hint['review_signal'] == 'review_unavailable' for hint in first['hints'])
    assert first['positive_witnesses'] == {} and first['candidates'] == {}
    assert not any(key.startswith('clauses:') for key in cache), 'Unbound quotes are not accepted negative evidence either'
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
@pytest.mark.parametrize('wrapped', ['in\u00adcreased', 'in-\ncreased'])
async def test_supported_paraphrase_keeps_exact_original_layout_normalization_and_cached_witness(wrapped):
    wire, answer = fixture()
    wire.references[1]['quote'] = f'In the coastal zone,\n the measurement {wrapped}\u00a0over the recorded period.'
    answer.points[0].evidence[0].quote = wire.references[1]['quote']
    quote = 'In the coastal zone, the measurement increased over the recorded period.'
    calls, cache = [], {}

    class Model:
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            calls.append(payload)
            clause_schema = kwargs['response_schema']['properties']['clauses']['properties']['S0']
            assert 'witnesses' in clause_schema['required']
            assert clause_schema['properties']['reason']['maxLength'] >= 600
            return json.dumps(response(payload, wire.references, quote=quote))

    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    result = await reasoned_review(service, wire, answer, 60, checkpoints=cache)
    assert result['status'] == 'checked' and result['hints'] == [] and result['positive_witnesses']
    await reasoned_review(service, wire, answer, 60, checkpoints=json.loads(json.dumps(cache)))
    assert len(calls) == 1
    proof = next(value for key, value in cache.items() if key.startswith('clauses:'))
    assert proof['clauses']['S0']['witnesses'][0]['quote'] == quote
    corrupted = json.loads(json.dumps(cache))
    key = next(key for key in corrupted if key.startswith('clauses:'))
    corrupted[key]['clauses']['S0']['witnesses'][0]['quote'] = wire.references[2]['quote']
    invalid = await reasoned_review(service, wire, answer, 60, checkpoints=corrupted)
    assert invalid['status'] == 'partial' and not invalid['positive_witnesses']
    assert key not in corrupted and len(calls) == 1, 'A stored result must still satisfy the current witness contract'
    retried = await reasoned_review(service, wire, answer, 60, checkpoints=corrupted)
    assert retried['status'] == 'checked' and len(calls) == 2


@pytest.mark.parametrize('changed', [
    'The nonrecovery finding does not establish a global effect.',
    'The non-recovery finding does establish a global effect.'])
def test_layout_normalization_cannot_erase_inline_hyphens_or_negation(changed):
    from helvetic_lens.research_review_witnesses import invalid_clause_witnesses

    refs = {1: {'quote': 'The non-recovery finding does not establish a global effect.'}}
    data = {'clauses': {'S0': {'citation_refs': [1], 'witnesses': [
        {'citation_ref': 1, 'quote': changed, 'scope_relation': 'compatible'}]}}}
    assert invalid_clause_witnesses(data, refs) == 'unbound_clause_witness'


@pytest.mark.parametrize('quote,valid', [
    ('The coastal zone is recovering...', True),
    ('The coastal zone is recovering…', True),
    ('...is recovering as stated in the report.', True),
    ('… is recovering as stated in the report.', True),
    ('... is recovering …', True),
    ('The coastal zone ... as stated in the report.', False),
    ('The coastal zone … as stated in the report.', False),
    ('The inland zone is recovering...', False),
    ('The coastal zone is not recovering...', False),
    ('...', False),
    ('…', False),
])
def test_witness_omission_marker_only_delimits_an_exact_contiguous_excerpt(quote, valid):
    from helvetic_lens.research_review_witnesses import invalid_clause_witnesses

    original = 'The coastal zone is recovering as stated in the report.'
    refs = {1: {'quote': original}}
    data = {'clauses': {'S0': {'citation_refs': [1], 'witnesses': [
        {'citation_ref': 1, 'quote': quote, 'scope_relation': 'compatible'}]}}}
    assert invalid_clause_witnesses(data, refs) == (None if valid else 'unbound_clause_witness')
    assert refs[1]['quote'] == original and data['clauses']['S0']['witnesses'][0]['quote'] == quote


def test_witness_edge_omission_does_not_strip_internal_omissions_from_source():
    from helvetic_lens.research_review_witnesses import invalid_clause_witnesses

    refs = {1: {'quote': 'The coastal zone is ... recovering as stated in the report.'}}
    data = {'clauses': {'S0': {'citation_refs': [1], 'witnesses': [
        {'citation_ref': 1, 'quote': 'The coastal zone is recovering...', 'scope_relation': 'compatible'}]}}}
    assert invalid_clause_witnesses(data, refs) == 'unbound_clause_witness'


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
