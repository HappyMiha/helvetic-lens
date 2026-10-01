"""A neutral question, natural refinement, readable answer and useful next work."""
import json
from copy import deepcopy

import pytest
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_exploration import QUESTION, start
from test_product_investigations import tick
from test_product_iterative_research import GRANT, RECIPIENT, complete
from test_product_research_memory import setup as memory_setup
from test_product_research_refinement import REFINEMENT, command

from helvetic_lens import product_direction_assessment as assessment
from helvetic_lens.product_exploration_followups import saved_context
from helvetic_lens.product_investigation_models import Investigation, InvestigationSource


def setup(monkeypatch, service, model, *, invalid=False):
    trace = memory_setup(monkeypatch, service, model)
    base = model.complete

    async def response(system, user, **kwargs):
        data = json.loads(user)
        result = json.loads(await base(system, user, **kwargs))
        if kwargs['response_schema']['title'] == 'Reflection' and result.get('assessment'):
            source = data['sources'][0]
            result['assessment']['further_check'] = {
                'source_id': source['id'], 'quote': source['excerpts'][0]['text'], 'locator': 'p1',
                'query': 'River Trust independent grant accounts ' + result['assessment']['question_id'],
                'purpose': 'Reconcile the grant with the recipient account in an independent record.'}
        if data.get('direction_assessment_target'):
            answer = result['direction_assessment']
            by_text = {s['excerpts'][0]['text']: s for s in data['sources']}
            if GRANT in by_text and RECIPIENT in by_text:
                answer.update(status='conflicting', points=[{
                    'statement': text, 'evidence': [{'source_id': by_text[text]['id'],
                        'quote': text, 'locator': 'p1', 'role': role}]}
                    for text, role in [(GRANT, 'support'), (RECIPIENT, 'counterevidence')]])
            answer['limitations'] = ['The two reported grant amounts have not been reconciled.']
            options = [c for c in data['next_check_candidates']['items'] if c['current_check']]
            if options:
                chosen = options[-1]
                result['question_renewals'] = []
                result['next_check_choice'] = {'question_id': chosen['question_id'],
                    'query': chosen['current_check']['query'], 'limitation_index': 0}
            if invalid:
                answer['points'][0]['evidence'][0]['quote'] = 'INVENTED ANSWER CANARY'
        return json.dumps(result)

    monkeypatch.setattr(model, 'complete', response)
    return trace


@pytest.mark.parametrize('product', ['legal', 'pharma'])
def test_question_to_refined_dossier_and_explicit_next_check(signed, monkeypatch, product):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, first, _ = start(client, product)
    initial = complete(client, service, root + '/investigations', first)
    assert initial['exploration']['status'] == 'ready', initial['stop_reason']
    initial_answer = initial['exploration']['briefing']['assessment']
    assert initial_answer['question'] == QUESTION
    assert initial_answer['contract'] == assessment.QUESTION_CONTRACT
    assert 'selection' not in initial_answer and 'selected_from_investigation_id' not in initial_answer
    assert initial_answer['status'] == 'conflicting'
    before = list(trace['queries'])
    body = command(initial)
    url = root + '/investigations/' + first['id'] + '/exploration/reply'
    response = post(client, url, body)
    assert response.status_code == 202, response.text
    child = response.json()
    assert post(client, url, body).json()['id'] == child['id']
    refined = complete(client, service, root + '/investigations', child)
    assert refined['exploration']['status'] == 'ready', refined['stop_reason']
    answer = refined['exploration']['briefing']['assessment']
    assert answer['question'] == REFINEMENT and answer['status'] == 'conflicting'
    assert answer['contract'] == assessment.QUESTION_CONTRACT
    assert refined['exploration']['selected_direction'] is None
    memory = trace['memory_requests'][0]['input']['research_memory']
    assert memory['selected_question'] == REFINEMENT and memory['episodes'][0]['question'] == QUESTION
    assert {s['query'] for s in memory['episodes'][0]['searches']} == set(before)
    assert trace['queries'][len(before)].startswith('Earlier reading gap ')
    current_sources = {s['id'] for s in refined['sources']}
    assert current_sources.isdisjoint({s['id'] for s in initial['sources']})
    assert all(e['source_id'] in current_sources for point in answer['points'] for e in point['evidence'])
    assert {e['role'] for p in answer['points'] for e in p['evidence']} == {'support', 'counterevidence'}
    assert len(trace['final_requests']) == 2  # Same final call, no answer-only inference.
    assert client.get(root + '/investigations/' + first['id']).json()['exploration']['briefing']['assessment'] == initial_answer
    check = refined['exploration']['next_check']
    assert check['answer_link']['question'] == REFINEMENT
    assert check['answer_link']['limitation'] == answer['limitations'][0]
    with service.db.session() as session:
        query = saved_context(session, session.get(Investigation, child['id']), check['question_id'])['query']
    assert query not in trace['queries']
    follow = {**command(refined), 'question': check['question'], 'follow_up_id': check['question_id']}
    response = post(client, root + '/investigations/' + child['id'] + '/exploration/reply', follow)
    assert response.status_code == 202, response.text
    successor = response.json()
    for _ in range(8):
        tick(service, successor['id'])
        if query in trace['queries']:
            break
    assert query in trace['queries']
    assert client.get(root + '/web-research').json()['policy']['enabled'] is False
    with service.db.session() as session:
        source = session.get(InvestigationSource, refined['sources'][0]['id'])
        source.snapshot = {**source.snapshot, 'allow_discovery': False}
        session.commit()
    changed = client.get(root + '/investigations/' + child['id']).json()['exploration']
    assert changed['status'] == 'evidence_changed' and changed['briefing'] is None


def test_invalid_answer_retains_cited_findings_without_extra_work(signed, monkeypatch):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model, invalid=True)
    root, first, _ = start(client)
    final = complete(client, service, root + '/investigations', first)
    brief = final['exploration']['briefing']
    assert final['exploration']['status'] == 'ready' and brief['findings']
    assert 'assessment' not in brief and brief['selected_direction_assessment'] == {'status': 'unavailable'}
    assert len(trace['final_requests']) == 1 and 'INVENTED ANSWER CANARY' not in json.dumps(final)


def test_legacy_initial_episode_stays_readable_without_reinterpretation(signed, monkeypatch):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, first, _ = start(client)
    with service.db.session() as session:
        run = session.get(Investigation, first['id'])
        state = deepcopy(run.research_state)
        state['exploration']['direction_assessment_contract'] = assessment.CONTRACT
        run.research_state = state
        session.commit()
    final = complete(client, service, root + '/investigations', first)
    assert final['exploration']['status'] == 'ready' and final['exploration']['briefing']['findings']
    assert 'assessment' not in final['exploration']['briefing'] and not trace['final_requests']
