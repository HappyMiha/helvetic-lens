"""A correction inherits evidence obligations, not optional retrieval fill."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_research_clause_witnesses import response
from test_research_point_review_corpus import corpus

from helvetic_lens import research_active_retrieval as retrieval
from helvetic_lens import research_evidence_pack as packing
from helvetic_lens import research_final_review as final
from helvetic_lens.config import Settings
from helvetic_lens.product_exploration import AssessmentPoint
from helvetic_lens.research_review_witnesses import witness_choices


@pytest.mark.asyncio
@pytest.mark.parametrize('negative_sibling', [False, True])
async def test_rebound_candidate_preserves_actual_and_prior_witnesses_without_promoting_background(monkeypatch, negative_sibling):
    wire, answer, concerns = corpus()
    wire.references[7]['quote'] = 'An unrelated administrative inventory.'
    wire.input['sources'][-1]['excerpts'][0]['text'] = wire.references[7]['quote']
    first = 'The permit ordinarily remains in effect.'
    answer.points[0].statement = first + (' It can never terminate.' if negative_sibling else '')
    before = deepcopy(wire.references)
    selections, calls = [], []
    original_selector = packing.select_evidence

    async def rank(service, current, task, seconds, **options):
        assert current.references == before, 'Both checks search the complete unchanged authorized corpus'
        return {'rankings': [{'query': 'permit', 'references': list(current.references),
            'scores': {ref: 1 for ref in current.references}}],
            'coverage': {'method': 'scripted_ranking', 'semantic_status': 'not_evaluated'}}

    async def select(service, current, task, seconds, **options):
        selections.append(set(options['required_refs']))
        return await original_selector(service, current, task, seconds, **options)

    class Model:
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            calls.append(payload)
            refs = {passage['citation_ref']: wire.references[passage['citation_ref']]
                for source in payload['source_context'] for passage in source['passages']}
            assert set(refs) == set(before), 'Whole structural units and optional background remain available'
            value = response(payload, refs, cited=2)
            value['concern_checks'][0]['citation_refs'] = [4]
            if len(calls) == 1 and negative_sibling:
                value['overall']['verdict'] = 'not_established'
                value['clauses']['S1']['verdict'] = 'contradicted'
                value['clauses']['S1']['witnesses'] = [{'key': next(key for key, ref in witness_choices(refs).items()
                    if ref == 5), 'scope_relation': 'compatible'}]
            return json.dumps(value)

    monkeypatch.setattr(retrieval, 'rank_evidence', rank)
    monkeypatch.setattr(packing, 'select_evidence', select)
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    result = await final.reasoned_review(service, wire, answer, 60, concerns=concerns)
    candidate = result['candidates']['P0']
    expected = {1, 2, 3, 4, *([5] if negative_sibling else [])}
    assert set(candidate['context_refs']) == expected
    assert candidate['statement'] == first
    assert [ref['quote'] for ref in candidate['evidence']] == [wire.references[2]['quote']]
    answer.points[0] = AssessmentPoint(statement=candidate['statement'], evidence=candidate['evidence'])
    inherited = deepcopy(concerns)
    inherited['P0']['context_refs'] = candidate['context_refs']
    reviewed = await final.reasoned_review(service, wire, answer, 60, concerns=inherited)
    assert reviewed['status'] == 'checked' and not reviewed['pending_checks']
    assert selections == [{1, 3}, expected]
    assert len(calls) == 2 and wire.references == before
    # Ref6 is the complete neighboring qualification to ref5; it remains in
    # the actual review packet without itself becoming another primary seed.
    assert 6 not in candidate['context_refs'] and 7 not in candidate['context_refs']
