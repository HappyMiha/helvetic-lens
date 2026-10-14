"""Anonymous feed acquisition through the shared source and original readers.

RSS/Atom entries are discovery leads, never substitutes for their full originals.
The independent-source collection pattern also used by LegalFeed is implemented
here with Core's existing robots, redirect, integrity and extraction safeguards.
"""
from urllib.parse import urljoin
from xml.etree.ElementTree import ParseError

import httpx

from . import decision_sources, product_document_storage
from .db import utcnow
from .decision_engines import DecisionUnavailable
from .decision_search import plain, public_url
from .document_formats import xml
from .product_contribution_extract import FORMATS, MAX_BYTES

XML_TYPES = {"application/rss+xml", "application/atom+xml", "application/xml", "text/xml"}


def feed_items(body, url):
    root = xml(body)
    kind = root.tag.rsplit("}", 1)[-1]
    if kind not in {"rss", "feed", "RDF"}:
        raise DecisionUnavailable("unsupported_xml_source")
    items, pages, omitted = {}, [], 0
    for row in root.iter():
        tag = row.tag.rsplit("}", 1)[-1]
        if tag not in {"item", "entry"}:
            continue
        fields = {child.tag.rsplit("}", 1)[-1]: "".join(child.itertext()) for child in row}
        target = fields.get("link", "")
        for child in row:
            if child.tag.rsplit("}", 1)[-1] == "link" and child.get("rel", "alternate") == "alternate":
                target = child.get("href") or target
        target = public_url(urljoin(url, target)) if target else None
        if not target:
            omitted += 1
            continue
        items[target] = {"url": target, "title": plain(fields.get("title", target), 240),
            "summary": plain(fields.get("description") or fields.get("summary") or "", 600),
            "date": fields.get("published") or fields.get("pubDate") or fields.get("updated"),
            "provider": "Publisher RSS/Atom", "kind": "feed_entry"}
    # Atom's next relation is also used by paged RSS archives. Each page is
    # anonymously fetched and retained; repeated URLs are stopped by the worker.
    for child in root.iter():
        if child.tag.rsplit("}", 1)[-1] == "link" and child.get("rel") == "next":
            target = public_url(urljoin(url, child.get("href", "")))
            if target and target not in pages:
                pages.append(target)
    return list(items.values()), pages, omitted


async def read(service, item, prefix, progress):
    cursor = progress.get("cursor") or {"page": 0, "offset": 0}
    original = progress.get("retained_document")
    if original:
        result = await product_document_storage.read(service,
            {"retained_document": original, "document_cursor": cursor})
        return {**result, "content_type": original["content_type"]}
    url = public_url(item["url"])
    if not url:
        raise DecisionUnavailable("unsafe_source")
    async with httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False,
            headers={"User-Agent": decision_sources.USER_AGENT}) as client:
        url, response = await decision_sources.redirect_fetch(client, url, MAX_BYTES, check_robots=True)
    code, content_type, body = response
    if code != 200:
        raise DecisionUnavailable("source_unavailable")
    media = content_type.split(";")[0].strip().lower()
    if media == "application/xhtml+xml":
        media = "text/html"
    suffix = next((suffix for suffix, types in FORMATS.items() if media in types), ".bin")
    original = product_document_storage.retain(service.environment_settings.storage_path / "artifacts",
        prefix, body, {"title": "source" + suffix, "content_type": media, "url": url,
            "requested_url": item["url"], "redirect_chain": response.redirect_chain,
            "fetched_at": utcnow().isoformat()})
    if media in XML_TYPES:
        try:
            items, pages, omitted = feed_items(body, url)
        except (ValueError, ParseError, DecisionUnavailable):
            return {"status": "unavailable", "error_code": "invalid_feed_source", "_retained_document": original}
        return {"status": "index", "items": items, "next_pages": pages,
            "omitted_records": omitted, "_retained_document": original}
    if suffix in {".bin", ".eml"}:
        return {"status": "unavailable", "error_code": "unsupported_source", "_retained_document": original}
    result = await product_document_storage.read(service,
        {"retained_document": original, "document_cursor": cursor})
    return {**result, "content_type": media}
