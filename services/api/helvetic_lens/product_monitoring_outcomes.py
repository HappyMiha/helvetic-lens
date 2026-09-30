"""Current, bounded reading of a scheduled check; no inference or copied evidence."""
from sqlalchemy import select

from .product_claim_evolution import evidence_payload
from .product_claim_evolution import payload as change_payload
from .product_claim_evolution import query as change_query
from .product_investigation_models import ClaimChange, DossierClaim, Investigation, InvestigationSource
from .product_public_research import sources_visible

CONTRACT = "monitoring-outcome/v1"
SUPPORTED = {"SUPPORTED", "CONTESTED"}
PHASES = {"search": "Search", "read": "Source reading", "extract": "Evidence analysis", "compare": "Comparison with earlier findings"}


def quotation_current(session, evidence):
    if not evidence or evidence["relation"] != "SUPPORTS" or not evidence["quote"].strip():
        return False
    source = session.get(InvestigationSource, evidence["source"]["id"])
    return bool(source and any(
        p.get("passage") == evidence["locator"] and evidence["quote"] in p.get("text", "")
        for p in source.snapshot.get("excerpts", [])))


def findings(session, run):
    # The full record retains every finding. This is a small, source-backed preview.
    candidates = session.scalars(select(DossierClaim).where(DossierClaim.investigation_id == run.id,
        DossierClaim.status.in_(SUPPORTED)).order_by(DossierClaim.created_at.desc(), DossierClaim.id).limit(24))
    result = []
    for claim in candidates:
        evidence = evidence_payload(session, claim)
        if quotation_current(session, evidence):
            result.append({"id": claim.id, "investigation_id": run.id, "statement": claim.statement,
                "status": claim.status, "revision": claim.revision, "evidence": evidence})
        if len(result) == 3:
            break
    return result


def comparisons(session, run):
    candidates = session.scalars(change_query(run.dossier_id).where(
        ClaimChange.investigation_id == run.id, ClaimChange.status == "active")
        .order_by(ClaimChange.created_at.desc(), ClaimChange.id).limit(24))
    result = []
    for change in candidates:
        previous_run = session.get(Investigation, change.previous_investigation_id)
        if not previous_run or previous_run.question != run.question:
            continue
        value = change_payload(session, change)
        previous, current = value["previous"], value["current"]
        if (previous["revision"] != change.previous_revision or previous["status"] != change.previous_status
                or previous["status"] not in SUPPORTED or current["status"] not in SUPPORTED
                or not quotation_current(session, previous["evidence"])
                or not quotation_current(session, current["evidence"])):
            continue
        result.append(value)
        if len(result) == 3:
            break
    return result


def project(session, run, trigger, branches):
    result = {"contract": CONTRACT, "state": run.status, "finding_state": "pending",
        "limitations": [], "findings": [], "comparisons": [],
        "scope": "This saved question and the sources captured in this check. Coverage is not exhaustive."}
    if run.status in {"queued", "running", "paused", "cancelled"}:
        return result
    if (run.question != trigger.question or run.publication_id
            or not session.scalar(select(Investigation.id).where(Investigation.id == run.id, sources_visible()))):
        result.update(state="unavailable", finding_state="unavailable")
        result["limitations"] = ["The evidence for this check is no longer available in its original scope."]
        return result

    phases = {step.get("phase") for branch in branches for step in branch.checkpoint.get("steps", [])
        if step.get("status") != "completed"}
    result["limitations"] = [label + " was not completed." for phase, label in PHASES.items() if phase in phases]
    incomplete = bool(phases or any(b.status != "completed" for b in branches))
    result["findings"] = findings(session, run)
    result["comparisons"] = comparisons(session, run)
    recurring = [b.checkpoint for b in branches if b.checkpoint.get("recurring_web")]
    if result["comparisons"]:
        found = "changes"
    elif result["findings"]:
        found = "findings"
    elif recurring and all(s.get("empty_search") for s in recurring):
        found = "no_matches"
    elif (recurring and sum(s.get("unchanged", 0) for s in recurring)
            and not sum(s.get("analysed", 0) for s in recurring)):
        found = "unchanged"
    else:
        found = "no_findings"
    result["finding_state"] = found
    result["state"] = "failed" if run.status == "failed" else "partial" if incomplete else "completed"
    if incomplete and not result["limitations"]:
        result["limitations"] = ["Part of this check could not be completed. Open the research record for its status."]
    return result
