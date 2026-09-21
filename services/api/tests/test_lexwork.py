import copy

import httpx
import pytest
from pdf_fixture import make_pdf

from helvetic_lens.config import DomainError, Settings
from helvetic_lens.diffing import compare_passages
from helvetic_lens.extraction import Fetcher, extract
from helvetic_lens.lexwork import reference

ORIGIN = "https://www.belex.sites.be.ch"
LAW = ORIGIN + "/app/de/texts_of_law/124.1"


def metadata(version=2114):
    return {"text_of_law": {
        "systematic_number": "124.1", "title": "Synthetic integration law",
        "current_version": {"id": version},
        "selected_version": {
            "id": version, "version_dates_str": "Test version",
            "pdf_link_tol": f"{ORIGIN}/api/de/versions/{version}/pdf_file",
        },
    }}


def fetcher_with_transport(monkeypatch, respond):
    client = httpx.AsyncClient
    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: client(transport=transport, **kw))
    return Fetcher(Settings(_env_file=None, allow_private_sources=True))


@pytest.mark.parametrize("url", [
    LAW + "?redirect=elsewhere", LAW.replace("https:", "http:"),
    LAW.replace("www.belex.sites.be.ch", "www.belex.sites.be.ch.attacker.example"),
    LAW.replace("https://", "https://user:secret@"),
    LAW.replace("/de/", "/en/"), LAW + "/versions/0",
])
def test_only_bounded_official_law_references_are_resolved(url):
    assert reference(url) is None


@pytest.mark.asyncio
async def test_stable_link_follows_new_current_pdf_and_keeps_exact_evidence(monkeypatch):
    current = 2114
    requests = []

    def respond(request):
        requests.append(str(request.url))
        if "/texts_of_law/" in request.url.path:
            return httpx.Response(200, json=metadata(current))
        return httpx.Response(200, content=make_pdf([
            f"Synthetic test law: integration notification required within {30 if current == 2114 else 60} days."
        ]), headers={"content-type": "application/pdf"})

    fetcher = fetcher_with_transport(monkeypatch, respond)
    previous = await fetcher.fetch(LAW)
    current = 2115
    updated = await fetcher.fetch(LAW)
    assert previous.metadata["lexwork_version_id"] == 2114
    assert updated.metadata["lexwork_version_id"] == 2115
    assert updated.metadata["lexwork_source_url"] == LAW
    assert updated.metadata["lexwork_version_selection"] == "current"
    assert len(updated.metadata["lexwork_metadata_sha256"]) == 64
    diff = compare_passages(extract(previous.body, previous.content_type).passages,
                            extract(updated.body, updated.content_type).passages)
    assert diff["changed"]
    assert requests == [ORIGIN + "/api/de/texts_of_law/124.1",
                        ORIGIN + "/api/de/versions/2114/pdf_file",
                        ORIGIN + "/api/de/texts_of_law/124.1",
                        ORIGIN + "/api/de/versions/2115/pdf_file"]


@pytest.mark.asyncio
async def test_explicit_history_does_not_silently_select_current_version(monkeypatch):
    record = metadata(2113)
    record["text_of_law"]["current_version"]["id"] = 2114
    requested = []

    def respond(request):
        requested.append(str(request.url))
        return (httpx.Response(200, json=record) if "/texts_of_law/" in request.url.path
                else httpx.Response(200, content=make_pdf(["Synthetic historical law text for testing only."])))

    result = await fetcher_with_transport(monkeypatch, respond).fetch(LAW + "/versions/2113")
    assert requested[0].endswith("/texts_of_law/124.1/versions/2113")
    assert result.metadata["lexwork_version_selection"] == "historical"
    assert result.metadata["lexwork_version_id"] == 2113


@pytest.mark.parametrize("damage", ["law", "version", "foreign_pdf", "language", "malformed", "redirect", "not_pdf"])
@pytest.mark.asyncio
async def test_unverified_publisher_evidence_is_rejected(monkeypatch, damage):
    record = copy.deepcopy(metadata())
    law = record["text_of_law"]
    if damage == "law":
        law["systematic_number"] = "999.9"
    if damage == "version":
        law["current_version"]["id"] = 2115
    if damage == "foreign_pdf":
        law["selected_version"]["pdf_link_tol"] = "https://elsewhere.example/law.pdf"
    if damage == "language":
        law["selected_version"]["pdf_link_tol"] = ORIGIN + "/api/fr/versions/2114/pdf_file"
    requests = []

    def respond(request):
        requests.append(str(request.url))
        if "/texts_of_law/" in request.url.path:
            return (httpx.Response(200, content=b"not JSON") if damage == "malformed"
                    else httpx.Response(200, json=record))
        if damage == "redirect":
            return httpx.Response(302, headers={"location": ORIGIN + "/api/de/versions/2115/pdf_file"})
        return httpx.Response(200, content=b"<html>A publisher error page, not a PDF.</html>")

    with pytest.raises(DomainError):
        await fetcher_with_transport(monkeypatch, respond).fetch(LAW)
    assert not any("elsewhere.example" in url or "/versions/2115/" in url for url in requests)


def test_basel_and_bern_data_links_share_exact_law_identity():
    basel = reference("https://www.gesetzessammlung.bs.ch/data/153.260/de")
    assert basel.number == "153.260" and basel.jurisdiction == "CH-BS"
    bern = reference(LAW)
    assert bern.number == "124.1" and bern.jurisdiction == "CH-BE"
