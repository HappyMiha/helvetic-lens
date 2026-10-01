"""Neutral source/file/recall/update outcomes; no live research or paid inference."""
import asyncio
import hashlib
import json
import shutil
from email.message import EmailMessage
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

import httpx
import pytest
from test_product_contributions import model_output, no_discovery, upload
from test_product_corpus_search import encoder
from test_product_decision_search import transport
from test_product_dossiers import ROOT, create
from test_product_dossiers import signed as signed
from test_product_evidence_search import local, retained, search
from test_product_investigations import complete
from test_product_web_research import setup

from helvetic_lens import evidence_graph_retrieval, research_catalogues
from helvetic_lens.product_contribution_extract import parse
from helvetic_lens.product_investigation_models import DossierEntity, DossierRelationship, Investigation
from helvetic_lens.product_investigations import scope
from helvetic_lens.product_models import ProductDossier


def zipped(files):
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return stream.getvalue()


DOCX = zipped({"word/document.xml": '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
<w:p><w:r><w:t>Fictional Alpine reuse report.</w:t></w:r></w:p>
<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Steel recovered: 12 tonnes.</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
</w:body></w:document>'''})


def test_office_tables_cells_and_slides_keep_exact_stored_text():
    doc = parse(DOCX, "report.docx", "application/octet-stream")
    assert doc["status"] == "complete" and "table-2-row-1-cell-1" in doc["excerpts"][1]["passage"]
    assert doc["excerpts"][1]["text"] == "Steel recovered: 12 tonnes."
    book = zipped({"xl/sharedStrings.xml": '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>Recovered steel</t></si></sst>',
        "xl/worksheets/sheet1.xml": '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="A1" t="s"><v>0</v></c><c r="B1"><f>6*2</f><v>12</v></c></row></sheetData></worksheet>'})
    cells = parse(book, "report.xlsx", "application/octet-stream")["excerpts"]
    assert [c["text"] for c in cells] == ["Recovered steel", "12"]
    assert "cell-B1" in cells[1]["passage"]
    slides = zipped({"ppt/slides/slide1.xml": '<s xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:p><a:r><a:t>Recovered steel</a:t></a:r></a:p></s>'})
    assert parse(slides, "report.pptx", "application/octet-stream")["excerpts"][0]["text"] == "Recovered steel"
    unsafe = zipped({"word/document.xml": '<!DOCTYPE a [<!ENTITY x "untrusted expansion">]><a>&x;</a>'})
    with pytest.raises(ValueError):
        parse(unsafe, "unsafe.docx", "application/octet-stream")


def test_email_attachments_are_local_cited_and_partial_failures_are_explicit():
    message = EmailMessage()
    message["Subject"], message["From"] = "Fictional reuse evidence", "researcher@example.org"
    message.set_content("Inspect the attached report. https://example.org/never-follow-this-link")
    message.add_attachment(DOCX, maintype="application", subtype="vnd.openxmlformats-officedocument.wordprocessingml.document", filename="report.docx")
    message.add_attachment(b"unsupported executable", maintype="application", subtype="octet-stream", filename="program.exe")
    value = parse(message.as_bytes(), "evidence.eml", "message/rfc822")
    assert value["status"] == "complete" and value["warnings"]
    assert any("attachment-" in e["passage"] and e["text"] == "Steel recovered: 12 tonnes." for e in value["excerpts"])
    assert value["attachments"][0]["sha256"] == hashlib.sha256(DOCX).hexdigest()
    assert value["attachments"][1]["status"] == "unavailable"


def test_direct_official_registry_and_feed_scopes_with_controlled_responses(monkeypatch):
    calls = []
    def handle(request):
        calls.append(request.url)
        if request.url.host == "clinicaltrials.gov":
            assert request.url.params["query.term"] == "fictional research"
            return httpx.Response(200, json={"studies": [{"protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Fictional registry fixture"},
                "descriptionModule": {"briefSummary": "Fixture, not clinical evidence."}}}], "nextPageToken": "more"})
        if request.url.host == "api.fda.gov":
            return httpx.Response(404, json={"error": {"code": "NOT_FOUND", "message": "No matches"}})
        assert request.url.host == "www.ema.europa.eu"
        return httpx.Response(200, text='<rss><channel><item><title>Fictional research record</title><link>https://www.ema.europa.eu/en/fixture</link><description>Test only</description></item></channel></rss>')
    transport(monkeypatch, handle)
    trials = asyncio.run(research_catalogues.search("clinicaltrials", "fictional research"))
    assert trials["more_available"] and trials["exhaustive"] is False
    assert trials["items"][0]["url"] == "https://clinicaltrials.gov/api/v2/studies/NCT00000001"
    assert asyncio.run(research_catalogues.search("fda_labels", "fictional research"))["items"] == []
    feed = asyncio.run(research_catalogues.search("ema_news", "fictional research"))
    assert "not an archive search" in feed["scope"] and len(feed["items"]) == 1
    assert len(calls) == 3


def test_office_contribution_runs_through_native_private_dossier_job(signed, monkeypatch):
    client, service, _, model = signed
    doc, _ = create(client)
    root = ROOT + "/" + doc["id"]
    forbidden = no_discovery(monkeypatch)
    model_output(monkeypatch, model)
    response = upload(client, root, DOCX, "report.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert response.status_code == 201, response.text
    value = complete(client, service, root + "/investigations", response.json()["analysis"])
    assert value["status"] == "completed" and not forbidden
    assert value["sources"][0]["snapshot"]["extraction_methods"] == ["ooxml-stored-text"]
    assert value["outcome"]["findings"][0]["review_requirement"]["required"]
    assert value["outcome"]["coverage_manifest"]["sources"][0]["extraction_methods"] == ["ooxml-stored-text"]


def test_graph_retrieval_uses_only_exact_citations_and_survives_embedding_outage(signed, monkeypatch):
    client, service, _, _ = signed
    doc, root = setup(client)
    quote = "Alpine Lab supplied a reuse report to Cedar Works."
    run_id, source_id = retained(service, doc, [quote, "An unrelated appendix."], finding=False)
    with service.db.session() as session:
        run = session.get(Investigation, run_id)
        from helvetic_lens.product_investigation_models import InvestigationSource
        source = session.get(InvestigationSource, source_id)
        citation = {"source_id": source_id, "quote": quote, "locator": "p0", "sha256": source.sha256}
        left, right = [DossierEntity(**scope(run), name=name, kind="organization", evidence=citation) for name in ("Alpine Lab", "Cedar Works")]
        session.add_all([left, right])
        session.flush()
        session.add(DossierRelationship(**scope(run), subject_id=left.id, object_id=right.id, predicate="supplied report", evidence=citation))
        session.commit()
    encoder(monkeypatch, service, failure="unavailable")
    local(monkeypatch, service)
    result = search(client, root, query="Cedar Works", mode="corpus")
    assert result.status_code == 200, result.text
    page = result.json()
    assert page["method"] == "lexical_graph_fallback" and not page["preparing"]
    assert page["items"][0]["graph_related"] and page["items"][0]["quote"] == quote
    with service.db.session() as session:
        parent = session.get(ProductDossier, doc["id"])
        narrowed = [item for item in page["items"] if item["locator"] != "p0"]
        value = evidence_graph_retrieval.project(session, parent, narrowed, "Cedar Works")
        assert not value["ranked_ids"] and not value["links"]


def test_json_fields_have_citable_locations():
    value = parse(json.dumps({"record": {"status": "withdrawn", "quantity": 12}}).encode(), "record.json", "application/json")
    assert value["extraction_methods"] == ["json-fields"]
    assert value["excerpts"][0]["text"] == "withdrawn" and "record.status" in value["excerpts"][0]["passage"]


def test_native_recall_prepares_all_public_passages_and_selects_semantic_match(signed, monkeypatch):
    from test_product_exploration import start
    from test_product_investigations import tick

    from helvetic_lens.product_investigation_models import InvestigationSource

    client, service, identity, model = signed
    root, run, _ = start(client, "legal")
    calls = encoder(monkeypatch, service)
    with service.db.session() as session:
        current = session.get(Investigation, run["id"])
        previous = Investigation(dossier_id=current.dossier_id, organization_id=current.organization_id,
            status="completed", request_key=str(uuid4()), question="Earlier fictional evidence")
        session.add(previous)
        session.flush()
        for index in range(9):
            text = "Keep the specimen between two and eight degrees." if index == 0 else f"Unrelated appendix {index}."
            source = InvestigationSource(**scope(previous), source_key=str(index), kind="public_source",
                title="Earlier record", url=f"https://example.org/record/{index}", sha256=hashlib.sha256(text.encode()).hexdigest(),
                snapshot={"excerpts": [{"passage": "p1", "text": text}]})
            session.add(source)
        session.commit()
    for _ in range(5):
        tick(service, run["id"])
        with service.db.session() as session:
            memory = session.get(Investigation, run["id"]).research_state.get("core", {}).get("recall")
            if memory:
                break
    assert memory and memory["retrieval"]["semantic_status"] == "complete"
    assert memory["retrieval"]["examined_records"] == memory["retrieval"]["prepared_records"] == 9
    assert memory["sources"][0]["url"] == "https://example.org/record/0"
    assert len(calls) == 2 and not model.calls, "Planning must wait for bounded saved-evidence recall"


@pytest.mark.skipif(not shutil.which("tesseract"), reason="Local OCR runtime not installed in this test environment")
def test_scanned_pdf_is_read_by_real_offline_ocr():
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen.canvas import Canvas

    from helvetic_lens.product_contribution_extract import extract_file

    picture = Image.new("RGB", (1200, 300), "white")
    ImageDraw.Draw(picture).text((40, 60), "Alpine material reuse report", font=ImageFont.load_default(size=48), fill="black")
    pdf = BytesIO()
    canvas = Canvas(pdf, pagesize=(600, 150))
    canvas.drawImage(ImageReader(picture), 0, 0, width=600, height=150)
    canvas.save()
    result = asyncio.run(extract_file(pdf.getvalue(), "scan.pdf", "application/pdf"))
    assert result["status"] == "complete", result
    assert "tesseract-ocr" in result["extraction_methods"]
    assert "Alpine material reuse report" in result["excerpts"][0]["text"]
    assert result["excerpts"][0]["passage"].startswith("page-1-ocr")
