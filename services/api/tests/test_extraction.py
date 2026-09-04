import socket

import httpx
import pytest
from conftest import policy
from pdf_fixture import make_pdf

from helvetic_lens.config import DomainError, Settings
from helvetic_lens.diffing import compare_passages
from helvetic_lens.extraction import (
    Fetched,
    Fetcher,
    _normalize_pdf_block,
    canonical_url,
    discover_links,
    extract,
    fedlex_eli_reference,
    validate_public_url,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Die Personengesell-\nschaft reicht ein.", "Die Personengesellschaft reicht ein."),
        ("Klein-\nund Mittelunternehmen", "Klein- und Mittelunternehmen"),
        ("Stamm-\noder Zweigniederlassung", "Stamm- oder Zweigniederlassung"),
        ("Risiko-\nManagement", "Risiko-Management"),
        ("Personengesell- schaft", "Personengesell- schaft"),
    ],
)
def test_pdf_dehyphenation_only_repairs_explicit_safe_line_breaks(raw, expected):
    assert _normalize_pdf_block(raw) == expected


def test_pdf_extraction_keeps_raw_multiline_evidence_when_repairing_soft_wraps():
    raw = "Die Personengesell-\nschaft reicht ein.\nKlein-\nund Mittelunternehmen"
    result = extract(make_pdf([raw]), "application/pdf", "wrapped.pdf")

    assert result.passages[0]["text"] == (
        "Die Personengesellschaft reicht ein. Klein- und Mittelunternehmen"
    )
    assert result.passages[0]["raw_text"] == raw


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
    content = make_pdf([
        "Synthetic policy: retain records for 30 days. This is a test.",
        "The second page contains a separate fictional paragraph.",
    ])
    result = extract(content, "application/pdf", "test.pdf")
    assert {p["page"] for p in result.passages} == {1, 2}
    assert result.preview()["page_count"] == 2
    with pytest.raises(DomainError) as error:
        extract(make_pdf([""]), "application/pdf")
    assert error.value.code == "ocr_required"


def test_pdf_above_the_old_mvp_page_limit_is_supported():
    content = make_pdf([
        f"Official report page {page_number}: extractable regulatory text."
        for page_number in range(1, 252)
    ])
    result = extract(content, "application/pdf", "long-report.pdf")
    assert result.preview()["page_count"] == 251
    assert result.passages[-1]["page"] == 251


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


@pytest.mark.parametrize(
    ("url", "collection", "language", "version", "requested_format", "language_defaulted"),
    [
        ("https://www.fedlex.admin.ch/eli/cc/2022/491/en", "cc", "en", None, None, False),
        ("https://fedlex.data.admin.ch/eli/cc/2022/491", "cc", "de", None, None, True),
        (
            "https://fedlex.data.admin.ch/eli/cc/2022/491/20230901/fr/html",
            "cc",
            "fr",
            "2023-09-01",
            "html",
            False,
        ),
        ("https://fedlex.admin.ch/eli/fga/2017/2057/it", "fga", "it", None, None, False),
        ("https://fedlex.data.admin.ch/eli/fga/2002/316", "fga", "de", None, None, True),
        (
            "https://fedlex.data.admin.ch/eli/oc/VII/342_337_325/fr",
            "oc",
            "fr",
            None,
            None,
            False,
        ),
        ("https://fedlex.data.admin.ch/eli/oc/VII/342_337_325", "oc", "de", None, None, True),
    ],
)
def test_fedlex_eli_reference_recognises_stable_law_urls(
    url, collection, language, version, requested_format, language_defaulted
):
    reference = fedlex_eli_reference(url)
    assert reference is not None
    assert reference.collection == collection and reference.language == language
    assert reference.language_defaulted is language_defaulted
    assert reference.version_date == version and reference.requested_format == requested_format
    assert reference.work_uri.startswith("https://fedlex.data.admin.ch/eli/" + collection + "/")
    if "/VII/" in url:
        assert "/VII/" in reference.work_uri
    assert fedlex_eli_reference("https://example.com/eli/cc/2022/491/en") is None
    assert fedlex_eli_reference("https://fedlex.admin.ch/eli/cc/2022/>/en") is None
    assert fedlex_eli_reference("https://fedlex.admin.ch/search") is None
    assert fedlex_eli_reference("https://fedlex.admin.ch/eli/cc/2022/491/de/print") is None
    assert (
        fedlex_eli_reference("https://fedlex.data.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/law.html")
        is None
    )


@pytest.mark.asyncio
async def test_native_fedlex_eli_fetch_resolves_current_official_html_and_keeps_provenance(monkeypatch):
    source = "https://www.fedlex.admin.ch/eli/cc/2022/491/en"
    expression = "https://fedlex.data.admin.ch/eli/cc/2022/491/20250707/en"
    manifestation = expression + "/html"
    artifact = (
        "https://fedlex.data.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/2022/491/"
        "20250707/en/html/fedlex-data-admin-ch-eli-cc-2022-491-20250707-en-html.html"
    )
    requests = []
    real_client = httpx.AsyncClient

    def respond(request):
        requests.append(request)
        if request.url.path == "/sparqlendpoint":
            query = request.url.params["query"]
            assert "jolux:isMemberOf <https://fedlex.data.admin.ch/eli/cc/2022/491>" in query
            assert "user-format/html" in query and "dateApplicability" in query
            return httpx.Response(
                200,
                json={
                    "results": {
                        "bindings": [
                            {
                                "expression": {"value": expression},
                                "date": {"value": "2025-07-07"},
                                "manifestation": {"value": manifestation},
                                "file": {"value": artifact},
                                "title": {"value": "Federal Act on Data Protection"},
                            }
                        ]
                    }
                },
            )
        assert str(request.url) == artifact
        return httpx.Response(200, headers={"content-type": "text/html"}, content=policy())

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    fetched = await Fetcher(Settings(_env_file=None, allow_private_sources=True)).fetch(source)
    assert fetched.url == artifact and len(requests) == 2
    assert fetched.metadata == {
        "provider": "native",
        "fedlex_eli": True,
        "eli_source_url": source,
        "eli_work_uri": "https://fedlex.data.admin.ch/eli/cc/2022/491",
        "eli_expression_uri": expression,
        "eli_manifestation_uri": manifestation,
        "eli_version_date": "2025-07-07",
        "eli_format": "html",
        "eli_language": "en",
        "eli_language_defaulted": False,
        "eli_title": "Federal Act on Data Protection",
    }
    document = extract(fetched.body, fetched.content_type, "law.html")
    assert document.title == "Synthetic retention policy" and "30 days" in document.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source", "bindings", "code"),
    [
        (
            "https://www.fedlex.admin.ch/eli/cc/2022/491/en",
            [],
            "fedlex_document_unavailable",
        ),
        (
            "https://www.fedlex.admin.ch/eli/cc/2022/491/en",
            [
                {
                    "expression": {"value": "https://fedlex.data.admin.ch/eli/cc/2022/491/20250707/en"},
                    "date": {"value": "2025-07-07"},
                    "manifestation": {
                        "value": "https://fedlex.data.admin.ch/eli/cc/2022/491/20250707/en/html"
                    },
                    "file": {"value": "https://malicious.example/law.html"},
                }
            ],
            "fedlex_metadata_error",
        ),
        (
            "https://fedlex.data.admin.ch/eli/cc/2022/491/20250707/en/html",
            [
                {
                    "expression": {"value": "https://fedlex.data.admin.ch/eli/cc/2022/491/20250707/en"},
                    "date": {"value": "2025-07-07"},
                    "manifestation": {
                        "value": "https://fedlex.data.admin.ch/eli/cc/2022/491/20250707/en/pdf-a"
                    },
                    "file": {
                        "value": "https://fedlex.data.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/"
                        "2022/491/20250707/en/pdf-a/law.pdf"
                    },
                }
            ],
            "fedlex_metadata_error",
        ),
    ],
)
async def test_fedlex_resolver_rejects_missing_or_out_of_scope_metadata(
    monkeypatch, source, bindings, code
):
    real_client = httpx.AsyncClient
    requested = []

    def respond(request):
        requested.append(str(request.url))
        return httpx.Response(200, json={"results": {"bindings": bindings}})

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    fetcher = Fetcher(Settings(_env_file=None, allow_private_sources=True))
    with pytest.raises(DomainError) as error:
        await fetcher.fetch(source)
    assert error.value.code == code and len(requested) == 1
