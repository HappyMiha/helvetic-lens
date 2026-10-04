"""Live ownership protects bounded analysis cleanup, never an expired owner."""
import asyncio
from copy import deepcopy

import pytest
from test_product_dossiers import signed as signed
from test_product_exploration import adapters, start
from test_product_investigations import tick
from test_product_retrieval_preparation_resume import clock, delayed_prepare

from helvetic_lens import jobs, research_gateway
from helvetic_lens import product_investigation_worker as worker
from helvetic_lens.config import DomainError
from helvetic_lens.models import Job
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch
from helvetic_lens.research_synthesis_resume import KEY


@pytest.fixture
def owned(signed, monkeypatch):
    client, service, _, _ = signed
    _, run, _ = start(client)
    now = clock(monkeypatch)
    service.settings.job_lease_seconds = 300
    with service.db.session() as session:
        saved = session.get(Investigation, run['id'])
        job = jobs.claim(session, saved.job_id, 'current-owner')
        assert job is not None
        saved.status = 'running'
        branch = InvestigationBranch(organization_id=saved.organization_id, dossier_id=saved.dossier_id,
            investigation_id=saved.id, query='Bounded lease fixture', reason='Lease ownership fixture',
            phase='brief', status='running', checkpoint={'inflight': 'current-token'})
        session.add(branch)
        session.flush()
        work = {'run_id': saved.id, 'generation': saved.generation, 'branch_id': branch.id,
            'token': 'current-token', 'phase': 'brief'}
        session.commit()
        return service, job.id, work, now


@pytest.mark.parametrize('invalid', ['expired', 'owner', 'generation', 'token', 'cancel', 'inactive'])
def test_invalid_owner_never_renews_or_dispatches(owned, monkeypatch, invalid):
    service, job_id, work, now = owned
    with service.db.session() as session:
        job = session.get(Job, job_id)
        if invalid == 'expired':
            now[0] += 301
        elif invalid == 'owner':
            job.lease_owner = 'replacement-owner'
        elif invalid == 'generation':
            session.get(Investigation, work['run_id']).generation += 1
        elif invalid == 'token':
            session.get(InvestigationBranch, work['branch_id']).checkpoint = {'inflight': 'replacement-token'}
        elif invalid == 'cancel':
            job.cancel_requested = True
        else:
            session.get(Investigation, work['run_id']).status = 'paused'
        before = job.heartbeat_at
        session.commit()

    async def forbidden(*args):
        pytest.fail('Invalid ownership must not dispatch analysis')

    monkeypatch.setattr(research_gateway, 'execute', forbidden)
    with pytest.raises(worker._LeaseLost):
        asyncio.run(worker._execute_owned(service, job_id, 'current-owner', work, 30))
    with service.db.session() as session:
        assert session.get(Job, job_id).heartbeat_at == before
        assert KEY not in session.get(InvestigationBranch, work['branch_id']).checkpoint


@pytest.mark.parametrize('startup_seconds', [7, 31])
def test_renewal_cost_consumes_original_operation_deadline(owned, monkeypatch, startup_seconds):
    service, job_id, work, now = owned
    original, observed = worker._renew_active_lease, []

    def renew(*args):
        original(*args)
        now[0] += startup_seconds

    async def execute(service, work, seconds):
        observed.append(seconds)
        return 'completed'

    monkeypatch.setattr(worker, '_renew_active_lease', renew)
    monkeypatch.setattr(research_gateway, 'execute', execute)

    async def run():
        if startup_seconds > 30:
            with pytest.raises(worker._DispatchDeferred):
                await worker._execute_owned(service, job_id, 'current-owner', work, 30)
        else:
            assert await worker._execute_owned(service, job_id, 'current-owner', work, 30) == 'completed'
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    assert observed == ([] if startup_seconds > 30 else [23])


@pytest.mark.parametrize('termination', ['owner_lost', 'caller_cancelled'])
def test_active_pulse_and_operation_are_joined_on_loss_or_cancellation(owned, monkeypatch, termination):
    service, job_id, work, _ = owned
    real_sleep = asyncio.sleep
    started, cancelled = [], []

    async def sleep(seconds):
        await real_sleep(.001)

    async def execute(service, work, seconds):
        started.append(True)
        if termination == 'owner_lost':
            with service.db.session() as session:
                session.get(Job, job_id).lease_owner = 'new-owner'
                session.commit()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    monkeypatch.setattr(worker.asyncio, 'sleep', sleep)
    monkeypatch.setattr(research_gateway, 'execute', execute)

    async def run():
        task = asyncio.create_task(worker._execute_owned(service, job_id, 'current-owner', work, 30))
        while not started:
            await real_sleep(0)
        if termination == 'caller_cancelled':
            task.cancel()
        with pytest.raises(worker._LeaseLost if termination == 'owner_lost' else asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert cancelled == [True]
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    with service.db.session() as session:
        assert KEY not in session.get(InvestigationBranch, work['branch_id']).checkpoint


def test_dispatch_renews_immediately_when_preparation_used_almost_the_whole_lease(owned, monkeypatch):
    service, job_id, work, now = owned
    now[0] = 299
    observed = []

    async def execute(service, work, seconds):
        with service.db.session() as session:
            job = session.get(Job, job_id)
            assert (worker.utcnow() - job.heartbeat_at.replace(tzinfo=worker.UTC)).total_seconds() == 0
        observed.append(seconds)

    monkeypatch.setattr(research_gateway, 'execute', execute)
    asyncio.run(worker._execute_owned(service, job_id, 'current-owner', work, .5))
    assert observed == [.5], 'A new lease heartbeat must not enlarge the original remaining operation time'


def test_live_lease_retains_completed_work_after_late_cleanup_and_resumes_without_repeat(signed, monkeypatch):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    _, run, _ = start(client)
    now = clock(monkeypatch)
    service.settings.job_lease_seconds = service.settings.apertus_timeout_seconds = 300
    target, responses, dispatch = [], [], []

    def is_target(work):
        if work['phase'] != 'reflect':
            return False
        if not target:
            target.append(work['branch_id'])
        return target[0] == work['branch_id']

    delayed_prepare(monkeypatch, now, is_target, prepare_seconds=10, commit_seconds=0)
    original_execute, original_renew, real_sleep = research_gateway.execute, worker._renew_active_lease, asyncio.sleep
    signals = {}
    preserved = {'stage': 'finalizing', 'raw': 'completed private draft',
        'parts': {'final_reviews': {'clauses:completed': {'verdict': 'supported', 'source_refs': [1]}}}}

    def renew(service, job_id, lease, work):
        original_renew(service, job_id, lease, work)
        if signals and work['branch_id'] == target[0]:
            signals['renewed'].set()

    async def sleep(seconds):
        if signals and seconds > 1:
            await signals['pulse'].wait()
            signals['pulse'].clear()
        else:
            await real_sleep(seconds)

    async def execute(service, work, seconds):
        if not is_target(work):
            return await original_execute(service, work, seconds)
        assert seconds == 285, 'Renewal does not enlarge the initial operation allowance'
        dispatch.append(seconds)
        if len(dispatch) == 2:
            assert work[KEY] == preserved
            return responses[0]  # The already completed gateway result is resumed, not regenerated.
        responses.append(await original_execute(service, work, seconds))
        work[KEY] = deepcopy(preserved)
        signals.update(pulse=asyncio.Event(), renewed=asyncio.Event())
        now[0] += 100
        signals['pulse'].set()
        await asyncio.wait_for(signals['renewed'].wait(), 2)
        # The finite operation has ended; synchronous cleanup exceeds the old
        # five-second headroom, but a still-owned lease was renewed beforehand.
        now[0] += seconds - 100 + 8
        signals.clear()
        raise DomainError('Completed work yields after cleanup.', 503, 'research_review_yield')

    monkeypatch.setattr(worker, '_renew_active_lease', renew)
    monkeypatch.setattr(worker.asyncio, 'sleep', sleep)
    monkeypatch.setattr(research_gateway, 'execute', execute)
    for _ in range(45):
        result = tick(service, run['id'])
        if dispatch:
            break
    assert result['state'] == 'continuing_evidence_review'
    with service.db.session() as session:
        branch = session.get(InvestigationBranch, target[0])
        assert branch.checkpoint[KEY] == preserved
        assert not branch.checkpoint.get('inflight')
        assert branch.checkpoint['steps'][-1]['execution']['outcome'] == 'checkpointed'
        assert branch.checkpoint['steps'][-1]['checkpointed'] is True
        assert not branch.checkpoint.get('provider_retries')
        retained_reading = deepcopy(branch.checkpoint.get('document_reads'))
    readings, analyses = len(trace['reads']), sum(item['phase'] == 'ResearchExtraction' for item in trace['models'])
    for _ in range(12):
        tick(service, run['id'])
        if len(dispatch) == 2:
            break
    assert dispatch == [285, 285] and len(responses) == 1
    assert len(trace['reads']) == readings
    assert sum(item['phase'] == 'ResearchExtraction' for item in trace['models']) == analyses
    with service.db.session() as session:
        branch = session.get(InvestigationBranch, target[0])
        assert branch.status != 'failed' and KEY not in branch.checkpoint
        assert branch.checkpoint.get('document_reads') == retained_reading
        assert not any(step['status'] == 'interrupted' for step in branch.checkpoint['steps'])
