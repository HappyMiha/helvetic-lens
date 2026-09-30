"""Chosen meaning reaches the real planner; fictional retained public passages."""
import json
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_clarification import pause
from test_product_early_clarification import setup as early_setup
from test_product_early_orientation import until
from test_product_exploration import QUESTION, start
from test_product_investigations import tick
from test_product_iterative_research import complete

from helvetic_lens import product_early_clarification as clarification
from helvetic_lens.product_investigation_models import (
    ClaimEvidence,
    Investigation,
    InvestigationSource,
    WebResearchPolicy,
)


def setup(monkeypatch, service, model, *, claims=False):
    trace = early_setup(monkeypatch, service, model, mode='claim' if claims else None)
    base = model.complete
    trace['direction_requests'] = []

    async def response(system, user, **kwargs):
        data = json.loads(user)
        title = kwargs['response_schema']['title']
        result = json.loads(await base(system, user, **kwargs))
        if title == 'EarlyOrientation':
            source = data['sources'][1]
            result['directions'][1].update(source_id=source['id'],
                quote=source['excerpts'][0]['text'], locator='p1')
        if data.get('selected_direction'):
            assert title == 'ResearchPlan'
            assert clarification.CONTEXT_SYSTEM in system
            context = data['selected_direction']
            trace['direction_requests'].append(deepcopy(data))
            prefix = 'recipient context' if context['direction_index'] == 0 else 'identity context'
            for branch in result['branches']:
                branch['query'] = prefix + ' ' + branch['query']
        return json.dumps(result)

    monkeypatch.setattr(model, 'complete', response)
    return trace


def choose(client, service, root, run, *, index=0, free_text=False):
    early = until(client, service, root, run)
    paused = pause(client, root, run)
    direction = paused['exploration']['orientation']['briefing']['directions'][index]
    body = {'request_key': str(uuid4()), 'expected_revision': paused['exploration']['revision'],
        'question': direction['question'], 'public_query_confirmed': True}
    if not free_text:
        body.update(direction=index, orientation_revision=paused['exploration']['orientation']['revision'])
    response = post(client, root + '/investigations/' + run['id'] + '/exploration/reply', body)
    assert response.status_code == 202, response.text
    return early, direction, response.json(), body


def plan(client, service, root, child):
    # The first durable delivery seeds branches; the second executes planning.
    for _ in range(2):
        if client.get(root + '/investigations/' + child['id']).json()['status'] not in {'queued', 'running'}:
            break
        tick(service, child['id'])


@pytest.mark.parametrize('product', ['legal', 'pharma'])
@pytest.mark.parametrize('index', [0, 1])
def test_chosen_meaning_reaches_actual_plan_and_search_without_recapturing_context(signed, monkeypatch, product, index):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client, product)
    early, direction, child, body = choose(client, service, root, run, index=index)
    before = len(trace['queries']), len(trace['reads'])
    context = child['exploration']['selected_direction']
    assert context['contract'] == clarification.CONTEXT_CONTRACT
    assert context['status'] == 'ready' and context['direction_index'] == index
    assert context['original_question'] == QUESTION and context['question'] == direction['question']
    assert context['why'] == direction['why'] and context['quote'] == direction['quote']
    assert context['source']['id'] == direction['source_id']
    assert context['investigation_id'] == run['id']
    assert context['orientation_revision'] == early['exploration']['orientation']['revision']
    assert not child['sources'] and child['exploration']['continuation'] is None
    with service.db.session() as session:
        source = session.get(InvestigationSource, direction['source_id'])
        assert context['source']['sha256'] == source.sha256
        saved = session.get(Investigation, child['id'])
        unchanged = deepcopy(saved.research_state), saved.revision, saved.event_sequence
    for _ in range(2):
        assert client.get(root + '/investigations/' + child['id']).json()['exploration']['selected_direction'] == context
    with service.db.session() as session:
        saved = session.get(Investigation, child['id'])
        assert (saved.research_state, saved.revision, saved.event_sequence) == unchanged
    plan(client, service, root, child)
    assert len(trace['direction_requests']) == 1
    supplied = trace['direction_requests'][0]
    assert supplied['selected_direction'] == context and supplied['question'] == direction['question']
    assert 'previous_public_briefing' not in supplied
    assert not client.get(root + '/investigations/' + child['id']).json()['sources']
    final = complete(client, service, root + '/investigations', child)
    assert final['exploration']['briefing'], final['stop_reason']
    assert len(trace['direction_requests']) == 1
    assert trace['queries'][before[0]].startswith('recipient context' if index == 0 else 'identity context')
    assert len(trace['reads']) > before[1]
    assert all(source['id'] != context['source']['id'] for source in final['sources'])
    assert final['exploration']['selected_direction'] == context
    assert len([m for m in trace['models'] if m['phase'] == 'ResearchPlan']) == 2
    old = client.get(root + '/investigations/' + run['id']).json()
    assert old['question'] == QUESTION and old['exploration']['orientation'] == early['exploration']['orientation']
    assert post(client, root + '/investigations/' + run['id'] + '/exploration/reply', body).json()['id'] == child['id']
    assert all(final['research']['used'].get(k, 0) <= v for k, v in final['research']['limits'].items())
    assert all(key not in json.dumps(final) for key in ('orientation_context', 'context_fingerprint', 'direction_context_contract'))
    with service.db.session() as session:
        assert session.scalar(select(WebResearchPolicy)) is None


@pytest.mark.parametrize('mode', ['free_text', 'legacy'])
def test_no_invented_selection_context_for_free_text_or_existing_episodes(signed, monkeypatch, mode):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client)
    _, _, child, _ = choose(client, service, root, run, free_text=mode == 'free_text')
    if mode == 'legacy':
        with service.db.session() as session:
            saved = session.get(Investigation, child['id'])
            state = deepcopy(saved.research_state)
            state['exploration'].pop('direction_context_contract')
            saved.research_state = state
            session.commit()
    current = client.get(root + '/investigations/' + child['id']).json()
    assert current['exploration']['selected_direction'] is None
    plan(client, service, root, child)
    supplied = [m['input'] for m in trace['models'] if m['phase'] == 'ResearchPlan'][-1]
    assert supplied['question'] == child['question'] and 'selected_direction' not in supplied
    assert not trace['direction_requests']


def mutate(service, run, child, direction, change):
    with service.db.session() as session:
        parent = session.get(Investigation, run['id'])
        source = session.get(InvestigationSource, direction['source_id'])
        if change == 'rights':
            source.snapshot = {**source.snapshot, 'allow_discovery': False}
        elif change == 'unquoted':
            recorded = parent.research_state['exploration']['orientation_context']['sources']
            other = next(s for s in recorded if s['id'] != source.id)
            session.get(InvestigationSource, other['id']).title = 'Changed unquoted source identity'
        elif change == 'private_claim':
            claims = parent.research_state['exploration']['orientation_context']['claims']
            assert claims
            private = InvestigationSource(dossier_id=parent.dossier_id, organization_id=parent.organization_id,
                investigation_id=parent.id, source_key='private-backing', kind='uploaded_file',
                title='PRIVATE SOURCE', url='', sha256='a' * 64,
                snapshot={'excerpts': [{'passage': 'p1', 'text': 'PRIVATE CONTENT'}]})
            session.add(private)
            session.flush()
            session.add(ClaimEvidence(dossier_id=parent.dossier_id, organization_id=parent.organization_id,
                investigation_id=parent.id, claim_id=claims[0]['id'], source_id=private.id,
                relation='SUPPORTS', quote='PRIVATE CONTENT', locator='p1'))
        elif change == 'link':
            state = deepcopy(parent.research_state)
            state['exploration']['continued_by'] = str(uuid4())
            parent.research_state = state
        elif change == 'capture_time':
            source.created_at += timedelta(days=1)
        elif change == 'contract':
            saved = session.get(Investigation, child['id'])
            state = deepcopy(saved.research_state)
            state['exploration'].pop('direction_context_contract')
            saved.research_state = state
        else:
            raise AssertionError(change)
        session.commit()


@pytest.mark.parametrize('change', ['rights', 'unquoted', 'private_claim', 'link'])
@pytest.mark.parametrize('during', [False, True])
def test_current_selection_context_and_work_fail_closed_when_earlier_dependencies_change(signed, monkeypatch, change, during):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model, claims=change == 'private_claim')
    root, run, _ = start(client)
    _, direction, child, _ = choose(client, service, root, run)
    before = len(trace['models']), len(trace['queries'])
    if during:
        base = model.complete
        async def response(system, user, **kwargs):
            result = await base(system, user, **kwargs)
            if json.loads(user).get('selected_direction'):
                mutate(service, run, child, direction, change)
            return result
        monkeypatch.setattr(model, 'complete', response)
    else:
        mutate(service, run, child, direction, change)
        hidden = client.get(root + '/investigations/' + child['id']).json()['exploration']
        assert hidden['selected_direction'] == {'status': 'evidence_changed'}
        assert direction['why'] not in json.dumps(hidden) and 'PRIVATE' not in json.dumps(hidden)
    plan(client, service, root, child)
    current = client.get(root + '/investigations/' + child['id']).json()
    assert current['status'] == 'paused'
    assert current['exploration']['selected_direction'] == {'status': 'evidence_changed'}
    assert len(trace['queries']) == before[1]
    assert len(trace['models']) == before[0] + int(during)
    assert not current['sources'] and not current['exploration']['briefing']
    client.cookies.clear()
    assert client.get(root + '/investigations/' + child['id']).status_code == 401


@pytest.mark.parametrize('change', ['capture_time', 'contract'])
def test_every_supplied_planner_field_is_rechecked_after_inference(signed, monkeypatch, change):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client)
    _, direction, child, _ = choose(client, service, root, run)
    before = len(trace['queries'])
    base = model.complete
    async def response(system, user, **kwargs):
        result = await base(system, user, **kwargs)
        if json.loads(user).get('selected_direction'):
            mutate(service, run, child, direction, change)
        return result
    monkeypatch.setattr(model, 'complete', response)
    plan(client, service, root, child)
    current = client.get(root + '/investigations/' + child['id']).json()
    assert current['status'] == 'paused' and not current['research']['questions']
    assert len(trace['queries']) == before and not current['sources']


def test_later_typed_choice_keeps_its_own_context_and_checks_the_full_ancestry(signed, monkeypatch):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client)
    _, first, child, _ = choose(client, service, root, run, index=1)
    _, second, descendant, _ = choose(client, service, root, child)
    context = descendant['exploration']['selected_direction']
    assert context['original_question'] == child['question']
    assert context['question'] == second['question'] and context['investigation_id'] == child['id']
    assert context['source']['id'] == second['source_id']
    before = len(trace['models']), len(trace['queries'])
    mutate(service, run, child, first, 'rights')
    hidden = client.get(root + '/investigations/' + descendant['id']).json()['exploration']
    assert hidden['selected_direction'] == {'status': 'evidence_changed'}
    plan(client, service, root, descendant)
    assert client.get(root + '/investigations/' + descendant['id']).json()['status'] == 'paused'
    assert (len(trace['models']), len(trace['queries'])) == before
