"""Bounded organization diagnostics; unknown usage is never reported as zero."""
from datetime import timedelta

from sqlalchemy import or_, select

from .config import DomainError
from .db import utcnow
from .interest_assessment import BriefExecution
from .models import InterestEventAssessment as Assessment
from .topic_matching import _iso


def measurement(provenance, status):
    empty = {"state": "missing", "provider_calls": None, "measured_calls": None,
             "input_tokens": None, "duration_ms": None, "runtime_fingerprint": None,
             "complete_input_coverage": False, "output_tokens": None}
    if status != "succeeded" or not isinstance(provenance, dict) or not provenance.get("execution"):
        return empty
    try:
        proof = BriefExecution.model_validate(provenance["execution"], strict=True)
        calls = provenance.get("provider_calls")
        measured = len(proof.generation_measurements)
        if type(calls) is not int or not measured <= calls <= 2:
            raise ValueError("Invalid provider call count")
    except (ValueError, TypeError):
        return {**empty, "state": "invalid"}
    return {**empty, "state": "recorded", "provider_calls": calls, "measured_calls": measured,
            "input_tokens": sum(row.input_tokens for row in proof.generation_measurements),
            "duration_ms": proof.duration_ms, "runtime_fingerprint": proof.runtime_fingerprint,
            "complete_input_coverage": measured == calls}


def page(session, organization, *, days=7, status="", locale="", cursor="", limit=20):
    if days not in {1, 7, 30, 90} or not 1 <= limit <= 50 or status not in {"", "queued", "running", "succeeded", "failed", "superseded"} or locale not in {"", "de", "fr", "it", "rm", "en"}:
        raise DomainError("Choose valid diagnostic filters.", 422, "invalid_brief_diagnostics")
    now = utcnow()
    filters = [Assessment.organization_id == organization, Assessment.created_at >= now - timedelta(days=days), Assessment.created_at <= now]
    if status:
        filters.append(Assessment.status == status)
    if locale:
        filters.append(Assessment.input_manifest["locale"].as_string() == locale)
    # Never load result, history_context, profile facts or passage-bearing manifests.
    query = select(Assessment.id, Assessment.event_id, Assessment.status, Assessment.attempts,
        Assessment.created_at, Assessment.started_at, Assessment.finished_at, Assessment.provenance,
        Assessment.input_manifest["locale"].as_string().label("locale"),
        Assessment.input_manifest["model"]["model"].as_string().label("model"),
    ).where(*filters)
    if cursor:
        position = session.execute(select(Assessment.id, Assessment.created_at).where(*filters, Assessment.id == cursor)).first()
        if position is None:
            raise DomainError("Refresh these diagnostic filters.", 422, "invalid_brief_diagnostics")
        query = query.where(or_(Assessment.created_at < position.created_at,
            (Assessment.created_at == position.created_at) & (Assessment.id < position.id)))
    records = list(session.execute(query.order_by(Assessment.created_at.desc(), Assessment.id.desc()).limit(limit+1)).mappings())
    items = []
    for row in records[:limit]:
        items.append({"id": row["id"], "event_id": row["event_id"], "status": row["status"],
            "attempts": row["attempts"], "locale": row["locale"],
            "model": row["model"][:300] if isinstance(row["model"], str) else None,
            "created_at": _iso(row["created_at"]), "started_at": _iso(row["started_at"]),
            "finished_at": _iso(row["finished_at"]), "measurement": measurement(row["provenance"], row["status"])})
    return {"items": items, "next_cursor": items[-1]["id"] if len(records)>limit else None,
            "as_of": _iso(now), "days": days, "ai_calls": 0,
            "unmeasured": ["all_attempt_costs", "output_tokens", "reader_cache_hits", "queue_wait"]}
