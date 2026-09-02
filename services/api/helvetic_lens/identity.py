import re
import unicodedata
from urllib.parse import urlsplit

_ELI_WORK = re.compile(r"/eli/(?P<collection>cc|oc|fga)/(?P<year>[^/]+)/(?P<id>[^/]+)", re.I)
_LEGAL_TITLE_WORDS = re.compile(
    r"\b(?:gesetz|verordnung|bundesbeschluss|loi|ordonnance|decreto|legge|ordinanza|law|act|code)\b",
    re.I,
)
_GENERIC = {
    "am",
    "au",
    "aux",
    "avec",
    "bei",
    "da",
    "das",
    "de",
    "dei",
    "del",
    "della",
    "der",
    "des",
    "die",
    "du",
    "e",
    "en",
    "et",
    "für",
    "im",
    "in",
    "la",
    "le",
    "les",
    "mit",
    "of",
    "on",
    "per",
    "sur",
    "the",
    "über",
    "und",
    "vom",
    "von",
}


def _clean(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold()
    return re.sub(r"\s+", " ", value).strip()


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[^\W\d_]{3,}", _clean(value), re.UNICODE)
        if token not in _GENERIC
    }


def _eli_work(value: str | None) -> str | None:
    if not value:
        return None
    match = _ELI_WORK.search(urlsplit(value).path)
    if not match:
        return None
    return "/eli/{collection}/{year}/{id}".format(**match.groupdict()).casefold()


def _identity_title(title: str, passages: list[dict]) -> str:
    generic_filename = bool(
        re.search(r"\.(?:pdf|txt|html?)$", title or "", re.I)
        or re.search(r"\b(?:pasted|uploaded|document|version)\b", title or "", re.I)
    )
    if (
        len(_tokens(title)) >= 3
        and not generic_filename
        and not re.fullmatch(r"[\d.\s-]+", title or "")
    ):
        return title
    candidates = [str(item.get("text", "")) for item in passages[:20]]
    legal = [item for item in candidates if _LEGAL_TITLE_WORDS.search(item) and 3 <= len(_tokens(item)) <= 35]
    if legal:
        return max(legal, key=lambda item: min(len(item), 400))
    descriptive = [item for item in candidates if 3 <= len(_tokens(item)) <= 35]
    return max(descriptive, key=lambda item: min(len(item), 400), default=title)


def _title_match(reference: str, candidate: str) -> tuple[str, float]:
    reference_tokens, candidate_tokens = _tokens(reference), _tokens(candidate)
    if len(reference_tokens) < 2 or len(candidate_tokens) < 3:
        return "uncertain", 0.0
    overlap = len(reference_tokens & candidate_tokens) / min(
        len(reference_tokens), len(candidate_tokens)
    )
    return ("mismatch" if overlap < 0.12 else "match"), round(overlap, 3)


def assess_document_identity(
    *,
    law_name: str,
    law_url: str | None,
    title: str,
    source_url: str | None,
    passages: list[dict],
) -> dict:
    """Return a conservative identity check; uncertainty never becomes a false match."""

    law_work, source_work = _eli_work(law_url), _eli_work(source_url)
    candidate_title = _identity_title(title, passages)
    if law_work and source_work:
        status = "match" if law_work == source_work else "mismatch"
        reason = (
            "The ELI work identifier matches the tracked document."
            if status == "match"
            else "The ELI work identifier belongs to a different document."
        )
        return {
            "status": status,
            "reason": reason,
            "score": 1.0 if status == "match" else 0.0,
            "tracked_title": law_name,
            "detected_title": candidate_title,
            "tracked_identifier": law_work,
            "detected_identifier": source_work,
        }
    status, score = _title_match(law_name, candidate_title)
    reason = {
        "match": "The extracted title is consistent with the tracked document.",
        "mismatch": "The extracted title appears to describe a different legal document.",
        "uncertain": "The file does not expose enough stable identity metadata to verify it automatically.",
    }[status]
    return {
        "status": status,
        "reason": reason,
        "score": score,
        "tracked_title": law_name,
        "detected_title": candidate_title,
        "tracked_identifier": law_work,
        "detected_identifier": source_work,
    }


def assess_comparison_identity(law, old, new) -> dict:
    old_report = assess_document_identity(
        law_name=law.name,
        law_url=law.url,
        title=old.title,
        source_url=old.source_url,
        passages=old.passages,
    )
    new_report = assess_document_identity(
        law_name=law.name,
        law_url=law.url,
        title=new.title,
        source_url=new.source_url,
        passages=new.passages,
    )
    pair_status, pair_score = _title_match(
        _identity_title(old.title, old.passages),
        _identity_title(new.title, new.passages),
    )
    reports = (old_report, new_report)
    explicit_ids = [report["detected_identifier"] for report in reports if report["detected_identifier"]]
    tracked_id = old_report["tracked_identifier"] or new_report["tracked_identifier"]
    if any(report["status"] == "mismatch" for report in reports):
        status = "mismatch"
        reason = "At least one saved file appears to belong to another legal document."
    elif tracked_id and len(explicit_ids) == 2 and all(value == tracked_id for value in explicit_ids):
        # Official multilingual expressions may have completely different titles.
        status = "match"
        reason = "Both saved versions have the tracked document's ELI work identifier."
    elif len(set(explicit_ids)) > 1:
        status = "mismatch"
        reason = "The before and after files expose different ELI work identifiers."
    elif pair_status == "mismatch":
        status = "mismatch"
        reason = "The before and after files appear to be different legal documents."
    elif all(report["status"] == "match" for report in reports) or (
        "match" in {old_report["status"], new_report["status"]} and pair_status == "match"
    ):
        status = "match"
        reason = "The saved versions are consistent with the tracked document."
    else:
        status = "uncertain"
        reason = "Document identity could not be verified from the available metadata."
    return {
        "status": status,
        "reason": reason,
        "old": old_report,
        "new": new_report,
        "pair_score": pair_score,
    }
