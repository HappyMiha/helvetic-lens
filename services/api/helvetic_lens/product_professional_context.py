"""Typed, literally cited source context; no inferred legal/clinical applicability."""
from typing import Literal

from pydantic import Field

from .config import DomainError
from .product_api import fail
from .product_investigations import Citation, Extraction, citation

CONTRACT = "professional-source-context/v1"
LEGAL = {"jurisdiction", "authority", "version", "effective_from", "effective_to", "decision_status", "procedure"}
PHARMA = {"medicine", "indication", "market", "regulatory_status", "study_phase", "publication_date"}
SYSTEM = """Extract professional_facts only where the supplied source explicitly
states a relevant fact. Each value must occur literally inside its exact quote at
the supplied locator/source_id. Use domain legal or pharma with its typed dimension.
Legal dimensions concern jurisdiction, authority, version, effective dates,
decision_status and procedure. Pharma dimensions concern medicine, indication,
market, regulatory_status, study_phase and publication_date. Preserve the source's
words: proposed, pending, revoked, approved, alleged, off-label and superseded are
different statuses. A date of capture is not an effective date. A trial is not an
authorization. A source's description is not a verified applicability verdict.
Extract relevant cross-domain facts when present; omit unsupported fields instead
of filling them from prior knowledge, branding or a user's ambiguous words.
For topics outside law, regulation and medicine, return professional_facts: [].
An ordinary date is not automatically legal effectiveness; a measurement is not
a study phase or legal procedure. Do not fill these dimensions to satisfy a form.
"""


class Fact(Citation):
    source_id: str = Field(min_length=36, max_length=36)
    domain: Literal["legal", "pharma"]
    dimension: Literal["jurisdiction", "authority", "version", "effective_from", "effective_to",
        "decision_status", "procedure", "medicine", "indication", "market", "regulatory_status",
        "study_phase", "publication_date"]
    value: str = Field(min_length=2, max_length=240)


class ProfessionalExtraction(Extraction):
    professional_facts: list[Fact] = Field(default_factory=list, max_length=12)


def validate(source, supplied, result, *, omit_invalid=False):
    facts = []
    for draft in getattr(result, "professional_facts", []):
        try:
            if (draft.source_id != source.id or draft.dimension not in (LEGAL if draft.domain == "legal" else PHARMA)
                or not draft.value.strip() or draft.value not in draft.quote or not any(
                    p["passage"] == draft.locator and draft.quote in p["text"] for p in supplied["source"]["excerpts"])):
                fail("Professional context needs the source's exact words.", 422, "invalid_evidence")
            facts.append({**draft.model_dump(), **citation(source, draft)})
        except DomainError:
            if not omit_invalid:
                raise
            result._optional_omissions = list(dict.fromkeys([*getattr(result, "_optional_omissions", []), "professional_facts"]))
    return facts


def current(source):
    facts = source.snapshot.get("professional_facts", [])
    return [f for f in facts if f.get("source_id") == source.id and f.get("sha256") == source.sha256
        and f.get("value", "") in f.get("quote", "") and any(
            p.get("passage") == f.get("locator") and f.get("quote") in p.get("text", "")
            for p in source.snapshot.get("excerpts", []))]


def project(sources):
    values = [fact for source in sources for fact in current(source)]
    return {"contract": CONTRACT, "facts": values,
        "unassessed_sources": sum(not current(source) for source in sources),
        "scope": "What the retained source explicitly says; applicability and current status still require review."}
