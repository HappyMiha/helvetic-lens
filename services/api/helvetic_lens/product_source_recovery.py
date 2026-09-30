"""Finite replacement selections after failed public reads; no new search."""
from .product_investigation_models import InvestigationBranch, InvestigationSource
from .product_investigations import ACTIVE, rows
from .product_source_reviews import current_reviews

CONTRACT = "source-recovery/v1"


def public_state(state):
    return bool(state.get("question_id")) and not any(state.get(key) for key in (
        "saved", "research_control", "contribution_entry_id", "public_file_id", "file", "recurring_web"))


def enabled(run, branch, state):
    data = run.research_state or {}
    return (data.get("exploration", {}).get("recovery_contract") == CONTRACT
        and public_state(state) and any(q["id"] == state["question_id"] and q.get("branch_id") == branch.id
            for q in data.get("questions", [])))


def recorded(state):
    return public_state(state) and state.get("source_recovery", {}).get("contract") == CONTRACT


def failed_read(state):
    if recorded(state):
        value = state["source_recovery"]
        value["failed_reads"] = value.get("failed_reads", 0) + 1


def selection_limit(state):
    from .product_read_relevance import selection_slots

    return state.get("source_limit", 2) + (state["source_recovery"]["failed_reads"] if recorded(state) else 0) + selection_slots(state)


def settle(branch, state):
    if (recorded(state) and branch.phase == "read"
            and state.get("read_index", 0) >= len(state.get("items", []))
            and state["source_recovery"]["failed_reads"]
            and len(state.get("items", [])) < selection_limit(state)
            and state.get("gate_index", 0) < len(state.get("candidates", []))):
        value = state["source_recovery"]
        value.setdefault("first_alternative_index", len(state.get("items", [])))
        value.setdefault("first_alternative_step", len(state.get("steps", [])))
        branch.phase = "gate"


def alternative(state, phase):
    if not recorded(state) or "first_alternative_index" not in state["source_recovery"]:
        return False
    return (phase in {"gate", "gate_review"} or phase == "read"
        and state.get("read_index", 0) >= state["source_recovery"]["first_alternative_index"])


def captured(state, source, fresh):
    if fresh and alternative(state, "read"):
        state["source_recovery"].setdefault("capture_ids", []).append(source.id)


def unavailable(session, run, branch, state, item):
    if not enabled(run, branch, state):
        return False
    seen = {s.url for s in rows(session, InvestigationSource, run)}
    for other in rows(session, InvestigationBranch, run):
        seen.update(other.checkpoint.get("attempted_urls", []))
    seen.update(state.get("attempted_urls", []))
    excluded = {url for url, review in current_reviews(session, run.dossier_id).items()
        if review.data_json["decision"] == "exclude"}
    return item["url"] in seen | excluded


def projection(session, run, available, *, invalid=False):
    base = {"contract": CONTRACT, "status": "unknown"}
    if invalid:
        return {**base, "status": "evidence_changed"}
    if run.research_state.get("exploration", {}).get("recovery_contract") != CONTRACT:
        return base
    result = {**base, "status": "ready", "failed_reads": 0, "candidates_checked": 0,
        "reads_attempted": 0, "captures": 0, "candidate_sets_exhausted": 0, "unfinished": 0}
    for branch in rows(session, InvestigationBranch, run):
        state = branch.checkpoint
        if not enabled(run, branch, state) or not recorded(state):
            continue
        value = state["source_recovery"]
        result["failed_reads"] += value["failed_reads"]
        start = value.get("first_alternative_step")
        steps = state.get("steps", [])[start:] if start is not None else []
        result["candidates_checked"] += sum(s["phase"] == "gate" and s["status"] != "running" for s in steps)
        result["reads_attempted"] += sum(s["phase"] == "read" for s in steps)
        result["captures"] += sum(key in available for key in value.get("capture_ids", []))
        missing = value["failed_reads"] and len(state.get("items", [])) < selection_limit(state)
        if missing and state.get("read_index", 0) >= len(state.get("items", [])):
            if state.get("gate_index", 0) >= len(state.get("candidates", [])):
                result["candidate_sets_exhausted"] += 1
        if ("first_alternative_index" in value and branch.status in ACTIVE | {"blocked"}
                and branch.phase in {"gate", "gate_review", "read"}):
            result["unfinished"] += 1
    return result
