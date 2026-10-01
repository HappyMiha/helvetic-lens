"""Saved reading survives refinement without becoming a new answer or model input."""
from copy import deepcopy

import pytest
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_orientation import until
from test_product_exploration import QUESTION, adapters, start
from test_product_iterative_research import complete
from test_product_question_dossier import setup
from test_product_research_refinement import command

from helvetic_lens.product_investigation_models import Investigation, InvestigationSource
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
