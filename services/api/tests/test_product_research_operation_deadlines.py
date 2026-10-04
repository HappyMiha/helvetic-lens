"""Configured model deadlines reach the durable worker without widening other work."""
from copy import deepcopy
from time import monotonic

import pytest
from test_product_dossiers import signed as signed
from test_product_exploration import adapters, start
from test_product_investigations import tick
from test_product_iterative_research import complete

from helvetic_lens import product_iterative_steps as steps
from helvetic_lens import research_gateway as gateway
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch


@pytest.mark.parametrize('provider_timeout,lease,explicit,metered,expected', [
    (180, 300, None, False, 180),
    (300, 300, None, False, 295),
    (300, 360, None, False, 300),
    (180, 300, 37, False, 37),
    (90, 300, None, False, 90),
    (30, 300, None, False, 30),
    (180, 300, None, True, 90),
])
def test_real_dispatch_records_operator_model_deadline_with_lease_and_phase_fences(
        signed, monkeypatch, provider_timeout, lease, explicit, metered, expected):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    _, run, _ = start(client)
    # Admission/recall schedules planning; mutate only the disposable fixture's
    # operator settings and legacy marker before any model operation is run.
    tick(service, run['id'])
    service.settings.apertus_timeout_seconds = provider_timeout
    service.settings.job_lease_seconds = lease
    if metered:
        with service.db.session() as session:
            saved = session.get(Investigation, run['id'])
            data = deepcopy(saved.research_state)
            data.pop('admission', None)
            data.pop('mission', None)
            saved.research_state = data
            session.commit()
    original_prepare, original_execute, original_model = steps.prepare, gateway.execute, model.complete
    dispatch, budgets = [], []

    def prepare(session, saved, branch, state, work):
        result = original_prepare(session, saved, branch, state, work)
        if work['phase'] == 'plan' and explicit is not None:
            work['timeout_seconds'] = explicit
        return result

    async def execute(service, work, seconds):
        if work['phase'] == 'plan':
            with service.db.session() as session:
                branch = session.get(InvestigationBranch, work['branch_id'])
                receipt = branch.checkpoint['steps'][-1]
                assert receipt['status'] == 'running'
                assert receipt['id'] == work['token']
                assert seconds <= work['deadline_seconds'] == receipt['deadline_seconds'] <= expected
                assert seconds > expected - 5
            dispatch.append(seconds)
        return await original_execute(service, work, seconds)

    async def model_complete(system, text, **options):
        if options['response_schema']['title'] == 'ResearchPlan':
            budget = options['budget']
            budgets.append(budget.deadline - monotonic())
            assert budget.max_requests == 1
        return await original_model(system, text, **options)

    monkeypatch.setattr(steps, 'prepare', prepare)
    monkeypatch.setattr(gateway, 'execute', execute)
    monkeypatch.setattr(model, 'complete', model_complete)
    for _ in range(5):
        tick(service, run['id'])
        if budgets:
            break
    assert len(dispatch) == len(budgets) == 1 and expected - 5 < dispatch[0] <= expected
    assert expected - 5 < budgets[0] <= expected
    assert service.settings.apertus_timeout_seconds == provider_timeout
    with service.db.session() as session:
        saved = session.get(Investigation, run['id'])
        assert saved.status in {'queued', 'running'}
        assert saved.research_state['questions'], 'The ordinary model result must still be applied'


def test_model_extension_preserves_capture_and_orientation_caps_through_real_research(signed, monkeypatch):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    root, run, _ = start(client)
    service.settings.apertus_timeout_seconds = 180
    service.settings.job_lease_seconds = 300
    original = gateway.execute
    dispatch = []

    async def execute(service, work, seconds):
        dispatch.append((work['phase'], seconds))
        return await original(service, work, seconds)

    monkeypatch.setattr(gateway, 'execute', execute)
    result = complete(client, service, root + '/investigations', run)
    assert result['exploration']['status'] == 'ready', result['stop_reason']
    assert trace['reads'] and trace['briefings']
    for phase in ('plan', 'extract', 'reflect', 'brief'):
        assert any(kind == phase and seconds == 180 for kind, seconds in dispatch), phase
    assert any(kind == 'orient' and seconds == 45 for kind, seconds in dispatch)
    assert all(seconds <= 90 for kind, seconds in dispatch if kind in {'recall', 'search', 'gate', 'read'})
    assert all(seconds <= service.settings.job_lease_seconds - 5 for _, seconds in dispatch)
