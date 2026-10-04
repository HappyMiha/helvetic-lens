"""Overall evaluates relationships using the exact clause-selected originals."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from helvetic_lens.config import Settings
from helvetic_lens.product_exploration import AssessmentOutcome
from helvetic_lens.research_final_review import reasoned_review
from helvetic_lens.research_model_transport import shape_errors
from helvetic_lens.research_review_witnesses import (
    invalid_review,
    normalize_clause_witnesses,
    review_schema,
    witness_choices,
)


def test_overall_union_retains_all_clause_originals_without_duplicates_or_concern_only_refs():
    assertion = 'The first survey measured the region. The second survey revisited it.'
    refs = {i: {'source_id': 'survey', 'locator': f'p{i}', 'quote': f'This is unchanged survey passage {i}.'}
        for i in range(1, 12)}
    choices = {ref: key for key, ref in witness_choices(refs).items()}
    raw = {'overall': {'verdict': 'contradicted', 'reason': 'The asserted relationship is not what these observations establish.'},
        'clauses': {key: {'verdict': 'supported', 'reason': '', 'witnesses': [
            {'key': choices[ref], 'scope_relation': 'compatible'} for ref in selected]}
            for key, selected in [('S0', range(1, 9)), ('S1', [8, 9, 10])]},
        'concern_checks': [{'id': 'C0', 'outcome': 'resolved', 'reason': '', 'citation_refs': [11]}]}
    before = deepcopy(raw)
    assert not shape_errors(raw, review_schema(assertion, refs, {'C0': {}}, point=True), {})
    normalized = normalize_clause_witnesses(raw, refs)
    assert normalized['overall']['citation_refs'] == list(range(1, 11)), 'The union is neither repeated nor truncated to eight'
    assert normalized['overall']['verdict'] == 'contradicted', 'Host attachment must not infer an overall verdict'
    assert normalized['concern_checks'][0]['citation_refs'] == [11]
    assert invalid_review(normalized, assertion, {'C0': {}}, point=True) is None
    assert raw == before and 'citation_refs' not in raw['overall']


@pytest.mark.asyncio
async def test_negative_overall_relationship_remains_rejected_with_supported_clauses_and_cached_raw_choices():
    refs = {
        1: {'source_id': 'registry', 'locator': 'p1', 'quote': 'North Reach started the registry in 2040.'},
        2: {'source_id': 'registry', 'locator': 'p2', 'quote': 'The registry accepted the first entry in 2042.'},
    }
    statement = 'North Reach started the registry in 2040. It accepted the first entry two years later.'
    answer = AssessmentOutcome(status='possible_answer', points=[{'statement': statement,
        'evidence': [{**ref, 'role': 'support'} for ref in refs.values()]}], limitations=[])
    wire = SimpleNamespace(input={'original_question': 'What happened and in what order?'}, references=refs)
    choices = {ref: key for key, ref in witness_choices(refs).items()}
    calls, cache = [], {}

    class Model:
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            calls.append(payload)
            return json.dumps({'overall': {'verdict': 'contradicted', 'reason': 'Scripted rejection of the relationship, independent of individual clauses.'},
                'clauses': {key: {'verdict': 'supported', 'reason': '', 'witnesses': [
                    {'key': choices[i + 1], 'scope_relation': 'compatible'}]}
                    for i, key in enumerate(payload['assertion_clauses'])}})

    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    result = await reasoned_review(service, wire, answer, 60, checkpoints=cache)
    assert result['status'] == 'checked' and result['pending_checks'] == []
    assert result['positive_witnesses'] == {} and result['candidates'] == {}
    assert result['hints'][0]['review_signal'] == 'contradicted'
    assert result['hints'][0]['original_windows'] == [{'text': ref['quote']} for ref in refs.values()]
    cache = json.loads(json.dumps(cache))
    binding, proof = next((key, value) for key, value in cache.items() if key.startswith('clauses:'))
    assert 'citation_refs' not in proof['overall']
    assert await reasoned_review(service, wire, answer, 60, checkpoints=cache) == result
    assert len(calls) == 1
    proof['overall']['citation_refs'] = [999]
    invalid = await reasoned_review(service, wire, answer, 60, checkpoints=cache)
    assert invalid['pending_checks'] == [{'item': 'P0', 'reason': 'invalid_response'}]
    assert binding not in cache and len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('overall_scope', ['reference_metadata', 'original_content', None])
async def test_overall_metadata_scope_is_required_and_independent_of_clause_scope(overall_scope):
    ref = {'source_id': 'bibliography', 'locator': 'p1', 'quote': 'North Reach Survey. Registry Analysis. 2040.'}
    wire = SimpleNamespace(input={'original_question': 'What does the bibliography list?'}, references={1: ref},
        reference_uses={1: 'reference_metadata'})
    answer = AssessmentOutcome(status='possible_answer', points=[{'statement': 'The bibliography lists Registry Analysis from 2040.',
        'evidence': [{**ref, 'role': 'support'}]}], limitations=[])

    class Model:
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            overall = {'verdict': 'supported', 'reason': ''}
            if overall_scope is not None:
                overall['assertion_scope'] = overall_scope
            return json.dumps({'overall': overall, 'clauses': {key: {
                'verdict': 'supported', 'reason': '', 'assertion_scope': 'reference_metadata',
                'witnesses': [{'key': next(iter(witness_choices({1: ref}))), 'scope_relation': 'compatible'}]}
                for key in payload['assertion_clauses']}})

    result = await reasoned_review(SimpleNamespace(settings=Settings(_env_file=None), model_client=Model()), wire, answer, 60)
    if overall_scope is None:
        assert result['pending_checks'] == [{'item': 'P0', 'reason': 'invalid_response'}]
    elif overall_scope == 'original_content':
        assert result['status'] == 'checked' and result['hints'][0]['review_signal'] == 'not_established'
        assert result['positive_witnesses'] == {} and result['candidates'] == {}
    else:
        assert result['status'] == 'checked' and result['hints'] == [] and result['positive_witnesses']
