"""Additional phases executed by the existing investigation worker lease."""
import json
import re
from copy import deepcopy

from . import decision_search, decision_sources
from . import product_exploration as exploration
from . import product_exploration_followups as followups
from . import product_exploration_progress as progress
from . import product_iterative_research as research
from .analysis import InferenceBudget
from .product_investigation_models import InvestigationBranch, InvestigationSource
from .product_investigations import event, rows
from .product_research_gate import evaluate


def prepare(session, run, branch, state, work):
    work["research"] = True
    selected = followups.context(session, run)
    if selected and selected["status"] == "ready":
        work["selected_public_check"] = selected
    if branch.phase in {"extract", "reflect", "orient", "brief"}:
        work["capture_progress"] = progress.context(session, run)
        work["capture_dependencies"] = progress.dependencies(session, run)
    work["decision_order"] = run.research_state.get("decision_order", "jev_first")
    work["question"] = run.question
    work["limits"] = run.research_state["limits"]
    if branch.phase == "plan":
        work["input"] = {"question": run.question, "branch_slots": min(6, max(2, work["limits"]["branches"] // 2))}
        if exploration.enabled(run):
            work["exploratory"] = True
            previous = run.research_state["exploration"].get("previous")
            if previous:
                from .product_investigation_models import Investigation

                prior = session.get(Investigation, previous["investigation_id"])
                if prior and prior.dossier_id == run.dossier_id:
                    current = exploration.projection(session, prior)
                    if current and current["status"] == "ready":
                        work["input"]["previous_public_briefing"] = current["briefing"]
                        work["input"]["previous_public_queries"] = [b.query for b in rows(session, InvestigationBranch, prior)
                            if b.checkpoint.get("question_id")]
    elif branch.phase in {"orient", "brief"}:
        work["input"] = exploration.prepare(session, run, early=branch.phase == "orient")
        if branch.phase == "orient":
            work["timeout_seconds"] = 20
            work["skip"] = len(work["input"]["sources"]) < 2
    elif branch.phase in {"gate", "gate_review"}:
        work["item"] = state["candidates"][state.get("gate_index", 0)]
        work["input"] = {"question": run.question, "branch": branch.query,
            "title": work["item"]["title"], "snippet": work["item"].get("summary", "")}
    elif branch.phase == "reflect":
        work["input"] = research.prepare_reflection(session, run, branch)


async def execute(service, work, seconds):
    phase = work["phase"]
    if phase == "search":
        result = await decision_search.federated_retrieve(service.settings, work["query"], "web", "balanced", work["product"])
        return {"items": result.pop("items"), "retrieval": result,
            "coverage": "Federated candidate retrieval only. Each candidate requires a separate relevance gate before reading."}
    if phase == "gate":
        return await evaluate(service.settings, work["question"], work["query"], work["item"], work["decision_order"])
    if phase == "read":
        return await decision_sources.safe_inspect(service.settings, work["query"], work["item"], "auto",
            rank_passages=False, excerpt_limit=8)
    schema, system = {
        "plan": (research.ResearchPlan, research.PLAN_SYSTEM),
        "gate_review": (research.CandidateAssessment, research.ASSESS_SYSTEM),
        "extract": (research.ResearchExtraction, research.EXTRACT_SYSTEM),
        "reflect": (research.Reflection, research.REFLECT_SYSTEM),
        "brief": (exploration.Briefing, exploration.SYSTEM),
        "orient": (exploration.EarlyOrientation, exploration.EARLY_SYSTEM),
    }[phase]
    if work.get("selected_public_check"):
        system += followups.CONTEXT_SYSTEM
    if work.get("capture_progress"):
        system += progress.SYSTEM
    if phase == "plan" and work.get("exploratory"):
        system += exploration.PLAN
    work["model_route"] = {"provider": service.settings.apertus_provider, "model": service.settings.apertus_model,
        "basis": "Workspace configuration used for this request; provider response does not expose model identity here."}
    raw = await service.model_client.complete(system, json.dumps(work["input"], ensure_ascii=False),
        response_schema=schema.model_json_schema(), budget=InferenceBudget(max_requests=1, max_seconds=seconds))
    if not isinstance(raw, str) or len(raw) > 30000:
        raise ValueError("Unbounded research response")
    return schema.model_validate_json(re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip()))


def settle(branch, state):
    if branch.phase == "gate" and (state.get("gate_index", 0) >= len(state.get("candidates", []))
            or len(state.get("items", [])) >= state.get("source_limit", 2)):
        state.setdefault("candidate_counts", {})["not_evaluated_within_source_budget"] = max(0, len(state.get("candidates", [])) - state.get("gate_index", 0))
        branch.phase = "read"
        state["empty_search"] = not state.get("items")
    if branch.phase == "extract" and state.get("extract_index", 0) >= len(state.get("source_ids", [])):
        if state.get("analysed", 0) and not state.get("saved") and not state.get("reflection_done"):
            branch.phase = "reflect"
            branch.status = "running"


def failed(branch, state, *, interrupted=False):
    if branch.phase in {"plan", "reflect", "brief", "orient"}:
        branch.status = "failed"
    if branch.phase in {"gate", "gate_review"}:
        item = state.get("candidates", [])[state.get("gate_index", 0)]
        state.setdefault("decisions", []).append({"id": item["id"], "url": item["url"],
            "title": item["title"], "verdict": "unavailable", "basis": "Interrupted request was not repeated." if interrupted else "Relevance evaluation unavailable; candidate not read."})
        state["gate_index"] = state.get("gate_index", 0) + 1
        branch.phase = "gate"


def apply(session, run, branch, state, work, result):
    phase = work["phase"]
    if work.get("model_route"):
        state.setdefault("model_routes", []).append({"step_id": work["token"], "phase": phase, **work["model_route"]})
    if phase == "plan":
        research.apply_plan(session, run, result)
        branch.status = "completed"
        state["planning_done"] = True
    elif phase == "brief":
        exploration.apply(session, run, work["input"], result)
        branch.status = "completed"
    elif phase == "orient":
        exploration.apply_orientation(session, run, work["input"], result)
        branch.status = "completed"
    elif phase == "search":
        seen = {s.url for s in rows(session, InvestigationSource, run)}
        for other in rows(session, InvestigationBranch, run):
            seen.update(other.checkpoint.get("attempted_urls", []))
        from .product_investigation_worker import excluded
        from .product_models import ProductDossier

        blocked = excluded(session, session.get(ProductDossier, run.dossier_id))
        candidates = [v for v in result["items"] if v["url"] not in seen | blocked]
        limit = work["limits"]["candidates_per_branch"]
        state.update(candidates=candidates[:limit], gate_index=0, items=[], source_limit=work["limits"]["sources_per_branch"],
            candidate_counts={"retrieved": len(result["items"]), "duplicate_or_excluded": len(result["items"]) - len(candidates),
                "outside_candidate_budget": max(0, len(candidates) - limit)},
            coverage={"retrieval": result["retrieval"], "scope": result["coverage"]})
        branch.phase = "gate"
        event(session, run, "search_completed", branch_id=branch.id, **state["candidate_counts"])
    elif phase in {"gate", "gate_review"}:
        item = work["item"]
        decision = result if phase == "gate" else {**result.model_dump(), "engine": "workspace_model",
            "model_route": work.get("model_route"), "basis": "Escalated uncertain title/snippet; not source evidence."}
        trace = {"id": item["id"], "url": item["url"], "title": item["title"], **decision}
        state.setdefault("decisions", []).append(trace)
        if phase == "gate" and decision["verdict"] == "uncertain":
            branch.phase = "gate_review"
            event(session, run, "candidate_uncertain", branch_id=branch.id, candidate_id=item["id"])
        else:
            if decision["verdict"] == "relevant":
                state.setdefault("items", []).append(item)
            state["gate_index"] = state.get("gate_index", 0) + 1
            branch.phase = "gate"
            event(session, run, {"relevant": "candidate_accepted", "unrelated": "candidate_rejected",
                "uncertain": "candidate_uncertain", "unavailable": "candidate_unavailable"}[decision["verdict"]],
                branch_id=branch.id, candidate_id=item["id"], verdict=decision["verdict"],
                engine=decision.get("engine"), phase=phase)
    elif phase == "reflect":
        research.apply_reflection(session, run, branch, work["input"], result)
        state.update(reflection_done=True, outcome=result.outcome)
        branch.status = "failed" if state.get("failed_extract_indices") else "completed"
    branch.checkpoint = deepcopy(state)
