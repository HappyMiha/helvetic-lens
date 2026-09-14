"""Synthetic Swiss protocol examples, never evidence of live warning coverage."""

from datetime import UTC, datetime
from xml.sax.saxutils import escape

import httpx
import pytest

from helvetic_lens import hazard_meteoalarm as source
from helvetic_lens.hazard_cap import HazardCAPError

NOW = datetime(2026, 9, 14, 8, 30, tzinfo=UTC)
SENT = "2026-09-14T08:00:00+00:00"
ID = source.ISSUER_PREFIX + "synthetic-fixture-1"
URL = source.CAP_BASE + "11111111-1111-4111-8111-111111111111"


def entry(*, index=0, url=URL, identifier=ID):
    return f"""<entry><id>{escape(url)}?index_info={index}</id>
    <published>{SENT}</published><updated>{SENT}</updated>
    <cap:identifier>{identifier}</cap:identifier><cap:sent>{SENT}</cap:sent>
    <cap:status>Actual</cap:status><cap:scope>Public</cap:scope><cap:message_type>Alert</cap:message_type>
    <link type="application/cap+xml" href="{escape(url)}"/></entry>"""


def feed(entries=""):
    return f"""<feed xmlns="{source.ATOM}" xmlns:cap="{source.CAP}">
    <id>{source.FEED_ID}</id><updated>2026-09-14T08:05:00Z</updated>
    <link type="application/atom+xml" rel="self" href="{source.FEED_URL}"/>{entries}</feed>""".encode()


def cap(identifier=ID):
    # This fixture proves transport binding only; full publication must still
    # reject its deliberately incomplete information/geometry contract.
    return f"""<alert xmlns="{source.CAP}"><identifier>{identifier}</identifier>
    <sender>synthetic@example.invalid</sender><sent>{SENT}</sent>
    <status>Actual</status><scope>Public</scope><msgType>Alert</msgType></alert>""".encode()


def response(payload, mime, status=200, **headers):
    return httpx.Response(status, headers={"Content-Type": mime, **headers}, stream=httpx.ByteStream(payload))


def test_empty_feed_is_a_complete_transport_snapshot_without_any_all_clear_claim():
    with httpx.Client(transport=httpx.MockTransport(lambda request: response(feed(), "application/atom+xml"))) as client:
        snapshot = source.download(now=lambda: NOW, client=client)
    assert snapshot.feed.warnings == snapshot.originals == ()
    assert snapshot.completed_at == NOW
    assert snapshot.feed.updated < snapshot.completed_at


def test_area_and_language_summaries_share_one_immutable_original_and_no_private_headers():
    requests = []
    original = cap()

    def handler(request):
        requests.append(request)
        assert "*/*;q=0.1" in request.headers["Accept"]  # Actual Atom route otherwise returns 406.
        if str(request.url) == source.FEED_URL:
            return response(feed(entry() + entry(index=1)), "application/atom+xml; charset=utf-8")
        assert str(request.url) == URL
        return response(original, "application/cap+xml")

    with httpx.Client(transport=httpx.MockTransport(handler), headers={"Authorization": "private-fixture"},
                      cookies={"private": "fixture"}, params={"home": "private-fixture"}) as client:
        snapshot = source.download(now=lambda: NOW, client=client)
    assert len(requests) == 2
    assert len(snapshot.originals) == 1
    assert snapshot.originals[0].payload == original
    assert all("authorization" not in request.headers and "cookie" not in request.headers
               and not request.url.query and request.method == "GET" for request in requests)


@pytest.mark.parametrize("url", [
    "https://example.invalid/warning", URL + "?index_info=0", URL + "#fragment",
    source.CAP_BASE + "../private", URL.replace("feeds-switzerland", "feeds-austria"),
    URL.replace("https:", "http:"), URL.replace("feeds.meteoalarm.org", "feeds.meteoalarm.org.evil.invalid"),
])
def test_only_direct_swiss_original_resources_may_be_fetched(url):
    with pytest.raises(source.MeteoAlarmError, match="meteoalarm_untrusted_cap_url"):
        source.parse_feed(feed(entry(url=url)), now=NOW)


@pytest.mark.parametrize(("before", "after", "code"), [
    (source.FEED_ID, "tag:meteoalarm.org,2021-02-19:AT", "meteoalarm_wrong_feed"),
    ("2026-09-14T08:05:00Z", "2026-09-14T09:05:00Z", "meteoalarm_future_feed"),
    ("<cap:status>Actual", "<cap:status>Exercise", "meteoalarm_nonpublic_warning"),
    ("<cap:scope>Public", "<cap:scope>Private", "meteoalarm_nonpublic_warning"),
    (ID, "2.49.0.0.40.0.foreign", "meteoalarm_wrong_issuer"),
    ("<cap:message_type>Alert", "<cap:message_type>Cancel", "meteoalarm_unexpected_message_type"),
    ("<published>" + SENT, "<published>2026-09-14T07:00:00+00:00", "meteoalarm_entry_time_conflict"),
])
def test_wrong_issuer_scope_or_inconsistent_summary_invalidates_whole_feed(before, after, code):
    with pytest.raises(source.MeteoAlarmError, match=code):
        source.parse_feed(feed(entry()).replace(before.encode(), after.encode()), now=NOW)


def test_conflicting_summaries_and_entity_expansion_cannot_be_accepted():
    with pytest.raises(source.MeteoAlarmError, match="meteoalarm_conflicting_cap_summary"):
        source.parse_feed(feed(entry() + entry(index=1, identifier=ID + "changed")), now=NOW)
    with pytest.raises(source.MeteoAlarmError, match="meteoalarm_duplicate_entry"):
        source.parse_feed(feed(entry() + entry()), now=NOW)
    with pytest.raises(HazardCAPError, match="hazard_forbidden_xml"):
        source.parse_feed(b'<!DOCTYPE feed [<!ENTITY secret SYSTEM "file:///private">]>' + feed(), now=NOW)
    with pytest.raises(source.MeteoAlarmError, match="meteoalarm_feed_structure_changed"):
        source.parse_feed(feed(entry().replace("<entry>", '<entry xmlns="urn:changed-contract">')), now=NOW)


@pytest.mark.parametrize("failure", ["redirect", "missing", "rate", "html", "identity", "oversize"])
def test_partial_original_failure_never_returns_an_empty_or_completed_snapshot(failure):
    requests = []

    def handler(request):
        requests.append(request)
        if str(request.url) == source.FEED_URL:
            return response(feed(entry()), "application/atom+xml")
        if failure == "redirect":
            return response(b"", "application/cap+xml", 302, Location="https://example.invalid/private")
        if failure == "missing":
            return response(b"", "application/cap+xml", 404)
        if failure == "rate":
            return response(b"", "application/cap+xml", 429, **{"Retry-After": "600"})
        if failure == "html":
            return response(b"<html>Unavailable</html>", "text/html")
        if failure == "identity":
            return response(cap(ID + "other"), "application/cap+xml")
        return response(b" " * (source.MAX_CAP_BYTES + 1), "application/cap+xml")

    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        with pytest.raises(source.MeteoAlarmError):
            source.download(now=lambda: NOW, client=client)
    assert len(requests) == 2


def test_batch_deadline_and_cancellation_prevent_publication():
    with httpx.Client(transport=httpx.MockTransport(lambda request: response(feed(entry()), "application/atom+xml"))) as client:
        times = iter((0, 0, source.TOTAL_SECONDS + 1))
        with pytest.raises(source.MeteoAlarmError, match="meteoalarm_batch_timeout"):
            source.download(now=lambda: NOW, client=client, monotonic=lambda: next(times))

        def cancel():
            raise RuntimeError("cancelled")

        with pytest.raises(RuntimeError, match="cancelled"):
            source.download(now=lambda: NOW, client=client, checkpoint=cancel)


@pytest.mark.parametrize(("value", "expected"), [
    ("600", 600), ("864000", 864000), ("Mon, 14 Sep 2026 08:40:00 GMT", 601),
    ("bad-header", source.POLL_SECONDS), (None, source.POLL_SECONDS),
])
def test_throttling_keeps_the_provider_requested_pause(value, expected):
    headers = {} if value is None else {"Retry-After": value}
    with httpx.Client(transport=httpx.MockTransport(lambda request: response(b"", "text/plain", 429, **headers))) as client:
        with pytest.raises(source.MeteoAlarmError) as caught:
            source.download(now=lambda: NOW, client=client)
    assert caught.value.code == "meteoalarm_rate_limited"
    assert caught.value.retry_after_seconds == expected
