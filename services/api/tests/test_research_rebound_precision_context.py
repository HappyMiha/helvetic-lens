"""A rebound retains short original context without becoming an approved answer."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_research_point_witness_capacity import fixture

from helvetic_lens import research_active_retrieval as retrieval
from helvetic_lens import research_answer_review as audit
from helvetic_lens import research_evidence_pack as packing
from helvetic_lens import research_final_review as final
from helvetic_lens.config import Settings
from helvetic_lens.product_exploration import AssessmentOutcome, AssessmentPoint
from helvetic_lens.product_operations import fingerprint
from helvetic_lens.research_answer_parts import precision_context_refs
from helvetic_lens.research_gateway import answer_quantity_errors


def precision_fixture():
    wire, _ = fixture(14)
    heading = 'Archive conditions, version 2.0.'
    wire.references[13]['quote'] = heading
    wire.input['sources'][0]['excerpts'][12]['text'] = heading
    text = 'Version 2.0 permits consultation. The archive permits reproduction under its conditions.'
    return wire, text


@pytest.mark.parametrize('heading', ['current', 'foreign', 'missing', 'stale_attachment', 'long'])
def test_precision_context_requires_current_source_identity_and_never_rewrites_witnesses(heading):
    wire, text = precision_fixture()
    if heading == 'foreign':
        wire.references[13]['source_id'] = 'another-original'
    elif heading == 'missing':
        del wire.references[13]
    elif heading == 'long':
        wire.references[13]['quote'] *= 10
    point = AssessmentPoint(statement=text, evidence=[
        {**wire.references[key], 'role': 'support'} for key in range(1, 13)])
    if heading == 'stale_attachment':
        wire.references[1]['quote'] += ' Changed after the proposal.'
    before = point.model_dump()
    refs_before = deepcopy(wire.references)
    # An exact alias is not a second context attachment.
    if 13 in wire.references:
        wire.references[15] = deepcopy(wire.references[13])
        refs_before[15] = deepcopy(wire.references[15])
    added = precision_context_refs(point, wire.references)
    assert point.model_dump() == before and wire.references == refs_before
    if heading == 'current':
        assert len(added) == 1 and added[0] in {13, 15}
        assert wire.references[added[0]]['quote'] == 'Archive conditions, version 2.0.'
    else:
        assert added == []
        assert answer_quantity_errors(AssessmentOutcome(status='partial', points=[point], limitations=[]))


@pytest.mark.asyncio
@pytest.mark.parametrize('next_result', ['supported', 'contradicted', 'oversized', 'cached_preceding_algorithm',
    'unresolved_inherited', 'shortened'])
async def test_finalizer_rebound_completes_large_witness_union_then_requires_ordinary_review(monkeypatch, next_result):
    wire, text = precision_fixture()
    answer = AssessmentOutcome(status='partial', limitations=[], points=[
        {'statement': text + (' An unsupported exception applies.' if next_result == 'shortened' else ''),
            # The cache migration case needs missing context: citation-only
            # completion now correctly retains an already attached heading.
            'evidence': [{**wire.references[1 if next_result == 'cached_preceding_algorithm' else 13],
                'role': 'context'}]}])
    original = answer.points[0].model_dump()
    inherited = {'previous_statements': ['Earlier wording omitted an original restriction.'],
        'issues': [{'target': 'points', 'signal': 'earlier_objection',
            'instruction': 'Check the exact restriction.', 'original_refs': [14]}]}
    if next_result == 'unresolved_inherited':
        inherited['issues'][0]['signal'] = 'omitted_qualification'
    saved = {'final_correction_round': {'contract': 'literal-request-repair/v1',
        'tasks': [], 'observations': [], 'completed': 0, 'receipts': []},
        'repair_concerns': {fingerprint({'request_key': None, 'point': original}): inherited}}
    calls, selections = [], []
    settings = Settings(_env_file=None)
    original_select = packing.select_evidence

    async def rank(*args, **kwargs):
        return {'rankings': [{'query': text, 'references': list(wire.references),
            'scores': {key: 1 for key in wire.references}}], 'coverage': {'method': 'scripted'}}

    async def select(*args, **kwargs):
        selections.append(set(kwargs['required_refs']))
        return await original_select(*args, **kwargs)

    async def fast(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': [], 'points_checked': 1}

    async def coverage(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': [], 'question_coverage': 'covered'}

    class Model:
        async def complete(self, system, serialized, **options):
            value = json.loads(serialized)
            calls.append(value)
            passages = {p['citation_ref']: p for source in value['source_context'] for p in source['passages']}
            assert set(passages) == set(wire.references), 'Whole original context must reach the review'
            assert value['final_claims_and_gaps']['P0']['statement'] == (text if len(calls) == 2 else original['statement'])
            concerns = value['prior_review_concerns']['concerns']
            assert any(14 in item['original_refs'] for item in concerns.values())
            if len(calls) == 2:
                assert set(value['selected_citation_refs']) == set(range(1, 14))
                omissions = [item for item in concerns.values() if item['signal'] == 'omitted_qualification']
                assert len(omissions) == (1 if next_result in {'shortened', 'unresolved_inherited'} else 0)
                if next_result == 'unresolved_inherited':
                    assert omissions[0]['instruction'] == inherited['issues'][0]['instruction']
                assert len(answer.points[0].evidence) == 13
                assert [ref.model_dump() for ref in answer.points[0].evidence[:12]] == [
                    {**wire.references[key], 'role': 'context'
                        if next_result == 'cached_preceding_algorithm' and key == 1 else 'support'}
                    for key in range(1, 13)]
                assert answer.points[0].evidence[12].model_dump() == {**wire.references[13], 'role': 'context'}
            verdict = 'contradicted' if len(calls) == 2 and next_result == 'contradicted' else 'supported'
            if len(calls) == 1 and next_result == 'oversized':
                # The next real selector must honor a restrictive current
                # envelope, not clip the newly required context to fit.
                settings.apertus_context_chars = 1
            return json.dumps({'overall': {'verdict': 'not_established' if next_result == 'shortened' and len(calls) == 1
                    else verdict, 'reason': 'The original conditions govern.'},
                'clauses': {key: {'verdict': 'not_established' if index == 2 else verdict,
                    'reason': 'The exact clauses govern.',
                    'witnesses': [{'key': passages[ref]['witness_key'], 'scope_relation': 'compatible'}
                        for ref in ([14] if index == 2 else list(range(1, 7)) if index == 0 else list(range(7, 13)))]}
                    for index, key in enumerate(value['assertion_clauses'])},
                'concern_checks': [{'id': key, 'outcome': 'cannot_assess'
                    if len(calls) == 2 and next_result == 'unresolved_inherited'
                    else 'remains' if verdict == 'contradicted' else 'resolved',
                    'reason': 'The original restriction was considered.',
                    'citation_refs': [] if len(calls) == 2 and next_result == 'unresolved_inherited' else [14]}
                    for key in concerns]})

    monkeypatch.setattr(retrieval, 'rank_evidence', rank)
    monkeypatch.setattr(packing, 'select_evidence', select)
    monkeypatch.setattr(audit, 'audit_points', fast)
    monkeypatch.setattr(audit, 'audit', coverage)
    parsed = SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer, reason=''))
    service = SimpleNamespace(settings=settings, model_client=Model())
    if next_result == 'cached_preceding_algorithm':
        with monkeypatch.context() as previous:
            previous.setattr(final, 'PRECISION_CONTEXT_POLICY', 'preceding-host-processing')
            previous.setattr(final, 'precision_context_refs', lambda *args: [])
            rejected = await final.finalize(service, wire.work, wire, parsed, 60, checkpoints=saved)
        assert rejected['rejected_points'] == [0] and answer.points == [] and len(calls) == 1
        assert not saved['narrowing_attempts']
        saved = json.loads(json.dumps(saved))
        # Supply the same private proposal, not an invented restoration of a
        # previously delivered subset. Only the host algorithm binding changed.
        answer.points = [AssessmentPoint.model_validate(original)]
        answer.status, answer.limitations = 'partial', []
    result = await final.finalize(service, wire.work, wire, parsed, 60, checkpoints=saved)
    assert selections == ([{1, 14}] * 2 if next_result == 'cached_preceding_algorithm' else [{13, 14}]) \
        + [set(range(1, 15))]
    assert len(saved['narrowing_attempts']) == 2
    rebound = next(v for k, v in saved['repair_concerns'].items()
        if k != fingerprint({'request_key': None, 'point': original}))
    assert rebound['previous_statements'][-1] == original['statement']
    assert rebound['issues'][0] == inherited['issues'][0]
    assert set(rebound['context_refs']) == (set(range(1, 15)) -
        ({13} if next_result == 'cached_preceding_algorithm' else set()))
    if next_result in {'supported', 'cached_preceding_algorithm', 'shortened'}:
        assert len(calls) == 2 and len(answer.points) == 1
        assert answer.points[0].statement == text
        assert len(answer.points[0].evidence) == 13
        assert not result['rejected_points']
    else:
        assert answer.points == [] and result['rejected_points'] == [0]
        assert len(calls) == (1 if next_result == 'oversized' else 2)
        if next_result == 'oversized':
            assert result['factual_review']['withheld_checks'] == [
                {'item': 'P0', 'reason': 'research_evidence_group_too_large'}]
        elif next_result == 'unresolved_inherited':
            assert result['factual_review']['withheld_checks'] == [{'item': 'P0', 'reason': 'unresolved_concern'}]
