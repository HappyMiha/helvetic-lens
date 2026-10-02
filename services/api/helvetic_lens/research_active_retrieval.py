"""Local hybrid retrieval over this investigation's exact, authorized originals."""
import asyncio
import json
from time import monotonic

from sqlalchemy import select

from . import evidence_embeddings as embeddings
from . import evidence_graph_retrieval as graph
from .config import DomainError
from .decision_engines import DecisionUnavailable
from .product_corpus_search import lexical_fallback, rank_records
from .product_operations import fingerprint
from .research_model_transport import explicit_requests

POLICY = fingerprint({'contract': 'active-original-retrieval/v1', 'model': embeddings.MODEL,
    'ranking': 'dense-bm25-cited-graph/2:1:1', 'queries': 'original-explicit-correction/v1'})


def _queries(wire, question):
    values = [question]
    try:
        task = json.loads(question)
    except (TypeError, ValueError):
        task = None
    if isinstance(task, dict) and any(key in task for key in ('original_question', 'requested_part')):
        values = [task.get('original_question'), task.get('requested_part')]
        correction = task.get('correction_target')
        if isinstance(correction, dict):
            values.append(correction.get('previous_statement'))
            values.extend(error.get('reason') for error in correction.get('validation_errors', [])
                if isinstance(error, dict))
    values = [value.strip() for value in values if isinstance(value, str) and value.strip()]
    if not values:
        values = [wire.input.get('original_question', '')]
    return list(dict.fromkeys(part for value in values for part in [value, *explicit_requests(value)] if part))


def _records(wire):
    sources = {source['id']: source for source in wire.input.get('sources', [])}
    items = []
    for key, ref in wire.references.items():
        if type(key) is not int or key <= 0 or ref['source_id'] not in sources:
            raise DomainError('Retrieval requires current canonical originals.', 422, 'research_evidence_required_reference_invalid')
        source = sources[ref['source_id']]
        item = {'id': str(key), **ref, 'title': source.get('title', ''), 'sha256': source.get('sha256', ''),
            'statement': '', 'claim_id': ''}
        # The key survives citation renumbering, but never a different source,
        # original, locator, title or full quotation (including an unencoded tail).
        item['record_key'] = 'active:' + fingerprint({key: item[key] for key in
            ('source_id', 'sha256', 'locator', 'title', 'quote')})
        item['input_sha256'] = embeddings.text_hash(embeddings.passage(item))
        items.append(item)
    return items


def _current(session, service, wire, items):
    from .product_investigation_models import Investigation, InvestigationSource
    from .product_investigations import worker_access
    from .product_models import ProductDossier
    from .product_public_research import sources_visible
    from .product_source_reviews import current_reviews

    work = wire.work
    run = session.get(Investigation, work['run_id'])
    if (not run or run.organization_id != service.organization_id or run.status not in {'queued', 'running'}
            or work.get('generation', run.generation) != run.generation):
        raise DomainError('The active evidence scope changed.', 409, 'evidence_changed')
    parent = session.get(ProductDossier, run.dossier_id)
    worker_access(session, run, parent.product)
    if not session.scalar(select(Investigation.id).where(Investigation.id == run.id, sources_visible())):
        raise DomainError('The original evidence is no longer accessible.', 409, 'evidence_changed')
    excluded = {url for url, review in current_reviews(session, parent.id).items()
        if review.data_json['decision'] == 'exclude'}
    sources = {source.id: source for source in session.scalars(select(InvestigationSource).where(
        InvestigationSource.investigation_id == run.id, InvestigationSource.dossier_id == run.dossier_id,
        InvestigationSource.organization_id == run.organization_id))}
    for item in items:
        source = sources.get(item['source_id'])
        if (not source or source.sha256 != item['sha256'] or source.title != item['title']
                or excluded.intersection({source.url, source.snapshot.get('requested_url'),
                    *source.snapshot.get('redirect_chain', [])})
                or not any(passage.get('passage') == item['locator'] and item['quote'] in passage.get('text', '')
                    for passage in source.snapshot.get('excerpts', []))):
            raise DomainError('The original evidence changed during retrieval.', 409, 'evidence_changed')
    return run, parent


def _database_cache(service, wire, items, queries, updates=None):
    from .product_retrieval_models import EvidenceVector

    with service.db.session() as session:
        if session.get_bind().dialect.name == 'postgresql':
            session.connection().exec_driver_sql("SET LOCAL statement_timeout = '3000ms'")
        run, parent = _current(session, service, wire, items)
        expected = {item['record_key']: item for item in items}
        rows = {row.record_key: row for row in session.scalars(select(EvidenceVector).where(
            EvidenceVector.dossier_id == run.dossier_id, EvidenceVector.organization_id == run.organization_id,
            EvidenceVector.investigation_id == run.id, EvidenceVector.record_key.in_(expected)))}
        if updates:
            for key, value in updates.items():
                item = expected[key]
                row = rows.get(key)
                if row is None:
                    row = EvidenceVector(dossier_id=run.dossier_id, organization_id=run.organization_id,
                        investigation_id=run.id, source_id=item['source_id'], record_key=key, claim_id=None)
                    session.add(row)
                row.model, row.input_sha256 = embeddings.MODEL, item['input_sha256']
                row.vector = embeddings.pack(value['vector'])
                row.input_tokens, row.truncated = value['input_tokens'], value['truncated']
            session.commit()
            return {}, {}
        cached = {}
        for key, row in rows.items():
            item = expected[key]
            if row.source_id != item['source_id'] or row.model != embeddings.MODEL or row.input_sha256 != item['input_sha256']:
                continue
            try:
                if (type(row.input_tokens) is not int or not 1 <= row.input_tokens <= 16000
                        or type(row.truncated) is not bool or row.truncated != (row.input_tokens > 512)):
                    continue
                cached[key] = {'vector': embeddings.unpack(row.vector), 'input_tokens': row.input_tokens,
                    'truncated': row.truncated}
            except DecisionUnavailable:
                continue
        links = {query: graph.project(session, parent, items, query) for query in queries}
        return cached, links


async def ensure_current(service, wire):
    """A retained selection never substitutes for current native permissions."""
    if getattr(service, 'db', None) is None:
        return
    if not getattr(wire, 'work', {}).get('run_id'):
        raise DomainError('Native retrieval requires its active investigation scope.', 422, 'research_evidence_scope_invalid')
    items = _records(wire)

    def check():
        with service.db.session() as session:
            _current(session, service, wire, items)

    await asyncio.to_thread(check)


async def rank_evidence(service, wire, question, seconds, *, checkpoints=None, on_progress=None):
    """Rank every current window locally; return priorities, never factual verdicts."""
    items, queries = _records(wire), _queries(wire, question)
    checkpoints = checkpoints if checkpoints is not None else {}
    deadline = monotonic() + max(0, seconds)
    native = getattr(service, 'db', None) is not None
    if native and not getattr(wire, 'work', {}).get('run_id'):
        raise DomainError('Native retrieval requires its active investigation scope.', 422, 'research_evidence_scope_invalid')
    scope = fingerprint({'organization_id': getattr(service, 'organization_id', None),
        'run_id': getattr(wire, 'work', {}).get('run_id')})
    private = checkpoints.setdefault('active_retrieval_vectors', {}).setdefault(scope, {}) if not native else None
    if native:
        cached, links = await asyncio.to_thread(_database_cache, service, wire, items, queries)
    else:
        cached, links = {}, {}
        for item in items:
            row = private.get(item['record_key'], {})
            if row.get('model') != embeddings.MODEL or row.get('input_sha256') != item['input_sha256']:
                continue
            try:
                if (type(row['input_tokens']) is not int or not 1 <= row['input_tokens'] <= 16000
                        or type(row['truncated']) is not bool or row['truncated'] != (row['input_tokens'] > 512)):
                    continue
                cached[item['record_key']] = {**row, 'vector': embeddings.unpack(bytes.fromhex(row['vector']))}
            except (DecisionUnavailable, ValueError, KeyError, TypeError):
                continue
    missing = list({item['record_key']: item for item in items if item['record_key'] not in cached}.values())
    encoder = embeddings.LocalEmbeddings(service.settings)
    failure, prepared_batches = None, 0

    async def encode(texts):
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise DomainError('Local evidence preparation is incomplete; completed work is retained.',
                503, 'research_evidence_pack_incomplete')
        async with asyncio.timeout(remaining):
            return await encoder.encode(texts)

    try:
        for offset in range(0, len(missing), embeddings.BATCH):
            batch = missing[offset:offset + embeddings.BATCH]
            values = await encode([embeddings.passage(item) for item in batch])
            updates = {item['record_key']: value for item, value in zip(batch, values)}
            if native:
                await asyncio.to_thread(_database_cache, service, wire, items, [], updates)
            else:
                for item, value in zip(batch, values):
                    private[item['record_key']] = {**value, 'model': embeddings.MODEL,
                        'input_sha256': item['input_sha256'], 'vector': embeddings.pack(value['vector']).hex()}
            cached.update(updates)
            prepared_batches += 1
            binding = fingerprint({'policy': POLICY, 'records': [(item['record_key'], item['input_sha256']) for item in batch],
                'scope': scope})
            checkpoints.setdefault('evidence_selection', {})[binding] = {'status': 'complete',
                'input_fingerprint': fingerprint([(item['record_key'], item['input_sha256']) for item in batch]),
                'policy_fingerprint': POLICY, 'selected': [int(item['id']) for item in batch]}
            if on_progress:
                on_progress()
    except DecisionUnavailable as exc:
        failure = exc.code
    except TimeoutError:
        raise DomainError('Local evidence preparation is incomplete; completed work is retained.',
            503, 'research_evidence_pack_incomplete') from None
    query_vectors = {}
    if not failure and items and not any(item['record_key'] not in cached for item in items):
        eligible = [query for query in queries if len('query: ' + query) <= 4000]
        try:
            for offset in range(0, len(eligible), embeddings.BATCH):
                batch = eligible[offset:offset + embeddings.BATCH]
                values = await encode(['query: ' + query for query in batch])
                query_vectors.update({query: value for query, value in zip(batch, values)})
        except DecisionUnavailable as exc:
            failure = exc.code
        except TimeoutError:
            failure = 'query_timeout'
    if native:
        # A cache is never permission evidence. Recheck after local inference,
        # including a failure, before returning any source or priority.
        cached, links = await asyncio.to_thread(_database_cache, service, wire, items, queries)
    vectors = {item['id']: cached[item['record_key']] for item in items if item['record_key'] in cached}
    rankings = []
    for query in queries:
        vector = query_vectors.get(query)
        semantic = vector is not None and not vector['truncated'] and len(vectors) == len(items)
        ranked = (rank_records(query, items, vectors, vector['vector'], links.get(query)) if semantic
            else lexical_fallback(query, items, links.get(query)))
        rankings.append({'query': query, 'references': [int(item['id']) for item in ranked],
            'scores': {int(item['id']): item['rank_score'] for item in ranked},
            'method': 'local_hybrid' if semantic else 'lexical_graph_fallback'})
    complete = bool(rankings) and all(row['method'] == 'local_hybrid' for row in rankings)
    return {'rankings': rankings, 'coverage': {'method': 'local_hybrid' if complete else 'lexical_graph_fallback',
        'semantic_status': 'complete' if complete else failure or 'query_unavailable' if items else 'empty',
        'examined_records': len(items), 'prepared_records': len(vectors), 'prepared_batches': prepared_batches,
        'truncated_records': sum(value['truncated'] for value in vectors.values()),
        'prefix_truncated_records': sum(len(item['quote']) > 2400 or len(item['title']) > 300 for item in items),
        'graph_truncated': any(value['truncated'] for value in links.values()),
        'model': embeddings.MODEL, 'basis': 'Retrieval priorities, not verified support or complete answer coverage.'}}
