"""B2 profile and explained deterministic matching; semantic promotion is separate."""

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CANTONS = frozenset("AG AI AR BE BL BS FR GE GL GR JU LU NE NW OW SG SH SO SZ TG TI UR VD VS ZG ZH".split())
Language = Literal["de", "fr", "it", "en"]
Cpv = Annotated[str, Field(pattern=r"^[0-9]{8}$")]
Money = Annotated[Decimal, Field(ge=0, le=Decimal("1000000000000"), max_digits=15, decimal_places=2)]


def tokens(value):
    return tuple(
        re.findall(r"\.[^\W\d_]\w*|[^\W_]+(?:[+#]+)?", unicodedata.normalize("NFKC", value).casefold())
    )


def phrase_in(phrase, text):
    phrase, text = tokens(phrase), tokens(text)
    return bool(phrase) and (" " + " ".join(phrase) + " ") in (" " + " ".join(text) + " ")


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Capability(Contract):
    name: str = Field(min_length=1, max_length=100)
    # Explicit user-provided phrase variants; do not invent cross-language matches.
    phrases: tuple[str, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def bounded_phrases(self):
        if not self.name.strip() or any(not tokens(p) or len(p) > 200 for p in self.phrases):
            raise ValueError("Use a named capability with bounded non-empty phrases")
        if len({tokens(p) for p in self.phrases}) != len(self.phrases):
            raise ValueError("Capability phrases must be distinct")
        return self


class TenderProfile(Contract):
    template_id: Literal["tender-watch"] = "tender-watch"
    template_version: Literal[1] = 1
    name: str = Field(min_length=1, max_length=100)
    company_name: str = Field(min_length=1, max_length=200)
    capabilities: tuple[Capability, ...] = Field(default=(), max_length=20)
    cpv_codes: tuple[Cpv, ...] = Field(default=(), max_length=40)
    cpv_include_descendants: bool = Field(default=True, strict=True)
    # These are contract locations, not the authority's postal address.
    contract_cantons: tuple[str, ...] = Field(default=(), max_length=26)
    offer_languages: tuple[Language, ...] = Field(default=(), max_length=4)
    authority_levels: tuple[Literal["federal", "cantonal", "municipal", "other"], ...] = Field(
        default=(), max_length=4
    )
    excluded_phrases: tuple[str, ...] = Field(default=(), max_length=30)
    excluded_cpv_codes: tuple[Cpv, ...] = Field(default=(), max_length=40)
    excluded_contract_types: tuple[Literal["service", "supply", "construction"], ...] = Field(
        default=(), max_length=3
    )
    minimum_contract_chf: Money | None = None
    maximum_contract_chf: Money | None = None
    available_reference_count: int | None = Field(default=None, strict=True, ge=0, le=10000)
    certificates: tuple[str, ...] | None = Field(default=None, max_length=50)
    # Stored preference, not a validated default or permission to enable an LLM.
    minimum_semantic_score: int | None = Field(default=None, strict=True, ge=0, le=100)

    @model_validator(mode="after")
    def consistent(self):
        if (
            not self.name.strip()
            or not self.company_name.strip()
            or not (self.capabilities or self.cpv_codes)
        ):
            raise ValueError("Name the monitor/company and select at least one capability or CPV code")
        if len({c.name.casefold() for c in self.capabilities}) != len(self.capabilities):
            raise ValueError("Capability names must be distinct")
        if not set(self.contract_cantons).issubset(CANTONS):
            raise ValueError("Select official canton codes for contract locations")
        for values in (
            self.cpv_codes,
            self.contract_cantons,
            self.offer_languages,
            self.authority_levels,
            self.excluded_cpv_codes,
            self.excluded_contract_types,
        ):
            if len(values) != len(set(values)):
                raise ValueError("Selections must be distinct")
        if (
            self.minimum_contract_chf is not None
            and self.maximum_contract_chf is not None
            and self.minimum_contract_chf > self.maximum_contract_chf
        ):
            raise ValueError("Minimum contract value exceeds maximum")
        for values in (self.excluded_phrases, self.certificates or ()):
            if any(not tokens(v) or len(v) > 200 for v in values) or len({tokens(v) for v in values}) != len(
                values
            ):
                raise ValueError("Use distinct bounded non-empty phrases or certificate identifiers")
        if set(self.cpv_codes) & set(self.excluded_cpv_codes):
            raise ValueError("A CPV code cannot be both an interest and an exclusion")
        return self

    def fingerprint(self):
        raw = json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return hashlib.sha256(raw.encode()).hexdigest()


class TextEvidence(Contract):
    locator: str = Field(min_length=1, max_length=300)
    language: Language
    text: str = Field(max_length=100000)


class CpvAncestry(Contract):
    code: Cpv
    ancestors: tuple[Cpv, ...] = Field(max_length=10)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def no_cycle(self):
        if self.code in self.ancestors or len(set(self.ancestors)) != len(self.ancestors):
            raise ValueError("CPV ancestry must be distinct and acyclic")
        return self


class TenderLotFacts(Contract):
    project_id: str = Field(min_length=1, max_length=36)
    lot_id: str | None = Field(default=None, min_length=1, max_length=36)
    publication_id: str = Field(min_length=1, max_length=36)
    evidence_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    phase: Literal["open", "advance_notice", "awarded", "cancelled", "revoked", "unknown"]
    text: tuple[TextEvidence, ...] = Field(max_length=200)
    cpv_codes: tuple[Cpv, ...] | None = Field(default=None, max_length=100)
    cpv_ancestry: tuple[CpvAncestry, ...] = Field(default=(), max_length=100)
    # Umbrella classification is context for reviewing a lot, never a lot match.
    project_cpv_codes: tuple[Cpv, ...] | None = Field(default=None, max_length=100)
    project_cpv_ancestry: tuple[CpvAncestry, ...] = Field(default=(), max_length=100)
    contract_type: Literal["service", "supply", "construction"] | None = None
    contract_canton: str | None = None
    contract_country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    authority_level: Literal["federal", "cantonal", "municipal", "other"] | None = None
    offer_languages: tuple[Language, ...] | None = Field(default=None, max_length=4)
    estimated_min_chf: Money | None = None
    estimated_max_chf: Money | None = None
    required_reference_count: int | None = Field(default=None, strict=True, ge=0, le=10000)
    references_locator: str | None = Field(default=None, min_length=1, max_length=300)
    required_certificates: tuple[str, ...] | None = Field(default=None, max_length=50)
    certificates_locator: str | None = Field(default=None, min_length=1, max_length=300)
    qualification_coverage: Literal["complete", "partial", "unknown"] = "unknown"
    offer_deadline: datetime | None = None

    @field_validator("offer_deadline")
    @classmethod
    def deadline_aware(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("A deadline needs an unambiguous source instant")
        return value

    @model_validator(mode="after")
    def source_consistency(self):
        if self.contract_canton is not None and self.contract_canton not in CANTONS:
            raise ValueError("Unknown canton")
        if self.contract_canton and self.contract_country not in {None, "CH"}:
            raise ValueError("Canton conflicts with contract country")
        if (
            self.estimated_min_chf is not None
            and self.estimated_max_chf is not None
            and self.estimated_min_chf > self.estimated_max_chf
        ):
            raise ValueError("Conflicting contract value range")
        if self.required_reference_count is not None and not self.references_locator:
            raise ValueError("A stated reference requirement needs exact source evidence")
        if self.required_certificates is not None and not self.certificates_locator:
            raise ValueError("Stated certificate requirements need exact source evidence")
        if self.offer_languages == ():
            raise ValueError("Use unknown rather than an empty allowed-language set")
        codes = [entry.code for entry in self.cpv_ancestry]
        if len(set(codes)) != len(codes) or not set(codes).issubset(self.cpv_codes or ()):
            raise ValueError("Ancestry must identify distinct codes in this lot")
        project_codes = [entry.code for entry in self.project_cpv_ancestry]
        if len(set(project_codes)) != len(project_codes) or not set(project_codes).issubset(
            self.project_cpv_codes or ()
        ):
            raise ValueError("Project ancestry must identify distinct project codes")
        if self.lot_id is None and (self.project_cpv_codes or self.project_cpv_ancestry):
            raise ValueError("Project context is separate only when assessing a lot")
        if self.required_certificates is not None and any(
            not tokens(value) or len(value) > 200 for value in self.required_certificates
        ):
            raise ValueError("Certificate identifiers must be bounded and non-empty")
        return self


def match_lot(profile: TenderProfile, facts: TenderLotFacts, *, now: datetime):
    """Discovery verdict for ONE lot; followed dossiers must keep receiving updates.

    Hard exclusions precede any future semantic assessment. Missing qualification
    data creates an unknown gap, not an assertion of noncompliance or eligibility.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Matching needs an aware clock")
    matched, excluded, unknown, gaps = [], [], [], []
    # Tokenize each source fragment once rather than once per profile phrase.
    texts = [(fragment, " " + " ".join(tokens(fragment.text)) + " ") for fragment in facts.text]

    def reason(code, **evidence):
        return {"code": code, **evidence}

    if facts.phase in {"awarded", "cancelled", "revoked"}:
        excluded.append(reason("discovery_phase_closed", value=facts.phase))
    elif facts.phase == "unknown":
        unknown.append(reason("publication_phase_unknown"))
    if facts.offer_deadline and facts.offer_deadline <= now:
        excluded.append(reason("offer_deadline_passed", value=facts.offer_deadline.isoformat()))
    for phrase in profile.excluded_phrases:
        normalized = " " + " ".join(tokens(phrase)) + " "
        for fragment, text in texts:
            if normalized in text:
                excluded.append(
                    reason(
                        "excluded_phrase", phrase=phrase, locator=fragment.locator, language=fragment.language
                    )
                )
                break
    source_codes = set(facts.cpv_codes or ())
    related = {code: {code} for code in source_codes}
    ancestry = {entry.code: entry for entry in facts.cpv_ancestry}
    if profile.cpv_include_descendants:
        for entry in facts.cpv_ancestry:
            related[entry.code].update(entry.ancestors)
    unresolved_hierarchy = source_codes - ancestry.keys() if profile.cpv_include_descendants else set()
    for code, parents in sorted(related.items()):
        for rule_code in sorted(parents & set(profile.excluded_cpv_codes)):
            excluded.append(
                reason(
                    "excluded_cpv",
                    value=code,
                    selected_code=rule_code,
                    taxonomy_sha256=ancestry[code].source_sha256 if code in ancestry else None,
                )
            )
    exclusion_unknown = bool(profile.excluded_cpv_codes and (facts.cpv_codes is None or unresolved_hierarchy))
    if exclusion_unknown:
        unknown.append(reason("cpv_exclusions_unverified"))
    if facts.contract_type in profile.excluded_contract_types:
        excluded.append(reason("excluded_contract_type", value=facts.contract_type))
    elif profile.excluded_contract_types and facts.contract_type is None:
        exclusion_unknown = True
        unknown.append(reason("contract_type_exclusions_unverified"))
    if profile.contract_cantons:
        if facts.contract_country and facts.contract_country != "CH":
            excluded.append(reason("contract_outside_switzerland", value=facts.contract_country))
        elif facts.contract_canton is None:
            unknown.append(reason("contract_location_unknown"))
        elif facts.contract_canton not in profile.contract_cantons:
            excluded.append(reason("contract_canton_excluded", value=facts.contract_canton))
    if profile.offer_languages:
        if facts.offer_languages is None:
            unknown.append(reason("offer_languages_unknown"))
        elif not set(profile.offer_languages) & set(facts.offer_languages):
            excluded.append(reason("offer_languages_excluded", value=list(facts.offer_languages)))
    if profile.authority_levels:
        if facts.authority_level is None:
            unknown.append(reason("authority_level_unknown"))
        elif facts.authority_level not in profile.authority_levels:
            excluded.append(reason("authority_level_excluded", value=facts.authority_level))
    if profile.minimum_contract_chf is not None:
        if facts.estimated_max_chf is not None and facts.estimated_max_chf < profile.minimum_contract_chf:
            excluded.append(reason("contract_value_below_minimum", value=str(facts.estimated_max_chf)))
        elif facts.estimated_min_chf is None or facts.estimated_min_chf < profile.minimum_contract_chf:
            unknown.append(reason("contract_minimum_not_established"))
    if profile.maximum_contract_chf is not None:
        if facts.estimated_min_chf is not None and facts.estimated_min_chf > profile.maximum_contract_chf:
            excluded.append(reason("contract_value_above_maximum", value=str(facts.estimated_min_chf)))
        elif facts.estimated_max_chf is None or facts.estimated_max_chf > profile.maximum_contract_chf:
            unknown.append(reason("contract_maximum_not_established"))
    for capability in profile.capabilities:
        phrases = [(phrase, " " + " ".join(tokens(phrase)) + " ") for phrase in capability.phrases]
        for fragment, text in texts:
            phrase = next((original for original, normalized in phrases if normalized in text), None)
            if phrase:
                matched.append(
                    reason(
                        "capability_phrase",
                        capability=capability.name,
                        phrase=phrase,
                        locator=fragment.locator,
                        language=fragment.language,
                    )
                )
                break
    cpv_matches = []
    for code, parents in sorted(related.items()):
        for rule_code in sorted(parents & set(profile.cpv_codes)):
            cpv_matches.append(
                reason(
                    "exact_cpv" if rule_code == code else "cpv_descendant",
                    value=code,
                    selected_code=rule_code,
                    taxonomy_sha256=ancestry[code].source_sha256 if code in ancestry else None,
                )
            )
    matched.extend(cpv_matches)
    project_context = []
    if facts.lot_id and facts.cpv_codes is None:
        project_ancestry = {entry.code: entry for entry in facts.project_cpv_ancestry}
        for code in facts.project_cpv_codes or ():
            parents = {code}
            if profile.cpv_include_descendants and code in project_ancestry:
                parents.update(project_ancestry[code].ancestors)
            for selected_code in sorted(parents & set(profile.cpv_codes)):
                project_context.append(
                    reason(
                        "project_cpv_context",
                        value=code,
                        selected_code=selected_code,
                        locator="/procurement",
                        lot_relevance="not_verified",
                        taxonomy_sha256=project_ancestry[code].source_sha256
                        if code in project_ancestry
                        else None,
                    )
                )
    if profile.cpv_codes and not cpv_matches and unresolved_hierarchy:
        unknown.append(reason("cpv_hierarchy_unknown"))
    if profile.cpv_codes and facts.cpv_codes is None:
        unknown.append(reason("cpv_unknown"))
    if facts.required_reference_count is not None:
        if profile.available_reference_count is None:
            unknown.append(reason("company_references_unknown", locator=facts.references_locator))
        elif profile.available_reference_count < facts.required_reference_count:
            gaps.append(
                reason(
                    "declared_reference_gap",
                    required=facts.required_reference_count,
                    declared=profile.available_reference_count,
                    locator=facts.references_locator,
                )
            )
    if facts.required_certificates:
        if profile.certificates is None:
            unknown.append(reason("company_certificates_unknown", locator=facts.certificates_locator))
        else:
            supplied = {tokens(c) for c in profile.certificates}
            missing = [c for c in facts.required_certificates if tokens(c) not in supplied]
            if missing:
                gaps.append(
                    reason("declared_certificate_gap", values=missing, locator=facts.certificates_locator)
                )
    if facts.qualification_coverage != "complete":
        unknown.append(reason("qualification_evidence_incomplete"))
    if excluded:
        verdict = "excluded"
    elif exclusion_unknown or facts.phase == "unknown":
        verdict = "unknown"
    elif matched:
        verdict = "needs_review" if unknown or gaps else "match"
    elif project_context:
        verdict = "needs_review"
    else:
        unresolved_interest = profile.cpv_codes and (facts.cpv_codes is None or unresolved_hierarchy)
        verdict = "unknown" if unresolved_interest or not facts.text and profile.capabilities else "no_match"
    return {
        "rule_version": "tender-deterministic-v2",
        "profile_sha256": profile.fingerprint(),
        "source_sha256": facts.evidence_sha256,
        "project_id": facts.project_id,
        "publication_id": facts.publication_id,
        "lot_id": facts.lot_id,
        "verdict": verdict,
        "matches": matched,
        "project_context": project_context,
        "exclusions": excluded,
        "unknowns": unknown,
        "qualification_gaps": gaps,
        "eligibility": "not_determined",
        "semantic_status": "disabled",
        "semantic_score": None,
    }
