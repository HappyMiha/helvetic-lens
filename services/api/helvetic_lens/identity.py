import hashlib
import json
import re
import unicodedata
from urllib.parse import urlsplit

IDENTITY_REVISION = "artifact-identity-v2"
_ELI_WORK = re.compile(r"/eli/(?P<collection>cc|oc|fga)/(?P<year>[^/]+)/(?P<id>[^/]+)", re.I)
_SR_RS = re.compile(r"\b(?:SR|RS)\s*([0-9]{1,4}(?:\.[0-9A-Za-z]+){1,4})\b", re.I)
_BARE_SR = re.compile(r"^\s*([0-9]{1,4}(?:\.[0-9A-Za-z]+){1,4})\s*$")
_LEGAL_TITLE_WORDS = re.compile(
    r"\b(?:gesetz|verordnung|bundesbeschluss|loi|ordonnance|decreto|legge|ordinanza|law|act|code)\b",
    re.I,
)
_LANG_PATH = re.compile(r"/(de|fr|it|rm|en)(?:/|$)", re.I)
_GENERIC = {
    "am", "au", "aux", "avec", "bei", "da", "das", "de", "dei", "del", "della",
    "der", "des", "die", "du", "e", "en", "et", "für", "im", "in", "la", "le",
    "les", "mit", "of", "on", "per", "sur", "the", "über", "und", "vom", "von",
}


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value or "").casefold()).strip()


def _tokens(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[^\W\d_]{3,}", _clean(value), re.UNICODE)
        if token not in _GENERIC
    }


def _eli_work(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.hostname not in {"fedlex.data.admin.ch", "fedlex.admin.ch", "www.fedlex.admin.ch"}:
        return None
    match = _ELI_WORK.search(parsed.path)
    if not match:
        return None
    return "/eli/{collection}/{year}/{id}".format(**match.groupdict()).casefold()


def _identity_title(title: str, passages: list[dict]) -> str:
    generic = bool(
        re.search(r"\.(?:pdf|txt|html?)$", title or "", re.I)
        or re.search(r"\b(?:pasted|uploaded|document|version)\b", title or "", re.I)
    )
    if len(_tokens(title)) >= 3 and not generic and not re.fullmatch(r"[\d.\s-]+", title or ""):
        return title[:500]
    candidates = [str(item.get("text", "")) for item in passages[:24]]
    legal = [item for item in candidates if _LEGAL_TITLE_WORDS.search(item) and 3 <= len(_tokens(item)) <= 35]
    descriptive = [item for item in candidates if 3 <= len(_tokens(item)) <= 35]
    return max(legal or descriptive, key=lambda item: min(len(item), 500), default=title)[:500]


def _title_score(reference: str, candidate: str) -> float:
    left, right = _tokens(reference), _tokens(candidate)
    if len(left) < 2 or len(right) < 3:
        return 0.0
    return round(len(left & right) / min(len(left), len(right)), 3)


def _sr_ids(title: str, passages: list[dict]) -> list[str]:
    values: list[str] = []
    for text in [title, *(str(item.get("text", "")) for item in passages[:20])]:
        values.extend(match.group(1).casefold() for match in _SR_RS.finditer(text))
        bare = _BARE_SR.fullmatch(text)
        if bare:
            values.append(bare.group(1).casefold())
    return list(dict.fromkeys(values))[:5]


def build_artifact_identity(
    *, title: str, source_url: str | None, passages: list[dict], extractor: str,
    content_type: str, filename: str, declared_date: str | None = None,
    metadata: dict | None = None,
) -> dict:
    metadata = metadata or {}
    detected_title = str(metadata.get("eli_title") or _identity_title(title, passages))[:500]
    official_eli = _eli_work(str(metadata.get("eli_work_uri") or "")) or _eli_work(source_url)
    sr_ids = _sr_ids(detected_title, passages)
    language = metadata.get("eli_language")
    if not language and source_url:
        match = _LANG_PATH.search(urlsplit(source_url).path)
        language = match.group(1).lower() if match else None
    canonical = official_eli or (f"sr:{sr_ids[0]}" if sr_ids else None)
    evidence = []
    if official_eli:
        evidence.append({"type": "official_identifier", "source": "Fedlex ELI metadata or URL", "value": official_eli})
    if sr_ids:
        evidence.append({"type": "official_identifier", "source": "Extracted SR/RS label", "value": sr_ids[0]})
    if detected_title:
        evidence.append({"type": "title", "source": "Connector metadata or extracted heading", "value": detected_title})
    payload = {
        "revision": IDENTITY_REVISION,
        "authority": "Swiss Confederation / Fedlex" if official_eli else (urlsplit(source_url).hostname if source_url else "User-provided artifact"),
        "canonical_work_id": canonical,
        "official_identifiers": ([{"scheme": "ELI", "value": official_eli}] if official_eli else []) + [{"scheme": "SR/RS", "value": value} for value in sr_ids],
        "document_kind": "legal_work" if _LEGAL_TITLE_WORDS.search(detected_title) else "document",
        "title": detected_title,
        "language": language or "unknown",
        "version_date": metadata.get("eli_version_date") or declared_date,
        "publication_date": metadata.get("publication_date"),
        "source_url": source_url,
        "extractor": extractor,
        "content_type": content_type,
        "filename": filename,
        "evidence": evidence,
    }
    payload["fingerprint"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return payload


def assess_document_identity(
    *, law_name: str, law_url: str | None, title: str, source_url: str | None,
    passages: list[dict], artifact_identity: dict | None = None, metadata: dict | None = None,
    extractor: str = "unknown", content_type: str = "unknown", filename: str = "document",
    declared_date: str | None = None,
) -> dict:
    artifact = artifact_identity or build_artifact_identity(
        title=title, source_url=source_url, passages=passages, extractor=extractor,
        content_type=content_type, filename=filename, declared_date=declared_date, metadata=metadata,
    )
    tracked_eli = _eli_work(law_url)
    detected_eli = next((item["value"] for item in artifact.get("official_identifiers", []) if item.get("scheme") == "ELI"), None)
    tracked_sr = next(iter(_sr_ids(law_name, [])), None)
    detected_sr = next((item["value"] for item in artifact.get("official_identifiers", []) if item.get("scheme") == "SR/RS"), None)
    score = _title_score(law_name, artifact.get("title", ""))
    if tracked_eli and detected_eli:
        status = "verified" if tracked_eli == detected_eli else "mismatch"
        reason = "The official Fedlex ELI work identifier matches the monitored document." if status == "verified" else "The official Fedlex ELI identifier belongs to a different legal work."
    elif tracked_sr and detected_sr:
        status = "verified" if tracked_sr == detected_sr else "mismatch"
        reason = "The official SR/RS identifier matches the monitored document." if status == "verified" else "The extracted SR/RS identifier belongs to a different legal work."
    elif tracked_eli and detected_sr and score < 0.12:
        status, reason = "mismatch", "The artifact exposes a different SR/RS work and its legal title conflicts with the monitored document."
    elif score >= 0.45:
        status, reason = "probable", "The extracted legal title is strongly consistent with the monitored document, but no matching official identifier was available."
    elif score >= 0.12:
        status, reason = "unknown", "The title is partly consistent, but stable official identity metadata is missing."
    elif detected_sr or _LEGAL_TITLE_WORDS.search(artifact.get("title", "")):
        status, reason = "mismatch", "The extracted legal title describes a different document."
    else:
        status, reason = "unknown", "The artifact does not expose enough stable identity metadata to verify it."
    return {
        "revision": IDENTITY_REVISION, "status": status, "reason": reason, "score": score,
        "tracked_title": law_name, "detected_title": artifact.get("title"),
        "tracked_identifier": tracked_eli or (f"sr:{tracked_sr}" if tracked_sr else None),
        "detected_identifier": artifact.get("canonical_work_id"), "artifact": artifact,
        "fingerprint": artifact.get("fingerprint"),
    }


def assess_comparison_identity(law, old, new) -> dict:
    def report(version):
        return assess_document_identity(
            law_name=law.name, law_url=law.url, title=version.title, source_url=version.source_url,
            passages=version.passages, artifact_identity=getattr(version, "identity_json", None),
            extractor=getattr(version, "extractor", "unknown"), content_type=getattr(version, "content_type", "unknown"),
            filename=getattr(version, "filename", "document"), declared_date=getattr(version, "declared_date", None),
        )

    old_report, new_report = report(old), report(new)
    old_id, new_id = old_report["detected_identifier"], new_report["detected_identifier"]
    pair_score = _title_score(old_report.get("detected_title", ""), new_report.get("detected_title", ""))
    if "mismatch" in {old_report["status"], new_report["status"]} or (old_id and new_id and old_id != new_id):
        status, reason = "mismatch", "At least one saved artifact belongs to another legal work."
    elif old_report["status"] == new_report["status"] == "verified":
        status, reason = "verified", "Both saved artifacts carry the monitored legal work's official identifier."
    elif "unknown" in {old_report["status"], new_report["status"]}:
        status, reason = "unknown", "One or both artifacts lack enough stable metadata for automatic assignment."
    else:
        status, reason = "probable", "The saved artifacts are consistently assigned by title or partial metadata."
    result = {"revision": IDENTITY_REVISION, "status": status, "reason": reason, "old": old_report, "new": new_report, "pair_score": pair_score}
    result["fingerprint"] = hashlib.sha256(json.dumps({
        "revision": IDENTITY_REVISION,
        "status": status,
        "tracked_name": _clean(law.name),
        "tracked_identifier": _eli_work(law.url) or _clean(law.url),
        "old": old_report["fingerprint"],
        "new": new_report["fingerprint"],
    }, sort_keys=True).encode()).hexdigest()
    return result
