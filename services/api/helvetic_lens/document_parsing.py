"""Bounded local parsing of already-permitted tender bytes; no network or OCR.

Raw originals remain authoritative. Complete denotes the extracted text layer,
not visual diagrams, embedded attachments or legal completeness of requirements.
Unsupported files remain available as originals without fabricated parsed text.
"""

import hashlib
from email.message import Message
from uuid import UUID
from zipfile import BadZipFile

from pydantic import ValidationError

from .config import DomainError
from .document_comparison import MAX_PASSAGES, MAX_TEXT_BYTES, ParsedDocument, Passage, text_fingerprint
from .docx_reader import DOCX_MIME, EXTRACTOR, read_docx
from .pdf_reader import PDF_EXTRACTOR_VERSION, read_pdf

MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
MAX_DOCUMENT_PAGES = 200


def parse_document(body: bytes, *, content_type: str, snapshot_id: UUID,
                   access_scope_id: UUID, source_id: str, dossier_id: str,
                   item_id: str, language: str) -> tuple[ParsedDocument, str]:
    """Return exact source/hash binding plus explicit extraction outcome.

    The caller must preserve original bytes atomically, validate source permission
    and scope, and store this projection under the same snapshot. No URL or token
    belongs in this parser. Application/octet-stream PDFs are recognized by magic;
    other binary files are never decoded speculatively as procurement text.
    """
    if not isinstance(body, bytes) or not body or len(body) > MAX_DOCUMENT_BYTES:
        raise ValueError("Document bytes are empty or exceed the supported bound")
    mime = content_type.split(";", 1)[0].strip().lower()
    passages, status, reason = [], "complete", "text_layer_extracted"
    text_bytes = 0

    def append(passage):
        nonlocal text_bytes
        text_bytes += len(passage.text.encode())
        if len(passages) >= MAX_PASSAGES or text_bytes > MAX_TEXT_BYTES:
            raise OverflowError("Parsed text limit exceeded")
        passages.append(passage)

    extractor = "tender-plain-utf8-v1"
    if body.startswith(b"%PDF") or mime == "application/pdf":
        extractor = f"tender-{PDF_EXTRACTOR_VERSION}-v1"
        try:
            pdf = read_pdf(body, max_pages=MAX_DOCUMENT_PAGES)
            for page in pdf.pages:
                if not page.blocks:
                    status, reason = "partial", "page_without_text"
                for index, block in enumerate(page.blocks, 1):
                    append(Passage(locator=f"page:{page.number}/block:{index}",
                                   page=page.number, text=block))
        except OverflowError:
            passages, status, reason = [], "failed", "parsed_limit_exceeded"
        except (DomainError, ValidationError):
            passages, status, reason = [], "failed", "pdf_extraction_failed"
    elif mime == DOCX_MIME or (mime == "application/octet-stream" and body.startswith(b"PK\x03\x04")):
        extractor = EXTRACTOR
        try:
            if read_docx(body, append):
                status, reason = "partial", "docx_unsupported_constructs"
        except OverflowError:
            passages, status, reason = [], "failed", "parsed_limit_exceeded"
        except (ValueError, BadZipFile, RuntimeError, NotImplementedError):
            passages, status, reason = [], "failed", "docx_extraction_failed"
    elif mime in {"text/plain", "text/markdown"}:
        try:
            header = Message()
            header["content-type"] = content_type
            encoding = header.get_content_charset()
            if encoding and encoding not in {"utf-8", "utf8"}:
                raise ValueError("Unsupported declared text encoding")
            decoded = body.decode("utf-8-sig", errors="strict")
            # Accept only declared UTF-8 text, never guess legacy encodings.
            for number, line in enumerate(decoded.splitlines(), 1):
                if line.strip():
                    append(Passage(locator=f"line:{number}", text=line))
        except OverflowError:
            passages, status, reason = [], "failed", "parsed_limit_exceeded"
        except ValueError:
            passages, status, reason = [], "failed", "text_extraction_failed"
    else:
        status, reason = "failed", "unsupported_format"
        extractor = "tender-unsupported-v1"
    if (len(passages) > MAX_PASSAGES
            or sum(len(p.text.encode()) for p in passages) > MAX_TEXT_BYTES):
        passages, status, reason = [], "failed", "parsed_limit_exceeded"
    if not passages and status != "failed":
        status, reason = "failed", "no_extractable_text"
    parsed = ParsedDocument(snapshot_id=snapshot_id, access_scope_id=access_scope_id,
                            source_id=source_id, dossier_id=dossier_id, item_id=item_id,
                            content_sha256=hashlib.sha256(body).hexdigest(),
                            text_sha256=text_fingerprint(passages), extractor_version=extractor,
                            language=language, parse_status=status, passages=tuple(passages))
    return parsed, reason
