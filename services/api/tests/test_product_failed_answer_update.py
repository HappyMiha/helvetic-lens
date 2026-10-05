"""An earlier dossier answer does not turn a failed later update into success."""
import json
from copy import deepcopy

from test_product_checked_delivery import finish
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_exploration import adapters, start
from test_product_investigations import tick

from helvetic_lens import research_gateway
from helvetic_lens.config import DomainError
from helvetic_lens.product_investigation_models import InvestigationBranch
from helvetic_lens.research_final_review import DEFERRED_NOTICE
from helvetic_lens.research_synthesis_resume import KEY, deferred_verification


def test_failed_answer_update_retains_previous_dossier_and_private_candidate_for_ordinary_retry(signed, monkeypatch):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    model_complete = model.complete

    async def mission(system, user, **kwargs):
        raw = await model_complete(system, user, **kwargs)
        if kwargs.get('response_schema', {}).get('title') != 'Briefing':
            return raw
        value = json.loads(raw)
        first = value['findings'][0]
        value.update(clarification='', directions=[], mission_checkpoint={
            'answer': {'status': 'possible_answer', 'points': [{'statement': first['statement'],
                'evidence': [{key: first[key] for key in ('source_id', 'quote', 'locator')} | {'role': 'support'}]}],
                'limitations': []}, 'action': 'finish', 'reason': 'The current retained original establishes this finding.',
            'next_checks': [], 'deepen_branches': []})
        return json.dumps(value)

    monkeypatch.setattr(model, 'complete', mission)
    original, calls = research_gateway.execute, []
    private = 'PRIVATE NEW CANDIDATE AWAITING A COMPLETE REVIEW'
    pending = {'stage': 'finalizing', 'binding': 'current-review-binding', 'raw': private,
        'parts': {'final_reviews': {}, 'workflow_gaps': []}}

    async def execute(service, work, seconds):
        if work['phase'] != 'brief':
            return await original(service, work, seconds)
        calls.append(work['branch_id'])
        if len(calls) == 2:
            # The earlier publication remains valid, but this new final review
            # cannot complete. Its private candidate must not become an answer.
            work[KEY] = deepcopy(pending)
            work.setdefault('model_route', {})['evidence_transport'] = {'input_fingerprint': 'retained-current-originals'}
            raise DomainError('The new assertion review is incomplete.', 503, 'research_review_incomplete')
        if len(calls) == 3:
            assert work[KEY] == pending, 'The ordinary retry must receive the pending candidate'
            assert not work.get('retry_deferred_review'), 'This is not a retry of an already published new subset'
        result = await original(service, work, seconds)
        if len(calls) == 1:
            # Model the existing trusted finalizer handoff; its exhaustion and
            # exact-input authorization gates are covered independently.
            result.mission_checkpoint.answer.status = 'partial'
            result.mission_checkpoint.answer.limitations.append(DEFERRED_NOTICE)
            saved = deepcopy(pending)
            saved['parts']['deferred_final_review'] = {'status': 'qualified_delivery',
                'pending_checks': [{'item': 'P1', 'reason': 'model_upstream_timeout'}]}
            work[KEY] = saved
            work.setdefault('model_route', {})['evidence_transport'] = {'input_fingerprint': 'retained-current-originals'}
            work['deferred_review_verification'] = deferred_verification(saved)
        return result

    monkeypatch.setattr(research_gateway, 'execute', execute)
    root, run, _ = start(client)
    delivered = finish(client, service, root, run)
    assert delivered['status'] == 'completed' and delivered['retry']['available']
    previous = deepcopy(delivered['exploration']['mission']['answer'])
    previous_briefing = deepcopy(delivered['exploration']['briefing'])
    assert previous['points'] and previous['status'] == 'partial'
    url = root + '/investigations/' + run['id']
    retry = post(client, url + '/control', {'action': 'retry', 'expected_revision': delivered['revision']})
    assert retry.status_code == 200, retry.text
    assert retry.json()['exploration']['mission']['stage'] == 'synthesizing'
    assert retry.json()['exploration']['mission']['answer'] == previous
    assert retry.json()['exploration']['current_activity']['status'] == 'waiting'
    assert private not in retry.text
    failed = finish(client, service, root, retry.json())
    assert failed['status'] == 'failed' and failed['retry']['available']
    assert failed['exploration']['mission']['stop'] == 'answer_unavailable'
    assert failed['exploration']['mission']['answer'] == previous
    assert failed['exploration']['briefing'] == previous_briefing
    assert 'latest answer could not be validated' in failed['stop_reason']
    assert 'previous saved answer remains available' in failed['stop_reason']
    assert 'Research returned a partial answer' not in failed['stop_reason']
    assert private not in json.dumps(failed) and private not in client.get(root + '/export').text
    with service.db.session() as session:
        branch = session.get(InvestigationBranch, calls[0])
        assert branch.status == 'failed' and branch.checkpoint[KEY] == pending
    tick(service, run['id'])
    assert len(calls) == 2, 'A failed update must wait for the ordinary explicit retry'
    retry = post(client, url + '/control', {'action': 'retry', 'expected_revision': failed['revision']})
    assert retry.status_code == 200, retry.text
    assert retry.json()['exploration']['mission']['stage'] == 'synthesizing'
    assert retry.json()['exploration']['mission']['answer'] == previous
    assert retry.json()['exploration']['current_activity']['status'] == 'waiting'
    assert private not in retry.text
    completed = finish(client, service, root, retry.json())
    assert completed['id'] == run['id'] and completed['status'] == 'completed'
    assert len(calls) == 3 and not completed['retry']['available']
    assert completed['exploration']['mission']['stop'] == 'available_checks_complete'
    assert len(completed['exploration']['mission']['checkpoints']) == 2
    assert completed['exploration']['mission']['verification'] is None
    assert completed['exploration']['mission']['answer']['status'] == 'possible_answer'
