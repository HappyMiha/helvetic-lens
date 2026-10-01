"""Resumable local semantic recall before public planning, using the shared cache."""
from copy import deepcopy

from sqlalchemy import select

from . import evidence_embeddings as embeddings
from . import evidence_graph_retrieval as graph
from . import research_knowledge as knowledge
from .db import utcnow
from .decision_engines import DecisionUnavailable
from .decision_search import lexical_order
from .product_corpus_search import rank_records
from .product_evidence_search import ledger
from .product_investigation_models import InvestigationBranch, InvestigationSource
from .product_investigations import event, rows, scope
from .product_models import ProductDossier
from .product_operations import fingerprint
from .product_retrieval_models import EvidenceVector

MAX_BATCHES = 8


def seed(session, run, product):
    if not session.scalar(knowledge.eligible_sources(run).limit(1)):
        knowledge.recall(session, run, product)
        return
    branches = rows(session, InvestigationBranch, run)
    branch = next((b for b in branches if b.phase == "plan"), None)
    if branch is None:
        branch = InvestigationBranch(**scope(run), query="Recall saved dossier evidence", phase="recall",
            reason="Read relevant saved evidence before new discovery.", checkpoint={"research_control": True, "recall_only": True})
        session.add(branch)
    branch.phase = "recall"


def records(session, run):
    source_ids = knowledge.eligible_sources(run).with_only_columns(InvestigationSource.id)
    visible = ledger(session.get_bind().dialect.name, run.dossier_id, run.organization_id, utcnow())
    # Public capture passages only: a mixed private/public finding must never
    # influence a public planner. Private evidence retains its separate branch.
    selected = session.execute(select(visible).where(visible.c.source_id.in_(source_ids), visible.c.kind == "passage")
        .order_by(visible.c.created_at.desc(), visible.c.id).limit(embeddings.MAX_RECORDS + 1)).mappings()
    items = [{key: value for key, value in dict(item).items() if key != "created_at"} for item in selected]
    return items[:embeddings.MAX_RECORDS], len(items) > embeddings.MAX_RECORDS


def mark(items):
    return fingerprint([(i["id"], i["sha256"], embeddings.text_hash(embeddings.passage(i))) for i in items])


def prepare(session, run, state, work):
    items, truncated = records(session, run)
    expected = {i["id"]: embeddings.text_hash(embeddings.passage(i)) for i in items}
    cached = {}
    for saved in session.scalars(select(EvidenceVector).where(EvidenceVector.dossier_id == run.dossier_id,
            EvidenceVector.organization_id == run.organization_id, EvidenceVector.model == embeddings.MODEL)):
        if expected.get(saved.record_key) == saved.input_sha256:
            try:
                cached[saved.record_key] = {"vector": embeddings.unpack(saved.vector), "truncated": saved.truncated}
            except DecisionUnavailable:
                pass
    parent = session.get(ProductDossier, run.dossier_id)
    work.update(recall_items=items, recall_cached=cached, recall_graph=graph.project(session, parent, items, run.question),
        recall_fingerprint=mark(items), recall_truncated=truncated, recall_batches=state.get("recall_batches", 0))
    work["input"] = {"question": run.question, "eligible_records": len(items), "prepared_records": len(cached),
        "evidence_fingerprint": work["recall_fingerprint"], "semantic_capacity_exceeded": truncated}


async def execute(service, work):
    items, cached = work["recall_items"], deepcopy(work["recall_cached"])
    missing = [i for i in items if i["id"] not in cached]
    encoded, batch, query_vector, error = [], [], None, None
    encoder = embeddings.LocalEmbeddings(service.settings)
    try:
        if missing and not work["recall_truncated"] and work["recall_batches"] < MAX_BATCHES:
            batch = missing[:embeddings.BATCH]
            encoded = await encoder.encode([embeddings.passage(i) for i in batch])
            cached.update({i["id"]: vector for i, vector in zip(batch, encoded)})
        elif missing:
            error = "preparation_budget" if not work["recall_truncated"] else "record_capacity"
        elif items:
            query_vector = (await encoder.encode(["query: " + work["question"]]))[0]["vector"]
    except (DecisionUnavailable, TimeoutError):
        error = "local_semantic_unavailable"
        batch, encoded = [], []
    pending = bool(batch and not error)
    if pending:
        return {"pending": True, "batch": [i["id"] for i in batch], "vectors": encoded, "prepared_records": len(cached)}
    if query_vector:
        ranked = rank_records(work["question"], items, cached, query_vector)
        method = "BM25 + local multilingual E5 + cited evidence relationships"
    else:
        by_id = {i["id"]: i for i in items}
        order = lexical_order(work["question"], [{**i, "summary": i["quote"]} for i in items])
        ranked = [{**by_id[key], "rank_score": 1 / (60 + index)} for index, key in enumerate(order, 1)]
        method = "BM25 + cited evidence relationships; local semantic ranking unavailable or still preparing"
    ranked = graph.fuse(ranked, work["recall_graph"])
    sources = list(dict.fromkeys(i["source_id"] for i in ranked))[:knowledge.RECALL_SOURCE_LIMIT]
    return {"pending": False, "source_ids": sources, "method": method,
        "examined_records": len(items), "prepared_records": len(cached), "semantic_status": "complete" if query_vector else "empty" if not items else error,
        "capacity_exceeded": work["recall_truncated"], "graph_truncated": work["recall_graph"]["truncated"]}


def apply(session, run, branch, state, work, result):
    current, _ = records(session, run)
    if mark(current) != work["recall_fingerprint"]:
        # No stale vectors/copies are committed. Start again from current rights;
        # already prepared permitted rows remain available in the shared cache.
        state["recall_restarts"] = state.get("recall_restarts", 0) + 1
        if state["recall_restarts"] >= 3:
            branch.phase = "plan"
            if state.get("recall_only"):
                branch.status = "completed"
            state["error"] = "Saved evidence changed repeatedly during recall; current research continues without recalled context."
        return
    if result.get("pending"):
        by_id = {i["id"]: i for i in current}
        for identifier, vector in zip(result["batch"], result["vectors"]):
            item = by_id[identifier]
            saved = session.scalar(select(EvidenceVector).where(EvidenceVector.dossier_id == run.dossier_id,
                EvidenceVector.organization_id == run.organization_id, EvidenceVector.record_key == identifier))
            if saved is None:
                saved = EvidenceVector(dossier_id=run.dossier_id, organization_id=run.organization_id,
                    investigation_id=item["investigation_id"], source_id=item["source_id"], claim_id=None, record_key=identifier)
                session.add(saved)
            saved.model, saved.input_sha256 = embeddings.MODEL, embeddings.text_hash(embeddings.passage(item))
            saved.vector, saved.input_tokens, saved.truncated = embeddings.pack(vector["vector"]), vector["input_tokens"], vector["truncated"]
        state["recall_batches"] = state.get("recall_batches", 0) + 1
        event(session, run, "saved_evidence_preparing", prepared_records=result["prepared_records"],
            eligible_records=len(current), resumable=True)
        return
    knowledge.recall(session, run, work["product"], selected_ids=result["source_ids"], retrieval=result)
    branch.phase = "plan"
    if state.get("recall_only"):
        branch.status = "completed"
    state["recall_done"] = True
