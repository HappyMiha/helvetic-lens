"""Saved reading survives refinement without becoming a new answer or model input."""
import json
from copy import deepcopy

import pytest
from sqlalchemy import select
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_orientation import until
from test_product_exploration import QUESTION, adapters, start
from test_product_iterative_research import complete
from test_product_question_dossier import setup
from test_product_research_refinement import command

from helvetic_lens.product_exploration import projection
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from helvetic_lens.product_investigations import payload


@pytest.mark.parametrize('product', ['legal', 'pharma'])
def test_saved_answer_survives_refinement_failure_and_reload_with_current_rights(signed, monkeypatch, product):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, first, _ = start(client, product)
    initial = complete(client, service, root + '/investigations', first)
    answer = initial['exploration']['briefing']['assessment']
    reply = post(client, root + '/investigations/' + first['id'] + '/exploration/reply', command(initial))
    assert reply.status_code == 202, reply.text
    child = reply.json()
    assert 'retained_research' not in child['exploration']  # Only the authenticated reader opts in.
    path = root + '/investigations/' + child['id']
    queued = client.get(path).json()
    retained = queued['exploration']['retained_research']
    assert queued['status'] == 'queued' and queued['exploration']['briefing'] is None
    assert retained['investigation_id'] == first['id'] and retained['question'] == QUESTION
    assert retained['exploration']['briefing']['assessment'] == answer
    assert retained['exploration']['sources'] == initial['exploration']['sources']
    assert not {'retained_research', 'next_check', 'continued_by', 'research_memory'} & retained['exploration'].keys()
    # The native bounded failure leaves this useful earlier reading intact.
    adapters(monkeypatch, service, model, unavailable=True)
    failed = complete(client, service, root + '/investigations', child)
    assert failed['exploration']['briefing'] is None
    assert failed['exploration']['retained_research'] == retained
    before_requests = len(trace['final_requests'])
    with service.db.session() as session:
        run = session.get(Investigation, child['id'])
        before = deepcopy(run.research_state), run.event_sequence, run.revision
        assert 'retained_research' not in payload(session, run)['exploration']
    assert client.get(path).json()['exploration']['retained_research'] == retained
    with service.db.session() as session:
        run = session.get(Investigation, child['id'])
        assert (run.research_state, run.event_sequence, run.revision) == before
    assert len(trace['final_requests']) == before_requests
    # A further correction with no useful successor output still finds the last answer.
    response = post(client, path + '/exploration/reply', command(failed))
    assert response.status_code == 202, response.text
    next_path = root + '/investigations/' + response.json()['id']
    assert client.get(next_path).json()['exploration']['retained_research'] == retained
    with service.db.session() as session:
        source = session.get(InvestigationSource, initial['sources'][0]['id'])
        source.snapshot = {**source.snapshot, 'allow_discovery': False}
        session.commit()
    changed = client.get(next_path).json()['exploration']
    assert changed['status'] == 'evidence_changed' and not changed.get('retained_research')
    client.cookies.clear()
    assert client.get(next_path).status_code == 401


def test_early_finding_is_kept_without_inventing_a_finished_answer(signed, monkeypatch):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    root, first, _ = start(client)
    early = until(client, service, root, first)
    assert early['exploration']['briefing'] is None
    response = post(client, root + '/investigations/' + first['id'] + '/exploration/reply', command(early))
    assert response.status_code == 202, response.text
    current = client.get(root + '/investigations/' + response.json()['id']).json()['exploration']
    saved = current['retained_research']
    assert saved['question'] == QUESTION and saved['exploration']['briefing'] is None
    assert saved['exploration']['orientation'] == early['exploration']['orientation']
    assert current['briefing'] is None
    # A fresh question outside this explicit ancestry must not borrow an answer.
    other_root, other, _ = start(client)
    assert not client.get(other_root + '/investigations/' + other['id']).json()['exploration'].get('retained_research')


@pytest.mark.parametrize('product,withdrawal', [('legal', 'permission'), ('pharma', 'revision')])
def test_full_typed_answer_is_retained_without_private_drafts_or_new_authority(signed, monkeypatch, product, withdrawal):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    base = model.complete

    async def respond(system, user, **kwargs):
        value = json.loads(await base(system, user, **kwargs))
        if kwargs['response_schema']['title'] == 'Briefing':
            data = json.loads(user)
            points = [{'statement': source['excerpts'][0]['text'], 'evidence': [{
                'source_id': source['id'], 'quote': source['excerpts'][0]['text'],
                'locator': source['excerpts'][0]['passage'], 'role': 'support'}]} for source in data['sources']]
            value['mission_checkpoint'] = {'answer': {'status': 'partial', 'points': points,
                'limitations': ['The fictional records do not reconcile the reported amounts.']},
                'action': 'finish', 'reason': 'The available originals were compared.', 'next_checks': []}
            value['findings'] = value['findings'][:1]
        return json.dumps(value)

    monkeypatch.setattr(model, 'complete', respond)
    root, first, _ = start(client, product)
    initial = complete(client, service, root + '/investigations', first)
    mission = initial['exploration']['mission']
    assert len(mission['answer']['points']) > len(initial['exploration']['briefing']['findings'])
    reply = post(client, root + '/investigations/' + first['id'] + '/exploration/reply', command(initial))
    assert reply.status_code == 202, reply.text
    child = reply.json()
    path = root + '/investigations/' + child['id']
    assert 'retained_research' not in child['exploration']
    queued = client.get(path).json()
    retained = queued['exploration']['retained_research']
    assert queued['status'] == 'queued' and queued['exploration']['mission']['answer'] is None
    assert retained['investigation_id'] == first['id']
    assert retained['exploration']['mission'] == mission
    # A later unfinished round can clear a legacy briefing while leaving a
    # checked checkpoint. Only the normal public mission projection is retained.
    with service.db.session() as session:
        parent = session.get(Investigation, first['id'])
        state = deepcopy(parent.research_state)
        state['exploration']['briefing'] = None
        state['mission']['last_continuation'] = {'draft': 'PRIVATE UNCHECKED ANSWER'}
        parent.research_state = state
        branch = session.scalar(select(InvestigationBranch).where(InvestigationBranch.investigation_id == first['id']))
        branch.checkpoint = {**branch.checkpoint, 'synthesis_checkpoint': {
            'raw': 'PRIVATE UNCHECKED ANSWER', 'parts': {'deferred_points': ['PRIVATE UNCHECKED ANSWER']}}}
        session.commit()
    preserved = client.get(path).json()['exploration']['retained_research']
    assert preserved['exploration']['briefing'] is None
    assert preserved['exploration']['mission'] == mission
    encoded = json.dumps(preserved)
    assert 'PRIVATE UNCHECKED ANSWER' not in encoded
    assert not {'last_continuation', 'input_fingerprint', 'source_dependencies'} & preserved['exploration']['mission'].keys()
    assert all('source_dependencies' not in c and 'input_fingerprint' not in c
        for c in preserved['exploration']['mission']['checkpoints'])
    adapters(monkeypatch, service, model, unavailable=True)
    failed = complete(client, service, root + '/investigations', child)
    assert failed['status'] == 'failed'
    assert failed['exploration']['mission']['answer'] is None
    assert failed['exploration']['retained_research'] == preserved
    with service.db.session() as session:
        current = session.get(Investigation, child['id'])
        assert 'retained_research' not in payload(session, current)['exploration']
        evidence = mission['answer']['points'][0]['evidence'][0]
        source = session.get(InvestigationSource, evidence['source_id'])
        if withdrawal == 'permission':
            source.snapshot = {**source.snapshot, 'allow_discovery': False}
        else:
            source.sha256 = 'f' * 64
        session.commit()
    response = client.get(path)
    # This continuation recalled the parent's original: the existing origin ACL
    # withdraws the entire child reader before any retained projection is added.
    assert response.status_code == 404, response.text
    assert 'retained_research' not in response.text and 'PRIVATE UNCHECKED ANSWER' not in response.text
    with service.db.session() as session:
        parent = session.get(Investigation, first['id'])
        assert projection(session, parent)['mission']['answer'] is None
