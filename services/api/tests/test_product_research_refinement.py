"""Natural correction through the real worker and public fixtures; no live calls."""
from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_orientation import until
from test_product_exploration import QUESTION, adapters, start
from test_product_investigations import tick
from test_product_iterative_research import complete
from test_product_research_memory import setup

from helvetic_lens import product_exploration_api as api
from helvetic_lens import product_iterative_steps as steps
from helvetic_lens.config import DomainError
from helvetic_lens.models import Job
from helvetic_lens.product_investigation_models import Investigation, InvestigationSource, WebResearchPolicy

REFINEMENT = 'Trace the recipient side of this grant, using what you found.'


def command(value):
    return {'request_key': str(uuid4()), 'expected_revision': value['exploration']['revision'],
        'question': REFINEMENT, 'public_query_confirmed': True, 'continue_research': True}


@pytest.mark.parametrize('product', ['legal', 'pharma'])
def test_own_words_continue_active_research_with_memory_and_current_citations(signed, monkeypatch, product):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, parent, _ = start(client, product)
    early = until(client, service, root, parent)
    before = list(trace['queries'])
    body = command(early)
    url = root + '/investigations/' + parent['id'] + '/exploration/reply'
    response = post(client, url, body)
    assert response.status_code == 202, response.text
    child = response.json()
    assert post(client, url, body).json()['id'] == child['id']
    assert post(client, url, {**body, 'question': 'Another unrelated instruction.'}).status_code == 409
    with service.db.session() as session:
        old = session.get(Investigation, parent['id'])
        assert old.status == 'paused' and session.get(Job, old.job_id).cancel_requested
        assert old.question == QUESTION and old.research_state['exploration']['continued_by'] == child['id']
        assert len(session.scalars(select(Investigation)).all()) == 2
        assert session.scalar(select(WebResearchPolicy)) is None
    result = complete(client, service, root + '/investigations', child)
    assert result['exploration']['status'] == 'ready', result['stop_reason']
    memory = trace['memory_requests'][0]['input']['research_memory']
    assert memory['selected_question'] == REFINEMENT
    assert memory['episodes'][0]['question'] == QUESTION
    assert {s['query'] for s in memory['episodes'][0]['searches']} == set(before)
    assert memory['episodes'][0]['sources'] and memory['episodes'][0]['work_questions']
    assert trace['queries'][len(before)].startswith('Earlier reading gap ')
    old_ids = {s['id'] for s in early['sources']}
    new_ids = {s['id'] for s in result['sources']}
    assert new_ids and old_ids.isdisjoint(new_ids)
    assert all(f['source_id'] in new_ids for f in result['exploration']['briefing']['findings'])
    assert result['exploration']['selected_direction'] is None  # No invented AI rationale for user text.


def test_correction_before_first_work_uses_zero_revision_without_invented_history(signed, monkeypatch):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    root, parent, _ = start(client)
    body = command(client.get(root + '/investigations/' + parent['id']).json())
    assert body['expected_revision'] == 0
    url = root + '/investigations/' + parent['id'] + '/exploration/reply'
    assert post(client, url, {**body, 'continue_research': False}).status_code == 422
    response = post(client, url, body)
    assert response.status_code == 202, response.text
    child = response.json()
    tick(service, child['id'])
    with service.db.session() as session:
        memory = session.get(Investigation, child['id']).research_state['exploration']['research_memory']['context']
        assert memory['episodes'][0]['question'] == QUESTION
        assert memory['episodes'][0]['sources'] == [] and memory['episodes'][0]['searches'] == []


@pytest.mark.parametrize('failure', ['stale', 'invalid_direction', 'enqueue'])
def test_rejected_handoff_keeps_existing_research_running(signed, monkeypatch, failure):
    client, service, _, model = signed
    setup(monkeypatch, service, model)
    root, parent, _ = start(client)
    early = until(client, service, root, parent)
    body = command(early)
    if failure == 'stale':
        body['expected_revision'] += 1
    elif failure == 'invalid_direction':
        body.update(direction=0, orientation_revision=early['exploration']['orientation']['revision'])
    else:
        def unavailable(*args):
            raise DomainError('Queue unavailable', status=503)
        monkeypatch.setattr(api, 'enqueue', unavailable)
    response = post(client, root + '/investigations/' + parent['id'] + '/exploration/reply', body)
    assert response.status_code == (503 if failure == 'enqueue' else 409), response.text
    with service.db.session() as session:
        saved = session.get(Investigation, parent['id'])
        assert saved.status == 'running'
        assert not session.get(Job, saved.job_id).cancel_requested
        assert not saved.research_state['exploration'].get('continued_by')
        assert len(session.scalars(select(Investigation)).all()) == 1


def test_old_inflight_result_is_discarded_after_atomic_refinement(signed, monkeypatch):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    root, parent, _ = start(client)
    original = steps.execute
    successor = []

    async def change_while_reading(service, work, seconds):
        result = await original(service, work, seconds)
        if work['phase'] == 'read' and not successor:
            current = client.get(root + '/investigations/' + parent['id']).json()
            response = post(client, root + '/investigations/' + parent['id'] + '/exploration/reply', command(current))
            assert response.status_code == 202, response.text
            successor.append(response.json())
        return result

    monkeypatch.setattr(steps, 'execute', change_while_reading)
    stopped = complete(client, service, root + '/investigations', parent)
    assert stopped['status'] == 'paused' and successor
    assert stopped['sources'] == []  # The in-flight capture was never committed.
    result = complete(client, service, root + '/investigations', successor[0])
    assert result['exploration']['status'] == 'ready'


@pytest.mark.parametrize('change', ['source_rights', 'parent_question'])
def test_refined_memory_still_fences_changed_or_private_ancestry(signed, monkeypatch, change):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, parent, _ = start(client)
    early = until(client, service, root, parent)
    child = post(client, root + '/investigations/' + parent['id'] + '/exploration/reply', command(early)).json()
    tick(service, child['id'])
    with service.db.session() as session:
        if change == 'source_rights':
            source = session.get(InvestigationSource, early['sources'][0]['id'])
            source.snapshot = {**source.snapshot, 'allow_discovery': False}
        else:
            session.get(Investigation, parent['id']).question = 'A changed private intent.'
        session.commit()
    before = deepcopy(trace['queries'])
    tick(service, child['id'])
    result = client.get(root + '/investigations/' + child['id']).json()
    assert result['status'] == 'paused' and result['exploration']['status'] == 'evidence_changed'
    assert result['exploration']['briefing'] is None and trace['queries'] == before
