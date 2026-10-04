"""Real worker leases retain local indexing without replaying source analysis."""
import json
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_product_dossiers import signed as signed
from test_product_exploration import adapters, start
from test_product_investigations import tick

from helvetic_lens import evidence_embeddings as embeddings
from helvetic_lens import jobs, research_gateway
from helvetic_lens import product_investigation_worker as worker
from helvetic_lens import product_iterative_steps as steps
from helvetic_lens import research_active_retrieval as retrieval
from helvetic_lens.db import utcnow
from helvetic_lens.models import Job
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from helvetic_lens.product_retrieval_models import EvidenceVector
from helvetic_lens.research_synthesis_resume import KEY


def clock(monkeypatch):
    now, origin = [0.0], utcnow()
    monkeypatch.setattr(worker, 'perf_counter', lambda: now[0])
    monkeypatch.setattr(retrieval, 'monotonic', lambda: now[0])
    monkeypatch.setattr(worker, 'utcnow', lambda: origin + timedelta(seconds=now[0]))
    monkeypatch.setattr(jobs, 'utcnow', lambda: origin + timedelta(seconds=now[0]))
    return now


def delayed_prepare(monkeypatch, now, target, *, prepare_seconds, commit_seconds):
    original_prepare, original_commit = steps.prepare, Session.commit

    def prepare(session, run, branch, state, work):
        result = original_prepare(session, run, branch, state, work)
        if target(work):
            now[0] += prepare_seconds
            session.info['preparation_commit_delay'] = commit_seconds
        return result

    def commit(session):
        delay = session.info.pop('preparation_commit_delay', 0)
        result = original_commit(session)
        now[0] += delay
        return result

    monkeypatch.setattr(steps, 'prepare', prepare)
    monkeypatch.setattr(Session, 'commit', commit)


def test_reflection_indexes_across_leases_then_calls_model_once_with_unchanged_reading(signed, monkeypatch):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    _, run, _ = start(client)
    service.settings.apertus_timeout_seconds = service.settings.job_lease_seconds = 300
    now = clock(monkeypatch)
    target, target_query = [], []

    def is_target(work):
        if work['phase'] != 'reflect':
            return False
        if not target:
            target.append(work['branch_id'])
            target_query.append(work['query'])
        return work['branch_id'] == target[0]

    delayed_prepare(monkeypatch, now, is_target, prepare_seconds=30, commit_seconds=10)
    original_execute, original_model = research_gateway.execute, model.complete
    encoded, dispatched, model_calls, snapshots = [], [], [], []

    async def encode(self, texts):
        encoded.extend(texts)
        now[0] += 50 if texts[0].startswith('passage:') else 1
        return [{'vector': (1.0,) + (0.0,) * 383, 'input_tokens': 40, 'truncated': False} for _ in texts]

    async def complete(system, user, **options):
        if options['response_schema']['title'] == 'Reflection' and json.loads(user)['branch'] == target_query[0]:
            model_calls.append(user)
        return await original_model(system, user, **options)

    async def execute(service, work, seconds):
        if not is_target(work):
            return await original_execute(service, work, seconds)
        assert seconds == 255, 'Both preparation and commit must consume the original lease'
        dispatched.append(seconds)
        with service.db.session() as session:
            source = session.get(InvestigationSource, work['input']['sources'][0]['id'])
            snapshots.append(deepcopy(source.snapshot))
            passage = source.snapshot['excerpts'][0]
            assert len(passage['text']) >= 96
            refs = {i + 1: {'source_id': source.id, 'locator': passage['passage'],
                'quote': passage['text'][:len(passage['text']) - i]} for i in range(96)}
            wire = SimpleNamespace(work=work, references=refs, input={
                'original_question': 'Compare the retained originals.',
                'sources': [{'id': source.id, 'sha256': source.sha256, 'title': source.title}]})
        parts = deepcopy(work.get(KEY, {}).get('parts', {}))

        def save():
            work[KEY] = {'stage': 'preparing', 'raw': '', 'parts': deepcopy(parts)}

        ranked = await retrieval.rank_evidence(service, wire, 'Compare the retained originals.', seconds,
            checkpoints=parts, on_progress=save)
        assert ranked['coverage']['prepared_records'] == len(refs) == 96
        assert set(ranked['rankings'][0]['references']) == set(refs)
        assert ranked['coverage']['semantic_status'] == 'complete'
        return await original_execute(service, work, seconds - 51)

    monkeypatch.setattr(embeddings.LocalEmbeddings, 'encode', encode)
    monkeypatch.setattr(research_gateway, 'execute', execute)
    monkeypatch.setattr(model, 'complete', complete)
    for _ in range(45):
        outcome = tick(service, run['id'])
        if dispatched:
            break
    else:
        pytest.fail('Reflection was never prepared')
    assert outcome['state'] == 'continuing_evidence_preparation'
    assert not model_calls
    readings = len(trace['reads'])
    analyses = sum(call['phase'] == 'ResearchExtraction' for call in trace['models'])
    with service.db.session() as session:
        branch = session.get(InvestigationBranch, target[0])
        assert branch.phase == 'reflect' and branch.status == 'running'
        assert not branch.checkpoint.get('inflight')
        assert len(branch.checkpoint[KEY]['parts']['evidence_selection']) == 5
        assert branch.checkpoint['steps'][-1]['checkpointed'] is True
        assert not branch.checkpoint.get('provider_retries')
        assert session.scalar(select(func.count()).select_from(EvidenceVector)) == 80
    for _ in range(12):
        tick(service, run['id'])
        if len(dispatched) == 2:
            break
    assert dispatched == [255, 255] and len(model_calls) == 1
    assert len([text for text in encoded if text.startswith('passage:')]) == 96
    assert len(set(text for text in encoded if text.startswith('passage:'))) == 96
    assert snapshots[0] == snapshots[1]
    assert len(trace['reads']) == readings
    assert sum(call['phase'] == 'ResearchExtraction' for call in trace['models']) == analyses
    with service.db.session() as session:
        branch = session.get(InvestigationBranch, target[0])
        assert branch.status != 'failed' and KEY not in branch.checkpoint
        assert all(step['status'] != 'interrupted' for step in branch.checkpoint['steps'])


@pytest.mark.parametrize('expiry', ['prepare', 'commit'])
def test_expired_before_dispatch_has_no_model_attempt_and_does_not_renew_job_attempts(signed, monkeypatch, expiry):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    _, run, _ = start(client)
    service.settings.apertus_timeout_seconds = service.settings.job_lease_seconds = 300
    now = clock(monkeypatch)
    delayed_prepare(monkeypatch, now, lambda work: work['phase'] == 'plan',
        prepare_seconds=301 if expiry == 'prepare' else 0,
        commit_seconds=301 if expiry == 'commit' else 0)
    original, calls = research_gateway.execute, []

    async def execute(service, work, seconds):
        calls.append(work['phase'])
        return await original(service, work, seconds)

    monkeypatch.setattr(research_gateway, 'execute', execute)
    for _ in range(5):
        result = tick(service, run['id'])
        if result['state'] == 'retrying':
            break
    assert 'plan' not in calls

    with service.db.session() as session:
        saved = session.get(Investigation, run['id'])
        branch = session.scalar(select(InvestigationBranch).where(InvestigationBranch.investigation_id == saved.id,
            InvestigationBranch.phase == 'plan'))
        job = session.get(Job, saved.job_id)
        assert job.attempts == 1 and job.error_code == 'research_preparation_deadline'
        assert saved.research_state['used']['model_calls'] == 0
        assert branch.status == 'running' and not branch.checkpoint.get('inflight')
        receipt = branch.checkpoint['steps'][-1]
        assert receipt['status'] == 'pending' and receipt['execution']['outcome'] == 'not_started'
        assert receipt['execution']['model_requests'] == 0
        job.max_attempts = 2
        session.commit()
    tick(service, run['id'])
    with service.db.session() as session:
        saved = session.get(Investigation, run['id'])
        job = session.get(Job, saved.job_id)
        assert job.state == 'failed' and job.attempts == 2
        assert saved.status == 'paused', 'Native attempt exhaustion keeps saved work available for explicit recovery'
    assert 'plan' not in calls


def test_not_started_read_preserves_prior_attempts_and_retries_the_unfetched_original(signed, monkeypatch):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    _, run, _ = start(client)
    service.settings.apertus_timeout_seconds = service.settings.job_lease_seconds = 300
    now = clock(monkeypatch)
    delayed, target = [True], []
    prior = 'https://example.org/already-attempted-original'
    original_prepare, original_execute = steps.prepare, research_gateway.execute

    def prepare(session, saved, branch, state, work):
        if work['phase'] == 'read' and not target:
            target.append(branch.id)
            state['attempted_urls'] = [prior]
        return original_prepare(session, saved, branch, state, work)

    monkeypatch.setattr(steps, 'prepare', prepare)
    delayed_prepare(monkeypatch, now, lambda work: delayed[0] and work['phase'] == 'read',
        prepare_seconds=0, commit_seconds=301)
    dispatched = []

    async def execute(service, work, seconds):
        if work['phase'] == 'read' and work['branch_id'] in target:
            dispatched.append(deepcopy(work))
        return await original_execute(service, work, seconds)

    monkeypatch.setattr(research_gateway, 'execute', execute)
    for _ in range(20):
        outcome = tick(service, run['id'])
        if outcome['state'] == 'retrying':
            break
    assert target and not dispatched and not trace['reads']
    with service.db.session() as session:
        branch = session.get(InvestigationBranch, target[0])
        assert branch.phase == 'read' and branch.checkpoint['attempted_urls'] == [prior]
        assert not branch.checkpoint.get('inflight')
    delayed[0] = False
    for _ in range(12):
        tick(service, run['id'])
        if dispatched:
            break
    assert len(dispatched) == 1
    assert trace['reads'].count(dispatched[0]['item']['url']) == 1
    assert not dispatched[0]['skip']
    with service.db.session() as session:
        branch = session.get(InvestigationBranch, target[0])
        assert branch.checkpoint['attempted_urls'] == [prior, dispatched[0]['item']['url']]
        assert branch.checkpoint['source_ids']


def test_not_started_search_is_recovered_by_empty_retry_and_can_reformulate(signed, monkeypatch):
    from test_product_query_recovery import ORIGINAL, setup

    from helvetic_lens import product_query_recovery as recovery
    from helvetic_lens.product_research_admission import unmetered

    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    _, run, _ = start(client)
    service.settings.apertus_timeout_seconds = service.settings.job_lease_seconds = 300
    now, delayed, target = clock(monkeypatch), [True], []

    def is_target(work):
        if work['phase'] != 'search' or work['query'] != ORIGINAL:
            return False
        if not target:
            target.append(work['branch_id'])
        return delayed[0]

    delayed_prepare(monkeypatch, now, is_target, prepare_seconds=0, commit_seconds=301)
    for _ in range(20):
        outcome = tick(service, run['id'])
        if outcome['state'] == 'retrying':
            break
    assert target and trace['queries'].count(ORIGINAL) == 0
    with service.db.session() as session:
        branch = session.get(InvestigationBranch, target[0])
        pending_id = branch.checkpoint['steps'][-1]['id']
        assert branch.checkpoint['steps'][-1]['status'] == 'pending'
        assert branch.checkpoint['steps'][-1]['execution']['outcome'] == 'not_started'
    delayed[0] = False
    for _ in range(20):
        tick(service, run['id'])
        with service.db.session() as session:
            branch = session.get(InvestigationBranch, target[0])
            if branch.phase == 'reformulate':
                break
    else:
        pytest.fail('A successful empty search could not schedule ordinary query recovery')
    assert trace['queries'].count(ORIGINAL) == 1
    with service.db.session() as session:
        saved = session.get(Investigation, run['id'])
        branch = session.get(InvestigationBranch, target[0])
        state = branch.checkpoint
        assert unmetered(saved) and recovery.enabled(saved)
        assert state['query_recovery']['contract'] == recovery.CONTRACT
        pending = next(step for step in state['steps'] if step['id'] == pending_id)
        completed = next(step for step in state['steps'] if step['id'] == pending['recovered_by'])
        assert pending['status'] == 'pending' and pending['execution']['outcome'] == 'not_started'
        assert pending['execution']['model_requests'] == 0
        assert completed['phase'] == 'search' and completed['status'] == 'completed'
        assert recovery.unproductive(state, allow_partial=True)
        unrecovered = deepcopy(state)
        unrecovered['steps'].append({'phase': 'gate', 'status': 'unavailable'})
        assert not recovery.unproductive(unrecovered, allow_partial=True)
