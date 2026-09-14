"""Bounded read-only decoding of the observed Aste UEF public representation.

This module neither performs HTTP nor grants source access. A collector must
retain the exact response bundle, validate permissions and establish discovery
provenance before admitting facts to the auction journal.
"""

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from html import unescape
from urllib.parse import parse_qsl, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from .auction_contracts import AuctionFacts, Documents, Price, clock
from .config import DomainError

ORIGIN = "https://www.aste.ti.ch"
SOURCE_KEY = "aste-ti"
ZONE = ZoneInfo("Europe/Zurich")
MAX_BYTES = 1024 * 1024
MAX_ITEMS = 500
MONTHS = {name: i + 1 for i, name in enumerate(("gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"))}


def _fail(code="aste_format_changed"):
    raise DomainError("Official auction evidence could not be verified.", 503, code)


def _html(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        _fail("aste_response_size")
    try:
        soup = BeautifulSoup(raw.decode("utf-8", errors="strict"), "html.parser")
    except (UnicodeError, ValueError):
        _fail()
    for tag in soup.select("script, style, template"):
        tag.decompose()
    return soup


def _one(soup, selector, *, optional=False):
    nodes = soup.select(selector)
    if len(nodes) > 1 or not nodes and not optional:
        _fail()
    return nodes[0] if nodes else None


def _text(node):
    return node.get_text(" ", strip=True) if node else ""


def _integer(value, *, maximum=10**9):
    if type(value) is not int or not 0 <= value <= maximum:
        _fail()
    return value


def _money(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        _fail()
    try:
        amount = Decimal(value)
    except InvalidOperation:
        _fail()
    cents = amount * 100
    if not amount.is_finite() or not 0 <= cents <= 10**15 or cents != cents.to_integral_value():
        _fail()
    return int(cents)


def _displayed_bid(value):
    if not isinstance(value, str):
        _fail("aste_price_inconsistent")
    match = re.fullmatch(r"CHF\s+([0-9]+(?:['’][0-9]{3})*\.[0-9]{2})", unescape(value))
    if not match:
        _fail("aste_price_inconsistent")
    return _money(match[1].replace("'", "").replace("’", ""))


def listing_url(*, upcoming=False, page=1, category=None):
    if type(page) is not int or not 1 <= page <= 5000 or category is not None and not re.fullmatch(r"[1-9][0-9]{0,8}", category):
        _fail("aste_listing_url_invalid")
    query = []
    if category is not None:
        query.append("category%5B%5D=" + category)
    if page != 1:
        query.append("page=" + str(page))
    return ORIGIN + ("/it/preview" if upcoming else "/it/") + ("?" + "&".join(query) if query else "")


def _listing_parts(url):
    try:
        parsed = urlsplit(url if url.startswith("https://") else ORIGIN + url)
        if (parsed.scheme != "https" or parsed.netloc != "www.aste.ti.ch" or parsed.fragment
                or parsed.path not in ("/it/", "/it/preview") or any(ord(c) < 33 or c == "\\" for c in url)):
            _fail("aste_listing_url_invalid")
        values = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
        if len(dict(values)) != len(values) or any(k not in ("page", "category[]") for k, _ in values):
            _fail("aste_listing_url_invalid")
        query = dict(values)
        number = query.get("page", "1")
        if not re.fullmatch(r"[1-9][0-9]{0,3}", number):
            _fail("aste_listing_url_invalid")
        result = {"upcoming": parsed.path == "/it/preview", "page": int(number), "category": query.get("category[]")}
        listing_url(**result)
        return result
    except (ValueError, TypeError):
        _fail("aste_listing_url_invalid")


def detail_url(identifier):
    if not isinstance(identifier, str) or not re.fullmatch(r"[1-9][0-9]{0,8}", identifier):
        _fail("aste_identity_invalid")
    return ORIGIN + "/it/auction/" + identifier


def status_url(identifier):
    return detail_url(identifier).replace("/it/auction/", "/it/api/auction/auction-status/")


@dataclass(frozen=True)
class Listing:
    identifiers: tuple[str, ...]
    next_url: str | None
    categories: tuple[tuple[str, str], ...]
    sha256: str


def parse_listing(raw, *, url):
    expected = _listing_parts(url)
    soup = _html(raw)
    _one(soup, ".auction-grid")
    categories = []
    for tag in soup.select('#auction-sorting-container [data-filter-type="category"]'):
        identifier, label = tag.get("data-filter-id", ""), _text(tag)
        if not re.fullmatch(r"[1-9][0-9]{0,8}", identifier) or not label or len(label) > 200:
            _fail()
        categories.append((identifier, label))
    if len(categories) > 100 or len({key for key, _ in categories}) != len(categories):
        _fail()
    active = [tag.get("data-filter-id") for tag in soup.select('#auction-sorting-container [data-filter-type="category"][data-active-filter]')]
    if active != ([expected["category"]] if expected["category"] else []):
        _fail("aste_category_filter_unconfirmed")
    identifiers = []
    for tag in soup.select(".auction-grid a.auction-element-link"):
        href = tag.get("href", "")
        match = re.fullmatch(r"/it/auction/([1-9][0-9]{0,8})", href)
        if not match:
            _fail("aste_identity_invalid")
        identifiers.append(match[1])
    if len(identifiers) > MAX_ITEMS or len(set(identifiers)) != len(identifiers):
        _fail("aste_listing_inconsistent")
    next_link = _one(soup, ".pagination a[rel~=next]", optional=True)
    next_url = None
    if next_link:
        following = _listing_parts(next_link.get("href", ""))
        if (following["upcoming"] != expected["upcoming"] or following["category"] != expected["category"]
                or following["page"] != expected["page"] + 1 or not identifiers):
            _fail("aste_listing_inconsistent")
        next_url = listing_url(**following)
    # No discovery page can assert removal, even when its visible grid is empty.
    return Listing(tuple(identifiers), next_url, tuple(categories), hashlib.sha256(raw).hexdigest())


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            _fail()
        result[key] = value
    return result


def _status(raw, *, now, max_age_seconds):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        _fail("aste_response_size")
    try:
        result = json.loads(raw, parse_float=Decimal, object_pairs_hook=_pairs,
            parse_constant=lambda _: _fail())
        time = result["time"]
        timestamp = _integer(time["server_time"]["timestamp"], maximum=253402300799)
        observed = datetime.fromtimestamp(timestamp, UTC)
        if not -timedelta(seconds=30) <= now - observed <= timedelta(seconds=max_age_seconds):
            _fail("aste_status_stale")
        end = time.get("auction_end_date")
        ends_at = None
        if end is not None:
            timestamp = _integer(end["timestamp"], maximum=253402300799)
            ends_at = datetime.fromtimestamp(timestamp, UTC)
            if (end["timezone"]["timezone"] != "Europe/Zurich"
                    or ends_at.astimezone(ZONE).strftime("%Y-%m-%d %H:%M:%S") != end["date"]):
                _fail("aste_timestamp_inconsistent")
        active = result["isAuctionActive"]
        if type(active) is not bool:
            _fail()
        count = result.get("numberBids")
        if count is not None:
            _integer(count)
        return result, ends_at, count, active
    except (ValueError, TypeError, KeyError, OverflowError, OSError):
        _fail()


def _local_date(text):
    match = re.fullmatch(r"(\d{1,2}) ([a-z]{3}) (\d{4}), (\d{2}):(\d{2}):(\d{2})", text)
    if not match or match[2] not in MONTHS:
        return None
    try:
        day, _, year, hour, minute, second = match.groups()
        naive = datetime(int(year), MONTHS[match[2]], int(day), int(hour), int(minute), int(second))
        candidates = {naive.replace(tzinfo=ZONE, fold=fold).astimezone(UTC) for fold in (0, 1)}
        candidates = {value for value in candidates if value.astimezone(ZONE).replace(tzinfo=None) == naive}
        return next(iter(candidates)) if len(candidates) == 1 else None
    except ValueError:
        return None


@dataclass(frozen=True)
class DocumentLink:
    official_id: str
    url: str
    title: str


@dataclass(frozen=True)
class Detail:
    facts: AuctionFacts
    documents: tuple[DocumentLink, ...]
    document_listing_present: bool
    raw_bundle: bytes


def parse_detail(html, status, *, identifier, now, max_age_seconds=300):
    """Decode one observed auction; category/location/brand remain unguessed.

    PDF links are discovery references, not assertions that their bytes were
    retrieved. A later admitted record must incorporate verified document hashes
    and permitted category-discovery evidence into its retained raw bundle.
    """
    now = clock(now)
    source_url = detail_url(identifier)
    soup = _html(html)
    component = _one(soup, "#auction-detail-component")
    if (component.get("data-auction-id") != identifier or component.get("data-auction-type") != "auction"
            or component.get("data-get-auction-status-url") != "/it/api/auction/auction-status/" + identifier):
        _fail("aste_identity_invalid")
    if component.get("data-currency-symbol") != "CHF":
        _fail("aste_currency_unsupported")
    title = _text(_one(component, "h1.auction-detail-main-title"))
    description = _text(_one(component, ".auction-detail-description-text", optional=True)) or None
    data, ends_at, bid_count, active = _status(status, now=now, max_age_seconds=max_age_seconds)
    prices = []
    start = component.get("data-startprice")
    if start not in (None, ""):
        prices.append(Price(kind="starting_price", currency="CHF", amount_minor=_money(start),
            locator="#auction-detail-component/@data-startprice"))
    if (bid_count is not None and bid_count > 0 and data.get("currentPrice") is not None
            and data.get("highestBidPrice") is not None):
        # JS updateAuctionDetailDataset uses currentPrice; a numeric amount is
        # only a current bid when the same status response confirms actual bids.
        current = _money(data["currentPrice"])
        if current != _displayed_bid(data["highestBidPrice"]):
            _fail("aste_price_inconsistent")
        prices.append(Price(kind="current_bid", currency="CHF", amount_minor=current,
            locator="auction-status.currentPrice; numberBids>0"))
    if bid_count == 0 and data.get("highestBidPrice") is not None:
        _fail("aste_price_inconsistent")
    starts_at = None
    start_rows = []
    for row in component.select(".auction-detail-list-table tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) == 2 and _text(cells[0]) == "Data d'inizio:":
            start_rows.append(cells[1])
    if len(start_rows) > 1:
        _fail()
    if start_rows:
        starts_at = _local_date(_text(start_rows[0]))
    state = "unknown"
    if active and ends_at and now < ends_at and (starts_at is None or starts_at <= now):
        state = "open"
    # Inactive alone does not distinguish cancellation, postponement or closure.
    container = _one(component, ".pdf-files-container", optional=True)
    documents = []
    if container:
        for link in container.select("a.auction-detail-media-link"):
            match = re.fullmatch(r"(/uploads/[1-9][0-9]{0,8}/[a-f0-9]{32}\.pdf)(?:\?[0-9]+(?:\.[0-9]+)*)?", link.get("href", ""))
            if not match:
                _fail("aste_document_url_invalid")
            title_node = _one(link, ".document-title")
            documents.append(DocumentLink(match[1], ORIGIN + link["href"], _text(title_node)))
        if len(documents) > 100 or len({item.official_id for item in documents}) != len(documents):
            _fail("aste_document_listing_inconsistent")
    raw_bundle = json.dumps({"schema": "aste-public-bundle-v1", "detail_url": source_url,
        "detail_base64": base64.b64encode(html).decode(), "status_url": status_url(identifier),
        "status_base64": base64.b64encode(status).decode()}, separators=(",", ":"), sort_keys=True).encode()
    if len(raw_bundle) > 2 * 1024 * 1024:
        _fail("aste_response_size")
    facts = AuctionFacts(source_key=SOURCE_KEY, canton="TI", auction_id=identifier, lot_id=None,
        authority="Aste UEF · Cantone Ticino", title=title, description=description,
        prices=tuple(prices), bid_count=bid_count, starts_at=starts_at, ends_at=ends_at, status=state,
        documents=Documents(state="unavailable"), source_url=source_url,
        raw_sha256=hashlib.sha256(raw_bundle).hexdigest(), observed_at=now)
    return Detail(facts, tuple(documents), container is not None, raw_bundle)
