"""Reference metadata stays readable without becoming unread-paper evidence."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from research_pack_fixtures import atomic_pack_model

from helvetic_lens import research_active_retrieval as retrieval
from helvetic_lens import research_synthesis_resume as resume
from helvetic_lens.config import Settings
from helvetic_lens.product_document_analysis import REVIEW_SYSTEM, DocumentReview
from helvetic_lens.product_document_analysis import schema as section_schema
from helvetic_lens.product_evidence_applicability import ScopedExtraction
from helvetic_lens.product_exploration import AssessmentOutcome, Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_answer_parts import source_groups
from helvetic_lens.research_evidence_pack import provider_sources
from helvetic_lens.research_final_review import reasoned_review
from helvetic_lens.research_model_transport import EvidenceWire
from helvetic_lens.research_reference_metadata import annotate_sources


def original_source():
    return {'id': 'a' * 36, 'sha256': 'b' * 64, 'title': 'Assessment chapter',
        'url': 'https://example.org/assessment.pdf', 'excerpts': [
            {'passage': 'p1', 'text': 'The projection is conditional on the stated scenario; this is not an observed completion.'},
            {'passage': 'p2', 'text': 'REFERENCES'},
            {'passage': 'p3', 'text': 'Smith, A., Recovery of atmospheric ozone, Journal of Observations, 5, 41–45, 2016.'},
            {'passage': 'p4', 'text': 'Jones, B., Uncertainty in projections, Journal of Observations, 7, 80–90, 2018.'}]}


def answer_wire():
    sources = annotate_sources([original_source()])
    return EvidenceWire({'phase': 'brief', 'work_id': 'private', 'input': {
        'original_question': 'What does the source establish and which studies does it cite?',
        'research_mission': {}, 'sources': sources}}, mission_schema(Briefing), '')


def test_original_classification_survives_windowing_and_local_citation_renumbering():
    wire = answer_wire()
    before = deepcopy(wire.references)
    assert wire.reference_uses == {2: 'reference_metadata', 3: 'reference_metadata', 4: 'reference_metadata'}
    assert all(set(ref) == {'source_id', 'locator', 'quote'} for ref in wire.references.values())
    local = {1: wire.references[4], 2: wire.references[1], 3: wire.references[3]}
    for field, groups in [('excerpts', provider_sources(wire, local)), ('passages', source_groups(wire, local))]:
        passages = groups[0][field]
        # Provider context follows original document order. Local citation IDs
        # must still identify exactly the same quotations and source-use roles.
        by_id = {p['citation_ref']: p for p in passages}
        assert len(passages) == len(by_id) == len(local)
        assert {key: p.get('source_use') for key, p in by_id.items()} == {
            1: 'reference_metadata', 2: None, 3: 'reference_metadata'}
        assert {key: p['text'] for key, p in by_id.items()} == {key: ref['quote'] for key, ref in local.items()}
    assert wire.references == before


def test_stale_original_classification_is_not_propagated():
    sources = annotate_sources([original_source()])
    sources[0]['excerpts'][2]['text'] += ' This original changed after classification.'
    work = {'phase': 'brief', 'input': {'sources': sources}}
    wire = EvidenceWire(work, Briefing, '')
    assert 3 not in wire.reference_uses and wire.reference_uses[4] == 'reference_metadata'


def test_metadata_citation_remains_in_typed_answer_without_becoming_substantive_finding():
    wire = answer_wire()
    raw = {'answer': {'status': 'possible_answer', 'points': [{
        'statement': 'The bibliography lists Smith’s study in 2016.',
        'evidence': [{'citation_ref': 3, 'role': 'support'}]}], 'remaining_gaps': []}, 'next_action': 'finish'}
    parsed = mission_schema(Briefing).model_validate_json(wire.decode(json.dumps(raw)))
    assert parsed.mission_checkpoint.answer.points[0].evidence[0].quote == wire.references[3]['quote']
    assert parsed.findings == []


def test_section_metadata_observation_is_context_not_a_substantive_support_claim():
    source = annotate_sources([original_source()])[0]
    work = {'phase': 'extract', 'source_id': source['id'], 'input': {
        'question': 'Which papers are cited?', 'source': source,
        'document_section': {'coverage_fingerprint': 'f' * 64}}}
    schema = section_schema(ScopedExtraction)
    wire = EvidenceWire(work, schema, '')
    raw = {'section_review': {'summary': 'Bibliographic records.',
        'observations': [{'role': 'support', 'citation_ref': 3}], 'limitations': []}}
    parsed = schema.model_validate_json(wire.decode(json.dumps(raw)))
    assert parsed.section_review.observations[0].role == 'context'
    assert parsed.claims[0].relation == 'CONTEXT'


@pytest.mark.parametrize('role', ['support', 'context'])
def test_review_metadata_is_visible_but_not_eligible_for_substantive_findings(role):
    quote = original_source()['excerpts'][2]['text']
    work = {'phase': 'document_review', 'input': {'coverage_fingerprint': 'c' * 64,
        'sections': [{'source_id': 'a' * 36, 'summary': 'Earlier synopsis wrongly claimed recovery.',
            'observations': [], 'reference_metadata': [{'source_id': 'a' * 36, 'locator': 'p3',
                'quote': quote, 'source_use': 'reference_metadata'}]}], 'cross_references': []}}
    work['reference_metadata'] = deepcopy(work['input']['sections'][0]['reference_metadata'])
    wire = EvidenceWire(work, DocumentReview, REVIEW_SYSTEM)
    assert wire.references[1]['quote'] == quote and not wire.finding_refs
    assert wire.input['sections'][0]['reference_metadata'][0]['source_use'] == 'reference_metadata'
    with pytest.raises(ValueError):
        wire.decode(json.dumps({'synopsis': 'A bibliography.', 'findings': [{
            'statement': 'The atmosphere fully recovered.', 'role': role, 'citation_ref': 1}],
            'cross_reference_checks': [], 'limitations': []}))


@pytest.mark.asyncio
@pytest.mark.parametrize('role', ['support', 'context'])
@pytest.mark.parametrize('scope', ['original_content', 'reference_metadata', None, 'unrecognized'])
async def test_existing_semantic_review_distinguishes_metadata_from_unread_results(role, scope):
    wire = answer_wire()
    statement = ('The bibliography lists Smith’s study in 2016.' if scope == 'reference_metadata'
        else 'The Antarctic ozone layer recovered between 2019 and 2022.')
    # Original canonical IDs are retained; a context label cannot bypass scope.
    answer = AssessmentOutcome(status='possible_answer', points=[{'statement': statement,
        'evidence': [{**wire.references[3], 'role': role}]}], limitations=[])
    calls = []

    class Model:
        @atomic_pack_model
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            calls.append(payload)
            assert payload['final_claims_and_gaps']['P0']['passages'][0]['source_use'] == 'reference_metadata'
            assert any(p.get('source_use') == 'reference_metadata'
                for source in payload['source_context'] for p in source['passages'])
            judgment = {'verdict': 'supported', 'reason': '', 'citation_refs': [3]}
            if scope is not None:
                judgment['assertion_scope'] = scope
            return json.dumps({'overall': judgment,
                'clauses': {key: judgment for key in payload['assertion_clauses']}})

    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    result = await reasoned_review(service, wire, answer, 60)
    assert len(calls) == 1
    if scope == 'reference_metadata':
        assert result['status'] == 'checked' and result['hints'] == []
    elif scope in {None, 'unrecognized'}:
        assert result['status'] == 'partial' and result['pending_checks'][0]['reason'] == 'invalid_response'
    else:
        assert result['status'] == 'checked' and result['hints'][0]['review_signal'] == 'not_established'
        assert not result['positive_witnesses']


@pytest.mark.asyncio
async def test_metadata_witness_does_not_clear_an_existing_content_objection():
    wire = answer_wire()
    calls = []
    answer = AssessmentOutcome(status='possible_answer', points=[{
        'statement': 'The atmosphere fully recovered.', 'evidence': [{**wire.references[3], 'role': 'context'}]}], limitations=[])

    class Model:
        @atomic_pack_model
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            calls.append(payload)
            judgment = {'verdict': 'supported', 'reason': '', 'citation_refs': [3], 'assertion_scope': 'original_content'}
            return json.dumps({'overall': judgment, 'clauses': {key: judgment for key in payload['assertion_clauses']},
                'concern_checks': [{'id': key, 'outcome': 'resolved', 'reason': 'The title was cited.',
                    'citation_refs': [3], 'assertion_scope': 'original_content'}
                    for key in payload['prior_review_concerns']['concerns']]})

    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    checkpoints = {}
    concerns = {'P0': {'previous_statements': [], 'issues': [{'instruction': 'The paper itself remains unread.'}]}}
    result = await reasoned_review(service, wire, answer, 60, checkpoints=checkpoints,
        concerns=concerns)
    assert result['pending_checks'] == [{'item': 'P0', 'reason': 'unresolved_concern'}]
    assert not result['positive_witnesses'] and not result['candidates']
    assert len(calls) == 1 and any(key.startswith('clauses:') for key in checkpoints)
    # Completed raw inference is retained privately, but source-use validation
    # must still reject the bibliography as evidence on a resumed review.
    result = await reasoned_review(service, wire, answer, 60,
        checkpoints=json.loads(json.dumps(checkpoints)), concerns=concerns)
    assert len(calls) == 1, 'A retained raw judgment is reused without purchasing another inference'
    assert result['pending_checks'] == [{'item': 'P0', 'reason': 'unresolved_concern'}]
    assert not result['positive_witnesses'] and not result['candidates']


@pytest.mark.asyncio
@pytest.mark.parametrize('gap_status', ['answered', 'answer_available', 'outside_request'])
async def test_bibliography_does_not_close_a_content_gap_because_another_point_exists(gap_status):
    wire = answer_wire()
    answer = AssessmentOutcome(status='partial', points=[{'statement': wire.references[1]['quote'],
        'evidence': [{**wire.references[1], 'role': 'support'}]}],
        limitations=['The empirical recovery result remains unknown.'])

    class Model:
        @atomic_pack_model
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            gap = 'L0' in payload['final_claims_and_gaps']
            judgment = {'verdict': 'not_established' if gap else 'supported', 'reason': '',
                'citation_refs': [3] if gap else [1], 'assertion_scope': 'original_content'}
            return json.dumps({'overall': judgment,
                'clauses': {key: judgment for key in payload['assertion_clauses']},
                **({'gap_status': gap_status} if gap else {})})

    service = SimpleNamespace(settings=Settings(_env_file=None), model_client=Model())
    result = await reasoned_review(service, wire, answer, 60)
    gaps = [hint for hint in result['hints'] if hint['path'][:2] == ['answer', 'limitations']]
    assert len(gaps) == 1
    assert gaps[0]['review_signal'] == ('not_a_gap' if gap_status == 'outside_request' else 'not_established')


def test_review_node_requires_all_existing_output_fields_but_accepts_empty_arrays():
    from helvetic_lens.product_document_reconciliation import ReviewNode
    work = {'phase': 'document_review', 'input': {'coverage_fingerprint': 'c' * 64,
        'sections': [], 'cross_references': []}}
    wire = EvidenceWire(work, ReviewNode, REVIEW_SYSTEM)
    assert set(wire.schema['required']) == {'synopsis', 'findings', 'cross_reference_checks', 'limitations'}
    value = ReviewNode.model_validate_json(wire.decode(json.dumps({'synopsis': 'No substantive findings.',
        'findings': [], 'cross_reference_checks': [], 'limitations': []})))
    assert value.findings == []


def test_source_use_policy_invalidates_previously_reviewed_draft(monkeypatch):
    work, settings = {}, Settings(_env_file=None)
    args = ('system', 'review', {}, 'unchanged original content', {})
    saved = resume.DraftCheckpoint(work, settings, *args)
    saved.save('reviewed', '{}', [], {'status': 'checked'})
    monkeypatch.setattr(resume, 'SOURCE_USE_POLICY', 'reference-metadata/new-policy')
    assert resume.DraftCheckpoint(work, settings, *args).value is None


@pytest.mark.asyncio
async def test_bounded_review_preserves_native_run_scope_for_local_retrieval(monkeypatch):
    work = {'run_id': 'native-run', 'generation': 7}
    refs = {key: {'source_id': str(key), 'locator': 'p1', 'quote': 'An original source statement. ' * 45}
        for key in range(1, 41)}
    wire = SimpleNamespace(work=work, references=refs, reference_uses={}, input={
        'original_question': 'Which evidence resolves the requested uncertainty?',
        'sources': [{'id': str(key), 'title': 'Original ' + str(key)} for key in refs]})
    checked = []

    async def rank(service, candidate, question, seconds, **kwargs):
        assert service.db is not None and candidate.work is work
        assert candidate.references == refs
        checked.append('rank')
        return {'rankings': [{'query': question, 'references': list(refs)}],
            'coverage': {'method': 'local_hybrid', 'semantic_status': 'complete'}}

    async def current(service, candidate):
        assert service.db is not None and candidate.work is work
        checked.append('current')

    class Model:
        @atomic_pack_model
        async def complete(self, system, text, **kwargs):
            payload = json.loads(text)
            judgment = {'verdict': 'supported', 'reason': '', 'citation_refs': []}
            return json.dumps({'overall': judgment,
                'clauses': {key: judgment for key in payload['assertion_clauses']}, 'gap_status': 'unresolved'})

    monkeypatch.setattr(retrieval, 'rank_evidence', rank)
    monkeypatch.setattr(retrieval, 'ensure_current', current)
    service = SimpleNamespace(db=object(), settings=Settings(_env_file=None, apertus_context_chars=18000), model_client=Model())
    result = await reasoned_review(service, wire, AssessmentOutcome(status='not_found', points=[],
        limitations=['The requested uncertainty is unresolved.']), 60)
    assert result['status'] == 'checked' and checked == ['rank', 'current']
