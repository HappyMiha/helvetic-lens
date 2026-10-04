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
@pytest.mark.parametrize('interruption', ['provider', 'deadline'])
def test_private_final_checkpoint_is_hidden_and_obeys_native_pause_and_source_fences(signed, monkeypatch, action, interruption):
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
            if interruption == 'deadline':
                import asyncio
                # Exercise the builtin exception produced by an expired task deadline.
                async with asyncio.timeout(0):
                    await asyncio.sleep(0)
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
    from test_product_investigations import complete

    from helvetic_lens import research_gateway
    client, service, _, model = signed
    pipeline(monkeypatch, service, model)
    root, run, _ = start(client)
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
    value = complete(client, service, root, run)
    result = post(client, root + '/' + run['id'] + '/control', {'action': 'retry', 'expected_revision': value['revision']})
    assert result.status_code == 200, result.text
    before = len(calls)
    tick(service, run['id'])
    assert len(calls) == before + 1
    with service.db.session() as session:
        branch = session.get(InvestigationBranch, calls[-1])
        assert branch.checkpoint['provider_retries'] == {'same-original-provider-input': 1}
        job = session.get(Job, session.get(Investigation, run['id']).job_id)
        assert job.error_code == 'research_provider_backoff'
    tick(service, run['id'])
    assert len(calls) == before + 1, 'Redelivery cannot bypass the new retry backoff'


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


@pytest.mark.parametrize('withdraw', [False, True])
@pytest.mark.parametrize('failure', ['research_review_incomplete', 'research_evidence_group_too_large', 'model_incomplete'])
def test_incomplete_final_review_requires_explicit_retry_and_retains_private_checkpoint(signed, monkeypatch, withdraw, failure):
    import json

    from test_product_early_orientation import exclude
    from test_product_exploration import adapters
    from test_product_exploration import start as explore
    from test_product_iterative_research import complete

    from helvetic_lens import research_gateway
    from helvetic_lens.research_synthesis_resume import EXHAUSTED_REVIEW, KEY

    client, service, identity, model = signed
    adapters(monkeypatch, service, model)
    scripted = model.complete
    async def completed_mission(*args, **kwargs):
        value = json.loads(await scripted(*args, **kwargs))
        if 'mission_checkpoint' in kwargs['response_schema'].get('properties', {}):
            first = value['findings'][0]
            value['mission_checkpoint'] = {'action': 'finish',
                'reason': 'The retained source supports this finding; remaining uncertainty is explicit.',
                'answer': {'status': 'partial', 'limitations': value['uncertainties'],
                    'points': [{'statement': first['statement'], 'evidence': [
                        {**{key: first[key] for key in ('source_id', 'locator', 'quote')}, 'role': 'support'}]}]}}
        return json.dumps(value)
    monkeypatch.setattr(model, 'complete', completed_mission)
    root, run, _ = explore(client)
    original, calls, sources = research_gateway.execute, [], []
    marker = 'PRIVATE CHECKED SIBLINGS AND PENDING FINAL REVIEW'
    async def incomplete(service, work, seconds):
        if work['phase'] != 'brief':
            return await original(service, work, seconds)
        calls.append(work['branch_id'])
        if len(calls) == 1:
            sources.extend(s['id'] for s in work['input']['sources'])
            work[KEY] = {'raw': marker, 'stage': 'reviewed'}
            if withdraw:
                exclude(service, identity, sources[0])
            status = {'research_evidence_group_too_large': 422, 'model_incomplete': 502}.get(failure, 503)
            raise DomainError('Fictional interrupted generation or evidence review', status, failure)
        assert work[KEY]['raw'] == marker
        assert [s['id'] for s in work['input']['sources']] == sources
        return await original(service, work, seconds)
    monkeypatch.setattr(research_gateway, 'execute', incomplete)
    result = complete(client, service, root + '/investigations', run)
    url = root + '/investigations/' + run['id']
    assert marker not in json.dumps(result) and marker not in client.get(root + '/export').text
    with service.db.session() as session:
        branch = session.get(InvestigationBranch, calls[0])
        if withdraw:
            assert KEY not in branch.checkpoint
            assert result['status'] == 'paused'
            return
        assert branch.checkpoint[KEY]['raw'] == marker
        assert branch.checkpoint['steps'][-1]['error_code'] == failure
        assert not branch.checkpoint.get('provider_retries'), 'Invalid review is not automatically repurchased'
        assert EXHAUSTED_REVIEW not in branch.checkpoint, 'An incomplete response cannot authorize checked partial delivery'
    assert result['status'] == 'failed' and result['retry']['available'] is True and len(calls) == 1
    tick(service, run['id'])
    assert len(calls) == 1
    reply = post(client, url + '/control', {'action': 'retry', 'expected_revision': result['revision']})
    assert reply.status_code == 200, reply.text
    finished = complete(client, service, root + '/investigations', reply.json())
    assert finished['status'] == 'completed' and len(calls) == 2
    with service.db.session() as session:
        assert KEY not in session.get(InvestigationBranch, calls[0]).checkpoint


def test_only_validated_saved_work_counts_as_progress():
    from helvetic_lens.research_synthesis_resume import completed_work
    saved = {'parts': {'empty': {}, 'workflow_gaps': ['Notice'], 'repair_concerns': {'P0': {}},
        'final_reviews': {'clauses:actual': {'overall': {'verdict': 'supported'}}}}, 'raw': 'First draft'}
    prior = completed_work(saved)
    saved['raw'] = 'Changed draft'
    saved['parts']['workflow_gaps'].append('Another notice')
    saved['parts']['empty2'] = {}
    saved['parts']['final_reviews']['reasoned:aggregate'] = {'status': 'partial'}
    assert completed_work(saved) == prior
    saved['parts']['final_reviews']['clauses:actual']['overall']['verdict'] = 'not_established'
    assert completed_work(saved) != prior


@pytest.mark.parametrize('withdraw', [False, True])
def test_completed_review_work_continues_automatically_with_source_and_privacy_fences(signed, monkeypatch, withdraw):
    import json

    from test_product_early_orientation import exclude
    from test_product_exploration import adapters
    from test_product_exploration import start as explore
    from test_product_iterative_research import complete

    from helvetic_lens import research_gateway
    from helvetic_lens.research_synthesis_resume import KEY

    client, service, identity, model = signed
    adapters(monkeypatch, service, model)
    root, run, _ = explore(client)
    execute, calls, sources = research_gateway.execute, [], []
    marker = 'PRIVATE REVIEW CHECKPOINT'
    async def yielded(service, work, seconds):
        if work['phase'] != 'brief':
            return await execute(service, work, seconds)
        calls.append(work['branch_id'])
        if len(calls) == 1:
            sources.extend(s['id'] for s in work['input']['sources'])
            work[KEY] = {'raw': marker, 'stage': 'reviewed', 'parts': {
                'final_reviews': {'clauses:checked': {'overall': {'verdict': 'supported'}}}}}
            if withdraw:
                exclude(service, identity, sources[0])
            raise DomainError('Work step ended after retained progress', 503, 'research_review_yield')
        assert work[KEY]['raw'] == marker
        assert [s['id'] for s in work['input']['sources']] == sources
        return await execute(service, work, seconds)
    monkeypatch.setattr(research_gateway, 'execute', yielded)
    result = complete(client, service, root + '/investigations', run)
    assert result['status'] == ('paused' if withdraw else 'completed')
    assert len(calls) == (1 if withdraw else 2)
    assert marker not in json.dumps(result) and marker not in client.get(root + '/export').text
    with service.db.session() as session:
        state = session.get(InvestigationBranch, calls[0]).checkpoint
        assert KEY not in state
        if not withdraw:
            assert not state.get('provider_retries')
            assert any(step.get('checkpointed') and step['status'] == 'completed' for step in state['steps'])


@pytest.mark.parametrize('progress', [True, False])
@pytest.mark.parametrize('interruption', ['provider', 'deadline'])
def test_only_new_validated_work_renews_a_later_provider_outage(signed, monkeypatch, progress, interruption):
    from test_product_exploration import adapters
    from test_product_exploration import start as explore

    from helvetic_lens import research_gateway
    from helvetic_lens.research_synthesis_resume import KEY

    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    root, run, _ = explore(client)
    execute, calls = research_gateway.execute, []
    async def intermittent(service, work, seconds):
        if work['phase'] != 'brief':
            return await execute(service, work, seconds)
        calls.append(work['branch_id'])
        if len(calls) > 4:
            return await execute(service, work, seconds)
        parts = {'workflow_gaps': [f'Unfinished check {len(calls)}'], 'empty': {}}
        if progress:
            parts['final_reviews'] = {f'clauses:accepted-{i}': {'overall': {'verdict': 'supported'}}
                for i in range(len(calls))}
        work[KEY] = {'stage': 'reviewed', 'raw': f'Private draft {len(calls)}', 'parts': parts}
        if interruption == 'deadline':
            raise TimeoutError('Worker step deadline')
        raise DomainError('Temporary outage after work or unchanged input', 503, 'model_rate_limited')
    monkeypatch.setattr(research_gateway, 'execute', intermittent)
    for _ in range(60):
        tick(service, run['id'])
        with service.db.session() as session:
            current = session.get(Investigation, run['id'])
            if current.status not in {'queued', 'running'}:
                final_status = current.status
                break
            job = session.get(Job, current.job_id)
            if job.error_code == 'research_provider_backoff':
                branch = session.get(InvestigationBranch, calls[0])
                assert list(branch.checkpoint['provider_retries'].values()) == [1 if progress else len(calls)]
                job.available_at = utcnow() - timedelta(seconds=1)
                session.commit()
    else:
        pytest.fail('Provider recovery never reached a final state')
    assert final_status == ('completed' if progress else 'failed')
    assert len(calls) == (5 if progress else 4)


@pytest.mark.parametrize(('phase', 'outcome'),
    [(phase, outcome) for phase in ('brief', 'reflect') for outcome in ('continue', 'stall', 'withdraw')]
    + [('orient', 'continue')])
def test_evidence_preparation_retains_batches_privately_and_only_new_work_continues(signed, monkeypatch, outcome, phase):
    import json

    from test_product_early_orientation import exclude
    from test_product_exploration import adapters
    from test_product_exploration import start as explore
    from test_product_iterative_research import complete

    from helvetic_lens import research_gateway
    from helvetic_lens.research_synthesis_resume import KEY

    client, service, identity, model = signed
    adapters(monkeypatch, service, model)
    scripted = model.complete

    async def completed_mission(*args, **kwargs):
        value = json.loads(await scripted(*args, **kwargs))
        if 'mission_checkpoint' in kwargs['response_schema'].get('properties', {}):
            first = value['findings'][0]
            value['mission_checkpoint'] = {'action': 'finish',
                'reason': 'The retained source supports this finding; remaining uncertainty is explicit.',
                'answer': {'status': 'partial', 'limitations': value['uncertainties'],
                    'points': [{'statement': first['statement'], 'evidence': [
                        {**{key: first[key] for key in ('source_id', 'locator', 'quote')}, 'role': 'support'}]}]}}
        return json.dumps(value)

    monkeypatch.setattr(model, 'complete', completed_mission)
    root, run, _ = explore(client)
    execute, calls, sources = research_gateway.execute, [], []
    marker = 'PRIVATE COMPLETED SOURCE SELECTION'
    batch = {'status': 'complete', 'input_fingerprint': 'original-batch',
        'policy_fingerprint': 'selection-policy', 'selected': []}

    async def preparing(service, work, seconds):
        if work['phase'] != phase or (calls and work['branch_id'] != calls[0]):
            return await execute(service, work, seconds)
        calls.append(work['branch_id'])
        if len(calls) == 1:
            sources.extend(source['id'] for source in work['input']['sources'])
            work[KEY] = {'stage': 'preparing', 'raw': '', 'parts': {'evidence_selection': {marker: batch}}}
            if outcome == 'withdraw':
                exclude(service, identity, sources[0])
            raise DomainError('Selection deadline after one completed batch', 503, 'research_evidence_pack_incomplete')
        assert work[KEY]['stage'] == 'preparing' and work[KEY]['raw'] == ''
        assert work[KEY]['parts']['evidence_selection'] == {marker: batch}
        assert [source['id'] for source in work['input']['sources']] == sources
        if outcome == 'stall' and len(calls) == 2:
            work[KEY]['parts']['timing'] = {'seconds': 90}  # Accounting is not progress.
            raise DomainError('No additional batch completed', 503, 'research_evidence_pack_incomplete')
        return await execute(service, work, seconds)

    monkeypatch.setattr(research_gateway, 'execute', preparing)
    result = complete(client, service, root + '/investigations', run)
    # A failed reflection remains retryable even when other branches produced
    # a final briefing; only an unavailable final briefing fails the whole run.
    expected = {'continue': 'completed', 'stall': 'failed' if phase == 'brief' else 'completed', 'withdraw': 'paused'}
    assert result['status'] == expected[outcome], result['stop_reason']
    if outcome == 'continue' or outcome == 'stall' and phase == 'reflect':
        assert result['exploration']['mission']['answer']['points']
    assert len(calls) == (1 if outcome == 'withdraw' else 2)
    assert marker not in json.dumps(result) and marker not in client.get(root + '/export').text
    with service.db.session() as session:
        branch = session.get(InvestigationBranch, calls[0])
        state = branch.checkpoint
        assert not state.get('provider_retries'), 'A selection deadline is not a provider outage'
        if outcome == 'stall':
            assert branch.status == 'failed'
            assert state[KEY]['parts']['evidence_selection'] == {marker: batch}
            assert state['error'].startswith('Evidence selection is incomplete.')
        else:
            assert KEY not in state
        if outcome != 'withdraw':
            assert sum(bool(step.get('checkpointed')) for step in state['steps']) == 1
    if outcome == 'stall':
        assert result['retry']['available'] is True
        tick(service, run['id'])
        assert len(calls) == 2, 'Unchanged preparation cannot create an automatic resume loop'
        reply = post(client, root + '/investigations/' + run['id'] + '/control',
            {'action': 'retry', 'expected_revision': result['revision']})
        assert reply.status_code == 200, reply.text
        finished = complete(client, service, root + '/investigations', reply.json())
        assert finished['status'] == 'completed' and len(calls) == 3
        assert finished['exploration']['mission']['answer']['points']


@pytest.mark.parametrize('brief_status', [None, 'failed', 'completed'])
def test_retry_eligibility_skips_only_obsolete_early_orientation(signed, monkeypatch, brief_status):
    from test_product_exploration import adapters
    from test_product_exploration import start as explore

    from helvetic_lens.product_contributions import retryable_branches
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    _, run, _ = explore(client)
    with service.db.session() as session:
        saved = session.get(Investigation, run['id'])
        saved.status = 'failed'
        def branch(phase, status):
            value = InvestigationBranch(organization_id=saved.organization_id, dossier_id=saved.dossier_id,
                investigation_id=saved.id, query=phase, phase=phase, status=status, reason='Synthetic unavailable phase',
                checkpoint={'steps': [{'status': 'unavailable'}]})
            session.add(value)
            session.flush()
            return value
        orient = branch('orient', 'failed')
        source = branch('reflect', 'failed')
        brief = branch('brief', brief_status) if brief_status else None
        candidates = {b.id for b in retryable_branches(session, saved)}
        assert (orient.id in candidates) == (brief_status is None)
        assert source.id in candidates, 'Final recovery must not hide unfinished source work'
        if brief is not None:
            assert (brief.id in candidates) == (brief_status == 'failed')
        assert orient.status == 'failed', 'Historical errors are not rewritten as success'
