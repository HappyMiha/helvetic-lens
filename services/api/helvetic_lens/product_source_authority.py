"""Source-specific editor assessments in the existing version-pinned review ledger."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .config import DomainError

COMMON = (
    ("UNASSESSED", "Not assessed"),
    ("SECONDARY_COMMENTARY", "Secondary commentary"),
    ("USER_DOCUMENT", "User document"),
    ("USER_STATEMENT", "User statement"),
    ("AI_INTERPRETATION", "AI interpretation"),
)
LEGAL_ROLES = COMMON + (
    ("PRIMARY_BINDING", "Primary binding material"),
    ("PRIMARY_NON_BINDING", "Primary non-binding material"),
    ("CASE_LAW", "Case law"),
    ("OFFICIAL_GUIDANCE", "Official guidance"),
    ("PARLIAMENTARY_MATERIAL", "Parliamentary material"),
)
PHARMA_ROLES = COMMON + (
    ("REGULATORY_PUBLICATION", "Regulatory publication"),
    ("REIMBURSEMENT_PUBLICATION", "Reimbursement publication"),
    ("CLINICAL_PUBLICATION", "Clinical publication"),
    ("TRIAL_REGISTRY", "Trial registry record"),
    ("CLINICAL_GUIDANCE", "Clinical guidance"),
    ("COMPANY_COMMUNICATION", "Company communication"),
)
LIMIT = 12


class SourceAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source_id: UUID
    evidence_id: UUID
    category: str = Field(pattern=r"^[A-Z_]{2,60}$")
    reason: str = Field(min_length=5, max_length=500)


class SourceAssessments(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    schema_version: Literal[1]
    domain_pack_version: str = Field(min_length=1, max_length=30)
    items: list[SourceAssessment] = Field(max_length=LIMIT)


def options(pack):
    return {"schema_version": 1, "domain_pack": pack.id, "domain_pack_version": pack.version,
        "limit": LIMIT, "categories": [{"category": code, "label": label} for code, label in pack.source_roles]}


def resolve(pack, data, current):
    if data.domain_pack_version != pack.version:
        raise DomainError("Source role options changed. Reload the findings before reviewing.", 409, "source_roles_changed")
    categories = dict(pack.source_roles)
    citations = {value["id"]: value for value in current["evidence"]}
    for comparison in current["comparisons"]:
        citations.update({value["id"]: value for value in comparison["evidence"]})
    seen, items = set(), []
    for entry in data.items:
        source_id, evidence_id = str(entry.source_id), str(entry.evidence_id)
        value = citations.get(evidence_id)
        if (source_id in seen or entry.category not in categories or not value or not value["valid"]
                or value["source"]["id"] != source_id):
            raise DomainError("Choose a distinct captured source, its exact citation and a registered source role.",
                422, "source_assessment_invalid")
        seen.add(source_id)
        items.append({"source_id": source_id, "evidence_id": evidence_id, "category": entry.category,
            "label": categories[entry.category], "reason": entry.reason, "quote": value["quote"],
            "locator": value["locator"], "source": dict(value["source"])})
    return {"schema_version": 1, "domain_pack": pack.id, "domain_pack_version": pack.version,
        "method": "editor_assessment", "items": sorted(items, key=lambda item: item["source_id"])}


def recorded(review, visible, *, compact=False):
    """Omit legacy metadata; hide the whole review when an original source is hidden."""
    value = review.basis.get("source_assessments") if review and visible else None
    if not isinstance(value, dict):
        return {}
    if compact:
        value = {**value, "items": [{key: item[key] for key in ("source_id", "category", "label")}
            for item in value["items"]]}
    return {"source_assessments": value}
