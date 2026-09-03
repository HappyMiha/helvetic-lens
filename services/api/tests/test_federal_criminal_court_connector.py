import asyncio
from datetime import UTC, datetime

import httpx
import pymupdf
from sqlalchemy import func, select

from helvetic_lens.config import Settings
from helvetic_lens.extraction import extract
from helvetic_lens.federal_criminal_court_connector import FederalCriminalCourtConnector
from helvetic_lens.models import (
    ConnectorReceipt,
    ConnectorState,
    RegulatoryDocumentVersion,
    RegulatoryIdentifier,
    RegulatoryRelation,
    RegulatoryWork,
)

DOCUMENTS = (
    ("39fa0bc1-1f50-4f6b-85dd-dddad405a087", "SK.2026.12"),
    ("b2f4cc68-85a8-46df-8eca-225923d36f44", "BB.2026.60"),
)


def home(*, broken=False, changed=False):
    if broken:
        return "<html><main>Temporarily unavailable</main></html>"
    subject = "Data retention (Art. 25 DSG)" if not changed else "Corrected data retention (Art. 25 DSG)"
    return f"""
    <html><main><h2>Liste der neu aufgenommenen Entscheide</h2>
      <div class="list-group-item">- <b>{DOCUMENTS[0][1]}</b> -
        <a class="icon--pdf" href="https://bstger.weblaw.ch/api/getDocumentContent/{DOCUMENTS[0][0]}">(PDF)</a><br>
        <a href="https://bstger.weblaw.ch/api/getDocumentContent/{DOCUMENTS[0][0]}">{subject};;duplicate translation</a>
      </div>
      <div class="list-group-item">- <b>{DOCUMENTS[1][1]}</b> -
        <a class="icon--pdf" href="https://bstger.weblaw.ch/api/getDocumentContent/{DOCUMENTS[1][0]}">(PDF)</a><br>
        <a href="https://bstger.weblaw.ch/api/getDocumentContent/{DOCUMENTS[1][0]}">Ordonnance de procédure (art. 97 CO)</a>
      </div>
    </main></html>
    """


def pdf(docket, french=False):
    document = pymupdf.open()
    page = document.new_page()
    heading = (
        "Jugement du 21 aout 2026 Cour des plaintes"
        if french
        else "Urteil vom 20. August 2026 Strafkammer"
    )
    page.insert_text(
        (72, 72),
        f"Bundesstrafgericht\nNummer: {docket}\n{heading}\n"
        "Art. 25 DSG und SR 235.1 werden angewendet.",
    )
    return document.tobytes()


def transport(*, broken=False, changed=False):
    async def handler(request: httpx.Request):
        if request.url.host == "www.bstger.ch" and request.url.path == "/de/home/index":
            return httpx.Response(200, text=home(broken=broken, changed=changed), headers={"content-type": "text/html"})
        if request.url.host == "www.bstger.ch" and request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /Core/\n")
        if request.url.host == "bstger.weblaw.ch":
            document_id = request.url.path.rsplit("/", 1)[-1]
            index = next(index for index, item in enumerate(DOCUMENTS) if item[0] == document_id)
            return httpx.Response(200, content=pdf(DOCUMENTS[index][1], french=index == 1), headers={"content-type": "application/pdf"})
        return httpx.Response(404, text="fixture route missing")

    return httpx.MockTransport(handler)


def connector(settings, **kwargs):
    delays = kwargs.pop("delays", [])

    async def no_wait(value):
        delays.append(value)

    return FederalCriminalCourtConnector(
        settings,
        item_page_size=kwargs.pop("item_page_size", 2),
        overlap_items=kwargs.pop("overlap_items", 2),
        transport=kwargs.pop("transport", transport()),
        sleep=no_wait,
        now=lambda: datetime(2026, 9, 3, 8, 0, tzinfo=UTC),
        **kwargs,
    )


def test_latest_overlap_is_bounded_and_detects_listing_revision(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path)
    source = connector(settings, item_page_size=1)
    first = asyncio.run(source.discover_since(None, {}))
    second = asyncio.run(source.discover_since(first.next_cursor, {}))
    changed = connector(settings, item_page_size=1, transport=transport(changed=True))
    changed_first = asyncio.run(changed.discover_since(None, {}))

    assert [item.external_identity for item in first.items] == [DOCUMENTS[0][0]]
    assert [item.external_identity for item in second.items] == [DOCUMENTS[1][0]]
    assert second.complete is True
    assert second.next_cursor == {"offset": 0, "cycle": 1}
    assert changed_first.items[0].source_revision != first.items[0].source_revision


def test_metadata_pdf_languages_citations_and_provenance(tmp_path):
    delays = []
    source = connector(Settings(_env_file=None, data_dir=tmp_path), delays=delays)
    page = asyncio.run(source.discover_since(None, {}))
    metadata = asyncio.run(source.fetch_metadata(page.items[0]))
    expression = asyncio.run(source.list_expressions(metadata))[0]
    artifact = asyncio.run(source.fetch_official_artifact(expression))
    relations = asyncio.run(source.extract_relations(metadata))
    french = asyncio.run(source.fetch_metadata(page.items[1]))

    assert metadata.metadata["court_level"] == "federal"
    assert metadata.metadata["chamber"] == "Strafkammer"
    assert metadata.metadata["decision_date"] == "2026-08-20"
    assert expression.language == "de"
    assert french.metadata["language"] == "fr"
    assert french.metadata["decision_date"] == "2026-08-21"
    assert metadata.raw_provenance["latest_feed"].startswith("https://www.bstger.ch/")
    assert artifact.body.startswith(b"%PDF")
    assert metadata.metadata["artifact_sha256"] == artifact.expected_sha256
    assert {item.target.identifiers[0].scheme for item in relations} == {"sr_rs", "legal_abbreviation"}
    assert all(item.relation_type == "cites" for item in relations)
    assert delays and all(value >= 0.9 for value in delays)


def test_runner_deduplicates_overlap_and_reopens_original_evidence(harness):
    _, _, service, _ = harness
    source = connector(service.settings)
    first = asyncio.run(service.connector_runner.run_page(source, stream="latest"))
    repeated = asyncio.run(service.connector_runner.run_page(source, stream="latest"))
    assert first.status == "persisted" and repeated.status == "persisted"

    with service.db.session(include_all_organizations=True) as session:
        decisions = session.scalars(select(RegulatoryWork).where(RegulatoryWork.authority == "federal_criminal_court")).all()
        assert len(decisions) == 2
        assert session.scalar(select(func.count()).select_from(ConnectorReceipt)) == 2
        assert session.scalar(select(func.count()).select_from(RegulatoryDocumentVersion)) == 2
        assert session.scalar(select(func.count()).select_from(RegulatoryRelation)) == 4
        dockets = session.scalars(select(RegulatoryIdentifier).where(RegulatoryIdentifier.scheme == "court_docket")).all()
        assert {item.normalized_value for item in dockets} == {item[1] for item in DOCUMENTS}
        version = session.scalar(select(RegulatoryDocumentVersion))
        artifact_path = service.settings.storage_path / "artifacts" / version.artifact_key
        reopened = extract(artifact_path.read_bytes(), version.content_type, version.filename, "official_connector")
        assert DOCUMENTS[0][1] in reopened.text


def test_health_and_runner_degrade_on_template_drift(harness):
    _, _, service, _ = harness
    source = connector(service.settings, transport=transport(broken=True))
    report = asyncio.run(source.health())
    result = asyncio.run(service.connector_runner.run_page(source, stream="latest"))

    assert report.status == "degraded"
    assert report.source_contract["error_code"] == "connector_contract_drift"
    assert result.status == "degraded"
    with service.db.session(include_all_organizations=True) as session:
        state = session.scalar(select(ConnectorState).where(ConnectorState.connector == "federal-criminal-court"))
        assert state.cursor_json is None
