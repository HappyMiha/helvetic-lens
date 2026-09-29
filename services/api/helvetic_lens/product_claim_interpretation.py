"""Editor classification over the existing evidence-pinned human review ledger."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .config import DomainError

KINDS = {
    "UNKNOWN": "Not classified",
    "SOURCE_STATEMENT": "Source statement",
    "USER_ASSERTION": "User assertion",
    "AI_INTERPRETATION": "AI interpretation",
}
COMMON = (("UNKNOWN", "UNCLASSIFIED", "Not classified"),
          ("USER_ASSERTION", "USER_STATEMENT", "User statement"),
          ("AI_INTERPRETATION", "AI_ANALYSIS", "AI analysis"))
LEGAL_TYPES = COMMON + (
    ("SOURCE_STATEMENT", "STATUTORY_RULE", "Statutory rule"),
    ("SOURCE_STATEMENT", "CASE_HOLDING", "Court holding"),
    ("SOURCE_STATEMENT", "FACT", "Fact asserted by a source"),
    ("USER_ASSERTION", "FACT", "Fact asserted by a user"),
    ("USER_ASSERTION", "PARTY_ARGUMENT", "Party argument"),
    ("AI_INTERPRETATION", "INTERPRETATION", "Interpretation of sources"),
    ("SOURCE_STATEMENT", "EXCEPTION", "Exception stated by a source"),
    ("SOURCE_STATEMENT", "PROCEDURAL_REQUIREMENT", "Procedural requirement"),
    ("SOURCE_STATEMENT", "JURISDICTION_RULE", "Jurisdiction rule"),
)
PHARMA_TYPES = COMMON + (
    ("SOURCE_STATEMENT", "REGULATORY_STATUS", "Regulatory status reported by a source"),
    ("SOURCE_STATEMENT", "MARKET_ACCESS_STATUS", "Market access status reported by a source"),
    ("SOURCE_STATEMENT", "SAFETY_SIGNAL", "Reported safety signal"),
    ("SOURCE_STATEMENT", "CLINICAL_RESULT", "Reported clinical result"),
    ("SOURCE_STATEMENT", "LABEL_CHANGE", "Reported label change"),
    ("SOURCE_STATEMENT", "REIMBURSEMENT_CHANGE", "Reported reimbursement change"),
    ("SOURCE_STATEMENT", "SUPPLY_EVENT", "Reported supply event"),
    ("SOURCE_STATEMENT", "COMPETITOR_EVENT", "Reported competitor event"),
    ("AI_INTERPRETATION", "EVIDENCE_INTERPRETATION", "Interpretation of evidence"),
)


class Interpretation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    schema_version: Literal[1]
    domain_pack_version: str = Field(min_length=1, max_length=30)
    kind: Literal["UNKNOWN", "SOURCE_STATEMENT", "USER_ASSERTION", "AI_INTERPRETATION"]
    claim_type: str = Field(pattern=r"^[A-Z_]{2,60}$")


def options(pack):
    return {"schema_version": 1, "domain_pack": pack.id, "domain_pack_version": pack.version,
        "types": [{"kind": kind, "kind_label": KINDS[kind], "claim_type": code, "label": label}
                  for kind, code, label in pack.claim_types]}


def resolve(pack, data):
    if data.domain_pack_version != pack.version:
        raise DomainError("Claim type options changed. Reload the findings before reviewing.", 409, "claim_type_changed")
    chosen = next((row for row in options(pack)["types"]
        if row["kind"] == data.kind and row["claim_type"] == data.claim_type), None)
    if chosen is None:
        raise DomainError("This claim type is not registered for this dossier's domain.", 422, "claim_type_invalid")
    return {"schema_version": 1, "domain_pack": pack.id, "domain_pack_version": pack.version,
        **chosen, "authority": "UNASSESSED"}


def recorded(review, visible):
    """Omit untyped legacy metadata to preserve existing dependency fingerprints."""
    value = review.basis.get("interpretation") if review and visible else None
    return {"interpretation": value} if isinstance(value, dict) else {}
