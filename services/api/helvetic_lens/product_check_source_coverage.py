"""Receipts for actual recurring checks; no source subscription or extra retrieval."""
from sqlalchemy import select

from .decision_search import public_url
from .product_investigation_models import Investigation, InvestigationSource, WebResearchTrigger
from .product_public_research import sources_visible
from .product_source_reviews import current_reviews
from .research_knowledge import captured_at

CONTRACT = "check-source-coverage/v1"
PRIOR_LIMIT = 12
LOOKBACK_LIMIT = 60
SCOPE = ("Only the sources returned by this saved-question search were eligible for reading. "
    "Earlier captures listed here were not automatically revisited. A captured-text change is not a verified factual change.")


def seed(session, run):
    candidates = list(session.scalars(select(InvestigationSource).join(Investigation,
        Investigation.id == InvestigationSource.investigation_id).join(WebResearchTrigger,
        WebResearchTrigger.investigation_id == Investigation.id).where(
            Investigation.dossier_id == run.dossier_id, Investigation.id != run.id,
            Investigation.question == run.question, WebResearchTrigger.question == run.question,
            Investigation.publication_id.is_(None), sources_visible(),
            InvestigationSource.kind == "public_source")
        .order_by(InvestigationSource.created_at.desc(), InvestigationSource.id.desc()).limit(LOOKBACK_LIMIT + 1)))
    prior, seen = [], set()
    for source in candidates[:LOOKBACK_LIMIT]:
        if source.url in seen or not public_url(source.url):
            continue
        seen.add(source.url)
        if len(prior) < PRIOR_LIMIT:
            prior.append({"id": source.id, "investigation_id": source.investigation_id,
                "url": source.url, "sha256": source.sha256,
                "content_key": source.snapshot.get("web_content_fingerprint")})
    return {"contract": CONTRACT, "prior": prior,
        "prior_truncated": len(candidates) > LOOKBACK_LIMIT or len(seen) > PRIOR_LIMIT}


def record(state, work):
    if not state.get("recurring_web") or state.get("source_coverage", {}).get("contract") != CONTRACT:
        return
    step = state["steps"][-1]
    if work["phase"] == "read":
        step["source_url"] = work["item"]["url"]
        step["skipped"] = bool(work.get("skip"))
    elif work["phase"] == "extract":
        step["source_id"] = work["source_id"]


def available(session, run, source):
    if not source or source.dossier_id != run.dossier_id or source.kind != "public_source":
        return False
    return bool(session.scalar(select(Investigation.id).join(WebResearchTrigger,
        WebResearchTrigger.investigation_id == Investigation.id).where(
            Investigation.id == source.investigation_id, Investigation.question == run.question,
            WebResearchTrigger.question == run.question, Investigation.publication_id.is_(None), sources_visible())))


def retained(session, run, pin):
    source = session.get(InvestigationSource, pin["id"])
    if (not available(session, run, source) or source.investigation_id != pin["investigation_id"]
            or source.url != pin["url"] or source.sha256 != pin["sha256"]
            or source.snapshot.get("web_content_fingerprint") != pin.get("content_key")):
        return None
    return source


def receipt(step):
    return {"status": step.get("status", "not_started"),
        "started_at": step.get("started_at"), "finished_at": step.get("finished_at")}


def hidden():
    return {"title": "Source no longer available", "url": None, "source_id": None,
        "investigation_id": None, "read_status": "unavailable", "analysis_status": "unavailable",
        "capture_state": None, "attempt": None, "attempt_count": 0, "last_success_at": None}


def candidate(session, run, item, steps, blocked):
    url = item.get("url", "")
    if not public_url(url) or url in blocked:
        return hidden()
    attempts = [s for s in steps if s.get("phase") == "read" and s.get("source_url") == url]
    step = attempts[-1] if attempts else {}
    state = {"completed": "read", "running": "reading", "unavailable": "failed", "interrupted": "interrupted"}
    row = {"title": str(item.get("title") or url)[:500], "url": url, "source_id": None,
        "investigation_id": None, "read_status": state.get(step.get("status"), "not_checked"),
        "analysis_status": "not_started", "capture_state": None, "attempt": receipt(step) if step else None,
        "attempt_count": len(attempts), "last_success_at": None}
    if step.get("skipped"):
        row["read_status"] = "not_checked"
    if row["read_status"] != "read":
        return row
    source = session.get(InvestigationSource, step.get("source_id")) if step.get("source_id") else None
    if not available(session, run, source) or source.investigation_id != run.id or source.url != url:
        return hidden()
    row.update(source_id=source.id, investigation_id=run.id,
        capture_state=source.snapshot.get("capture_state"), captured_at=captured_at(source))
    extraction = [s for s in steps if s.get("phase") == "extract" and s.get("source_id") == source.id]
    last = extraction[-1] if extraction else {}
    row["analysis_status"] = ("not_needed" if row["capture_state"] == "unchanged" else
        {"completed": "analysed", "running": "analysing", "unavailable": "failed", "interrupted": "interrupted"}
        .get(last.get("status"), "not_started"))
    row["analysis_attempt"] = receipt(last) if last else None
    baseline_id = source.snapshot.get("previous_analysed_source_id")
    baseline = session.get(InvestigationSource, baseline_id) if baseline_id else None
    if available(session, run, baseline):
        row["last_success_at"] = baseline.snapshot.get("analysis_completed_at")
    if row["analysis_status"] == "analysed":
        row["last_success_at"] = source.snapshot.get("analysis_completed_at")
    return row


def project(session, run, branches):
    states = [b.checkpoint for b in branches if b.checkpoint.get("recurring_web")]
    state = states[0] if states else {}
    saved = state.get("source_coverage", {})
    result = {"contract": CONTRACT, "recorded": saved.get("contract") == CONTRACT,
        "scope": SCOPE, "sources": [], "search": None, "prior_limit": PRIOR_LIMIT,
        "prior_truncated": bool(saved.get("prior_truncated")), "prior_hidden": 0}
    if not result["recorded"]:
        result["scope"] = "Source-by-source receipts were not recorded for this check. Counts cannot establish which pages were read."
        return result
    blocked = {url for url, review in current_reviews(session, run.dossier_id).items()
        if review.data_json["decision"] == "exclude"}
    steps = state.get("steps", [])
    searches = [s for s in steps if s.get("phase") == "search"]
    result["search"] = receipt(searches[-1]) if searches else receipt({})
    seen = set()
    for item in state.get("items", []):
        if item.get("url") in seen:
            continue
        seen.add(item.get("url"))
        result["sources"].append(candidate(session, run, item, steps, blocked))
    for pin in saved.get("prior", []):
        if pin["url"] in seen:
            continue
        source = retained(session, run, pin)
        if not source:
            result["prior_hidden"] += 1
            continue
        row = {"title": source.title[:500], "url": source.url, "source_id": source.id,
            "investigation_id": source.investigation_id, "read_status": "not_checked",
            "analysis_status": "not_started", "capture_state": None, "attempt": None,
            "attempt_count": 0, "last_success_at": source.snapshot.get("analysis_completed_at"),
            "captured_at": captured_at(source)}
        result["sources"].append(row)
    return result
