"""Consequential early choices through the actual worker; fictional public evidence."""
import json
import time
from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude, until
from test_product_exploration import QUESTION, start
from test_product_informed_research import setup as informed_setup
from test_product_investigations import tick
from test_product_iterative_research import complete

from helvetic_lens.product_investigation_models import (
    ClaimEvidence,
    DossierClaim,
    Investigation,
    InvestigationBranch,
    InvestigationSource,
    WebResearchPolicy,
)

SELECTED = "Investigate recipient disclosure rather than assume the foundation's identity."


def setup(monkeypatch, service, model, mode=None):
    trace = informed_setup(monkeypatch, service, model)
    base = model.complete

    async def response(system, user, **kwargs):
        data = json.loads(user)
        result = json.loads(await base(system, user, **kwargs))
        title = kwargs['response_schema']['title']
        if title == 'EarlyOrientation':
            assert 'No generic domain checklist' in system
            assert 0 < kwargs['budget'].deadline - time.monotonic() <= 20
            source = data['sources'][0]
            cite = {'source_id': source['id'], 'quote': source['excerpts'][0]['text'], 'locator': 'p1'}
            result.update(clarification='Would you like to verify identity or follow the recipient records?',
                directions=[{**cite, 'question': SELECTED,
                    'why': 'Follow the recipient records and check the reported transaction.'},
                    {**cite, 'question': 'Investigate which foundation matches the submitted name.',
                    'why': 'Check entity identity before following the financial records.'}])
            if mode == 'quote':
                result['directions'][0]['quote'] = 'Invented unsupported passage'
            elif mode == 'duplicate':
                result['directions'][1]['question'] = result['directions'][0]['question']
            elif mode == 'single':
                result['directions'] = result['directions'][:1]
            elif mode == 'no_question':
                result['clarification'] = ''
            elif mode in {'absent', 'claim_without_fork'}:
                result.pop('clarification')
                result.pop('directions')
        if title == 'ResearchExtraction' and mode in {'claim', 'claim_without_fork'} and not result['claims']:
            quote = data['source']['excerpts'][0]['text']
            result['claims'] = [{'statement': 'Alpine Foundation has registry identity CH-100.',
                'existing_claim_id': None, 'relation': 'SUPPORTS', 'quote': quote, 'locator': 'p1'}]
        if title == 'ResearchPlan' and data['question'] == SELECTED:
            for branch in result['branches']:
                branch['query'] = 'focused recipient disclosure ' + branch['query']
        return json.dumps(result)

    monkeypatch.setattr(model, 'complete', response)
    return trace


def pause(client, root, run):
    url = root + '/investigations/' + run['id']
    current = client.get(url).json()
    paused = post(client, url + '/control', {'action': 'pause', 'expected_revision': current['revision']})
    assert paused.status_code == 200, paused.text
    return paused.json()


def command(value):
    return {'request_key': str(uuid4()), 'expected_revision': value['exploration']['revision'],
        'orientation_revision': value['exploration']['orientation']['revision'],
        'direction': 0, 'question': SELECTED, 'public_query_confirmed': True}


@pytest.mark.parametrize('product', ['legal', 'pharma'])
def test_early_choice_changes_real_planning_and_search_with_exact_replay(signed, monkeypatch, product):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client, product)
    early = until(client, service, root, run)
    url = root + '/investigations/' + run['id']
    assert early['status'] == 'running' and early['exploration']['briefing'] is None
    assert post(client, url + '/exploration/reply', command(early)).status_code == 409
    paused = pause(client, root, run)
    body = command(paused)
    assert body['expected_revision'] > body['orientation_revision']
    for changes in ({'expected_revision': early['exploration']['revision']},
                    {'orientation_revision': body['orientation_revision'] + 1},
                    {'question': 'An unshown query with a different purpose.'}):
        assert post(client, url + '/exploration/reply', {**body, **changes}).status_code == 409
    response = post(client, url + '/exploration/reply', body)
    assert response.status_code == 202, response.text
    successor = response.json()
    assert post(client, url + '/exploration/reply', body).json()['id'] == successor['id']
    assert post(client, url + '/exploration/reply', {**body, 'direction': 1}).status_code == 409
    assert post(client, url + '/exploration/reply', {**body, 'request_key': str(uuid4())}).status_code == 409
    before = len(trace['queries'])
    final = complete(client, service, root + '/investigations', successor)
    assert final['exploration']['briefing'], final['stop_reason']
    plan = [m['input'] for m in trace['models'] if m['phase'] == 'ResearchPlan'][-1]
    assert plan['question'] == SELECTED and 'previous_public_briefing' not in plan
    assert trace['queries'][before].startswith('focused recipient disclosure')
    old = client.get(url).json()
    assert old['question'] == QUESTION and old['status'] == 'paused'
    assert old['exploration']['orientation'] == early['exploration']['orientation']
    assert len(old['sources']) == len(early['sources'])
    assert 'orientation_context' not in json.dumps(old)
    assert client.get(root + '/investigations').json()['total'] == 2
    with service.db.session() as session:
        assert session.scalar(select(WebResearchPolicy)) is None
    client.cookies.clear()
    assert client.get(url).status_code == 401
    assert client.post(url + '/exploration/reply', json=body).status_code in {401, 403}


def test_silence_keeps_one_bounded_episode_and_final_brief_replaces_early_choice(signed, monkeypatch):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client)
    early = until(client, service, root, run)
    final = complete(client, service, root + '/investigations', run)
    assert len(trace['orientations']) == 1 and len(trace['briefings']) == 1
    assert len(trace['queries']) == 3 and len(trace['reads']) == 3
    assert final['exploration']['briefing'] and final['status'] == 'completed'
    assert final['exploration']['orientation'] == early['exploration']['orientation']
    assert final['research']['used']['model_calls'] <= final['research']['limits']['model_calls']
    body = command(early)
    body['expected_revision'] = final['exploration']['revision']
    assert post(client, root + '/investigations/' + run['id'] + '/exploration/reply', body).status_code == 409
    assert client.get(root + '/investigations').json()['total'] == 1
    assert not client.get(root + '/web-research').json()['policy']['enabled']


@pytest.mark.parametrize('mode', ['quote', 'duplicate', 'single', 'no_question', 'absent'])
def test_invalid_or_absent_fork_never_fabricates_choices_or_stops_research(signed, monkeypatch, mode):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model, mode)
    root, run, _ = start(client)
    final = complete(client, service, root + '/investigations', run)
    assert final['exploration']['briefing'] and len(trace['orientations']) == 1
    early = final['exploration']['orientation']
    if mode == 'absent':
        assert early['status'] == 'ready' and early['briefing']['directions'] == []
    else:
        assert early['status'] == 'unavailable' and early['briefing'] is None
    assert 'Invented unsupported' not in json.dumps(final)


@pytest.mark.parametrize('change', ['excluded', 'hash', 'unquoted_metadata', 'claim', 'read_context', 'question', 'receipt'])
def test_changed_full_early_context_hides_choices_and_rejects_selection(signed, monkeypatch, change):
    client, service, identity, model = signed
    setup(monkeypatch, service, model, mode=change)
    root, run, _ = start(client)
    early = until(client, service, root, run)
    paused = pause(client, root, run)
    body = command(paused)
    sid = early['exploration']['orientation']['briefing']['source_dependencies'][1]['source_id']
    if change == 'excluded':
        exclude(service, identity, sid)
    else:
        with service.db.session() as session:
            saved = session.get(Investigation, run['id'])
            if change in {'hash', 'unquoted_metadata'}:
                source = session.get(InvestigationSource, sid)
                if change == 'hash':
                    source.sha256 = 'e' * 64
                else:
                    source.title = 'Different unquoted source identity'
            elif change == 'claim':
                claims = saved.research_state['exploration']['orientation_context']['claims']
                assert claims
                session.get(DossierClaim, claims[0]['id']).statement = 'Changed public claim context'
            elif change == 'read_context':
                branch = next(b for b in session.scalars(select(InvestigationBranch).where(
                    InvestigationBranch.investigation_id == run['id']))
                    if b.checkpoint.get('read_relevance', {}).get('assessments'))
                state = deepcopy(branch.checkpoint)
                state['read_relevance']['assessments'][0]['reason'] = 'Changed read assessment context'
                branch.checkpoint = state
            elif change == 'question':
                saved.question = 'A different original question'
            else:
                state = deepcopy(saved.research_state)
                state['exploration'].pop('orientation_context')
                saved.research_state = state
            session.commit()
    url = root + '/investigations/' + run['id']
    current = client.get(url).json()
    assert current['exploration']['orientation']['briefing'] is None
    assert current['exploration']['orientation']['status'] == 'evidence_changed'
    assert post(client, url + '/exploration/reply', body).status_code == 409
    assert client.get(root + '/investigations').json()['total'] == 1


@pytest.mark.parametrize('change', ['excluded', 'binding'])
def test_chosen_early_evidence_is_rechecked_before_descendant_work(signed, monkeypatch, change):
    client, service, identity, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client)
    early = until(client, service, root, run)
    paused = pause(client, root, run)
    url = root + '/investigations/' + run['id']
    body = command(paused)
    response = post(client, url + '/exploration/reply', body)
    assert response.status_code == 202, response.text
    new = response.json()
    if change == 'excluded':
        exclude(service, identity, early['exploration']['sources'][0]['id'])
    else:
        with service.db.session() as session:
            parent = session.get(Investigation, run['id'])
            state = deepcopy(parent.research_state)
            state['exploration']['orientation']['briefing']['directions'][0]['why'] = 'A changed rationale'
            parent.research_state = state
            session.commit()
    before = len(trace['queries']), len(trace['models'])
    tick(service, new['id'])
    current = client.get(root + '/investigations/' + new['id']).json()
    assert current['status'] == 'paused'
    assert current['exploration']['status'] == 'evidence_changed'
    assert (len(trace['queries']), len(trace['models'])) == before
    assert post(client, url + '/exploration/reply', body).json()['id'] == new['id']
    assert client.get(root + '/investigations').json()['total'] == 2


def test_reply_shape_does_not_allow_mixed_or_unpinned_early_choice(signed):
    client, _, _, _ = signed
    for fields in ({'orientation_revision': 0, 'direction': 0},
                   {'orientation_revision': 2},
                   {'orientation_revision': True, 'direction': 0},
                   {'orientation_revision': 2, 'direction': 0, 'follow_up_id': str(uuid4())}):
        response = post(client, '/api/products/legal/dossiers/missing/investigations/missing/exploration/reply',
            {'request_key': str(uuid4()), 'expected_revision': 2,
                'question': SELECTED, 'public_query_confirmed': True, **fields})
        assert response.status_code == 422


@pytest.mark.parametrize('fork', [False, True])
def test_private_backing_invalidates_all_new_early_output_even_without_a_fork(signed, monkeypatch, fork):
    client, service, _, model = signed
    setup(monkeypatch, service, model, mode='claim' if fork else 'claim_without_fork')
    root, run, _ = start(client)
    early = until(client, service, root, run)
    assert bool(early['exploration']['orientation']['briefing']['directions']) is fork
    pause(client, root, run)
    with service.db.session() as session:
        saved = session.get(Investigation, run['id'])
        claims = saved.research_state['exploration']['orientation_context']['claims']
        assert claims
        source = InvestigationSource(dossier_id=saved.dossier_id, organization_id=saved.organization_id,
            investigation_id=saved.id, source_key='private-context', kind='uploaded_file', title='PRIVATE SOURCE',
            url='', sha256='f' * 64, snapshot={'excerpts': [{'passage': 'p1', 'text': 'PRIVATE PASSAGE'}]})
        session.add(source)
        session.flush()
        session.add(ClaimEvidence(dossier_id=saved.dossier_id, organization_id=saved.organization_id,
            investigation_id=saved.id, claim_id=claims[0]['id'], source_id=source.id,
            relation='SUPPORTS', quote='PRIVATE PASSAGE', locator='p1'))
        session.commit()
    current = client.get(root + '/investigations/' + run['id']).json()['exploration']
    assert current['orientation']['status'] == 'evidence_changed'
    assert current['orientation']['briefing'] is None
    assert 'PRIVATE' not in json.dumps(current)


def test_changed_ancestor_during_selected_planning_discards_the_model_result(signed, monkeypatch):
    client, service, identity, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client)
    early = until(client, service, root, run)
    paused = pause(client, root, run)
    new = post(client, root + '/investigations/' + run['id'] + '/exploration/reply', command(paused))
    assert new.status_code == 202, new.text
    base = model.complete
    async def response(system, user, **kwargs):
        result = await base(system, user, **kwargs)
        if kwargs['response_schema']['title'] == 'ResearchPlan' and json.loads(user)['question'] == SELECTED:
            exclude(service, identity, early['exploration']['sources'][0]['id'])
        return result
    monkeypatch.setattr(model, 'complete', response)
    before = len(trace['queries'])
    final = complete(client, service, root + '/investigations', new.json())
    assert final['status'] == 'paused' and final['exploration']['status'] == 'evidence_changed'
    assert len(trace['queries']) == before
    assert not final['exploration']['briefing']


@pytest.mark.parametrize('changed', ['title', 'excerpts'])
def test_early_source_identity_and_unquoted_passages_are_rechecked_after_inference(signed, monkeypatch, changed):
    client, service, _, model = signed
    setup(monkeypatch, service, model)
    base = model.complete
    async def response(system, user, **kwargs):
        result = await base(system, user, **kwargs)
        if kwargs['response_schema']['title'] == 'EarlyOrientation':
            data = json.loads(user)
            with service.db.session() as session:
                source = session.get(InvestigationSource, data['sources'][1]['id'])
                if changed == 'title':
                    source.title = 'Changed unquoted identity while inference ran'
                else:
                    source.snapshot = {**source.snapshot, 'excerpts': [*source.snapshot['excerpts'],
                        {'passage': 'p2', 'text': 'New material not supplied to this inference.'}]}
                session.commit()
        return result
    monkeypatch.setattr(model, 'complete', response)
    root, run, _ = start(client)
    final = complete(client, service, root + '/investigations', run)
    assert final['exploration']['orientation']['status'] == 'unavailable'
    assert final['exploration']['orientation']['briefing'] is None
    assert final['exploration']['briefing']
