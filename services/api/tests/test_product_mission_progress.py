"""Saved workflow stages never override current work or publish private drafts."""
import json
from copy import deepcopy
from types import SimpleNamespace

from test_product_dossiers import signed as signed
from test_product_retained_frontier import frontier as frontier

from helvetic_lens import product_research_mission as mission
from helvetic_lens.product_investigation_models import InvestigationBranch
from helvetic_lens.product_investigations import scope


def test_current_briefing_stage_preserves_answer_history_and_source_fences(frontier):
    session, run, source_branch, source, _ = frontier
    passage = source.snapshot['excerpts'][0]
    supplied = {'sources': [{'id': source.id, 'kind': source.kind, 'sha256': source.sha256,
        'url': source.url, 'title': source.title, 'excerpts': deepcopy(source.snapshot['excerpts'])}]}
    answer = {'status': 'possible_answer', 'points': [{'statement': passage['text'], 'evidence': [{
        'source_id': source.id, 'locator': passage['passage'], 'quote': passage['text'], 'role': 'support'}]}],
        'limitations': []}
    mission.apply(session, run, supplied, SimpleNamespace(mission_checkpoint=mission.Checkpoint(
        answer=answer, action='finish', reason='The checked original supports the saved answer.'),
        clarification='', directions=[]))
    saved_answer = mission.project(session, run)['answer']
    mission.update(run, stage='deepening', stop=None)
    private = 'PRIVATE UNREVIEWED FINAL ANSWER'
    brief = InvestigationBranch(**scope(run), query='Retry existing research briefing',
        phase='brief', status='queued', reason='Finish the saved research answer.',
        checkpoint={'research_control': True, 'synthesis_checkpoint': {'stage': 'finalizing', 'raw': private}})
    session.add(brief)
    session.flush()
    saved = deepcopy(run.research_state)
    for branch_status in ('queued', 'running'):
        brief.status = branch_status
        value = mission.project(session, run)
        assert value['stage'] == 'synthesizing'
        assert value['answer'] == saved_answer
        assert private not in json.dumps(value)
        assert run.research_state == saved
    # Pending source work still requires investigation; merely retaining a
    # finalizing draft cannot claim the whole mission has reached synthesis.
    source_branch.status, source_branch.phase = 'queued', 'extract'
    assert mission.project(session, run)['stage'] == 'deepening'
    source_branch.status = 'completed'
    assert mission.project(session, run)['stage'] == 'synthesizing'
    brief.status = 'completed'
    assert mission.project(session, run)['stage'] == 'deepening'
    brief.status = 'queued'
    for status in ('paused', 'failed', 'completed'):
        run.status = status
        assert mission.project(session, run)['stage'] == 'deepening'
    run.status = 'running'
    mission.update(run, stage='incomplete', stop='review_unavailable')
    assert mission.project(session, run)['stage'] == 'incomplete'
    mission.update(run, stage='deepening', stop=None)
    assert run.research_state == saved
    source.sha256 = 'b' * 64
    withdrawn = mission.project(session, run)
    assert withdrawn['stage'] == 'evidence_changed' and withdrawn['answer'] is None
