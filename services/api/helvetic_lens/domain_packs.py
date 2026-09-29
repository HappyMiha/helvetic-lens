"""Application-owned domain policies over the existing shared dossier engine.

These are runtime definitions, not persisted templates or source approvals.
Generated proposals retain the definition revision that produced them.
"""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from sqlalchemy import select

from .config import DomainError
from .product_claim_interpretation import LEGAL_TYPES, PHARMA_TYPES
from .product_models import ProductDossier


@dataclass(frozen=True)
class DomainPack:
    id: str
    version: str
    domain: Literal["LEGAL", "PHARMA"]
    label: str
    focus: str
    topic_instructions: str
    topic_task: str
    context_schema_id: str
    claim_types: tuple[tuple[str, str, str], ...] = ()
    scientific_literature: bool = False

    def descriptor(self):
        from .dossier_templates import available

        return {"id": self.id, "version": self.version, "domain": self.domain,
                "label": self.label, "focus": self.focus, "context_schema_id": self.context_schema_id,
                "template_ids": [item.id for item in available(self.domain)],
                "claim_types": [{"kind": kind, "claim_type": code, "label": label} for kind, code, label in self.claim_types]}


LEGAL = DomainPack(
    id="LegalPack", version="1.3.0", domain="LEGAL", label="Legal monitoring",
    focus="Legal developments, proceedings and regulatory changes relevant to your question.",
    topic_instructions=(
        "Propose up to six distinct legal monitoring topics for the supplied context and feedback. "
        "These are editable search interests, not legal conclusions. "
        "Do not invent law citations, legal requirements, events or source coverage. "
    ),
    topic_task="legal_profile_topics", context_schema_id="legal-context/v1", claim_types=LEGAL_TYPES,
)
PHARMA = DomainPack(
    id="PharmaPack", version="1.3.0", domain="PHARMA", label="Pharmaceutical monitoring",
    focus="Medicines, safety, clinical evidence, regulation and market access relevant to your question.",
    topic_instructions=(
        "Propose up to six distinct pharmaceutical monitoring topics for the supplied context and feedback. "
        "Use medicine, active substance, indication, safety, clinical evidence, regulatory or market-access "
        "concepts only where relevant to the user's goal. These are editable search interests, "
        "not medical advice, treatment recommendations or established clinical or regulatory conclusions. "
        "Do not invent studies, efficacy or safety findings, approvals, reimbursement decisions, "
        "events or source coverage. Separate research signals from authoritative decisions. "
    ),
    topic_task="pharma_profile_topics", context_schema_id="pharma-context/v1", claim_types=PHARMA_TYPES, scientific_literature=True,
)
_PRODUCTS = MappingProxyType({"legal": LEGAL, "loyer": LEGAL, "pharma": PHARMA})


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
