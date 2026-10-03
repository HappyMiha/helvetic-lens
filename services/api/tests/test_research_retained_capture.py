"""Saved-original reuse through native reading; scripted analysis is not semantic proof."""
import json
from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_product_dossiers import create
from test_product_dossiers import signed as signed
from test_product_exploration import start
from test_product_investigations import tick

from helvetic_lens import decision_sources, research_gateway
from helvetic_lens import product_document_reading as reading
from helvetic_lens import product_exploration as exploration
from helvetic_lens import product_exploration_progress as progress
from helvetic_lens import product_iterative_research as research
from helvetic_lens import research_knowledge as knowledge
from helvetic_lens.product_investigation_models import (
    Investigation,
    InvestigationBranch,
    InvestigationEvent,
    InvestigationSource,
)
from helvetic_lens.product_investigations import rows, scope, snapshot
from helvetic_lens.product_models import DossierEntry

URL = 'https://example.org/retained-original'
CAPTURED = '2020-02-03T10:00:00+00:00'
TEXTS = ['The original describes a conditional obligation, not a present event.',
         'The final page limits that obligation to organizations with authorization.']


def test_capture_date_preserves_legacy_context_and_admission_dates():
    admitted = datetime(2026, 10, 3, tzinfo=UTC)
    source = SimpleNamespace(id='copy', investigation_id='run', kind='public_source', title='Original',
        url=URL, sha256='a' * 64, created_at=admitted,
        snapshot={'retained_origin': {'source_id': 'original', 'captured_at': CAPTURED}})
    before = progress.record(source)
    assert before['captured_at'] == admitted.isoformat()  # Existing stored context remains byte-identical.
    assert knowledge.source_ref(source)['captured_at'] == CAPTURED  # Existing reader fallback stays intact.
    source.snapshot = {**source.snapshot, 'captured_at': CAPTURED}
    assert progress.record(source) == {**before, 'captured_at': CAPTURED}
    assert source.created_at == admitted


def prepared(signed, *, portions=1, refresh=False, cross_dossier=False):
    client, service, _, _ = signed
    _, child, _ = start(client)
    other = create(client)[0] if cross_dossier else None
    tick(service, child['id'])  # Ordinary admission and worker initialization.
    with service.db.session() as session:
        run = session.get(Investigation, child['id'])
        for branch in rows(session, InvestigationBranch, run):
            branch.status = 'completed'
        knowledge.recall(session, run, 'pharma', selected_ids=[])
        previous = Investigation(dossier_id=other['id'] if other else run.dossier_id, organization_id=run.organization_id,
            request_key=str(uuid4()), question='An earlier, different question.', status='completed')
        session.add(previous)
        session.flush()
        original_branch = InvestigationBranch(**scope(previous), query=previous.question, status='completed', reason='Saved original reading.')
        session.add(original_branch)
        session.flush()
        originals = []
        for n in range(portions):
            next_cursor = {'page': n + 1, 'offset': 0} if n + 1 < portions else None
            source, _ = snapshot(session, previous, {'status': 'complete', 'url': URL,
                'title': 'Fictional complete original', 'sha256': 'a' * 64, 'fetched_at': CAPTURED,
                'excerpts': [{'passage': f'page-{n + 1}-char-1', 'text': TEXTS[n]}],
                'text_truncated': bool(next_cursor), 'warnings': [], 'document_index': '0',
                'branch_id': original_branch.id, 'reading': {'contract': 'document-reading/v1',
                    'cursor': {'page': n, 'offset': 0}, 'next_cursor': next_cursor,
                    'pages': [n + 1, n + 1], 'characters_read': len(TEXTS[n]),
                    'complete': next_cursor is None},
                'analysis_completed': True, 'section_review': {'summary': 'OLD ANALYSIS CANARY'},
                'professional_facts': [{'value': 'OLD ANALYSIS CANARY'}]}, public=True)
            source.created_at = datetime(2020, 2, 3, 10, tzinfo=UTC)
            originals.append(source.id)
        original_branch.checkpoint = {'document_reads': {'0': {'source_ids': originals,
            'url': URL, 'sha256': 'a' * 64, 'read_complete': True, 'analysis_complete': True,
            'next_cursor': None}}}
        question = research.BranchDraft(question='What is the current obligation?', query='Find the original obligation',
            purpose='Read the complete record for the current question.', priority=5,
            refresh_retained_sources=refresh)
        qid = research.add_question(session, run, question)
        research.schedule_questions(session, run)
        branch = next(b for b in rows(session, InvestigationBranch, run) if b.checkpoint.get('question_id') == qid)
        branch.phase = 'read'
        branch.checkpoint = {**branch.checkpoint, 'read_as_found': True,
            'items': [{'id': 'approved-original', 'url': URL, 'title': 'Approved original'}],
            'decisions': [{'id': 'approved-original', 'url': URL, 'verdict': 'relevant'}],
            'read_index': 0, 'extract_index': 0, 'gate_index': 1, 'candidates': []}
        session.commit()
        return child['id'], branch.id, originals, original_branch.id


def prepare_work(session, run, branch):
    state = deepcopy(branch.checkpoint)
    work = {'research': True, 'phase': 'read', 'product': 'pharma', 'query': branch.query,
        'item': state['items'][state['read_index']], 'blocked_urls': []}
    reading.prepare(run, state, work)
    knowledge.prepare_capture(session, run, state, work)
    return work


@pytest.mark.parametrize('portions', [1, 2])
def test_native_reuses_all_original_portions_but_analyzes_current_question(signed, monkeypatch, portions):
    _, service, _, model = signed
    run_id, branch_id, originals, _ = prepared(signed, portions=portions)
    analyses = []

    async def no_fetch(*args, **kwargs):
        pytest.fail('An eligible retained original must not be downloaded again')

    async def analyze(system, user, **kwargs):
        data = json.loads(user)
        assert 'OLD ANALYSIS CANARY' not in user
        if kwargs['response_schema']['title'] == 'EarlyOrientation':
            source = data['sources'][0]
            return json.dumps({'interpretations': [{'source_id': source['id'],
                'quote': source['excerpts'][0]['text'], 'locator': source['excerpts'][0]['passage'],
                'meaning': 'The original describes a conditional obligation.',
                'why': 'The exact source text conditions the obligation.', 'signal': 'possible'}],
                'uncertainties': []})
        analyses.append(data)
        return json.dumps({'claims': [], 'entities': [], 'relationships': [],
            'section_review': {'coverage_fingerprint': data['document_section']['coverage_fingerprint'],
                'summary': 'The current question was considered against this exact original section.',
                'observations': [], 'cross_references': [], 'limitations': []}})

    monkeypatch.setattr(decision_sources, 'safe_inspect', no_fetch)
    monkeypatch.setattr(model, 'complete', analyze)
    for _ in range(portions * 3):
        tick(service, run_id)
        with service.db.session() as session:
            sources = rows(session, InvestigationSource, session.get(Investigation, run_id))
            if len(sources) == portions and all(s.snapshot.get('analysis_completed') for s in sources):
                break
    with service.db.session() as session:
        run, branch = session.get(Investigation, run_id), session.get(InvestigationBranch, branch_id)
        captured = rows(session, InvestigationSource, run)
        assert len(analyses) == len(captured) == portions
        assert all(v.get('question') == run.question and v.get('branch') == branch.query for v in analyses), analyses
        assert [v['source']['id'] for v in analyses] == [s.id for s in captured]
        assert all(s.id not in originals for s in captured)
        for source, original_id in zip(captured, originals, strict=True):
            old = session.get(InvestigationSource, original_id)
            assert source.snapshot['excerpts'] == old.snapshot['excerpts']
            assert source.snapshot['fetched_at'] == CAPTURED
            assert knowledge.source_ref(source)['captured_at'] == CAPTURED
            assert knowledge.captured_at(source) == CAPTURED
            assert source.created_at.year > 2020  # Admission/search pagination is not backdated.
            assert source.snapshot['analysis_completed']
        assert {s['captured_at'] for s in exploration.projection(session, run)['sources']} == {CAPTURED}
        events = [e for e in rows(session, InvestigationEvent, run) if e.kind == 'source_captured']
        assert len(events) == portions and all(e.created_at.year > 2020 for e in events)
        assert [p['source_id'] for p in run.research_state['core']['recall']['origin_pins']] == originals
        assert run.research_state['used']['source_fetches'] == 0
        steps = branch.checkpoint['steps']
        assert [s['execution']['provider'] for s in steps if s['phase'] == 'read'] == ['database'] * portions
        public = reading.projection(branch.checkpoint)
        assert public[0]['read_complete'] and not public[0]['analysis_complete']
        assert public[0]['characters_read'] == sum(len(t) for t in TEXTS[:portions])
        assert 'retained_capture_origins' not in json.dumps(public)
        assert knowledge.current(session, run)
        # Later validation includes the newly admitted origins, not only the initial recall.
        old.snapshot = {**old.snapshot, 'section_review': {'summary': 'Changed source receipt'}}
        session.commit()
        assert not knowledge.current(session, run)


@pytest.mark.parametrize('change', ['refresh', 'partial', 'missing_portion', 'truncated', 'excluded', 'private', 'other_dossier'])
def test_ineligible_or_refresh_original_is_not_admitted(signed, change):
    _, service, _, _ = signed
    run_id, branch_id, ids, original_branch_id = prepared(signed, portions=2, refresh=change == 'refresh',
        cross_dossier=change == 'other_dossier')
    with service.db.session() as session:
        run, branch = session.get(Investigation, run_id), session.get(InvestigationBranch, branch_id)
        origin = session.get(InvestigationSource, ids[-1])
        old_branch = session.get(InvestigationBranch, original_branch_id)
        if change in {'partial', 'missing_portion'}:
            state = deepcopy(old_branch.checkpoint)
            if change == 'partial':
                state['document_reads']['0']['read_complete'] = False
            else:
                state['document_reads']['0']['source_ids'] = ids[1:]
            old_branch.checkpoint = state
        elif change == 'truncated':
            origin.snapshot = {**origin.snapshot, 'text_truncated': True}
        elif change == 'excluded':
            session.add(DossierEntry(dossier_id=run.dossier_id, kind='source_review', request_key=str(uuid4()),
                url=URL, body='Excluded original.', data_json={'decision': 'exclude', 'revision': 1}))
        elif change == 'private':
            for key in ids:
                session.get(InvestigationSource, key).kind = 'team_contribution'
        session.commit()
        work = prepare_work(session, run, branch)
        assert 'retained_capture' not in work
        assert knowledge.current(session, run)  # No new authority was recorded by preparation.
        assert run.research_state['core']['recall']['origin_pins'] == []


@pytest.mark.parametrize('change', ['content', 'withdrawal'])
def test_native_revalidates_retained_original_after_dispatch_before_capture(signed, monkeypatch, change):
    _, service, _, _ = signed
    run_id, branch_id, ids, _ = prepared(signed)
    execute = research_gateway.execute

    async def changed(service, work, seconds):
        assert work['execution_route']['provider'] == 'database'
        result = await execute(service, work, seconds)
        with service.db.session() as session:
            old = session.get(InvestigationSource, ids[0])
            old.snapshot = {**old.snapshot, **({'allow_discovery': False} if change == 'withdrawal'
                else {'excerpts': [{'passage': 'p1', 'text': 'The original was replaced after preparation.'}]})}
            session.commit()
        return result

    monkeypatch.setattr(research_gateway, 'execute', changed)
    tick(service, run_id)
    with service.db.session() as session:
        run = session.get(Investigation, run_id)
        assert rows(session, InvestigationSource, run) == []
        branch = session.get(InvestigationBranch, branch_id)
        assert branch.checkpoint['steps'][-1]['status'] != 'completed'
        assert run.research_state['core']['recall']['origin_pins'] == []
