"""Versioned, application-owned contracts for the shared research runtime.

Registration describes an implemented capability, never grants source access or
loads executable code supplied by a model, source, user or domain configuration.
"""
from dataclasses import asdict, dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    provider: str
    input_schema: str
    output_schema: str
    version: str = "1.0.0"
    deterministic: bool = False
    latency_class: str = "interactive"
    cost_class: str = "metered"

    def descriptor(self):
        return {**asdict(self), "domain": "GENERAL", "enabled": True,
            "requires_llm": self.provider in {"decision", "synthesis"},
            "supported_providers": {"decision": ["laya", "jev"],
                "synthesis": ["configured_workspace_model"]}.get(self.provider, [self.provider])}


SKILLS = MappingProxyType({s.id: s for s in (
    Skill("recall", "Read saved evidence", "local_retrieval", "dossier-question/v1", "evidence-pack/v1", version="1.1.0", cost_class="local"),
    Skill("plan", "Choose useful research directions", "synthesis", "research-context/v1", "research-plan/v1"),
    Skill("search", "Find source candidates", "source_search", "public-query/v1", "source-candidates/v1", cost_class="provider_dependent"),
    Skill("gate", "Assess candidate relevance", "decision", "candidate-question/v1", "relevance-decision/v1"),
    Skill("gate_review", "Resolve uncertain relevance", "synthesis", "candidate-question/v1", "candidate-assessment/v1"),
    Skill("read", "Capture a source", "source_reader", "source-reference/v1", "captured-passages/v1", deterministic=True, cost_class="local"),
    Skill("extract", "Extract cited findings", "synthesis", "captured-passages/v1", "evidence-ledger/v1"),
    Skill("compare", "Compare earlier findings", "synthesis", "claim-comparison/v1", "claim-changes/v1"),
    Skill("reflect", "Identify remaining questions", "synthesis", "evidence-pack/v1", "research-reflection/v1"),
    Skill("orient", "Explain the emerging picture", "synthesis", "evidence-pack/v1", "early-orientation/v1"),
    Skill("brief", "Answer with evidence and gaps", "synthesis", "evidence-pack/v1", "research-briefing/v1"),
    Skill("reformulate", "Recover an unproductive search", "synthesis", "search-outcome/v1", "revised-query/v1"),
)})


@dataclass(frozen=True)
class SourceAdapter:
    id: str
    label: str
    kind: str
    capabilities: tuple[str, ...]
    version: str = "1.0.0"

    def descriptor(self):
        return {**asdict(self), "access": "current_permissions_and_runtime_configuration",
            "coverage": "Registration does not establish availability, completeness or authority."}


SOURCES = MappingProxyType({s.id: s for s in (
    SourceAdapter("saved_evidence", "Saved dossier evidence", "local", ("search", "capture", "version", "review")),
    SourceAdapter("connected_pages", "Connected source pages", "native", ("capture", "version", "health")),
    SourceAdapter("native_feeds", "Configured source feeds", "native", ("discovery", "version", "health")),
    SourceAdapter("uploaded_files", "Contributed files", "local", ("capture",)),
    SourceAdapter("crossref", "Crossref publication metadata", "catalogue", ("discovery",)),
    SourceAdapter("fedlex", "Fedlex legislation titles", "catalogue", ("discovery",)),
    SourceAdapter("europepmc", "Europe PMC literature", "catalogue", ("discovery",)),
    SourceAdapter("clinicaltrials", "ClinicalTrials.gov trial registry", "catalogue", ("discovery",)),
    SourceAdapter("fda_labels", "openFDA drug labels", "catalogue", ("discovery",)),
    SourceAdapter("ema_news", "EMA current news feed", "catalogue", ("discovery",)),
    SourceAdapter("finma_news", "FINMA current news feed", "catalogue", ("discovery",)),
    SourceAdapter("federal_court", "Federal Supreme Court latest publication day", "catalogue", ("discovery",)),
    SourceAdapter("public_web", "Configured web search", "web", ("discovery",)),
    SourceAdapter("public_url", "Submitted public source", "web", ("capture",)),
)})

REVIEW_POLICIES = MappingProxyType({domain: {
    "id": domain.lower() + "-evidence-review/v1", "version": "1.0.0",
    "requires_review": ["conflicting_evidence", "evidence_changed", "incomplete_evidence", "unreviewed_interpretation"],
    "acceptance": "A current explicit human acceptance bound to the exact evidence is required for accepted status.",
    "domain": domain,
} for domain in ("GENERAL", "LEGAL", "PHARMA")})


def review_requirement(review, policy):
    reasons = []
    if review.get("has_conflicting_evidence"):
        reasons.append("conflicting_evidence")
    if review.get("stale"):
        reasons.append("evidence_changed")
    if not review.get("reviewable") or not review.get("complete"):
        reasons.append("incomplete_evidence")
    accepted = (review.get("human_status") == "ACCEPTED" and not review.get("stale")
        and review.get("reviewable") and review.get("complete"))
    if not accepted and not reasons:
        reasons.append("unreviewed_interpretation")
    return {"policy_id": policy["id"], "required": not accepted, "reasons": reasons,
        "accepted_for_use": accepted, "machine_support_is_human_acceptance": False}


def validate_pack(pack):
    if (not pack.skill_ids or any(key not in SKILLS for key in pack.skill_ids)
            or any(key not in SOURCES for key in pack.source_ids)
            or pack.domain not in REVIEW_POLICIES):
        raise ValueError("Domain pack references an unregistered research capability")
    return pack
