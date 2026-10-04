"""Planner interpretations own source work without claiming to quote the user."""
import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from test_product_dossiers import signed as signed
from test_product_iterative_research import start
from test_product_requested_originals import IDENTITY, complete, seed
from test_product_source_requirements import QUESTION, SPANS, planned

from helvetic_lens import product_iterative_research as research
from helvetic_lens import product_requested_originals as originals
from helvetic_lens import product_research_mission as mission
from helvetic_lens import product_source_requirements as ledger
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.product_document_analysis import schema as section_schema
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from helvetic_lens.product_investigations import rows, scope
from helvetic_lens.research_model_transport import EvidenceWire
from helvetic_lens.research_synthesis_resume import DraftCheckpoint

NAMES = ['Archive Board official terms', 'Archive Board access conditions']


def interpreted(*, same_question=True):
    value = planned(same_question=same_question).model_dump()
    for branch, name in zip(value['branches'], NAMES, strict=True):
        branch.pop('requested_sources')
        branch['source_targets'] = [name]
    return research.ResearchPlan.model_validate(value)


def test_typed_legacy_plans_do_not_invent_v2_fields_and_followups_cannot_admit_targets():
    old = [research.PlannedBranch(question=f'Which original rule {index} applies?',
        query=f'Archive rule {index}', purpose='Read the original rule.', priority=5,
        requested_sources=[]) for index in (1, 2)]
    parsed = research.ResearchPlan(objective=QUESTION, completion_criteria=['Read the originals.'], branches=old)
    assert all('requested_sources' in item.model_fields_set and 'source_targets' not in item.model_fields_set
        for item in parsed.branches)
    with pytest.raises(ValidationError):
        research.BranchDraft.model_validate({**old[0].model_dump(exclude={'requested_sources', 'source_targets'}),
            'source_targets': [NAMES[0]]})


def test_interpreted_plan_dedup_retains_legacy_ownership_and_json_restart(signed):
    client, service, _, _ = signed
    _, result, _ = start(client, question=QUESTION)
    with service.db.session() as session:
        run = session.get(Investigation, result['id'])
        research.apply_plan(session, run, planned())
        previous = deepcopy(run.research_state['questions'][0][ledger.FIELD])
        research.apply_plan(session, run, interpreted())
        values = ledger.requirements(run)
        assert [value['requested_source'] for value in values] == [*SPANS, *NAMES]
        assert [value['origin'] for value in values] == ['literal_request'] * 2 + ['planner_interpretation'] * 2
        assert len({value['question_id'] for value in values}) == 1
        assert run.research_state['questions'][0][ledger.FIELD] == previous
        assert run.research_state['questions'][0][ledger.TARGET_FIELD]['contract'] == ledger.TARGET_CONTRACT
        research.apply_plan(session, run, interpreted())
        run.research_state = json.loads(json.dumps(run.research_state))
        assert ledger.requirements(run) == values
        assert run.research_state['questions'][0][ledger.FIELD] == previous
        projected = json.dumps(research.public_questions(run.research_state['questions']))
        assert ledger.FIELD not in projected and ledger.TARGET_FIELD not in projected
        run.question += ' Revised question.'
        assert ledger.requirements(run) == []


def test_interpreted_plan_rolls_back_if_a_duplicate_query_has_no_owner(signed):
    client, service, _, _ = signed
    _, result, _ = start(client, question=QUESTION)
    with service.db.session() as session:
        run = session.get(Investigation, result['id'])
        session.add(InvestigationBranch(**scope(run), query='Archive original rules 1',
            reason='Unowned bootstrap query.', checkpoint={}))
        session.flush()
        before, count = deepcopy(run.research_state), len(rows(session, InvestigationBranch, run))
        with pytest.raises(DomainError, match='no admitted owner'):
            research.apply_plan(session, run, interpreted(same_question=False))
        assert run.research_state == before and len(rows(session, InvestigationBranch, run)) == count


def test_new_plan_host_admits_literal_urls_without_promoting_a_model_url_name(signed):
    client, service, _, _ = signed
    url = 'https://example.org/original'
    question = f'Read {url} and explain its rules.'
    _, result, _ = start(client, question=question)
    with service.db.session() as session:
        run = session.get(Investigation, result['id'])
        plan = interpreted()
        plan.branches[0].source_targets = [url]
        plan.branches[1].source_targets = []
        research.apply_plan(session, run, plan)
        values = ledger.requirements(run)
        assert len(values) == 2 and {value['origin'] for value in values} == {'planner_interpretation', 'submitted_url'}
        assert len({value['id'] for value in values}) == 2
        assert all(value['requested_source'] == url for value in values)
        model, submitted = values
        assert 'direct_url' not in model and submitted['direct_url'] == url
        assert all(ledger.FIELD not in owner for owner in run.research_state['questions'])
        # New metadata does not turn planned URL text into submitted-source proof.
        assert originals.outcomes(session, run)[0]['status'] == 'not_identified'


@pytest.mark.parametrize('fault', ['changed_origin', 'bad_origin', 'invented_submitted_url', 'changed_question'])
def test_target_receipt_provenance_cannot_be_rewritten(fault):
    run = SimpleNamespace(question=QUESTION, research_state={'questions': [{'id': 'owner'}]})
    ledger.attach_targets(run, 'owner', NAMES)
    assert len(ledger.requirements(run)) == 2
    data = deepcopy(run.research_state)
    first = data['questions'][0][ledger.TARGET_FIELD]['requirements'][0]
    if fault == 'changed_origin':
        first['origin'] = 'submitted_url'
    elif fault == 'bad_origin':
        first['origin'] = []
    elif fault == 'invented_submitted_url':
        first.update(origin='submitted_url', requested_source='https://example.org/model-only')
        first['id'] = ledger.target_identifier(run.question, first['requested_source'], first['origin'])
    else:
        run.question += ' Another question.'
    run.research_state = data
    values = ledger.requirements(run)
    assert values == [] if fault == 'changed_question' else [value['requested_source'] for value in values] == NAMES[1:]
    with pytest.raises(DomainError):
        ledger.attach_targets(run, 'owner', ['https://example.org/model-only'], origin='submitted_url')


def test_v2_cited_identity_keeps_legacy_matches_and_still_requires_current_full_reading(signed):
    service, run_id, branch_id, source_ids, owner_id = seed(signed)
    with service.db.session() as session:
        run = session.get(Investigation, run_id)
        source = session.get(InvestigationSource, source_ids[0])
        branch = session.get(InvestigationBranch, branch_id)
        old = deepcopy(source.snapshot['requested_source_matches'])
        ledger.attach_targets(run, owner_id, [NAMES[0]])
        requirement = next(item for item in ledger.requirements(run) if item['origin'] == 'planner_interpretation')
        proposal = research.RequestedSourceMatch(requirement_id=requirement['id'], source_id=source.id,
            locator='p1', quote=IDENTITY)
        ledger.retain_matches(run, source, [proposal])
        assert source.snapshot['requested_source_matches'][:len(old)] == old
        value = source.snapshot['requested_source_matches'][-1]
        assert value['contract'] == ledger.TARGET_MATCH_CONTRACT and value['origin'] == 'planner_interpretation'
        assert value['identity']['quote'] == IDENTITY
        complete(session, run, branch, [source])
        status = next(item for item in originals.outcomes(session, run) if item['id'] == requirement['id'])
        assert status['status'] == 'matched_read' and status['origin'] == 'planner_interpretation'
        assert status['identity_basis'] == 'quoted_match'
        for change in ('origin', 'quote', 'legacy_contract'):
            invalid = deepcopy(value)
            if change == 'origin':
                invalid['origin'] = 'submitted_url'
            elif change == 'quote':
                invalid['identity']['quote'] = 'An invented source identity.'
            else:
                invalid['contract'] = ledger.MATCH_CONTRACT
            assert not originals.valid_match(invalid, source, requirement, run.question)
        state = deepcopy(branch.checkpoint)
        state['document_reads']['0']['read_complete'] = False
        branch.checkpoint = state
        assert next(item for item in originals.outcomes(session, run) if item['id'] == requirement['id'])['status'] == 'reading_incomplete'
        source.snapshot = {**source.snapshot, 'allow_discovery': False}
        assert next(item for item in originals.outcomes(session, run) if item['id'] == requirement['id'])['status'] == 'not_identified'


def test_reader_receives_origin_and_matches_only_exact_bounded_target_ids():
    source_id = str(uuid4())
    run = SimpleNamespace(question=QUESTION, research_state={'questions': [{'id': 'owner'}]})
    ledger.attach_targets(run, 'owner', NAMES)
    required = [{key: item[key] for key in ('id', 'requested_source', 'origin')} for item in ledger.requirements(run)]
    work = {'phase': 'extract', 'source_id': source_id, 'input': {'question': QUESTION,
        'source': {'id': source_id, 'excerpts': [{'passage': 'p1', 'text': IDENTITY}]},
        'document_section': {'coverage_fingerprint': 'a' * 64}, 'requested_sources': required}}
    schema = section_schema(research.ResearchExtraction)
    wire = EvidenceWire(work, schema, '')
    assert wire.input['requested_sources'] == required
    assert wire.schema['$defs']['RequestedSourceMatch']['properties']['requirement_id']['enum'] == [item['id'] for item in required]
    response = {'section_review': {'summary': 'The document identifies its own issued terms.',
        'observations': [{'role': 'context', 'citation_ref': 1}]},
        'requested_source_matches': [{'requirement_id': required[0]['id'], 'citation_ref': 1}]}
    value = schema.model_validate_json(wire.decode(json.dumps(response)))
    assert value.requested_source_matches[0].quote == IDENTITY
    assert value.requested_source_matches[0].source_id == source_id


def test_planned_notice_is_workflow_information_not_a_user_requirement_or_answer():
    points = [{'statement': 'An independently checked point.', 'evidence': []}]
    answer = {'status': 'possible_answer', 'points': points, 'limitations': ['An independent qualification.']}
    outcome = {'id': 'target', 'question_id': 'owner', 'requested_source': NAMES[0],
        'origin': 'planner_interpretation', 'status': 'not_identified',
        'reason': 'The planned source target has not been identified in current completed acquisition work.'}
    delivered, _ = mission.with_source_work(answer, [outcome])
    assert delivered['points'] == points and answer['status'] == 'possible_answer'
    assert delivered['status'] == 'partial'
    assert delivered['limitations'][0] == answer['limitations'][0]
    assert delivered['limitations'][1].startswith('Planned source target “Archive Board official terms”')
    assert 'Requested source' not in delivered['limitations'][1]


def test_new_plan_wire_binding_does_not_reuse_previous_word_reference_preparation():
    work = {'phase': 'plan', 'input': {'question': QUESTION, 'branch_slots': 2, 'available_catalogues': {}}}
    wire = EvidenceWire(work, research.ResearchPlan, '')
    old_input = {**deepcopy(wire.input), 'question_words': [{'ref': 1, 'text': 'Which'}]}
    old_schema = deepcopy(wire.schema)
    branch = old_schema['$defs']['PlannedBranch']
    branch['properties']['requested_sources'] = {'type': 'array', 'items': {'type': 'object'}}
    branch['properties'].pop('source_targets')
    branch['required'] = [key if key != 'source_targets' else 'requested_sources' for key in branch['required']]
    saved = {}
    before = DraftCheckpoint(saved, Settings(_env_file=None), 'previous word selection protocol', 'same-review',
        old_schema, json.dumps(old_input), {})
    before.save('draft', 'INVALID OLD PLAN', [], {})
    assert DraftCheckpoint(json.loads(json.dumps(saved)), Settings(_env_file=None), wire.system, 'same-review',
        wire.schema, json.dumps(wire.input), {}).value is None
