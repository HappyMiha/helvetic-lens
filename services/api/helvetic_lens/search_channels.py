"""Operator-selected broad discovery; independent, key-free public catalogues."""
import hashlib
import json
import re
from time import perf_counter
from urllib.parse import urlsplit

import httpx

from .decision_engines import DecisionUnavailable

MAX_BYTES = 1_000_000


def broad_configured(settings):
    return bool(settings.searxng_base_url) if settings.web_search_provider == "searxng" else (
        bool(settings.search1api_api_key.get_secret_value()) if settings.web_search_provider == "search1api" else False)


def catalogue_names(product):
    from .domain_packs import for_product

    return for_product(product).discovery_sources


def request_count(settings, depth="balanced", alternatives=(), *, product=None):
    # Counts requests to provider APIs, not the engines behind a metasearch API.
    broad = 0 if settings.web_search_provider == "none" else (
        2 if settings.web_search_provider == "search1api" and depth != "quick" else 1)
    names = catalogue_names(product)[:1] if depth == "quick" else catalogue_names(product)
    direct = sum(3 if name == "federal_court" else 1 for name in names) if product else (1 if depth == "quick" else 2)
    return broad + (len(alternatives) if broad else 0) + direct


def paid_request_count(settings, depth="balanced", alternatives=()):
    """Only a configured paid broad-web provider consumes a query allowance."""
    if settings.web_search_provider != "search1api" or not broad_configured(settings):
        return 0
    return (1 if depth == "quick" else 2) + len(alternatives)


def request_settings(settings, skipped_paid=None):
    return settings.model_copy(update={"web_search_provider": "none"}) if skipped_paid else settings


def note_skipped_paid(result, reason):
    if reason:
        result.setdefault("skipped_channels", []).append({"name": "Search1API", "reason": reason})
    return result


async def bounded_get(url, params, *, timeout=15):
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            async with client.stream("GET", url, params=params,
                    headers={"Accept": "application/json", "User-Agent": "HelveticLens/1.0 (public research)"}) as response:
                if response.status_code != 200:
                    raise DecisionUnavailable("quota" if response.status_code in (402, 429) else "unavailable")
                body = bytearray()
                async for part in response.aiter_bytes():
                    body.extend(part)
                    if len(body) > MAX_BYTES:
                        raise DecisionUnavailable("response_too_large")
        result = json.loads(body)
        if not isinstance(result, dict):
            raise ValueError("Expected an object")
        return result
    except (httpx.HTTPError, ValueError) as exc:
        raise DecisionUnavailable("invalid_search_response") from exc


async def searxng(settings, query, index, *, limit=12, cursor=None, **_):
    from .decision_search import plain, public_url

    base = settings.searxng_base_url.rstrip("/")
    parts = urlsplit(base)
    # This endpoint is operator-owned, never taken from a query or model output.
    if (parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password
            or parts.query or parts.fragment):
        raise DecisionUnavailable("search_not_configured")
    page = int(cursor or 1)
    if page < 1:
        raise DecisionUnavailable("invalid_search_cursor")
    started = perf_counter()
    result = await bounded_get(base + "/search", {
        "q": query, "format": "json", "categories": "general", "engines": settings.searxng_engines,
        "language": "auto", "safesearch": 0, "pageno": page}, timeout=20)
    records = result.get("results")
    errors = result.get("unresponsive_engines", [])
    if not isinstance(records, list) or len(records) > 200 or not isinstance(errors, list):
        raise DecisionUnavailable("invalid_search_response")
    items = {}
    for raw in records[:limit]:
        if not isinstance(raw, dict) or not isinstance(raw.get("title"), str) or not isinstance(raw.get("content", ""), str):
            continue
        url = public_url(raw.get("url"))
        title = plain(raw["title"], 240)
        if not url or not title:
            continue
        identifier = hashlib.sha256(url.encode()).hexdigest()[:32]
        items.setdefault(identifier, {"id": identifier, "kind": "web_source", "provider": "SearXNG",
            "title": title, "summary": plain(raw.get("content", ""), 600), "url": url, "date": None})
    # Report configured engine names, never raw upstream errors or stack traces.
    allowed = set(settings.searxng_engines.split(","))
    unavailable = sorted({v[0] for v in errors if isinstance(v, list) and v and isinstance(v[0], str) and v[0] in allowed})
    if unavailable and len(unavailable) == len(allowed) and not items:
        raise DecisionUnavailable("upstream_unavailable")
    return {"items": list(items.values()), "next_cursor": str(page + 1) if items else None, "page_number": page,
        "index": "web", "service": "searxng", "provider": "SearXNG",
        "status": "partial" if errors else "complete", "unavailable_engines": unavailable,
        "engines_requested": sorted(allowed), "latency_ms": round((perf_counter() - started) * 1000, 2),
        "cost_usd": None, "omitted_records": len(records) - len(items), "candidate_limit": limit}


async def direct_search(provider, query, cursor=None):
    from .decision_search import plain, public_url
    from .product_research import public_search

    if provider in {"clinicaltrials", "fda_labels", "ema_news", "finma_news", "federal_court"}:
        from .research_catalogues import search
        return await search(provider, query, **({"cursor": cursor} if cursor is not None else {}))
    if provider != "crossref":
        return await public_search(provider, query, cursor, unlimited=True)
    result = await bounded_get("https://api.crossref.org/works", {"query.bibliographic": query,
        "rows": 12, "cursor": cursor or "*", "select": "DOI,title,URL,abstract,publisher"})
    message = result.get("message")
    records = message.get("items") if isinstance(message, dict) else None
    if not isinstance(records, list) or len(records) > 12:
        raise DecisionUnavailable("invalid_search_response")
    items = []
    for raw in records:
        if not isinstance(raw, dict):
            continue
        titles = raw.get("title")
        url = public_url(raw.get("URL"))
        abstract = raw.get("abstract", "")
        if not url or not isinstance(titles, list) or not titles or not isinstance(titles[0], str) or not isinstance(abstract, str):
            continue
        title = plain(titles[0], 240)
        if title:
            items.append({"id": hashlib.sha256(url.encode()).hexdigest()[:32], "kind": "literature",
                "provider": "Crossref", "title": title, "url": url, "summary": plain(abstract, 600), "date": None})
    return {"items": items, "omitted_records": len(records) - len(items),
        "next_cursor": message.get("next-cursor") if records and message.get("next-cursor") != cursor else None}


def explicit_sources(text):
    """URLs submitted in the public question still go through the normal reader."""
    from .decision_search import public_url

    items = {}
    for raw in re.findall(r"https://[^\s<>\"']+", text):
        url = public_url(raw.rstrip(".,;!?)"))
        if url and url not in items:
            items[url] = {"id": hashlib.sha256(url.encode()).hexdigest()[:32], "kind": "web_source",
                "provider": "Submitted public source", "title": urlsplit(url).hostname,
                "url": url, "summary": "Public URL supplied with the research question; contents not yet read.", "date": None}
        if len(items) >= 4:
            break
    return list(items.values())
