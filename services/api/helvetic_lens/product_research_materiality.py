"""One explainable change policy for evidence readers and personal in-app updates."""
from datetime import UTC

from .db import utcnow

CONTRACT = "research-materiality/v1"


def project(outcome):
    changes = [c for c in outcome.get("comparisons", []) if c["kind"] in {"CONTRADICTS", "UPDATES"}
        and not c.get("source_relationship", {}).get("content_hash_match")
        and not c.get("source_relationship", {}).get("same_supporting_excerpt")]
    if changes:
        category = "material"
        reasons = [c["explanation"] for c in changes]
    elif outcome.get("state") in {"failed", "partial", "unavailable"}:
        category, reasons = "coverage_gap", outcome.get("limitations") or ["This check could not establish whether the evidence changed."]
    elif not outcome.get("repeated_evidence") and any(f.get("human_status") != "REJECTED" for f in outcome.get("findings", [])):
        category, reasons = "findings", ["New supported findings are available for review; their effect on the answer is not yet established."]
    else:
        category, reasons = "quiet", ["No consequential evidence change was established in this check."]
    return {"contract": CONTRACT, "category": category, "reasons": reasons,
        "claim_ids": [c["current"]["id"] for c in changes],
        "scope": "Importance to this saved question, not a verified legal or medical conclusion. Failed checks never mean no change."}


def delivery(mode, materiality, finished_at, *, now=None):
    now = now or utcnow()
    category = materiality.get("category", "findings")
    if mode == "silent" or category == "quiet":
        return "silent"
    # Digests release the previous UTC day's accumulated research at midnight.
    # This is native in-app delivery; it never grants external-email consent.
    if mode == "digest":
        return "digest" if finished_at.replace(tzinfo=UTC).date() < now.date() else "waiting_for_digest"
    return "immediate"
