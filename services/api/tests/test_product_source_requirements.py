"""Requested originals survive admission, reading and restart without becoming facts."""
import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_document_source_context import original
from test_product_dossiers import signed as signed
from test_product_iterative_research import start

from helvetic_lens import product_document_analysis as documents
from helvetic_lens import product_iterative_research as research
from helvetic_lens import product_source_requirements as ledger
from helvetic_lens.config import DomainError
from helvetic_lens.product_evidence_applicability import ScopedExtraction
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationPlan
from helvetic_lens.product_investigations import rows, scope
from helvetic_lens.product_question_renewal import parse_recoverable
from helvetic_lens.research_model_transport import EvidenceWire, shape_errors

QUESTION = 'Which rules apply? Read the Archive terms and the Archive access policy.'
SPANS = ['the Archive terms', 'the Archive access policy']
IDENTITY = 'Archive terms and access policy, issued by the Archive Board for its deposits.'


def planned(*, same_question=True, required=True):
    return research.ResearchPlan(objective=QUESTION, completion_criteria=['Read the requested originals.'], branches=[
        {'question': 'Which original rules govern archive access?' if same_question else f'What does original {i} require?',
            'query': f'Archive original rules {i}', 'purpose': 'Read the original archive rules.', 'priority': 5,
            **({'requested_sources': [span]} if required else {})} for i, span in enumerate(SPANS)])


def test_deduplicated_plan_keeps_both_original_tasks_and_repeated_plan_does_not_duplicate(signed):
    client, service, _, _ = signed
    _, result, _ = start(client, question=QUESTION)
    with service.db.session() as session:
        run = session.get(Investigation, result['id'])
        research.apply_plan(session, run, planned())
        expected = ledger.requirements(run)
        assert [item['requested_source'] for item in expected] == SPANS
        assert len({item['question_id'] for item in expected}) == 1
        owner = run.research_state['questions'][0]
        assert owner['branch_id']
        research.apply_plan(session, run, planned())
        assert ledger.requirements(run) == expected
        run.research_state = json.loads(json.dumps(run.research_state))
        assert ledger.requirements(run) == expected
        assert ledger.FIELD not in json.dumps(research.projection(run))
        assert all(ledger.FIELD not in json.dumps(value.document) for value in rows(session, InvestigationPlan, run))


def test_failed_duplicate_owner_rolls_back_entire_plan(signed):
    client, service, _, _ = signed
    _, result, _ = start(client, question=QUESTION)
    with service.db.session() as session:
        run = session.get(Investigation, result['id'])
        session.add(InvestigationBranch(**scope(run), query='Archive original rules 1', reason='An unowned bootstrap query.', checkpoint={}))
        session.flush()
        before, branches = deepcopy(run.research_state), len(rows(session, InvestigationBranch, run))
        with pytest.raises(DomainError, match='no admitted owner'):
            research.apply_plan(session, run, planned(same_question=False))
        assert run.research_state == before
        assert len(rows(session, InvestigationBranch, run)) == branches
        assert ledger.requirements(run) == []


@pytest.mark.parametrize('fault', ['invented', 'overflow'])
def test_unadmitted_originals_reject_plan_before_writing(signed, fault):
    client, service, _, _ = signed
    _, result, _ = start(client, question=QUESTION)
    with service.db.session() as session:
        run = session.get(Investigation, result['id'])
        value = planned(same_question=False)
        if fault == 'invented':
            value.branches[1].requested_sources = ['A model-invented requirement']
        else:
            value.branches.append(research.PlannedBranch(question='What is the additional source?',
                query='Additional original', purpose='Read another original.', priority=5, requested_sources=SPANS))
            run.research_state = {**run.research_state, 'limits': {**run.research_state['limits'], 'branches': 2}}
        before = deepcopy(run.research_state)
        with pytest.raises(DomainError):
            research.apply_plan(session, run, value)
        assert run.research_state == before


@pytest.mark.parametrize('legacy', [False, True])
def test_only_new_plans_own_admitted_literal_urls(signed, legacy):
    client, service, _, _ = signed
    question = 'Read https://example.org/original and explain its rules.'
    _, result, _ = start(client, question=question)
    with service.db.session() as session:
        run = session.get(Investigation, result['id'])
        value = planned(required=False)
        if not legacy:
            value = research.ResearchPlan.model_validate({**value.model_dump(), 'branches': [
                {**item.model_dump(), 'requested_sources': []} for item in value.branches]})
        research.apply_plan(session, run, value)
        requirements = ledger.requirements(run)
        assert ([item['direct_url'] for item in requirements] == ['https://example.org/original']) is not legacy
        if legacy:
            assert requirements == []


def test_plural_reader_identity_survives_optional_failure_without_approving_reading(monkeypatch):
    run = SimpleNamespace(id=str(uuid4()), question=QUESTION, research_state={'questions': [{'id': 'owner'}]})
    ledger.attach(run, 'owner', SPANS)
    source = original(run, [('page-1-text-1', IDENTITY)], [])
    work = {'phase': 'extract', 'source_id': source.id, 'input': {'question': QUESTION,
        'requested_sources': [{key: item[key] for key in ('id', 'requested_source')} for item in ledger.requirements(run)],
        'source': {'id': source.id, 'sha256': source.sha256, 'url': source.url, 'excerpts': deepcopy(source.snapshot['excerpts'])}}}
    documents.prepare_section(work, source)
    schema = documents.schema(ScopedExtraction)
    wire = EvidenceWire(work, schema, '')
    response = {'section_review': {'summary': 'The document identifies its issued terms and access policy.',
        'observations': [{'role': 'context', 'citation_ref': 1}]}, 'source_class': None,
        'requested_source_matches': [{'requirement_id': item['id'], 'citation_ref': 1} for item in ledger.requirements(run)]}
    assert wire.input['requested_sources'] == work['input']['requested_sources']
    assert not shape_errors(response, wire.schema, wire.schema['$defs'])
    parsed = schema.model_validate_json(wire.decode(json.dumps(response)))
    monkeypatch.setattr(research, 'apply_extraction', lambda *args: None)
    monkeypatch.setattr(research, 'rows', lambda *args: [])
    research.extract(None, run, source, parsed)
    expected = deepcopy(source.snapshot['requested_source_matches'])
    assert len(expected) == 2 and all(item['identity']['quote'] == IDENTITY for item in expected)
    assert all('read_complete' not in item for item in expected)
    response['requested_source_matches'][0]['citation_ref'] = 99999
    parsed = parse_recoverable(schema, wire.decode(json.dumps(response)),
        {'requested_source_matches': '_requested_sources_unavailable'})
    assert parsed.section_review.observations[0].quote == IDENTITY and parsed._requested_sources_unavailable
    research.extract(None, run, source, parsed)
    assert source.snapshot['requested_source_matches'] == expected
    # Same text/SHA from a different source ID must not be rebound to this source.
    forged = research.RequestedSourceMatch(requirement_id=expected[0]['requirement_id'],
        source_id=str(uuid4()), locator='page-1-text-1', quote=IDENTITY)
    source.snapshot = {**source.snapshot, 'requested_source_matches': [{'requirement_id': []}]}
    ledger.retain_matches(run, source, [forged])
    assert source.snapshot['requested_source_matches'] == []
