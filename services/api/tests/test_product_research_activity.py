"""Recorded worker activity and its expiry; synthetic sources, no live research."""
import json
from copy import deepcopy
from datetime import timedelta

import pytest
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude
from test_product_exploration import adapters, start
from test_product_investigations import tick
from test_product_iterative_research import complete

from helvetic_lens import product_exploration, product_iterative_steps
from helvetic_lens.db import utcnow
from helvetic_lens.models import Job
from helvetic_lens.product_api import iso
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationSource


def current(client, root, run):
    response = client.get(root + '/investigations/' + run['id'])
    assert response.status_code == 200, response.json()
    return response.json()['exploration']['current_activity']


def projected(service, run):
    with service.db.session() as session:
        return product_exploration.projection(session, session.get(Investigation, run['id']))['current_activity']


@pytest.mark.parametrize('product', ['legal', 'pharma'])
def test_actual_worker_stages_expose_public_question_and_only_captured_sources(signed, monkeypatch, product):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    root, run, _ = start(client, product)
    assert current(client, root, run)['status'] == 'waiting'
    execute = product_iterative_steps.execute
    observed = []

    async def inspect(service, work, seconds):
        # Exercise every actual worker step without an artificial HTTP burst.
        activity = projected(service, run)
        if not observed or (work['phase'] == 'read' and not any(v['phase'] == 'read' for v in observed)):
            public = current(client, root, run)
            assert public['status'] == activity['status']
            assert public['phase'] == activity['phase']
            assert public['question'] == activity['question']
            assert public['latest_source'] == activity['latest_source']
        assert activity['status'] == 'working', activity
        assert activity['phase'] == work['phase']
        assert 0 < activity['valid_for_ms'] <= seconds * 1000
        with service.db.session() as session:
            saved = session.get(Investigation, run['id'])
            before = deepcopy(saved.research_state)
            branch = session.get(InvestigationBranch, work['branch_id'])
            receipt = deepcopy(branch.checkpoint['current_activity'])
            question = next((q for q in saved.research_state['questions'] if q['id'] == branch.checkpoint.get('question_id')), None)
            assert activity['question'] == (question['question'] if question else saved.question)
            assert 'job_id' not in activity and 'leased_at' not in activity
        again = projected(service, run)
        assert again['phase'] == activity['phase'] and again['valid_for_ms'] <= activity['valid_for_ms']
        with service.db.session() as session:
            assert session.get(Investigation, run['id']).research_state == before
            assert session.get(InvestigationBranch, work['branch_id']).checkpoint['current_activity'] == receipt
        source = activity['latest_source']
        if source:
            assert source['url'] in trace['reads']
            if work['phase'] == 'read':
                assert source['url'] != work['item']['url']
        observed.append(activity)
        return await execute(service, work, seconds)

    monkeypatch.setattr(product_iterative_steps, 'execute', inspect)
    value = complete(client, service, root + '/investigations', run)
    assert value['exploration']['briefing'], value['stop_reason']
    assert {v['phase'] for v in observed} >= {'plan', 'search', 'gate', 'read', 'extract', 'reflect', 'orient', 'brief'}
    assert any(v['latest_source'] for v in observed)
    assert current(client, root, run) == {'contract': 'research-activity/v1', 'status': 'finished'}
    assert client.get(root + '/web-research').json()['policy']['enabled'] is False


@pytest.mark.parametrize('case, expected', [
    ('expired', 'stale'), ('replaced_lease', 'stale'), ('cancel_requested', 'stale'),
    ('queued_job', 'stale'), ('missing_receipt', 'unknown'), ('malformed_expiry', 'unknown'),
    ('private_branch', 'unknown'), ('unrelated_branch', 'unknown'),
])
def test_unconfirmed_activity_cannot_expose_a_current_question(signed, monkeypatch, case, expected):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    root, run, _ = start(client)
    execute = product_iterative_steps.execute
    captured = []

    async def inspect(service, work, seconds):
        if work['phase'] != 'search' or captured:
            return await execute(service, work, seconds)
        with service.db.session() as session:
            branch = session.get(InvestigationBranch, work['branch_id'])
            state = deepcopy(branch.checkpoint)
            changed = deepcopy(state)
            job = session.get(Job, session.get(Investigation, run['id']).job_id)
            lease, status, cancel = job.leased_at, job.state, job.cancel_requested
            if case == 'expired':
                changed['current_activity']['expires_at'] = iso(utcnow() - timedelta(seconds=1))
            elif case == 'replaced_lease':
                job.leased_at = job.leased_at + timedelta(seconds=1)
            elif case == 'cancel_requested':
                job.cancel_requested = True
            elif case == 'queued_job':
                job.state = 'queued'
            elif case == 'missing_receipt':
                changed.pop('current_activity')
            elif case == 'malformed_expiry':
                changed['current_activity']['expires_at'] = 'not-a-date'
            elif case == 'private_branch':
                changed['contribution_entry_id'] = 'PRIVATE FILE CANARY'
            elif case == 'unrelated_branch':
                changed['question_id'] = 'PRIVATE QUESTION CANARY'
            branch.checkpoint = changed
            session.commit()
        activity = current(client, root, run)
        assert activity == {'contract': 'research-activity/v1', 'status': expected}
        assert 'PRIVATE' not in json.dumps(activity)
        captured.append(activity)
        with service.db.session() as session:
            session.get(InvestigationBranch, work['branch_id']).checkpoint = state
            job = session.get(Job, session.get(Investigation, run['id']).job_id)
            job.leased_at, job.state, job.cancel_requested = lease, status, cancel
            session.commit()
        return await execute(service, work, seconds)

    monkeypatch.setattr(product_iterative_steps, 'execute', inspect)
    for _ in range(4):
        tick(service, run['id'])
        if captured:
            break
    assert captured
    value = client.get(root + '/investigations/' + run['id']).json()
    stopped = post(client, root + '/investigations/' + run['id'] + '/control', {'action': 'cancel', 'expected_revision': value['revision']})
    assert stopped.status_code == 200
    assert current(client, root, run)['status'] == 'finished'


@pytest.mark.parametrize('change', ['exclude', 'hash', 'rights'])
def test_current_source_change_hides_running_activity_and_source_context(signed, monkeypatch, change):
    client, service, identity, model = signed
    adapters(monkeypatch, service, model)
    root, run, _ = start(client)
    execute = product_iterative_steps.execute
    captured = []

    async def inspect(service, work, seconds):
        if work['phase'] == 'extract' and not captured:
            activity = current(client, root, run)
            assert activity['status'] == 'working' and activity['latest_source']
            if change == 'exclude':
                exclude(service, identity, activity['latest_source']['id'])
            else:
                with service.db.session() as session:
                    source = session.get(InvestigationSource, activity['latest_source']['id'])
                    if change == 'hash':
                        source.sha256 = 'b' * 64
                    else:
                        source.snapshot = {**source.snapshot, 'allow_discovery': False}
                    session.commit()
            captured.append(current(client, root, run))
            assert captured[-1] == {'contract': 'research-activity/v1', 'status': 'evidence_changed'}
        return await execute(service, work, seconds)

    monkeypatch.setattr(product_iterative_steps, 'execute', inspect)
    for _ in range(15):
        tick(service, run['id'])
        if captured:
            break
    assert captured == [{'contract': 'research-activity/v1', 'status': 'evidence_changed'}]


def test_pause_resume_and_legacy_metadata_never_invent_a_running_stage(signed, monkeypatch):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    root, run, _ = start(client)
    tick(service, run['id'])
    url = root + '/investigations/' + run['id']
    page = client.get(url).json()
    paused = post(client, url + '/control', {'action': 'pause', 'expected_revision': page['revision']}).json()
    assert current(client, root, run)['status'] == 'paused'
    resumed = post(client, url + '/control', {'action': 'resume', 'expected_revision': paused['revision']})
    assert resumed.status_code == 200
    assert current(client, root, run)['status'] == 'waiting'
    with service.db.session() as session:
        saved = session.get(Investigation, run['id'])
        data = deepcopy(saved.research_state)
        data['exploration'].pop('activity_contract')
        saved.research_state = data
        session.commit()
    assert current(client, root, run) == {'contract': 'research-activity/v1', 'status': 'unknown'}
    tick(service, run['id'])
    assert current(client, root, run)['status'] == 'unknown'


def test_recovered_interrupted_receipt_is_not_a_current_operation(signed, monkeypatch):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    root, run, _ = start(client)
    for _ in range(3):
        tick(service, run['id'])
    with service.db.session() as session:
        from helvetic_lens.product_investigations import rows
        saved = session.get(Investigation, run['id'])
        branch = next(b for b in rows(session, InvestigationBranch, saved)
            if b.checkpoint.get('question_id') and b.checkpoint.get('steps'))
        state = deepcopy(branch.checkpoint)
        state['steps'][-1]['status'] = 'running'
        state['inflight'] = state['steps'][-1]['id']
        branch.phase = state['steps'][-1]['phase']
        branch.checkpoint = state
        branch_id = branch.id
        session.commit()
    assert current(client, root, run)['status'] == 'stale'
    tick(service, run['id'])
    assert current(client, root, run)['status'] == 'waiting'
    with service.db.session() as session:
        assert session.get(InvestigationBranch, branch_id).checkpoint['steps'][-1]['status'] == 'interrupted'


def test_changed_parent_evidence_hides_a_running_continued_question(signed, monkeypatch):
    from test_product_saved_check import command, prepared, url

    client, service, identity, model = signed
    root, old, _ = prepared(client, service, model, monkeypatch)
    child = post(client, url(root, old), command(old)).json()
    execute = product_iterative_steps.execute
    observed = []

    async def inspect(service, work, seconds):
        if not observed:
            first = current(client, root, child)
            exclude(service, identity, old['exploration']['next_check']['source']['id'])
            observed.append((first, current(client, root, child)))
        return await execute(service, work, seconds)

    monkeypatch.setattr(product_iterative_steps, 'execute', inspect)
    for _ in range(4):
        tick(service, child['id'])
        if observed:
            break
    assert observed and observed[0][0]['status'] == 'working'
    assert observed[0][1] == {'contract': 'research-activity/v1', 'status': 'evidence_changed'}
