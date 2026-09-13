"""Project permitted SIMAP evidence into separate lots without inventing facts."""

from bs4 import BeautifulSoup

from .simap_sources import parse_publication, source_id
from .tender_contracts import TenderLotFacts, TextEvidence

LANGUAGES = {"de", "fr", "it", "en"}


def translated(raw, locator):
    if raw is None:
        return []
    if not isinstance(raw, dict):
        raise ValueError("Invalid multilingual source field")
    fragments = []
    for language in sorted(LANGUAGES):
        value = raw.get(language)
        if value is None:
            continue
        if not isinstance(value, str) or len(value) > 100000:
            raise ValueError("Invalid or oversized source text")
        # Source originals stay untouched in the publication evidence. Only the
        # visible words in supported HTML enter deterministic discovery matching.
        soup = BeautifulSoup(value, "html.parser")
        for hidden in soup(["script", "style", "template"]):
            hidden.decompose()
        text = soup.get_text(" ", strip=True)
        if text:
            fragments.append(TextEvidence(locator=f"{locator}/{language}", language=language, text=text))
    return fragments


def codes(block):
    values = []
    primary = block.get("cpvCode")
    if primary:
        if not isinstance(primary, dict):
            raise ValueError("Invalid CPV field")
        values.append(primary.get("code"))
    additional = block.get("additionalCpvCodes") or []
    if not isinstance(additional, list):
        raise ValueError("Invalid additional CPV list")
    for item in additional:
        if not isinstance(item, dict):
            raise ValueError("Invalid CPV item")
        values.append(item.get("code"))
    if any(not isinstance(value, str) for value in values):
        raise ValueError("Invalid CPV identifier")
    return tuple(sorted(set(values))) if values else None


def facts_from_publication(record, *, now, cpv_ancestry=(), authority_levels=None):
    checked = parse_publication(
        record["original"],
        project_id=record["project_id"],
        publication_id=record["publication_id"],
        now=now,
    )
    if checked["evidence_sha256"] != record["evidence_sha256"]:
        raise ValueError("Publication evidence no longer matches its stored fingerprint")
    raw, base = checked["original"], checked["original"]["base"]
    info = raw.get("project-info") or {}
    if not isinstance(info, dict):
        raise ValueError("Invalid project information")
    phase = {
        "tender": "open",
        "competition": "open",
        "study_contract": "open",
        "advance_notice": "advance_notice",
        "request_for_information": "advance_notice",
        "award": "awarded",
        "direct_award": "awarded",
        "abandonment": "cancelled",
        "revocation": "revoked",
    }.get(raw["type"], "unknown")
    if info.get("processType") == "invitation" and phase == "open":
        phase = "unknown"  # A public record does not prove this company is invited.
    lot_mode = base.get("lotsType")
    if lot_mode not in {"with", "without"}:
        raise ValueError("Unknown lot scope")
    if raw.get("lot"):
        if lot_mode != "with" or not isinstance(raw["lot"], dict):
            raise ValueError("Specific lot conflicts with project scope")
        scoped = [(raw["lot"], "/lot", False)]
    elif lot_mode == "with":
        lots = raw.get("lots")
        if not isinstance(lots, list) or not 1 <= len(lots) <= 1000:
            raise ValueError("A publication with lots needs its explicit lot records")
        scoped = [(lot, f"/lots/{index}", True) for index, lot in enumerate(lots)]
    else:
        if raw.get("lots"):
            raise ValueError("Unexpected lots in a project without lots")
        procurement = raw.get("procurement") or {}
        scoped = [(procurement, "/procurement", True)]
    languages = info.get("offerLanguages")
    if languages is not None:
        if not isinstance(languages, list) or not set(languages).issubset(LANGUAGES):
            raise ValueError("Unknown source offer language")
        languages = tuple(sorted(set(languages))) or None
    ancestry = {entry.code: entry for entry in cpv_ancestry}
    if len(ancestry) != len(cpv_ancestry):
        raise ValueError("Duplicate taxonomy evidence")
    result, seen = [], set()
    project_cpv = codes(raw.get("procurement") or {}) if lot_mode == "with" and not raw.get("lot") else None
    for block, locator, has_procurement in scoped:
        if not isinstance(block, dict):
            raise ValueError("Invalid scoped publication data")
        lot_id = source_id(block.get("id")) if lot_mode == "with" else None
        if lot_id in seen:
            raise ValueError("Duplicate lot in publication")
        seen.add(lot_id)
        if lot_mode == "with":
            text = translated(block.get("title"), locator + "/title")
        else:
            text = translated(info.get("title"), "/project-info/title")
        text.extend(translated(block.get("orderDescription"), locator + "/orderDescription"))
        # Never borrow umbrella title/other-lot descriptions for a particular lot.
        # Award/revocation lot references contain identity, not full procurement.
        cpv = codes(block) if has_procurement else None
        address = block.get("orderAddress")
        country, canton = None, None
        if has_procurement and block.get("orderAddressOnlyDescription") == "no" and address is not None:
            if not isinstance(address, dict):
                raise ValueError("Invalid contract address")
            country, canton = address.get("countryId"), address.get("cantonId")
        contract_type = block.get("projectSubType") if lot_mode == "with" else info.get("orderType")
        if contract_type not in {"service", "supply", "construction"}:
            contract_type = None
        result.append(
            TenderLotFacts(
                project_id=checked["project_id"],
                publication_id=checked["publication_id"],
                lot_id=lot_id,
                evidence_sha256=checked["evidence_sha256"],
                phase=phase,
                text=tuple(text),
                cpv_codes=cpv,
                cpv_ancestry=tuple(ancestry[code] for code in cpv or () if code in ancestry),
                project_cpv_codes=project_cpv,
                project_cpv_ancestry=tuple(ancestry[code] for code in project_cpv or () if code in ancestry),
                contract_country=country,
                contract_canton=canton,
                contract_type=contract_type,
                authority_level=(authority_levels or {}).get(base.get("procOfficeId")),
                offer_languages=languages,
                offer_deadline=checked["offer_deadline"]["utc"],
                # No machine-verified requirement or estimate extraction is available
                # yet. Do not mistake an award amount for an estimated opportunity.
                qualification_coverage="unknown",
            )
        )
    return tuple(result)
