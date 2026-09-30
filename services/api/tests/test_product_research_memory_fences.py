"""Continuation privacy, durability and citation boundaries with fictional sources."""
import json
from copy import deepcopy

import pytest
from test_product_direction_assessment import setup as direction_setup
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_clarification import pause
from test_product_early_orientation import exclude
from test_product_episode_progress import extra_source
from test_product_exploration import start
from test_product_investigations import tick
from test_product_iterative_research import complete
from test_product_research_memory import setup
from test_product_selected_direction import choose
from test_product_typed_capture_history import observe

from helvetic_lens import product_research_memory as memory
from helvetic_lens.product_investigation_models import Investigation, InvestigationSource


def seeded(signed, monkeypatch, *, during=None):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model, during=during)
    root, parent, _ = start(client)
    _, _, child, _ = choose(client, service, root, parent)
    with service.db.session() as session:
        old = session.get(Investigation, parent['id'])
        extra = extra_source(session, old)
        extra_source(session, old, private=True)
        extra_id = extra.id
        session.commit()
    tick(service, child['id'])
    with service.db.session() as session:
        context = memory.context(session, session.get(Investigation, child['id']))
    assert context and 'PRIVATE CANARY' not in json.dumps(context)
    return trace, root, parent, child, extra_id


@pytest.mark.parametrize('change,when', [('text', 'before'), ('text', 'during'), ('text', 'after'),
    ('title', 'during'), ('rights', 'during'), ('exclude', 'after'), ('question_state', 'during'),
    ('missing', 'before'), ('missing', 'after'), ('contract', 'during'), ('context', 'during'), ('ancestry', 'after')])
def test_changed_memory_dependencies_fence_work_and_saved_output(signed, monkeypatch, change, when):
    client, service, identity, _ = signed
    armed = False
    def mutate():
        if change == 'exclude':
            exclude(service, identity, extra_id)
            return
        with service.db.session() as session:
            source = session.get(InvestigationSource, extra_id)
            if change == 'text':
                source.snapshot = {**source.snapshot, 'excerpts': [{'text': 'PRIVATE CHANGED HISTORICAL TEXT', 'passage': 'p1'}]}
            elif change == 'title':
                source.title = 'PRIVATE CHANGED HISTORICAL TITLE'
            elif change == 'rights':
                source.snapshot = {**source.snapshot, 'allow_discovery': False}
            elif change == 'question_state':
                run = session.get(Investigation, parent['id'])
                data = deepcopy(run.research_state)
                child_run = session.get(Investigation, child['id'])
                selected_id = memory.state(child_run)['context']['episodes'][0]['work_questions'][0]['id']
                question = next(q for q in data['questions'] if q['id'] == selected_id)
                question['status'] = 'evidence_found' if question['status'] == 'unresolved' else 'unresolved'
                run.research_state = data
            else:
                run = session.get(Investigation, child['id'])
                data = deepcopy(run.research_state)
                if change == 'missing':
                    data['exploration'].pop('research_memory')
                elif change == 'contract':
                    data['exploration'].pop('memory_contract')
                elif change == 'context':
                    data['exploration']['research_memory']['context']['selected_question'] = 'PRIVATE CHANGED QUESTION'
                else:
                    data['exploration']['previous']['early_fingerprint'] = 'changed'
                run.research_state = data
            session.commit()
    def during(data, phase):
        if armed and phase == 'ResearchPlan':
            mutate()
    trace, root, parent, child, extra_id = seeded(signed, monkeypatch, during=during)
    if when == 'before':
        mutate()
    if when == 'during':
        armed = True
    value = complete(client, service, root + '/investigations', child)
    if when == 'after':
        assert value['exploration']['status'] == 'ready'
        mutate()
        value = client.get(root + '/investigations/' + child['id']).json()
    else:
        assert value['status'] == 'paused', value['stop_reason']
        assert not any(q.startswith('Earlier reading gap ') for q in trace['queries'])
    assert value['exploration']['status'] == 'evidence_changed'
    assert 'PRIVATE CHANGED' not in json.dumps(value)
    assert not value['exploration'].get('briefing')
    if when == 'during':
        with service.db.session() as session:
            assert session.get(Investigation, child['id']).research_state['exploration']['memory_inputs_invalid']


@pytest.mark.parametrize('mode', ['free_text', 'legacy', 'legacy_parent'])
def test_untyped_and_legacy_history_is_not_invented(signed, monkeypatch, mode):
    client, service, _, model = signed
    direction_setup(monkeypatch, service, model)
    root, parent, _ = start(client)
    if mode == 'legacy_parent':
        with service.db.session() as session:
            run = session.get(Investigation, parent['id'])
            data = deepcopy(run.research_state)
            data['exploration'].pop('query_journal_contract')
            run.research_state = data
            session.commit()
    _, _, child, _ = choose(client, service, root, parent, free_text=mode == 'free_text')
    if mode == 'legacy':
        with service.db.session() as session:
            run = session.get(Investigation, child['id'])
            data = deepcopy(run.research_state)
            data['exploration'].pop('memory_contract')
            run.research_state = data
            session.commit()
    requests = observe(monkeypatch, model)
    result = complete(client, service, root + '/investigations', child)
    assert result['exploration']['status'] == 'ready'
    contexts = [r['input']['research_memory'] for r in requests if r['input'].get('research_memory')]
    if mode == 'legacy_parent':
        assert contexts and contexts[0]['episodes'][0]['sources']
        assert contexts[0]['episodes'][0]['query_history_status'] == 'unknown'
        assert contexts[0]['episodes'][0]['searches'] == contexts[0]['episodes'][0]['work_questions'] == []
    else:
        assert not contexts


def test_pause_resume_preserves_seeded_memory_and_one_plan(signed, monkeypatch):
    client, service, _, _ = signed
    trace, root, _, child, _ = seeded(signed, monkeypatch)
    with service.db.session() as session:
        before = deepcopy(memory.state(session.get(Investigation, child['id'])))
    stopped = pause(client, root, child)
    tick(service, child['id'])
    assert not trace['memory_requests']
    url = root + '/investigations/' + child['id']
    assert post(client, url + '/control', {'action': 'resume', 'expected_revision': stopped['revision']}).status_code == 200
    value = complete(client, service, root + '/investigations', child)
    assert value['exploration']['status'] == 'ready'
    assert sum(r['phase'] == 'ResearchPlan' for r in trace['memory_requests']) == 1
    with service.db.session() as session:
        assert memory.state(session.get(Investigation, child['id'])) == before


def test_historical_segment_cannot_be_used_as_current_finding(signed, monkeypatch):
    client, service, _, model = signed
    setup(monkeypatch, service, model)
    root, parent, _ = start(client)
    _, _, child, _ = choose(client, service, root, parent)
    base = model.complete
    async def bad_citation(system, user, **kwargs):
        data = json.loads(user)
        value = json.loads(await base(system, user, **kwargs))
        if kwargs['response_schema']['title'] == 'Briefing' and data.get('research_memory'):
            value['findings'][0]['source_id'] = data['research_memory']['episodes'][0]['sources'][0]['historical_source_id']
        return json.dumps(value)
    monkeypatch.setattr(model, 'complete', bad_citation)
    value = complete(client, service, root + '/investigations', child)
    assert value['exploration']['status'] == 'unavailable'
    assert not value['exploration'].get('briefing')


def test_limits_are_pinned_and_unknown_content_is_not_silently_complete(signed, monkeypatch):
    client, service, _, model = signed
    direction_setup(monkeypatch, service, model)
    root, parent, _ = start(client)
    _, _, child, _ = choose(client, service, root, parent)
    original = memory.LIMITS
    monkeypatch.setattr(memory, 'LIMITS', {**original, 'searches': 1, 'questions': 1, 'sources': 1, 'segments': 1, 'characters': 20})
    tick(service, child['id'])
    monkeypatch.setattr(memory, 'LIMITS', original)
    requests = observe(monkeypatch, model)
    value = complete(client, service, root + '/investigations', child)
    assert value['exploration']['status'] == 'ready'
    context = requests[0]['input']['research_memory']
    assert context['scope']['truncated'] and context['scope']['sources'] == context['scope']['searches'] == 1
    segment = context['episodes'][0]['sources'][0]['segments'][0]
    assert len(segment['text']) == 20 and segment['truncated']
    assert all(r['input']['research_memory'] == context for r in requests)


@pytest.mark.parametrize('bounded', [False, True])
def test_mixed_saved_check_uses_earlier_work_without_changing_its_query(signed, monkeypatch, bounded):
    from test_product_answer_next_check import setup as next_setup
    from test_product_saved_check import command, url
    client, service, _, model = signed
    trace = next_setup(monkeypatch, service, model)
    root, parent, _ = start(client)
    _, _, child, _ = choose(client, service, root, parent)
    value = complete(client, service, root + '/investigations', child)
    query = trace['choices'][-1]['query']
    if bounded:
        monkeypatch.setattr(memory, 'LIMITS', {**memory.LIMITS, 'episodes': 1})
    requests = observe(monkeypatch, model)
    response = post(client, url(root, value), command(value))
    assert response.status_code == 202, response.text
    grandchild = response.json()
    before = len(trace['queries'])
    final = complete(client, service, root + '/investigations', grandchild)
    assert final['exploration']['status'] == 'ready'
    assert trace['queries'][before] == query
    assert all(r['phase'] != 'ResearchPlan' for r in requests)
    context = requests[0]['input']['research_memory']
    assert [e['investigation_id'] for e in context['episodes']] == ([child['id']] if bounded else [child['id'], parent['id']])
    assert context['scope']['truncated'] is bounded
    assert 'PRIVATE CANARY' not in json.dumps(requests)
    with service.db.session() as session:
        run = session.get(Investigation, child['id'])
        data = deepcopy(run.research_state)
        data['exploration']['research_memory']['context']['selected_question'] = 'Changed earlier retained meaning'
        run.research_state = data
        session.commit()
    assert client.get(root + '/investigations/' + grandchild['id']).json()['exploration']['status'] == 'evidence_changed'
