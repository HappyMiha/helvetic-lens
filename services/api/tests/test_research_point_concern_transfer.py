"""Point corrections retain their exact fresh objections across interruption."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from research_pack_fixtures import witnessed_review
from test_research_review_resilience import fixture, response

from helvetic_lens import research_answer_review as audit
from helvetic_lens import research_final_review as final
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_exploration import AssessmentPoint
from helvetic_lens.product_operations import fingerprint


@pytest.mark.asyncio
@pytest.mark.parametrize('append_coverage,legacy_pending', [(False, False), (True, False), (False, True)])
async def test_fresh_objection_survives_interrupted_citation_repair_without_owning_new_findings(
        monkeypatch, append_coverage, legacy_pending):
    texts, work, wire, parsed = fixture(slots=not append_coverage)
    wire.references[5] = {'source_id': 'registry', 'locator': 'p5',
        'quote': 'South Survey maintains the archive under the current conditions.'}
    wire.references[6] = {'source_id': 'registry', 'locator': 'p6',
        'quote': 'The register accepts applications.'}
    original = parsed.mission_checkpoint.answer.model_dump()
    saved, calls, writers, resumed, reviewed_refs = {}, [], [], [False], []

    async def fast(settings, work, wire, answer, *args, **kwargs):
        index = next((i for i, point in enumerate(answer.points) if point.statement == texts[1]), None)
        return {'status': 'checked', 'hints': [{'path': ['answer', 'points', index],
            'review_signal': 'not_established'}] if index is not None else [], 'decisions': []}

    async def coverage(settings, work, wire, answer, *args, **kwargs):
        statements = [point.statement for point in answer.points]
        missing = texts[1] not in statements or append_coverage and wire.references[6]['quote'] not in statements
        return {'status': 'checked', 'question_coverage': 'missing' if missing else 'covered', 'decisions': [],
            'hints': [{'review_signal': 'requested_part_missing', 'user_request': work['input']['original_question']}]
                if missing else []}

    async def writer(service, current, focus, seconds, **options):
        writers.append(deepcopy(options['correction']))
        if options['correction'] is None:
            assert append_coverage
            assert options['feedback']['issues'][0]['target'] == 'coverage'
            return [AssessmentPoint(statement=wire.references[6]['quote'],
                evidence=[{**wire.references[6], 'role': 'support'}])], '', {
                    'status': 'proposed', 'replacement_targets': ['new']}
        assert 'edit_scope' not in options['correction'], 'An advisory correction can change meaning before approval'
        assert options['correction']['previous_statement'] == texts[1]
        if not resumed[0]:
            raise DomainError('Synthetic writer interruption', 504, 'model_upstream_timeout')
        return [AssessmentPoint(statement=texts[1], evidence=[{**wire.references[5], 'role': 'support'}])], '', {
            'status': 'proposed'}

    class Model:
        async def complete(self, system, serialized, **options):
            value = json.loads(serialized)
            target, item = next(iter(value['final_claims_and_gaps'].items()))
            statement = item.get('statement', item.get('gap'))
            calls.append(statement)
            if statement != texts[1]:
                assert 'prior_review_concerns' not in value, 'A sibling or appended finding cannot inherit this objection'
                return response(value)
            concerns = value['prior_review_concerns']['concerns']
            reviewed_refs.append(value['selected_citation_refs'])
            old = [key for key, issue in concerns.items() if issue['original_refs'] == [2]]
            new = [key for key, issue in concerns.items() if issue['original_refs'] == [5]]
            assert len(old) == 1
            if value['selected_citation_refs'] == [5]:
                assert len(new) == 1, 'New fast concern is separate from the unresolved original concern'
                assert concerns[old[0]]['instruction'] == final.FAST_ADVISORY
            else:
                assert value['selected_citation_refs'] == [2] and not new
            verdict = {'verdict': 'supported', 'reason': 'The supplied statement is supported.', 'citation_refs': [5]}
            raw = {'overall': verdict, 'clauses': {key: verdict for key in value['assertion_clauses']},
                'concern_checks': [{'id': key, 'outcome': 'cannot_assess' if key in old else 'resolved',
                    'reason': 'The old concern remains unresolved.' if key in old else 'The new concern is resolved.',
                    'citation_refs': [] if key in old else [5]} for key in concerns]}
            return json.dumps(witnessed_review(raw, value))

    monkeypatch.setattr(audit, 'audit_points', fast)
    monkeypatch.setattr(audit, 'audit', coverage)
    monkeypatch.setattr(final, 'answer_request', writer)
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    with pytest.raises(DomainError) as error:
        await final.finalize(service, work, wire, parsed, 60, checkpoints=saved, defer_pending=True)
    assert error.value.code == 'model_upstream_timeout'
    assert parsed.mission_checkpoint.answer.model_dump() == original
    plan = saved['final_correction_round']
    point_task = next(task for task in plan['tasks'] if task['points'])
    owner = 'R0' if wire.request_keys else None
    assert point_task['points'] == [fingerprint({'request_key': owner, 'point': original['points'][1]})]
    assert point_task['prior_concerns']['issues'] == [{'target': 'points', 'signal': 'fast_not_established',
        'instruction': final.FAST_ADVISORY, 'original_text': [wire.references[2]['quote']]}]
    assert all('prior_concerns' not in task for task in plan['tasks'] if not task['points'])
    assert plan['completed'] == 0 and calls == [], 'The interrupted correction precedes any factual approval'
    if legacy_pending:
        plan.pop('point_concern_contract')
        point_task.pop('prior_concerns')
        # A previously completed sibling remains in the current answer. The
        # legacy pending task needs re-planning, not restoration of that draft.
        plan['tasks'].insert(0, {'key': owner, 'focus': work['input']['original_question'],
            'points': [fingerprint({'request_key': owner, 'point': original['points'][0]})],
            'gaps': [], 'issues': []})
        plan['completed'], plan['receipts'] = 1, [{'status': 'proposed'}]
    saved, resumed[0] = json.loads(json.dumps(saved)), True
    result = await final.finalize(service, work, wire, parsed, 60, checkpoints=saved, defer_pending=True)
    assert writers[0] == writers[1], 'Automatic resume keeps the same correction controls'
    assert calls.count(texts[1]) == 2 and reviewed_refs == [[5], [2]], (
        'Review the proposed attachment, then the original fallback; neither resolves the original concern')
    assert calls.count(texts[0]) == calls.count(texts[2]) == 1, 'Completed siblings are not repurchased'
    if legacy_pending:
        assert saved['previous_final_correction_round']['completed'] == 1
        assert saved['final_correction_round']['point_concern_contract'] == 'point-task-concerns/v1'
        assert saved['final_correction_round']['completed'] == 1, 'Only the unfinished point was corrected'
        assert parsed.mission_checkpoint.answer.points[0].model_dump() == original['points'][0]
    answer = parsed.mission_checkpoint.answer
    assert [point.statement for point in answer.points] == [texts[0], texts[2],
        *([wire.references[6]['quote']] if append_coverage else [])]
    assert result['factual_review']['withheld_checks'] == [{'item': 'P1', 'reason': 'unresolved_concern'}]
    assert result['question_coverage'] == 'missing'
    assert any(issue.get('original_text') == [wire.references[2]['quote']]
        for concern in saved['repair_concerns'].values() for issue in concern['issues'])
