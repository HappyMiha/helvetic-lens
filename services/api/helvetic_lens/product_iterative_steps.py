"""Additional phases executed by the existing investigation worker lease."""
import re
from copy import deepcopy

from . import (
    decision_search,
    decision_sources,
    research_gateway,
    research_knowledge,
    research_recall,
    search_channels,
)
from . import product_branch_assessment as branch_assessment
from . import product_direction_assessment as direction_assessment
from . import product_early_clarification as clarification
from . import product_evidence_applicability as applicability
from . import product_exploration as exploration
from . import product_exploration_followups as followups
from . import product_exploration_progress as progress
from . import product_exploration_scope as research_scope
from . import product_informed_research as informed
from . import product_iterative_research as research
from . import product_observed_queries as queries
from . import product_query_recovery as query_recovery
from . import product_question_renewal as renewal
from . import product_read_relevance as read_relevance
from . import product_research_memory as memory
from . import product_research_pacing as pacing
from . import product_source_recovery as recovery
from .product_investigation_models import InvestigationBranch, InvestigationSource
from .product_investigations import event, rows
from .product_research_gate import evaluate


def prepare(session, run, branch, state, work):
    work["research"] = True
    work["query"] = query_recovery.query(branch, state)
    selected = followups.context(session, run) if branch.phase != "reformulate" else None
    if selected and selected["status"] == "ready":
        work["selected_public_check"] = selected
    if branch.phase in {"extract", "reflect", "orient", "brief"}:
        work["capture_progress"] = progress.context(session, run)
        work["capture_dependencies"] = progress.dependencies(session, run)
    work["decision_order"] = run.research_state.get("decision_order", "jev_first")
    work["question"] = run.question
    work["limits"] = run.research_state["limits"]
    if branch.phase == "recall":
        research_recall.prepare(session, run, state, work)
    elif branch.phase == "plan":
        work["input"] = {"question": run.question, "branch_slots": min(6, max(2, work["limits"]["branches"] // 2))}
        direction = clarification.context(session, run)
        if direction and direction["status"] == "ready":
            work["input"]["selected_direction"] = direction
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
    elif branch.phase == "reformulate":
        query_recovery.prepare(session, run, branch, state, work)
    elif branch.phase in {"orient", "brief"}:
        work["input"] = exploration.prepare(session, run, early=branch.phase == "orient")
        if branch.phase == "orient":
            work["early_clarification"] = clarification.enabled(run)
            work["timeout_seconds"] = 20
            work["skip"] = len(work["input"]["sources"]) < 2
    elif branch.phase in {"gate", "gate_review"}:
        work["item"] = state["candidates"][state.get("gate_index", 0)]
        work["skip"] = recovery.unavailable(session, run, branch, state, work["item"])
        work["input"] = {"question": run.question, "branch": work["query"],
            "title": work["item"]["title"], "snippet": work["item"].get("summary", "")}
    elif branch.phase == "reflect":
        work["input"] = research.prepare_reflection(session, run, branch)


async def execute(service, work, seconds):
    if work["phase"] == "recall":
        return await research_recall.execute(service, work)
    phase = work["phase"]
    if phase == "search":
        urls = [v["url"] for v in search_channels.explicit_sources(work["question"])]
        result = await decision_search.federated_retrieve(search_channels.request_settings(service.settings, work.get("skipped_paid_search")), work["query"], "web", "balanced", work["product"],
            **({"public_sources": urls} if urls else {}))
        search_channels.note_skipped_paid(result, work.get("skipped_paid_search"))
        return {"items": result.pop("items"), "retrieval": result,
            "coverage": "Federated candidate retrieval only. Each candidate requires a separate relevance gate before reading."}
    if phase == "gate":
        return await evaluate(service.settings, work["question"], work["query"], work["item"], work["decision_order"])
    if phase == "read":
        return await decision_sources.safe_inspect(service.settings, work["query"], work["item"], "auto",
            rank_passages=False, excerpt_limit=8)
    schema, system = {
        "reformulate": (query_recovery.QueryReformulation, query_recovery.SYSTEM),
        "plan": (research.ResearchPlan, research.PLAN_SYSTEM),
        "gate_review": (research.CandidateAssessment, research.ASSESS_SYSTEM),
        "extract": (research.ResearchExtraction, research.EXTRACT_SYSTEM),
        "reflect": (research.Reflection, research.REFLECT_SYSTEM),
        "brief": (exploration.Briefing, exploration.SYSTEM),
        "orient": (exploration.EarlyOrientation, exploration.EARLY_SYSTEM),
    }[phase]
    if phase == "orient" and work.get("early_clarification"):
        schema, system = exploration.ClarifyingOrientation, system + exploration.CLARIFICATION_SYSTEM
    if phase == "reflect" and work["input"].get("branch_assessment_question"):
        schema, system = branch_assessment.AssessedReflection, system + branch_assessment.SYSTEM
    if phase == "extract" and work.get("read_relevance"):
        schema, system = read_relevance.ReadExtraction, system + read_relevance.SYSTEM
    if phase == "brief" and work["input"].get("assessment_question"):
        schema, system = exploration.AssessedBriefing, system + exploration.ASSESSMENT_SYSTEM
    if phase == "brief" and work["input"].get("question_renewal_targets"):
        schema = renewal.RenewalAssessedBriefing if work["input"].get("assessment_question") else renewal.RenewalBriefing
        system += renewal.SYSTEM
    if phase == "brief" and work["input"].get("direction_assessment_target"):
        schema = direction_assessment.RenewedDirectionBriefing if work["input"].get("question_renewal_targets") else direction_assessment.DirectionBriefing
        system += direction_assessment.SYSTEM
        if "next_check_candidates" in work["input"]:
            schema = direction_assessment.RenewedSuggestedDirectionBriefing if work["input"].get("question_renewal_targets") else direction_assessment.SuggestedDirectionBriefing
            system += direction_assessment.NEXT_CHECK_SYSTEM
    if phase == "brief" and work["input"].get("research_scope"):
        system += research_scope.SYSTEM
        if work["input"]["research_scope"].get("observed_queries", {}).get("status") == "ready":
            system += queries.SYSTEM
    if phase in {"orient", "reflect", "brief"} and work["input"].get("read_context"):
        system += informed.SYSTEM
    if work["input"].get("evidence_applicability"):
        system += applicability.SYSTEM
        if phase == "extract" and work.get("applicability"):
            schema = applicability.ScopedExtraction
    if work["input"].get("research_memory"):
        system += memory.SYSTEM
    if work.get("selected_public_check"):
        system += followups.CONTEXT_SYSTEM
    if work.get("capture_progress"):
        system += progress.SYSTEM
    if phase == "plan" and work.get("exploratory"):
        system += exploration.PLAN
    if phase == "plan" and work["input"].get("selected_direction"):
        system += clarification.CONTEXT_SYSTEM
    if work["input"].get("saved_knowledge"):
        system += research_knowledge.SYSTEM
    raw = await research_gateway.complete(service, work, system, schema, seconds)
    if not isinstance(raw, str) or len(raw) > 30000:
        raise ValueError("Unbounded research response")
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    if phase == "extract" and work.get("applicability"):
        return renewal.parse_recoverable(schema, raw, {"applicability_checks": "_applicability_unavailable"})
    if phase == "brief":
        optional = {}
        if work["input"].get("direction_assessment_target"):
            optional["direction_assessment"] = "_direction_unavailable"
        if "next_check_candidates" in work["input"]:
            optional["next_check_choice"] = "_next_check_unavailable"
        if work["input"].get("question_renewal_targets") and work["input"].get("question_renewal_recovery") == renewal.RECOVERY_CONTRACT:
            optional["question_renewals"] = "_renewal_unavailable"
        if optional:
            return renewal.parse_recoverable(schema, raw, optional)
    return schema.model_validate_json(raw)


def settle(branch, state):
    read_relevance.settle(branch, state)
    recovery.settle(branch, state)
    if pacing.settle(branch, state):
        return
    if branch.phase == "gate" and (state.get("gate_index", 0) >= len(state.get("candidates", []))
            or len(state.get("items", [])) >= recovery.selection_limit(state)):
        state.setdefault("candidate_counts", {})["not_evaluated_within_source_budget"] = max(0, len(state.get("candidates", [])) - state.get("gate_index", 0))
        branch.phase = "read"
        state["empty_search"] = not state.get("items")
    if branch.phase == "extract" and state.get("extract_index", 0) >= len(state.get("source_ids", [])):
        if state.get("analysed", 0) and not state.get("saved") and not state.get("reflection_done"):
            branch.phase = "reflect"
            branch.status = "running"


def failed(branch, state, *, interrupted=False):
    if branch.phase == "read":
        recovery.failed_read(state)
    if branch.phase == "recall":
        # A failed/interrupted local preparation never repeats an external model
        # request. Continue planning without memory; cached batches are retained.
        branch.phase = "plan"
        state["recall_unavailable"] = True
        if state.get("recall_only"):
            branch.status = "completed"
    elif branch.phase in {"plan", "reflect", "brief", "orient", "reformulate"}:
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
    if phase == "recall":
        research_recall.apply(session, run, branch, state, work, result)
    elif phase == "plan":
        research.apply_plan(session, run, result)
        branch.status = "completed"
        state["planning_done"] = True
    elif phase == "reformulate":
        query_recovery.apply(session, run, branch, state, result)
    elif phase == "brief":
        exploration.apply(session, run, work["input"], result)
        branch.status = "completed"
    elif phase == "orient":
        exploration.apply_orientation(session, run, work["input"], result)
        branch.status = "completed"
    elif phase == "search":
        seen = {s.url for s in rows(session, InvestigationSource, run)
            if not (state.get("refresh_retained_sources") and s.snapshot.get("retained_origin"))}
        for other in rows(session, InvestigationBranch, run):
            seen.update(other.checkpoint.get("attempted_urls", []))
        from .product_investigation_worker import excluded
        from .product_models import ProductDossier

        blocked = excluded(session, session.get(ProductDossier, run.dossier_id))
        recover = recovery.enabled(run, branch, state)
        candidates = []
        for item in result["items"]:
            if item["url"] not in seen | blocked:
                candidates.append(item)
                if recover:
                    seen.add(item["url"])
        if recover:
            state["source_recovery"] = {"contract": recovery.CONTRACT, "failed_reads": 0}
        limit = work["limits"]["candidates_per_branch"]
        state.update(candidates=candidates[:limit], gate_index=0, items=[], source_limit=work["limits"]["sources_per_branch"],
            candidate_counts={"retrieved": len(result["items"]), "duplicate_or_excluded": len(result["items"]) - len(candidates),
                "outside_candidate_budget": max(0, len(candidates) - limit)},
            coverage={"retrieval": result["retrieval"], "scope": result["coverage"]})
        branch.phase = "gate"
        if result["retrieval"].get("status") == "unavailable":
            branch.status = "failed"
            state["error"] = "All discovery channels were unavailable. No absence of evidence can be inferred."
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
