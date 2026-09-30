"""Complete fictional continuation journeys; not live legal/pharma acceptance."""
import json
from copy import deepcopy

import pytest
from test_product_direction_assessment import setup as direction_setup
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_exploration import QUESTION, start
from test_product_iterative_research import complete
from test_product_selected_direction import choose

from helvetic_lens import product_research_memory as memory
from helvetic_lens.product_investigation_models import Investigation


def setup(monkeypatch, service, model, *, repeat=False, during=None):
    trace = direction_setup(monkeypatch, service, model)
    base = model.complete
    trace['memory_requests'] = []
    async def response(system, user, **kwargs):
        data = json.loads(user)
        value = json.loads(await base(system, user, **kwargs))
        if data.get('research_memory'):
            assert memory.SYSTEM in system
            trace['memory_requests'].append({'phase': kwargs['response_schema']['title'], 'input': deepcopy(data)})
            if kwargs['response_schema']['title'] == 'ResearchPlan':
                context = data['research_memory']
                assert context['episodes'][0]['sources'] and context['episodes'][0]['searches']
                for n, branch in enumerate(value['branches']):
                    branch['query'] = (context['episodes'][0]['searches'][0]['query'] if repeat and n == 0
                        else 'Earlier reading gap ' + branch['query'])
                    branch['purpose'] = ('Recheck the earlier query against the clarified recipient question.' if repeat and n == 0
                        else 'Investigate the recipient-side gap in the earlier captured account.')
            if during:
                during(data, kwargs['response_schema']['title'])
        return json.dumps(value)
    monkeypatch.setattr(model, 'complete', response)
    return trace


@pytest.mark.parametrize('product,repeat', [('legal', True), ('pharma', False)])
def test_clarified_research_uses_actual_history_and_reads_current_evidence(signed, monkeypatch, product, repeat):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model, repeat=repeat)
    root, parent, _ = start(client, product)
    early, direction, child, body = choose(client, service, root, parent)
    old_queries = list(trace['queries'])
    old_source_ids = {s['id'] for s in early['sources']}
    result = complete(client, service, root + '/investigations', child)
    assert result['exploration']['status'] == 'ready', result['stop_reason']
    requests = trace['memory_requests']
    assert requests and requests[0]['phase'] == 'ResearchPlan'
    context = requests[0]['input']['research_memory']
    assert context['contract'] == memory.CONTRACT and context['selected_question'] == direction['question']
    assert context['episodes'][0]['question'] == QUESTION
    assert {q['query'] for q in context['episodes'][0]['searches']} == set(old_queries)
    assert context['episodes'][0]['work_questions']
    assert {s['historical_source_id'] for s in context['episodes'][0]['sources']} == old_source_ids
    assert all(x['input']['research_memory'] == context for x in requests)
    assert {'ResearchPlan', 'ResearchExtraction', 'Briefing'}.issubset({x['phase'] for x in requests})
    next_query = trace['queries'][len(old_queries)]
    assert next_query == context['episodes'][0]['searches'][0]['query'] if repeat else next_query.startswith('Earlier reading gap ')
    assert result['question'] == direction['question']
    assert old_source_ids.isdisjoint({s['id'] for s in result['sources']})
    assessment = result['exploration']['briefing']['assessment']
    current = {s['id'] for s in result['sources']}
    assert all(e['source_id'] in current for point in assessment['points'] for e in point['evidence'])
    assert assessment['limitations']
    assert 'research_memory' not in json.dumps(result) and 'memory_contract' not in json.dumps(result)
    assert post(client, root + '/investigations/' + parent['id'] + '/exploration/reply', body).json()['id'] == child['id']
    with service.db.session() as session:
        saved = session.get(Investigation, child['id'])
        before = deepcopy(saved.research_state), saved.revision, saved.event_sequence
    assert client.get(root + '/investigations/' + child['id']).json()['exploration']['briefing'] == result['exploration']['briefing']
    with service.db.session() as session:
        saved = session.get(Investigation, child['id'])
        assert (saved.research_state, saved.revision, saved.event_sequence) == before
    assert not client.get(root + '/web-research').json()['policy']['enabled']
    assert all(result['research']['used'].get(k, 0) <= v for k, v in result['research']['limits'].items())
