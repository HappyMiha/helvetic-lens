import pytest
from pdf_fixture import make_pdf

from helvetic_lens.config import DomainError
from helvetic_lens.extraction import extract
from helvetic_lens.pdf_reader import read_pdf


def test_column_order_comes_from_layout_not_pdf_drawing_order():
    body = make_pdf([[
        (320, 720, "Art. 2 Second column\nSecond obligation stays here."),
        (72, 720, "Art. 1 First column\nFirst obligation stays here."),
    ]])
    result = extract(body, "application/pdf")
    assert [p["text"] for p in result.passages] == [
        "Art. 1 First column First obligation stays here.",
        "Art. 2 Second column Second obligation stays here.",
    ]
    assert result.extractor == "native-pdfminer-v1"
    assert result.body == body


def test_blank_pages_keep_actual_citation_numbers_and_metadata_is_unicode():
    title = "Überwachung — Décisions, decisioni e decisiuns"
    body = make_pdf(["", "Art. 1 Überwachung: données personnelles, società, Svizra, rights."], title=title)
    result = extract(body, "application/pdf")
    assert result.title == title
    assert result.passages[0]["page"] == 2
    assert "Überwachung" in result.text and "données" in result.text and "società" in result.text
    assert read_pdf(body).page_count == 2


def test_metadata_excerpt_does_not_truncate_full_document_evidence():
    body = make_pdf([f"Article {number}: this page has substantive legal evidence." for number in range(1, 43)])
    excerpt = read_pdf(body, text_page_limit=40)
    assert excerpt.page_count == 42 and len(excerpt.pages) == 40
    full = extract(body, "application/pdf")
    assert full.passages[-1]["page"] == 42
    assert "Article 42" in full.text


def test_page_limit_includes_blank_pages_and_rejects_before_layout(monkeypatch):
    body = make_pdf(["", "", "Article 3: text must not bypass the total page limit."])

    def no_layout(*args):
        pytest.fail("Layout must not start for a PDF above the page limit")

    monkeypatch.setattr("helvetic_lens.pdf_reader.PDFPageInterpreter.process_page", no_layout)
    with pytest.raises(DomainError) as error:
        read_pdf(body, max_pages=2)
    assert error.value.status == 413


@pytest.mark.parametrize("password", ["secret", ""])
def test_encrypted_pdfs_are_rejected_even_with_an_empty_open_password(password):
    body = make_pdf(["This protected document contains text that must not be imported."], password=password)
    with pytest.raises(DomainError) as error:
        extract(body, "application/pdf")
    assert error.value.code == "encrypted_pdf"


@pytest.mark.parametrize("body", [b"%PDF broken", b"%PDF-1.7\n%%EOF", b"not a pdf"])
def test_malformed_pdf_has_a_stable_user_facing_error(body):
    with pytest.raises(DomainError) as error:
        read_pdf(body)
    assert error.value.code == "invalid_pdf"
