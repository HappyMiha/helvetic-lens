"""Requested-original work uses the current ordinary frontier and reader channels."""
import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_product_dossiers import signed as signed
from test_product_exploration import adapters, start
from test_product_investigations import tick
from test_product_retained_frontier import frontier as frontier

from helvetic_lens import product_iterative_research as research
from helvetic_lens import product_iterative_steps as steps
from helvetic_lens import product_requested_originals as requested_originals
from helvetic_lens import product_research_mission as mission
from helvetic_lens import product_source_requirements as requirements
from helvetic_lens import research_gateway
from helvetic_lens.product_investigation_models import Investigation, InvestigationSource
from helvetic_lens.product_investigation_worker import finish_or_yield, settle
from helvetic_lens.product_models import DossierEntry


def own(frontier):
    session, run, branch, _, _ = frontier
    requirements.attach(run, branch.checkpoint['question_id'], ['Alpin Foundation'])
    return requested_originals.outcomes(session, run)


def exclude(frontier, url):
    session, run, _, _, identity = frontier
    session.add(DossierEntry(dossier_id=run.dossier_id, organization_id=run.organization_id,
        request_key=str(uuid4()), kind='source_review', actor_user_id=identity['user']['id'],
        url=url, body='PRIVATE exclusion reason', data_json={'decision': 'exclude', 'revision': 1}))
    session.flush()


@pytest.mark.parametrize('mode', ['completed', 'failed', 'cursor_after_exclusion'])
def test_pending_original_resumes_only_its_saved_owner_frontier(frontier, mode):
    session, run, branch, source, _ = frontier
    outcomes = own(frontier)
    assert outcomes[0]['status'] == 'not_identified'
    if mode == 'completed':
        branch.status = 'completed'
    if mode == 'cursor_after_exclusion':
        exclude(frontier, branch.checkpoint['candidates'][1]['url'])
        branch.checkpoint = {**branch.checkpoint, 'next_discovery_cursors': {'broad': 'page-2'},
            'discovery_history': [{'cursor': 'page-1'}]}
    before = deepcopy(branch.checkpoint)
    assert mission.continue_required_sources(session, run, branch, outcomes)
    assert branch.status == 'running'
    assert branch.phase == ('search' if mode == 'cursor_after_exclusion' else 'gate')
    restored = json.loads(json.dumps(branch.checkpoint))
    for key in ('source_ids', 'document_reads', 'candidates', 'attempted_urls', 'steps', 'synthesis_checkpoint'):
        assert restored[key] == before[key]
    assert 'question_finished' not in restored
    owner = next(q for q in run.research_state['questions'] if q['id'] == outcomes[0]['question_id'])
    assert owner['status'] == 'investigating'
    if mode != 'completed':
        assert restored['reflection_frontier_recovery'] == {'source_ids': [source.id]}
    if mode == 'cursor_after_exclusion':
        assert restored['discovery_cursor'] == {'broad': 'page-2'}
        assert restored['discovery_history'] == [{'cursor': 'page-1'}]
    # This is neither a completed reading nor approval of the failed reflection.
    assert not restored['reflection_done'] and run.research_state['mission']['checkpoints'] == []
    assert not mission.continue_required_sources(session, run, branch, outcomes)


def test_reopened_failed_reflection_still_requires_a_new_completed_original(frontier):
    session, run, branch, source, _ = frontier
    assert mission.continue_required_sources(session, run, branch, own(frontier))
    state = json.loads(json.dumps(branch.checkpoint))
    state['gate_index'] = len(state['candidates'])
    branch.phase = 'extract'
    settle(branch, state)
    assert branch.status == 'failed'
    assert branch.checkpoint['reflection_frontier_recovery'] == {'source_ids': [source.id]}
    assert not branch.checkpoint['reflection_done']


@pytest.mark.parametrize('status', ['matched_read', 'acquisition_unavailable', 'reading_incomplete', 'analysis_incomplete'])
def test_bound_attempts_do_not_automatically_reopen_discovery(frontier, status):
    session, run, branch, _, _ = frontier
    outcomes = own(frontier)
    outcomes[0]['status'] = status
    before = deepcopy(branch.checkpoint)
    assert not mission.continue_required_sources(session, run, branch, outcomes)
    assert branch.checkpoint == before


@pytest.mark.parametrize('change', ['excluded_candidate', 'attempted_candidate', 'withdrawn_source',
    'private_branch', 'no_discovery', 'changed_question', 'wrong_owner', 'foreign_run', 'legacy'])
def test_missing_or_ineligible_frontier_cannot_be_reopened(frontier, change):
    session, run, branch, source, _ = frontier
    outcomes = own(frontier)
    branch.status = 'completed'  # The broad legacy completed-branch gate is insufficient.
    if change == 'excluded_candidate':
        exclude(frontier, branch.checkpoint['candidates'][1]['url'])
    elif change == 'attempted_candidate':
        branch.checkpoint = {**branch.checkpoint,
            'attempted_urls': [*branch.checkpoint['attempted_urls'], branch.checkpoint['candidates'][1]['url']]}
    elif change == 'withdrawn_source':
        source.snapshot = {**source.snapshot, 'allow_discovery': False}
    elif change == 'private_branch':
        branch.checkpoint = {**branch.checkpoint, 'saved': True}
    elif change == 'no_discovery':
        run.external_discovery = False
    elif change == 'changed_question':
        run.question += ' Changed scope.'
    elif change == 'wrong_owner':
        outcomes[0]['question_id'] = str(uuid4())
    elif change == 'foreign_run':
        branch.investigation_id = str(uuid4())
    else:
        data = deepcopy(run.research_state)
        for question in data['questions']:
            question.pop(requirements.FIELD, None)
        run.research_state = data
    before = deepcopy(branch.checkpoint)
    assert not mission.continue_required_sources(session, run, branch, outcomes)
    assert branch.checkpoint == before


def test_worker_does_not_stamp_reopened_question_finished(frontier, monkeypatch):
    from helvetic_lens import jobs, product_claim_evolution
    from helvetic_lens import product_investigation_worker as worker

    session, run, branch, _, _ = frontier
    own(frontier)
    branch.checkpoint = {key: value for key, value in branch.checkpoint.items() if key != 'question_finished'}
    def finish(session, run, current):
        assert current is branch
        return not mission.continue_required_sources(session, run, current, requested_originals.outcomes(session, run))
    monkeypatch.setattr(research, 'finish_question', finish)
    monkeypatch.setattr(worker.query_recovery, 'schedule', lambda *args: False)
    monkeypatch.setattr(product_claim_evolution, 'schedule', lambda *args: False)
    monkeypatch.setattr(worker.exploration, 'schedule', lambda *args: False)
    yielded = []
    monkeypatch.setattr(jobs, 'yield_batch', lambda *args: yielded.append(True))
    finish_or_yield(session, run, SimpleNamespace())
    assert yielded == [True] and branch.status == 'running'
    assert 'question_finished' not in branch.checkpoint


def test_source_work_limits_are_named_current_and_owned_without_replacing_checked_points(frontier, monkeypatch):
    session, run, branch, source, _ = frontier
    own(frontier)
    current = requested_originals.outcomes(session, run)
    current.append({'id': 'optional-target', 'question_id': current[0]['question_id'],
        'requested_source': 'Additional publication catalogue', 'origin': 'planner_interpretation',
        'status': 'not_identified', 'reason': 'The planned source target has not been identified.'})
    monkeypatch.setattr(requested_originals, 'outcomes', lambda *args, **kwargs: deepcopy(current))
    passage = source.snapshot['excerpts'][0]
    supplied = {'sources': [{'id': source.id, 'kind': source.kind, 'sha256': source.sha256,
        'url': source.url, 'title': source.title, 'excerpts': deepcopy(source.snapshot['excerpts'])}]}
    answer = {'status': 'possible_answer', 'points': [{'statement': passage['text'], 'evidence': [{
        'source_id': source.id, 'locator': passage['passage'], 'quote': passage['text'], 'role': 'support'}]}],
        'limitations': ['A separate interpretation remains unsettled.']}
    result = SimpleNamespace(mission_checkpoint=mission.Checkpoint(answer=answer, action='finish',
        reason='The checked findings are ready with their current source-work limitations.'), clarification='', directions=[])
    mission.apply(session, run, supplied, result)
    saved = deepcopy(run.research_state['mission']['checkpoints'])
    view = mission.project(session, run)
    assert view['answer']['status'] == 'partial'
    assert view['requested_sources'] == current
    assert view['answer']['limitations'] == [answer['limitations'][0], *mission.source_work_limits(current)]
    assert len(view['answer']['limitations']) == 2, 'Only the actual request adds a completion limit'
    assert mission.context(session, run)['previous_checkpoint']['answer'] == view['answer']
    assert 'source_work' not in json.dumps(view)
    assert 'source_work' not in mission.context(session, run)['previous_checkpoint']
    assert requirements.FIELD not in json.dumps(mission.context(session, run)['attempted_questions'])
    # Only the host-owned notices are replaced; checked originals and other limits stay.
    current[0].update(status='matched_read', reason=requested_originals.REASONS['matched_read'])
    resolved = mission.project(session, run)
    assert resolved['answer']['status'] == 'possible_answer'
    assert resolved['answer']['limitations'] == answer['limitations']
    assert resolved['answer']['points'] == view['answer']['points']
    assert mission.context(session, run)['previous_checkpoint']['answer'] == resolved['answer']
    assert resolved['requested_sources'][1] == current[1], 'The unresolved discovery target remains visible'
    current[0].update(status='reading_incomplete', reason=requested_originals.REASONS['reading_incomplete'])
    changed = mission.project(session, run)
    assert changed['answer']['status'] == 'partial'
    assert changed['answer']['limitations'] == [answer['limitations'][0], *mission.source_work_limits(current)]
    assert mission.context(session, run)['previous_checkpoint']['answer'] == changed['answer']
    assert run.research_state['mission']['checkpoints'] == saved
    assert 'identity' not in changed['requested_sources'][0] and 'sha256' not in changed['requested_sources'][0]


@pytest.mark.parametrize('base_status,has_receipt', [('possible_answer', True), ('partial', True), ('partial', False)])
def test_saved_planner_penalty_is_removed_only_with_its_exact_host_receipt(frontier, monkeypatch, base_status, has_receipt):
    session, run, _, source, _ = frontier
    current = [{'id': 'optional-target', 'question_id': 'owner', 'origin': 'planner_interpretation',
        'requested_source': 'Additional publication catalogue', 'status': 'not_identified',
        'reason': 'The planned source target has not been identified.'}]
    monkeypatch.setattr(requested_originals, 'outcomes', lambda *args, **kwargs: deepcopy(current))
    passage = source.snapshot['excerpts'][0]
    supplied = {'sources': [{'id': source.id, 'kind': source.kind, 'sha256': source.sha256,
        'url': source.url, 'title': source.title, 'excerpts': deepcopy(source.snapshot['excerpts'])}]}
    answer = {'status': base_status, 'points': [{'statement': passage['text'], 'evidence': [{
        'source_id': source.id, 'locator': passage['passage'], 'quote': passage['text'], 'role': 'support'}]}],
        'limitations': ['An independently assessed qualification remains.']}
    result = SimpleNamespace(mission_checkpoint=mission.Checkpoint(answer=answer, action='finish',
        reason='The checked answer is retained.'), clarification='', directions=[])
    mission.apply(session, run, supplied, result)
    assert run.research_state['mission']['checkpoints'][-1]['answer']['status'] == base_status
    assert run.research_state['mission']['checkpoints'][-1]['answer']['limitations'] == answer['limitations']
    # An immutable old delivery may contain the former automatic planner limit.
    state = deepcopy(run.research_state)
    record = state['mission']['checkpoints'][-1]
    notice = 'Planned source target “Additional publication catalogue”: The planned source target has not been identified.'
    record['answer']['status'] = 'partial'
    record['answer']['limitations'].append(notice)
    if has_receipt:
        record['source_work'] = {'status': base_status, 'limitations': [notice]}
    else:
        record.pop('source_work', None)
    run.research_state = state
    saved = deepcopy(run.research_state)
    public = mission.project(session, run)
    context = mission.context(session, run)
    assert public['answer'] == context['previous_checkpoint']['answer']
    assert public['answer']['status'] == (base_status if has_receipt else 'partial')
    assert public['answer']['limitations'] == answer['limitations'] + ([] if has_receipt else [notice])
    assert public['answer']['points'] == record['answer']['points']
    assert public['requested_sources'] == context['requested_sources'] == current
    assert 'source_work' not in context['previous_checkpoint']
    assert 'source_work' not in public['checkpoints'][-1]
    assert run.research_state == saved, 'Read-only projection must not rewrite the stored delivery or proofs'


def test_legacy_mission_has_no_fabricated_requested_source_status(frontier):
    session, run, _, _, _ = frontier
    assert requested_originals.outcomes(session, run) == []
    assert 'requested_sources' not in mission.context(session, run)
    assert 'requested_sources' not in mission.project(session, run)


def test_optional_bad_identity_match_does_not_discard_a_valid_extraction(monkeypatch):
    quote = 'The original record states the applicable condition.'
    async def complete(*args):
        return json.dumps({'claims': [{'statement': quote, 'quote': quote, 'locator': 'p1', 'relation': 'SUPPORTS'}],
            'requested_source_matches': [{'requirement_id': 12, 'locator': 'p1'}]})
    monkeypatch.setattr(research_gateway, 'complete', complete)
    result = asyncio.run(steps.execute(SimpleNamespace(), {'phase': 'extract', 'unmetered_research': True,
        'input': {'question': 'Read the original record.', 'source': {'id': 'a' * 36,
            'excerpts': [{'passage': 'p1', 'text': quote}]}}}, 10))
    assert result.claims[0].quote == quote
    assert result.requested_source_matches == []
    assert result._optional_omissions == ['requested_source_matches']


def test_actual_reader_input_has_all_current_requirements_across_owners(signed, monkeypatch):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    base = model.complete
    captured = []
    async def complete(system, user, **kwargs):
        data = json.loads(user)
        if kwargs['response_schema']['title'] == 'ResearchExtraction':
            captured.append(deepcopy(data))
        return await base(system, user, **kwargs)
    monkeypatch.setattr(model, 'complete', complete)
    _, started, _ = start(client)
    wanted = None
    for _ in range(20):
        with service.db.session() as session:
            run = session.get(Investigation, started['id'])
            questions = run.research_state.get('questions', [])
            if wanted is None and len(questions) >= 2:
                requirements.attach(run, questions[0]['id'], ['Alpin Foundation'])
                requirements.attach(run, questions[1]['id'], ['money'])
                wanted = [{key: item[key] for key in ('id', 'requested_source', 'origin')} for item in requirements.requirements(run)]
                session.commit()
        tick(service, started['id'])
        if captured:
            break
    assert captured and wanted and len(wanted) == 2
    assert captured[0]['requested_sources'] == wanted
    assert requirements.FIELD not in captured[0]
    with service.db.session() as session:
        source = session.get(InvestigationSource, captured[0]['source']['id'])
        assert source.kind == 'public_source'
        assert captured[0]['source']['url'] == source.url
        assert captured[0]['source']['excerpts'], 'Identity metadata does not replace captured passages'


def test_normal_result_omits_only_private_source_matches_and_keeps_stored_proof(signed):
    from test_product_requested_originals import seed

    from helvetic_lens.product_investigation_models import InvestigationSource

    client = signed[0]
    service, run_id, _, source_ids, _ = seed(signed)
    with service.db.session() as session:
        run = session.get(Investigation, run_id)
        dossier_id = run.dossier_id
        # The resolver fixture intentionally supplies only ownership fields;
        # the ordinary API also projects the normal question status/text.
        data = deepcopy(run.research_state)
        for question in data['questions']:
            question.update(question=run.question, status='unresolved')
        run.research_state = data
        source = session.get(InvestigationSource, source_ids[0])
        saved = deepcopy(source.snapshot)
        assert saved['requested_source_matches']
        assert requested_originals.outcomes(session, run)[0]['status'] == 'matched_read'
        session.commit()
    response = client.get(f'/api/products/pharma/dossiers/{dossier_id}/investigations/{run_id}')
    assert response.status_code == 200, response.text
    public = next(source for source in response.json()['sources'] if source['id'] == source_ids[0])
    assert public['snapshot'] == {key: value for key, value in saved.items() if key != 'requested_source_matches'}
    assert 'requested-original-match/v1' not in response.text
    with service.db.session() as session:
        source = session.get(InvestigationSource, source_ids[0])
        assert source.snapshot == saved
        assert requested_originals.outcomes(session, session.get(Investigation, run_id))[0]['status'] == 'matched_read'
