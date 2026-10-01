"""Small direct official-source adapters, independent of broad web search."""
import hashlib
import json
import re
from datetime import date
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

from .decision_engines import DecisionUnavailable
from .decision_search import lexical_order, plain, public_url
from .document_formats import xml

FEEDS = {
    "ema_news": ("https://www.ema.europa.eu/en/news.xml", "EMA news"),
    "finma_news": ("https://www.finma.ch/en/rss/news/", "FINMA news"),
}


async def get(url, params=None, *, empty_fda=False):
    async with httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False) as client:
        async with client.stream("GET", url, params=params,
                headers={"User-Agent": "HelveticLens/1.0 (+https://helveticlens.ch)"}) as response:
            data = bytearray()
            async for part in response.aiter_bytes():
                data.extend(part)
                if len(data) > 1_000_000:
                    raise DecisionUnavailable("response_too_large")
            if empty_fda and response.status_code == 404:
                error = json.loads(data).get("error", {})
                if error.get("code") == "NOT_FOUND":
                    return b'{"results":[]}'
            if response.status_code != 200:
                raise DecisionUnavailable("quota" if response.status_code == 429 else "unavailable")
            return bytes(data)


def item(url, title, summary, provider, *, date=None, kind="official_metadata"):
    url = public_url(url)
    if not url or not isinstance(title, str) or not title.strip():
        return None
    return {"id": hashlib.sha256(url.encode()).hexdigest()[:32], "url": url,
        "title": plain(title, 240), "summary": plain(summary, 600), "provider": provider, "kind": kind, "date": date}


def result(items, scope, *, examined=None, more=False, next_cursor=None):
    valid = [i for i in items if i]
    return {"items": valid, "scope": scope, "exhaustive": False, "more_available": more,
        "next_cursor": next_cursor,
        "examined_records": len(items) if examined is None else examined,
        "omitted_records": max(0, (len(items) if examined is None else examined) - len(valid))}


async def search(provider, query, cursor=None):
    if provider == "clinicaltrials":
        body = json.loads(await get("https://clinicaltrials.gov/api/v2/studies", {
            "query.term": query, "format": "json", "pageSize": 12,
            "fields": "NCTId,BriefTitle,BriefSummary,OverallStatus,LastUpdatePostDate",
            **({"pageToken": cursor} if cursor else {})}))
        rows = body.get("studies")
        if not isinstance(rows, list) or len(rows) > 12:
            raise DecisionUnavailable("invalid_search_response")
        items = []
        for row in rows:
            protocol = row.get("protocolSection", {})
            identity = protocol.get("identificationModule", {})
            nct = identity.get("nctId", "")
            if not re.fullmatch(r"NCT\d{8}", nct):
                continue
            status = protocol.get("statusModule", {})
            items.append(item("https://clinicaltrials.gov/api/v2/studies/" + nct, identity.get("briefTitle"),
                protocol.get("descriptionModule", {}).get("briefSummary", ""), "ClinicalTrials.gov",
                date=status.get("lastUpdatePostDateStruct", {}).get("date"), kind="trial_registry"))
        return result(items, "One page of matching ClinicalTrials.gov registry records; registrations are not verified findings.",
            examined=len(rows), more=bool(body.get("nextPageToken")), next_cursor=body.get("nextPageToken"))
    if provider == "fda_labels":
        # Escape the public question as a phrase; do not interpret caller syntax.
        phrase = json.dumps(query, ensure_ascii=False)
        terms = " OR ".join(field + ":" + phrase for field in
            ("openfda.brand_name", "openfda.generic_name", "indications_and_usage", "warnings"))
        offset = int(cursor or 0)
        if offset < 0 or offset > 25000:
            raise DecisionUnavailable("provider_pagination_limit")
        body = json.loads(await get("https://api.fda.gov/drug/label.json", {"search": terms, "limit": 12, "skip": offset}, empty_fda=True))
        rows = body.get("results")
        if not isinstance(rows, list) or len(rows) > 12:
            raise DecisionUnavailable("invalid_search_response")
        items = []
        for row in rows:
            identifier = row.get("id", "")
            if not re.fullmatch(r"[a-fA-F0-9-]{36}", identifier):
                continue
            fda = row.get("openfda", {})
            names = fda.get("brand_name") or fda.get("generic_name") or ["Drug label " + identifier]
            summaries = row.get("indications_and_usage") or []
            url = "https://api.fda.gov/drug/label.json?" + urlencode({"search": "id:" + json.dumps(identifier), "limit": 1})
            items.append(item(url, " / ".join(names), " ".join(summaries), "openFDA drug labels",
                date=row.get("effective_time")))
        more = body.get("meta", {}).get("results", {}).get("total", 0) > offset + len(rows)
        return result(items, "One page of openFDA label records. Label text is not proof of regulatory approval; the provider's paging limit still applies.",
            examined=len(rows), more=more, next_cursor=str(offset + len(rows)) if more and rows and offset + len(rows) <= 25000 else None)
    if provider in FEEDS:
        url, name = FEEDS[provider]
        root = xml(await get(url))
        if root.tag.split("}")[-1] != "rss":
            raise DecisionUnavailable("invalid_feed_response")
        rows = root.findall("./channel/item")
        items = [item(row.findtext("link", ""), row.findtext("title"), row.findtext("description", ""),
            name, date=row.findtext("pubDate")) for row in rows[:200]]
        candidates = [i for i in items if i]
        order = lexical_order(query, candidates)
        by_id = {i["id"]: i for i in candidates}
        offset = int(cursor or 0)
        return result([by_id[key] for key in order[offset:offset + 12]],
            "Up to 12 text-ranked entries from the current official feed; not an archive search. Candidate relevance is still assessed.",
            examined=min(len(rows), 200), more=len(order) > offset + 12,
            next_cursor=str(offset + 12) if len(order) > offset + 12 else None)
    if provider == "federal_court":
        from urllib.robotparser import RobotFileParser

        from .decision_sources import read_bytes
        from .federal_court_connector import COURT_INDEX, COURT_ROBOTS, _date_rows, _date_url, _latest_dates

        async with httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False,
                headers={"User-Agent": "HelveticLens/1.0 (+https://helveticlens.ch)"}) as client:
            code, _, body = await read_bytes(client, COURT_ROBOTS, 65536)
            rules = RobotFileParser()
            if code == 200:
                rules.parse(body.decode("utf-8", errors="replace").splitlines())
            elif code in (404, 410):
                rules.parse([])
            else:
                raise DecisionUnavailable("robots_unavailable")
            async def page(url):
                if not rules.can_fetch("HelveticLens", url):
                    raise DecisionUnavailable("robots_disallowed")
                code, _, body = await read_bytes(client, url, 1_000_000)
                if code != 200:
                    raise DecisionUnavailable("unavailable")
                return BeautifulSoup(body, "html.parser")
            dates = _latest_dates(await page(COURT_INDEX))
            if not dates:
                raise DecisionUnavailable("invalid_search_response")
            day, offset = (date.fromisoformat(cursor.split(":")[0]), int(cursor.split(":")[1])) if cursor else (dates[0], 0)
            if day not in dates or offset < 0:
                raise DecisionUnavailable("archive_cursor_unavailable")
            date_index = dates.index(day)
            url = _date_url(day)
            rows = _date_rows(await page(url), day, url)
        candidates = [item(r["canonical_url"], r["docket"] + " — " + r["subject"], r["area"],
            "Swiss Federal Supreme Court", date=r["decision_date"]) for r in rows[:200]]
        by_id = {i["id"]: i for i in candidates if i}
        order = lexical_order(query, list(by_id.values()))
        following = f"{day.isoformat()}:{offset + 12}" if len(order) > offset + 12 else f"{dates[date_index + 1].isoformat()}:0" if date_index + 1 < len(dates) else None
        return result([by_id[key] for key in order[offset:offset + 12]],
            "One page of one publication day from the accessible official court index. Earlier indexed days can be followed; this is not the complete historical case-law archive.",
            examined=min(len(rows), 200), more=bool(following), next_cursor=following)
    raise DecisionUnavailable("unknown_source_adapter")
