"""Completed answer delivery and future research controls have separate owners."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_product_checked_delivery import finish
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_exploration import adapters, start

from helvetic_lens import product_research_mission as mission
from helvetic_lens import research_gateway
from helvetic_lens.analysis import ModelClient
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_exploration import Briefing
from helvetic_lens.product_investigation_models import InvestigationBranch
from helvetic_lens.product_operations import fingerprint
from helvetic_lens.research_synthesis_resume import KEY


@pytest.mark.parametrize('control', ['incomplete_clarify', 'cited_clarify', 'rejected_citation'])
def test_checked_answer_publishes_independently_and_failed_apply_resumes_private_candidate(signed, monkeypatch, control):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    model_complete = model.complete
    generated, attempts, saved = [], [], {}

    async def briefing(system, user, **kwargs):
        raw = await model_complete(system, user, **kwargs)
        if kwargs.get('response_schema', {}).get('title') != 'Briefing':
            return raw
        generated.append(True)
        value = json.loads(raw)
        first = value['findings'][0]
        ref = {key: first[key] for key in ('source_id', 'quote', 'locator')}
        value.update(clarification='', directions=[], mission_checkpoint={
            'answer': {'status': 'partial', 'points': [{'statement': first['statement'],
                'evidence': [{**ref, 'role': 'support'}]}], 'limitations': ['A genuine requested uncertainty remains.']},
            'action': 'clarify', 'reason': 'PRIVATE DRAFT CONTROL REASON',
            'next_checks': [], 'deepen_branches': []})
        if control == 'cited_clarify':
            value.update(clarification='Which of these source-supported directions should be pursued?', directions=[
                {**ref, 'question': 'What was the initial registry scope?', 'why': 'The retained original distinguishes initial scope.'},
                {**ref, 'question': 'What changed in the later registry scope?', 'why': 'The retained original identifies later scope.'}])
            value['mission_checkpoint']['deepen_branches'] = ['an-unexecuted-private-frontier']
        return json.dumps(value)

    monkeypatch.setattr(model, 'complete', briefing)
    execute = research_gateway.execute

    async def completed(service, work, seconds):
        if work['phase'] != 'brief':
            return await execute(service, work, seconds)
        attempts.append(work['branch_id'])
        if len(attempts) == 1:
            result = await execute(service, work, seconds)
            saved['class'] = type(result)
            saved['quote'] = result.mission_checkpoint.answer.points[0].evidence[0].quote
            if control == 'rejected_citation':
                result.mission_checkpoint.answer.points[0].evidence[0].quote = 'A quotation not present in the current original.'
        else:
            assert work[KEY] == saved['checkpoint'], 'The same-ID retry must receive the exact unpublished final candidate'
            result = saved['class'].model_validate_json(work[KEY]['raw'])
            assert result.mission_checkpoint.answer.points[0].evidence[0].quote != saved['quote']
            # Simulate a fresh checked handoff over the retained proposal. The
            # model draft is not purchased again; actual source validation runs.
            result.mission_checkpoint.answer.points[0].evidence[0].quote = saved['quote']
        cp = {'stage': 'finalizing', 'binding': 'current-final-review', 'raw': result.model_dump_json(),
            'parts': {'final_reviews': {'clauses:retained': {'overall': {'verdict': 'supported'}}}}}
        cp['fingerprint'] = fingerprint(cp)
        work[KEY] = deepcopy(cp)
        saved['checkpoint'] = deepcopy(cp)
        work.setdefault('model_route', {})['evidence_transport'] = {'input_fingerprint': 'current-originals'}
        # This is the host review handoff, never a model-supplied field. The
        # real gateway's emission boundary is exercised separately below.
        mission.remember_delivery(work, result)
        return result

    monkeypatch.setattr(research_gateway, 'execute', completed)
    root, run, _ = start(client)
    value = finish(client, service, root, run)
    if control == 'rejected_citation':
        assert value['status'] == 'failed' and value['retry']['available']
        assert value['exploration']['mission']['answer'] is None
        assert value['exploration']['briefing'] is None
        with service.db.session() as session:
            state = session.get(InvestigationBranch, attempts[0]).checkpoint
            assert state[KEY] == saved['checkpoint']
            assert state['steps'][-1]['error_code'] == 'invalid_evidence'
        retry = post(client, root + '/investigations/' + run['id'] + '/control',
            {'action': 'retry', 'expected_revision': value['revision']})
        assert retry.status_code == 200, retry.text
        value = finish(client, service, root, retry.json())
        assert len(attempts) == 2 and len(generated) == 1
    assert value['status'] == 'completed' and value['exploration']['mission']['answer']['points']
    assert value['exploration']['mission']['answer']['status'] == 'partial'
    if control == 'cited_clarify':
        assert value['exploration']['mission']['stop'] == 'needs_direction'
        assert value['exploration']['mission']['stage'] == 'waiting_for_direction'
        assert len(value['exploration']['briefing']['directions']) == 2
        assert value['exploration']['mission']['checkpoints'][-1]['deepen_branches'] == []
    else:
        assert value['exploration']['mission']['stop'] == 'no_useful_next_check'
        assert value['exploration']['briefing']['clarification'] == ''
        assert value['exploration']['briefing']['directions'] == []
        assert 'PRIVATE DRAFT CONTROL REASON' not in json.dumps(value)
    with service.db.session() as session:
        assert KEY not in session.get(InvestigationBranch, attempts[0]).checkpoint


@pytest.mark.asyncio
@pytest.mark.parametrize('pending', [False, True])
async def test_gateway_emits_delivery_receipt_only_after_completed_final_review(monkeypatch, pending):
    from helvetic_lens import research_answer_review, research_final_coverage, research_final_review

    settings = Settings(_env_file=None, apertus_provider='swisscom')
    model = ModelClient(settings)
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'Who operates the registry?', 'research_mission': {},
        'sources': [{'id': 'a' * 36, 'kind': 'public_source', 'excerpts': [
            {'passage': 'p1', 'text': 'North Reach operates the registry.'}]}]}}

    async def complete(*args, **kwargs):
        return json.dumps({'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'points': [
            {'statement': 'North Reach operates the registry.', 'evidence': [{'citation_ref': 1, 'role': 'support'}]}]},
            'next_action': 'clarify'})

    async def final(*args, **kwargs):
        return {'status': 'partial' if pending else 'checked', 'hints': [], 'question_coverage': 'covered',
            'factual_review': {'status': 'partial' if pending else 'checked',
                'pending_checks': [{'item': 'P0', 'reason': 'step_deadline'}] if pending else []}}

    async def original(*args, **kwargs):
        return None

    async def reconcile(*args, **kwargs):
        return {'status': 'checked', 'removed_notices': 0}

    monkeypatch.setattr(model, 'complete', complete)
    monkeypatch.setattr(research_final_review, 'finalize', final)
    monkeypatch.setattr(research_answer_review, 'original_check', original)
    monkeypatch.setattr(research_final_coverage, 'reconcile', reconcile)
    schema = mission.schema(Briefing)
    service = SimpleNamespace(settings=settings, model_client=model)
    if pending:
        with pytest.raises(DomainError, match='Some final evidence checks are incomplete'):
            await research_gateway.complete(service, work, '', schema, 90)
        assert 'completed_answer_delivery' not in work
        return
    result = schema.model_validate_json(await research_gateway.complete(service, work, '', schema, 90))
    assert mission.delivery_current(work, result)
    assert result.mission_checkpoint.action == 'clarify', 'Controls are private until ordinary application'
    assert json.loads(work[KEY]['raw'])['next_action'] == 'clarify'
    assert 'completed_answer_delivery' not in result.model_dump()
    assert not mission.delivery_current({**work, 'completed_answer_delivery': True}, result)
    changed = result.model_copy(deep=True)
    changed.mission_checkpoint.answer.points[0].statement = 'A different unchecked statement.'
    assert not mission.delivery_current(work, changed)
    changed_work = deepcopy(work)
    changed_work['input']['original_question'] = 'Another request?'
    assert not mission.delivery_current(changed_work, result)


def test_complete_continuation_preserves_its_cited_next_work():
    from helvetic_lens.product_iterative_research import Gap

    ref = {'source_id': 's' * 36, 'locator': 'p1', 'quote': 'The retained original identifies the missing comparison.'}
    result = mission.schema(Briefing).model_validate({'understanding': 'A source-backed continuation remains useful.',
        'findings': [], 'uncertainties': ['The requested comparison remains unresolved.'],
        'clarification': '', 'directions': [], 'mission_checkpoint': {
            'answer': {'status': 'not_found', 'points': [], 'limitations': ['The requested comparison remains unresolved.']},
            'action': 'continue', 'reason': 'Read the named comparison.', 'deepen_branches': [],
            'next_checks': [Gap(**ref, question='What does the named comparison establish?', query='Named comparison',
                purpose='Resolve the original comparison.', priority=1, kind='missing_evidence').model_dump()]}})
    assert mission.checked_delivery(result).model_dump() == result.model_dump()
