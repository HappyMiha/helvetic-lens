"""Retained discovery after a failed reflection; no live adapters or model calls."""
import json
from copy import deepcopy
from uuid import uuid4

import pytest
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_exploration import start

from helvetic_lens import product_iterative_research as research
from helvetic_lens import product_iterative_steps as steps
from helvetic_lens import product_research_mission as mission
from helvetic_lens.config import DomainError
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from helvetic_lens.product_investigation_worker import settle
from helvetic_lens.product_investigations import rows, scope
from helvetic_lens.product_models import DossierEntry
from helvetic_lens.product_operations import fingerprint
from helvetic_lens.research_reading_context import stamp


@pytest.fixture
def frontier(signed):
    client, service, identity, _ = signed
    _, started, _ = start(client)
    with service.db.session() as session:
        run = session.get(Investigation, started['id'])
        run.status = 'running'
        for previous in rows(session, InvestigationBranch, run):
            previous.status = 'completed'
        source = InvestigationSource(**scope(run), source_key='a' * 64, kind='public_source',
            title='Original record', url='https://example.org/read', sha256='a' * 64,
            snapshot={'excerpts': [{'passage': 'p1', 'text': 'The original record states the applicable condition.'}]})
        session.add(source)
        session.flush()
        identifier = research.add_question(session, run, research.BranchDraft(
            question='What do the original records establish?', query='original records condition',
            purpose='Read the requested original records.', priority=1))
        research.schedule_questions(session, run)
        question = next(q for q in run.research_state['questions'] if q['id'] == identifier)
        branch = session.get(InvestigationBranch, question['branch_id'])
        review = {'findings': [], 'synopsis': 'The complete fictional original was read.'}
        doc = {'sha256': source.sha256, 'source_ids': [source.id], 'read_complete': True,
            'analysis_complete': True, 'complete': True, 'reconciliation': review,
            'reading_context_binding': {**stamp(run.question, run.id),
                'review_fingerprint': fingerprint(review), 'dependencies': [{'source_id': source.id,
                    'sha256': source.sha256, 'fingerprint': fingerprint(source.snapshot)}]}}
        candidates = [{'id': str(index), 'url': url, 'title': 'Original record', 'summary': 'Public original.'}
            for index, url in enumerate([source.url, 'https://example.org/remaining'])]
        branch.phase, branch.status = 'reflect', 'failed'
        branch.checkpoint = {**branch.checkpoint, 'iterative': True, 'read_as_found': True,
            'source_ids': [source.id], 'items': candidates[:1], 'candidates': candidates,
            'gate_index': 1, 'read_index': 1, 'extract_index': 1, 'analysed': 1,
            'attempted_urls': [source.url], 'document_reads': {'0': doc}, 'question_finished': True,
            'source_limit': 1, 'steps': [{'phase': 'reflect', 'status': 'unavailable', 'error_code': 'invalid_evidence'}],
            'error': 'The reflection did not produce validated evidence.',
            'synthesis_checkpoint': {'private': 'Unvalidated reflection remains private.'}}
        session.flush()
        yield session, run, branch, source, identity


def request(session, run, branch, source):
    supplied = {'sources': [{'id': source.id, 'kind': source.kind, 'sha256': source.sha256,
        'url': source.url, 'title': source.title, 'excerpts': deepcopy(source.snapshot['excerpts'])}],
        'research_mission': mission.context(session, run)}
    checkpoint = mission.Checkpoint(answer={'status': 'partial', 'points': [], 'limitations': []},
        action='continue', reason='Read the remaining original before finishing.', deepen_branches=[branch.id])
    return supplied, checkpoint


@pytest.mark.parametrize('cursor', [False, True])
def test_failed_reflection_frontier_is_offered_selected_and_resumed_without_approving_it(frontier, cursor):
    session, run, branch, source, _ = frontier
    if cursor:
        branch.checkpoint = {**branch.checkpoint, 'gate_index': 2, 'next_discovery_cursors': {'broad': '2'}}
    before = deepcopy(branch.checkpoint)
    supplied, checkpoint = request(session, run, branch, source)
    assert branch.id in [f['branch_id'] for f in supplied['research_mission']['discovery_frontiers']]
    work = {'input': supplied, 'mission_continuation': mission.continuation_context(session, run)}
    assert mission.route_continuation(work, checkpoint)
    gaps, deeper = mission.next_work(session, run, supplied, checkpoint)
    assert mission.schedule_next(session, run, supplied, gaps, deeper)
    assert branch.status == 'running' and branch.phase == ('search' if cursor else 'gate')
    state = json.loads(json.dumps(branch.checkpoint))
    assert state['reflection_frontier_recovery'] == {'source_ids': [source.id]}
    assert not state['reflection_done']
    assert state['steps'] == before['steps'] and state['synthesis_checkpoint'] == before['synthesis_checkpoint']
    for key in ('source_ids', 'document_reads', 'candidates', 'attempted_urls', 'read_index', 'extract_index'):
        assert state[key] == before[key]
    if not cursor:
        assert state['source_limit'] == len(before['items']) + 3
    assert run.research_state['mission']['checkpoints'] == []


@pytest.mark.parametrize('change', ['plan', 'search', 'gate', 'read', 'wrong_step', 'successful_reflection',
    'no_frontier', 'attempted_candidate', 'excluded_candidate', 'lost_source', 'withdrawn', 'excluded_source',
    'changed_sha', 'changed_text', 'changed_question', 'incomplete_read', 'failed_analysis', 'foreign_question'])
def test_failed_frontier_requires_current_complete_readings_and_eligible_discovery(frontier, change):
    session, run, branch, source, identity = frontier
    supplied, checkpoint = request(session, run, branch, source)
    state = deepcopy(branch.checkpoint)
    if change in {'plan', 'search', 'gate', 'read'}:
        branch.phase = change
    elif change == 'wrong_step':
        state['steps'][-1]['phase'] = 'read'
    elif change == 'successful_reflection':
        state['reflection_done'] = True
    elif change == 'no_frontier':
        state['gate_index'] = 2
    elif change == 'attempted_candidate':
        state['attempted_urls'].append(state['candidates'][1]['url'])
    elif change.startswith('excluded_'):
        url = source.url if change == 'excluded_source' else state['candidates'][1]['url']
        session.add(DossierEntry(dossier_id=run.dossier_id, organization_id=run.organization_id,
            request_key=str(uuid4()), kind='source_review', actor_user_id=identity['user']['id'],
            url=url, body='Private exclusion reason.', data_json={'decision': 'exclude', 'revision': 1}))
        session.flush()
    elif change == 'lost_source':
        state['source_ids'].append('missing')
    elif change == 'withdrawn':
        source.snapshot = {**source.snapshot, 'allow_discovery': False}
    elif change == 'changed_sha':
        source.sha256 = 'b' * 64
    elif change == 'changed_text':
        source.snapshot = {**source.snapshot, 'excerpts': [{'passage': 'p1', 'text': 'A changed source original.'}]}
    elif change == 'changed_question':
        run.question = 'An unrelated new research request.'
    elif change == 'incomplete_read':
        state['document_reads']['0']['complete'] = False
    elif change == 'failed_analysis':
        state['failed_extract_indices'] = [0]
    else:
        state['question_id'] = 'another-question'
    branch.checkpoint = state
    assert not mission.discovery_frontier_available(session, run, branch)
    assert branch.id not in mission.continuation_context(session, run)['frontiers']
    assert branch.id not in [f['branch_id'] for f in mission.context(session, run)['discovery_frontiers']]
    with pytest.raises(DomainError, match='current supplied search frontier'):
        mission.next_work(session, run, supplied, checkpoint)


@pytest.mark.parametrize('progress', ['rejected', 'failed_read', 'duplicate', 'unanalysed', 'new_complete'])
def test_recovered_frontier_cannot_repeat_reflection_without_new_complete_original(frontier, progress):
    _, _, branch, source, _ = frontier
    state = deepcopy(branch.checkpoint)
    steps.continue_discovery(branch, state)
    state = json.loads(json.dumps(state))  # The progress guard survives worker restart.
    state['gate_index'] = len(state['candidates'])
    if progress != 'rejected':
        state['items'].append(state['candidates'][1])
        state['read_index'] = 2
    if progress == 'failed_read':
        state['document_reads']['1'] = {'read_complete': False, 'error': 'Unavailable.'}
    if progress == 'duplicate':
        state['unchanged'] = 1
        state['document_reads']['1'] = {**deepcopy(state['document_reads']['0']), 'source_ids': [source.id]}
    if progress in {'unanalysed', 'new_complete'}:
        state['source_ids'].append('new-original')
        state['extract_index'] = 2
        state['document_reads']['1'] = {'source_ids': ['new-original'], 'read_complete': True,
            'analysis_complete': progress == 'new_complete', 'complete': progress == 'new_complete',
            'review_failed': progress == 'unanalysed'}
        state['analysed'] += int(progress == 'new_complete')
    branch.phase = 'extract'
    settle(branch, state)
    if progress == 'new_complete':
        assert branch.phase == 'reflect' and branch.status == 'running'
        assert 'reflection_frontier_recovery' not in branch.checkpoint
    else:
        assert branch.phase == 'extract' and branch.status == 'failed'
        assert branch.checkpoint['reflection_frontier_recovery']['source_ids'] == [source.id]
    assert branch.checkpoint['steps'][-1]['status'] == 'unavailable'
    assert not branch.checkpoint['reflection_done']


def test_completed_legacy_frontier_keeps_existing_eligibility(frontier):
    session, run, branch, _, _ = frontier
    branch.status = 'completed'
    branch.checkpoint = {'next_discovery_cursors': {'broad': '2'}}
    assert mission.discovery_frontier_available(session, run, branch)
    state = deepcopy(branch.checkpoint)
    steps.continue_discovery(branch, state)
    assert branch.phase == 'search' and branch.status == 'running'
    assert 'reflection_frontier_recovery' not in state


@pytest.mark.parametrize('mode', ['paired_brief', 'reflection_only', 'legacy'])
def test_ordinary_retry_keeps_frontier_for_paired_mission_brief_only(frontier, signed, mode):
    session, run, branch, source, _ = frontier
    client, _, _, _ = signed
    run.status = 'failed'
    before = deepcopy(branch.checkpoint)
    if mode != 'reflection_only':
        brief = InvestigationBranch(**scope(run), query=f'Research checkpoint 1 {run.id}',
            phase='brief', status='failed', reason='Complete the requested answer.',
            checkpoint={'research_control': True, 'mission_round': 1,
                'steps': [{'phase': 'brief', 'status': 'unavailable'}]})
        session.add(brief)
    if mode == 'legacy':
        data = deepcopy(run.research_state)
        data['mission']['contract'] = 'legacy-mission'
        run.research_state = data
    run_id, branch_id, generation = run.id, branch.id, run.generation
    path = f'/api/products/pharma/dossiers/{run.dossier_id}/investigations/{run.id}/control'
    revision = run.revision
    session.commit()
    response = post(client, path, {'action': 'retry', 'expected_revision': revision})
    assert response.status_code == 200, response.text
    session.expire_all()
    run, branch = session.get(Investigation, run_id), session.get(InvestigationBranch, branch_id)
    assert run.generation == generation + 1 and run.status == 'queued'
    if mode != 'paired_brief':
        assert branch.status == 'queued' and branch.phase == 'reflect'
        return
    assert branch.status == 'failed' and branch.phase == 'reflect'
    assert branch.checkpoint == before, 'Retry preserves failed reflection, originals and private state verbatim'
    assert brief.status == 'queued' and brief.phase == 'brief'
    work = {'phase': 'brief'}
    steps.prepare(session, run, brief, deepcopy(brief.checkpoint), work)
    assert branch.id in work['mission_continuation']['frontiers']
    assert branch.id in [f['branch_id'] for f in work['input']['research_mission']['discovery_frontiers']]
    _, checkpoint = request(session, run, branch, source)
    assert mission.route_continuation(work, checkpoint)
    gaps, deeper = mission.next_work(session, run, work['input'], checkpoint)
    assert mission.schedule_next(session, run, work['input'], gaps, deeper)
    assert branch.phase == 'gate' and branch.status == 'running'
    assert branch.checkpoint['document_reads'] == before['document_reads']
    assert branch.checkpoint['steps'] == before['steps']
