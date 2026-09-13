import copy
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from uuid import uuid4

import httpx
import pytest

from helvetic_lens import simap_sources as simap

PROJECT = str(uuid4())
PUBLICATION = str(uuid4())
NOW = datetime(2026, 9, 12, 6, tzinfo=UTC)


def search_row(**extra):
    return {
        "id": PROJECT,
        "publicationId": PUBLICATION,
        "publicationDate": "2026-09-12",
        "pubType": "tender",
        "lots": [],
        **extra,
    }


def page(*rows, last_item=""):
    return {"projects": list(rows), "pagination": {"lastItem": last_item, "itemsPerPage": 20}}


def detail():
    return {
        "id": PUBLICATION,
        "type": "tender",
        "hasProjectDocuments": True,
        "base": {
            "id": PUBLICATION,
            "projectId": PROJECT,
            "type": "tender",
            "publicationDate": "2026-09-12",
            "initialPublicationDate": "2026-08-06",
            "correctedPubId": str(uuid4()),
        },
        "dates": {"publicationDate": "2026-09-12", "offerDeadline": "2026-10-16T15:00:00+02:00"},
        "project-info": {"title": {"de": "Original", "fr": "Texte original", "en": None, "it": None}},
        "terms": {"termsNote": {"de": "<p>Official unchanged text</p>"}},
    }


def parse(raw, **kwargs):
    return simap.parse_publication(
        raw, project_id=PROJECT, publication_id=PUBLICATION, now=kwargs.get("now", NOW)
    )


def test_distribution_gate_uses_publication_day_zurich_offset_at_the_date():
    assert simap.publication_gate("2026-03-29") == datetime(2026, 3, 29, 6, tzinfo=UTC)
    assert simap.publication_gate("2026-10-25") == datetime(2026, 10, 25, 7, tzinfo=UTC)
    assert simap.publication_gate("2026-09-12") == NOW
    raw = detail()
    with pytest.raises(simap.PublicationEmbargo) as embargo:
        parse(raw, now=NOW - timedelta(microseconds=1))
    assert embargo.value.until == NOW
    assert parse(raw)["publication_id"] == PUBLICATION


def test_correction_is_not_released_using_earlier_initial_publication_date():
    raw = detail()
    with pytest.raises(simap.PublicationEmbargo):
        parse(raw, now=datetime(2026, 9, 11, 18, tzinfo=UTC))
    parsed = parse(raw)
    assert parsed["corrected_publication_id"] == raw["base"]["correctedPubId"]
    assert parsed["project_id"] == PROJECT


def test_withheld_page_preserves_continuation_and_reschedule_time():
    row = search_row()
    result = simap.parse_search_page(page(row, last_item="20260912|42058"), now=NOW - timedelta(seconds=1))
    assert result.publications == ()
    assert result.next_cursor == "20260912|42058"
    assert result.withheld_until == NOW
    visible = simap.parse_search_page(page(row, last_item="20260912|42058"), now=NOW)
    assert len(visible.publications) == 1
    assert visible.withheld_until is None


def test_future_lot_is_not_leaked_inside_an_older_project():
    row = search_row(
        lots=[
            {
                "lotId": str(uuid4()),
                "publicationId": str(uuid4()),
                "publicationDate": "2026-09-13",
            }
        ]
    )
    result = simap.parse_search_page(page(row), now=NOW)
    assert not result.publications
    assert result.withheld_until == datetime(2026, 9, 13, 6, tzinfo=UTC)


def test_identical_duplicates_are_deduplicated_and_conflicts_are_not_silently_overwritten():
    row = search_row()
    assert len(simap.parse_search_page(page(row, row), now=NOW).publications) == 1
    conflict = {**row, "publicationId": str(uuid4())}
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        simap.parse_search_page(page(row, conflict), now=NOW)


def test_official_empty_cursor_terminates_but_repeated_nonempty_cursor_fails():
    result = simap.parse_search_page(page(), now=NOW)
    assert result.next_cursor is None and not result.publications
    with pytest.raises(ValueError, match="repeated"):
        simap.parse_search_page(
            page(search_row(), last_item="20260912|42058"), now=NOW, previous_cursor="20260912|42058"
        )
    with pytest.raises(ValueError, match="Invalid source search cursor"):
        simap.parse_search_page(page(last_item=None), now=NOW)


def test_source_original_is_preserved_and_documents_and_qa_are_not_claimed_accessible():
    raw = detail()
    saved = copy.deepcopy(raw)
    parsed = parse(raw)
    assert raw == saved == parsed["original"]
    assert parsed["document_coverage"] == "requires_authorized_access"
    assert parsed["qa_coverage"] == "not_verified"
    assert parsed["offer_deadline"]["utc"] == "2026-10-16T13:00:00+00:00"
    assert parsed["offer_deadline"]["source_locator"] == "/dates/offerDeadline"
    raw["terms"].clear()
    assert parsed["original"]["terms"] == saved["terms"]
    assert len(parsed["evidence_sha256"]) == 64


@pytest.mark.parametrize("value", ["2026-10-25T02:30:00", "2026-03-29T02:30:00", "2026-09-12", "unbekannt"])
def test_ambiguous_or_invalid_deadline_keeps_original_but_never_invents_an_instant(value):
    raw = detail()
    raw["dates"]["offerDeadline"] = value
    parsed = parse(raw)["offer_deadline"]
    assert parsed["source_value"] == value
    assert parsed["utc"] is None
    assert parsed["status"] == "invalid_or_ambiguous"


def test_explicit_dst_fold_offsets_and_utc_are_respected_without_using_todays_offset():
    first = simap.deadline("2026-10-25T02:30:00+02:00")
    second = simap.deadline("2026-10-25T02:30:00+01:00")
    assert second - first == timedelta(hours=1)
    assert simap.deadline("2026-10-25T00:30:00Z") == first
    assert simap.deadline("2026-11-25T15:00:00") == datetime(2026, 11, 25, 14, tzinfo=UTC)


def test_missing_deadline_does_not_borrow_offer_opening_or_publication_date():
    raw = detail()
    raw["dates"] = {"offerOpening": {"dateTime": "2026-10-19T00:00:00+02:00", "ignoreTime": True}}
    assert parse(raw)["offer_deadline"]["status"] == "not_provided"


def test_wrong_dossier_version_or_conflicting_publication_date_is_rejected():
    raw = detail()
    raw["base"]["projectId"] = str(uuid4())
    with pytest.raises(ValueError, match="identity"):
        parse(raw)
    raw = detail()
    raw["dates"]["publicationDate"] = "2026-08-06"
    with pytest.raises(ValueError, match="Conflicting publication dates"):
        parse(raw)


def mock_client(monkeypatch, handler):
    original = httpx.Client

    def factory(**kwargs):
        assert kwargs["follow_redirects"] is False and kwargs["trust_env"] is False
        return original(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(simap.httpx, "Client", factory)


def test_public_client_only_reads_official_routes_and_never_adds_auth(monkeypatch):
    seen = []

    def serve(request):
        seen.append(request)
        assert request.method == "GET" and request.url.host == "www.simap.ch"
        assert "authorization" not in request.headers and "cookie" not in request.headers
        return httpx.Response(200, json=page())

    mock_client(monkeypatch, serve)
    client = simap.PublicClient()
    client.search("software", last_item="20260912|42058")
    client.publication(PROJECT, PUBLICATION)
    assert seen[0].url.params["lastItem"] == "20260912|42058"
    assert seen[1].url.path.endswith(f"/{PROJECT}/publication-details/{PUBLICATION}")
    with pytest.raises(ValueError):
        client.publication("../private", PUBLICATION)
    with pytest.raises(ValueError, match="empty cursor"):
        client.search("software", last_item="")
    assert len(seen) == 2


@pytest.mark.parametrize(
    "status,reason",
    [
        (401, "access_required"),
        (403, "access_denied"),
        (404, "not_available"),
        (429, "rate_limited"),
        (302, "source_error"),
    ],
)
def test_access_errors_and_redirects_do_not_become_an_empty_successful_listing(monkeypatch, status, reason):
    mock_client(
        monkeypatch,
        lambda request: httpx.Response(
            status, headers={"Location": "https://unapproved.example/file", "Retry-After": "172800"}
        ),
    )
    with pytest.raises(simap.SourceUnavailable) as failure:
        simap.PublicClient().search("software")
    assert failure.value.reason == reason
    assert failure.value.retry_after_seconds == 172800


def test_retry_after_http_date_is_respected_and_response_body_is_bounded(monkeypatch):
    future = format_datetime(datetime.now(UTC) + timedelta(hours=1), usegmt=True)
    responses = [httpx.Response(429, headers={"Retry-After": future}), httpx.Response(200, content=b"x" * 40)]
    mock_client(monkeypatch, lambda request: responses.pop(0))
    with pytest.raises(simap.SourceUnavailable) as limited:
        simap.PublicClient().search("software")
    assert 3590 <= limited.value.retry_after_seconds <= 3600
    monkeypatch.setattr(simap, "MAX_BYTES", 16)
    with pytest.raises(simap.SourceUnavailable, match="response_too_large"):
        simap.PublicClient().search("software")


def test_nonfinite_json_and_malformed_lot_are_not_accepted_as_source_evidence(monkeypatch):
    mock_client(monkeypatch, lambda request: httpx.Response(200, content=b'{"amount": NaN}'))
    with pytest.raises(simap.SourceUnavailable, match="invalid_json_number"):
        simap.PublicClient().search("software")
    with pytest.raises(ValueError, match="Invalid lot record"):
        simap.parse_search_page(page(search_row(lots=["unexpected"])), now=NOW)


def header_publication(publication_id=PUBLICATION, *, day="2026-09-12"):
    return {
        "id": publication_id,
        "pubType": "tender",
        "dates": {"publicationDate": day},
        "hasProjectDocuments": True,
    }


def test_project_header_deduplicates_shared_publication_without_using_vendor_actions():
    first, second = str(uuid4()), str(uuid4())
    raw = {
        "id": PROJECT,
        "lotsType": "with",
        "lots": [
            {"id": first, "latestPublication": header_publication()},
            {
                "id": second,
                "latestPublication": header_publication(),
                "latestVendorDigitalSubmission": {"id": "PRIVATE"},
            },
        ],
        "actions": {"submit": "NOT AN INSTRUCTION"},
        "vendorStatus": "invited",
    }
    parsed = simap.parse_project_header(raw, project_id=PROJECT, now=NOW)
    assert len(parsed.publications) == 1 and parsed.publications[0]["lot_ids"] == sorted([first, second])
    assert "PRIVATE" not in str(parsed) and "actions" not in str(parsed)


def test_project_header_returns_other_public_lots_and_reschedules_future_publications():
    old_id, future_id = str(uuid4()), str(uuid4())
    raw = {
        "id": PROJECT,
        "lotsType": "with",
        "lots": [
            {"id": str(uuid4()), "latestPublication": header_publication(old_id)},
            {"id": str(uuid4()), "latestPublication": header_publication(future_id, day="2026-09-13")},
        ],
    }
    result = simap.parse_project_header(raw, project_id=PROJECT, now=NOW)
    assert [p["publication_id"] for p in result.publications] == [old_id]
    assert result.withheld_until == NOW + timedelta(days=1)
    raw["lots"][1]["latestPublication"]["id"] = old_id
    with pytest.raises(ValueError, match="Conflicting publication references"):
        simap.parse_project_header(raw, project_id=PROJECT, now=NOW)


def test_project_without_lots_and_historical_lot_display_numbers_do_not_invent_lot_identity():
    header = {"id": PROJECT, "lotsType": "without", "latestPublication": header_publication()}
    assert simap.parse_project_header(header, project_id=PROJECT, now=NOW).publications[0]["lot_ids"] == []
    entry = {"id": PUBLICATION, "pubType": "tender", "publicationDate": "2026-09-12", "lotNumber": 3}
    result = simap.parse_publication_history(
        {"pastPublications": [entry, entry]}, project_id=PROJECT, now=NOW
    )
    assert len(result.publications) == 1 and result.publications[0]["lot_ids"] == []
    assert (
        simap.parse_publication_history({"pastPublications": []}, project_id=PROJECT, now=NOW).publications
        == ()
    )


@pytest.mark.parametrize(
    "raw",
    [
        {"id": PROJECT, "lotsType": "with", "lots": []},
        {"id": PROJECT, "lotsType": "without", "latestPublication": {}},
        {"id": str(uuid4()), "lotsType": "without", "latestPublication": header_publication()},
        {"id": PROJECT, "lotsType": "new_unknown_type"},
    ],
)
def test_missing_or_wrong_project_header_fails_without_marking_followed_tender_closed(raw):
    with pytest.raises(ValueError):
        simap.parse_project_header(raw, project_id=PROJECT, now=NOW)


def test_extended_official_client_uses_read_only_public_header_history_and_cpv_filters(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request)
        assert request.method == "GET" and "authorization" not in request.headers
        return httpx.Response(200, json={})

    mock_client(monkeypatch, handler)
    client = simap.PublicClient()
    client.search(cpv_codes=["72000000", "72200000"])
    client.project_header(PROJECT)
    lot = str(uuid4())
    client.publication_history(PUBLICATION, lot_id=lot)
    assert seen[0].url.params.get_list("cpvCodes") == ["72000000", "72200000"]
    assert "search" not in seen[0].url.params
    assert seen[1].url.path == f"/api/publications/v2/project/{PROJECT}/project-header"
    assert seen[2].url.path == f"/api/publications/v1/publication/{PUBLICATION}/past-publications"
    assert seen[2].url.params["lotId"] == lot
    with pytest.raises(ValueError):
        client.search()
    with pytest.raises(ValueError):
        client.search(cpv_codes=["../private"])
    with pytest.raises(ValueError):
        client.project_header("../private")
    assert len(seen) == 3
