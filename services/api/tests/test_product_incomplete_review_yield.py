"""Native continuation of untouched checks is distinct from successful work."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude
from test_product_exploration import adapters
from test_product_exploration import start as explore
from test_product_iterative_research import complete

from helvetic_lens import research_final_review as review
from helvetic_lens import research_gateway
from helvetic_lens.config import DomainError
from helvetic_lens.product_investigation_models import InvestigationBranch
from helvetic_lens.product_investigation_worker import new_incomplete_review
from helvetic_lens.research_synthesis_resume import KEY, completed_work


def negative_checkpoint(work):
    attempt = review.review_attempt(SimpleNamespace(work=work))
    work['unfinished_review_attempt'] = attempt
    return {'stage': 'finalizing', 'binding': 'exact-draft-binding', 'request_binding': 'exact-request-binding',
        'raw': 'PRIVATE INCOMPLETE TARGET', 'parts': {'final_reviews': {'incomplete_assertions': {
            'exact-target': {'attempt': attempt, 'policy_fingerprint': review.POLICY,
                'input_fingerprint': 'clauses:exact-current-request', 'reason': 'model_incomplete'}}}}}


def test_only_new_current_negative_receipt_permits_continuation_without_completed_progress():
    work = {'run_id': 'current-run', 'generation': 1}
    current = negative_checkpoint(work)
    assert new_incomplete_review(None, current, work)
    assert completed_work(current) == {}
    assert not new_incomplete_review(deepcopy(current), current, work)
    for field, value in [('attempt', 'old-generation'), ('policy_fingerprint', 'old-policy'),
            ('reason', 'model_timeout'), ('input_fingerprint', ''), ('input_fingerprint', None)]:
        invalid = deepcopy(current)
        invalid['parts']['final_reviews']['incomplete_assertions']['exact-target'][field] = value
        assert not new_incomplete_review(None, invalid, work)
    for field, value in [('stage', 'draft'), ('binding', ''), ('request_binding', '')]:
        invalid = deepcopy(current)
        invalid[field] = value
        assert not new_incomplete_review(None, invalid, work)
    assert not new_incomplete_review(None, current, {**work, 'generation': 2})
    assert not new_incomplete_review(None, current, {**work, 'unfinished_review_attempt': None})


@pytest.mark.parametrize('outcome', ['continue', 'stall', 'withdraw'])
def test_first_incomplete_target_yields_native_once_without_renewing_proofs_or_outage_count(signed, monkeypatch, outcome):
    client, service, identity, model = signed
    adapters(monkeypatch, service, model)
    scripted = model.complete

    async def completed_mission(*args, **kwargs):
        value = json.loads(await scripted(*args, **kwargs))
        if 'mission_checkpoint' in kwargs['response_schema'].get('properties', {}):
            first = value['findings'][0]
            value['mission_checkpoint'] = {'action': 'finish',
                'reason': 'The retained source supports this finding; uncertainty stays explicit.',
                'answer': {'status': 'partial', 'limitations': value['uncertainties'],
                    'points': [{'statement': first['statement'], 'evidence': [
                        {**{key: first[key] for key in ('source_id', 'locator', 'quote')}, 'role': 'support'}]}]}}
        return json.dumps(value)

    monkeypatch.setattr(model, 'complete', completed_mission)
    root, run, _ = explore(client)
    execute, calls, sources = research_gateway.execute, [], []
    retry_key = 'same-provider-input'

    async def yielded(service, work, seconds):
        if work['phase'] != 'brief':
            return await execute(service, work, seconds)
        calls.append(work['branch_id'])
        work['model_route'] = {'evidence_transport': {'input_fingerprint': retry_key}}
        if len(calls) == 1:
            sources.extend(source['id'] for source in work['input']['sources'])
            work[KEY] = negative_checkpoint(work)
            assert completed_work(work[KEY]) == {}
            # Existing outage accounting must survive negative-only continuation.
            with service.db.session() as session:
                branch = session.get(InvestigationBranch, work['branch_id'])
                branch.checkpoint = {**branch.checkpoint, 'provider_retries': {retry_key: 2}}
                session.commit()
            if outcome == 'withdraw':
                exclude(service, identity, sources[0])
            raise DomainError('Untouched siblings remain after output length finish', 503, 'research_review_yield')
        assert work[KEY]['raw'] == 'PRIVATE INCOMPLETE TARGET'
        assert completed_work(work[KEY]) == {}
        assert [source['id'] for source in work['input']['sources']] == sources
        with service.db.session() as session:
            state = session.get(InvestigationBranch, work['branch_id']).checkpoint
            assert state['provider_retries'] == {retry_key: 2}
            previous = state['steps'][-2]
            assert previous['status'] == 'unavailable'
            assert previous['error_code'] == 'model_incomplete'
            assert previous['execution']['outcome'] == 'unavailable'
            assert not previous.get('checkpointed')
        if outcome == 'stall':
            work['unfinished_review_attempt'] = review.review_attempt(SimpleNamespace(work=work))
            raise DomainError('No new work or new failed target', 503, 'research_review_yield')
        return await execute(service, work, seconds)

    monkeypatch.setattr(research_gateway, 'execute', yielded)
    result = complete(client, service, root + '/investigations', run)
    assert result['status'] == {'continue': 'completed', 'stall': 'failed', 'withdraw': 'paused'}[outcome]
    assert len(calls) == (1 if outcome == 'withdraw' else 2)
    assert 'PRIVATE INCOMPLETE TARGET' not in json.dumps(result)
    assert 'PRIVATE INCOMPLETE TARGET' not in client.get(root + '/export').text
    with service.db.session() as session:
        state = session.get(InvestigationBranch, calls[0]).checkpoint
        if outcome == 'stall':
            assert state['provider_retries'] == {retry_key: 2}
            assert state['steps'][-1]['error_code'] == 'research_review_incomplete'
            assert completed_work(state[KEY]) == {}
