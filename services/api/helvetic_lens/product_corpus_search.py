"""Automatic, resumable preparation and full permitted-ledger retrieval.

Only derived, source-contained vectors persist. Every candidate and count comes
from today's authorized ledger, never from the cache. Questions remain transient.
"""
import asyncio
import re
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from . import decision_engines as decisions
from . import evidence_embeddings as embeddings
from . import evidence_graph_retrieval as graph
from .decision_search import lexical_order
from .product_api import fail, iso
from .product_evidence_search import (
    BATCH_SIZE,
    INSTRUCTIONS,
    RELEVANCE,
    TIME_LIMIT,
    capture_rows,
    fingerprint,
    ledger,
    literal_match,
    semantic_state,
)
from .product_investigations import access
from .product_retrieval_models import EvidenceVector


async def database(function, *args):
    try:
        return await asyncio.to_thread(function, *args)
    except OperationalError as error:
        if getattr(error.orig, "sqlstate", None) == "57014":
            fail("Saved-evidence preparation exceeded its database time limit. Try again or use Words.", 503, "search_read_timeout")
        raise


def cache_rows(service, identity, product, dossier_id, command, items):
    expected = {item["id"]: embeddings.text_hash(embeddings.passage(item)) for item in items}
    with service.db.session() as session:
        row = access(session, identity, product, dossier_id)
        if session.get_bind().dialect.name == "postgresql":
            session.connection().exec_driver_sql("SET LOCAL statement_timeout = '3000ms'")
        visible = ledger(session.get_bind().dialect.name, row.id, row.organization_id, command.as_of)
        query = select(EvidenceVector).join(visible,
            (visible.c.id == EvidenceVector.record_key) & (visible.c.source_id == EvidenceVector.source_id)
            & (visible.c.investigation_id == EvidenceVector.investigation_id)).where(
                EvidenceVector.dossier_id == row.id, EvidenceVector.organization_id == row.organization_id,
                EvidenceVector.model == embeddings.MODEL)
        found = {}
        for saved in session.scalars(query):
            if expected.get(saved.record_key) != saved.input_sha256:
                continue
            try:
                found[saved.record_key] = {"vector": embeddings.unpack(saved.vector),
                    "input_tokens": saved.input_tokens, "truncated": saved.truncated}
            except decisions.DecisionUnavailable:
                continue  # A malformed derived cache is regenerated from evidence.
        return found


def save_batch(service, identity, product, dossier_id, command, captured_fingerprint, items, vectors):
    with service.db.session() as session:
        row = access(session, identity, product, dossier_id, write=True, action="read")
        if session.get_bind().dialect.name == "postgresql":
            session.connection().exec_driver_sql("SET LOCAL statement_timeout = '3000ms'")
        if fingerprint(capture_rows(session, row, command)) != captured_fingerprint:
            fail("Saved evidence or access changed during preparation. Search again.", 409, "evidence_changed")
        for item, vector in zip(items, vectors):
            saved = session.scalar(select(EvidenceVector).where(EvidenceVector.dossier_id == row.id,
                EvidenceVector.organization_id == row.organization_id, EvidenceVector.record_key == item["id"]))
            if saved is None:
                saved = EvidenceVector(dossier_id=row.id, organization_id=row.organization_id,
                    investigation_id=item["investigation_id"], source_id=item["source_id"],
                    claim_id=item["claim_id"] or None, record_key=item["id"])
                session.add(saved)
            saved.model = embeddings.MODEL
            saved.input_sha256 = embeddings.text_hash(embeddings.passage(item))
            saved.vector = embeddings.pack(vector["vector"])
            saved.input_tokens = vector["input_tokens"]
            saved.truncated = vector["truncated"]
        session.commit()


def rank_records(query, items, vectors, query_vector, relationships=None):
    similarities = {item["id"]: sum(a * b for a, b in zip(query_vector, vectors[item["id"]]["vector"])) for item in items}
    dense = sorted(similarities, key=lambda key: (-similarities[key], key))
    # Stable ID ties match the preselected independent development experiment.
    lexical = lexical_order(query, [{**item, "summary": item["statement"] + " " + item["quote"]}
        for item in sorted(items, key=lambda item: item["id"])])
    terms = set(re.findall(r"\w+", query.casefold()))
    has_words = {item["id"] for item in items if terms.intersection(re.findall(r"\w+",
        (item["title"] + " " + item["statement"] + " " + item["quote"]).casefold()))}
    lexical = [key for key in lexical if key in has_words]
    scores = {key: 2 / (60 + index) for index, key in enumerate(dense, 1)}
    for index, key in enumerate(lexical, 1):
        scores[key] += 1 / (60 + index)
    by_id = {item["id"]: item for item in items}
    ranked = [{**by_id[key], "rank_score": scores[key], "semantic_similarity": similarities[key],
        "embedding_truncated": vectors[key]["truncated"], "semantic_match": False,
        "literal_match": literal_match(query, by_id[key]), "relevance_probability": None, "confidence": None}
        for key in sorted(scores, key=lambda key: (-scores[key], key))]
    return graph.fuse(ranked, relationships)


def relationships(service, identity, product, dossier_id, items, query):
    with service.db.session() as session:
        row = access(session, identity, product, dossier_id)
        if session.get_bind().dialect.name == "postgresql":
            session.connection().exec_driver_sql("SET LOCAL statement_timeout = '3000ms'")
        return graph.project(session, row, items, query)


def lexical_fallback(query, items, links):
    by_id = {i["id"]: i for i in items}
    order = lexical_order(query, [{**i, "summary": i["statement"] + " " + i["quote"]} for i in items])
    ranked = [{**by_id[key], "rank_score": 1 / (60 + number), "semantic_similarity": None,
        "semantic_match": False, "embedding_truncated": False, "literal_match": literal_match(query, by_id[key]),
        "relevance_probability": None, "confidence": None} for number, key in enumerate(order, 1)]
    return graph.fuse(ranked, links)


async def search_corpus(service, identity, product, dossier_id, command, request, before,
                        captured_fingerprint, revalidate, limiter, started):
    if before["total"] > embeddings.MAX_RECORDS:
        fail("This dossier exceeds the 20,000-record meaning-search limit. Use Words across the full ledger or Direct comparison in successive batches.",
             409, "evidence_capacity")
    if command.fingerprint and command.fingerprint != captured_fingerprint:
        fail("Saved evidence or access changed. Search again to see current results.", 409, "evidence_changed")
    items = before["items"]
    cached = await database(cache_rows, service, identity, product, dossier_id, command, items)
    missing = [item for item in items if item["id"] not in cached]
    encoder = embeddings.LocalEmbeddings(service.settings)
    answers, error, embedding_calls, response_items = [], None, 0, []
    prepared = len(cached)
    preparing = bool(missing)
    links = {"ranked_ids": [], "links": {}, "truncated": False}
    async def current():
        if await request.is_disconnected():
            fail("The search connection was closed.", 499, "search_cancelled")
        await revalidate()
    if missing:
        await asyncio.to_thread(limiter.check, "evidence_prepare_user", identity.user_id, limit=90, window_seconds=60)
        await asyncio.to_thread(limiter.check, "evidence_prepare_platform", "local", limit=180, window_seconds=60)
        batch = missing[:embeddings.BATCH]
        await current()
        try:
            encoded = await encoder.encode([embeddings.passage(item) for item in batch])
        except decisions.DecisionUnavailable:
            await current()
            error, preparing, encoded = "evidence_preparation_unavailable", False, None
        if encoded is not None:
            embedding_calls = 1
            await current()
            await database(save_batch, service, identity, product, dossier_id, command,
                                captured_fingerprint, batch, encoded)
            prepared += len(batch)
        # A separate request ranks; each preparation checkpoint has a finite cost
        # and is safely resumable after closing the tab or losing the connection.
    elif items:
        await asyncio.to_thread(limiter.check, "private_evidence_user", identity.user_id, limit=6, window_seconds=60)
        await asyncio.to_thread(limiter.check, "private_evidence_platform", "local", limit=30, window_seconds=60)
        await current()
        try:
            encoded = await encoder.encode(["query: " + command.query])
        except decisions.DecisionUnavailable:
            await current()
            error, encoded = "evidence_ranking_unavailable", None
        embedding_calls = int(encoded is not None)
        await current()
        links = await database(relationships, service, identity, product, dossier_id, items, command.query)
        ranked = (await asyncio.to_thread(rank_records, command.query, items, cached, encoded[0]["vector"], links)
            if encoded else lexical_fallback(command.query, items, links))
        response_items = ranked[command.offset:command.offset + BATCH_SIZE]
        engine = decisions.LayaEngine(service.settings)
        try:
            async with asyncio.timeout(max(0.01, TIME_LIMIT - (perf_counter() - started))):
                for item in response_items if encoded else []:
                    await current()
                    answer = await engine.choose(semantic_state(command.query, item), INSTRUCTIONS, RELEVANCE)
                    answers.append((item["id"], answer))
        except (decisions.DecisionUnavailable, TimeoutError) as failure:
            error = failure.code if isinstance(failure, decisions.DecisionUnavailable) else "timeout"
        by_id = dict(answers)
        for item in response_items:
            if answer := by_id.get(item["id"]):
                item.update(semantic_match=answer.choice == "A", relevance_probability=answer.probabilities["A"],
                            confidence=answer.confidence)
    fallback = error in {"evidence_preparation_unavailable", "evidence_ranking_unavailable"}
    if fallback:
        links = await database(relationships, service, identity, product, dossier_id, items, command.query)
        response_items = lexical_fallback(command.query, items, links)[command.offset:command.offset + BATCH_SIZE]
    await current()
    measure = decisions.measurement("laya", [answer for _, answer in answers], service.settings, error=error)
    measure.update({"engine": "local_retrieval", "models": sorted(set(measure["models"] + ([embeddings.MODEL] if embedding_calls else []))),
        "requests_completed": embedding_calls + len(answers), "embedding_requests": embedding_calls,
        "latency_ms": round((perf_counter() - started) * 1000, 2), "estimated_cost_usd": None,
        "cost_scope": "Local preparation, query and decision compute are not metered; cost unknown, not zero.",
        "accuracy": None, "accuracy_basis": "Independent NoMIRACL sample evaluates retrieval, not this dossier's relevance or medical/legal accuracy."})
    end = command.offset + len(response_items)
    return {"dossier_id": dossier_id, "query": command.query, "mode": "corpus", "method": "lexical_graph_fallback" if fallback else "local_corpus_hybrid",
        "semantic_available": not fallback, "graph_truncated": links["truncated"],
        "items": response_items, "total_records": before["total"], "matching_records": None,
        "examined_records": 0 if preparing else len(items), "offset": command.offset, "batch_size": BATCH_SIZE,
        "next_offset": end if not preparing and end < len(items) else None, "as_of": iso(command.as_of),
        "fingerprint": captured_fingerprint, "measurement": measure, "preparing": preparing,
        "prepared_records": prepared, "preparation_batch": embeddings.BATCH,
        "coverage": "All currently permitted captured passages and source-linked findings in completed private investigations in this dossier are ranked, up to 20,000 records. "
            "Every ranked candidate remains available, including uncertain or model-negative records. Exact names and currently cited evidence relationships also influence ranking. "
            "Uncaptured files, public discussions and the live web are outside this saved-evidence search. "
            "Local preparation considers up to 512 tokens from each title, finding and the first 2,400 passage characters; longer text can be truncated. "
            "Laya independently comments on the displayed 12 candidates without suppressing or changing their corpus ranking. "
            "Similarity and model opinions do not verify truth. "
            + ("Local meaning search is unavailable. Results use words and cited relationships; prepared vectors are retained for a retry." if fallback else
               "Preparation is incomplete; no whole-dossier ranking is claimed yet." if preparing else
               "Direct comparison is partly unavailable; corpus ranking remains complete." if error else "")}
