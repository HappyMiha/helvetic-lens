"""Bounded local upload parser. No network, model or source discovery."""
import json
import sys
from pathlib import PurePath

MAX_BYTES = 2 * 1024 * 1024
MAX_TEXT = 24000
FORMATS = {
    ".txt": {"text/plain"}, ".md": {"text/plain", "text/markdown"},
    ".csv": {"text/plain", "text/csv", "application/vnd.ms-excel"},
    ".html": {"text/html"}, ".htm": {"text/html"}, ".pdf": {"application/pdf"},
}


def parse(body, filename, content_type):
    from .extraction import extract
    from .pdf_reader import read_pdf

    if not body or len(body) > MAX_BYTES:
        return {"error": "Original retained. Automatic extraction accepts files up to 2 MB."}
    suffix = PurePath(filename).suffix.lower()
    media = content_type.split(";")[0].strip().lower()
    if suffix not in FORMATS or media not in FORMATS[suffix] | {"", "application/octet-stream"}:
        return {"error": "Original retained. Automatic extraction supports TXT, Markdown, CSV, HTML and text PDF with matching content types."}
    if suffix == ".pdf":
        if not body.startswith(b"%PDF"):
            return {"error": "Original retained. The file does not contain a PDF document."}
        pdf = read_pdf(body, max_pages=60, text_page_limit=20)
        sections = [(f"page-{page.number}", block) for page in pdf.pages for block in page.blocks]
        page_count = pdf.page_count
        truncated = page_count > 20
    elif suffix in {".html", ".htm"}:
        result = extract(body, "text/html", filename)
        sections = [(passage["id"], passage["text"]) for passage in result.passages]
        truncated, page_count = False, None
    else:
        try:
            text = body.decode("utf-8-sig")
        except UnicodeError:
            return {"error": "Original retained. Text extraction requires UTF-8 encoding."}
        if any(ord(c) < 32 and c not in "\r\n\t" for c in text):
            return {"error": "Original retained. This file contains unsupported binary content."}
        sections, truncated, page_count = [("text", text)], False, None
    excerpts, remaining, extracted = [], MAX_TEXT, sum(len(text) for _, text in sections)
    for position, (location, text) in enumerate(sections, 1):
        if remaining <= 0:
            break
        value = text[:remaining]
        for offset in range(0, len(value), 1200):
            part = value[offset:offset + 1200]
            if part.strip():
                excerpts.append({"passage": f"{location}-block-{position}-char-{offset + 1}", "text": part})
        remaining -= len(value)
    if not excerpts:
        return {"error": "Original retained. No readable text was found; image and scanned PDF OCR is unavailable."}
    return {"status": "complete", "excerpts": excerpts, "text_truncated": truncated or extracted > MAX_TEXT,
        "extracted_characters": extracted, "page_count": page_count,
        "scope": "Local file extraction: at most 2 MB, 60 PDF pages, text from the first 20 PDF pages and 24,000 characters. "
            "No OCR. Quotes refer to retained extracted text; original bytes remain downloadable."}


def main():
    # Applied inside a fresh child before loading the PDF/HTML parser. Parent also
    # enforces a wall deadline and kills/reaps this process on cancellation.
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (12, 12))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:
        result = parse(sys.stdin.buffer.read(MAX_BYTES + 1), sys.argv[1], sys.argv[2])
    except Exception:
        result = {"error": "Original retained. The document is damaged, encrypted, scanned or exceeds extraction limits."}
    sys.stdout.write(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
