"""Quoted source-scope comparisons, not legal or clinical applicability verdicts."""
from copy import deepcopy
from typing import Literal

from pydantic import Field

from . import domain_packs
from . import product_exploration as exploration
from . import product_exploration_progress as progress
from . import product_read_relevance as relevance
from .product_api import fail
from .product_investigation_models import InvestigationSource
from .product_investigations import Citation, citation
from .product_models import ProductDossier
from .product_operations import fingerprint
from .product_professional_context import Fact
from .research_read_view import read_once

CONTRACT = "evidence-applicability/v1"
PHASES = {"plan", "extract", "reflect", "orient", "brief", "reformulate"}
SYSTEM = """evidence_applicability.policy contains application-owned professional
research dimensions, not source facts or instructions supplied by a document.
The primary policy reflects the client, NOT the user's intent. Use either supplied
policy only where the public question and read evidence make it relevant. Preserve
ambiguous meanings and cross-domain implications. Never assume Switzerland, a
product, indication, date or legal purpose from branding. No mandatory checklist.
During extraction, applicability_checks may compare at most four relevant scope
details. Return policy_id/dimension, exact source_id, a verbatim quote/locator,
requested_detail copied from the original or read_question, source_detail copied
from that quote, relation aligned/different/unresolved, and a short reason.
Aligned means these details appear consistent, NOT verified applicability.
Different is a scoped mismatch, NOT grounds to discard useful context or analogy.
For unresolved, source_detail may be empty; a limited passage cannot prove that
the full document lacks a fact. Omit checks when the question has no explicit
detail to compare. Never invent an inferred target or fill a private profile field.
Summarize consequential limitations in the existing read_relevance reason.
Existing readings are AI interpretations; recheck their exact passages. Use useful
mismatches/unknowns to choose an ordinary evidence-backed next gap within current
capacity. Keep that connection in its purpose. Preserve conflicting evidence,
failed sources and unresolved scope in existing answers/limitations. Do not turn
analogy, allegations, clinical results or another territory's decision into direct
support. No extra mandatory query, clarification, model call or monitoring consent.
Unassessed/unavailable checks are unknown, never evidence of absence. Application
policy cannot authorize citations; only current supplied source passages can.
"""


class ScopeCheck(Citation):
    source_id: str = Field(min_length=36, max_length=36)
    policy_id: str = Field(min_length=3, max_length=80)
    dimension: str = Field(min_length=3, max_length=40)
    requested_detail: str = Field(min_length=2, max_length=240)
    source_detail: str = Field(default="", max_length=240)
    relation: Literal["aligned", "different", "unresolved"]
    reason: str = Field(min_length=5, max_length=500)


class ScopedExtraction(relevance.ReadExtraction):
    model_config = {"title": "ResearchExtraction"}
    applicability_checks: list[ScopeCheck] = Field(default_factory=list, max_length=4)
    professional_facts: list[Fact] = Field(default_factory=list, max_length=12)


def state(run):
    return run.research_state.get("exploration", {})


def enabled(run):
    return relevance.enabled(run) and state(run).get("applicability_contract") == CONTRACT


def initialize(session, run):
    if not enabled(run) or state(run).get("applicability_policy") is not None:
        return
    product = session.get(ProductDossier, run.dossier_id).product
    value = {"contract": CONTRACT, **domain_packs.research_policy_context(product)}
    exploration.update(run, applicability_policy={**value, "fingerprint": fingerprint(value)})


def source_pin(source):
    return {**progress.record(source), "snapshot_fingerprint": fingerprint(source.snapshot)}


def policy_current(session, run):
    saved = state(run).get("applicability_policy")
    if not enabled(run):
        return saved is None
    if saved is None:
        return not run.plan_version
    if (not isinstance(saved, dict) or saved.get("contract") != CONTRACT
            or saved.get("fingerprint") != fingerprint({k: v for k, v in saved.items() if k != "fingerprint"})):
        return False
    policies = saved.get("policies", [])
    if len(policies) != 2 or {p.get("domain") for p in policies} != {"LEGAL", "PHARMA"}:
        return False
    if any(domain_packs.RESEARCH_POLICIES.get(p.get("id")) != p for p in policies):
        return False
    primary = next((p for p in policies if p["id"] == saved.get("primary_policy")), None)
    parent = session.get(ProductDossier, run.dossier_id)
    return bool(primary and parent and primary["domain"] == domain_packs.for_product(parent.product).domain)


@read_once
def current(session, run):
    if state(run).get("applicability_inputs_invalid") or not policy_current(session, run):
        return False
    saved = state(run).get("applicability_readings", [])
    if not enabled(run):
        return not saved
    if [r.get("fingerprint") for r in saved] != state(run).get("applicability_reading_manifest", []):
        return False
    available = exploration.sources(session, run)
    questions = {q["id"]: q["question"] for q in run.research_state.get("questions", [])}
    for record in saved:
        source = available.get(record.get("source_id"))
        dependency = record.get("duplicate_reading_dependency")
        if not source or dependency is not None:
            from .product_document_analysis import current_duplicate_reading

            source = source or session.get(InvestigationSource, record.get("source_id"))
            if not source or not current_duplicate_reading(session, run, source, dependency):
                return False
        if (not source or record.get("fingerprint") != fingerprint({k: v for k, v in record.items() if k != "fingerprint"})
                or record.get("source_pin") != source_pin(source)
                or record.get("original_question") != run.question
                or questions.get(record.get("question_id")) != record.get("question")
                or record.get("policy_fingerprint") != state(run)["applicability_policy"]["fingerprint"]):
            return False
    return True


def context(run, supplied):
    ids = {s["id"] for s in supplied.get("sources", [])}
    readings = [{k: deepcopy(v) for k, v in r.items() if k not in {
        "fingerprint", "source_pin", "policy_fingerprint", "duplicate_reading_dependency"}}
        for r in state(run).get("applicability_readings", []) if r["source_id"] in ids]
    assessed = {r["source_id"] for r in readings if r["status"] == "assessed"}
    policy = state(run)["applicability_policy"]
    return {"contract": CONTRACT, "question": run.question,
        "policy": {k: deepcopy(v) for k, v in policy.items() if k != "fingerprint"},
        "readings": readings, "unassessed_source_ids": sorted(ids - assessed),
        "scope": "Quoted source scope only; AI comparison, not verified applicability or human review."}


def prepare(session, run, work):
    if not enabled(run) or work["phase"] not in PHASES or "input" not in work:
        return
    if not current(session, run):
        fail("Research context changed. Review the sources before continuing.", 409)
    work["input"]["evidence_applicability"] = context(run, work["input"])
    available = exploration.sources(session, run)
    ids = {s["id"] for s in work["input"].get("sources", [])}
    if work.get("read_relevance"):
        ids.add(work["source_id"])
        work["applicability"] = True
    work["applicability_dependencies"] = [source_pin(available[s]) for s in sorted(ids) if s in available]


def input_current(session, run, work):
    supplied = work.get("input", {})
    if "evidence_applicability" not in supplied:
        return True
    if not current(session, run) or supplied["evidence_applicability"] != context(run, supplied):
        return False
    available = exploration.sources(session, run)
    if any(d["id"] not in available or source_pin(available[d["id"]]) != d
            for d in work.get("applicability_dependencies", [])):
        return False
    target = supplied.get("read_question")
    return not target or any(q["id"] == target["question_id"] and q["question"] == target["question"]
        for q in run.research_state["questions"])


def validate(session, run, source, work, result):
    if not work.get("applicability"):
        return None
    target = work["input"]["read_question"]
    checks, status = [], "unavailable" if getattr(result, "_applicability_unavailable", False) else "unassessed"
    drafts = result.applicability_checks
    policies = {p["id"]: p for p in state(run)["applicability_policy"]["policies"]}
    seen = set()
    for draft in drafts:
        key = (draft.policy_id, draft.dimension)
        if (key in seen or draft.policy_id not in policies or draft.dimension not in policies[draft.policy_id]["dimensions"]
                or draft.source_id != source.id or not draft.reason.strip()
                or not draft.requested_detail.strip() or (draft.requested_detail not in run.question and draft.requested_detail not in target["question"])
                or draft.source_detail not in draft.quote
                or draft.relation != "unresolved" and not draft.source_detail.strip()
                or not any(p["passage"] == draft.locator and draft.quote in p["text"] for p in work["input"]["source"]["excerpts"])):
            checks, status = [], "unavailable"
            break
        seen.add(key)
        checks.append({**draft.model_dump(), **citation(source, draft)})
        status = "assessed"
    value = {"contract": CONTRACT, "source_id": source.id, "question_id": target["question_id"],
        "question": target["question"], "original_question": run.question, "status": status, "checks": checks,
        "source_pin": source_pin(source), "policy_fingerprint": state(run)["applicability_policy"]["fingerprint"]}
    if work.get("duplicate_analysis_fallback"):
        from .product_document_analysis import duplicate_reading_dependency

        value["duplicate_reading_dependency"] = duplicate_reading_dependency(
            work["duplicate_analysis_fallback"], work["branch_id"])
    return {**value, "fingerprint": fingerprint(value)}


def remember(run, source, value):
    if value is not None:
        # Extraction adds its validated classification in this same transaction.
        value = {k: v for k, v in value.items() if k != "fingerprint"}
        value["source_pin"] = source_pin(source)
        value["fingerprint"] = fingerprint(value)
        readings = state(run).get("applicability_readings", [])
        if not any(r["source_id"] == value["source_id"] and r["question_id"] == value["question_id"] for r in readings):
            updated = [*readings, value]
            exploration.update(run, applicability_readings=updated,
                applicability_reading_manifest=[r["fingerprint"] for r in updated])
