"""Public web retrieval and same-input, inspectable System One decisions."""
import asyncio
import hashlib
import html
import ipaddress
import math
import re
from collections import Counter
from time import perf_counter
from urllib.parse import urlsplit, urlunsplit

from . import decision_engines as decision
from . import search_channels
from .product_provenance import canonical

MAX_RESULTS = 12


def public_url(value):
    if not isinstance(value, str) or len(value) > 2000 or any(ord(c) < 33 for c in value) or "\\" in value:
        return None
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").lower()
        if (parts.scheme != "https" or parts.username or parts.password or parts.port not in (None, 443)
                or "." not in host or host.endswith((".localhost", ".local", ".internal"))):
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            pass
        return urlunsplit(("https", host, parts.path or "/", parts.query, ""))
    except ValueError:
        return None


def plain(value, limit):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", value))).strip()[:limit]


async def retrieve(settings, query, index, *, service="google", limit=MAX_RESULTS):
    if settings.web_search_provider == "searxng":
        return await search_channels.searxng(settings, query, index, limit=limit)
    if settings.web_search_provider != "search1api":
        raise decision.DecisionUnavailable("search_not_configured")
    key = settings.search1api_api_key.get_secret_value()
    if not key:
        raise decision.DecisionUnavailable("search_not_configured")
    started = perf_counter()
    result = await decision.bounded_json("https://api.search1api.com/" + ("news" if index == "news" else "search"), key,
        {"query": query, "search_service": service, "max_results": limit}, timeout=25)
    if (not isinstance(result, dict) or result.get("error") or not isinstance(result.get("results"), list)
            or len(result["results"]) > 100):
        raise decision.DecisionUnavailable("invalid_search_response")
    items = {}
    for raw in result["results"][:limit]:
        if not isinstance(raw, dict) or not isinstance(raw.get("title"), str) or not isinstance(raw.get("snippet", ""), str):
            continue
        url = public_url(raw.get("link"))
        title = plain(raw["title"], 240)
        if not url or not title:
            continue
        identifier = hashlib.sha256(url.encode()).hexdigest()[:32]
        items.setdefault(identifier, {"id": identifier, "kind": "web_source", "provider": "Search1API",
            "title": title, "summary": plain(raw.get("snippet", ""), 600), "url": url, "date": None})
    return {"items": list(items.values()), "index": index, "service": service, "provider": "Search1API",
        "latency_ms": round((perf_counter() - started) * 1000, 2), "cost_usd": None,
        "omitted_records": len(result["results"]) - len(items), "candidate_limit": limit}


def lexical_order(query, items):
    """Small-candidate BM25 preserves exact names alongside semantic decisions."""
    terms = set(re.findall(r"\w+", query.casefold()))
    docs = [Counter(re.findall(r"\w+", (v["title"] + " " + v["summary"]).casefold())) for v in items]
    average = sum(sum(doc.values()) for doc in docs) / max(len(docs), 1) or 1
    df = {term: sum(term in doc for doc in docs) for term in terms}
    def score(doc):
        length = sum(doc.values())
        return sum(math.log(1 + (len(docs) - df[t] + 0.5) / (df[t] + 0.5))
            * doc[t] * 2.2 / (doc[t] + 1.2 * (0.25 + 0.75 * length / average)) for t in terms if doc[t])
    return [v[0]["id"] for v in sorted(zip(items, docs), key=lambda v: -score(v[1]))]


def reciprocal_fusion(rankings):
    weights = {}
    for ranking in rankings:
        for position, identifier in enumerate(dict.fromkeys(ranking), 1):
            weights[identifier] = weights.get(identifier, 0) + 1 / (60 + position)
    return weights


async def federated_retrieve(settings, query, index, depth, product, alternatives=(), *, public_sources=()):
    started = perf_counter()
    limit = 8 if depth == "quick" else 20 if depth == "deep" else 12
    broad = settings.web_search_provider
    name = "SearXNG web" if broad == "searxng" else "Google " + index
    lanes = []
    if broad != "none":
        lanes.append((name, query, retrieve(settings, query, index, limit=limit)))
        if depth != "quick" and broad == "search1api":
            lanes.append(("Bing web", query, retrieve(settings, query, "web", service="bing", limit=limit)))
        for number, alternative in enumerate(alternatives, 1):
            lanes.append((f"{name} alternative {number}", alternative, retrieve(settings, alternative, "web", limit=limit)))
    from .research_contracts import SOURCES
    available = search_channels.catalogue_names(product)
    catalogues = available[:1] if depth == "quick" else available
    labels = {key: SOURCES[key].label for key in available}
    for provider in catalogues:
        lanes.append((labels[provider], query, search_channels.direct_search(provider, query)))
    outcomes = await asyncio.gather(*(work for _, _, work in lanes), return_exceptions=True)
    items, rankings, coverage, origins, found_by = {}, [], [], {}, {}
    omitted = 0
    for (name, lane_query, _), result in zip(lanes, outcomes):
        if isinstance(result, Exception):
            code = result.code if isinstance(result, decision.DecisionUnavailable) else "unavailable"
            coverage.append({"name": name, "query": lane_query, "status": "unavailable", "count": 0, "reason": code})
            continue
        ranking = []
        for item in result["items"]:
            safe = public_url(item["url"])
            if not safe:
                omitted += 1
                continue
            identifier = hashlib.sha256(safe.encode()).hexdigest()[:32]
            if identifier in items:
                omitted += 1
            items.setdefault(identifier, {**item, "id": identifier, "url": safe,
                "title": item["title"][:240], "summary": item["summary"][:600]})
            if identifier not in ranking:
                ranking.append(identifier)
            if name not in origins.setdefault(identifier, []):
                origins[identifier].append(name)
            if lane_query not in found_by.setdefault(identifier, []):
                found_by[identifier].append(lane_query)
        rankings.append(ranking)
        omitted += result.get("omitted_records", 0)
        partial = result.get("status") == "partial"
        coverage.append({"name": name + (" (available engines)" if partial else ""), "query": lane_query,
            "status": "complete", "count": len(ranking),
            "scope": result.get("scope") or "Bounded catalogue or search response; not exhaustive coverage.",
            "more_available": result.get("more_available") or bool(result.get("next_cursor")),
            "examined_records": result.get("examined_records")})
        if partial:
            for engine in result.get("unavailable_engines") or ["upstream engine"]:
                coverage.append({"name": name + " / " + engine, "query": lane_query,
                    "status": "unavailable", "count": 0, "reason": "upstream_unavailable"})
    submitted = search_channels.explicit_sources(" ".join([query, *public_sources]))
    for item in submitted:
        items.setdefault(item["id"], item)
        origins.setdefault(item["id"], []).append("Submitted public source")
        if query not in found_by.setdefault(item["id"], []):
            found_by[item["id"]].append(query)
    if submitted:
        rankings.append([v["id"] for v in submitted])
        coverage.append({"name": "Submitted public sources", "query": query, "status": "complete", "count": len(submitted)})
    fusion = reciprocal_fusion(rankings)
    maximum = 8 if depth == "quick" else 36 if depth == "deep" else 24
    candidates = sorted(items.values(), key=lambda item: -fusion[item["id"]])[:maximum]
    for item in candidates:
        item["retrieval_queries"] = found_by[item["id"]]
    return {"items": candidates, "index": "web" if broad != "search1api" else index,
        "service": "federated", "provider": "Public catalogues / " + broad,
        "latency_ms": round((perf_counter() - started) * 1000, 2), "cost_usd": None,
        "omitted_records": omitted, "candidate_limit": maximum, "discovered_count": len(items),
        "status": "complete" if all(c["status"] == "complete" for c in coverage) else "partial" if rankings else "unavailable",
        "lanes": coverage, "origins": {v["id"]: origins[v["id"]] for v in candidates},
        "skipped_channels": [{"name": labels[key], "reason": "Outside quick-search budget."} for key in available if key not in catalogues],
        "search_requests": search_channels.request_count(settings, depth, alternatives, product=product), "depth": depth}


async def execute(settings, query, mode, depth="balanced", product="pharma", alternatives=()):
    """Auto falls back on any disclosed provider failure, never on confidence alone."""
    started = perf_counter()
    available = decision.engines(settings)
    selected = None
    plans, rankings, traces, errors, times = {}, {}, {}, {}, {}
    asked = ["laya"] if mode == "laya" else (["jev"] if mode == "jev" else ["jev", "laya"])

    async def plan(name):
        t0 = perf_counter()
        try:
            answer = await decision.strategy(available[name], query)
            plans[name] = answer.choice
            traces.setdefault(name, []).append(answer)
        except decision.DecisionUnavailable as exc:
            errors[name] = exc.code
        finally:
            times[name] = (perf_counter() - t0) * 1000

    async def ranking(name, items):
        t0 = perf_counter()
        try:
            answers = await decision.rank(available[name], query, items)
            rankings[name] = {identifier: {"relevance": result.probabilities["A"],
                "selected_probability": result.selected_probability, "confidence": result.confidence}
                for identifier, result in answers}
            traces.setdefault(name, []).extend(answer for _, answer in answers)
        except decision.DecisionUnavailable as exc:
            errors[name] = exc.code
        except TimeoutError:
            errors[name] = "timeout"
        finally:
            times[name] = times.get(name, 0) + (perf_counter() - t0) * 1000

    if mode == "compare":
        await asyncio.gather(*(plan(name) for name in asked))
    else:
        for name in asked:
            await plan(name)
            if name in plans:
                break
    selected = next((name for name in asked if name in plans), None)
    if selected is None:
        retrieval = await federated_retrieve(settings, query, "web", depth, product, alternatives)
        items = retrieval.pop("items")
        return {"items": items, "retrieval": retrieval, "selected_engine": None,
                "candidates_sha256": hashlib.sha256(canonical({"query": query, "items": items}).encode()).hexdigest(),
                "latency_ms": round((perf_counter() - started) * 1000, 2),
                "coverage": "Source candidates in discovery order; decision providers were unavailable. Pages have not been read.",
                "error": "Decision providers are unavailable. Showing source discovery without semantic ranking.",
                "engines": [{**decision.measurement(name, [], settings, error=errors.get(name)),
                             "latency_ms": round(times.get(name, 0), 2), "scores": {}} for name in asked]}
    retrieval = await federated_retrieve(settings, query, plans[selected], depth, product, alternatives)
    items = retrieval.pop("items")
    candidates_sha256 = hashlib.sha256(canonical({"query": query, "items": items}).encode()).hexdigest()
    if mode == "compare":
        await asyncio.gather(*(ranking(name, items) for name in asked if name in plans))
    else:
        await ranking(selected, items)
        if selected not in rankings and mode == "auto" and selected == "jev":
            await plan("laya")
            if "laya" in plans:
                await ranking("laya", items)
    selected = next((name for name in asked if name in rankings), None)
    measurements = []
    for name in asked:
        if name not in times:
            continue
        scores = rankings.get(name, {})
        measurements.append({**decision.measurement(name, traces.get(name, []), settings, error=errors.get(name)),
            "latency_ms": round(times[name], 2), "strategy": plans.get(name), "scores": scores,
            "mean_selected_probability": sum(v["selected_probability"] for v in scores.values()) / len(scores) if scores else None,
            "mean_confidence": sum(v["confidence"] for v in scores.values()) / len(scores) if scores else None})
    if selected:
        semantic = sorted(rankings[selected], key=lambda key: -rankings[selected][key]["relevance"])
        # Two semantic votes retain semantic priority without pretending that a
        # provider's probability and a lexical score share a calibrated scale.
        hybrid = reciprocal_fusion([semantic, semantic, lexical_order(query, items), [v["id"] for v in items]])
        items.sort(key=lambda item: -hybrid[item["id"]])
        retrieval["ordering"] = "Reciprocal-rank fusion (k=60): semantic relevance twice, BM25 exact terms and federated index rank once each."
    return {"items": items, "selected_engine": selected, "engines": measurements, "retrieval": retrieval,
            "candidates_sha256": candidates_sha256, "latency_ms": round((perf_counter() - started) * 1000, 2),
            "error": None if selected else "Decision ranking failed. These links retain the search index order.",
            "coverage": f"Up to {retrieval['candidate_limit']} deduplicated HTTPS candidates from the reported indexes, with multilingual semantic judgments and exact-term ranking. "
                "Indexes discover sources beyond a fixed list but do not cover the whole internet. Only query, title and short snippet are evaluated. "
                "Full pages were not fetched; relevance is not factual verification."}
