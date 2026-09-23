"""Strict Fedlex HTML article boundaries; never slice flattened text or URL anchors."""

import hashlib
import re

from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .config import DomainError
from .extraction import HTML_EXTRACTOR_VERSION, Extracted, Fetched, extract, fedlex_eli_reference, normalize

NUMBER = re.compile(r"([1-9][0-9]{0,4})([a-z]?)")
ARTICLE_ID = re.compile(r"art_([1-9][0-9]{0,4})(?:_([a-z]))?")
PARSER = "fedlex-range-v1"


def number_key(value: str):
    match = NUMBER.fullmatch(value)
    if not match:
        raise ValueError("Use an article number such as 319 or 323b.")
    return int(match[1]), match[2]


class ArticleSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    start: str = Field(max_length=6)
    end: str = Field(max_length=6)
    language: str = Field(default="de", pattern="^de$")

    @field_validator("start", "end")
    @classmethod
    def article_number(cls, value):
        value = value.lower()
        number_key(value)
        return value

    @model_validator(mode="after")
    def ordered(self):
        if number_key(self.start) > number_key(self.end):
            raise ValueError("The first article must precede or equal the last article.")
        return self


def validate_selection(url: str, provider: str, selection: dict | None) -> dict:
    if not selection:
        return {}
    try:
        selected = ArticleSelection.model_validate(selection).model_dump()
    except ValueError as exc:
        raise DomainError("Enter a valid article range, for example 319 to 323b.", 422, "invalid_article_range") from exc
    reference = fedlex_eli_reference(url)
    if (not reference or reference.collection != "cc" or reference.language != "de"
            or reference.requested_format not in {None, "html"} or provider != "native"):
        raise DomainError("Selected articles require a German Fedlex consolidated-law URL and native HTML extraction.",
                          422, "article_source_unsupported")
    return selected


def scope_label(selection: dict, url: str) -> str:
    reference = fedlex_eli_reference(url)
    name = " OR" if reference and reference.work_uri.endswith("/cc/27/317_321_377") else ""
    return f"Art. {selection['start']}–{selection['end']}{name}, DE"


def extract_document(fetched: Fetched, filename: str, provider: str = "native", *,
                     selection: dict | None = None, source_url: str = "") -> Extracted:
    if not selection:
        return extract(fetched.body, fetched.content_type, filename, provider)
    selection = validate_selection(source_url, provider, selection)
    if (fetched.metadata.get("fedlex_eli") is not True
            or fetched.metadata.get("eli_language") != "de"
            or fetched.metadata.get("eli_format") != "html"
            or fetched.content_type.split(";")[0] not in {"text/html", "application/xhtml+xml"}):
        raise DomainError("Fedlex did not return the expected German structured HTML. The previous snapshot is preserved.",
                          422, "article_structure_changed")
    # Keep the fetcher's size/timeout limits and a separate parser input bound.
    if len(fetched.body) > 8 * 1024 * 1024:
        raise DomainError("The article source exceeds the parser input limit.", 413, "document_too_large")
    soup = BeautifulSoup(fetched.body, "html.parser")
    roots = soup.select("#lawcontent main#maintext")
    if len(roots) != 1:
        raise DomainError("Fedlex article structure is missing or ambiguous. Review the official source.",
                          422, "article_structure_changed")
    nodes = roots[0].find_all("article")
    def boundary(number):
        match = NUMBER.fullmatch(number)
        anchor = f"art_{match[1]}" + (f"_{match[2]}" if match[2] else "")
        positions = [index for index, node in enumerate(nodes) if node.get("id") == anchor]
        if len(positions) != 1:
            raise DomainError("The first or last selected article is missing or ambiguous. Check both boundaries; the previous snapshot is preserved.",
                              422, "article_boundary_missing")
        return positions[0]
    first, last = boundary(selection["start"]), boundary(selection["end"])
    if first > last:
        raise DomainError("Fedlex article boundaries are out of order. Review the source.", 422, "article_structure_changed")
    indexed = []
    seen = set()
    for node in nodes[first:last + 1]:
        match = ARTICLE_ID.fullmatch(node.get("id", ""))
        if not match or node.find("article"):
            raise DomainError("This Fedlex article numbering or structure is unsupported. Review the official source.",
                              422, "article_structure_changed")
        number = match[1] + (match[2] or "")
        key = number_key(number)
        if number in seen or indexed and key <= indexed[-1][0]:
            raise DomainError("Fedlex article boundaries are duplicated or out of order. Review the source.",
                              422, "article_structure_changed")
        seen.add(number)
        indexed.append((key, number, node))
    selected = [(number, node) for key, number, node in indexed]
    required_numbers = {str(number) for number in range(number_key(selection["start"])[0], number_key(selection["end"])[0] + 1)
                        if number_key(selection["start"]) <= (number, "") <= number_key(selection["end"])}
    if not required_numbers <= seen:
        raise DomainError("An article inside the selected range is missing. Review the official structure.",
                          422, "article_structure_changed")
    if len(selected) > 500:
        raise DomainError("Select no more than 500 articles at a time.", 413, "document_too_large")
    articles, passages = [], []
    for number, node in selected:
        if sum(candidate.get("id") == node["id"] for candidate in nodes) != 1:
            raise DomainError("An article boundary is ambiguous. Review the official structure.", 422, "article_structure_changed")
        heading = node.find(class_="heading", recursive=False)
        heading_link = heading.find("a", href=f"#{node['id']}") if heading else None
        label = normalize(heading_link.get_text(" ", strip=True)) if heading_link else ""
        if re.sub(r"\s+", "", label) != f"Art.{number}":
            raise DomainError("An article heading does not match its structural boundary. Review the source.",
                              422, "article_structure_changed")
        bodies = node.select(":scope > .collapseable")
        if len(bodies) != 1 or not normalize(bodies[0].get_text(" ", strip=True)):
            raise DomainError(f"Art. {number} has no complete readable body. The previous snapshot is preserved.",
                              422, "article_structure_changed")
        section_titles = []
        for parent in node.parents:
            if parent.name == "section":
                title = parent.find(class_="heading", recursive=False)
                if title:
                    section_titles.append(normalize(title.get_text(" ", strip=True)))
        title = " / ".join(reversed(section_titles[:3]))
        # Retain all body text, including lists and article-local editorial notes.
        # Newline boundaries preserve paragraphs; no substring search selects text.
        body = bodies[0]
        for br in body.find_all("br"):
            br.replace_with(" ")
        for paragraph in body.find_all(["p", "li", "tr", "dt", "dd"]):
            paragraph.insert_after("\n\n")
        body_text = "\n\n".join(normalize(part) for part in body.get_text(" ").split("\n\n") if normalize(part))
        article_text = f"Art. {number}\n{title}\n\n{body_text}"
        passages.append({"id": f"art-{number}", "text": article_text, "page": None,
                         "article_number": number, "article_heading": title, "source_anchor": node["id"]})
        articles.append({"number": number, "heading": title, "anchor": node["id"], "characters": len(article_text)})
    text = "\n\n".join(p["text"] for p in passages)
    if len(text) > 1200000 or len(passages) > 6000:
        raise DomainError("The selected articles exceed the MVP text limit. Choose a smaller range.", 413, "document_too_large")
    title_node = soup.select_one("#preface h1")
    title = fetched.metadata.get("eli_title") or (normalize(title_node.get_text(" ", strip=True)) if title_node else filename)
    provenance = {"selection": selection, "scope": scope_label(selection, source_url),
                  "parser": PARSER, "articles": articles,
                  "official_url": source_url, "artifact_url": fetched.url,
                  "original_sha256": hashlib.sha256(fetched.body).hexdigest(),
                  "official_version_date": fetched.metadata.get("eli_version_date"),
                  "expression_uri": fetched.metadata.get("eli_expression_uri")}
    return Extracted(title[:500], text, passages, "text/html", filename, fetched.body,
                     f"native-{PARSER}-{HTML_EXTRACTOR_VERSION}", provenance)


def verify_article_continuity(previous: list[dict], current: list[dict]):
    if [p.get("article_number") for p in previous] != [p.get("article_number") for p in current]:
        raise DomainError("The selected article structure changed or an article disappeared. Review the official source; the last successful snapshot is preserved.",
                          422, "article_structure_changed")


def comparison_projection(passages: list[dict], body: bytes) -> list[dict]:
    """Project source-confirmed editorial layout; never rewrite retained evidence.

    Inline HTML spans do not insert word spaces. Only paired numeric footnote
    references/backlinks are removed; the full footnote wording remains evidence.
    Ambiguous article/note structure receives no editorial-equivalence key.
    """
    soup = BeautifulSoup(body, "html.parser")
    roots = soup.select("#lawcontent main#maintext")
    nodes = roots[0].find_all("article") if len(roots) == 1 else []
    output = []
    for passage in passages:
        item = dict(passage)
        item.pop("editorial_comparison_key", None)
        matches = [node for node in nodes if node.get("id") == passage.get("source_anchor")]
        if len(matches) != 1 or not passage.get("article_number"):
            output.append(item)
            continue
        containers = matches[0].select(":scope > .collapseable")
        if len(containers) != 1:
            output.append(item)
            continue
        container = containers[0]
        valid = True
        for note in container.select(".footnotes p[id]"):
            refs = [link for link in container.select("sup a[href]") if link.get("href") == f"#{note['id']}"]
            backlinks = note.select("sup a[href]")
            if (len(refs) != 1 or len(backlinks) != 1
                    or not refs[0].get("id") or not refs[0].get_text(strip=True).isdigit()
                    or backlinks[0].get("href") != f"#{refs[0]['id']}"
                    or refs[0].get_text(strip=True) != backlinks[0].get_text(strip=True)):
                valid = False
                break
            refs[0].decompose()
            backlinks[0].decompose()
        if valid:
            for br in container.find_all("br"):
                br.replace_with(" ")
            for block in container.find_all(["p", "li", "tr", "dt", "dd"]):
                block.insert_after("\n")
            projection = normalize(container.get_text())
            item["editorial_comparison_key"] = hashlib.sha256(
                (str(passage["article_number"]) + "\n" + passage.get("article_heading", "")
                 + "\n" + projection).encode()
            ).hexdigest()
        output.append(item)
    return output
