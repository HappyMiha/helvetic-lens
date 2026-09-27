"""Retained human originals and private, serialized contribution analysis."""
import asyncio
import hashlib
import json
import sys
from copy import deepcopy
from uuid import uuid4

from sqlalchemy import select

from .product_api import entry_payload, fail, iso
from .product_investigation_models import Investigation, InvestigationBranch
from .product_investigations import enqueue, event, plan, rows, scope, snapshot, summary
from .product_models import DossierEntry

PUBLIC_READ_PURPOSE = "Identify the main factual statements in this publicly accessible document."


def queue(session, parent, entry, identity):
    session.flush()
    question = (entry.body if entry.kind == "research_request" else
                "Review this contribution and extract relevant, source-linked findings: " + (entry.title or entry.kind))[:300]
    run = Investigation(dossier_id=parent.id, organization_id=parent.organization_id,
        request_key=str(uuid4()), trigger_entry_id=entry.id, external_discovery=False,
        question=question, created_by_user_id=identity.user_id, actor_user_id=identity.user_id,
        session_id=identity.session_id, session_organization_id=identity.organization_id)
    session.add(run)
    session.flush()
    enqueue(session, run)
    event(session, run, "contribution_queued", entry_id=entry.id, contribution_kind=entry.kind,
        disclosure="Original retained. Private analysis by the workspace model. Only a submitted URL may be fetched; no public discovery or publication.")
    return run


def original(session, identifier):
    entry = session.get(DossierEntry, identifier) if identifier else None
    if not entry:
        return None
    data = entry_payload(session, entry)
    return {key: data[key] for key in ("id", "kind", "title", "body", "url", "byte_size", "sha256", "author", "created_at")}


def analysis(session, entry):
    if not entry.data_json.get("analysis_requested"):
        return None
    run = session.scalar(select(Investigation).where(Investigation.trigger_entry_id == entry.id))
    return summary(run) if run else None


def capture(session, run, entry, result, *, kind):
    # The same entry can contain both a comment and a URL; keep both origins.
    item = {**result, "title": entry.title or entry.kind.replace("_", " ").capitalize(),
        "url": entry.url if kind != "uploaded_file" else "", "key": f"entry:{entry.id}:{kind}",
        "kind": kind, "origin_entry_id": entry.id, "origin_date": iso(entry.created_at),
        "captured_from": entry.kind, "allow_discovery": False}
    return snapshot(session, run, item, captured=True)[0]


def seed(session, run, parent, settings):
    from .product_investigations import capabilities
    from .product_research import research_sources

    entry = session.get(DossierEntry, run.trigger_entry_id)
    if entry.body:
        result = {"status": "complete", "sha256": hashlib.sha256(entry.body.encode()).hexdigest(),
            "excerpts": [{"passage": f"original-char-{i + 1}", "text": entry.body[i:i + 1200]}
                         for i in range(0, len(entry.body), 1200)],
            "scope": "Exact submitted human text, not a machine finding or independently verified fact."}
        source = capture(session, run, entry, result, kind="human_contribution")
        session.add(InvestigationBranch(**scope(run), query="Review submitted text", phase="extract",
            reason="Extract attributable evidence from the retained original.",
            checkpoint={"saved": True, "source_ids": [source.id], "extract_index": 0}))
    if entry.url or entry.kind == "file":
        session.add(InvestigationBranch(**scope(run), query="Read submitted file" if entry.kind == "file" else "Read submitted source URL",
            phase="read", reason="Capture the submitted source within access and format limits.",
            checkpoint={"contribution_entry_id": entry.id, "items": [{"url": entry.url, "title": "Submitted public document"}],
                        "file": entry.kind == "file"}))
    if entry.kind in {"correction", "research_request"}:
        saved = [item for item in research_sources(session, parent, run.question, run.organization_id)
                 if item.get("key") != entry.id][:2]
        source_ids = [snapshot(session, run, item)[0].id for item in saved]
        if source_ids:
            session.add(InvestigationBranch(**scope(run), query="Check saved dossier context", phase="extract",
                reason="Compare the request against two bounded saved evidence snapshots. No external search.",
                checkpoint={"saved": True, "source_ids": source_ids, "extract_index": 0}))
    run.status = "running"
    plan(session, run, "Private review of a retained contribution; public discovery is disabled.", trigger={"entry_id": entry.id})
    available = capabilities(settings, parent.product)
    for item in available:
        if item["id"] in {"public_web", "scientific_literature"}:
            item.update(available=False, description="Not used for private contributions. Use explicit Ask for public discovery.")
    event(session, run, "capabilities_resolved", capabilities=available)


async def read_file(folder, data):
    # Storage key is created by the server, never a caller-provided path.
    path = folder / data["artifact_key"]
    if path.parent != folder or not path.is_file():
        return {"error": "Original file is temporarily unavailable. Retry after storage is restored."}
    with path.open("rb") as stream:
        body = stream.read(2 * 1024 * 1024 + 1)
    if len(body) > 2 * 1024 * 1024:
        return {"error": "Original retained. Automatic extraction accepts files up to 2 MB."}
    if hashlib.sha256(body).hexdigest() != data["sha256"]:
        return {"error": "Original integrity check failed. No text was analysed."}
    process = await asyncio.create_subprocess_exec(sys.executable, "-m", "helvetic_lens.product_contribution_extract",
        data["title"], data["content_type"], stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    try:
        async with asyncio.timeout(25):
            output, _ = await process.communicate(body)
        if process.returncode or len(output) > 250000:
            return {"error": "Original retained. Local extraction could not finish within its resource limits."}
        result = json.loads(output)
        return {**result, "sha256": data["sha256"]}
    except TimeoutError:
        return {"error": "Original retained. Local extraction reached its time limit."}
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()


def retry(session, run):
    if not run.trigger_entry_id or run.status not in {"failed", "completed"}:
        fail("Retry is available for finished contribution reviews with unavailable steps.", 409)
    failed = [branch for branch in rows(session, InvestigationBranch, run) if branch.status == "failed"]
    if not failed:
        fail("There are no unavailable contribution steps to retry.", 409)
    for branch in failed:
        state = deepcopy(branch.checkpoint)
        state.pop("inflight", None)
        state.pop("error", None)
        if state.get("source_ids"):
            # Only advance() skips a failed extraction index. Revisit unavailable
            # extraction steps, retaining successful indices and all evidence.
            state["retry_indices"] = sorted(set(state.get("failed_extract_indices", [])))
            if state["retry_indices"]:
                state["extract_index"] = state["retry_indices"].pop(0)
            else:
                state["extract_index"] = 0
            state["failed_extract_indices"] = []
            branch.phase = "extract"
        else:
            state["read_index"] = 0
            branch.phase = "read"
        branch.status, branch.checkpoint = "queued", state
    plan(session, run, "Editor requested another attempt at unavailable contribution steps; completed evidence is retained.")
