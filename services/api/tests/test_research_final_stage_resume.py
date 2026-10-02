"""An ordinary worker resume must not undo a final-review correction."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_research_answer_parts import selection_json

from helvetic_lens import research_answer_review as review
from helvetic_lens import research_gateway as gateway
from helvetic_lens.analysis import ModelClient
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_exploration import AssessmentPoint, Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_synthesis_resume import KEY


@pytest.mark.asyncio
async def test_multipart_narrowed_draft_survives_gateway_retry_with_same_citations_and_sibling(monkeypatch):
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    good = 'North Reach operates the registry.'
    bad = good + ' North Reach owns the archive.'
    sibling = 'The public archive is available.'
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'Who operates the registry? Is the archive available?', 'research_mission': {},
        'sources': [{'id': 'a' * 36, 'kind': 'public_source', 'url': 'https://example.org/registry',
            'excerpts': [{'passage': 'p1', 'text': good}, {'passage': 'p2', 'text': sibling}]}]}}
    initial = deepcopy(work)
    def point(statement, ref):
        return {'statement': statement, 'evidence': [{'citation_ref': ref, 'role': 'support'}]}
    raw = json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'responses': {
        'r1': {'disposition': 'answered', 'remaining_gap': '', 'points': [point(bad, 1)]},
        'r2': {'disposition': 'answered', 'remaining_gap': '', 'points': [point(sibling, 2)]}}}, 'next_action': 'finish'})
    calls, interrupted = [], [False]

    async def complete(system, user, **kwargs):
        value = json.loads(user)
        if 'final_claims_and_gaps' in value:
            statement = next(iter(value['final_claims_and_gaps'].values()))['statement']
            calls.append(('final', statement))
            def judgment(verdict, refs):
                return {'verdict': verdict, 'reason': '', 'citation_refs': refs}
            if statement == bad:
                return json.dumps({'overall': judgment('not_established', []),
                    'clauses': {'S0': judgment('supported', [1]), 'S1': judgment('not_established', [])},
                    **({'concern_checks': [{'id': key, 'outcome': 'remains', 'reason': '', 'citation_refs': [1]}
                        for key in value['prior_review_concerns']['concerns']]} if value.get('prior_review_concerns') else {})})
            assert statement in {good, sibling}
            if statement == good and not interrupted[0]:
                interrupted[0] = True
                raise DomainError('Synthetic interruption after narrowing', 503, 'model_upstream_timeout')
            verdict = judgment('supported', [1 if statement == good else 2])
            return json.dumps({'overall': verdict, 'clauses': {'S0': verdict},
                **({'concern_checks': [{'id': key, 'outcome': 'resolved', 'reason': '', 'citation_refs': [1]}
                    for key in value['prior_review_concerns']['concerns']]} if value.get('prior_review_concerns') else {})})
        if 'requested_part' in value:
            first = value['requested_part'] == 'Who operates the registry?'
            calls.append(('synthesis', value['requested_part']))
            if 'citation_refs' in kwargs['response_schema']['properties']:
                return selection_json([1 if first else 2], kwargs)
            return json.dumps({**point(bad if first else sibling, 1 if first else 2), 'remaining_gap': ''})
        calls.append(('draft', ''))
        return raw

    async def unchanged(*args, **kwargs):
        return AssessmentPoint(statement=bad, evidence=[{'source_id': 'a' * 36, 'locator': 'p1',
            'quote': good, 'role': 'support'}]), '', {'status': 'proposed'}
    async def audit(*args, **kwargs):
        return {'status': 'checked', 'question_coverage': 'covered', 'hints': [], 'decisions': []}
    async def original(*args, **kwargs):
        return None
    monkeypatch.setattr(model, 'complete', complete)
    monkeypatch.setattr(review, 'audit', audit)
    monkeypatch.setattr(review, 'original_check', original)
    monkeypatch.setattr('helvetic_lens.research_final_review.answer_request', unchanged)
    schema = mission_schema(Briefing)
    service = SimpleNamespace(settings=settings, model_client=model)
    with pytest.raises(DomainError, match='Synthetic interruption'):
        await gateway.complete(service, work, '', schema, 90)
    saved = json.loads(json.dumps(work[KEY]))
    assert saved['stage'] == 'finalizing'
    slots = json.loads(saved['raw'])['answer']['responses']
    assert slots['r1']['points'] == [point(good, 1)] and slots['r2']['points'] == [point(sibling, 2)]
    before = len(calls)
    resumed = {**initial, KEY: saved}
    result = schema.model_validate_json(await gateway.complete(service, resumed, '', schema, 90))
    answer = result.mission_checkpoint.answer
    assert calls[before:] == [('final', good)], 'Resume only the pending check, never restore the rejected draft'
    assert [p.statement for p in answer.points] == [good, sibling]
    assert [p.evidence[0].quote for p in answer.points] == [good, sibling]
    assert answer.status == 'possible_answer' and not answer.limitations
    assert resumed['model_route']['resumed_stage'] == 'finalizing'
    assert not gateway.answer_quantity_errors(answer)
