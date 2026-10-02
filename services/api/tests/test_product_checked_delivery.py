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
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch
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


@pytest.mark.parametrize('withdraw,refresh_policy', [(False, False), (True, False), (False, True)])
def test_exhausted_review_delivers_checked_subset_and_same_id_retry_keeps_private_obligation(signed, monkeypatch, withdraw, refresh_policy):
    client, service, identity, model = signed
    adapters(monkeypatch, service, model)
    model_complete = model.complete

    async def mission(system, user, **kwargs):
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

    monkeypatch.setattr(model, 'complete', mission)
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
        saved = deepcopy(work[KEY])
        result = await original(service, work, seconds)
        if len(calls) == exhaustion_attempts + 1:
            result.mission_checkpoint.answer.status = 'partial'
            result.mission_checkpoint.answer.limitations.append(DEFERRED_NOTICE)
            saved['parts']['deferred_final_review'] = {'status': 'qualified_delivery',
                'answer': {'points': [{'statement': private}]},
                'pending_checks': [{'item': 'P1', 'reason': 'model_upstream_timeout'}]}
            work[KEY] = saved
            work['deferred_review_verification'] = deferred_verification(saved)
            if withdraw:
                exclude(service, identity, work['input']['sources'][0]['id'])
        return result

    monkeypatch.setattr(research_gateway, 'execute', execute)
    root, run, _ = start(client)
    initial = finish(client, service, root, run)
    assert initial['status'] == 'failed' and initial['retry']['available'] and len(calls) == exhaustion_attempts
    assert initial['exploration']['mission']['answer'] is None
    url = root + '/investigations/' + run['id']
    retry = post(client, url + '/control', {'action': 'retry', 'expected_revision': initial['revision']})
    assert retry.status_code == 200, retry.text
    delivered = finish(client, service, root, retry.json())
    assert private not in json.dumps(delivered) and private not in client.get(root + '/export').text
    if withdraw:
        assert delivered['status'] == 'paused'
        with service.db.session() as session:
            state = session.get(InvestigationBranch, calls[0]).checkpoint
            assert KEY not in state and EXHAUSTED_REVIEW not in state
        return
    assert delivered['status'] == 'completed' and delivered['retry']['available'] is True
    mission = delivered['exploration']['mission']
    assert mission['stop'] == 'review_unavailable' and mission['stage'] == 'incomplete'
    assert mission['answer']['points'] and mission['answer']['status'] == 'partial'
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
