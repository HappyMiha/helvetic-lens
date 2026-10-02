"""Temporary inference outages retain the native research checkpoint."""
from datetime import timedelta

import pytest
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_investigations import pipeline, start, tick

from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.models import Job
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch
from helvetic_lens.product_investigations import rows


@pytest.mark.parametrize('action', ['continue', 'pause', 'withdraw'])
def test_private_final_checkpoint_is_hidden_and_obeys_native_pause_and_source_fences(signed, monkeypatch, action):
    import json

    from test_product_early_orientation import exclude
    from test_product_exploration import adapters
    from test_product_exploration import start as explore

    from helvetic_lens import research_gateway
    from helvetic_lens.research_synthesis_resume import KEY

    client, service, identity, model = signed
    adapters(monkeypatch, service, model)
    root, run, _ = explore(client)
    execute, calls, source_ids = research_gateway.execute, [], []
    marker = 'PRIVATE UNFINISHED ANSWER CHECKPOINT'
    async def interrupted(service, work, seconds):
        if work['phase'] != 'brief':
            return await execute(service, work, seconds)
        calls.append(work['branch_id'])
        if len(calls) == 1:
            source_ids.extend(s['id'] for s in work['input']['sources'])
            work[KEY] = {'raw': marker, 'stage': 'reviewed'}
            raise DomainError('Synthetic provider outage', 503, 'model_rate_limited')
        assert work[KEY]['raw'] == marker
        return await execute(service, work, seconds)
    monkeypatch.setattr(research_gateway, 'execute', interrupted)
    for _ in range(45):
        tick(service, run['id'])
        with service.db.session() as session:
            job = session.get(Job, session.get(Investigation, run['id']).job_id)
            if job.error_code == 'research_provider_backoff':
                break
    else:
        pytest.fail('No private final checkpoint was retained')
    url = root + '/investigations/' + run['id']
    value = client.get(url).json()
    assert marker not in json.dumps(value)
    assert marker not in client.get(root + '/export').text
    with service.db.session() as session:
        assert session.get(InvestigationBranch, calls[0]).checkpoint[KEY]['raw'] == marker
    if action == 'pause':
        assert post(client, url + '/control', {'action': 'pause', 'expected_revision': value['revision']}).status_code == 200
    elif action == 'withdraw':
        exclude(service, identity, source_ids[0])
    with service.db.session() as session:
        job = session.get(Job, session.get(Investigation, run['id']).job_id)
        job.available_at = utcnow() - timedelta(seconds=1)
        session.commit()
    tick(service, run['id'])
    assert len(calls) == (2 if action == 'continue' else 1)
    with service.db.session() as session:
        branch = session.get(InvestigationBranch, calls[0])
        if action == 'continue':
            assert KEY not in branch.checkpoint
    assert marker not in client.get(url).text


def test_same_provider_input_does_not_restart_outage_retries_when_accounting_changes(signed, monkeypatch):
    from helvetic_lens import research_gateway
    client, service, _, model = signed
    pipeline(monkeypatch, service, model)
    _, run, _ = start(client)
    execute = research_gateway.execute
    calls = []
    async def unavailable(service, work, seconds):
        if work['phase'] != 'extract':
            return await execute(service, work, seconds)
        calls.append(work['branch_id'])
        work['execution_route']['input_fingerprint'] = 'changed-accounting-' + str(len(calls))
        work['model_route'] = {'evidence_transport': {'input_fingerprint': 'same-original-provider-input'}}
        raise DomainError('Synthetic outage', 503, 'model_temporarily_unavailable')
    monkeypatch.setattr(research_gateway, 'execute', unavailable)
    for _ in range(12):
        tick(service, run['id'])
        with service.db.session() as session:
            current = session.get(Investigation, run['id'])
            job = session.get(Job, current.job_id)
            if job.state == 'queued':
                job.available_at = utcnow() - timedelta(seconds=1)
            session.commit()
        if len(calls) == 4:
            break
    assert len(calls) == 4 and len(set(calls)) == 1
    with service.db.session() as session:
        branch = session.get(InvestigationBranch, calls[0])
        assert branch.checkpoint['provider_retries'] == {'same-original-provider-input': 3}
        assert branch.checkpoint.get('failed_extract_indices')


@pytest.mark.parametrize('pause', [False, True])
def test_rate_limit_wait_is_durable_deduplicated_and_respects_pause(signed, monkeypatch, pause):
    client, service, _, model = signed
    pipeline(monkeypatch, service, model)
    root, run, _ = start(client)
    original = model.complete
    calls = []
    async def temporary_outage(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise DomainError('Synthetic temporary upstream issue', 503, 'model_rate_limited')
        return await original(*args, **kwargs)
    monkeypatch.setattr(model, 'complete', temporary_outage)
    for _ in range(10):
        tick(service, run['id'])
        with service.db.session() as session:
            current = session.get(Investigation, run['id'])
            job = session.get(Job, current.job_id)
            if job.error_code == 'research_provider_backoff':
                branch = next(b for b in rows(session, InvestigationBranch, current) if b.phase == 'extract')
                captured = branch.checkpoint['source_ids']
                assert not branch.checkpoint.get('failed_extract_indices')
                assert not branch.checkpoint.get('inflight')
                assert job.available_at.replace(tzinfo=utcnow().tzinfo) > utcnow()
                break
    else:
        pytest.fail('No durable waiting checkpoint')
    tick(service, run['id'])
    assert len(calls) == 1  # Duplicate delivery cannot bypass the persisted delay.
    if pause:
        value = client.get(root + '/' + run['id']).json()
        result = post(client, root + '/' + run['id'] + '/control', {'action': 'pause', 'expected_revision': value['revision']})
        assert result.status_code == 200, result.text
    with service.db.session() as session:
        current = session.get(Investigation, run['id'])
        job = session.get(Job, current.job_id)
        job.available_at = utcnow() - timedelta(seconds=1)
        session.commit()
    tick(service, run['id'])
    assert len(calls) == (1 if pause else 2)
    with service.db.session() as session:
        current = session.get(Investigation, run['id'])
        assert captured == next(b.checkpoint['source_ids'] for b in rows(session, InvestigationBranch, current) if b.checkpoint.get('source_ids'))
    if not pause:
        value = client.get(root + '/' + run['id']).json()
        assert value['claims'] and len(value['sources']) == 1


def test_linked_source_leads_do_not_invalidate_unchanged_canonical_evidence(signed, monkeypatch):
    from test_product_exploration import adapters
    from test_product_exploration import start as explore
    from test_product_iterative_research import complete

    from helvetic_lens import decision_sources

    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    original = decision_sources.safe_inspect
    async def read(*args, **kwargs):
        value = await original(*args, **kwargs)
        value['links'] = [{'url': 'https://example.org/original', 'title': 'Original grant record',
            'context': 'An original source for the foundation grant.', 'kind': 'document'}]
        return value
    monkeypatch.setattr(decision_sources, 'safe_inspect', read)
    root, run, _ = explore(client)
    value = complete(client, service, root + '/investigations', run)
    assert value['status'] == 'completed', value['stop_reason']
    assert value['exploration']['status'] == 'ready'
    supplied = trace['briefings'][-1]
    assert any(source.get('discovery_links') for source in supplied['synthesis_sources'])
    assert all('discovery_links' not in source for source in supplied['sources'])
