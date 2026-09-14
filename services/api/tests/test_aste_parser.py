"""Synthetic shapes grounded in the official public HTML/JS, not source licences."""

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest

from helvetic_lens.aste_parser import ORIGIN, listing_url, parse_detail, parse_listing
from helvetic_lens.config import DomainError

NOW = datetime(2026, 9, 14, 2, 0, tzinfo=UTC)
END = datetime(2026, 9, 17, 5, 59, tzinfo=UTC)


def status(**changes):
    return json.dumps({"time": {"server_time": {"timestamp": int(NOW.timestamp())},
        "auction_end_date": {"timestamp": int(END.timestamp()), "date": "2026-09-17 07:59:00",
                            "timezone": {"timezone": "Europe/Zurich"}}},
        "numberBids": 0, "currentPrice": 20, "highestBidPrice": None, "isAuctionActive": True, **changes}).encode()


def detail(**changes):
    values = {"identifier": "185", "start": "20", "title": "Synthetic bicycle",
        "date": "10 set 2026, 08:00:00", "extra": "", "documents": ""}
    values.update(changes)
    return (f'<div id="auction-detail-component" data-auction-id="{values["identifier"]}" data-auction-type="auction" '
        f'data-get-auction-status-url="/it/api/auction/auction-status/{values["identifier"]}" data-currency-symbol="CHF" data-startprice="{values["start"]}">'
        f'<h1 class="auction-detail-main-title">{values["title"]}</h1>'
        '<div class="auction-detail-description-text">Synthetic inspection terms. <script>never execute</script></div>'
        f'<table class="auction-detail-list-table"><tr><td>Data d&#39;inizio:</td><td>{values["date"]}</td></tr></table>'
        f'{values["documents"]}{values["extra"]}</div>').encode()


def listing(*, ids=("185",), following="", active="", grid=True):
    return ('<div id="auction-sorting-container">'
        f'<div data-filter-type="category" data-filter-id="30" {active}>Biciclette</div></div>'
        + ('<div class="auction-grid">' if grid else "<div>")
        + "".join(f'<a class="auction-element-link" href="/it/auction/{identifier}">Synthetic</a>' for identifier in ids)
        + '</div><div class="pagination">'
        + (f'<a rel="next" href="{following}">Next</a>' if following else "") + "</div>").encode()


def test_zero_bid_amount_is_starting_price_not_a_bid_and_exact_source_is_retained():
    html, raw = detail(), status()
    result = parse_detail(html, raw, identifier="185", now=NOW)
    assert result.facts.auction_id == "185" and result.facts.lot_id is None
    assert result.facts.price("current_bid") is None
    assert result.facts.price("starting_price").amount_minor == 2000
    assert result.facts.ends_at == END and result.facts.starts_at.hour == 6
    assert result.facts.status == "open"
    assert result.facts.category is None and result.facts.brand is None and result.facts.asset_location is None
    assert result.facts.documents.state == "unavailable" and not result.document_listing_present
    assert "never execute" not in result.facts.description
    assert result.facts.raw_sha256 == hashlib.sha256(result.raw_bundle).hexdigest()
    assert json.loads(result.raw_bundle)["status_url"].endswith("/auction-status/185")


def test_actual_bid_and_starting_price_remain_distinct_with_exact_cents():
    result = parse_detail(detail(), status(numberBids=7, currentPrice=8500.25, highestBidPrice="CHF&nbsp;8’500.25"),
        identifier="185", now=NOW)
    assert result.facts.price("current_bid").amount_minor == 850025
    assert result.facts.price("starting_price").amount_minor == 2000


@pytest.mark.parametrize("patch", [{"numberBids": None}, {"numberBids": 3, "currentPrice": None}, {"currentPrice": None}])
def test_unknown_bid_inputs_never_become_zero_price(patch):
    result = parse_detail(detail(), status(**patch), identifier="185", now=NOW)
    assert result.facts.price("current_bid") is None


@pytest.mark.parametrize("patch", [{"numberBids": True}, {"numberBids": -1}, {"numberBids": "7"},
    {"numberBids": 1, "currentPrice": 12.345, "highestBidPrice": "CHF 12.34"},
    {"numberBids": 1, "currentPrice": True, "highestBidPrice": "CHF 1.00"},
    {"numberBids": 1, "currentPrice": 100, "highestBidPrice": "CHF 99.00"},
    {"numberBids": 0, "highestBidPrice": "CHF 20.00"}, {"isAuctionActive": "true"}])
def test_ambiguous_status_is_rejected(patch):
    with pytest.raises(DomainError):
        parse_detail(detail(), status(**patch), identifier="185", now=NOW)


def test_duplicate_json_keys_and_stale_or_future_status_fail_closed():
    invalid = status().replace(b'"numberBids": 0', b'"numberBids": 0, "numberBids": 1')
    for raw, now in [(invalid, NOW), (status(), NOW + timedelta(minutes=6)), (status(), NOW - timedelta(minutes=1))]:
        with pytest.raises(DomainError):
            parse_detail(detail(), raw, identifier="185", now=now)


def test_timestamp_zone_or_wall_time_disagreement_is_not_silently_converted():
    for key, value in [("date", "2026-09-17 08:59:00"), ("timezone", {"timezone": "UTC"})]:
        raw = json.loads(status())
        raw["time"]["auction_end_date"][key] = value
        with pytest.raises(DomainError):
            parse_detail(detail(), json.dumps(raw).encode(), identifier="185", now=NOW)


@pytest.mark.parametrize("text", ["29 mar 2026, 02:30:00", "25 ott 2026, 02:30:00", "unknown", "31 feb 2026, 07:00:00"])
def test_missing_or_ambiguous_local_start_time_remains_unknown(text):
    result = parse_detail(detail(date=text), status(), identifier="185", now=NOW)
    assert result.facts.starts_at is None


def test_inactive_is_not_an_invented_cancellation_or_postponement():
    result = parse_detail(detail(), status(isAuctionActive=False), identifier="185", now=NOW)
    assert result.facts.status == "unknown"


def test_listings_preserve_pagination_category_proof_and_empty_is_not_removal():
    result = parse_listing(listing(following="/it/?page=2"), url=ORIGIN + "/it/")
    assert result.identifiers == ("185",) and result.next_url == ORIGIN + "/it/?page=2"
    assert result.categories == (("30", "Biciclette"),)
    result = parse_listing(listing(active="data-active-filter", following="/it/?category%5B%5D=30&page=2"),
        url=listing_url(category="30"))
    assert result.next_url == listing_url(category="30", page=2)
    assert parse_listing(listing(ids=()), url=ORIGIN + "/it/").identifiers == ()


@pytest.mark.parametrize("following", ["/it/?page=1", "/it/?page=3", "/it/preview?page=2",
    "https://evil.invalid/it/?page=2", "/it/?page=2&category[]=30", "/it/?page=2&page=3"])
def test_pagination_cannot_escape_repeat_skip_or_change_category(following):
    with pytest.raises(DomainError):
        parse_listing(listing(following=following), url=ORIGIN + "/it/")


def test_unconfirmed_category_or_markup_drift_is_not_a_successful_empty_scan():
    for raw, url in [(listing(), listing_url(category="30")), (listing(grid=False), listing_url()),
                     (listing(ids=("185", "185")), listing_url()), (b"<h1>Log in</h1>", listing_url())]:
        with pytest.raises(DomainError):
            parse_listing(raw, url=url)


def test_document_references_do_not_claim_downloaded_bytes_or_infer_conditions():
    path = "/uploads/146/" + "a" * 32 + ".pdf"
    documents = f'<div class="pdf-files-container"><a class="auction-detail-media-link" href="{path}?2.35"><span class="document-title">Synthetic sale terms</span></a></div>'
    result = parse_detail(detail(documents=documents), status(), identifier="185", now=NOW)
    assert result.document_listing_present and result.documents[0].official_id == path
    assert result.documents[0].url == ORIGIN + path + "?2.35"
    assert result.facts.documents.state == "unavailable" and result.facts.conditions_sha256 is None
    for bad in [documents.replace(path, "https://evil.invalid/x.pdf"), documents.replace("?2.35", "?token=private")]:
        with pytest.raises(DomainError):
            parse_detail(detail(documents=bad), status(), identifier="185", now=NOW)


def test_identity_and_duplicate_detail_elements_fail_before_journal_admission():
    for html in [detail(identifier="186"), detail(extra='<h1 class="auction-detail-main-title">Second</h1>')]:
        with pytest.raises(DomainError):
            parse_detail(html, status(), identifier="185", now=NOW)
