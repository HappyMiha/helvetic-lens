"""Observed public research work, never a score for coverage or answer quality."""
from . import product_query_recovery as query_recovery
from . import product_source_recovery as recovery
from .product_investigation_models import InvestigationBranch, InvestigationSource
from .product_investigations import rows

CONTRACT = "observed-research-scope/v1"
SYSTEM = """research_scope is a server-observed account of this episode at the
time of this request. Explain consequential gaps in your existing uncertainties
or assessment limitations. Completed searches return candidates, not evidence;
completed reads capture selected passages, not entire documents. Candidate counts
are appearances, not unique or independent sources. Failed/interrupted work and
unexamined candidates cannot establish absence. Open questions are workflow gaps,
not proof that other questions are answered. No count establishes relevance,
truth, complete coverage or an answer. Unknown scope must remain unknown. Do not
invent missing operations, provider failures or reasons. source_recovery describes
failed reads and bounded checks of already retrieved alternatives; captures do not
prove equal authority, relevance or an answer. Preserve exhausted options and
unfinished work. query_recovery records an unconfirmed alternate search wording,
not corrected intent or evidence. Distinguish a proposed query from executed
retrieval and actual captures. Original question remains authoritative. No extra model request.
"""
RESOURCES = {"search_requests", "source_fetches", "model_calls", "decision_calls",
    "active_seconds", "branch_budget", "depth_budget"}


def observed(session, run, available, *, invalid=False):
    value = {"contract": CONTRACT, "status": "unknown"}
    data = run.research_state
    if data["exploration"].get("scope_contract") != CONTRACT:
        return value
    # Revoked material must not survive as derived counts. Duplicates are already
    # intentionally outside the briefing's public source set.
    captured = [s for s in rows(session, InvestigationSource, run)
        if s.kind == "public_source" and not s.snapshot.get("duplicate_of")]
    if invalid or any(s.id not in available or s.sha256 != s.snapshot.get("sha256", s.sha256)
            for s in captured):
        return {**value, "status": "evidence_changed"}
    questions = data["questions"]
    question_ids = {q["id"] for q in questions}
    branches = [b for b in rows(session, InvestigationBranch, run)
        if b.checkpoint.get("question_id") in question_ids
        and not b.checkpoint.get("research_control")
        and not b.checkpoint.get("public_file_id")
        and not b.checkpoint.get("contribution_entry_id")]
    steps = [s for b in branches for s in b.checkpoint.get("steps", [])]

    def attempts(phase):
        return {status: sum(s.get("phase") == phase and s.get("status") == status for s in steps)
            for status in ("completed", "unavailable", "interrupted", "running")}

    candidates = {"retrieved": 0, "not_evaluated": 0, "evaluation_unavailable": 0,
        "selected_not_read": 0}
    indexes = {"completed": 0, "unavailable": 0, "unknown_searches": 0}
    checkpoints = []
    for branch in branches:
        prior = branch.checkpoint.get("query_recovery", {}).get("prior")
        if prior:
            checkpoints.append(prior)
        checkpoints.append(branch.checkpoint)
    for checkpoint in checkpoints:
        lanes = checkpoint.get("coverage", {}).get("retrieval", {}).get("lanes")
        if lanes is None:
            indexes["unknown_searches"] += sum(s.get("phase") == "search" and s.get("status") == "completed"
                for s in checkpoint.get("steps", [])[checkpoint.get("query_recovery", {}).get("start_step", 0):])
        else:
            indexes["completed"] += sum(lane.get("status") == "complete" for lane in lanes)
            indexes["unavailable"] += sum(lane.get("status") == "unavailable" for lane in lanes)
        counts = checkpoint.get("candidate_counts", {})
        candidates["retrieved"] += counts.get("retrieved", 0)
        candidates["not_evaluated"] += counts.get("outside_candidate_budget", 0) + max(
            0, len(checkpoint.get("candidates", [])) - checkpoint.get("gate_index", 0))
        decisions = {d["id"]: d.get("verdict") for d in checkpoint.get("decisions", [])}
        candidates["evaluation_unavailable"] += sum(v in {"unavailable", "uncertain"} for v in decisions.values())
        attempted = set(checkpoint.get("attempted_urls", []))
        candidates["selected_not_read"] += sum(i["url"] not in attempted for i in checkpoint.get("items", []))
    pending = [q for q in questions if q["status"] in {"open", "investigating", "unresolved"}]
    stops = set(data.get("stops", [])) | {q.get("waiting_reason") for q in pending}
    material = list(available.values())
    return {**value, "status": "ready", "activity": run.status,
        "searches": attempts("search"), "indexes": indexes,
        "reads": attempts("read"), "candidates": candidates,
        "material": {"sources": len(material),
            "passages": sum(len(s.snapshot.get("excerpts", [])) for s in material),
            "truncated_sources": sum(s.snapshot.get("text_truncated") is True for s in material),
            "unknown_reader_scope": sum(not isinstance(s.snapshot.get("text_truncated"), bool) for s in material)},
        "questions": {"open": len(pending), "not_started": sum(not q.get("branch_id") for q in pending)},
        "budget_stops": sorted(stops & RESOURCES),
        "source_recovery": recovery.projection(session, run, available),
        "query_recovery": query_recovery.projection(session, run, available)}
