"""One per-run coverage manifest over committed native execution receipts."""
from copy import deepcopy

from .product_api import iso
from .product_investigation_models import InvestigationBranch, InvestigationSource
from .product_investigations import rows
from .research_knowledge import source_ref

CONTRACT = "research-coverage/v1"


def unresolved_questions(run, *, answer=None):
    """Completed search branches do not discharge unanswered synthesis work."""
    questions = [{"question": q["question"], "status": q["status"], "reason": q.get("waiting_reason")}
        for q in run.research_state.get("questions", []) if q["status"] in {"open", "investigating", "unresolved"}]
    if answer is not None:
        gaps = answer.get("limitations", [])
        if not gaps and not answer.get("points"):
            gaps = [run.question]
        known = {" ".join(item["question"].split()) for item in questions}
        for gap in gaps:
            key = " ".join(gap.split())
            if key and key not in known:
                questions.append({"question": gap, "status": "unresolved", "reason": "Unresolved in the current answer."})
                known.add(key)
    return questions


def project(session, run, *, reading=False):
    branches = rows(session, InvestigationBranch, run)
    sources = rows(session, InvestigationSource, run)
    channels, executions, skipped_channels = [], [], []
    candidates = {}
    for branch in branches:
        state = branch.checkpoint
        for item in [*state.get("candidates", []), *state.get("items", [])]:
            candidates.setdefault(item["url"], {"title": item["title"], "url": item["url"],
                "read_status": "not_checked", "analysis_status": "not_started", "source_id": None,
                "last_attempt_at": None, "last_success_at": None, "reason": "Outside the completed checks so far."})
        for decision in state.get("decisions", []):
            if decision.get("verdict") == "unrelated" and decision.get("url") in candidates:
                candidates[decision["url"]].update(read_status="not_relevant", reason="Assessed as unrelated to this question.")
        for step in state.get("steps", []):
            execution = step.get("execution")
            executions.append({"id": step.get("id"), "branch_id": branch.id, "phase": step["phase"],
                "status": step["status"], "started_at": step.get("started_at"),
                "finished_at": step.get("finished_at"), "receipt": deepcopy(execution)})
            if step["phase"] == "search":
                recorded = execution.get("channels") if execution else None
                if recorded is None:
                    channels.append({"name": "Search attempt", "status": "unavailable" if step["status"] in {"unavailable", "interrupted"}
                        else "running" if step["status"] == "running" else "unknown", "count": None,
                        "step_id": step.get("id"), "reason": "No completed channel receipt."})
                else:
                    channels.extend({**deepcopy(lane), "step_id": step.get("id")} for lane in recorded)
                    skipped_channels.extend(deepcopy(execution.get("skipped_channels", [])))
            if step["phase"] == "read" and step.get("source_url"):
                item = candidates.setdefault(step["source_url"], {"title": step["source_url"], "url": step["source_url"]})
                item.update(read_status="not_checked" if step.get("skipped") else {
                    "completed": "captured", "unavailable": "failed", "interrupted": "interrupted", "running": "reading"
                }.get(step["status"], "unknown"), last_attempt_at=step.get("started_at"),
                    reason="Excluded by current source policy." if step.get("skipped") else None,
                    source_id=step.get("source_id"))
                if step["status"] == "completed" and step.get("source_id"):
                    item["last_success_at"] = step.get("finished_at")
    steps = [step for branch in branches for step in branch.checkpoint.get("steps", [])]
    captured = []
    for source in sources:
        extraction = [step for step in steps if step["phase"] == "extract" and step.get("source_id") == source.id]
        latest = extraction[-1] if extraction else None
        reused = bool(source.snapshot.get("retained_origin"))
        unchanged = bool(source.snapshot.get("unchanged_from") or source.snapshot.get("duplicate_of") or source.snapshot.get("capture_state") == "unchanged")
        state = ("reused" if reused else "unchanged" if unchanged else "captured")
        retained_analysis = reused and source.snapshot.get("analysis_completed") is True
        analysis = ({"completed": "analysed", "unavailable": "failed", "interrupted": "interrupted", "running": "analysing"}
            .get(latest["status"], "unknown") if latest else "retained_analysis" if retained_analysis else "not_needed" if unchanged else "not_started")
        captured.append({**source_ref(source), "read_status": state, "analysis_status": analysis,
            "extraction_methods": source.snapshot.get("extraction_methods", []),
            "extraction_warnings": source.snapshot.get("warnings", []),
            "text_truncated": bool(source.snapshot.get("text_truncated")),
            "fresh_source_check": not reused and source.kind == "public_source",
            "analysed_at": latest.get("finished_at") if latest else source.snapshot.get("analysis_completed_at") if retained_analysis else None})
        if source.url in candidates:
            candidates[source.url].update(source_id=source.id, read_status=state, analysis_status=analysis)
    from .product_research_mission import project as mission_projection

    # The mission reader owns the source/hash/quote fences for final gaps.
    from .product_research_mission import reading_projection

    mission = reading_projection(session, run) if reading else mission_projection(session, run)
    unresolved = unresolved_questions(run, answer=(mission or {}).get("answer"))
    omitted = sum(branch.checkpoint.get("candidate_counts", {}).get("outside_candidate_budget", 0) for branch in branches)
    failures = sum(e["status"] in {"unavailable", "interrupted"} for e in executions)
    partial_channels = sum(c["status"] not in {"complete", "empty"} for c in channels)
    pending_sources = sum(c.get("read_status") in {"not_checked", "failed", "interrupted", "unknown", "reading"} for c in candidates.values())
    core = run.research_state.get("core") or {}
    memory = core.get("recall") or {}
    scope = "in_progress" if run.status in {"queued", "running"} else "partial" if (
        failures or partial_channels or pending_sources or unresolved or omitted or run.status != "completed") else "bounded_checks_completed"
    return {"contract": CONTRACT, "investigation_id": run.id, "recorded": bool(core),
        "status": scope, "exhaustive": False, "updated_at": iso(run.updated_at),
        "summary": {"captured_sources": len(captured), "reused_sources": sum(s["read_status"] == "reused" for s in captured),
            "failed_steps": failures, "unavailable_channels": partial_channels,
            "unchecked_sources": pending_sources, "open_questions": len(unresolved), "omitted_candidates": omitted},
        "search_order": core.get("search_order"), "pack_id": core.get("pack_id"), "pack_version": core.get("pack_version"),
        "saved_evidence": {k: memory.get(k) for k in ("eligible_sources", "examined_sources", "selected_sources", "truncated", "method", "retrieval")},
        "channels": channels, "skipped_channels": skipped_channels, "sources": captured, "candidates": list(candidates.values()),
        "open_questions": unresolved, "stops": list(run.research_state.get("stops", [])),
        **({} if reading else {"executions": executions}),
        "limitations": ["Coverage describes this bounded research episode, not the whole internet.",
            "Retained captures keep their original date; reuse is not a fresh source check.",
            "Empty search results and inaccessible sources do not establish absence."]}
