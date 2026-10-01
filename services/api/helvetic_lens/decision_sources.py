"""Explicit anonymous inspection of a search result, with robots and size limits."""
import asyncio
import hashlib
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from .config import DomainError
from .db import utcnow
from .decision_engines import DecisionUnavailable, engines, rank
from .decision_search import lexical_order, plain, public_url
from .extraction import validate_public_url
from .product_contribution_extract import FORMATS, MAX_BYTES, extract_file

USER_AGENT = "HelveticLens/1.6 (+https://helveticlens.ch)"


class Download(tuple):
    def __new__(cls, code, media, body, location=None):
        value = super().__new__(cls, (code, media, body))
        value.location = location
        return value


async def read_bytes(client, url, limit):
    await validate_public_url(url, allow_private=False)
    client.cookies.clear()  # Every hop is anonymous, including after robots lookup.
    async with client.stream("GET", url) as response:
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > limit:
                raise DecisionUnavailable("source_too_large")
        return Download(response.status_code, response.headers.get("content-type", ""), bytes(body), response.headers.get("location"))


async def redirect_fetch(client, url, limit, *, check_robots=False, blocked_urls=()):
    visited = []
    for _ in range(6):
        url = public_url(url)
        if not url or url in visited:
            raise DecisionUnavailable("unsafe_or_looping_redirect")
        if url in blocked_urls:
            raise DecisionUnavailable("source_excluded")
        visited.append(url)
        if check_robots:
            parts = urlsplit(url)
            _, robots_response = await redirect_fetch(client, f"https://{parts.netloc}/robots.txt", 65536)
            code, media, robots = robots_response
            if code == 200:
                if "html" in media.lower():
                    raise DecisionUnavailable("robots_unavailable")
                rules = RobotFileParser()
                rules.parse(robots.decode("utf-8", errors="replace").splitlines())
                if not rules.can_fetch("HelveticLens", url):
                    raise DecisionUnavailable("robots_disallowed")
            elif code not in (404, 410):
                raise DecisionUnavailable("robots_unavailable")
        response = await read_bytes(client, url, limit)
        if response[0] not in {301, 302, 303, 307, 308}:
            result = Download(*response, location=getattr(response, "location", None))
            result.redirect_chain = visited
            return url, result
        target = getattr(response, "location", None)
        if not target:
            raise DecisionUnavailable("redirect_unavailable")
        url = urljoin(url, target)
    raise DecisionUnavailable("redirect_limit")


async def inspect_source(settings, query, item, mode, *, rank_passages=True, excerpt_limit=3, document_cursor=None, retain_original=None, blocked_urls=()):
    url = public_url(item["url"])
    if not url:
        raise DecisionUnavailable("unsafe_source")
    async with asyncio.timeout(90):
        async with httpx.AsyncClient(timeout=12, follow_redirects=False, trust_env=False,
                                    headers={"User-Agent": USER_AGENT}) as client:
            url, response = await redirect_fetch(client, url, MAX_BYTES if document_cursor is not None else 1000000, check_robots=True, blocked_urls=blocked_urls)
            code, content_type, body = response
            if code != 200:
                # Ordinary redirects are allowed; authentication barriers are not.
                raise DecisionUnavailable("source_unavailable")
        media = content_type.split(";")[0].lower()
        suffix = next((suffix for suffix, types in FORMATS.items() if media in types), None)
        if media == "application/xhtml+xml":
            suffix, media = ".html", "text/html"
        if not suffix or suffix == ".eml":
            raise DecisionUnavailable("unsupported_source")
        links = []
        if media in ("text/html", "application/xhtml+xml"):
            soup = BeautifulSoup(body, "html.parser")
            for tag in soup.select("script,style,noscript,form"):
                tag.decompose()
            root = soup.find("main") or soup.find("article") or soup
            seen = {url}
            # Main-text references first, then useful site navigation. Links are
            # discovery leads only and must pass normal access/read validation.
            for anchor in [*root.find_all("a", href=True), *soup.find_all("a", href=True)]:
                target = public_url(urljoin(url, anchor["href"]))
                title = plain(anchor.get_text(" ", strip=True), 180)
                if target and target not in seen and title and not anchor["href"].startswith("#"):
                    links.append({"title": title, "url": target,
                        "context": plain(anchor.parent.get_text(" ", strip=True), 350),
                        "kind": "document" if root in anchor.parents else "navigation"})
                    seen.add(target)
                if len(links) >= 512:
                    break
        fetched_at = utcnow().isoformat()
        retained = None
        if retain_original and document_cursor is not None:
            from .product_document_storage import retain
            retained = retain(retain_original["folder"], retain_original["prefix"], body,
                {"title": "source" + suffix, "content_type": media, "url": url,
                 "fetched_at": fetched_at, "links": links, "requested_url": public_url(item["url"]), "redirect_chain": response.redirect_chain})
        document = await extract_file(body, "source" + suffix, media, **({"cursor": document_cursor} if document_cursor is not None else {}))
        if document.get("error"):
            raise DecisionUnavailable("source_extraction_unavailable")
        passages = [{"id": passage["passage"], "title": item["title"], "summary": passage["text"]}
                    for passage in document["excerpts"]]
        order = lexical_order(query, passages)
        by_id = {v["id"]: v for v in passages}
        selected = passages if document_cursor is not None else [by_id[i] for i in order[:8]]
        inspected_engine = None
        errors = []
        choices = ["laya"] if mode == "laya" else ["jev"] if mode == "jev" else ["jev", "laya"]
        scores = {}
        for name in choices if rank_passages else []:
            try:
                answers = await rank(engines(settings)[name], query, selected)
                scores = {identifier: result.probabilities["A"] for identifier, result in answers}
                selected.sort(key=lambda value: -scores[value["id"]])
                inspected_engine = name
                break
            except (DecisionUnavailable, TimeoutError):
                errors.append(name)
        return {"status": "complete", "url": url, "fetched_at": fetched_at,
            "requested_url": public_url(item["url"]), "redirect_chain": response.redirect_chain,
            **({"_retained_document": retained} if retained else {}),
            "sha256": hashlib.sha256(body).hexdigest(), "content_type": media,
            "excerpts": [{"text": v["summary"], "passage": v["id"], "relevance": scores.get(v["id"])} for v in (selected if document_cursor is not None else selected[:excerpt_limit])],
            "links": links, "engine": inspected_engine, "unavailable_engines": errors,
            "reading": document.get("reading"),
            "scope": ("Immutable anonymous original, at most 100 MB; all extracted passages in this saved portion. "
                if document_cursor is not None else "Anonymous fetch, at most 1 MB; safe redirects checked against each destination's robots policy. "
                f"Up to the first 24,000 extracted characters, eight lexical candidate passages and {excerpt_limit} verbatim excerpts. "
                "Links are present in the page, not verified citations or approved monitoring sources."),
            "text_truncated": document["text_truncated"], "extracted_characters": document["extracted_characters"],
            "extraction_methods": document["extraction_methods"], "extraction_scope": document["scope"],
            "warnings": document["warnings"], "page_count": document["page_count"]}


async def safe_inspect(settings, query, item, mode, *, rank_passages=True, excerpt_limit=3, document_cursor=None, retain_original=None, blocked_urls=()):
    try:
        return await inspect_source(settings, query, item, mode, rank_passages=rank_passages, excerpt_limit=excerpt_limit, blocked_urls=blocked_urls, **({"retain_original": retain_original} if retain_original else {}), **({"document_cursor": document_cursor} if document_cursor is not None else {}))
    except (DecisionUnavailable, DomainError, httpx.HTTPError, TimeoutError, ValueError) as exc:
        return {"status": "unavailable", "url": item["url"],
            "error_code": getattr(exc, "code", "source_unavailable"),
            "error": "This source could not be inspected within its access, format or time limits. Open the original source directly."}
