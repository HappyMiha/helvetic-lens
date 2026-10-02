"""A conservative structural boundary between original findings and references.

The original is never shortened. Only a confirmed bibliography's entry blocks
receive a use restriction; inline citations and uncertain/mixed prose stay intact.
"""
import re
import unicodedata
from collections import Counter
from copy import deepcopy

from .product_operations import fingerprint

POLICY = "reference-metadata/v1"
INSTRUCTIONS = """Passages labelled source_use=reference_metadata describe the citing
document's bibliography or reference metadata, not findings established by the
referenced work. They may support statements about what was cited, authors, titles,
dates or identifiers, and motivate reading an original. A title, citation or report
name does not establish the scientific or legal assertion embedded in that title.
The referenced original remains unread unless separately supplied. Do not turn
reference metadata into substantive findings, even if an earlier synopsis did so.
"""
_HEADING = re.compile(r"(?:references|bibliography|literature cited|références|bibliographie|literaturverzeichnis)", re.I)
_AUTHOR = re.compile(r"^(?:\[\d+\]\s*)?(?:[^\W\d_][\w’'‐–-]*(?:\s+[\w’'‐–-]+){0,3},?\s+(?:[A-Z]\.\s*)+|[A-Z]{2,}(?:\s+[A-Za-z]+){0,3}(?:\s*\([^)]{3,120}\))?,)")
_YEAR_END = re.compile(r"\b(?:18|19|20)\d{2}[a-z]?\.?\s*$")


def _normal(text):
    return unicodedata.normalize("NFC", " ".join(text.split()))


def _entry(text):
    text = _normal(text)
    # A heading AND consecutive complete entry records are required. A DOI,
    # date or legal citation in ordinary prose cannot establish this boundary.
    return bool(_AUTHOR.match(text) and _YEAR_END.search(text) and text.count(",") >= 3)


def _order(locator):
    return tuple((1, int(part)) if part.isdigit() else (0, part) for part in re.split(r"(\d+)", locator))


def _blocks(sources):
    blocks = {}
    for source in sources:
        for passage in source.get("excerpts", []):
            locator, text = passage.get("passage"), passage.get("text")
            if not isinstance(locator, str) or not isinstance(text, str):
                continue
            match = re.fullmatch(r"(.+)-char-(\d+)", locator)
            base, start = (match[1], int(match[2]) - 1) if match else (locator, 0)
            blocks.setdefault(base, []).append((start, text, passage))
    result = []
    for base in sorted(blocks, key=_order):
        text, valid = "", True
        for start, part, _ in sorted(blocks[base], key=lambda item: item[0]):
            if start > len(text) or text[start:min(len(text), start + len(part))] != part[:max(0, len(text) - start)]:
                valid = False
                break
            if start + len(part) > len(text):
                text += part[len(text) - start:]
        result.append((base, text if valid else "", [p for _, _, p in blocks[base]]))
    return result


def annotate_sources(sources):
    """Derive copied passage annotations from complete current sibling originals.

    SHA and URL group sequential saved portions. Locator offsets reassemble entry
    fragments BEFORE citation-window slicing; a missing prefix remains unknown.
    Existing labels are discarded, so summaries/model output cannot set the type.
    """
    values, documents = deepcopy(sources), {}
    for source in values:
        for passage in source.get("excerpts", []):
            passage.pop("source_use", None)
            passage.pop("source_use_basis", None)
        if source.get("sha256"):
            documents.setdefault((source["sha256"], source.get("url", "")), []).append(source)
    for (sha, _), siblings in documents.items():
        blocks = _blocks(siblings)
        pages = {}
        for base, text, _ in blocks:
            match = re.match(r"page-(\d+)-text-", base)
            if match:
                pages.setdefault(match[1], []).append(_normal(text))
        repeats = Counter(text for values in pages.values() for text in set(values[:1] + values[-1:])
            if text and len(text) <= 50 and not re.search(r"[.?!;:]", text))

        def neutral(text):
            text = _normal(text)
            return bool(text and (text.isdecimal() or repeats[text] >= 2))

        active, anchor, continuation = None, None, set()
        for index, (base, text, passages) in enumerate(blocks):
            normalized = _normal(text)
            if _HEADING.fullmatch(normalized):
                # TOC headings followed by page numbers or narrative cannot arm
                # the classifier. Two independent entry blocks confirm a list.
                following = [value for _, value, _ in blocks[index + 1:] if not neutral(value)][:2]
                active = base if len(following) == 2 and all(_entry(value) for value in following) else None
                anchor = active
            elif not active and anchor and _entry(text):
                following = next((value for _, value, _ in blocks[index + 1:] if not neutral(value)), "")
                if _entry(following):
                    active = anchor
            elif active and not (_entry(text) or neutral(text) or index in continuation):
                # PDF layout can break ONE bibliographic entry around a running
                # header or page boundary. Confirm the complete entry before
                # assigning its fragments the same restricted use.
                combined, tail = text, []
                if _AUTHOR.match(normalized):
                    for following_index in range(index + 1, min(index + 5, len(blocks))):
                        following = blocks[following_index][1]
                        if neutral(following):
                            tail.append(following_index)
                            continue
                        if _AUTHOR.match(_normal(following)):
                            break
                        combined += " " + following
                        tail.append(following_index)
                        if _entry(combined):
                            continuation.update(tail)
                            break
                if not tail or not _entry(combined):
                    active = None
            if not active:
                continue
            for passage in passages:
                passage.update(source_use="reference_metadata", source_use_basis={
                    "policy": POLICY, "document_sha256": sha, "locator": passage["passage"],
                    "text_sha256": fingerprint(passage["text"]), "section_locator": active})
    return values


def passage_use(source, passage):
    """Validate host metadata against the complete immutable passage it describes."""
    basis = passage.get("source_use_basis") or {}
    if (passage.get("source_use") == "reference_metadata" and basis.get("policy") == POLICY
            and source.get("sha256") and basis.get("document_sha256") == source["sha256"]
            and basis.get("locator") == passage.get("passage")
            and basis.get("text_sha256") == fingerprint(passage.get("text"))):
        return "reference_metadata"
    return "original"


def citation_use(source, locator, quote):
    matching = [p for p in source.get("excerpts", []) if p.get("passage") == locator
        and isinstance(quote, str) and quote and quote in p.get("text", "")]
    return "reference_metadata" if matching and all(passage_use(source, p) == "reference_metadata" for p in matching) else "original"


def pure_metadata(source):
    passages = [p for p in source.get("excerpts", []) if p.get("text", "").strip()]
    return bool(passages) and all(passage_use(source, p) == "reference_metadata" for p in passages)


def metadata_passages(source):
    return [{"source_id": source["id"], "locator": p["passage"], "quote": p["text"],
        "source_use": "reference_metadata"} for p in source.get("excerpts", [])
        if passage_use(source, p) == "reference_metadata"]


def metadata_summary():
    return "This section contains bibliographic reference metadata and original-source leads. It does not establish the referenced works' substantive findings."


def discovery_leads(source):
    """Literal DOI identifiers are leads, never evidence that a paper was read."""
    values = {}
    for passage in source.get("excerpts", []):
        if passage_use(source, passage) != "reference_metadata":
            continue
        for match in re.finditer(r"\bdoi:\s*(10\.\d{4,9}/[^\s<>]+)", passage["text"], re.I):
            doi = match[1].rstrip(".,;)")
            url = "https://doi.org/" + doi
            values[url] = {"title": _normal(passage["text"])[:500], "url": url,
                "context": passage["text"], "kind": "reference", "source_use": "reference_metadata"}
    return list(values.values())
