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
from .extraction import extract, validate_public_url

USER_AGENT = "HelveticLens/1.6 (+https://helveticlens.ch)"


async def read_bytes(client, url, limit):
    await validate_public_url(url, allow_private=False)
    async with client.stream("GET", url) as response:
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > limit:
                raise DecisionUnavailable("source_too_large")
        return response.status_code, response.headers.get("content-type", ""), bytes(body)


async def inspect_source(settings, query, item, mode):
    url = public_url(item["url"])
    if not url:
        raise DecisionUnavailable("unsafe_source")
    parts = urlsplit(url)
    async with asyncio.timeout(55):
        async with httpx.AsyncClient(timeout=12, follow_redirects=False, trust_env=False,
                                    headers={"User-Agent": USER_AGENT}) as client:
            code, _, robots = await read_bytes(client, f"https://{parts.netloc}/robots.txt", 65536)
            if code == 200:
                rules = RobotFileParser()
                rules.parse(robots.decode("utf-8", errors="replace").splitlines())
                if not rules.can_fetch("HelveticLens", url):
                    raise DecisionUnavailable("robots_disallowed")
            elif code not in (404, 410):
                raise DecisionUnavailable("robots_unavailable")
            code, content_type, body = await read_bytes(client, url, 1000000)
            if code != 200:
                # No cookies, login, paywall/challenge handling or redirect bypass.
                raise DecisionUnavailable("source_unavailable")
        media = content_type.split(";")[0].lower()
        if media not in ("text/html", "application/xhtml+xml", "text/plain", "application/pdf"):
            raise DecisionUnavailable("unsupported_source")
        links = []
        if media in ("text/html", "application/xhtml+xml"):
            soup = BeautifulSoup(body, "html.parser")
            for tag in soup.select("script,style,nav,header,footer,noscript,form"):
                tag.decompose()
            root = soup.find("main") or soup.find("article") or soup
            seen = {url}
            for anchor in root.find_all("a", href=True):
                target = public_url(urljoin(url, anchor["href"]))
                title = plain(anchor.get_text(" ", strip=True), 180)
                if target and target not in seen and title and not anchor["href"].startswith("#"):
                    links.append({"title": title, "url": target})
                    seen.add(target)
                if len(links) >= 20:
                    break
        document = await asyncio.to_thread(extract, body, media,
            "source.pdf" if media == "application/pdf" else "source.html", "native")
        text = document.text[:24000]
        # Stable non-overlapping passages; bounded candidate selection is disclosed.
        passages = [{"id": f"p{i // 600 + 1}", "title": item["title"], "summary": text[i:i + 600]}
                    for i in range(0, len(text), 600) if text[i:i + 600].strip()]
        order = lexical_order(query, passages)
        by_id = {v["id"]: v for v in passages}
        selected = [by_id[i] for i in order[:8]]
        inspected_engine = None
        errors = []
        choices = ["laya"] if mode == "laya" else ["jev"] if mode == "jev" else ["jev", "laya"]
        scores = {}
        for name in choices:
            try:
                answers = await rank(engines(settings)[name], query, selected)
                scores = {identifier: result.probabilities["A"] for identifier, result in answers}
                selected.sort(key=lambda value: -scores[value["id"]])
                inspected_engine = name
                break
            except (DecisionUnavailable, TimeoutError):
                errors.append(name)
        return {"status": "complete", "url": url, "fetched_at": utcnow().isoformat(),
            "sha256": hashlib.sha256(body).hexdigest(), "content_type": media,
            "excerpts": [{"text": v["summary"], "passage": v["id"], "relevance": scores.get(v["id"])} for v in selected[:3]],
            "links": links, "engine": inspected_engine, "unavailable_engines": errors,
            "scope": "Anonymous fetch, at most 1 MB; redirects and access barriers are not followed. "
                "Up to the first 24,000 extracted characters, eight lexical candidate passages and three verbatim excerpts. "
                "Links are present in the page, not verified citations or approved monitoring sources.",
            "text_truncated": len(document.text) > 24000, "extracted_characters": len(document.text)}


async def safe_inspect(settings, query, item, mode):
    try:
        return await inspect_source(settings, query, item, mode)
    except (DecisionUnavailable, DomainError, httpx.HTTPError, TimeoutError, ValueError):
        return {"status": "unavailable", "url": item["url"],
            "error": "This source could not be inspected within its access, format or time limits. Open the original source directly."}
