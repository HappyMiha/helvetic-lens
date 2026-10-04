"""Native checked-subset delivery retains an honest, private retry obligation."""
import json
from copy import deepcopy
from datetime import timedelta

import pytest
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude
from test_product_exploration import adapters, start
from test_product_investigations import tick

from helvetic_lens import research_gateway
from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.models import Job
from helvetic_lens.product_exploration import Briefing
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch
from helvetic_lens.product_iterative_research import Gap
from helvetic_lens.product_operations import fingerprint
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_final_review import DEFERRED_NOTICE
from helvetic_lens.research_synthesis_resume import (
    EXHAUSTED_REVIEW,
    KEY,
    deferred_verification,
    exhausted_review,
)


def finish(client, service, root, run):
    for _ in range(160):
        value = client.get(root + '/investigations/' + run['id']).json()
        if value['status'] not in {'queued', 'running'}:
            return value
        with service.db.session() as session:
            job = session.get(Job, session.get(Investigation, run['id']).job_id)
            job.available_at = utcnow() - timedelta(seconds=1)
            session.commit()
        tick(service, run['id'])
    pytest.fail('The ordinary native workflow did not stop')


@pytest.mark.parametrize('withdraw,refresh_policy,reject_delivery,handoff_outage', [
    (False, False, False, False), (True, False, False, False), (False, True, False, False),
    (False, False, True, False), (False, False, False, True)])
def test_exhausted_review_delivers_checked_subset_and_same_id_retry_keeps_private_obligation(
        signed, monkeypatch, withdraw, refresh_policy, reject_delivery, handoff_outage):
    client, service, identity, model = signed
    adapters(monkeypatch, service, model)
    model_complete = model.complete

    async def mission_response(system, user, **kwargs):
        raw = await model_complete(system, user, **kwargs)
        if kwargs.get('response_schema', {}).get('title') != 'Briefing':
            return raw
        value = json.loads(raw)
        first = value['findings'][0]
        value.update(clarification='', directions=[], mission_checkpoint={
            'answer': {'status': 'possible_answer', 'points': [{'statement': first['statement'],
                'evidence': [{key: first[key] for key in ('source_id', 'quote', 'locator')} | {'role': 'support'}]}],
                'limitations': []}, 'action': 'finish', 'reason': 'The current fictional originals establish this finding.',
            'next_checks': [], 'deepen_branches': []})
        return json.dumps(value)

    monkeypatch.setattr(model, 'complete', mission_response)
    original, calls = research_gateway.execute, []
    private = 'PRIVATE UNREVIEWED ASSERTION MUST NOT BE DISPLAYED'
    checkpoint = {'stage': 'finalizing', 'binding': 'exact-draft-binding', 'raw': private,
        'parts': {'final_reviews': {'clauses:one': {'overall': {'verdict': 'supported'}}}}}
    exhaustion_attempts = 5 if refresh_policy else 4

    async def execute(service, work, seconds):
        if work['phase'] != 'brief':
            return await original(service, work, seconds)
        calls.append(work['branch_id'])
        if len(calls) <= exhaustion_attempts:
            assert not work.get(EXHAUSTED_REVIEW), 'First outage and automatic backoffs cannot authorize partial delivery'
            work[KEY] = deepcopy(checkpoint)
            if refresh_policy and len(calls) >= 2:
                work[KEY]['binding'] = 'new-policy-binding'
            if refresh_policy and len(calls) == 2:
                # The gateway separately proves this signal requires a rejected
                # current checkpoint. Old outage counts cannot authorize it.
                work['synthesis_checkpoint_invalidated'] = True
            work['model_route'] = {'evidence_transport': {'input_fingerprint': 'same-current-originals'}}
            raise DomainError('Synthetic upstream timeout', 504, 'model_upstream_timeout')
        assert work[EXHAUSTED_REVIEW]['input_fingerprint'] == 'same-current-originals'
        assert work[KEY]['raw'] == private
        assert work['automatic_review_handoff'] is (len(calls) == exhaustion_attempts + 1)
        if handoff_outage:
            work[KEY]['parts']['final_reviews']['clauses:new-checked-progress'] = {'overall': {'verdict': 'supported'}}
            work['model_route'] = {'evidence_transport': {'input_fingerprint': 'same-current-originals'}}
            raise DomainError('Subset coverage is still unavailable after new checked progress', 504, 'model_upstream_timeout')
        if reject_delivery and len(calls) == exhaustion_attempts + 2:
            assert work['retry_deferred_review'] is False
            assert work[KEY]['parts']['deferred_final_review']['status'] == 'pending'
        saved = deepcopy(work[KEY])
        # This test owns the worker/publication boundary. Its checkpoint and
        # reviewer are scripted; real hosted binding and no-redraft behavior are
        # exercised separately in test_research_checked_delivery_gateway.py.
        delivered_schema = mission_schema(Briefing)
        result = delivered_schema.model_validate_json(await mission_response('', json.dumps(work['input']),
            response_schema=delivered_schema.model_json_schema()))
        if len(calls) == exhaustion_attempts + 1:
            result.mission_checkpoint.answer.status = 'partial'
            result.mission_checkpoint.answer.limitations.append(DEFERRED_NOTICE)
            saved['parts']['deferred_final_review'] = {'status': 'qualified_delivery',
                'answer': {'points': [{'statement': private}]},
                'pending_checks': [{'item': 'P1', 'reason': 'model_upstream_timeout'}]}
            work[KEY] = saved
            work['deferred_review_verification'] = deferred_verification(saved)
            # These are private proposals, not prerequisites for publishing a
            # checked subset. Neither malformed clarification nor an unbound
            # optional future query may launch more work or discard the answer.
            result.mission_checkpoint.action = 'clarify'
            result.mission_checkpoint.reason = private
            result.mission_checkpoint.next_checks = [Gap(source_id='0' * 36,
                quote=private, locator='not-a-current-original', question='Optional future precision?',
                query='Optional future precision', purpose=private, priority=5, kind='missing_evidence')]
            result.mission_checkpoint.deepen_branches = ['not-a-current-frontier']
            if reject_delivery:
                result.mission_checkpoint.answer.points[0].evidence[0].quote = 'An unsupplied factual quotation.'
            if withdraw:
                exclude(service, identity, work['input']['sources'][0]['id'])
        return result

    monkeypatch.setattr(research_gateway, 'execute', execute)
    root, run, _ = start(client)
    delivered = finish(client, service, root, run)
    assert len(calls) == exhaustion_attempts + 1, 'Exhaustion hands off once without repurchasing the pending review'
    url = root + '/investigations/' + run['id']
    assert private not in json.dumps(delivered) and private not in client.get(root + '/export').text
    if handoff_outage:
        assert delivered['status'] == 'failed' and delivered['retry']['available']
        assert delivered['exploration']['mission']['answer'] is None
        with service.db.session() as session:
            state = session.get(InvestigationBranch, calls[0]).checkpoint
            assert state['provider_retries'] == {'same-current-originals': 3}
            assert 'clauses:new-checked-progress' in state[KEY]['parts']['final_reviews']
            assert state['steps'][-1]['error_code'] == 'model_upstream_timeout'
            assert 'retry_at' not in state['steps'][-1]
        tick(service, run['id'])
        assert len(calls) == exhaustion_attempts + 1, 'New progress must not renew the exhausted automatic allowance'
        return
    if withdraw:
        assert delivered['status'] == 'paused'
        with service.db.session() as session:
            state = session.get(InvestigationBranch, calls[0]).checkpoint
            assert KEY not in state and EXHAUSTED_REVIEW not in state
        return
    if reject_delivery:
        assert delivered['status'] == 'failed' and delivered['retry']['available']
        assert delivered['exploration']['mission']['answer'] is None
        with service.db.session() as session:
            state = session.get(InvestigationBranch, calls[0]).checkpoint
            assert state[KEY]['raw'] == private
            assert state[KEY]['parts']['deferred_final_review']['status'] == 'pending'
            assert state[KEY]['fingerprint'] == fingerprint({k: v for k, v in state[KEY].items() if k != 'fingerprint'})
            assert state['steps'][-1]['error_code'] == 'invalid_evidence'
        retry = post(client, url + '/control', {'action': 'retry', 'expected_revision': delivered['revision']})
        assert retry.status_code == 200, retry.text
        recovered = finish(client, service, root, retry.json())
        assert recovered['status'] == 'completed' and recovered['exploration']['mission']['answer']['points']
        return
    assert delivered['status'] == 'completed' and delivered['retry']['available'] is True
    mission = delivered['exploration']['mission']
    assert mission['stop'] == 'review_unavailable' and mission['stage'] == 'incomplete'
    assert mission['answer']['points'] and mission['answer']['status'] == 'partial'
    assert mission['checkpoints'][-1]['gaps'] == [] and mission['checkpoints'][-1]['deepen_branches'] == []
    assert delivered['exploration']['briefing']['clarification'] == ''
    assert delivered['exploration']['briefing']['directions'] == []
    assert mission['verification'] == {'status': 'partial', 'pending_checks': 1,
        'reasons': ['model_upstream_timeout'], 'basis': DEFERRED_NOTICE}
    with service.db.session() as session:
        branch = session.get(InvestigationBranch, calls[0])
        assert branch.status == 'failed' and branch.checkpoint[KEY]['raw'] == private
    tick(service, run['id'])
    assert len(calls) == exhaustion_attempts + 1, 'Qualified delivery must not silently launch another investigation'
    retry = post(client, url + '/control', {'action': 'retry', 'expected_revision': delivered['revision']})
    assert retry.status_code == 200, retry.text
    finished = finish(client, service, root, retry.json())
    assert finished['id'] == run['id'] and finished['status'] == 'completed' and len(calls) == exhaustion_attempts + 2
    assert not finished['retry']['available']
    assert finished['exploration']['mission']['verification'] is None
    with service.db.session() as session:
        state = session.get(InvestigationBranch, calls[0]).checkpoint
        assert KEY not in state and EXHAUSTED_REVIEW not in state


@pytest.mark.parametrize('change', ['first_failure', 'other_input', 'preparing', 'not_failed'])
def test_qualification_intent_requires_exhausted_exact_final_review(change):
    state = {KEY: {'stage': 'finalizing', 'binding': 'draft'}, 'provider_retries': {'same-input': 3},
        'steps': [{'phase': 'brief', 'status': 'unavailable', 'error_code': 'model_upstream_timeout',
            'execution': {'evidence_transport': {'input_fingerprint': 'same-input'}}}]}
    assert exhausted_review(state)['input_fingerprint'] == 'same-input'
    if change == 'first_failure':
        state['provider_retries']['same-input'] = 1
    elif change == 'other_input':
        state['steps'][0]['execution']['evidence_transport']['input_fingerprint'] = 'changed-input'
    elif change == 'preparing':
        state[KEY]['stage'] = 'preparing'
    else:
        state['steps'][0]['status'] = 'completed'
    assert exhausted_review(state) is None


@pytest.mark.parametrize('selected_question', [False, True])
def test_checked_delivery_copies_future_controls_without_changing_checked_assessments(selected_question):
    from helvetic_lens import product_research_mission as mission
    from helvetic_lens.product_direction_assessment import RenewedSuggestedDirectionBriefing
    from helvetic_lens.product_question_renewal import RenewalAssessedBriefing

    ref = {'source_id': 's' * 36, 'locator': 'paragraph-1', 'quote': 'An exact retained source passage.'}
    answer = {'status': 'partial', 'points': [{'statement': 'The retained finding has a stated limit.',
        'evidence': [{**ref, 'role': 'support'}]}], 'limitations': ['A genuine evidence gap remains.']}
    value = {'understanding': 'The original question has this checked partial answer.',
        'findings': [{**ref, 'statement': answer['points'][0]['statement'], 'basis': 'direct'}],
        'uncertainties': answer['limitations'], 'clarification': 'Which later direction should be explored?',
        'directions': [{**ref, 'question': 'An optional later question?', 'why': 'Optional work is not the checked answer.'}],
        'question_renewals': [{**answer, 'question_id': 'old-question'}],
        'mission_checkpoint': {'answer': answer, 'action': 'clarify', 'reason': 'An optional draft-control reason.',
            'next_checks': [], 'deepen_branches': ['draft-frontier']}}
    if selected_question:
        value['assessment'] = {**answer, 'question_id': 'selected-question'}
        base = RenewalAssessedBriefing
    else:
        value.update(direction_assessment={**answer, 'selection': None},
            next_check_choice={'question_id': 'old-question', 'query': 'Optional future query', 'limitation_index': 0})
        base = RenewedSuggestedDirectionBriefing
    original = mission.schema(base).model_validate(value)
    original._renewal_unavailable = True
    before = original.model_dump()
    delivered = mission.checked_delivery(original, {'basis': DEFERRED_NOTICE})
    assert original.model_dump() == before and original._renewal_unavailable
    for field in ('findings', 'uncertainties', 'understanding', 'assessment' if selected_question else 'direction_assessment'):
        assert delivered.model_dump()[field] == before[field]
    assert delivered.mission_checkpoint.answer.model_dump() == answer
    assert delivered.clarification == '' and delivered.directions == [] and delivered.question_renewals == []
    assert not delivered._renewal_unavailable
    assert getattr(delivered, 'next_check_choice', None) is None
    assert delivered.mission_checkpoint.action == 'finish' and delivered.mission_checkpoint.reason == DEFERRED_NOTICE
    assert delivered.mission_checkpoint.next_checks == [] and delivered.mission_checkpoint.deepen_branches == []
