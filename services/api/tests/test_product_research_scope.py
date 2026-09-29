"""Durable scripted public research; these fixtures do not measure semantic quality."""
import json
from copy import deepcopy
from uuid import uuid4

import pytest
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude
from test_product_episode_progress import extra_source
from test_product_exploration import adapters, start
from test_product_investigations import tick
from test_product_iterative_research import complete

from helvetic_lens import decision_search, decision_sources
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from helvetic_lens.product_investigations import rows, scope


def observed(value):
    return value['exploration']['research_scope']


@pytest.mark.parametrize('product', ['legal', 'pharma'])
def test_useful_brief_retains_failed_reads_reader_limits_and_actual_final_input(signed, monkeypatch, product):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    reader = decision_sources.safe_inspect
    search = decision_search.federated_retrieve

    async def read(*args, **kwargs):
        if args[2]['url'].endswith('/identity'):
            return {'status': 'unavailable', 'error': 'PRIVATE PROVIDER ERROR'}
        result = await reader(*args, **kwargs)
        result['text_truncated'] = args[2]['url'].endswith('/grant')
        return result

    async def retrieve(*args):
        result = await search(*args)
        result['items'].extend([{'id': str(i), 'url': f'https://example.org/extra-{i}',
            'title': 'motorway unrelated', 'summary': ''} for i in range(6)])
        return result

    monkeypatch.setattr(decision_sources, 'safe_inspect', read)
    monkeypatch.setattr(decision_search, 'federated_retrieve', retrieve)
    root, run, _ = start(client, product)
    value = complete(client, service, root + '/investigations', run)
    actual = observed(value)
    assert value['exploration']['briefing'] and actual['status'] == 'ready'
    assert actual['reads']['unavailable'] == 1
    assert actual['reads']['completed'] == actual['material']['sources'] == 2
    assert actual['material']['passages'] == 2
    assert actual['material']['truncated_sources'] == 1
    assert actual['material']['unknown_reader_scope'] == 0
    assert actual['candidates']['not_evaluated'] > 0
    assert actual['searches']['completed'] == len(trace['queries']) == 3
    assert actual['questions']['open'] >= 1
    request = trace['briefings'][-1]['research_scope']
    assert request['reads'] == actual['reads'] and request['candidates'] == actual['candidates']
    with service.db.session() as session:
        saved = session.get(Investigation, run['id'])
        assert saved.research_state['used']['search_requests'] > actual['searches']['completed']
        assert saved.research_state['exploration']['briefing']['research_scope_at_briefing'] == request
        before = deepcopy(saved.research_state)
    assert client.get(root + '/investigations/' + run['id']).json() == value
    with service.db.session() as session:
        assert session.get(Investigation, run['id']).research_state == before
    assert 'PRIVATE PROVIDER ERROR' not in json.dumps(actual)
    assert client.get(root + '/web-research').json()['policy']['enabled'] is False


@pytest.mark.parametrize('failure', ['read', 'search'])
def test_unavailable_search_or_read_never_means_no_information_exists(signed, monkeypatch, failure):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)

    async def fail(*args, **kwargs):
        raise RuntimeError('PRIVATE FAILURE CANARY')

    monkeypatch.setattr(decision_sources if failure == 'read' else decision_search,
        'safe_inspect' if failure == 'read' else 'federated_retrieve', fail)
    root, run, _ = start(client)
    value = complete(client, service, root + '/investigations', run)
    actual = observed(value)
    assert actual['status'] == 'ready' and actual['material']['sources'] == 0
    assert actual['reads' if failure == 'read' else 'searches']['unavailable'] > 0
    assert actual['questions']['open'] > 0 and value['exploration']['briefing'] is None
    assert not trace.get('briefings') and 'PRIVATE FAILURE CANARY' not in json.dumps(actual)


@pytest.mark.parametrize('legacy', [False, True])
def test_old_scope_unknown_and_unrelated_private_work_excluded(signed, monkeypatch, legacy):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    root, run, _ = start(client)
    with service.db.session() as session:
        saved = session.get(Investigation, run['id'])
        if legacy:
            state = deepcopy(saved.research_state)
            state['exploration'].pop('scope_contract')
            saved.research_state = state
        extra_source(session, saved, private=True)
        session.add(InvestigationBranch(**scope(saved), query='PRIVATE BRANCH CANARY', reason='Private fixture work', status='completed',
            checkpoint={'steps': [{'phase': 'read', 'status': 'completed'}]}))
        session.commit()
    value = complete(client, service, root + '/investigations', run)
    actual = observed(value)
    assert actual['status'] == ('unknown' if legacy else 'ready')
    if legacy:
        assert set(actual) == {'contract', 'status'}
        assert trace['briefings'][-1]['research_scope'] == actual
    else:
        assert actual['reads']['completed'] == len(trace['reads']) == 3
        assert actual['material']['sources'] == actual['material']['unknown_reader_scope'] == 3
    assert 'PRIVATE' not in json.dumps(actual) and 'PRIVATE' not in json.dumps(trace['briefings'])


@pytest.mark.parametrize('when', ['after', 'during', 'hash'])
def test_revoked_inputs_hide_scope_without_retaining_counts(signed, monkeypatch, when):
    client, service, identity, model = signed
    adapters(monkeypatch, service, model)
    base = model.complete

    async def respond(system, user, **kwargs):
        raw = await base(system, user, **kwargs)
        data = json.loads(user)
        if when == 'during' and kwargs['response_schema']['title'] == 'Briefing':
            exclude(service, identity, data['sources'][0]['id'])
        return raw

    monkeypatch.setattr(model, 'complete', respond)
    root, run, _ = start(client)
    value = complete(client, service, root + '/investigations', run)
    if when == 'after':
        exclude(service, identity, value['exploration']['sources'][0]['id'])
    elif when == 'hash':
        with service.db.session() as session:
            source = session.get(InvestigationSource, value['exploration']['sources'][0]['id'])
            source.sha256 = 'b' * 64
            session.commit()
    value = client.get(root + '/investigations/' + run['id']).json()
    assert observed(value) == {'contract': 'observed-research-scope/v1', 'status': 'evidence_changed'}
    assert value['exploration']['briefing'] is None


def test_pause_resume_and_budget_reservations_are_not_search_attempts(signed, monkeypatch):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    root, run, _ = start(client, 'legal')
    tick(service, run['id'])
    url = root + '/investigations/' + run['id']
    value = client.get(url).json()
    paused = post(client, url + '/control', {'action': 'pause', 'expected_revision': value['revision']}).json()
    actual = observed(paused)
    assert actual['activity'] == 'paused' and sum(actual['searches'].values()) == 0
    assert not trace['queries']
    resumed = post(client, url + '/control', {'action': 'resume', 'expected_revision': paused['revision']})
    assert resumed.status_code == 200
    value = complete(client, service, root + '/investigations', run)
    assert observed(value)['activity'] == 'completed'
    assert observed(value)['searches']['completed'] == len(trace['queries']) == 3


def test_running_receipt_becomes_interrupted_without_repeating_the_search(signed, monkeypatch):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    root, run, _ = start(client)
    tick(service, run['id'])
    tick(service, run['id'])
    with service.db.session() as session:
        saved = session.get(Investigation, run['id'])
        branch = next(b for b in rows(session, InvestigationBranch, saved) if b.checkpoint.get('question_id'))
        token = str(uuid4())
        branch.checkpoint = {**branch.checkpoint, 'inflight': token,
            'steps': [{'id': token, 'phase': 'search', 'status': 'running'}]}
        session.commit()
    url = root + '/investigations/' + run['id']
    assert observed(client.get(url).json())['searches']['running'] == 1
    value = complete(client, service, root + '/investigations', run)
    assert observed(value)['searches']['interrupted'] == 1
    assert observed(value)['searches']['running'] == 0
    assert observed(value)['searches']['completed'] == len(trace['queries'])


def test_budget_limited_questions_are_preserved_beside_a_useful_brief(signed, monkeypatch):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    root, run, _ = start(client)
    with service.db.session() as session:
        saved = session.get(Investigation, run['id'])
        state = deepcopy(saved.research_state)
        state['limits']['branches'] = 2
        state['limits']['source_fetches'] = 1
        saved.research_state = state
        session.commit()
    value = complete(client, service, root + '/investigations', run)
    actual = observed(value)
    assert value['exploration']['briefing'] and value['status'] == 'paused'
    assert 'source_fetches' in actual['budget_stops']
    assert actual['candidates']['selected_not_read'] > 0
    assert actual['questions']['open'] > 0
    assert actual['reads']['completed'] == 1


@pytest.mark.parametrize('outcome', ['partial', 'all_unavailable', 'unrecorded'])
def test_index_outcomes_survive_a_completed_federated_step(signed, monkeypatch, outcome):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    base = decision_search.federated_retrieve

    async def search(*args):
        result = await base(*args)
        if outcome == 'unrecorded':
            result.pop('lanes')
        else:
            result['lanes'] = [{'status': 'unavailable', 'name': 'PRIVATE INDEX CANARY',
                'query': 'PRIVATE QUERY CANARY'}]
            if outcome == 'partial':
                result['lanes'].append({'status': 'complete'})
            else:
                result['items'] = []
        return result

    monkeypatch.setattr(decision_search, 'federated_retrieve', search)
    root, run, _ = start(client)
    value = complete(client, service, root + '/investigations', run)
    actual = observed(value)
    completed = actual['searches']['completed']
    assert completed == len(trace['queries']) > 0
    assert actual['indexes']['unknown_searches'] == (completed if outcome == 'unrecorded' else 0)
    assert actual['indexes']['unavailable'] == (0 if outcome == 'unrecorded' else completed)
    if outcome == 'all_unavailable':
        assert value['exploration']['briefing'] is None and actual['material']['sources'] == 0
    else:
        assert trace['briefings'][-1]['research_scope']['indexes'] == actual['indexes']
    assert 'PRIVATE' not in json.dumps(actual)
