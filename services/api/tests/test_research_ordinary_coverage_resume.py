"""Ordinary completion cannot skip missing-request repair after coverage interruption."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from research_pack_fixtures import atomic_pack_model
from test_research_late_aggregate import CORRECT, GOOD, OTHER, QUESTION, WRONG

from helvetic_lens import research_answer_review as audit
from helvetic_lens import research_final_coverage as coverage
from helvetic_lens import research_final_review as final
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.decision_engines import Decision, DecisionUnavailable
from helvetic_lens.product_exploration import AssessmentOutcome, Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_model_transport import EvidenceWire
from helvetic_lens.research_synthesis_resume import completed_work


@pytest.mark.asyncio
@pytest.mark.parametrize(('failure', 'code'), [
    ('step_deadline', 'research_review_yield'),
    ('unavailable', 'model_temporarily_unavailable'),
    ('invalid', 'research_review_incomplete'),
])
async def test_ordinary_current_subset_coverage_resumes_into_one_aggregate_amendment(monkeypatch, failure, code):
    work = {'phase': 'brief', 'input': {'original_question': QUESTION, 'research_mission': {}, 'sources': [
        {'id': 'a' * 36, 'kind': 'public_source', 'title': 'Registry rules', 'url': 'https://example.org/rules',
            'excerpts': [{'passage': f'p{i}', 'text': text} for i, text in enumerate([GOOD, CORRECT, OTHER], 1)]}]}}
    wire = EvidenceWire(work, mission_schema(Briefing), '')
    refs = {ref['quote']: ref for ref in wire.references.values()}
    answer = AssessmentOutcome(status='possible_answer', points=[{'statement': statement,
        'evidence': [{**refs[original], 'role': 'support'}]}
        for statement, original in [(GOOD, GOOD), (WRONG, CORRECT), (OTHER, OTHER)]], limitations=[])
    parsed = SimpleNamespace(mission_checkpoint=SimpleNamespace(answer=answer, reason='', action='finish'))
    clock, phase, saved, atomic = [0.0], ['first'], {}, {}
    judgments, writers, requests = [], [], []

    async def fast(*args, **kwargs):
        return {'status': 'checked', 'hints': [], 'decisions': []}

    class Engine:
        async def choose(self, payload, system, criteria):
            assert system == coverage.SYSTEM and criteria == coverage.CRITERIA
            statements = list(payload['answer_points'].values())
            requests.append((phase[0], statements))
            if statements == [GOOD, OTHER] and phase[0] == 'first':
                if failure == 'unavailable':
                    raise DecisionUnavailable('unavailable')
                assert failure == 'invalid'
                return Decision('jev', 'fixture', 'invented_choice', {}, 1, 1, 0, 1, 1)
            choice = 'covered' if WRONG in statements or CORRECT in statements else 'missing'
            return Decision('jev', 'fixture', choice, {}, 1, 1, 0, 1, 1)

    class Model:
        @atomic_pack_model
        async def complete(self, system, text, **options):
            payload = json.loads(text)
            if 'final_claims_and_gaps' in payload:
                item = next(iter(payload['final_claims_and_gaps'].values()))
                statement = item['statement']
                judgments.append(statement)
                judgment = {'verdict': 'contradicted' if statement == WRONG else 'supported',
                    'reason': '', 'citation_refs': payload['selected_citation_refs']}
                result = {'overall': judgment, 'clauses': {key: judgment for key in payload['assertion_clauses']}}
                if payload.get('prior_review_concerns'):
                    result['concern_checks'] = [{'id': key, 'outcome': 'resolved', 'reason': '',
                        'citation_refs': judgment['citation_refs']} for key in payload['prior_review_concerns']['concerns']]
                return json.dumps(result)
            schema = options['response_schema']
            if 'citation_refs' in schema['properties']:
                return json.dumps({'citation_refs': {key: item['items']['enum']
                    for key, item in schema['properties']['citation_refs']['properties'].items()}})
            if payload.get('correction_target'):
                assert payload['correction_target']['previous_statement'] == WRONG
                writers.append('point')
                if failure == 'step_deadline':
                    clock[0] = 79.0
                return json.dumps({'points': []})
            writers.append('aggregate')
            assert phase[0] == 'resume'
            assert payload['requested_part'] == QUESTION
            assert payload['retained_answer'] == {'P0': GOOD, 'P1': OTHER}
            ref = next(p['citation_ref'] for source in payload['sources'] for p in source['passages']
                if p.get('text') == CORRECT)
            return json.dumps({'points': [{'statement': CORRECT, 'replace_point': 'new',
                'evidence': [{'citation_ref': ref, 'role': 'support'}]}], 'remaining_gap': ''})

    def retain():
        atomic.update(answer=deepcopy(parsed.mission_checkpoint.answer.model_dump()), parts=deepcopy(saved))

    monkeypatch.setattr(audit, 'audit_points', fast)
    monkeypatch.setattr(audit.decision, 'engines', lambda settings: {'jev': Engine()})
    for module in (audit, coverage, final):
        monkeypatch.setattr(module, 'monotonic', lambda: clock[0])
    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    with pytest.raises(DomainError) as exc:
        await final.finalize(service, work, wire, parsed, 90, checkpoints=saved,
            on_progress=retain, defer_pending=True)
    assert exc.value.code == code
    assert [p.statement for p in parsed.mission_checkpoint.answer.points] == [GOOD, OTHER]
    assert writers == ['point'] and judgments == [GOOD, WRONG, OTHER]
    assert 'deferred_final_review' not in saved, 'This is ordinary completion, not qualified delivery'
    assert saved['coverage_interruption']['decisions'][0]['choice'] == 'unavailable'
    assert all(r['choice'] in {'covered', 'missing'} for r in saved['delivered_coverage'].values())
    assert not any('coverage_interruption' in key for key in completed_work({'parts': saved}))

    saved = json.loads(json.dumps(atomic['parts']))
    parsed.mission_checkpoint.answer = AssessmentOutcome.model_validate(atomic['answer'])
    clock[0], phase[0] = 0.0, 'resume'
    result = await final.finalize(service, work, wire, parsed, 90, checkpoints=saved,
        on_progress=retain, defer_pending=True)
    assert result['question_coverage'] == 'covered'
    assert [p.statement for p in parsed.mission_checkpoint.answer.points] == [GOOD, OTHER, CORRECT]
    assert writers == ['point', 'aggregate'] and judgments == [GOOD, WRONG, OTHER, CORRECT]
    assert ('resume', [GOOD, OTHER]) in requests
    assert 'coverage_interruption' not in saved
    before = deepcopy((requests, writers, judgments))
    await final.finalize(service, work, wire, parsed, 90, checkpoints=json.loads(json.dumps(saved)), defer_pending=True)
    assert (requests, writers, judgments) == before, 'Exact completed coverage and factual work are not repurchased'
