"""Saved purpose through durable work; fictional sources, no live model research."""
import json
from copy import deepcopy

import pytest
from test_product_adaptive_orientation import adaptive
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude
from test_product_episode_progress import extra_source
from test_product_exploration import adapters, start
from test_product_investigations import tick
from test_product_iterative_research import complete
from test_product_research_activity import current, projected

from helvetic_lens import product_exploration, product_iterative_steps
from helvetic_lens.product_investigation_models import (
    ClaimEvidence,
    DossierClaim,
    Investigation,
    InvestigationBranch,
    InvestigationSource,
)
from helvetic_lens.product_investigations import scope


def question_for(session, run, work):
    saved = session.get(Investigation, run['id'])
    branch = session.get(InvestigationBranch, work['branch_id'])
    question = next((q for q in saved.research_state['questions']
        if q['id'] == branch.checkpoint.get('question_id')), None)
    return saved, question


def advance(service, run, observed):
    for _ in range(65):
        tick(service, run['id'])
        if observed:
            return
    raise AssertionError('Expected current question was not executed')


@pytest.mark.parametrize('product', ['legal', 'pharma'])
@pytest.mark.parametrize('reconsideration', [False, True])
def test_actual_initial_and_followup_purpose_reuses_saved_context_without_work(
    signed, monkeypatch, product, reconsideration,
):
    client, service, _, model = signed
    trace = (adaptive if reconsideration else adapters)(monkeypatch, service, model)
    root, run, _ = start(client, product)
    execute = product_iterative_steps.execute
    observed = []

    async def inspect(service, work, seconds):
        if work['phase'] == 'search':
            with service.db.session() as session:
                saved, q = question_for(session, run, work)
                before, event = deepcopy(saved.research_state), saved.event_sequence
                purpose = product_exploration.projection(session, saved)['current_activity']['purpose']
                assert purpose['text'] == q['purpose']
                assert purpose['contract'] == 'research-purpose/v1'
                if q['trigger']:
                    assert purpose['kind'] == 'source_follow_up'
                    assert purpose['trigger']['quote'] == q['trigger']['quote']
                    assert purpose['trigger']['locator'] == q['trigger']['locator']
                    source = session.get(InvestigationSource, q['trigger']['source_id'])
                    assert purpose['trigger']['source']['url'] == source.url
                    assert q['open_check_context']['claims'] is not None
                else:
                    assert purpose['kind'] == 'planned' and 'trigger' not in purpose
                assert saved.research_state == before and saved.event_sequence == event
            assert projected(service, run)['purpose'] == purpose
            if not observed:
                assert current(client, root, run)['purpose'] == purpose
            observed.append(purpose)
        return await execute(service, work, seconds)

    monkeypatch.setattr(product_iterative_steps, 'execute', inspect)
    final = complete(client, service, root + '/investigations', run)
    assert final['exploration']['briefing'], final['stop_reason']
    assert {p['kind'] for p in observed} == {'planned', 'source_follow_up'}
    assert len(trace['queries']) == (4 if reconsideration else 3)
    assert len(trace['reads']) == len(trace['queries'])
    assert 'purpose_fingerprint' not in json.dumps(final)
    assert 'purpose_contract' not in final['exploration']
    assert current(client, root, run) == {'contract': 'research-activity/v1', 'status': 'finished'}
    assert not client.get(root + '/web-research').json()['policy']['enabled']
    client.cookies.clear()
    assert client.get(root + '/investigations/' + run['id']).status_code == 401


@pytest.mark.parametrize('change', ['legacy', 'missing', 'empty', 'oversized', 'binding'])
def test_unverifiable_purpose_never_reconstructs_an_explanation(signed, monkeypatch, change):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    _, run, _ = start(client)
    execute = product_iterative_steps.execute
    observed = []

    async def inspect(service, work, seconds):
        if work['phase'] == 'search' and not observed:
            with service.db.session() as session:
                saved, q = question_for(session, run, work)
                state = deepcopy(saved.research_state)
                question = next(v for v in state['questions'] if v['id'] == q['id'])
                if change == 'legacy':
                    state['exploration'].pop('purpose_contract')
                elif change == 'missing':
                    question.pop('purpose')
                else:
                    question['purpose'] = {'empty': ' ', 'oversized': 'x' * 501,
                        'binding': 'PRIVATE CHANGED PURPOSE CANARY'}[change]
                saved.research_state = state
                session.commit()
            value = projected(service, run)
            assert value['status'] == 'working' and value['purpose'] is None
            assert 'PRIVATE' not in json.dumps(value)
            observed.append(value)
        return await execute(service, work, seconds)

    monkeypatch.setattr(product_iterative_steps, 'execute', inspect)
    advance(service, run, observed)


@pytest.mark.parametrize('change', [
    'rights', 'hash', 'unquoted', 'claim_text', 'claim_status', 'mixed_claim', 'trigger', 'missing_context',
])
def test_current_gap_purpose_withholds_changed_complete_context(signed, monkeypatch, change):
    client, service, identity, model = signed
    adapters(monkeypatch, service, model)
    _, run, _ = start(client)
    execute = product_iterative_steps.execute
    observed = []

    async def inspect(service, work, seconds):
        with service.db.session() as session:
            _, q = question_for(session, run, work)
            is_gap = q and q.get('trigger')
        if work['phase'] == 'search' and is_gap and not observed:
            assert projected(service, run)['purpose']['kind'] == 'source_follow_up'
            with service.db.session() as session:
                saved, q = question_for(session, run, work)
                state = deepcopy(saved.research_state)
                question = next(v for v in state['questions'] if v['id'] == q['id'])
                context = question['open_check_context']
                if change in {'rights', 'hash'}:
                    source = session.get(InvestigationSource, q['trigger']['source_id'])
                    if change == 'rights':
                        source.snapshot = {**source.snapshot, 'allow_discovery': False}
                    else:
                        source.sha256 = 'b' * 64
                elif change == 'unquoted':
                    unquoted = next(d['source_id'] for d in context['source_dependencies']
                        if d['source_id'] != q['trigger']['source_id'])
                elif change in {'claim_text', 'claim_status', 'mixed_claim'}:
                    claim = session.get(DossierClaim, context['claims'][0]['id'])
                    if change == 'claim_text':
                        claim.statement = 'PRIVATE CHANGED CLAIM CANARY'
                    elif change == 'claim_status':
                        claim.status = 'CONTESTED' if claim.status != 'CONTESTED' else 'SUPPORTED'
                    else:
                        private = extra_source(session, saved, private=True)
                        session.add(ClaimEvidence(**scope(saved), source_id=private.id, claim_id=claim.id,
                            relation='CONTEXT', quote='PRIVATE CANARY', locator='p1'))
                elif change == 'trigger':
                    question['trigger']['quote'] = 'PRIVATE FORGED TRIGGER CANARY'
                else:
                    question.pop('open_check_context')
                saved.research_state = state
                session.commit()
            if change == 'unquoted':
                exclude(service, identity, unquoted)
            result = projected(service, run)
            assert result.get('purpose') is None
            assert 'PRIVATE' not in json.dumps(result)
            observed.append(result)
        return await execute(service, work, seconds)

    monkeypatch.setattr(product_iterative_steps, 'execute', inspect)
    advance(service, run, observed)


@pytest.mark.parametrize('action', ['pause', 'cancel'])
def test_controls_remove_a_real_working_purpose(signed, monkeypatch, action):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    root, run, _ = start(client)
    execute = product_iterative_steps.execute
    observed = []

    async def inspect(service, work, seconds):
        if work['phase'] == 'search' and not observed:
            assert projected(service, run)['purpose']
            page = client.get(root + '/investigations/' + run['id']).json()
            result = post(client, root + '/investigations/' + run['id'] + '/control',
                {'action': action, 'expected_revision': page['revision']})
            assert result.status_code == 200
            value = current(client, root, run)
            assert value['status'] == ('paused' if action == 'pause' else 'finished')
            assert 'purpose' not in value
            observed.append(value)
        return await execute(service, work, seconds)

    monkeypatch.setattr(product_iterative_steps, 'execute', inspect)
    advance(service, run, observed)


@pytest.mark.parametrize('product', ['legal', 'pharma'])
def test_selected_check_uses_original_citation_and_withholds_changed_ancestor(signed, monkeypatch, product):
    from test_product_open_check import prepared
    from test_product_saved_check import command, url

    client, service, identity, model = signed
    root, old, _ = prepared(client, service, model, monkeypatch, product)
    check = old['exploration']['next_check']
    child = post(client, url(root, old), command(old)).json()
    execute = product_iterative_steps.execute
    observed = []

    async def inspect(service, work, seconds):
        if work['phase'] == 'search' and not observed:
            value = projected(service, child)
            assert value['purpose']['kind'] == 'source_follow_up'
            assert value['purpose']['text'] == check['purpose']
            assert value['purpose']['trigger']['quote'] == check['quote']
            assert value['purpose']['trigger']['source']['id'] == check['source']['id']
            exclude(service, identity, check['source']['id'])
            value = projected(service, child)
            assert value == {'contract': 'research-activity/v1', 'status': 'evidence_changed'}
            observed.append(value)
        return await execute(service, work, seconds)

    monkeypatch.setattr(product_iterative_steps, 'execute', inspect)
    advance(service, child, observed)
