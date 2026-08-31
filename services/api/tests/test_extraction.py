import socket

import httpx
import pymupdf
import pytest
from conftest import policy

from regwatch.config import DomainError, Settings
from regwatch.diffing import compare_passages
from regwatch.extraction import Fetched, Fetcher, canonical_url, discover_links, extract, validate_public_url


def test_normalisation_removes_layout_noise_but_keeps_changed_numbers():
    a = extract(policy(30), "text/html")
    b = extract(
        policy(30)
        .replace(b"must retain", b"must   \n retain")
        .replace(b"Footer updated every day", b"New footer"),
        "text/html",
    )
    assert a.content_hash == b.content_hash
    assert not compare_passages(a.passages, b.passages)["changed"]
    c = extract(policy(60, "<p>A new record owner must be appointed.</p>"), "text/html")
    diff = compare_passages(a.passages, c.passages)
    assert diff["counts"]["modified"] == 1 and diff["counts"]["added"] == 1
    assert "30" in diff["items"][1]["old"]["text"] and "60" in diff["items"][1]["new"]["text"]


def test_pdf_text_and_page_references_with_scanned_pdf_error():
    with pymupdf.open() as document:
        document.new_page().insert_text(
            (72, 72), "Synthetic policy: retain records for 30 days. This is a test."
        )
        document.new_page().insert_text((72, 72), "The second page contains a separate fictional paragraph.")
        content = document.tobytes()
    result = extract(content, "application/pdf", "test.pdf")
    assert {p["page"] for p in result.passages} == {1, 2}
    assert result.preview()["page_count"] == 2
    with pymupdf.open() as blank:
        blank.new_page()
        with pytest.raises(DomainError) as error:
            extract(blank.tobytes(), "application/pdf")
    assert error.value.code == "ocr_required"


@pytest.mark.parametrize(
    "body,mime,name",
    [
        (b"", "text/plain", "empty.txt"),
        (b"\x00\x01\x02broken binary", "application/octet-stream", "file.bin"),
        (b'{"not":"a supported regulatory document format"}', "application/json", "data.json"),
        (b"%PDF damaged", "application/pdf", "broken.pdf"),
        (b"<html><main><div id='app'></div></main></html>", "text/html", "spa.html"),
        (
            b"<form><input type='password'></form><p>Sign in to access the regulator's documents.</p>",
            "text/html",
            "login.html",
        ),
    ],
)
def test_invalid_documents_explain_failure(body, mime, name):
    with pytest.raises(DomainError):
        extract(body, mime, name)


def test_discovery_normalises_fragments_keeps_queries_and_obeys_limits():
    body = '<main><a href="/laws/a?edition=1#x">One</a><a href="/laws/a?edition=1#y">Duplicate</a><a href="/laws/a?edition=2">Two</a>'
    body += '<a href="/lawsmith/a">Wrong prefix</a><a href="https://outside.example/laws/a">Wrong host</a>'
    body += "".join('<a href="/laws/' + str(number) + '">Document</a>' for number in range(60)) + "</main>"
    result = discover_links(Fetched("https://example.com/laws/", body.encode(), "text/html"), "/laws")
    assert result["returned_count"] == 50 and result["candidate_count"] == 62
    assert result["limit_reached"] is True
    assert result["candidates"][0]["url"] == "https://example.com/laws/a?edition=1"
    assert result["candidates"][1]["url"] == "https://example.com/laws/a?edition=2"
    assert canonical_url("HTTPS://EXAMPLE.COM:443/a?q=1#part") == "https://example.com/a?q=1"


def test_discovery_ignores_navigation_and_prioritises_direct_documents_before_the_limit():
    body = '<body><nav><a href="/navigation">Navigation only</a></nav><div role="main">'
    body += "".join(f'<a href="/section/{number}">Related page</a>' for number in range(55))
    body += '<a href="/files/law.pdf">Actual circular PDF</a></div></body>'
    result = discover_links(Fetched("https://example.com/list", body.encode(), "text/html"))
    assert result["candidate_count"] == 56 and result["returned_count"] == 50
    assert result["candidates"][0]["url"] == "https://example.com/files/law.pdf"
    assert all("/navigation" not in candidate["url"] for candidate in result["candidates"])


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "ftp://example.com/file", "https://user:password@example.com", "not a url"]
)
def test_invalid_source_urls_are_rejected(url):
    with pytest.raises(DomainError):
        canonical_url(url)


@pytest.mark.asyncio
async def test_private_and_local_sources_are_blocked_without_dns_assumptions(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 80)),
        ],
    )
    with pytest.raises(DomainError) as error:
        await validate_public_url("https://example.com/")
    assert error.value.code == "private_source"


@pytest.mark.asyncio
async def test_downloader_bounds_response_size_and_follows_redirects(monkeypatch):
    real_client = httpx.AsyncClient
    requested = []

    def respond(request):
        requested.append(str(request.url))
        if request.url.path == "/redirect":
            return httpx.Response(302, headers={"location": "/law"})
        return httpx.Response(200, headers={"content-type": "text/html"}, content=policy() * 5)

    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs))
    fetcher = Fetcher(Settings(_env_file=None, allow_private_sources=True, max_document_bytes=1024))
    with pytest.raises(DomainError) as error:
        await fetcher.fetch("http://test.invalid/redirect")
    assert error.value.code == "document_too_large"
    assert requested == ["http://test.invalid/redirect", "http://test.invalid/law"]


@pytest.mark.asyncio
async def test_discovery_download_stops_before_a_redirect_outside_the_selected_section(monkeypatch):
    real_client = httpx.AsyncClient
    requested = []

    def respond(request):
        requested.append(str(request.url))
        return httpx.Response(302, headers={"location": "/outside/another-document"})

    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs))
    fetcher = Fetcher(Settings(_env_file=None, allow_private_sources=True))
    with pytest.raises(DomainError) as error:
        await fetcher.fetch(
            "http://test.invalid/laws/redirect",
            boundary=("http://test.invalid/laws/", "/laws"),
        )
    assert error.value.code == "outside_section"
    assert requested == ["http://test.invalid/laws/redirect"]
