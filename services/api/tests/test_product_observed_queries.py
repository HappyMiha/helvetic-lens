"""Real durable dispatches using fictional providers; not live research accuracy."""
import json
from copy import deepcopy

import pytest
from test_product_dossiers import signed as signed
from test_product_exploration import QUESTION, start
from test_product_iterative_research import complete
from test_product_query_recovery import ALTERNATIVE, ORIGINAL, setup

from helvetic_lens import product_observed_queries as queries
from helvetic_lens.product_investigation_models import Investigation


def journal(value):
    return value["exploration"]["research_scope"]["observed_queries"]


@pytest.mark.parametrize("product,mode", [("legal", "empty"), ("pharma", "unrelated")])
def test_original_and_alternative_calls_match_durable_journal_and_final_request(signed, monkeypatch, product, mode):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model, mode)
    root, run, _ = start(client, product)
    value = complete(client, service, root + "/investigations", run)
    assert value["exploration"]["status"] == "ready", value["stop_reason"]
    result = journal(value)
    assert result["status"] == "ready" and result["contract"] == queries.CONTRACT
    assert result["scope"] == {"investigation_id": run["id"], "limit": 24,
        "search_steps": len(trace["queries"]), "unrecorded_steps": 0, "truncated": False}
    assert sorted(v["query"] for v in result["items"]) == sorted(trace["queries"])
    assert {ORIGINAL, ALTERNATIVE}.issubset({v["query"] for v in result["items"]})
    assert all(v["outcome"] == "completed" and v["retrieval"]["status"] == "complete" for v in result["items"])
    assert all(v["started_at"] and v["finished_at"] for v in result["items"])
    assert trace["briefings"][-1]["research_scope"]["observed_queries"] == result
    assert value["question"] == QUESTION
    assert all(key not in json.dumps(value) for key in ("query_observation", "observed_query_context", "query_journal_contract", "query_inputs_invalid"))
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        before = deepcopy(saved.research_state), saved.revision, saved.event_sequence
    assert journal(client.get(root + "/investigations/" + run["id"]).json()) == result
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        assert (saved.research_state, saved.revision, saved.event_sequence) == before
    assert not client.get(root + "/web-research").json()["policy"]["enabled"]
    client.cookies.clear()
    assert client.get(root + "/investigations/" + run["id"]).status_code == 401


def saved_journal(service, run):
    with service.db.session() as session:
        return queries.projection(session, session.get(Investigation, run['id']))


def alter_receipt(service, run, change):
    from helvetic_lens.product_investigation_models import InvestigationBranch
    from helvetic_lens.product_investigations import rows
    with service.db.session() as session:
        saved = session.get(Investigation, run['id'])
        branch = next(b for b in rows(session, InvestigationBranch, saved)
            if any(s.get('query_observation') for s in b.checkpoint.get('steps', [])))
        state = deepcopy(branch.checkpoint)
        step = next(s for s in state['steps'] if s.get('query_observation'))
        change(saved, state, step)
        branch.checkpoint = state
        session.commit()


@pytest.mark.parametrize('mode,status', [('partial', 'partial'), ('unknown', 'unknown'),
    ('outage', None), ('all_empty', 'complete')])
def test_provider_outcomes_are_distinct_and_errors_private(signed, monkeypatch, mode, status):
    client, service, _, model = signed
    setup(monkeypatch, service, model, mode)
    root, run, _ = start(client)
    value = complete(client, service, root + '/investigations', run)
    result = saved_journal(service, run)
    original = next(v for v in result['items'] if v['query'] == ORIGINAL)
    assert original['outcome'] == ('unavailable' if mode == 'outage' else 'completed')
    if status:
        assert original['retrieval']['status'] == status
        assert original['retrieval']['candidate_appearances'] == 0
    else:
        assert original['retrieval'] is None
    assert 'PRIVATE PROVIDER CANARY' not in json.dumps(value)
    assert 'PRIVATE PROVIDER CANARY' not in json.dumps(result)


def test_proposal_pause_resume_records_only_actual_dispatch(signed, monkeypatch):
    from test_product_dossiers import post
    from test_product_investigations import tick
    from test_product_query_recovery import until_reformulation
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client)
    until_reformulation(service, run)
    tick(service, run['id'])  # Propose an alternative without dispatching it.
    before = saved_journal(service, run)
    assert trace['reformulations'] and ALTERNATIVE not in trace['queries']
    assert all(v['query'] != ALTERNATIVE for v in before['items'])
    url = root + '/investigations/' + run['id']
    value = client.get(url).json()
    paused = post(client, url + '/control', {'action': 'pause', 'expected_revision': value['revision']})
    assert paused.status_code == 200
    tick(service, run['id'])
    assert saved_journal(service, run) == before
    assert post(client, url + '/control', {'action': 'resume', 'expected_revision': paused.json()['revision']}).status_code == 200
    value = complete(client, service, root + '/investigations', run)
    assert sum(v['query'] == ALTERNATIVE for v in journal(value)['items']) == trace['queries'].count(ALTERNATIVE) == 1


def test_lost_lease_keeps_dispatch_unconfirmed_then_interrupted_without_replay(signed, monkeypatch):
    from test_product_investigations import tick

    from helvetic_lens import decision_search
    from helvetic_lens.models import Job
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client)
    base = decision_search.federated_retrieve
    observations = []
    async def interrupted(*args):
        result = await base(*args)
        if args[1] == ORIGINAL:
            observations.append(saved_journal(service, run))
            with service.db.session() as session:
                job = session.get(Job, session.get(Investigation, run['id']).job_id)
                job.state, job.lease_owner = 'queued', None
                session.commit()
        return result
    monkeypatch.setattr(decision_search, 'federated_retrieve', interrupted)
    for _ in range(10):
        tick(service, run['id'])
        if observations:
            break
    pending = next(v for v in observations[0]['items'] if v['query'] == ORIGINAL)
    assert pending['outcome'] == 'unconfirmed' and pending['retrieval'] is None and pending['finished_at'] is None
    assert saved_journal(service, run)['items'] == observations[0]['items']
    complete(client, service, root + '/investigations', run)
    ended = next(v for v in saved_journal(service, run)['items'] if v['query'] == ORIGINAL)
    assert ended['outcome'] == 'interrupted' and ended['retrieval'] is None
    assert trace['queries'].count(ORIGINAL) == 1


@pytest.mark.parametrize('mutation', ['wording', 'outcome', 'time', 'missing', 'question', 'contract', 'private_branch'])
def test_changed_query_dependencies_hide_completed_output(signed, monkeypatch, mutation):
    client, service, _, model = signed
    setup(monkeypatch, service, model)
    root, run, _ = start(client)
    value = complete(client, service, root + '/investigations', run)
    assert journal(value)['status'] == 'ready'
    def change(saved, state, step):
        if mutation == 'wording':
            step['query_observation']['query'] = 'PRIVATE CHANGED WORDING'
        elif mutation == 'outcome':
            step['query_observation']['retrieval']['candidate_appearances'] += 1
        elif mutation == 'time':
            step['finished_at'] = '2000-01-01T00:00:00+00:00'
        elif mutation == 'missing':
            step.pop('query_observation')
        elif mutation == 'private_branch':
            state['file'] = {'id': 'private-fixture'}
        else:
            data = deepcopy(saved.research_state)
            if mutation == 'question':
                next(q for q in data['questions'] if q['id'] == state['question_id'])['question'] = 'PRIVATE CHANGED QUESTION'
            else:
                data['exploration'].pop('query_journal_contract')
            saved.research_state = data
    alter_receipt(service, run, change)
    value = client.get(root + '/investigations/' + run['id']).json()
    assert value['exploration']['status'] == 'evidence_changed'
    assert 'observed_queries' not in value['exploration']['research_scope']
    assert 'PRIVATE CHANGED' not in json.dumps(value['exploration'])


def test_changed_journal_during_final_inference_is_discarded(signed, monkeypatch):
    client, service, _, model = signed
    setup(monkeypatch, service, model)
    root, run, _ = start(client)
    base = model.complete
    async def changed(system, user, **kwargs):
        result = await base(system, user, **kwargs)
        if kwargs['response_schema']['title'] == 'Briefing':
            alter_receipt(service, run, lambda saved, state, step: step['query_observation'].update(query='PRIVATE LATE CHANGE'))
        return result
    monkeypatch.setattr(model, 'complete', changed)
    value = complete(client, service, root + '/investigations', run)
    assert value['status'] == 'paused'
    assert value['exploration']['status'] == 'evidence_changed'
    assert 'briefing' not in value['exploration'] or not value['exploration']['briefing']
    with service.db.session() as session:
        assert session.get(Investigation, run['id']).research_state['exploration']['query_inputs_invalid']


def test_legacy_searches_remain_unknown_without_reconstruction(signed, monkeypatch):
    client, service, _, model = signed
    setup(monkeypatch, service, model)
    root, run, _ = start(client)
    with service.db.session() as session:
        saved = session.get(Investigation, run['id'])
        data = deepcopy(saved.research_state)
        data['exploration'].pop('query_journal_contract')
        saved.research_state = data
        session.commit()
    value = complete(client, service, root + '/investigations', run)
    assert journal(value) == {'contract': queries.CONTRACT, 'status': 'unknown'}


def test_revoked_origin_hides_exact_query_journal(signed, monkeypatch):
    from test_product_early_orientation import exclude
    client, service, identity, model = signed
    setup(monkeypatch, service, model)
    root, run, _ = start(client)
    value = complete(client, service, root + '/investigations', run)
    assert journal(value)['items']
    exclude(service, identity, value['exploration']['sources'][0]['id'])
    value = client.get(root + '/investigations/' + run['id']).json()
    assert value['exploration']['research_scope']['status'] == 'evidence_changed'
    assert 'observed_queries' not in value['exploration']['research_scope']


@pytest.mark.parametrize('mode', ['bounded', 'missing'])
def test_bounds_and_unrecorded_dispatch_are_explicit(signed, monkeypatch, mode):
    from test_product_query_recovery import until_reformulation
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    if mode == 'bounded':
        monkeypatch.setattr(queries, 'MAX_ITEMS', 2)
    root, run, _ = start(client)
    if mode == 'missing':
        until_reformulation(service, run)
        alter_receipt(service, run, lambda saved, state, step: step.pop('query_observation'))
    value = complete(client, service, root + '/investigations', run)
    result = journal(value)
    assert result['status'] == 'ready'
    assert result['scope']['search_steps'] == len(trace['queries'])
    if mode == 'bounded':
        assert result['scope']['limit'] == len(result['items']) == 2
        assert result['scope']['truncated']
    else:
        assert result['scope']['unrecorded_steps'] == 1
        assert len(result['items']) == len(trace['queries']) - 1
    assert trace['briefings'][-1]['research_scope']['observed_queries'] == result


def test_earlier_query_change_fences_a_typed_descendant(signed, monkeypatch):
    from test_product_investigations import tick
    from test_product_selected_direction import choose
    from test_product_selected_direction import setup as directions
    client, service, _, model = signed
    trace = directions(monkeypatch, service, model)
    root, parent, _ = start(client)
    _, _, child, _ = choose(client, service, root, parent)
    earlier = client.get(root + '/investigations/' + parent['id']).json()
    assert journal(earlier)['items']
    before = len(trace['queries']), len(trace['reads'])
    alter_receipt(service, parent, lambda saved, state, step: step['query_observation'].update(query='PRIVATE PARENT CHANGE'))
    tick(service, child['id'])
    value = client.get(root + '/investigations/' + child['id']).json()
    assert value['status'] == 'paused'
    assert value['exploration']['status'] == 'evidence_changed'
    assert (len(trace['queries']), len(trace['reads'])) == before
    assert 'PRIVATE PARENT CHANGE' not in json.dumps(value)
