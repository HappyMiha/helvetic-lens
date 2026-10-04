"""Bounded local upload parser. No network, model or source discovery."""
import asyncio
import hashlib
import json
import sys
from pathlib import PurePath

MAX_BYTES = 100 * 1024 * 1024
MAX_TEXT = 24000
FORMATS = {
    ".txt": {"text/plain"}, ".md": {"text/plain", "text/markdown"},
    ".csv": {"text/plain", "text/csv", "application/vnd.ms-excel"},
    ".html": {"text/html"}, ".htm": {"text/html"}, ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    ".eml": {"message/rfc822"},
    ".json": {"application/json"},
}


def parse(body, filename, content_type, *, nested=False, cursor=None):
    from .extraction import extract
    from .pdf_reader import read_pdf

    progressive = cursor is not None
    cursor = cursor or {"page": 0, "offset": 0}
    if set(cursor) != {"page", "offset"} or any(type(v) is not int or v < 0 for v in cursor.values()):
        raise ValueError("Invalid document position")
    start, offset = cursor["page"], cursor["offset"]
    if start > 1000 or offset > 10_000_000:
        raise ValueError("Document position exceeds limits")
    if not body or len(body) > MAX_BYTES:
        return {"error": "Original retained. Automatic extraction accepts files up to 100 MB."}
    suffix = PurePath(filename).suffix.lower()
    media = content_type.split(";")[0].strip().lower()
    if suffix not in FORMATS or media not in FORMATS[suffix] | {"", "application/octet-stream"}:
        return {"error": "Original retained. Automatic extraction supports TXT, Markdown, CSV, HTML, PDF, DOCX, XLSX, PPTX and EML with matching content types."}
    warnings, attachments, methods, structures = [], [], [], {}
    if suffix == ".pdf":
        if not body.startswith(b"%PDF"):
            return {"error": "Original retained. The file does not contain a PDF document."}
        pdf = read_pdf(body, max_pages=1000 if progressive else 60,
            text_page_limit=4 if progressive else 20, page_start=start)
        sections = [(f"page-{page.number}-text-{i}", block) for page in pdf.pages
            for i, block in enumerate(page.blocks, 1)] if progressive else [(f"page-{page.number}", block) for page in pdf.pages for block in page.blocks]
        from .document_ocr import pdf_pages
        scanned = [page.number for page in pdf.pages if page.requires_ocr]
        methods = ["pdfminer"]
        if scanned:
            recognized, warnings = pdf_pages(body, scanned)
            sections.extend(recognized)
            if recognized:
                methods.append("tesseract-ocr")
        page_count = pdf.page_count
        truncated = page_count > (start + 4 if progressive else 20)
    elif suffix in {".docx", ".xlsx", ".pptx"}:
        from .document_formats import office
        sections = office(body, suffix)
        methods, truncated, page_count = ["ooxml-stored-text"], False, None
    elif suffix == ".json":
        sections = []
        def walk(value, path="$", depth=0):
            if depth > 30 or len(sections) > 4000:
                raise ValueError("JSON exceeds limits")
            if isinstance(value, dict):
                for key, child in value.items():
                    walk(child, path + "." + str(key)[:120], depth + 1)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    walk(child, path + f"[{index}]", depth + 1)
            elif value is not None:
                sections.append((path, str(value)))
        walk(json.loads(body))
        methods, truncated, page_count = ["json-fields"], False, None
    elif suffix == ".eml":
        if nested:
            return {"error": "Nested messages are retained but not recursively extracted."}
        from .document_formats import email
        sections, attachments, warnings = email(body, parse)
        methods, truncated, page_count = ["mime-stored-text"], False, None
    elif suffix in {".html", ".htm"}:
        result = extract(body, "text/html", filename)
        sections = [(passage["id"], passage["text"]) for passage in result.passages]
        structures = {passage['id']: passage['html_structure'] for passage in result.passages
            if passage.get('html_structure')}
        methods = ["html-text"]
        truncated, page_count = False, None
    else:
        try:
            text = body.decode("utf-8-sig")
        except UnicodeError:
            return {"error": "Original retained. Text extraction requires UTF-8 encoding."}
        if any(ord(c) < 32 and c not in "\r\n\t" for c in text):
            return {"error": "Original retained. This file contains unsupported binary content."}
        sections, truncated, page_count, methods = [("text", text)], False, None, ["utf8-text"]
    excerpts, remaining, extracted = [], MAX_TEXT, sum(len(text) for _, text in sections)
    skipped, consumed = offset, 0
    for position, (location, text) in enumerate(sections, 1):
        if skipped >= len(text):
            skipped -= len(text)
            continue
        if remaining <= 0:
            break
        begin = skipped
        skipped = 0
        value = text[begin:begin + remaining]
        if len(location) > 80:
            location = location[:50] + "-" + hashlib.sha256(location.encode()).hexdigest()[:16]
        for part_start in range(0, len(value), 1200):
            part = value[part_start:part_start + 1200]
            if part.strip():
                locator = location if progressive and suffix == ".pdf" else f"{location}-block-{position}"
                excerpts.append({"passage": f"{locator}-char-{begin + part_start + 1}", "text": part,
                    **({'html_structure': structures[location]} if location in structures else {})})
        remaining -= len(value)
        consumed += len(value)
    next_cursor = ({"page": start, "offset": offset + consumed} if offset + consumed < extracted else
        {"page": start + 4, "offset": 0} if suffix == ".pdf" and truncated else None)
    reading = {"contract": "document-reading/v1", "cursor": cursor, "next_cursor": next_cursor,
        "pages": [start + 1, min(start + 4, page_count)] if suffix == ".pdf" else None,
        "page_count": page_count, "characters_read": consumed,
        "complete": next_cursor is None and not warnings,
        "unread_reason": "More document sections remain." if next_cursor else "Extraction warnings require checking the original." if warnings else None}
    if not excerpts and not progressive:
        return {"error": "Original retained. No readable text was found within extraction limits.", "warnings": warnings}
    return {"status": "complete", "excerpts": excerpts, "text_truncated": bool(next_cursor),
        "extracted_characters": extracted, "page_count": page_count, "extraction_methods": methods,
        "warnings": list(dict.fromkeys(warnings)), "attachments": attachments,
        **({"reading": reading} if progressive else {}),
        "scope": ("Incremental local extraction: 100 MB originals, up to 1,000 PDF pages; four pages and 24,000 characters per saved portion. "
            if progressive else "Local extraction: at most 100 MB, 60 PDF pages, text from the first 20 pages, OCR of up to four scanned pages, 24,000 characters. ")
            + "Up to ten email attachments. Office cells use stored values; formulas and active content are not executed. "
            "Layout, merged cells and OCR may require checking the original. Quotes refer to extracted text, not verified facts."}


async def extract_file(body, filename, content_type, *, cursor=None):
    """Fresh isolated parser with wall/CPU/memory/output bounds; no model calls."""
    process = await asyncio.create_subprocess_exec(sys.executable, "-m", __name__, filename, content_type, json.dumps(cursor),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        start_new_session=True)
    try:
        async with asyncio.timeout(55):
            output, _ = await process.communicate(body)
        if process.returncode or len(output) > 250000:
            raise ValueError("Parser exceeded its limits")
        return json.loads(output)
    except (ValueError, TimeoutError):
        return {"error": "Original retained. Extraction could not finish within its format, size or time limits."}
    finally:
        # Kill descendants too: a cancelled PDF render/OCR must not outlive its job.
        import os
        import signal
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()


def main():
    # Applied inside a fresh child before loading the PDF/HTML parser. Parent also
    # enforces a wall deadline and kills/reaps this process on cancellation.
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (40, 40))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:
        result = parse(sys.stdin.buffer.read(MAX_BYTES + 1), sys.argv[1], sys.argv[2],
            cursor=json.loads(sys.argv[3]) if len(sys.argv) > 3 else None)
    except Exception:
        result = {"error": "Original retained. The document is damaged, encrypted, unsupported or exceeds extraction limits."}
    sys.stdout.write(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
