"""Shared, page-aware PDF text extraction using the MIT-licensed pdfminer.six.

Keep layout analysis here; legal-text normalization belongs to extraction.py.
No OCR, rendering engine, network call, or model is involved in reading a PDF.
"""

from dataclasses import dataclass
from io import BytesIO

from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTContainer, LTTextContainer
from pdfminer.pdfdocument import PDFDocument, PDFPasswordIncorrect
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pdfminer.pdftypes import resolve1
from pdfminer.psexceptions import PSException
from pdfminer.utils import decode_text

from .config import DomainError

MAX_PDF_PAGES = 1000
PDF_EXTRACTOR_VERSION = "pdfminer-v1"


@dataclass(frozen=True)
class PdfTextPage:
    number: int
    blocks: tuple[str, ...]


@dataclass(frozen=True)
class PdfText:
    title: str
    page_count: int
    pages: tuple[PdfTextPage, ...]


def _text_blocks(layout: LTContainer):
    # pdfminer orders text boxes using layout geometry, including columns.
    # Forms can contain nested text; do not extract a container twice.
    for item in layout:
        if isinstance(item, LTTextContainer):
            text = item.get_text().strip()
            if text:
                yield text
        elif isinstance(item, LTContainer):
            yield from _text_blocks(item)


def read_pdf(
    body: bytes, *, max_pages: int = MAX_PDF_PAGES, text_page_limit: int | None = None
) -> PdfText:
    """Count real pages before layout work; optionally read only an opening excerpt.

    The page limit applies to the whole file, including blank pages. The excerpt
    limit is for court metadata only, never for persisted document evidence.
    """
    try:
        with BytesIO(body) as stream:
            document = PDFDocument(PDFParser(stream), caching=False)
            if document.encryption:
                raise DomainError("Password-protected PDFs are not supported.", 422, "encrypted_pdf")
            pages = []
            for page in PDFPage.create_pages(document):
                pages.append(page)
                if len(pages) > max_pages:
                    raise DomainError(f"This PDF exceeds the {max_pages:,}-page extraction limit.", 413)
            if not pages:
                raise ValueError("PDF has no pages")

            title = ""
            for info in document.info:
                value = resolve1(info.get("Title", ""))
                if isinstance(value, bytes):
                    value = decode_text(value)
                if isinstance(value, str) and value.strip():
                    title = value.strip()
                    break

            resources = PDFResourceManager()
            device = PDFPageAggregator(resources, laparams=LAParams(all_texts=True))
            interpreter = PDFPageInterpreter(resources, device)
            result = []
            characters = block_count = 0
            try:
                for number, page in enumerate(pages[:text_page_limit], 1):
                    interpreter.process_page(page)
                    blocks = tuple(_text_blocks(device.get_result()))
                    characters += sum(len(block) for block in blocks)
                    block_count += len(blocks)
                    if characters > 1_200_000 or block_count > 6000:
                        raise DomainError(
                            "The extracted document exceeds the MVP text limit.", 413, "document_too_large"
                        )
                    result.append(PdfTextPage(number, blocks))
            finally:
                device.close()
            return PdfText(title, len(pages), tuple(result))
    except PDFPasswordIncorrect as exc:
        raise DomainError("Password-protected PDFs are not supported.", 422, "encrypted_pdf") from exc
    except (PSException, ValueError, TypeError, KeyError, IndexError, EOFError, OSError, RecursionError) as exc:
        raise DomainError(
            "This PDF could not be read. It may be damaged or unsupported.", 422, "invalid_pdf"
        ) from exc
