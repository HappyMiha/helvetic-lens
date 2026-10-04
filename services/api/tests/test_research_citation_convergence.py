"""Growing cited witness sets remain proposals until their ordinary review passes."""
import json
from types import SimpleNamespace

import pytest
from test_research_point_witness_capacity import fixture

from helvetic_lens import research_active_retrieval as retrieval
from helvetic_lens import research_answer_review as audit
from helvetic_lens import research_final_review as final
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_exploration import AssessmentOutcome
from helvetic_lens.product_operations import fingerprint


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', ['stable', 'interrupted', 'contradicted', 'unresolved', 'oversized'])
async def test_reviewed_witnesses_grow_eight_to_twelve_then_require_current_review(monkeypatch, outcome):
    wire, _ = fixture(18)
    text = 'The archive permits consultation under its conditions. Reproduction retains the stated restrictions.'
    answer = AssessmentOutcome(status='partial', limitations=[], points=[{
        'statement': text, 'evidence': [
            {**wire.references[1], 'role': 'support'}, {**wire.references[18], 'role': 'context'}]}])
    original = answer.points[0].model_dump()
    concern = {'previous_statements': ['Earlier wording omitted a condition.'], 'issues': [
        {'target': 'points', 'signal': 'earlier_objection',
            'instruction': 'Check the original restriction.', 'original_refs': [17]}]}
    saved = {'final_correction_round': {'contract': 'literal-request-repair/v1',
        'tasks': [], 'observations': [], 'completed': 0, 'receipts': []},
        'repair_concerns': {fingerprint({'request_key': None, 'point': original}): concern}}
    settings = Settings(_env_file=None)
    parsed = SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer, reason=''))
    calls, successful, snapshots = [], [], []
    interrupted = False

    def retain():
        snapshots.append(json.loads(json.dumps({'parts': saved, 'answer': answer.model_dump()})))

    async def rank(*args, **kwargs):
        return {'rankings': [{'query': text, 'references': list(wire.references),
            'scores': {key: 1 for key in wire.references}}], 'coverage': {'method': 'scripted'}}

    async def fast(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': [], 'points_checked': len(answer.points)}

    async def coverage(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': [], 'question_coverage': 'covered'}

    class Model:
        async def complete(self, system, serialized, **options):
            nonlocal interrupted
            payload = json.loads(serialized)
            selected = set(payload['selected_citation_refs'])
            calls.append(selected)
            assert payload['final_claims_and_gaps']['P0']['statement'] == text
            assert 18 in selected, 'Original context evidence cannot be discarded'
            assert any(e['locator'] == wire.references[18]['locator'] and e['role'] == 'context'
                for e in snapshots[-1]['answer']['points'][0]['evidence']) if snapshots else True
            concerns = payload['prior_review_concerns']['concerns']
            assert any(17 in c['original_refs'] for c in concerns.values())
            passages = {p['citation_ref']: p for source in payload['source_context']
                for p in source['passages'] if 'citation_ref' in p}
            assert set(passages) == set(wire.references), 'Whole originals and contrary context still reach review'
            if len(selected) > 2:
                retained = snapshots[-1]
                assert retained['answer'] == answer.model_dump(), 'Checkpoint the exact new point before review'
                assert fingerprint({'request_key': None, 'point': answer.points[0].model_dump()}) in (
                    retained['parts']['citation_attachment_states'])
            if len(selected) == 13 and outcome == 'interrupted' and not interrupted:
                interrupted = True
                raise DomainError('Provider pause', 429, 'model_rate_limited')
            assert selected not in successful, 'Completed exact reviews must not be purchased again'
            successful.append(selected)
            verdict = 'contradicted' if len(selected) == 13 and outcome == 'contradicted' else 'supported'
            witnesses = list(range(1, 9 if len(selected) == 2 else 13))
            if outcome == 'oversized' and len(selected) == 9:
                settings.apertus_context_chars = 1
            return json.dumps({'overall': {'verdict': verdict, 'reason': 'The current originals govern.'},
                'clauses': {key: {'verdict': verdict, 'reason': 'The exact clause was checked.',
                    'witnesses': [{'key': passages[ref]['witness_key'], 'scope_relation': 'compatible'}
                        for ref in witnesses[index*len(witnesses)//2:(index+1)*len(witnesses)//2]]}
                    for index, key in enumerate(payload['assertion_clauses'])},
                'concern_checks': [{'id': key, 'outcome': 'cannot_assess'
                    if len(selected) == 13 and outcome == 'unresolved' else
                    'remains' if verdict == 'contradicted' else 'resolved',
                    'reason': 'The earlier restriction remains subject to the current originals.',
                    'citation_refs': [] if len(selected) == 13 and outcome == 'unresolved' else [17]}
                    for key in concerns]})

    monkeypatch.setattr(retrieval, 'rank_evidence', rank)
    monkeypatch.setattr(audit, 'audit_points', fast)
    monkeypatch.setattr(audit, 'audit', coverage)
    service = SimpleNamespace(settings=settings, model_client=Model())
    if outcome == 'interrupted':
        with pytest.raises(DomainError, match='Provider pause'):
            await final.finalize(service, wire.work, wire, parsed, 60, checkpoints=saved, on_progress=retain)
        resumed = json.loads(json.dumps({'parts': saved, 'answer': answer.model_dump()}))
        saved = resumed['parts']
        answer = AssessmentOutcome.model_validate(resumed['answer'])
        parsed.mission_checkpoint.answer = answer
        assert len(answer.points[0].evidence) == 13
    result = await final.finalize(service, wire.work, wire, parsed, 60, checkpoints=saved, on_progress=retain)
    assert [len(refs) for refs in calls] == ([2, 9, 13, 13] if outcome == 'interrupted' else
        [2, 9] if outcome == 'oversized' else [2, 9, 13])
    assert len(saved['citation_attachment_states']) == 3
    if outcome in {'stable', 'interrupted'}:
        assert not result['rejected_points'] and len(answer.points) == 1
        assert answer.points[0].statement == text
        assert [e.model_dump() for e in answer.points[0].evidence] == [
            *({**wire.references[key], 'role': 'support'} for key in range(1, 13)),
            {**wire.references[18], 'role': 'context'}]
        retained = saved['repair_concerns'][fingerprint({'request_key': None, 'point': answer.points[0].model_dump()})]
        assert retained['issues'][0] == concern['issues'][0]
    else:
        assert not answer.points and result['rejected_points'] == [0]
        if outcome != 'contradicted':
            assert result['factual_review']['withheld_checks'] == [{'item': 'P0',
                'reason': 'unresolved_concern' if outcome == 'unresolved' else 'research_evidence_group_too_large'}]
    assert original == {'statement': text, 'evidence': [
        {**wire.references[1], 'role': 'support'}, {**wire.references[18], 'role': 'context'}]}
