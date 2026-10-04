"""Requested-source identity is a revocable selection aid, never truth approval."""
import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_document_source_context import original
from test_product_dossiers import signed as signed
from test_research_evidence_pack import ranking

from helvetic_lens import product_document_analysis as documents
from helvetic_lens import product_iterative_research as research
from helvetic_lens import research_requested_sources as requested
from helvetic_lens.product_evidence_applicability import ScopedExtraction
from helvetic_lens.product_exploration import Briefing
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_evidence_pack import provider_sources, select_evidence
from helvetic_lens.research_model_transport import EvidenceWire, shape_errors
from helvetic_lens.research_reference_metadata import annotate_sources

QUESTION = 'Which renewal and cancellation rules apply? Use the Harbor archive rules.'
REQUIREMENT = 'the Harbor archive rules'
IDENTITY = 'Harbor archive rules, issued by the Harbor Archive Board for its deposits.'


def reading(monkeypatch):
    run = SimpleNamespace(id=str(uuid4()), question=QUESTION, research_state={})
    first = original(run, [('page-1-text-1', IDENTITY)], [])
    later = original(run, [('page-90-text-1', 'Renewal requires the written consent of the archive owner.')], [])
    work = {'phase': 'extract', 'source_id': first.id, 'input': {'question': QUESTION,
        'source': {'id': first.id, 'sha256': first.sha256, 'url': first.url,
            'excerpts': deepcopy(first.snapshot['excerpts'])}}}
    documents.prepare_section(work, first)
    schema = documents.schema(ScopedExtraction)
    wire = EvidenceWire(work, schema, '')
    response = {'section_review': {'summary': 'This is the named archive document.', 'observations': []},
        'source_class': {'category': 'primary', 'requested_source': REQUIREMENT, 'citation_ref': 1}}
    parsed = schema.model_validate_json(wire.decode(json.dumps(response)))
    monkeypatch.setattr(research, 'apply_extraction', lambda *args: None)
    monkeypatch.setattr(research, 'rows', lambda *args: [])
    monkeypatch.setattr(documents, 'rows', lambda *args: [])
    monkeypatch.setattr('helvetic_lens.product_document_reconciliation.compact_reviews', lambda *args: {})
    research.extract(None, run, first, parsed)
    return run, first, later, work, parsed


def answer_wire(sources, question=QUESTION):
    return EvidenceWire({'phase': 'brief', 'input': {'original_question': question,
        'sources': sources, 'research_mission': {}}}, mission_schema(Briefing), '', retrieve_originals=True)


def test_existing_section_read_binds_request_and_later_original_portions_without_claims(monkeypatch):
    run, first, later, work, parsed = reading(monkeypatch)
    assert parsed.source_class.quote == IDENTITY and parsed.source_class.requested_source == REQUIREMENT
    assert parsed.claims == []
    before = deepcopy([s.snapshot for s in [first, later]])
    values = documents.compact_sources(None, run, [first, later], retain_originals=True)
    assert values[1]['requested_source_basis']['identity']['source_id'] == first.id
    wire = answer_wire(values)
    original_refs = deepcopy(wire.references)
    selected = {key: ref for key, ref in wire.references.items() if ref['source_id'] == later.id}
    groups = provider_sources(wire, selected)
    assert groups[0]['requested_source_basis']['identity']['quote'] == IDENTITY
    assert groups[0]['requested_source_basis']['requested_source'] == REQUIREMENT
    assert wire.references == original_refs and [s.snapshot for s in [first, later]] == before
    assert all(ref['quote'] != IDENTITY for ref in selected.values()), 'Identity metadata is not auto-added support'
    # Source-group projection used by correction and review follows the same helper.
    from helvetic_lens.research_answer_parts import source_groups
    assert source_groups(wire, selected)[0]['requested_source_basis'] == groups[0]['requested_source_basis']
    # A later unknown reading cannot erase a valid same-question match.
    parsed.source_class.category, parsed.source_class.requested_source = 'unknown', ''
    research.extract(None, run, first, parsed)
    assert first.snapshot['source_class'] == before[0]['source_class']


@pytest.mark.parametrize('choice,provider_valid,has_match', [
    ('null', True, False), ('legacy_missing', False, False),
    ('legacy_nested_missing', False, False), ('empty', True, False),
    ('unknown', True, False), ('document_title', True, False),
    ('invalid_citation', False, False), ('invalid_type', False, False),
    ('exact', True, True),
])
def test_explicit_provider_choice_preserves_legacy_and_optional_read_recovery(
        monkeypatch, choice, provider_valid, has_match):
    from helvetic_lens.product_question_renewal import parse_recoverable

    run, first, _, work, _ = reading(monkeypatch)
    first.snapshot.pop('source_class')
    schema = documents.schema(ScopedExtraction)
    canonical_before = deepcopy(schema.model_json_schema())
    wire = EvidenceWire(work, schema, '')
    response = {'section_review': {'summary': 'The supplied original identifies the archive rules.',
        'observations': [{'role': 'context', 'citation_ref': 1}]},
        'source_class': {'category': 'primary', 'requested_source': REQUIREMENT, 'citation_ref': 1}}
    if choice == 'null':
        response['source_class'] = None
    elif choice == 'legacy_missing':
        response.pop('source_class')
    elif choice == 'legacy_nested_missing':
        response['source_class'].pop('requested_source')
    elif choice == 'empty':
        response['source_class']['requested_source'] = ''
    elif choice == 'unknown':
        response['source_class']['category'] = 'unknown'
    elif choice == 'document_title':
        response['source_class']['requested_source'] = IDENTITY
    elif choice == 'invalid_citation':
        response['source_class']['citation_ref'] = 9999
    elif choice == 'invalid_type':
        response['source_class']['requested_source'] = ['not a source requirement']
    # The dispatched grammar requires a choice; canonical legacy decoding stays
    # compatible and a malformed classification cannot discard the real reading.
    errors = shape_errors(response, wire.schema, wire.schema['$defs'])
    assert (not errors) is provider_valid
    assert all(error['path'][0] == 'source_class' for error in errors)
    parsed = parse_recoverable(schema, wire.decode(json.dumps(response)),
        {'source_class': '_source_class_unavailable'})
    assert parsed.section_review.observations[0].quote == IDENTITY
    assert parsed.section_review.observations[0].locator == wire.references[1]['locator']
    assert wire.references[1]['source_id'] == first.id
    if choice in {'invalid_citation', 'invalid_type'}:
        assert parsed.source_class is None and parsed._source_class_unavailable
    research.extract(None, run, first, parsed)
    view = {'id': first.id, 'sha256': first.sha256, 'url': first.url,
        'excerpts': first.snapshot['excerpts'], 'source_class': first.snapshot.get('source_class')}
    assert bool(requested.validated_matches([view], QUESTION)) is has_match
    assert schema.model_json_schema() == canonical_before
    # Optional metadata recovery cannot salvage invalid required observations.
    response['section_review']['observations'][0]['citation_ref'] = 9999
    with pytest.raises(ValueError):
        wire.decode(json.dumps(response))


@pytest.mark.parametrize('change', ['question', 'quote', 'sha', 'identity_withdrawn', 'other_url',
    'old_copy_id', 'unknown', 'invented_requirement', 'bad_category', 'bad_contract', 'malformed_id'])
def test_stale_or_unbound_matches_never_enter_provider_context(monkeypatch, change):
    run, first, later, _, _ = reading(monkeypatch)
    values = documents.compact_sources(None, run, [first, later], retain_originals=True)
    question = QUESTION
    if change == 'question':
        question = 'Use the Harbor archive rules to determine only admission fees.'
    elif change == 'quote':
        values[0]['retrieval_originals'][0]['text'] = 'A different current document identity.'
    elif change == 'sha':
        values[0]['sha256'] = 'b' * 64
    elif change == 'identity_withdrawn':
        values = values[1:]
    elif change == 'other_url':
        values[1]['url'] = 'https://example.test/another-original.pdf'
    elif change == 'old_copy_id':
        values[0]['id'] = str(uuid4())
    elif change == 'bad_contract':
        for value in values:
            value['requested_source_basis']['contract'] = 'obsolete'
    elif change == 'malformed_id':
        for value in values:
            value['requested_source_basis']['identity']['source_id'] = ['not an ID']
    else:
        for value in values:
            value.pop('requested_source_basis')
        item = deepcopy(first.snapshot['source_class'])
        if change == 'unknown':
            item['category'] = 'unknown'
        elif change == 'bad_category':
            item['category'] = 'TRUSTED_AUTHORITY'
        else:
            item['requested_source'] = 'an invented source requirement'
        values[0]['source_class'] = item
    wire = answer_wire(values, question)
    if change == 'other_url':
        assert 'requested_source_basis' in wire.input['sources'][0]
        assert 'requested_source_basis' not in wire.input['sources'][1]
    else:
        assert not any(s.get('requested_source_basis') for s in wire.input['sources'])
        assert not any(g.get('requested_source_basis') for g in provider_sources(wire, wire.references))


def test_bibliography_identity_is_not_a_match_to_the_referenced_original():
    source = {'id': 'source', 'sha256': 'a' * 64, 'url': 'https://example.test/article', 'excerpts': [
        {'passage': 'page-9-text-1', 'text': 'References'},
        {'passage': 'page-9-text-2', 'text': 'Smith, A., Harbor archive rules, Journal of Archives, 4, 12–19, 2021.'},
        {'passage': 'page-9-text-3', 'text': 'Jones, B., Archive standards, Journal of Archives, 3, 10–19, 2020.'}]}
    source = annotate_sources([source])[0]
    quote = source['excerpts'][1]['text']
    value = {'category': 'primary', 'requested_source': REQUIREMENT, 'original_question': QUESTION,
        'source_id': 'source', 'sha256': source['sha256'], 'locator': 'page-9-text-2', 'quote': quote}
    assert source['excerpts'][1]['source_use'] == 'reference_metadata'
    assert requested.match(value, source, QUESTION) is None


@pytest.mark.asyncio
@pytest.mark.parametrize('matched', [True, False])
async def test_each_literal_query_prefers_complete_matched_group_then_retains_other_evidence(monkeypatch, matched):
    run, first, later, _, _ = reading(monkeypatch)
    later.snapshot['excerpts'].append({'passage': 'page-120-text-1',
        'text': 'Cancellation is permitted only after the stated waiting period.'})
    commentary = original(run, [('page-1-text-1', 'A commentary summarizes both renewal and cancellation.')], [])
    commentary.url, commentary.sha256 = 'https://example.test/commentary.pdf', 'b' * 64
    counter = original(run, [('page-1-text-1', 'An independent record questions how the waiting period was applied.')], [])
    counter.url, counter.sha256 = 'https://example.test/counter.pdf', 'c' * 64
    if not matched:
        first.snapshot.pop('source_class')
    wire = answer_wire(documents.compact_sources(None, run, [first, later, commentary, counter], retain_originals=True))
    ids = {ref['quote']: key for key, ref in wire.references.items()}
    renewal = ids[later.snapshot['excerpts'][0]['text']]
    cancellation = ids[later.snapshot['excerpts'][1]['text']]
    summary = ids[commentary.snapshot['excerpts'][0]['text']]
    contrary = ids[counter.snapshot['excerpts'][0]['text']]
    calls = ranking(monkeypatch, [{'query': q, 'references': [summary, target, contrary],
        'scores': {summary: 1, target: .8, contrary: .5}} for q, target in
        [('Which renewal rules apply?', renewal), ('Which cancellation rules apply?', cancellation)]])
    attempts, saved = [], {}
    def size(refs):
        return len(refs) * 100
    def fits(refs):
        attempts.append(set(refs))
        return size(refs) <= 400
    service = SimpleNamespace(settings=SimpleNamespace(apertus_context_chars=400))
    before = deepcopy(wire.references)
    selected = await select_evidence(service, wire, QUESTION, 20, checkpoints=saved,
        fits=fits, request_size=size, required_refs=[contrary])
    assert contrary in selected and selected == {key: before[key] for key in selected}
    accepted = [refs for refs in attempts if 1 < len(refs) <= 4]
    if matched:
        assert accepted[0] == {contrary, renewal} and accepted[1] == {contrary, renewal, cancellation}
    else:
        assert accepted[0] == {contrary, summary}, 'Unannotated sources retain ordinary query seeding'
    assert {renewal, cancellation, summary, contrary} == set(selected)
    assert wire.references == before and saved['retrieval_coverage']['absence_established'] is False
    await select_evidence(service, wire, QUESTION, 20, checkpoints=saved,
        fits=fits, request_size=size, required_refs=[contrary])
    assert len(calls) == 1, 'Exact current preference reuses selection without reranking'
    if matched:
        for source in wire.input['sources']:
            source.pop('requested_source_basis', None)
        await select_evidence(service, wire, QUESTION, 20, checkpoints=saved,
            fits=fits, request_size=size, required_refs=[contrary])
        assert len(calls) == 2, 'Changed source preference invalidates saved selection'


@pytest.mark.parametrize('change', ['none', 'question', 'withdrawal', 'malformed_pin'])
def test_new_recalled_note_rebinds_only_through_current_eligible_origin(signed, tmp_path, change):
    from test_product_exploration import start
    from test_research_retained_html import capture

    from helvetic_lens import research_knowledge as knowledge
    from helvetic_lens.product_investigation_models import Investigation, InvestigationSource
    from helvetic_lens.product_investigations import snapshot
    from helvetic_lens.product_models import DossierEntry

    client, service, _, model = signed
    _, child, _ = start(client)
    value, _, _ = capture(tmp_path)
    with service.db.session() as session:
        run = session.get(Investigation, child['id'])
        run.question = 'Which rules apply? Use the Archive terms.'
        previous = Investigation(organization_id=run.organization_id, dossier_id=run.dossier_id,
            request_key=str(uuid4()), question=run.question, status='completed')
        session.add(previous)
        session.flush()
        origin, _ = snapshot(session, previous, {**value, 'status': 'complete'}, public=True)
        origin.snapshot = {**origin.snapshot, 'source_class': {'category': 'primary',
            'requested_source': 'the Archive terms', 'original_question': run.question,
            'source_id': origin.id, 'sha256': origin.sha256,
            'locator': origin.snapshot['excerpts'][0]['passage'], 'quote': origin.snapshot['excerpts'][0]['text']}}
        knowledge.recall(session, run, 'pharma', selected_ids=[origin.id])
        copy = session.get(InvestigationSource, run.research_state['core']['recall']['sources'][0]['id'])
        assert copy.snapshot['source_class']['source_id'] == origin.id
        if change == 'question':
            run.question = 'Use the Archive terms to investigate an unrelated current matter.'
        elif change == 'withdrawal':
            session.add(DossierEntry(dossier_id=run.dossier_id, kind='source_review', request_key=str(uuid4()),
                url=origin.url, body='Exclude this original.', data_json={'decision': 'exclude', 'revision': 1}))
        elif change == 'malformed_pin':
            copy.snapshot = {**copy.snapshot, 'retained_origin': {'source_id': []},
                'source_class': {**copy.snapshot['source_class'], 'source_id': copy.id}}
        session.commit()
        before = deepcopy(origin.snapshot), deepcopy(copy.snapshot)
        values = documents.compact_sources(session, run, [copy], retain_originals=True)
        wire = answer_wire(values, run.question)
        if change == 'none':
            basis = requested.provider_basis(wire, copy.id)['requested_source_basis']
            assert basis['identity']['source_id'] == copy.id and basis['identity']['quote'] == value['excerpts'][0]['text']
        else:
            assert requested.provider_basis(wire, copy.id) == {}
        assert (origin.snapshot, copy.snapshot) == before
        assert not session.dirty and not session.new and not session.deleted and model.calls == []
