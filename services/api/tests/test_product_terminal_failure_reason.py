"""Terminal reading counts must not hide a separate final-answer failure."""
from copy import deepcopy

import pytest
from test_product_dossiers import signed as signed
from test_product_exploration import start

from helvetic_lens.models import Job
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch
from helvetic_lens.product_investigation_worker import finish_or_yield
from helvetic_lens.product_investigations import scope
from helvetic_lens.product_research_admission import unmetered


@pytest.mark.parametrize('answer_failed,unread', [(True, 0), (True, 1), (False, 1)])
def test_terminal_public_reason_preserves_answer_failure_and_document_counts(signed, answer_failed, unread):
    client, service, _, model = signed
    root, run, _ = start(client)
    calls = deepcopy(model.calls)
    documents = {str(index): {'contract': 'document-reading/v1',
        'title': f'Original {index + 1}', 'url': f'https://example.org/original-{index + 1}',
        'sha256': str(index + 1) * 64, 'read_complete': index >= unread,
        'analysis_complete': False, 'complete': False,
        'unread_reason': 'Reading remains incomplete.' if index < unread else 'Validated analysis remains incomplete.'}
        for index in range(2)}
    with service.db.session() as session:
        row = session.get(Investigation, run['id'])
        assert unmetered(row)
        row.status = 'running'
        state = deepcopy(row.research_state)
        state['mission'].update(stage='finished',
            stop='answer_unavailable' if answer_failed else 'documents_incomplete')
        state['exploration'].update(status='unavailable', briefing=None)
        row.research_state = state
        phase = 'brief' if answer_failed else 'document_review'
        branch = InvestigationBranch(**scope(row), query=row.question, phase=phase,
            status='failed', reason='Complete the retained research.', checkpoint={
                'research_control': answer_failed, 'document_reads': deepcopy(documents),
                'steps': [{'phase': phase, 'status': 'failed'}]})
        session.add(branch)
        session.flush()
        # Exercise terminal coordinator and real document projection; no provider
        # dispatch or substitute for the failure-message block is installed.
        job = session.get(Job, row.job_id)
        finish_or_yield(session, row, job)
        assert row.status == 'failed' and job.result_json == {'status': 'failed'}
        assert branch.checkpoint['document_reads'] == documents
        reason = row.stop_reason
        session.commit()

    value = client.get(root + '/investigations/' + run['id']).json()
    assert value['status'] == 'failed' and value['stop_reason'] == reason
    assert value['exploration']['mission']['answer'] is None
    assert value['exploration']['mission']['checkpoints'] == []
    assert 'previous saved answer' not in reason
    document_reason = (f'Research is incomplete: {unread} document(s) still need reading; '
        f'{2 - unread} were read but still need validated analysis. Sources and completed work are retained; '
        'the remaining limitations are shown with each document.')
    if answer_failed:
        assert reason == ('The sources were retained, but the final answer could not be validated. '
            'Retry to continue from the saved research. ' + document_reason)
    else:
        assert reason == document_reason
        assert 'answer could not be validated' not in reason
    assert model.calls == calls
