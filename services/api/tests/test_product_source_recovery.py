"""Bounded durable fallback on synthetic sources, not live research quality."""
import json
from copy import deepcopy
from uuid import uuid4

import pytest
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude
from test_product_exploration import adapters, start
from test_product_investigations import tick
from test_product_iterative_research import complete

from helvetic_lens import decision_search, decision_sources, product_exploration
from helvetic_lens.models import Job
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch
from helvetic_lens.product_investigations import rows


def prepare(monkeypatch, service, model, *, all_fail=False):
    trace = adapters(monkeypatch, service, model)
    retrieve, inspect = decision_search.federated_retrieve, decision_sources.safe_inspect
    trace['attempts'] = []

    async def search(*args):
        result = await retrieve(*args)
        if 'legal identity' in args[1]:
            road, good = result['items']
            result['items'] = [{**good, 'id': f'failed-{n}', 'url': f'https://example.org/failed-{n}'} for n in (1, 2)] + [good, road]
        return result

    async def read(*args, **kwargs):
        url = args[2]['url']
        trace['attempts'].append(url)
        if all_fail or '/failed-' in url:
            return {'status': 'unavailable', 'error': 'PRIVATE PROVIDER CANARY'}
        return await inspect(*args, **kwargs)

    monkeypatch.setattr(decision_search, 'federated_retrieve', search)
    monkeypatch.setattr(decision_sources, 'safe_inspect', read)
    return trace


def recovery(value):
    return value['exploration']['research_scope']['source_recovery']


def projection(service, run):
    with service.db.session() as session:
        return product_exploration.projection(session, session.get(Investigation, run['id']))


def until_recovery(service, run):
    for _ in range(15):
        tick(service, run['id'])
        with service.db.session() as session:
            saved = session.get(Investigation, run['id'])
            branch = next((b for b in rows(session, InvestigationBranch, saved)
                if 'first_alternative_index' in b.checkpoint.get('source_recovery', {})), None)
            if branch:
                return branch.id
    raise AssertionError('No real recovery checkpoint')


@pytest.mark.parametrize('product', ['legal', 'pharma'])
def test_failed_pages_use_gated_alternatives_and_produce_cited_brief(signed, monkeypatch, product):
    client, service, _, model = signed
    trace = prepare(monkeypatch, service, model)
    root, run, _ = start(client, product)
    read = decision_sources.safe_inspect
    active = []

    async def inspect(*args, **kwargs):
        if args[2]['url'].endswith('/identity'):
            view = projection(service, run)
            active.append(view['current_activity'])
            assert view['current_activity']['checking_alternative'] is True
        return await read(*args, **kwargs)

    monkeypatch.setattr(decision_sources, 'safe_inspect', inspect)
    value = complete(client, service, root + '/investigations', run)
    result = recovery(value)
    assert value['exploration']['briefing'] and value['exploration']['status'] == 'ready'
    assert result == {'contract': 'source-recovery/v1', 'status': 'ready', 'failed_reads': 2,
        'candidates_checked': 2, 'reads_attempted': 1, 'captures': 1, 'candidate_sets_exhausted': 1, 'unfinished': 0}
    assert len(trace['queries']) == 3 and len(trace['attempts']) == len(set(trace['attempts'])) == 5
    assert value['research']['used']['source_fetches'] == 5 <= value['research']['limits']['source_fetches']
    assert value['exploration']['research_scope']['reads']['unavailable'] == 2
    assert value['exploration']['research_scope']['reads']['completed'] == 3
    assert active and all(v['phase'] == 'read' for v in active)
    assert trace['briefings'][-1]['research_scope']['source_recovery'] == result
    assert all(f['source_id'] in {s['id'] for s in value['exploration']['sources']} for f in value['exploration']['briefing']['findings'])
    assert 'PRIVATE PROVIDER CANARY' not in json.dumps(value)
    assert client.get(root + '/web-research').json()['policy']['enabled'] is False
    assert client.get(root + '/investigations').json()['total'] == 1


@pytest.mark.parametrize('mode', ['all_fail', 'legacy', 'duplicate', 'excluded_before', 'excluded_after'])
def test_exhaustion_legacy_duplicate_and_access_fences(signed, monkeypatch, mode):
    client, service, identity, model = signed
    trace = prepare(monkeypatch, service, model, all_fail=mode == 'all_fail')
    root, run, _ = start(client)
    if mode == 'legacy':
        with service.db.session() as session:
            saved = session.get(Investigation, run['id'])
            data = deepcopy(saved.research_state)
            data['exploration'].pop('recovery_contract')
            saved.research_state = data
            session.commit()
    if mode == 'duplicate':
        search = decision_search.federated_retrieve
        async def duplicate(*args):
            result = await search(*args)
            if 'legal identity' in args[1]:
                result['items'].insert(1, deepcopy(result['items'][0]))
            return result
        monkeypatch.setattr(decision_search, 'federated_retrieve', duplicate)
    if mode in {'excluded_before', 'excluded_after'}:
        from helvetic_lens.product_models import DossierEntry
        def block():
            with service.db.session() as session:
                saved = session.get(Investigation, run['id'])
                session.add(DossierEntry(dossier_id=saved.dossier_id, organization_id=saved.organization_id,
                    request_key=str(uuid4()), kind='source_review', actor_user_id=identity['user']['id'],
                    url='https://example.org/identity', body='PRIVATE EXCLUSION REASON',
                    data_json={'decision': 'exclude', 'revision': 1}))
                session.commit()
        if mode == 'excluded_before':
            until_recovery(service, run)
            block()
        else:
            reader = decision_sources.safe_inspect
            async def exclude_after(*args, **kwargs):
                result = await reader(*args, **kwargs)
                if args[2]['url'].endswith('/identity'):
                    block()
                return result
            monkeypatch.setattr(decision_sources, 'safe_inspect', exclude_after)
    value = complete(client, service, root + '/investigations', run)
    assert len(trace['attempts']) == len(set(trace['attempts']))
    assert value['research']['used']['source_fetches'] <= value['research']['limits']['source_fetches']
    if mode == 'legacy':
        assert recovery(value) == {'contract': 'source-recovery/v1', 'status': 'unknown'}
        assert 'https://example.org/identity' not in trace['attempts']
    else:
        assert recovery(value)['candidate_sets_exhausted'] >= 1
        if mode == 'all_fail':
            assert value['exploration']['briefing'] is None and recovery(value)['captures'] == 0
        elif mode == 'duplicate':
            assert recovery(value)['captures'] == 1 and value['exploration']['briefing']
        else:
            assert recovery(value)['captures'] == 0
            assert all(s['url'] != 'https://example.org/identity' for s in value['sources'])
            if mode == 'excluded_before':
                assert 'https://example.org/identity' not in trace['attempts']


@pytest.mark.parametrize('resource', ['source_fetches', 'decision_calls', 'active_seconds', 'model_calls'])
def test_recovery_cannot_expand_an_exhausted_budget(signed, monkeypatch, resource):
    client, service, _, model = signed
    trace = prepare(monkeypatch, service, model)
    root, run, _ = start(client)
    until_recovery(service, run)
    with service.db.session() as session:
        saved = session.get(Investigation, run['id'])
        data = deepcopy(saved.research_state)
        data['used'][resource] = data['limits'][resource] - int(resource == 'model_calls')
        saved.research_state = data
        session.commit()
    if resource == 'model_calls':
        from helvetic_lens import product_iterative_steps
        async def uncertain(*args):
            return {'verdict': 'uncertain', 'engine': 'fixture', 'basis': 'Needs model review.'}
        monkeypatch.setattr(product_iterative_steps, 'evaluate', uncertain)
    value = complete(client, service, root + '/investigations', run)
    assert resource in value['research']['stops']
    assert 'https://example.org/identity' not in trace['attempts']
    assert recovery(value)['captures'] == 0
    assert recovery(value)['unfinished'] >= 1
    assert value['research']['used'][resource] <= value['research']['limits'][resource] + (1 if resource == 'active_seconds' else 0)


@pytest.mark.parametrize('action', ['pause', 'cancel'])
def test_user_control_stops_alternative_work(signed, monkeypatch, action):
    client, service, _, model = signed
    trace = prepare(monkeypatch, service, model)
    root, run, _ = start(client)
    until_recovery(service, run)
    url = root + '/investigations/' + run['id']
    value = client.get(url).json()
    stopped = post(client, url + '/control', {'action': action, 'expected_revision': value['revision']})
    assert stopped.status_code == 200
    count = len(trace['attempts'])
    tick(service, run['id'])
    assert len(trace['attempts']) == count
    if action == 'pause':
        resumed = post(client, url + '/control', {'action': 'resume', 'expected_revision': stopped.json()['revision']})
        assert resumed.status_code == 200
        done = complete(client, service, root + '/investigations', run)
        assert recovery(done)['captures'] == 1


def test_interrupted_read_is_not_replayed_and_its_slot_can_recover(signed, monkeypatch):
    client, service, _, model = signed
    trace = prepare(monkeypatch, service, model)
    root, run, _ = start(client)
    reader = decision_sources.safe_inspect
    interrupted = []
    async def read(*args, **kwargs):
        result = await reader(*args, **kwargs)
        if not interrupted:
            with service.db.session() as session:
                job = session.get(Job, session.get(Investigation, run['id']).job_id)
                job.state, job.lease_owner = 'queued', None
                session.commit()
            interrupted.append(args[2]['url'])
        return result
    monkeypatch.setattr(decision_sources, 'safe_inspect', read)
    value = complete(client, service, root + '/investigations', run)
    assert trace['attempts'].count(interrupted[0]) == 1
    assert value['exploration']['research_scope']['reads']['interrupted'] == 1
    assert recovery(value)['failed_reads'] == 2 and recovery(value)['captures'] == 1


def test_revoked_recovery_evidence_hides_dependent_summary(signed, monkeypatch):
    client, service, identity, model = signed
    prepare(monkeypatch, service, model)
    root, run, _ = start(client)
    value = complete(client, service, root + '/investigations', run)
    source = next(s for s in value['exploration']['sources'] if s['url'].endswith('/identity'))
    exclude(service, identity, source['id'])
    now = client.get(root + '/investigations/' + run['id']).json()
    assert now['exploration']['research_scope']['status'] == 'evidence_changed'
    assert 'source_recovery' not in now['exploration']['research_scope']
