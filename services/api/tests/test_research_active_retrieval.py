"""Active originals reuse local retrieval without promoting its scores to facts."""
import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import delete, func, select
from test_product_dossiers import signed as signed
from test_product_evidence_search import retained
from test_product_web_research import setup

from helvetic_lens import evidence_embeddings as embeddings
from helvetic_lens import research_active_retrieval as retrieval
from helvetic_lens.config import DomainError
from helvetic_lens.decision_engines import DecisionUnavailable
from helvetic_lens.models import OrganizationMembership, UserSession
from helvetic_lens.product_investigation_models import Investigation, InvestigationSource
from helvetic_lens.product_models import DossierEntry
from helvetic_lens.product_retrieval_models import EvidenceVector


def local_service():
    return SimpleNamespace(settings=SimpleNamespace(evidence_embedding_url='http://localhost:18762/v1/embeddings',
        laya_api_key=SecretStr('local-fixture')), organization_id='fixture-tenant')


def wire_fixture(count=20):
    refs = {key: {'source_id': 'source', 'locator': f'p{key}',
        'quote': 'The refrigerator maintains safe cold storage.' if key == count else f'Unrelated administration record {key}.'}
        for key in range(1, count + 1)}
    return SimpleNamespace(references=refs, input={'original_question': 'Wie wird das Medikament gelagert?',
        'sources': [{'id': 'source', 'sha256': 'capture-hash', 'title': 'Captured source'}]})


def encoder(monkeypatch, *, hook=None, failure=None, truncated=False):
    calls = []

    async def encode(self, texts):
        calls.append(texts)
        if hook:
            hook(len(calls))
        if failure:
            raise DecisionUnavailable(failure)
        return [{'vector': tuple(([1.0, 0.0] if text.startswith('query:') or 'refrigerator' in text
            else [0.0, 1.0]) + [0.0] * 382), 'input_tokens': 600 if truncated and text.startswith('passage:') else 40,
            'truncated': truncated and text.startswith('passage:')} for text in texts]

    monkeypatch.setattr(embeddings.LocalEmbeddings, 'encode', encode)
    return calls


@pytest.mark.asyncio
async def test_all_originals_rank_and_warm_cache_only_encodes_queries_without_source_mutation(monkeypatch):
    wire, service, checkpoints = wire_fixture(), local_service(), {}
    original = deepcopy(wire.__dict__)
    calls = encoder(monkeypatch)
    result = await retrieval.rank_evidence(service, wire, wire.input['original_question'], 60, checkpoints=checkpoints)
    assert result['rankings'][0]['references'][0] == 20
    assert set(result['rankings'][0]['references']) == set(wire.references)
    assert result['coverage']['semantic_status'] == 'complete'
    assert result['coverage']['prepared_records'] == 20
    assert len([call for call in calls if call[0].startswith('passage:')]) == 2
    warm_start = len(calls)
    warm = await retrieval.rank_evidence(service, wire, wire.input['original_question'], 60,
        checkpoints=json.loads(json.dumps(checkpoints)))
    assert warm['rankings'] == result['rankings']
    assert all(text.startswith('query:') for call in calls[warm_start:] for text in call)
    assert wire.__dict__ == original
    assert all(row['status'] == 'complete' and row['selected'] for row in checkpoints['evidence_selection'].values())


@pytest.mark.asyncio
async def test_cache_does_not_cross_tenant_or_model_and_changed_full_quote_is_reencoded(monkeypatch):
    wire, service, checkpoints = wire_fixture(2), local_service(), {}
    calls = encoder(monkeypatch)
    await retrieval.rank_evidence(service, wire, 'Storage', 60, checkpoints=checkpoints)
    first = len(calls)
    wire.references[1]['quote'] += ' Added condition.'
    await retrieval.rank_evidence(service, wire, 'Storage', 60, checkpoints=checkpoints)
    assert [len(call) for call in calls[first:] if call[0].startswith('passage:')] == [1]
    first = len(calls)
    service.organization_id = 'another-tenant'
    await retrieval.rank_evidence(service, wire, 'Storage', 60, checkpoints=checkpoints)
    assert [len(call) for call in calls[first:] if call[0].startswith('passage:')] == [2]
    for cache in checkpoints['active_retrieval_vectors'].values():
        for row in cache.values():
            row['model'] = 'a-different-model'
    first = len(calls)
    await retrieval.rank_evidence(service, wire, 'Storage', 60, checkpoints=checkpoints)
    assert [len(call) for call in calls[first:] if call[0].startswith('passage:')] == [2]


@pytest.mark.asyncio
async def test_local_unavailability_keeps_full_lexical_ranking_and_reports_truncation_honestly(monkeypatch):
    wire, service = wire_fixture(), local_service()
    encoder(monkeypatch, failure='unavailable')
    fallback = await retrieval.rank_evidence(service, wire, 'refrigerator', 60)
    assert fallback['rankings'][0]['references'][0] == 20
    assert set(fallback['rankings'][0]['references']) == set(wire.references)
    assert fallback['coverage']['method'] == 'lexical_graph_fallback'
    assert fallback['coverage']['semantic_status'] == 'unavailable'
    assert fallback['coverage']['prepared_records'] == 0
    wire.references[1]['quote'] += ' Long tail.' * 300
    original = wire.references[1]['quote']
    encoder(monkeypatch, truncated=True)
    result = await retrieval.rank_evidence(service, wire, 'refrigerator', 60)
    assert result['coverage']['truncated_records'] == 20
    assert result['coverage']['prefix_truncated_records'] == 1
    assert wire.references[1]['quote'] == original


@pytest.mark.asyncio
async def test_deadline_retains_only_completed_batches_and_resumes_missing_originals(monkeypatch):
    wire, service, checkpoints, now = wire_fixture(), local_service(), {}, [0.0]
    monkeypatch.setattr(retrieval, 'monotonic', lambda: now[0])
    calls = encoder(monkeypatch)
    def elapsed():
        now[0] = 61.0
    with pytest.raises(DomainError) as error:
        await retrieval.rank_evidence(service, wire, 'Storage', 60, checkpoints=checkpoints, on_progress=elapsed)
    assert error.value.code == 'research_evidence_pack_incomplete'
    assert len(checkpoints['evidence_selection']) == 1 and len(calls) == 1
    result = await retrieval.rank_evidence(service, wire, 'Storage', 60, checkpoints=checkpoints)
    assert result['coverage']['prepared_records'] == 20
    assert [len(call) for call in calls if call[0].startswith('passage:')] == [16, 4]


@pytest.mark.asyncio
async def test_correction_ranks_meaningful_questions_not_serialized_candidate_payload(monkeypatch):
    wire, service = wire_fixture(2), local_service()
    calls = encoder(monkeypatch)
    task = json.dumps({'original_question': 'How should it be stored?', 'requested_part': 'Explain temperature limits.',
        'correction_target': {'previous_statement': 'It can remain outside the refrigerator.',
            'validation_errors': [{'reason': 'The quoted condition does not support ambient storage.',
                'candidate_windows': [{'text': 'Must not become an embedding query.'}]}]}})
    result = await retrieval.rank_evidence(service, wire, task, 60)
    queries = [text for call in calls for text in call if text.startswith('query:')]
    assert any('How should it be stored?' in text for text in queries)
    assert any('does not support ambient storage' in text for text in queries)
    assert all('candidate_windows' not in text and 'Must not become' not in text for text in queries)
    assert len(result['rankings']) == len(queries)


def native_wire(signed):
    client, service, identity, _ = signed
    doc, _ = setup(client)
    texts = ['Unrelated administration.', 'The refrigerator maintains safe cold storage.']
    run_id, source_id = retained(service, doc, texts, finding=False, status='running')
    with service.db.session() as session:
        run, source = session.get(Investigation, run_id), session.get(InvestigationSource, source_id)
        run.actor_user_id = run.created_by_user_id = identity['user']['id']
        run.session_id = session.scalar(select(UserSession.id).where(UserSession.user_id == identity['user']['id']))
        run.session_organization_id = service.organization_id
        wire = SimpleNamespace(work={'run_id': run_id, 'generation': run.generation},
            references={i + 1: {'source_id': source.id, 'locator': f'p{i}', 'quote': text} for i, text in enumerate(texts)},
            input={'original_question': 'Storage', 'sources': [{'id': source.id, 'title': source.title, 'sha256': source.sha256}]})
        session.commit()
    return wire, doc


@pytest.mark.parametrize('change', ['membership', 'source', 'quote'])
def test_native_rechecks_authority_and_exact_original_before_committing_vectors(signed, monkeypatch, change):
    _, service, identity, _ = signed
    wire, doc = native_wire(signed)
    def revoke(_count):
        with service.db.session() as session:
            if change == 'membership':
                session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == identity['user']['id']))
            elif change == 'source':
                session.add(DossierEntry(dossier_id=doc['id'], actor_user_id=identity['user']['id'],
                    request_key=str(uuid4()), kind='source_review', url='https://example.org/source',
                    data_json={'revision': 1, 'decision': 'exclude'}))
            else:
                source = session.get(InvestigationSource, wire.references[1]['source_id'])
                source.snapshot = {**source.snapshot, 'excerpts': []}
            session.commit()
    encoder(monkeypatch, hook=revoke)
    checkpoints = {}
    with pytest.raises(DomainError):
        asyncio.run(retrieval.rank_evidence(service, wire, 'Storage', 60, checkpoints=checkpoints))
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(EvidenceVector)) == 0
    assert not checkpoints.get('evidence_selection')


def test_native_warm_cache_remains_source_contained_and_does_not_grant_access(signed, monkeypatch):
    _, service, identity, _ = signed
    wire, _ = native_wire(signed)
    calls = encoder(monkeypatch)
    result = asyncio.run(retrieval.rank_evidence(service, wire, 'Storage', 60))
    assert result['coverage']['prepared_records'] == 2
    first = len(calls)
    asyncio.run(retrieval.rank_evidence(service, wire, 'Storage', 60))
    assert all(text.startswith('query:') for call in calls[first:] for text in call)
    with service.db.session() as session:
        cache = list(session.scalars(select(EvidenceVector)))
        assert len(cache) == 2 and all(row.investigation_id == wire.work['run_id'] for row in cache)
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == identity['user']['id']))
        session.commit()
    with pytest.raises(DomainError):
        asyncio.run(retrieval.ensure_current(service, wire))
    with pytest.raises(DomainError):
        asyncio.run(retrieval.rank_evidence(service, wire, 'Storage', 60))
