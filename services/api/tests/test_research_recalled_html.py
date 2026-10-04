"""Recalled HTML keeps current citation IDs and revocable original-byte lineage."""
from copy import deepcopy
from uuid import uuid4

import pytest
from test_product_dossiers import create
from test_product_dossiers import signed as signed
from test_product_exploration import start
from test_research_original_context import wire_for
from test_research_retained_html import capture

from helvetic_lens import research_knowledge as knowledge
from helvetic_lens.html_document_structure import HTML_STRUCTURE_VERSION
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from helvetic_lens.product_investigations import scope, snapshot
from helvetic_lens.product_models import DossierEntry
from helvetic_lens.research_html_structure import annotate_retained, retained_originals
from helvetic_lens.research_original_context import contextual_references, provider_excerpts


def recalled(signed, *, foreign=False):
    client, service, _, model = signed
    _, child, _ = start(client)
    other = create(client)[0] if foreign else None
    folder = service.settings.storage_path / 'artifacts'
    folder.mkdir(exist_ok=True, parents=True)
    value, original, path = capture(folder)
    with service.db.session() as session:
        run = session.get(Investigation, child['id'])
        previous = Investigation(organization_id=run.organization_id,
            dossier_id=other['id'] if other else run.dossier_id, request_key=str(uuid4()),
            question='Read the archive terms.', status='completed')
        session.add(previous)
        session.flush()
        branch = InvestigationBranch(**scope(previous), query=previous.question,
            status='completed', reason='Retained complete original.')
        session.add(branch)
        session.flush()
        source, _ = snapshot(session, previous, {**value, 'status': 'complete',
            'branch_id': branch.id, 'document_index': '0'}, public=True)
        branch.checkpoint = {'document_reads': {'0': {'source_ids': [source.id],
            'sha256': source.sha256, 'read_complete': True, 'analysis_complete': True,
            'retained_document': {'content_type': 'text/html', 'url': source.url,
                'sha256': source.sha256, 'artifact_key': original['artifact_key']}}}}
        if foreign:
            copy, _ = snapshot(session, run, {**deepcopy(source.snapshot),
                'key': 'retained:' + source.id, 'retained_origin': knowledge.origin_pin(source)}, public=True)
        else:
            knowledge.recall(session, run, 'pharma', selected_ids=[source.id])
            copy = session.get(InvestigationSource, run.research_state['core']['recall']['sources'][0]['id'])
        session.commit()
        assert model.calls == []
        return run.id, source.id, copy.id, branch.id, path


def view(source):
    return {'id': source.id, 'sha256': source.sha256, 'url': source.url, 'title': source.title,
        'excerpts': deepcopy(source.snapshot['excerpts'])}


def test_ordinary_recall_resolves_parent_bytes_without_relabelling_or_mutating_sources(signed):
    _, service, _, _ = signed
    run_id, origin_id, copy_id, branch_id, path = recalled(signed)
    with service.db.session() as session:
        origin, copy = [session.get(InvestigationSource, key) for key in (origin_id, copy_id)]
        before = deepcopy(origin.snapshot), deepcopy(copy.snapshot), path.read_bytes()
        wire = wire_for([view(copy)])
        original_refs = deepcopy(wire.references)
        originals = retained_originals(session, run_id, wire.input['sources'])
        assert originals == [{'source_id': copy_id, 'sha256': copy.sha256,
            'artifact_key': path.name, 'excerpts': copy.snapshot['excerpts']}]
        assert annotate_retained(path.parent, wire.input['sources'], originals) == [copy_id]
        assert {p['html_structure']['version'] for p in wire.input['sources'][0]['excerpts']} == {HTML_STRUCTURE_VERSION}
        selected = next(key for key, ref in wire.references.items() if 'written permission' in ref['quote'])
        projected = provider_excerpts(wire, contextual_references(wire, [selected]))
        assert set(projected) == {copy_id} and origin_id not in projected
        assert 'Archive terms' in {p['text'] for p in projected[copy_id]}
        assert not any('weekday' in p['text'] for p in projected[copy_id])
        assert wire.references == original_refs
        assert (origin.snapshot, copy.snapshot, path.read_bytes()) == before
        assert not session.dirty and not session.new and not session.deleted
        # Direct captures still resolve through the original run's own registry.
        assert retained_originals(session, origin.investigation_id, [view(origin)])[0]['source_id'] == origin_id
        assert session.get(InvestigationBranch, branch_id).checkpoint['document_reads']['0']['source_ids'] == [origin_id]


@pytest.mark.parametrize('change', ['origin_snapshot', 'origin_private', 'copy_private', 'copy_excerpts',
    'copy_excluded', 'origin_incomplete', 'withdrawal', 'malformed_pin', 'missing_document', 'view_sha'])
def test_recalled_structure_requires_current_exact_eligible_origin(signed, change):
    _, service, _, _ = signed
    run_id, origin_id, copy_id, branch_id, path = recalled(signed)
    with service.db.session() as session:
        run = session.get(Investigation, run_id)
        origin, copy = [session.get(InvestigationSource, key) for key in (origin_id, copy_id)]
        if change == 'origin_snapshot':
            origin.snapshot = {**origin.snapshot, 'warnings': ['Changed retained source receipt.']}
        elif change == 'origin_private':
            origin.kind = 'team_contribution'
        elif change == 'copy_private':
            copy.kind = 'team_contribution'
        elif change == 'copy_excerpts':
            copy.snapshot = {**copy.snapshot, 'excerpts': [{'passage': 'p00001-block-1-char-1', 'text': 'Forged content.'}]}
        elif change == 'copy_excluded':
            copy.snapshot = {**copy.snapshot, 'allow_discovery': False}
        elif change == 'origin_incomplete':
            session.get(Investigation, origin.investigation_id).status = 'running'
        elif change == 'withdrawal':
            session.add(DossierEntry(dossier_id=run.dossier_id, kind='source_review', request_key=str(uuid4()),
                url=origin.url, body='Exclude this original.', data_json={'decision': 'exclude', 'revision': 1}))
        elif change == 'malformed_pin':
            copy.snapshot = {**copy.snapshot, 'retained_origin': {'source_id': ['not an identifier']}}
        elif change == 'missing_document':
            session.get(InvestigationBranch, branch_id).checkpoint = {'document_reads': {}}
        session.commit()
        current = view(copy)
        if change == 'view_sha':
            current['sha256'] = 'b' * 64
        wire = wire_for([current])
        before = deepcopy(wire.input)
        assert retained_originals(session, run_id, wire.input['sources']) == []
        assert annotate_retained(path.parent, wire.input['sources'], []) == []
        assert wire.input == before


def test_same_bytes_in_another_dossier_do_not_authorize_recalled_enrichment(signed):
    _, service, _, _ = signed
    run_id, _, copy_id, _, _ = recalled(signed, foreign=True)
    with service.db.session() as session:
        assert retained_originals(session, run_id, [view(session.get(InvestigationSource, copy_id))]) == []


@pytest.mark.parametrize('change', ['bytes', 'outside_symlink'])
def test_recalled_registry_does_not_bypass_existing_byte_or_path_validation(signed, tmp_path, change):
    _, service, _, _ = signed
    run_id, _, copy_id, _, path = recalled(signed)
    with service.db.session() as session:
        wire = wire_for([view(session.get(InvestigationSource, copy_id))])
        originals = retained_originals(session, run_id, wire.input['sources'])
    assert originals
    if change == 'bytes':
        path.write_bytes(path.read_bytes() + b' altered')
    else:
        outside = tmp_path / 'outside.original'
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
    before = deepcopy(wire.input)
    assert annotate_retained(path.parent, wire.input['sources'], originals) == []
    assert wire.input == before
