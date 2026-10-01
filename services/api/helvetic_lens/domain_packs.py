"""Application-owned domain policies over the existing shared dossier engine.

These are runtime definitions, not persisted templates or source approvals.
Generated proposals retain the definition revision that produced them.
"""
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from sqlalchemy import select

from .config import DomainError
from .product_claim_interpretation import LEGAL_TYPES, PHARMA_TYPES
from .product_models import ProductDossier
from .product_source_authority import LEGAL_ROLES, PHARMA_ROLES
from .research_contracts import REVIEW_POLICIES, SKILLS, SOURCES, validate_pack


@dataclass(frozen=True)
class DomainPack:
    id: str
    version: str
    domain: Literal["GENERAL", "LEGAL", "PHARMA"]
    label: str
    focus: str
    topic_instructions: str
    topic_task: str
    context_schema_id: str
    claim_types: tuple[tuple[str, str, str], ...] = ()
    source_roles: tuple[tuple[str, str], ...] = ()
    scientific_literature: bool = False
    research_policy_id: str = ""
    skill_ids: tuple[str, ...] = tuple(SKILLS)
    source_ids: tuple[str, ...] = ("saved_evidence", "connected_pages", "native_feeds", "uploaded_files", "crossref", "public_web", "public_url")

    @property
    def review_policy(self):
        return deepcopy(REVIEW_POLICIES[self.domain])

    @property
    def discovery_sources(self):
        return tuple(key for key in self.source_ids if SOURCES[key].kind == "catalogue")

    def descriptor(self):
        from .dossier_templates import available

        return {"id": self.id, "version": self.version, "domain": self.domain,
                "label": self.label, "focus": self.focus, "context_schema_id": self.context_schema_id,
                "template_ids": [item.id for item in available(self.domain)],
                "research_policy_id": self.research_policy_id,
                "contract": "domain-pack/v2", "skills": [SKILLS[key].descriptor() for key in self.skill_ids],
                "sources": [SOURCES[key].descriptor() for key in self.source_ids], "review_policy": self.review_policy,
                "source_roles": [{"category": code, "label": label} for code, label in self.source_roles],
                "claim_types": [{"kind": kind, "claim_type": code, "label": label} for kind, code, label in self.claim_types]}


LEGAL = DomainPack(
    id="LegalPack", version="2.0.0", domain="LEGAL", label="Legal monitoring",
    focus="Legal developments, proceedings and regulatory changes relevant to your question.",
    topic_instructions=(
        "Propose up to six distinct legal monitoring topics for the supplied context and feedback. "
        "These are editable search interests, not legal conclusions. "
        "Do not invent law citations, legal requirements, events or source coverage. "
    ),
    topic_task="legal_profile_topics", context_schema_id="legal-context/v1", claim_types=LEGAL_TYPES, source_roles=LEGAL_ROLES,
    research_policy_id="legal-research/v1",
    source_ids=("saved_evidence", "connected_pages", "native_feeds", "uploaded_files", "crossref", "fedlex", "public_web", "public_url"),
)
PHARMA = DomainPack(
    id="PharmaPack", version="2.0.0", domain="PHARMA", label="Pharmaceutical monitoring",
    focus="Medicines, safety, clinical evidence, regulation and market access relevant to your question.",
    topic_instructions=(
        "Propose up to six distinct pharmaceutical monitoring topics for the supplied context and feedback. "
        "Use medicine, active substance, indication, safety, clinical evidence, regulatory or market-access "
        "concepts only where relevant to the user's goal. These are editable search interests, "
        "not medical advice, treatment recommendations or established clinical or regulatory conclusions. "
        "Do not invent studies, efficacy or safety findings, approvals, reimbursement decisions, "
        "events or source coverage. Separate research signals from authoritative decisions. "
    ),
    topic_task="pharma_profile_topics", context_schema_id="pharma-context/v1", claim_types=PHARMA_TYPES, source_roles=PHARMA_ROLES, scientific_literature=True,
    research_policy_id="pharma-research/v1",
    source_ids=("saved_evidence", "connected_pages", "native_feeds", "uploaded_files", "crossref", "europepmc", "public_web", "public_url"),
)
GENERAL = DomainPack(id="GeneralPack", version="2.0.0", domain="GENERAL", label="Research",
    focus="Evidence relevant to the user's question, with explicit uncertainty and source scope.",
    topic_instructions="Identify useful, distinct research directions without inventing evidence or source coverage.",
    topic_task="general_research_topics", context_schema_id="general-context/v1", research_policy_id="general-research/v1")
REGISTRY = MappingProxyType({pack.id: validate_pack(pack) for pack in (GENERAL, LEGAL, PHARMA)})
_PRODUCTS = MappingProxyType({"legal": LEGAL, "loyer": LEGAL, "pharma": PHARMA})

# Retain supported versions when introducing a later policy. These application
# definitions contain no dossier data, source approvals or inferred user intent.
RESEARCH_POLICIES = {
    "general-research/v1": {"id": "general-research/v1", "domain": "GENERAL", "dimensions": {
        "subject": "The people, entities or problem actually addressed by the source.",
        "period": "The evidence date and period, separately from capture time.",
        "provenance": "Original record, independent evidence, commentary or assertion; do not infer truth from repetition."}},
    "legal-research/v1": {"id": "legal-research/v1", "domain": "LEGAL", "dimensions": {
        "jurisdiction": "Territory and legal level; a different canton or country may offer analogy, not the applicable rule.",
        "period": "The requested date versus the quoted version/effective period; capture date is not an effective date.",
        "authority": "Primary rule, holding, guidance or commentary; a publisher name alone does not prove binding authority.",
        "procedure": "Allegation, procedural order, settlement or adjudicated finding; preserve the distinction.",
        "subject": "The persons, conduct and exceptions actually addressed by the quoted rule or decision."}},
    "pharma-research/v1": {"id": "pharma-research/v1", "domain": "PHARMA", "dimensions": {
        "medicine": "Product, active substance and formulation; a drug class or similar name does not establish identity.",
        "indication": "The population and use studied or authorised; do not assume every use is off-label or infer illegality.",
        "market": "Territory of the decision or access conditions; another market is context, not local authorization.",
        "period": "The requested period versus the dated evidence or decision; capture date does not prove current status.",
        "evidence_stage": "Study design, observed endpoint and population; a clinical result is not an approval or established benefit.",
        "decision_type": "Authorization, reimbursement, safety communication or commercial statement; do not substitute one for another."}},
}


def research_policy_context(product):
    return {"primary_policy": for_product(product).research_policy_id,
        "policies": [deepcopy(RESEARCH_POLICIES[p.research_policy_id]) for p in (LEGAL, PHARMA)]}


def for_product(product: str) -> DomainPack:
    try:
        return _PRODUCTS[product]
    except KeyError:
        raise DomainError("This monitoring direction is not supported.", 422, "domain_pack_unknown") from None


def for_profile(session, profile) -> DomainPack:
    """Resolve only after the caller has authorized access to the profile."""
    product = session.scalar(select(ProductDossier.product).where(
        ProductDossier.profile_id == profile.id))
    # Existing standalone profiles are the native Legal workflow.
    return LEGAL if product is None else for_product(product)
