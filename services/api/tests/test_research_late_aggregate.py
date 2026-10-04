"""Late loss of coverage gets one ordinary amendment, not a fresh research loop."""
import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from research_pack_fixtures import atomic_pack_model

from helvetic_lens import research_answer_review as audit
from helvetic_lens import research_final_review as review
from helvetic_lens.config import Settings
from helvetic_lens.product_exploration import AssessmentOutcome, Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_answer_parts import AGGREGATE_POLICY
from helvetic_lens.research_model_transport import EvidenceWire

GOOD = 'North Reach operates the registry.'
OTHER = 'The public may inspect the register.'
WRONG = 'Permits remain valid after written withdrawal.'
CORRECT = 'Permits cease to be valid when withdrawn.'
QUESTION = 'Who operates the registry, who can inspect it, and when does a permit cease to be valid?'


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['complete', 'interrupted_after_append', 'empty', 'unchanged'])
async def test_removed_point_gets_one_late_aggregate_with_retained_work_and_resume(monkeypatch, mode):
    work = {'phase': 'brief', 'input': {'original_question': QUESTION, 'research_mission': {}, 'sources': [
        {'id': 'a' * 36, 'kind': 'public_source', 'title': 'Registry rules', 'url': 'https://example.org/rules',
            'excerpts': [{'passage': f'p{i}', 'text': text} for i, text in enumerate([GOOD, CORRECT, OTHER], 1)]}]}}
    wire = EvidenceWire(work, mission_schema(Briefing), '')
    refs = {ref['quote']: ref for ref in wire.references.values()}
    answer = AssessmentOutcome(status='possible_answer', points=[{'statement': statement,
        'evidence': [{**refs[original], 'role': 'support'}]}
        for statement, original in [(GOOD, GOOD), (WRONG, CORRECT), (OTHER, OTHER)]], limitations=[])
    parsed = SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer, reason='', action='finish'))
    siblings = deepcopy([answer.points[0], answer.points[2]])
    checked, writers, coverage, saved, retained = [], [], [], {}, []
    clock, reentry_seconds = [0.0], []
    finalize = review.finalize

    async def reenter(*args, **kwargs):
        reentry_seconds.append(args[4])
        return await finalize(*args, **kwargs)

    monkeypatch.setattr(review, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(review, 'finalize', reenter)

    async def fast(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': []}

    async def assess(settings, work, wire, answer, seconds, **kwargs):
        statements = [point.statement for point in answer.points]
        coverage.append(statements)
        covered = WRONG in statements or CORRECT in statements
        return {'status': 'checked', 'question_coverage': 'covered' if covered else 'missing', 'decisions': [],
            'hints': [] if covered else [{'path': ['answer'], 'review_signal': 'requested_part_missing',
                'user_request': QUESTION, 'instruction': 'Complete the original question from retained evidence.'}]}

    class Model:
        @atomic_pack_model
        async def complete(self, system, text, **options):
            value = json.loads(text)
            if 'final_claims_and_gaps' in value:
                item = next(iter(value['final_claims_and_gaps'].values()))
                statement = item.get('statement', item.get('gap'))
                checked.append(statement)
                negative = statement == WRONG
                judgment = {'verdict': 'contradicted' if negative else 'supported',
                    'reason': 'The original states that withdrawal ends validity.' if negative else '',
                    'citation_refs': value['selected_citation_refs']}
                result = {'overall': judgment, 'clauses': {key: judgment for key in value['assertion_clauses']}}
                if value.get('prior_review_concerns'):
                    result['concern_checks'] = [{'id': key, 'outcome': 'resolved', 'reason': '',
                        'citation_refs': judgment['citation_refs']} for key in value['prior_review_concerns']['concerns']]
                return json.dumps(result)
            schema = options['response_schema']
            if 'citation_refs' in schema['properties']:
                return json.dumps({'citation_refs': {key: item['items']['enum']
                    for key, item in schema['properties']['citation_refs']['properties'].items()}})
            if value.get('correction_target'):
                writers.append('point')
                assert value['correction_target']['previous_statement'] == WRONG
                clock[0] += 12  # The late amendment inherits the spent step time.
                return json.dumps({'points': []})  # This point cannot survive its completed correction.
            writers.append('aggregate')
            assert value['requested_part'] == QUESTION
            assert value['retained_answer'] == {'P0': GOOD, 'P1': OTHER}
            assert value['new_point_capacity'] == 6 and value['retained_gaps'] == []
            if mode == 'empty':
                return json.dumps({'points': [], 'remaining_gap': ''})
            statement, target = (GOOD, 'P0') if mode == 'unchanged' else (CORRECT, 'new')
            citation = next(p['citation_ref'] for source in value['sources'] for p in source['passages']
                if p.get('text') == statement)
            return json.dumps({'points': [{'statement': statement, 'replace_point': target,
                'evidence': [{'citation_ref': citation, 'role': 'support'}]}], 'remaining_gap': ''})

    interrupted = False

    def retain():
        nonlocal interrupted
        snapshot = json.loads(json.dumps(saved))
        retained.append(snapshot)
        plan = snapshot.get('final_correction_round', {})
        if (mode == 'interrupted_after_append' and not interrupted
                and len(plan.get('tasks', [])) == 2 and plan['completed'] == 1):
            interrupted = True
            raise asyncio.CancelledError

    monkeypatch.setattr(audit, 'audit_points', fast)
    monkeypatch.setattr(audit, 'audit', assess)
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    if mode == 'interrupted_after_append':
        with pytest.raises(asyncio.CancelledError):
            await finalize(service, work, wire, parsed, 90, checkpoints=saved,
                on_progress=retain, defer_pending=True)
        assert writers == ['point'] and saved == retained[-1]
        assert len(saved['final_correction_round']['receipts']) == 1
        saved = json.loads(json.dumps(saved))
        parsed.mission_checkpoint.answer = AssessmentOutcome.model_validate_json(answer.model_dump_json())

    result = await finalize(service, work, wire, parsed, 90, checkpoints=saved,
        on_progress=retain, defer_pending=True)
    answer = parsed.mission_checkpoint.answer
    complete = mode in {'complete', 'interrupted_after_append'}
    assert writers == ['point', 'aggregate']
    assert reentry_seconds == ([] if mode == 'interrupted_after_append' else [78])
    assert answer.points[:2] == siblings and WRONG not in [p.statement for p in answer.points]
    assert [GOOD, OTHER] in coverage, 'Coverage must be checked after removing the rejected point'
    assert result['question_coverage'] == ('covered' if complete else 'missing')
    assert answer.status == ('possible_answer' if complete else 'partial')
    assert checked.count(WRONG) == checked.count(OTHER) == 1
    assert checked.count(GOOD) == (2 if mode == 'unchanged' else 1)
    plan = saved['final_correction_round']
    assert len(plan['tasks']) == plan['completed'] == len(plan['receipts']) == 2
    assert plan['receipts'][-1]['amendment_contract'] == AGGREGATE_POLICY
    assert not plan['tasks'][-1]['points'] and plan['tasks'][-1]['focus'] == QUESTION
    if complete:
        assert answer.points[-1].statement == CORRECT and checked.count(CORRECT) == 1
    before = list(writers), list(checked), deepcopy(answer.model_dump())
    repeated = await finalize(service, work, wire, parsed, 90,
        checkpoints=json.loads(json.dumps(saved)), defer_pending=True)
    assert (writers, checked, answer.model_dump()) == before
    assert repeated['question_coverage'] == result['question_coverage']
