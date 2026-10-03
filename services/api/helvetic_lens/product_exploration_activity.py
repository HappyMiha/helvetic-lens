"""A current public research checkpoint, bounded by the actual worker receipt."""
from datetime import UTC, datetime, timedelta

from . import product_source_recovery as recovery
from .db import utcnow
from .models import Job
from .product_api import iso
from .product_investigation_models import InvestigationBranch
from .product_investigations import ACTIVE, rows
from .product_operations import fingerprint
from .research_knowledge import captured_at

CONTRACT = "research-activity/v1"
PURPOSE_CONTRACT = "research-purpose/v1"
PHASES = {"plan", "search", "gate", "gate_review", "read", "extract", "reflect", "orient", "brief", "compare", "reformulate", "document_review"}


def record(run, job, state, work):
    if (run.research_state or {}).get("exploration", {}).get("activity_contract") != CONTRACT:
        return
    state["current_activity"] = {"contract": CONTRACT, "step_id": work["token"],
        "job_id": job.id, "leased_at": iso(job.leased_at),
        "expires_at": iso(utcnow() + timedelta(seconds=work["deadline_seconds"]))}
    if run.research_state["exploration"].get("purpose_contract") == PURPOSE_CONTRACT:
        question = next((q for q in run.research_state["questions"]
            if q["id"] == state.get("question_id") and q.get("branch_id") == work["branch_id"]), None)
        if question:
            state["current_activity"]["purpose_fingerprint"] = purpose_binding(run, question)


def purpose_binding(run, question):
    return fingerprint({"original_question": run.question, **{k: question.get(k) for k in
        ("id", "question", "query", "purpose", "priority", "trigger", "claim_id",
            "branch_id", "parent_branch_id", "kind")}})


def purpose(session, run, question, receipt, available):
    """A saved research rationale, never reconstructed from queries or model thoughts."""
    from pydantic import ValidationError

    from . import product_exploration_followups as followups
    from .config import DomainError
    from .product_investigations import Citation, citation

    state = run.research_state["exploration"]
    if (state.get("purpose_contract") != PURPOSE_CONTRACT or not question
            or receipt.get("purpose_fingerprint") != purpose_binding(run, question)):
        return None
    text = question.get("purpose")
    if not isinstance(text, str) or not 5 <= len(text.strip()) <= 500:
        return None
    value = {"contract": PURPOSE_CONTRACT, "text": text.strip()}
    trigger = question.get("trigger")
    if trigger:
        dependencies = state.get("adaptive_dependencies", [])
        if not followups.open_context_current(session, run, question, dependencies):
            return None
        if not isinstance(trigger, dict):
            return None
        source = available.get(trigger.get("source_id"))
        if (not source or source.sha256 != trigger.get("sha256") or not any(
                d["source_id"] == source.id and d["sha256"] == source.sha256 for d in dependencies)):
            return None
        try:
            cited = citation(source, Citation(quote=trigger["quote"], locator=trigger["locator"]))
        except (DomainError, ValidationError, KeyError):
            return None
        return {**value, "kind": "source_follow_up", "trigger": {
            "quote": cited["quote"], "locator": cited["locator"],
            "source": {"id": source.id, "title": source.title, "url": source.url}}}
    if followups.reference(run):
        # Selected checks already have a current, typed ancestor receipt. An
        # untyped earlier briefing is not enough to reconstruct this provenance.
        context = followups.context(session, run)
        if (not context or context["status"] != "ready" or context["question"] != question["question"]
                or context["purpose"] != text):
            return None
        return {**value, "kind": "source_follow_up", "trigger": {
            "quote": context["quote"], "locator": context["locator"],
            "source": {k: context["source"][k] for k in ("id", "title", "url")}}}
    if question.get("kind") == "planned" and not question.get("parent_branch_id"):
        return {**value, "kind": "planned"}
    return None


def projection(session, run, available, *, invalid=False):
    value = {"contract": CONTRACT, "status": "unknown"}
    if invalid:
        return {**value, "status": "evidence_changed"}
    if run.research_state["exploration"].get("activity_contract") != CONTRACT:
        return value
    if run.status not in ACTIVE:
        return {**value, "status": "paused" if run.status == "paused" else "finished"}
    branches = rows(session, InvestigationBranch, run)
    inflight = [b for b in branches if b.status in ACTIVE and b.checkpoint.get("inflight")]
    if not inflight:
        job = session.get(Job, run.job_id) if run.job_id else None
        if job and job.state == "queued" and job.error_code == "research_provider_backoff":
            return {**value, "status": "waiting", "resume_at": iso(job.available_at),
                "reason": "The analysis provider is temporarily unavailable. Saved reading is retained; this step will resume automatically."}
        return {**value, "status": "waiting"}
    if len(inflight) != 1:
        return value
    branch = inflight[0]
    state = branch.checkpoint
    question = next((q for q in run.research_state["questions"]
        if q["id"] == state.get("question_id") and q.get("branch_id") == branch.id), None)
    control = (state.get("research_control") and branch.phase in {"plan", "orient", "brief"}
        or state.get("comparison") and branch.phase == "compare")
    if (not (question or control) or branch.phase not in PHASES
            or state.get("public_file_id") or state.get("contribution_entry_id")):
        return value
    receipt = state.get("current_activity", {})
    steps = state.get("steps", [])
    if (receipt.get("contract") != CONTRACT or not steps
            or receipt.get("step_id") != state["inflight"]
            or steps[-1].get("id") != state["inflight"]
            or steps[-1].get("phase") != branch.phase or steps[-1].get("status") != "running"):
        return value
    job = session.get(Job, run.job_id) if run.job_id else None
    try:
        expiry = datetime.fromisoformat(receipt["expires_at"])
        if expiry.tzinfo is None:
            return value
        expiry = expiry.astimezone(UTC)
    except (KeyError, ValueError, TypeError):
        return value
    now = utcnow()
    remaining = int((expiry - now).total_seconds() * 1000)
    if (not job or receipt.get("job_id") != job.id or job.target_id != run.id
            or job.type != "product_investigation" or job.organization_id != run.organization_id
            or job.state != "running" or not job.lease_owner or job.cancel_requested
            or not job.leased_at or receipt.get("leased_at") != iso(job.leased_at)
            or remaining <= 0 or remaining > 90000):
        return {**value, "status": "stale"}
    latest = max(available.values(), key=lambda source: (source.created_at.replace(tzinfo=source.created_at.tzinfo or UTC).timestamp(), source.id), default=None)
    return {**value, "status": "working", "phase": branch.phase,
        "question": question["question"] if question else run.question,
        "purpose": purpose(session, run, question, receipt, available),
        "observed_at": iso(now), "valid_for_ms": remaining,
        "checking_alternative": recovery.alternative(state, branch.phase),
        "testing_query": bool(state.get("query_recovery", {}).get("query")) and branch.phase == "search",
        "latest_source": {"id": latest.id, "title": latest.title, "url": latest.url,
            "captured_at": captured_at(latest)} if latest else None}
