"""Print the actual saved answer through current dossier and evidence access."""
import json
from copy import deepcopy
from html import escape

import pytest
from bs4 import BeautifulSoup
from sqlalchemy import select
from test_auth import _register
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_exploration import QUESTION, adapters, start
from test_product_iterative_research import GRANT, RECIPIENT, complete
from test_product_research_refinement import REFINEMENT, command

from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from helvetic_lens.product_models import ResearchThread

STATEMENT = 'The fictional <script>grant</script> is reported differently by the two sources.'
GAP = 'The sources do not explain the difference <pending review>.'
PRIVATE = 'PRIVATE UNCHECKED SYNTHESIS MUST NOT BE PRINTED'


def prepare(signed, monkeypatch, product='legal'):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    base = model.complete

    async def respond(system, user, **kwargs):
        value = json.loads(await base(system, user, **kwargs))
        if kwargs['response_schema']['title'] == 'Briefing':
            data = json.loads(user)
            def ref(text, role):
                source = next(s for s in data['sources'] if s['excerpts'][0]['text'] == text)
                return {'source_id': source['id'], 'quote': text, 'locator': 'p1', 'role': role}
            value['mission_checkpoint'] = {'answer': {'status': 'conflicting', 'points': [
                {'statement': STATEMENT, 'evidence': [ref(GRANT, 'support'), ref(RECIPIENT, 'counterevidence')]},
                {'statement': 'The foundation reported this amount.', 'evidence': [ref(GRANT, 'context')]}],
                'limitations': [GAP]}, 'action': 'finish', 'reason': 'Available original records disagree.', 'next_checks': []}
        return json.dumps(value)

    monkeypatch.setattr(model, 'complete', respond)
    root, first, _ = start(client, product)
    value = complete(client, service, root + '/investigations', first)
    assert value['status'] == 'completed', value['stop_reason']
    assert value['exploration']['mission']['answer']['points'][0]['statement'] == STATEMENT
    return root, value, trace


@pytest.mark.parametrize('product', ['legal', 'pharma'])
def test_prints_modern_answer_exact_passages_conflicts_gaps_without_legacy_threads(signed, monkeypatch, product):
    client, service, _, _ = signed
    root, value, trace = prepare(signed, monkeypatch, product)
    with service.db.session() as session:
        assert session.scalar(select(ResearchThread)) is None
        run = session.get(Investigation, value['id'])
        before = deepcopy(run.research_state), run.revision, run.event_sequence
    observed = deepcopy(trace)
    response = client.get(root + '/brief')
    assert response.status_code == 200, response.text
    soup = BeautifulSoup(response.text, 'html.parser')
    section = soup.select_one('.research-reading')
    assert section and QUESTION in section.text
    assert 'Where the evidence conflicts' in section.text and STATEMENT in section.text
    assert GAP in section.text and 'What we still do not know' in section.text
    refs = value['exploration']['mission']['answer']['points']
    expected = [ref['quote'] for point in refs for ref in point['evidence']]
    assert sorted(q.text for q in section.select('blockquote')) == sorted(expected)
    assert {p.text for p in section.select('.research-citation > p')} >= {'p1'}
    urls = {s['id']: s['url'] for s in value['exploration']['sources']}
    assert {link['href'] for link in section.select('a')} == {urls[ref['source_id']] for point in refs for ref in point['evidence']}
    assert all(role in section.text for role in ['Supporting passage', 'Counterevidence', 'Context'])
    assert not soup.select('script') and escape(STATEMENT) in response.text
    assert response.text.index('Research answer') < response.text.index('Dossier context')
    assert 'no-store' in response.headers['cache-control']
    assert "default-src 'none'" in response.headers['content-security-policy']
    assert trace == observed  # Printing does not search, read sources or call a model.
    with service.db.session() as session:
        run = session.get(Investigation, value['id'])
        assert (run.research_state, run.revision, run.event_sequence) == before
    exported = client.get(root + '/export').json()
    assert exported['investigations'][0]['exploration']['mission']['answer'] == value['exploration']['mission']['answer']
    foreign = root.replace('/' + product + '/', '/pharma/' if product == 'legal' else '/legal/')
    assert client.get(foreign + '/brief').status_code == 404
    assert _register(client, 'another-owner@example.ch').status_code == 201
    assert client.get(root + '/brief').status_code == 404
    client.cookies.clear()
    assert client.get(root + '/brief').status_code == 401


@pytest.mark.parametrize('withdrawal', ['permission', 'revision', 'quote'])
def test_changed_evidence_hides_answer_without_falling_back_to_raw_history(signed, monkeypatch, withdrawal):
    client, service, _, _ = signed
    root, value, _ = prepare(signed, monkeypatch)
    ref = value['exploration']['mission']['answer']['points'][0]['evidence'][0]
    with service.db.session() as session:
        source = session.get(InvestigationSource, ref['source_id'])
        if withdrawal == 'permission':
            source.snapshot = {**source.snapshot, 'allow_discovery': False}
        elif withdrawal == 'revision':
            source.sha256 = 'f' * 64
        else:
            source.snapshot = {**source.snapshot, 'excerpts': [{'passage': 'p1', 'text': 'Replaced original passage.'}]}
        session.commit()
    response = client.get(root + '/brief')
    assert response.status_code == 200
    assert 'supporting evidence has changed' in response.text
    assert escape(STATEMENT) not in response.text and escape(GAP) not in response.text
    assert GRANT not in response.text and RECIPIENT not in response.text


@pytest.mark.parametrize('product', ['legal', 'pharma'])
def test_new_episode_prints_earlier_answer_under_its_original_question(signed, monkeypatch, product):
    client, service, _, _ = signed
    root, value, _ = prepare(signed, monkeypatch, product)
    response = post(client, root + '/investigations/' + value['id'] + '/exploration/reply', command(value))
    assert response.status_code == 202, response.text
    child_id = response.json()['id']
    printed = BeautifulSoup(client.get(root + '/brief').text, 'html.parser')
    current = printed.select_one('.research-reading')
    earlier = current.select_one('.retained-answer')
    assert 'Research queued' in current.text and REFINEMENT in current.text
    assert QUESTION in earlier.text and REFINEMENT not in earlier.text and STATEMENT in earlier.text
    assert 'belongs to the earlier question' in earlier.text
    with service.db.session() as session:
        child = session.get(Investigation, child_id)
        child.status = 'failed'
        session.commit()
    assert 'Latest attempt did not finish' in client.get(root + '/brief').text
    # A withdrawn original cannot be printed through the retained-reading path.
    with service.db.session() as session:
        ref = value['exploration']['mission']['answer']['points'][0]['evidence'][0]
        source = session.get(InvestigationSource, ref['source_id'])
        source.snapshot = {**source.snapshot, 'allow_discovery': False}
        session.commit()
    withheld = client.get(root + '/brief')
    assert withheld.status_code == 200 and escape(STATEMENT) not in withheld.text
    assert 'Earlier saved research' not in withheld.text


@pytest.mark.parametrize('stop', ['answer_unavailable', 'review_unavailable'])
def test_saved_checkpoint_keeps_failure_qualification_and_hides_private_drafts(signed, monkeypatch, stop):
    client, service, _, _ = signed
    root, value, _ = prepare(signed, monkeypatch)
    with service.db.session() as session:
        run = session.get(Investigation, value['id'])
        state = deepcopy(run.research_state)
        state['mission']['stop'] = stop
        state['mission']['last_continuation'] = {'draft': PRIVATE}
        if stop == 'review_unavailable':
            state['mission']['verification'] = {'status': 'partial', 'basis': 'Remaining verification is pending.'}
        run.research_state = state
        branch = session.scalar(select(InvestigationBranch).where(InvestigationBranch.investigation_id == run.id))
        branch.checkpoint = {**branch.checkpoint, 'synthesis_checkpoint': {'raw': PRIVATE}}
        session.commit()
    response = client.get(root + '/brief')
    assert escape(STATEMENT) in response.text and PRIVATE not in response.text
    assert ('Last saved answer' if stop == 'answer_unavailable' else 'Some checks are still pending') in response.text


def test_queued_research_is_not_reported_as_a_finished_answer(signed):
    client, _, _, _ = signed
    root, _, _ = start(client)
    response = client.get(root + '/brief')
    assert response.status_code == 200 and 'Research queued' in response.text
    assert 'No new answer has been saved' in response.text
    assert 'Earlier saved research' not in response.text


def test_preliminary_analogy_keeps_its_qualification(signed, monkeypatch):
    client, service, _, _ = signed
    root, value, _ = prepare(signed, monkeypatch)
    with service.db.session() as session:
        run = session.get(Investigation, value['id'])
        state = deepcopy(run.research_state)
        state.pop('mission')
        state['exploration']['briefing'].pop('assessment', None)
        state['exploration']['briefing']['findings'][0]['basis'] = 'analogy'
        run.research_state = state
        session.commit()
    response = client.get(root + '/brief')
    assert response.status_code == 200
    assert 'AI · analogy, not a direct match' in response.text
    assert 'Saved preliminary findings' in response.text
