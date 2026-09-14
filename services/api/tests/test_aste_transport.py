from datetime import UTC, datetime

import httpx
import pytest

from helvetic_lens.aste_parser import ORIGIN, listing_url
from helvetic_lens.aste_transport import AsteTransportError, fetch, validate_url


@pytest.mark.parametrize("path", ["/it/api/auction/bid/185", "/it/api/auction/buy/185",
    "/it/api/auction/toggleFavorite/185", "/it/login", "/it/auction/185?session=secret",
    "/it/api/auction/auction-status/185?sinceBidId=8", "/it/../admin", "/it/%2e%2e/admin",
    "/uploads/146/a.pdf", "/it/?page=2&page=3", "/it/?search=private-profile"])
def test_transport_never_fetches_action_or_private_query_urls(path):
    with pytest.raises(AsteTransportError):
        validate_url(ORIGIN + path)


def test_transport_has_no_inherited_auth_cookies_redirects_or_private_headers():
    calls, guards = [], []

    def handle(request):
        calls.append(request)
        assert request.method == "GET" and str(request.url) == listing_url(category="30", page=2)
        assert not any(name in request.headers for name in ("authorization", "cookie", "x-private"))
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(200, headers={"Content-Type": "text/html"}, stream=httpx.ByteStream(b"<html>synthetic</html>"))

    with httpx.Client(transport=httpx.MockTransport(handle), auth=("private", "secret"),
                      cookies={"session": "secret"}, headers={"x-private": "secret"}, params={"search": "private"},
                      follow_redirects=True) as client:
        body = fetch(client, listing_url(category="30", page=2), guard=lambda: guards.append(True))
    assert body == b"<html>synthetic</html>" and len(calls) == 1 and guards == [True, True]


def test_redirect_is_not_followed_and_publisher_backoff_is_preserved():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": "https://evil.invalid/", "retry-after": "600"})

    with httpx.Client(transport=httpx.MockTransport(handle), follow_redirects=True) as client:
        with pytest.raises(AsteTransportError) as error:
            fetch(client, ORIGIN + "/it/", guard=lambda: None)
    assert error.value.code == "aste_http_302" and error.value.retry_after_seconds == 600 and len(calls) == 1


@pytest.mark.parametrize("headers,body", [
    ({"Content-Type": "text/html", "Content-Length": "999999999"}, b"small"),
    ({"Content-Type": "text/html", "Content-Encoding": "gzip"}, b"compressed"),
    ({"Content-Type": "text/plain"}, b"wrong-type"), ({"Content-Type": "text/html"}, b"")])
def test_size_type_encoding_or_empty_body_failure_never_becomes_empty_listing(headers, body):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, headers=headers, stream=httpx.ByteStream(body)))) as client:
        with pytest.raises(AsteTransportError):
            fetch(client, ORIGIN + "/it/", guard=lambda: None)


def test_rights_guard_can_reject_before_http_or_after_stream_without_publishing_bytes():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, headers={"content-type": "text/html"}, stream=httpx.ByteStream(b"synthetic"))

    def deny():
        raise ValueError("synthetic revoked lease")

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError):
            fetch(client, ORIGIN + "/it/", guard=deny)
        assert not calls
        checked = []

        def second_denies():
            if checked:
                deny()
            checked.append(True)

        with pytest.raises(ValueError):
            fetch(client, ORIGIN + "/it/", guard=second_denies)
        assert len(calls) == 1


def test_http_date_retry_after_and_pdf_signature_check():
    now = datetime(2026, 9, 14, 2, 0, tzinfo=UTC)
    path = ORIGIN + "/uploads/146/" + "a" * 32 + ".pdf?2.35"
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(429, headers={"retry-after": "Mon, 14 Sep 2026 02:02:00 GMT"}))) as client:
        with pytest.raises(AsteTransportError) as error:
            fetch(client, path, guard=lambda: None, now=lambda: now)
    assert error.value.retry_after_seconds == 121
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, headers={"content-type": "application/pdf"}, stream=httpx.ByteStream(b"<html>Login</html>")))) as client:
        with pytest.raises(AsteTransportError):
            fetch(client, path, guard=lambda: None)


def test_long_publisher_wait_is_not_shortened_by_the_transport():
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(429, headers={"retry-after": "864000"}))) as client:
        with pytest.raises(AsteTransportError) as error:
            fetch(client, ORIGIN + "/it/", guard=lambda: None)
    assert error.value.retry_after_seconds == 864000
