"""Provider JSON gets simpler without relaxing canonical evidence validation."""
import json
from copy import deepcopy

import pytest
from research_pack_fixtures import atomic_pack_model

from helvetic_lens import product_document_analysis as documents
from helvetic_lens import research_gateway
from helvetic_lens.product_evidence_applicability import ScopedExtraction
from helvetic_lens.product_exploration import AssessedBriefing
from helvetic_lens.research_model_transport import EvidenceWire, windows


def section():
    text = 'The fictional mountain measures 123 metres above the local datum. The record does not compare heights above sea level.'
    return {'phase': 'extract', 'source_id': 'a' * 36, 'input': {
        'question': 'Compare the mountain measurements.',
        'source': {'id': 'a' * 36, 'excerpts': [{'passage': 'p00028', 'text': text}]},
        'existing_claims': [{'statement': 'Unsupported earlier guess', 'id': 'b' * 36}],
        'document_section': {'coverage_fingerprint': 'c' * 64},
        'read_question': {'question_id': 'd' * 36, 'question': 'Compare the measurements.'}}}


def test_new_plan_explicitly_chooses_catalogues_and_general_search_skips_unrelated_feeds(monkeypatch):
    import asyncio

    from helvetic_lens import decision_search, search_channels
    from helvetic_lens.config import Settings
    from helvetic_lens.product_iterative_research import ResearchPlan

    wire = EvidenceWire({'phase': 'plan', 'input': {'question': 'Compare two definitions.', 'branch_slots': 2,
        'available_catalogues': {'finma_news': 'FINMA current news feed'}}}, ResearchPlan, '')
    data = {'objective': 'Compare the original definitions.', 'completion_criteria': ['Both definitions compared.'],
        'branches': [{'question': f'What does definition {n} mean?', 'query': f'Original definition {n}',
            'purpose': 'Find the original source.', 'priority': 5, 'catalogues': []} for n in (1, 2)]}
    for missing in (None, 'omitted'):
        bad = deepcopy(data)
        if missing is None:
            bad['branches'][0]['catalogues'] = None
        else:
            bad['branches'][0].pop('catalogues')
        with pytest.raises(ValueError):
            wire.decode(json.dumps(bad))
    plan = ResearchPlan.model_validate_json(wire.decode(json.dumps(data)))
    calls = []
    async def broad(*args, **kwargs):
        calls.append('web')
        return {'items': []}
    async def catalogue(*args, **kwargs):
        pytest.fail('A general question must not dispatch an unrelated catalogue.')
    monkeypatch.setattr(decision_search, 'retrieve', broad)
    monkeypatch.setattr(search_channels, 'direct_search', catalogue)
    result = asyncio.run(decision_search.federated_retrieve(Settings(web_search_provider='searxng'),
        plan.branches[0].query, 'web', 'deep', 'legal', selected_catalogues=plan.branches[0].catalogues))
    assert calls == ['web'] and result['items'] == []


def test_section_contract_keeps_exact_quotes_and_does_not_mutate_previous_claims():
    work = section()
    before = deepcopy(work)
    schema = documents.schema(ScopedExtraction)
    wire = EvidenceWire(work, schema, 'Complex original contract', shared_answer=False)
    assert work == before
    assert 'existing_claims' not in wire.input
    assert set(wire.schema['properties']) == {'section_review', 'read_relevance'}
    assert 'Assertion' not in wire.schema['$defs']
    raw = json.dumps({'section_review': {'summary': 'This section uses a local datum.',
        'observations': [{'role': 'support', 'citation_ref': 1, 'reason': 'Why this quote is relevant.',
            'statement': 'A model paraphrase must not replace the exact original.'}], 'limitations': ['Sea-level comparison is not supplied.']},
        'read_relevance': {'citation_ref': 1, 'category': 'context', 'reason': 'The datum differs from sea level.'}})
    parsed = schema.model_validate_json(wire.decode(raw))
    assert parsed.claims[0].existing_claim_id is None
    assert parsed.claims[0].quote == work['input']['source']['excerpts'][0]['text']
    assert parsed.claims[0].locator == 'p00028'
    assert parsed.read_relevance.source_id == 'a' * 36 and parsed.read_relevance.question_id == 'd' * 36
    assert parsed.section_review.coverage_fingerprint == 'c' * 64
    assert not research_gateway.extraction_citation_errors(parsed, work)
    parsed.section_review.observations[0].statement = 'The fictional mountain measures 999 metres.'
    assert research_gateway.extraction_citation_errors(parsed, work)


@pytest.mark.parametrize('reference', [True, '1', 0, -1, 2, None])
def test_unknown_or_coerced_reference_cannot_become_evidence(reference):
    wire = EvidenceWire(section(), documents.schema(ScopedExtraction), '')
    with pytest.raises(ValueError):
        wire.decode(json.dumps({'section_review': {'summary': 'A source section.', 'observations': [{'role': 'support', 'citation_ref': reference}]}}))


def test_long_passages_are_fully_available_in_contiguous_windows():
    text = ' '.join(f'Word{i:04d}' for i in range(2000))
    values = list(windows(text))
    assert all(10 <= len(value) <= 600 and value in text for value in values)
    assert values[0].startswith('Word0000') and values[-1].endswith('Word1999')
    assert all(word in ' '.join(values) for word in text.split())


def test_final_answer_references_only_current_source_excerpts():
    work = {'phase': 'brief', 'input': {'sources': [section()['input']['source']],
        'previous_briefing': {'quote': 'Do not turn earlier text into evidence.', 'locator': 'fake'}}}
    wire = EvidenceWire(work, AssessedBriefing, '')
    assert len(wire.references) == 1
    decoded = json.loads(wire.decode(json.dumps({'understanding': 'A test research question.',
        'findings': [{'statement': 'Test finding', 'basis': 'direct', 'citation_ref': 1}],
        'uncertainties': ['Test limitation.'], 'clarification': '', 'directions': [],
        'assessment': {'question_id': 'b', 'status': 'possible_answer', 'points': [], 'limitations': ['Test limitation.']}})))
    assert decoded['findings'][0]['quote'].startswith('The fictional mountain')
    assert decoded['findings'][0]['source_id'] == 'a' * 36


def test_short_table_cells_and_bad_optional_metadata_do_not_erase_reading():
    from helvetic_lens.product_question_renewal import parse_recoverable
    work = section()
    work['input']['source']['excerpts'].append({'passage': 'page-5-cell-1', 'text': 'No'})
    schema = documents.schema(ScopedExtraction)
    wire = EvidenceWire(work, schema, '', shared_answer=False)
    assert wire.input['source']['excerpts'][-1] == {'passage': 'page-5-cell-1', 'text': 'No'}
    response = {'section_review': {'summary': 'The source describes a local datum.',
        'observations': [{'role': 'support', 'citation_ref': 1}]},
        'read_relevance': {'citation_ref': 9999, 'category': 'direct', 'reason': 'Invalid reference.'}}
    result = parse_recoverable(schema, wire.decode(json.dumps(response)), {'read_relevance': '_read_relevance_unavailable'})
    assert result.section_review.observations and result.read_relevance is None
    assert result._read_relevance_unavailable


def test_whole_document_review_cannot_cite_summaries_or_the_wrong_reference_target():
    work = {'phase': 'document_review', 'input': {'coverage_fingerprint': 'f' * 64,
        'sections': [{'source_id': 'a' * 36, 'summary': 'A summary is not an original quote.',
            'observations': [{'quote': 'The original provision applies to the fictional reference.', 'locator': 'page-1-p1',
                'statement': 'The original provision applies.', 'role': 'support'}]}],
        'cross_references': [{'id': 'b' * 64, 'target_passages': [{'source_id': 'a' * 36,
            'text': 'The separate target excludes the fictional exception.', 'passage': 'page-2-p1'}]}]}}
    wire = EvidenceWire(work, documents.DocumentReview, documents.REVIEW_SYSTEM)
    assert wire.finding_refs == {1} and wire.target_refs == {'b' * 64: {2}}
    raw = {'findings': [{'statement': 'The original provision applies.', 'role': 'support', 'citation_ref': 1}],
        'cross_reference_checks': [{'id': 'b' * 64, 'status': 'verified', 'explanation': 'The target supplies the exclusion.',
            'evidence': {'statement': 'The target excludes the exception.', 'role': 'counterevidence', 'citation_ref': 2}}]}
    result = documents.DocumentReview.model_validate_json(wire.decode(json.dumps(raw)))
    assert result.coverage_fingerprint == 'f' * 64
    assert result.findings[0].source_id == 'a' * 36
    assert result.cross_reference_checks[0].evidence.locator == 'page-2-p1'
    raw['findings'][0]['citation_ref'] = 2
    with pytest.raises(ValueError):
        wire.decode(json.dumps(raw))
    raw['findings'][0]['citation_ref'] = 1
    raw['cross_reference_checks'][0]['evidence']['citation_ref'] = 1
    with pytest.raises(ValueError):
        wire.decode(json.dumps(raw))


def test_single_final_answer_materializes_consistent_dossier_fields():
    from helvetic_lens.product_direction_assessment import RenewedSuggestedDirectionBriefing
    from helvetic_lens.product_research_mission import schema as mission_schema
    work = {'phase': 'brief', 'input': {'original_question': 'Compare the measurement definitions.',
        'sources': [section()['input']['source']], 'research_mission': {'round': 1},
        'direction_assessment_target': {'selection': None, 'question': 'Compare the measurement definitions.'}}}
    schema = mission_schema(RenewedSuggestedDirectionBriefing)
    wire = EvidenceWire(work, schema, '', shared_answer=False)
    assert set(wire.schema['properties']) == {'answer', 'next_action', 'next_checks', 'deepen_branches', 'clarification', 'directions'}
    raw = {'mission_checkpoint': {'answer': {'status': 'possible_answer',
        'points': [{'statement': 'The measurement uses a local datum.', 'evidence': [{'citation_ref': 1, 'role': 'support'}]}],
        'limitations': ['The available record does not compare sea-level measurements.']},
        'action': 'finish', 'reason': 'The available record explains the different datum.'}}
    value = schema.model_validate_json(wire.decode(json.dumps(answer_wire(raw))))
    assert value.findings[0].quote == value.mission_checkpoint.answer.points[0].evidence[0].quote
    assert value.direction_assessment.points == value.mission_checkpoint.answer.points
    assert value.direction_assessment.selection is None and not value.clarification and not value.directions
    assert schema.model_validate_json(wire.decode(wire.encode_checkpoint(value))) == value
    malformed = json.dumps(answer_wire(raw)).replace(', "action":', '}, "action":', 1)
    assert schema.model_validate_json(wire.decode(malformed)) == value
    with pytest.raises(ValueError):
        wire.decode(json.dumps(answer_wire(raw))[:-1])  # Missing content is never invented.


def test_repair_receives_all_structural_errors_including_null_citations():
    from helvetic_lens.research_model_transport import WireError
    wire = EvidenceWire(section(), documents.schema(ScopedExtraction), '')
    with pytest.raises(WireError) as caught:
        wire.decode(json.dumps({'section_review': {'summary': 'x' * 1700,
            'observations': [{'role': 'direct', 'citation_ref': None}]}, 'copied_input_metadata': {}}))
    paths = {tuple(error['path']) for error in caught.value.validation_errors}
    assert ('section_review', 'summary') in paths
    assert ('section_review', 'observations', 0, 'role') in paths
    assert ('section_review', 'observations', 0, 'citation_ref') in paths
    assert ('copied_input_metadata',) in paths


def test_unavailable_reference_targets_are_never_presented_as_verified():
    work = {'phase': 'document_review', 'input': {'coverage_fingerprint': 'f' * 64,
        'sections': [], 'cross_references': [{'id': 'b' * 64, 'target_passages': []}]}}
    wire = EvidenceWire(work, documents.DocumentReview, documents.REVIEW_SYSTEM)
    assert wire.input['cross_references'] == [] and not wire.references
    value = documents.DocumentReview.model_validate_json(wire.decode('{"findings":[],"cross_reference_checks":[],"limitations":[]}'))
    assert value.cross_reference_checks[0].status == 'unresolved'
    assert value.cross_reference_checks[0].evidence is None


def test_uncited_context_cannot_erase_a_supported_document_finding():
    work = {'phase': 'document_review', 'input': {'coverage_fingerprint': 'f' * 64,
        'sections': [{'source_id': 'a' * 36, 'observations': [{
            'quote': 'The fictional original names a local datum.', 'locator': 'p1', 'role': 'support'}]}],
        'cross_references': []}}
    wire = EvidenceWire(work, documents.DocumentReview, documents.REVIEW_SYSTEM)
    raw = {'findings': [{'statement': 'The original names a local datum.', 'role': 'support', 'citation_ref': 1},
        {'statement': 'An uncited interpretation.', 'role': 'inference', 'citation_ref': None},
        {'statement': 'No sea-level comparison is supplied.', 'role': 'limitation'}], 'limitations': []}
    result = documents.DocumentReview.model_validate_json(wire.decode(json.dumps(raw)))
    assert len(result.findings) == 1 and result.findings[0].role == 'support'
    assert 'No sea-level comparison is supplied.' in result.limitations
    assert any('not retained' in text for text in result.limitations)
    raw['findings'][1]['role'] = 'support'
    with pytest.raises(ValueError):
        wire.decode(json.dumps(raw))


def test_nullable_catalogue_errors_report_the_invalid_members_not_expected_null():
    from helvetic_lens.research_model_transport import shape_errors
    errors = shape_errors(['invented', 'also invented'], {'anyOf': [
        {'type': 'array', 'items': {'enum': ['actual']}}, {'type': 'null'}]}, {}, ('catalogues',))
    assert len(errors) == 2
    assert all('actual' in error['reason'] for error in errors)
    assert errors[1]['path'] == ['catalogues', 1]


def test_mission_reflection_does_not_treat_a_planner_hypothesis_as_user_intent():
    from helvetic_lens.product_branch_assessment import AssessedReflection
    work = {'phase': 'reflect', 'input': {'question': 'Why do these definitions differ?',
        'branch': {'question': 'Give exact millimetre precision for a single unified metric.'},
        'branch_assessment_question': {'question': 'Invented extra requirement'},
        'sources': [section()['input']['source']], 'previous_public_queries': ['earlier query']}}
    wire = EvidenceWire(work, AssessedReflection, '')
    assert wire.input['original_question'] == work['input']['question']
    assert 'branch' not in wire.input and 'branch_assessment_question' not in wire.input
    assert set(wire.schema['properties']) == {'outcome', 'gaps', 'search_deeper'}
    result = AssessedReflection.model_validate_json(wire.decode(json.dumps({
        'outcome': 'The original source explains the different definitions.', 'gaps': [], 'search_deeper': False})))
    assert result.assessment is None


@pytest.mark.parametrize('status,points', [('not_found', []), ('not_found', [
    {'statement': 'The available record discusses a different datum.', 'evidence': [{'citation_ref': 1, 'role': 'context'}]}]),
    ('conflicting', [{'statement': 'The records describe incompatible datums.', 'evidence': [
        {'citation_ref': 2, 'role': 'counterevidence'}, {'citation_ref': 1, 'role': 'support'}]}])])
def test_mission_legacy_cards_never_promote_context_or_counterevidence_to_direct_support(status, points):
    from helvetic_lens.product_research_mission import schema as mission_schema
    source = section()['input']['source']
    source['excerpts'].append({'passage': 'p29', 'text': 'A second passage describes an incompatible datum.'})
    work = {'phase': 'brief', 'input': {'original_question': 'Which datum is supported?',
        'sources': [source], 'assessment_question': {'question_id': 'test-question'}, 'research_mission': {}}}
    schema = mission_schema(AssessedBriefing)
    wire = EvidenceWire(work, schema, '', shared_answer=False)
    result = schema.model_validate_json(wire.decode(json.dumps(answer_wire({'mission_checkpoint': {
        'answer': {'status': status, 'points': points, 'limitations': ['The available record does not settle this.']},
        'action': 'finish', 'reason': 'Useful available checks are exhausted.'}}))))
    if status == 'not_found':
        assert not result.findings
    else:
        assert not result.findings  # A one-quote legacy card cannot carry both sides.
        assert {(ref.role, ref.locator) for ref in result.mission_checkpoint.answer.points[0].evidence} == {
            ('support', 'p00028'), ('counterevidence', 'p29')}


def answer_wire(value):
    data = deepcopy(value['mission_checkpoint'])
    for point in data['answer']['points']:
        for ref in point.pop('evidence'):
            point.setdefault(ref['role'] + '_refs', []).append(ref['citation_ref'])
    return data


def test_answer_pack_excludes_old_generated_answers_and_preserves_canonical_input():
    from helvetic_lens.product_research_mission import schema as mission_schema
    source = section()['input']['source']
    source['url'] = 'https://example.org/original'
    canonical = deepcopy(source)
    canonical['excerpts'].append({'passage': 'p2', 'text': 'An unrelated but fully read paragraph.'})
    work = {'phase': 'brief', 'input': {'original_question': 'Compare the datums.',
        'sources': [canonical], 'synthesis_sources': [{**source, 'whole_document_review': {
            'findings': [{'quote': 'An earlier model claim is not original evidence.'}]}}],
        'research_mission': {'previous_checkpoint': {'answer': 'An old wrong answer.'},
            'attempted_questions': [{'query': 'previous query', 'question': 'An invented user requirement.',
                'status': 'unresolved', 'purpose': 'An earlier tentative purpose.',
                'open_check_context': {'private': 'Do not transport internal receipts.'}}],
            'documents': [{'read_complete': True, 'analysis_complete': True, 'reconciliation': {
                'findings': [{'quote': 'An earlier model claim.'}], 'limitations': ['The datum is local.']}}]}}}
    before = deepcopy(work)
    wire = EvidenceWire(work, mission_schema(AssessedBriefing), '')
    assert work == before and len(wire.references) == 1
    assert 'previous_checkpoint' not in wire.input['research_mission']
    assert wire.input['research_mission']['attempted_queries'] == ['previous query']
    assert wire.input['research_mission']['attempted_questions'] == [
        {'question': 'An invented user requirement.', 'status': 'unresolved'}]
    assert 'not user requirements or evidence' in wire.system
    assert 'Do not transport internal receipts' not in json.dumps(wire.input)
    assert 'An earlier model claim' not in json.dumps(wire.input)
    assert 'review_limitations' not in wire.input['research_mission']['documents'][0]
    assert wire.input['research_mission']['documents'][0]['analysis_complete']


def test_answer_quantity_check_rejects_invented_precision_but_preserves_digit_grouping():
    from helvetic_lens.product_exploration import AssessmentOutcome
    from helvetic_lens.research_gateway import answer_quantity_errors
    def answer(statement, quote):
        return AssessmentOutcome(status='possible_answer', limitations=['Only the supplied record was checked.'],
            points=[{'statement': statement, 'evidence': [{'source_id': 'a', 'locator': 'p1', 'quote': quote, 'role': 'support'}]}])
    assert answer_quantity_errors(answer('The difference is 2,072 metres.', 'The difference is more than 2,000 metres.'))
    assert not answer_quantity_errors(answer('The definition specifies 9,192,631,770 periods.',
        'The definition specifies 9 192 631 770 periods.'))


def test_final_discovery_leads_do_not_duplicate_original_evidence_or_ranking_metadata():
    from helvetic_lens.product_research_mission import schema as mission_schema
    source = section()['input']['source']
    source['discovery_links'] = [{'title': 'An original lead', 'url': 'https://example.org/original',
        'context': 'A public reference', 'summary': 'A public reference', 'id': 'temporary', 'kind': 'document'},
        {'title': 'Account menu', 'url': 'https://example.org/menu', 'kind': 'navigation'}]
    work = {'phase': 'brief', 'input': {'original_question': 'Compare the datums.',
        'sources': [source, deepcopy(source)], 'research_mission': {}}}
    wire = EvidenceWire(work, mission_schema(AssessedBriefing), '')
    assert len(wire.references) == 2
    assert wire.input['sources'][0]['discovery_links'][0] == {
        'title': 'An original lead', 'url': 'https://example.org/original', 'context': 'A public reference', 'kind': 'document'}
    assert wire.input['sources'][1]['discovery_links'] == []
    assert not {'claim_id', 'reconsideration'} & wire.schema['$defs']['Gap']['properties'].keys()


@pytest.mark.asyncio
async def test_known_invalid_answer_is_rejected_when_repair_time_is_exhausted(monkeypatch):
    from types import SimpleNamespace

    from helvetic_lens.analysis import ModelClient
    from helvetic_lens.config import Settings
    from helvetic_lens.product_research_mission import schema as mission_schema
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    client = ModelClient(settings)
    elapsed = [0]
    @atomic_pack_model
    async def complete(*args, **kwargs):
        elapsed[0] = 9  # The draft, not evidence preparation, consumes the available time.
        return json.dumps({'answer': {'status': 'possible_answer', 'points': [
            {'statement': 'The mountain measures 999 metres.', 'support_refs': [1]}],
            'limitations': ['Only this original was read.']}, 'action': 'finish', 'reason': 'The original answers the question.'})
    monkeypatch.setattr(client, 'complete', complete)
    monkeypatch.setattr(research_gateway, 'monotonic', lambda: elapsed[0])
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {'original_question': 'How high is it?',
        'sources': [section()['input']['source']], 'research_mission': {}, 'assessment_question': {'question_id': 'q'}}}
    with pytest.raises(ValueError, match='Answer quantities are absent'):
        await research_gateway._complete(SimpleNamespace(model_client=client, settings=settings), work, '',
            mission_schema(AssessedBriefing), 10)


def test_empty_review_has_valid_schema_and_cannot_invent_original_evidence():
    work = {'phase': 'document_review', 'input': {'coverage_fingerprint': 'f' * 64,
        'sections': [{'source_id': 'a' * 36, 'summary': 'No relevant original passage was selected.', 'observations': []}],
        'cross_references': []}}
    wire = EvidenceWire(work, documents.DocumentReview, documents.REVIEW_SYSTEM)
    assert not wire.references and wire.schema['properties']['findings']['maxItems'] == 0
    def check(node):
        if isinstance(node, dict):
            if 'minimum' in node and 'maximum' in node:
                assert node['minimum'] <= node['maximum']
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)
    check(wire.schema)
    result = documents.DocumentReview.model_validate_json(wire.decode(json.dumps({
        'findings': [], 'cross_reference_checks': [], 'limitations': ['No original passage was selected.']})))
    assert not result.findings and result.coverage_fingerprint == 'f' * 64
    with pytest.raises(ValueError):
        wire.decode(json.dumps({'findings': [{'statement': 'Invented finding.', 'role': 'support', 'citation_ref': 1}]}))


@pytest.mark.asyncio
async def test_missing_dated_context_is_recovered_without_regenerating_the_whole_answer(monkeypatch):
    from types import SimpleNamespace

    from helvetic_lens import research_answer_review as review
    from helvetic_lens.analysis import ModelClient
    from helvetic_lens.config import Settings
    from helvetic_lens.decision_engines import Decision
    from helvetic_lens.product_research_mission import schema as mission_schema
    settings = Settings(_env_file=None, apertus_provider='swisscom')
    client, calls = ModelClient(settings), []
    @atomic_pack_model
    async def complete(*args, **kwargs):
        calls.append(1)
        assert len(calls) <= 2, 'The cited draft is retained through context recovery and final review.'
        value = json.loads(args[1])
        if 'final_claims_and_gaps' in value:
            assert value['selected_citation_refs'] == [1, 2]
            verdict = {'verdict': 'supported', 'reason': '', 'citation_refs': [1, 2]}
            return json.dumps({'overall': verdict, 'clauses': {'S0': verdict}})
        return json.dumps({'answer': {'status': 'possible_answer', 'points': [
            {'statement': 'The committee adopted the revised unit in 2005.', 'evidence': [{'citation_ref': 1, 'role': 'support'}]}],
            'remaining_gaps': []}, 'next_action': 'finish', 'reason': 'The original records the decision.'})
    monkeypatch.setattr(client, 'complete', complete)
    async def audit(*args, **kwargs):
        return {'hints': [], 'status': 'checked'}
    async def original(*args):
        return None
    class Engine:
        async def choose(self, *args):
            return Decision('jev', 'test', 'supported', {'supported': 1}, 1, 1, 1, 1, 1)
    monkeypatch.setattr(review, 'audit', audit)
    monkeypatch.setattr(review, 'original_check', original)
    monkeypatch.setattr(review.decision, 'engines', lambda settings: {'jev': Engine()})
    source = {'id': 'a' * 36, 'kind': 'public_source', 'excerpts': [
        {'passage': 'p1', 'text': 'The committee adopted the revised unit.'},
        {'passage': 'p2', 'text': 'Committee decision (2005)'}]}
    work = {'phase': 'brief', 'unmetered_research': True, 'input': {
        'original_question': 'When was the revised unit adopted?', 'sources': [source], 'research_mission': {}, 'assessment_question': {'question_id': 'q'}}}
    schema = mission_schema(AssessedBriefing)
    raw = await research_gateway._complete(SimpleNamespace(model_client=client, settings=settings), work, '', schema, 90)
    result = schema.model_validate_json(raw)
    assert len(calls) == 2
    assert len(result.mission_checkpoint.answer.points[0].evidence) == 2
    assert not research_gateway.answer_quantity_errors(result.mission_checkpoint.answer)


@pytest.mark.asyncio
@pytest.mark.parametrize('phase', ['reflect', 'orient'])
async def test_preliminary_research_uses_selected_originals_and_repairs_unshown_reference_within_envelope(monkeypatch, phase):
    from types import SimpleNamespace

    from helvetic_lens import research_active_retrieval
    from helvetic_lens.analysis import ModelClient
    from helvetic_lens.config import Settings
    from helvetic_lens.product_exploration import ClarifyingOrientation
    from helvetic_lens.product_iterative_research import Reflection
    from helvetic_lens.research_evidence_pack import request_characters
    from helvetic_lens.research_synthesis_resume import KEY

    settings = Settings(_env_file=None, apertus_provider='swisscom',
        apertus_context_chars=24000 if phase == 'orient' else 12000)
    client, calls, ranked = ModelClient(settings), [], []
    sources = []
    for index in range(1, 51):
        quote = f'Station {index} capacity remains provisional; consult the original register. ' + 'Operational qualification. ' * 10
        sources.append({'id': f'{index:036d}', 'sha256': f'{index:064x}', 'url': f'https://example.test/{index}',
            'title': f'Original station {index}', 'excerpts': [{'passage': 'p1', 'text': quote}],
            'section_review': {'summary': 'Repeated derived material. ' * 50},
            'discovery_links': [{'url': f'https://example.test/register/{index}', 'title': 'The original register',
                'context': quote, 'kind': 'reference'}]})
    work = {'phase': phase, 'unmetered_research': True, 'input': {
        'question' if phase == 'reflect' else 'original_question': 'Explain station capacity and the remaining qualifications.', 'sources': sources,
        'previous_public_queries': ['Earlier register query'], 'search_continuation': {'pages_checked': 1}}}
    if phase == 'orient':
        work['input'].update(
            selected_direction={'question': 'Distinguish planned and operational capacity.'},
            selected_public_check={'question': 'Read the register', 'purpose': 'Resolve the operational qualification.'},
            read_context={'reading_limits': [{'source_id': sources[0]['id'], 'text_truncated': True}]},
            evidence_applicability={'scope': 'Authorization is not established.'},
            saved_knowledge={'claims': ['Earlier generated conclusion. ' * 10000]},
            research_memory={'episodes': ['Historical passages. ' * 10000]},
            capture_progress={'items': ['Repeated capture bookkeeping. ' * 10000]}, claims=['Not new evidence.'])
    original = deepcopy(work['input'])

    async def rank(service, wire, question, seconds, **kwargs):
        ranked.append(list(wire.references))
        return {'rankings': [{'query': question, 'references': list(wire.references)}],
            'coverage': {'method': 'local_hybrid', 'semantic_status': 'ready'}}

    async def complete(system, content, **kwargs):
        data = json.loads(content)
        assert request_characters(system, data, kwargs['response_schema'],
            provider=settings.apertus_provider) <= settings.apertus_context_chars
        assert 'sources' in data, 'Oversized format feedback must retry the bounded original request'
        refs = [p['citation_ref'] for source in data['sources'] for p in source['excerpts']]
        assert refs and len(refs) < 50 and 50 not in refs
        assert all('section_review' not in source and 'discovery_links' not in source for source in data['sources'])
        if phase == 'reflect':
            assert data['discovery_leads'] and all(lead['citation_ref'] in refs for lead in data['discovery_leads'])
            assert data['evidence_scope']['absence_established'] is False
        else:
            for key in ('selected_direction', 'selected_public_check', 'read_context', 'evidence_applicability'):
                assert data[key] == original[key]
            assert not {'saved_knowledge', 'research_memory', 'capture_progress', 'claims'} & data.keys()
            assert 'Unselected material and unassessed sources are not evidence of absence' in system
        calls.append(data)
        # A known canonical ref that was NOT supplied must not pass decoding.
        # The large malformed outcome also makes feedback exceed the envelope.
        if phase == 'orient':
            return json.dumps({'interpretations': [{'meaning': 'Invalid repeated draft. ' * 1000 if len(calls) == 1 else 'Capacity may mean planned or operational capacity.',
                'why': 'The original describes capacity as provisional.', 'signal': 'possible',
                'citation_ref': 50 if len(calls) == 1 else refs[0]}],
                'uncertainties': ['The relevant capacity definition needs to be checked.'],
                'clarification': 'Which capacity definition is useful?',
                'directions': [{'question': question, 'why': 'The original motivates this distinction.',
                    'citation_ref': refs[0]} for question in ('What capacity is planned?', 'What capacity is operational?')]})
        return json.dumps({'outcome': 'Invalid repeated draft. ' * 1000 if len(calls) == 1 else 'One selected original motivates reading its register.',
            'gaps': [{'question': 'What does the original register establish?', 'query': data['discovery_leads'][0]['url'],
                'purpose': 'Read the register named by this exact source.', 'priority': 3,
                'kind': 'independent_verification', 'catalogues': [], 'citation_ref': 50 if len(calls) == 1 else refs[0]}],
            'search_deeper': False})

    monkeypatch.setattr(research_active_retrieval, 'rank_evidence', rank)
    monkeypatch.setattr(client, 'complete', complete)
    schema = Reflection if phase == 'reflect' else ClarifyingOrientation
    service = SimpleNamespace(model_client=client, settings=settings)
    raw = await research_gateway._complete(service, work, '', schema, 60)
    result = schema.model_validate_json(raw)
    witness = result.gaps[0] if phase == 'reflect' else result.interpretations[0]
    assert witness.source_id == sources[0]['id']
    if phase == 'orient':
        assert result.clarification and len(result.directions) == 2
        assert all(direction.source_id == sources[0]['id'] for direction in result.directions)
    assert len(ranked) == 1 and len(calls) == 2
    assert work[KEY]['stage'] == 'preparing' and work[KEY]['raw'] == ''
    assert 'answer_review' not in work['model_route']
    assert work['model_route']['format_repair_mode'] == 'fresh_bounded_draft'
    assert work['input'] == original
    # Only validated preparation is reusable; a prior orientation/reflection is
    # never restored as a final-answer draft or an already accepted new decision.
    await research_gateway._complete(service, work, '', schema, 60)
    assert len(calls) == 3 and len(ranked) == 1
    assert work[KEY]['stage'] == 'preparing' and work[KEY]['raw'] == ''


@pytest.mark.asyncio
async def test_early_orientation_without_original_witness_stays_unfinished(monkeypatch):
    from types import SimpleNamespace

    from helvetic_lens.analysis import ModelClient
    from helvetic_lens.config import DomainError, Settings
    from helvetic_lens.product_exploration import EarlyOrientation
    from helvetic_lens.research_synthesis_resume import KEY

    settings = Settings(_env_file=None, apertus_provider='swisscom')
    client = ModelClient(settings)
    async def complete(*args, **kwargs):
        pytest.fail('An interpretation cannot be generated without an original witness.')
    monkeypatch.setattr(client, 'complete', complete)
    work = {'phase': 'orient', 'unmetered_research': True, 'input': {
        'original_question': 'Explain the requested comparison.', 'sources': []}}
    with pytest.raises(DomainError) as exc:
        await research_gateway._complete(SimpleNamespace(model_client=client, settings=settings),
            work, '', EarlyOrientation, 60)
    assert exc.value.code == 'research_evidence_pack_incomplete'
    assert work[KEY]['stage'] == 'preparing' and work[KEY]['raw'] == ''


def test_multipart_answer_requires_every_request_and_retains_canonical_repair_bindings():
    from helvetic_lens.product_research_mission import schema as mission_schema
    schema = mission_schema(AssessedBriefing)
    source = section()['input']['source']
    work = {'phase': 'brief', 'input': {'original_question': 'What does the record establish? When?',
        'sources': [source], 'research_mission': {}, 'assessment_question': {'question_id': 'q'}}}
    wire = EvidenceWire(work, schema, '', shared_answer=False)
    assert wire.request_keys == {'r1': 'What does the record establish?', 'r2': 'When?'}
    point = {'statement': 'The fictional mountain measures 123 metres above a local datum.',
        'evidence': [{'citation_ref': 1, 'role': 'support'}]}
    raw = {'answer': {'status': 'possible_answer', 'remaining_gaps': [], 'responses': {
        'r1': {'disposition': 'answered', 'points': [point], 'remaining_gap': ''},
        'r2': {'disposition': 'unresolved', 'points': [], 'remaining_gap': 'The measurement date is not established.'}}},
        'next_action': 'finish', 'reason': 'The record supplies the measurement but not its date.'}
    value = schema.model_validate_json(wire.decode(json.dumps(raw)))
    assert value.mission_checkpoint.answer.status == 'partial'
    assert value.mission_checkpoint.answer.limitations == ['The measurement date is not established.']
    assert schema.model_validate_json(wire.decode(wire.encode_checkpoint(value))) == value
    missing = deepcopy(raw)
    del missing['answer']['responses']['r2']
    with pytest.raises(ValueError):
        wire.decode(json.dumps(missing))
    empty = deepcopy(raw)
    empty['answer']['responses']['r2'] = {'disposition': 'answered', 'points': [], 'remaining_gap': ''}
    with pytest.raises(ValueError):
        wire.decode(json.dumps(empty))
    raw['answer']['status'] = 'partial'
    raw['answer']['responses']['r1'] = {'disposition': 'unresolved', 'points': [], 'remaining_gap': 'No supported measurement.'}
    value = schema.model_validate_json(wire.decode(json.dumps(raw)))
    assert value.mission_checkpoint.answer.status == 'not_found' and not value.mission_checkpoint.answer.points
    assert wire.schema['$defs']['AssessmentOutcome']['properties']['remaining_gaps']['maxItems'] == 6
    raw['answer']['remaining_gaps'] = [f'Additional unanswered aspect {i}.' for i in range(6)]
    value = schema.model_validate_json(wire.decode(json.dumps(raw)))
    assert len(value.mission_checkpoint.answer.limitations) == 8
    assert schema.model_validate_json(wire.decode(wire.encode_checkpoint(value))) == value


@pytest.mark.parametrize('instruction', [
    'Start with https://example.org/a and https://example.org/b',
    'Почни з https://example.org/a та https://example.org/b',
    'Commencez par https://example.org/a et https://example.org/b',
    'Beginne mit https://example.org/a und https://example.org/b',
])
def test_url_start_instruction_is_preserved_as_context_not_a_fabricated_fact_request(instruction):
    from helvetic_lens.research_model_transport import explicit_requests, request_parts
    question = 'When was the change adopted? Distinguish adoption and publication. ' + instruction
    assert explicit_requests(question) == ['When was the change adopted?', 'Distinguish adoption and publication.']
    assert request_parts(question)[1] == [instruction]
    # If all we have is a source instruction, do not erase the entire question.
    assert explicit_requests(instruction) == [instruction]


@pytest.mark.parametrize('sentence', [
    'Use https://example.org/a and explain whether its conclusion is supported.',
    'Start with https://example.org/a but exclude the annex.',
    'Does https://example.org/a contradict https://example.org/b?',
    'Почни з https://example.org/a та поясни відмінності.',
])
def test_substantive_or_uncertain_url_sentences_remain_answer_obligations(sentence):
    from helvetic_lens.research_model_transport import explicit_requests
    assert explicit_requests('What changed? ' + sentence) == ['What changed?', sentence]
