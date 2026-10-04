"""Duplicate captures reuse current whole-original analysis, never SHA-only approval."""
import json
from copy import deepcopy
from uuid import uuid4

import pytest
from test_product_dossiers import signed as signed
from test_product_investigations import start, tick

from helvetic_lens import product_document_analysis as analysis
from helvetic_lens import product_document_reconciliation as tree
from helvetic_lens.product_contributions import retry
from helvetic_lens.product_document_reading import incomplete, projection
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from helvetic_lens.product_investigation_worker import next_extraction, settle
from helvetic_lens.product_investigations import scope
from helvetic_lens.product_operations import fingerprint

QUOTE = "The original reports a proposed acquisition, subject to approval."


def seed(signed, monkeypatch, *, review_tree=False):
    client, service, _, _ = signed
    _, result, _ = start(client, "What is the status of the proposed acquisition?")
    identifiers = [str(uuid4()) for _ in range(2)]
    with service.db.session() as session:
        run = session.get(Investigation, result["id"])
        run.status, run.plan_version = "failed", 1
        sources = []
        for index, identifier in enumerate(identifiers):
            excerpts = [{"passage": "p1", "text": QUOTE}]
            snapshot = {"excerpts": excerpts, "reading": {"pages": None}, "document_index": "0",
                "allow_discovery": True, "research_question": f"Discovery query {index}"}
            if index:
                snapshot["duplicate_of"] = identifiers[0]
            else:
                snapshot["section_review"] = {"contract": analysis.CONTRACT, "sha256": "a" * 64,
                    "coverage_fingerprint": fingerprint({"sha256": "a" * 64, "excerpts": excerpts}),
                    "summary": "The acquisition remains conditional.", "cross_references": [], "limitations": [],
                    "observations": [{"statement": QUOTE, "role": "support", "locator": "p1", "quote": QUOTE}]}
            source = InvestigationSource(**scope(run), id=identifier, source_key=str(index) * 64,
                kind="public_source", title="Original announcement", url=f"https://example.org/original?alias={index}",
                sha256="a" * 64, snapshot=snapshot)
            sources.append(source)
            session.add(source)
        session.flush()
        branches = []
        for index, identifier in enumerate(identifiers):
            state = {"source_ids": [] if index else [identifier], "extract_index": 0 if index else 1,
                "read_index": 1, "items": [{}], "unchanged": 1,
                "document_reads": {"0": {"sha256": "a" * 64, "source_ids": [identifier],
                    "read_complete": True, "analysis_complete": False, "complete": False}}}
            branch = InvestigationBranch(**scope(run), query=f"Discovery query {index}",
                phase="extract", status="failed" if index else "completed", reason="Read the original.", checkpoint=state)
            session.add(branch)
            branches.append(branch)
        session.flush()
        canonical = branches[0]
        state = deepcopy(canonical.checkpoint)
        if review_tree:
            monkeypatch.setattr(tree, "INPUT_CHARACTERS", 1)
        work = {"query": canonical.query}
        analysis.prepare(session, run, state, work)
        data = {"coverage_fingerprint": work["input"]["coverage_fingerprint"],
            "findings": [{"source_id": identifiers[0], "statement": QUOTE, "role": "support", "locator": "p1", "quote": QUOTE}],
            "cross_reference_checks": [], "limitations": []}
        if review_tree:
            data["synopsis"] = "The proposed acquisition remains conditional."
        parsed = (tree.ReviewNode if review_tree else analysis.DocumentReview).model_validate(data)
        analysis.apply(session, run, state, work, parsed)
        if review_tree and not state["document_reads"]["0"]["complete"]:
            completion = {"query": canonical.query}
            analysis.prepare(session, run, state, completion)
            assert completion["review_tree_complete"]
        assert state["document_reads"]["0"]["complete"]
        state["steps"] = [{"phase": "document_review", "document_index": "0", "status": "completed",
            "execution": {"input_fingerprint": fingerprint({"input": work["input"], "query": work["query"]})}}]
        canonical.checkpoint = state
        session.commit()
        return service, run.id, [b.id for b in branches], identifiers


@pytest.mark.parametrize("review_tree", [False, True])
def test_current_analysis_reuses_original_provenance_and_retry_completes_without_reanalysis(signed, monkeypatch, review_tree):
    service, run_id, branches, identifiers = seed(signed, monkeypatch, review_tree=review_tree)
    with service.db.session() as session:
        run = session.get(Investigation, run_id)
        canonical, duplicate = [session.get(InvestigationBranch, identifier) for identifier in branches]
        before = deepcopy(canonical.checkpoint)
        retry(session, run)
        assert duplicate.status == "queued"
        state = deepcopy(duplicate.checkpoint)
        assert analysis.refresh_duplicate_analysis(session, run, state, schedule_missing=True)
        doc = state["document_reads"]["0"]
        assert doc["complete"] and doc["analysis_complete"]
        assert doc["source_ids"] == [identifiers[1]]
        assert doc["reconciliation"] == before["document_reads"]["0"]["reconciliation"]
        assert doc["reconciliation"]["findings"][0]["source_id"] == identifiers[0]
        assert state["source_ids"] == [] and canonical.checkpoint == before
        settle(duplicate, state)
        assert duplicate.status == "completed"
        assert not incomplete([duplicate], session, run)
        public = projection(state, session, run)[0]
        assert public["complete"] and "duplicate_analysis" not in public and "source_ids" not in public
        assert not projection(state)[0]["complete"]  # No current dependency check, no completion claim.
        run.question = "Has approval actually been granted?"
        changed = projection(state, session, run)[0]
        assert not changed["complete"] and "reconciliation" not in changed
        assert doc["complete"]  # Reader freshness does not mutate the saved alias receipt.


@pytest.mark.parametrize("fault", ["missing", "cycle", "hash", "run", "organization", "dossier", "withdrawn",
    "incomplete", "stale_section", "missing_question_proof", "multiple_unresolved", "empty_id", "false_link"])
def test_ineligible_dependency_never_supplies_completion_or_citations(signed, monkeypatch, fault):
    service, run_id, branches, identifiers = seed(signed, monkeypatch)
    with service.db.session() as session, session.no_autoflush:
        run = session.get(Investigation, run_id)
        canonical, duplicate = [session.get(InvestigationBranch, identifier) for identifier in branches]
        source, copy = [session.get(InvestigationSource, identifier) for identifier in identifiers]
        state = deepcopy(duplicate.checkpoint)
        assert analysis.refresh_duplicate_analysis(session, run, state)
        if fault == "missing":
            copy.snapshot = {**copy.snapshot, "duplicate_of": str(uuid4())}
        elif fault == "cycle":
            source.snapshot = {**source.snapshot, "duplicate_of": copy.id}
        elif fault == "hash":
            source.sha256 = "b" * 64
        elif fault in {"run", "organization", "dossier"}:
            setattr(source, {"run": "investigation_id", "organization": "organization_id", "dossier": "dossier_id"}[fault], str(uuid4()))
        elif fault == "withdrawn":
            source.snapshot = {**source.snapshot, "allow_discovery": False}
        elif fault == "incomplete":
            canonical.checkpoint["document_reads"]["0"]["analysis_complete"] = False
        elif fault == "stale_section":
            source.snapshot = {**source.snapshot, "excerpts": [{"passage": "p1", "text": "Changed original."}]}
        elif fault == "missing_question_proof":
            canonical.checkpoint["steps"] = []
        elif fault == "multiple_unresolved":
            state["document_reads"]["0"]["source_ids"].append(str(uuid4()))
        elif fault == "empty_id":
            state["document_reads"]["0"]["source_ids"].append(None)
        else:
            source.snapshot = {**source.snapshot, "duplicate_of": ""}
        public = projection(state, session, run)[0]
        assert not public["complete"] and not public["analysis_complete"]
        assert "reconciliation" not in public and "duplicate_analysis" not in public


def test_unavailable_canonical_analysis_schedules_each_local_section_once_for_ordinary_extraction(signed, monkeypatch):
    service, run_id, branches, identifiers = seed(signed, monkeypatch)
    with service.db.session() as session:
        run = session.get(Investigation, run_id)
        canonical, duplicate = [session.get(InvestigationBranch, identifier) for identifier in branches]
        canonical.checkpoint["document_reads"]["0"]["analysis_complete"] = False
        state = deepcopy(duplicate.checkpoint)
        state["retry_indices"] = []
        state["document_reads"]["0"]["review_failed"] = True
        assert analysis.refresh_duplicate_analysis(session, run, state, schedule_missing=True)
        assert state["source_ids"] == [identifiers[1]] and not state["retry_indices"]
        assert not state["document_reads"]["0"]["complete"]
        assert not state["document_reads"]["0"].get("review_failed")
        assert not analysis.refresh_duplicate_analysis(session, run, state, schedule_missing=True)
        duplicate.status = "queued"
        settle(duplicate, state)
        assert duplicate.phase == "extract" and duplicate.status == "queued"
        source = session.get(InvestigationSource, identifiers[1])
        work = {"input": {"question": run.question, "source": {"id": source.id}}}
        analysis.prepare_section(work, source)
        assert work["input"]["source"]["excerpts"] == source.snapshot["excerpts"]
        assert work["input"]["document_section"]["coverage_fingerprint"]
        state["failed_extract_indices"] = [0]
        next_extraction(state)
        assert state["extract_index"] == 1
        assert not analysis.refresh_duplicate_analysis(session, run, state, schedule_missing=True)
        assert not analysis.ready_to_review(state)  # Failure uses explicit retry, never a repeated skip.


@pytest.mark.parametrize('change,scope_status', [(None, 'unassessed'), (None, 'assessed'), ('legacy', 'unassessed'),
    ('alias_withdrawn', 'unassessed'), ('original_withdrawn', 'unassessed'), ('capture_changed', 'unassessed')])
def test_scheduled_duplicate_reaches_real_worker_analysis_with_current_fences(signed, monkeypatch, change, scope_status):
    from test_product_dossiers import ROOT, post

    from helvetic_lens import product_evidence_applicability as applicability
    from helvetic_lens import product_exploration as exploration
    from helvetic_lens import product_iterative_research as research
    from helvetic_lens import product_read_relevance as relevance
    from helvetic_lens import product_source_recovery as recovery
    from helvetic_lens.product_exploration import sources as visible_sources
    from helvetic_lens.product_investigation_models import ClaimEvidence
    from helvetic_lens.product_investigations import rows

    service, run_id, branches, identifiers = seed(signed, monkeypatch)
    model = signed[3]
    with service.db.session() as session:
        run = session.get(Investigation, run_id)
        canonical, duplicate = [session.get(InvestigationBranch, identifier) for identifier in branches]
        current = deepcopy(canonical.checkpoint)
        current['document_reads']['0'].update(complete=False, analysis_complete=False)
        current['items'] = [{'title': 'Original announcement', 'url': 'https://example.org/original?alias=0'}]
        canonical.checkpoint = current
        canonical.status = 'failed'
        question_id = str(uuid4())
        run.research_state = {**research.initial(research.Limits()), 'exploration': {
            'read_relevance_contract': relevance.CONTRACT, 'recovery_contract': recovery.CONTRACT,
            'applicability_contract': applicability.CONTRACT},
            'questions': [{'id': question_id, 'question': run.question, 'query': duplicate.query,
                'query_key': research.query_key(duplicate.query), 'purpose': 'Read the original.',
                'priority': 1, 'depth': 0, 'kind': 'planned', 'status': 'investigating', 'branch_id': duplicate.id,
                'claim_id': None}]}
        run.status, duplicate.status = 'queued', 'queued'
        duplicate.checkpoint = {**duplicate.checkpoint, 'question_id': question_id,
            'iterative': True, 'reflection_done': True,
            'items': [{'title': 'Original announcement', 'url': 'https://example.org/original?alias=1'}]}
        applicability.initialize(session, run)
        session.commit()
    calls = []

    async def complete(system, text, **options):
        value = json.loads(text)
        title = options['response_schema']['title']
        calls.append(title)
        if title == 'ResearchExtraction':
            assert value['source']['id'] == identifiers[1]
            assert value['source']['excerpts'] == [{'passage': 'p1', 'text': QUOTE}]
            assert value['read_question']['question_id'] == question_id
            assert value['evidence_applicability']['readings'] == []
            if change in {'alias_withdrawn', 'original_withdrawn', 'capture_changed'}:
                with service.db.session() as session:
                    source = session.get(InvestigationSource,
                        identifiers[0] if change == 'original_withdrawn' else identifiers[1])
                    source.snapshot = {**source.snapshot, **({'excerpts': [{'passage': 'p1', 'text': 'Changed original.'}]}
                        if change == 'capture_changed' else {'allow_discovery': False})}
                    session.commit()
            return json.dumps({'claims': [{'statement': QUOTE, 'existing_claim_id': None,
                    'relation': 'SUPPORTS', 'quote': QUOTE, 'locator': 'p1'}], 'entities': [], 'relationships': [],
                'applicability_checks': [{'source_id': identifiers[1], 'policy_id': 'legal-research/v1',
                    'dimension': 'subject', 'requested_detail': 'proposed acquisition',
                    'source_detail': 'proposed acquisition', 'relation': 'aligned',
                    'reason': 'Both the question and the original describe a proposed acquisition.',
                    'quote': QUOTE, 'locator': 'p1'}] if scope_status == 'assessed' else [],
                'section_review': {'coverage_fingerprint': value['document_section']['coverage_fingerprint'],
                    'summary': 'The acquisition remains conditional.', 'observations': [
                        {'statement': QUOTE, 'role': 'support', 'quote': QUOTE, 'locator': 'p1'}],
                    'cross_references': [], 'limitations': []}})
        assert title == 'DocumentReview'
        source_id = value['sections'][0]['source_id']
        assert source_id == identifiers[1] if len(calls) == 2 else source_id == identifiers[0]
        return json.dumps({'coverage_fingerprint': value['coverage_fingerprint'], 'findings': [
            {'source_id': source_id, 'statement': QUOTE, 'role': 'support', 'quote': QUOTE, 'locator': 'p1'}],
            'cross_reference_checks': [], 'limitations': []})

    monkeypatch.setattr(model, 'complete', complete)
    tick(service, run_id)
    with service.db.session() as session:
        run = session.get(Investigation, run_id)
        branch = session.get(InvestigationBranch, branches[1])
        source = session.get(InvestigationSource, identifiers[1])
        assert calls == ['ResearchExtraction'], 'The scheduled fallback must not be deterministically skipped'
        assert not branch.checkpoint['document_reads']['0']['analysis_complete']
        assert identifiers[1] not in visible_sources(session, run), 'Analysis is not general duplicate visibility'
        if change in {'alias_withdrawn', 'original_withdrawn', 'capture_changed'}:
            assert analysis.section(source) is None
            assert branch.checkpoint['steps'][-1]['status'] == 'unavailable'
            assert not rows(session, ClaimEvidence, run)
            assert not run.research_state['exploration'].get('applicability_readings')
            return
        assert analysis.section(source) and branch.phase == 'document_review'
        assert branch.checkpoint['steps'][-1]['status'] == 'completed'
        assert [e.source_id for e in rows(session, ClaimEvidence, run)] == [identifiers[1]]
        assert exploration.adaptive_current(session, run)
        reading = run.research_state['exploration']['applicability_readings'][0]
        assert reading['status'] == scope_status
        assert bool(reading['checks']) == (scope_status == 'assessed')
        assert reading['duplicate_reading_dependency']['branch_id'] == branch.id
        if change == 'legacy':
            # The prior native stored the exact reading and scheduler receipt,
            # but predates the durable private dependency field.
            data = deepcopy(run.research_state)
            old = data['exploration']['applicability_readings'][0]
            old.pop('duplicate_reading_dependency')
            old['fingerprint'] = fingerprint({k: v for k, v in old.items() if k != 'fingerprint'})
            data['exploration']['applicability_reading_manifest'] = [old['fingerprint']]
            run.research_state = data
            session.commit()
    tick(service, run_id)
    with service.db.session() as session:
        run = session.get(Investigation, run_id)
        branch = session.get(InvestigationBranch, branches[1])
        document = branch.checkpoint['document_reads']['0']
        assert calls == ['ResearchExtraction', 'DocumentReview']
        assert document['complete'] and document['analysis_complete']
        assert document['reconciliation']['findings'][0]['source_id'] == identifiers[1]
        assert not document.get('duplicate_analysis'), 'Completion came from a fresh whole-original review'
        assert not session.get(InvestigationBranch, branches[0]).checkpoint['document_reads']['0']['analysis_complete']
        assert identifiers[1] not in visible_sources(session, run)
        assert exploration.adaptive_current(session, run), 'Completed reconciliation must retain reading freshness'
        context = applicability.context(run, {'sources': [{'id': identifiers[0]}]})
        assert context['readings'] == [], 'A private duplicate record is not general provider context'
        assert 'duplicate_reading_dependency' not in json.dumps(
            applicability.context(run, {'sources': [{'id': identifiers[1]}]}))
        if change != 'legacy':
            state = deepcopy(branch.checkpoint)
            state.pop('duplicate_analysis_fallbacks')
            branch.checkpoint = state
            session.commit()
            assert exploration.adaptive_current(session, run), 'Completed provenance does not depend on pending scheduling'
        for fault in ('question', 'sha', 'withdrawn', 'capture', 'section', 'receipt'):
            original_question = run.question
            original = session.get(InvestigationSource, identifiers[0])
            original_sha, original_snapshot = original.sha256, deepcopy(original.snapshot)
            alias = session.get(InvestigationSource, identifiers[1])
            alias_snapshot, checkpoint = deepcopy(alias.snapshot), deepcopy(branch.checkpoint)
            if fault == 'question':
                run.question += ' Has approval been granted?'
            elif fault == 'sha':
                original.sha256 = 'b' * 64
            elif fault in {'withdrawn', 'capture'}:
                original.snapshot = {**original.snapshot, **({'allow_discovery': False} if fault == 'withdrawn'
                    else {'excerpts': [{'passage': 'p1', 'text': 'Changed original.'}]})}
            elif fault == 'section':
                alias.snapshot = {k: v for k, v in alias.snapshot.items() if k != 'section_review'}
            else:
                altered = deepcopy(branch.checkpoint)
                altered['steps'][0]['status'] = 'unavailable'
                branch.checkpoint = altered
            assert not applicability.current(session, run), fault
            run.question, original.sha256, original.snapshot = original_question, original_sha, original_snapshot
            alias.snapshot, branch.checkpoint = alias_snapshot, checkpoint
        assert applicability.current(session, run)
        path = f'{ROOT}/{run.dossier_id}/investigations/{run.id}/control'
        revision, generation = run.revision, run.generation
        session.commit()
    response = post(signed[0], path, {'action': 'retry', 'expected_revision': revision})
    assert response.status_code == 200, response.text
    tick(service, run_id)
    with service.db.session() as session:
        run = session.get(Investigation, run_id)
        assert run.generation == generation + 1
        assert run.status != 'paused', run.stop_reason
        assert calls == ['ResearchExtraction', 'DocumentReview', 'DocumentReview']
        assert exploration.adaptive_current(session, run)
        assert identifiers[1] not in visible_sources(session, run)


@pytest.mark.parametrize('change', ['unscheduled', 'question', 'generation', 'cycle', 'foreign_run', 'withdrawn'])
def test_duplicate_extraction_exception_requires_current_scheduled_chain(signed, monkeypatch, change):
    service, run_id, branches, identifiers = seed(signed, monkeypatch)
    with service.db.session() as session, session.no_autoflush:
        run = session.get(Investigation, run_id)
        canonical, duplicate = [session.get(InvestigationBranch, identifier) for identifier in branches]
        canonical.checkpoint['document_reads']['0']['analysis_complete'] = False
        state = deepcopy(duplicate.checkpoint)
        assert analysis.refresh_duplicate_analysis(session, run, state, schedule_missing=True)
        assert analysis.scheduled_duplicate_analysis(session, run, state, identifiers[1])
        if change == 'unscheduled':
            state.pop('duplicate_analysis_fallbacks')
        elif change == 'question':
            run.question += ' A different question.'
        elif change == 'generation':
            run.generation += 1
        else:
            source = session.get(InvestigationSource, identifiers[0])
            if change == 'cycle':
                source.snapshot = {**source.snapshot, 'duplicate_of': identifiers[1]}
            elif change == 'foreign_run':
                source.investigation_id = str(uuid4())
            else:
                source.snapshot = {**source.snapshot, 'allow_discovery': False}
        assert analysis.scheduled_duplicate_analysis(session, run, state, identifiers[1]) is None
