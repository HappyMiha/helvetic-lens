"""A current public research checkpoint, bounded by the actual worker receipt."""
from datetime import UTC, datetime, timedelta

from .db import utcnow
from .models import Job
from .product_api import iso
from .product_investigation_models import InvestigationBranch
from .product_investigations import ACTIVE, rows

CONTRACT = "research-activity/v1"
PHASES = {"plan", "search", "gate", "gate_review", "read", "extract", "reflect", "orient", "brief", "compare"}


def record(run, job, state, work):
    if (run.research_state or {}).get("exploration", {}).get("activity_contract") != CONTRACT:
        return
    state["current_activity"] = {"contract": CONTRACT, "step_id": work["token"],
        "job_id": job.id, "leased_at": iso(job.leased_at),
        "expires_at": iso(utcnow() + timedelta(seconds=work["deadline_seconds"]))}


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
        "observed_at": iso(now), "valid_for_ms": remaining,
        "latest_source": {"id": latest.id, "title": latest.title, "url": latest.url,
            "captured_at": iso(latest.created_at)} if latest else None}
