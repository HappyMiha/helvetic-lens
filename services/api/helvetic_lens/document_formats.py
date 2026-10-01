"""Offline OOXML and MIME readers; no macros, formula evaluation or linked resources."""
import hashlib
import re
import zipfile
from email import policy
from email.parser import BytesParser
from io import BytesIO
from xml.etree import ElementTree as ET

MAX_EXPANDED = 16 * 1024 * 1024


def xml(body):
    if re.search(br"<!\s*(DOCTYPE|ENTITY)", body.replace(b"\x00", b""), re.I):
        raise ValueError("XML declarations are unsupported")
    return ET.fromstring(body)


def office(body, suffix):
    sections = []
    with zipfile.ZipFile(BytesIO(body)) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if (len(entries) > 1000 or len(set(names)) != len(names)
                or sum(entry.file_size for entry in entries) > MAX_EXPANDED
                or any(entry.flag_bits & 1 or entry.file_size > 4 * 1024 * 1024 for entry in entries)):
            raise ValueError("Office archive exceeds limits")
        def read(name):
            return xml(archive.read(name))
        if suffix == ".docx":
            root = read("word/document.xml")
            ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            body_node = root.find(ns + "body")
            if body_node is None:
                raise ValueError("No document body")
            for number, block in enumerate(body_node, 1):
                if block.tag == ns + "tbl":
                    for row_number, row in enumerate(block.findall(ns + "tr"), 1):
                        for col, cell in enumerate(row.findall(ns + "tc"), 1):
                            sections.append((f"table-{number}-row-{row_number}-cell-{col}",
                                "\n".join("".join(p.itertext()) for p in cell.findall(ns + "p"))))
                elif block.tag == ns + "p":
                    sections.append((f"paragraph-{number}", "".join(t.text or "" for t in block.iter(ns + "t"))))
        elif suffix == ".xlsx":
            ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
            strings = ["".join(t.text or "" for t in entry.iter(ns + "t"))
                for entry in read("xl/sharedStrings.xml")] if "xl/sharedStrings.xml" in names else []
            for name in sorted(n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)):
                for cell in read(name).iter(ns + "c"):
                    address = cell.get("r", "")
                    if not re.fullmatch(r"[A-Z]{1,3}[1-9]\d{0,6}", address):
                        continue
                    value = cell.findtext(ns + "v", "")
                    if cell.get("t") == "s":
                        value = strings[int(value)]
                    elif cell.get("t") == "inlineStr":
                        value = "".join(t.text or "" for t in cell.iter(ns + "t"))
                    # Stored values only. Formulas are never calculated or executed.
                    if value:
                        sections.append((name.split("/")[-1][:-4] + "-cell-" + address, value))
        else:
            ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
            for name in sorted(n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)):
                for number, paragraph in enumerate(read(name).iter(ns + "p"), 1):
                    sections.append((name.split("/")[-1][:-4] + f"-paragraph-{number}",
                        "".join(t.text or "" for t in paragraph.iter(ns + "t"))))
    return sections


def email(body, parse):
    message = BytesParser(policy=policy.default).parsebytes(body)
    if message.defects or not any(message.get(key) for key in ("From", "Subject", "Date")):
        raise ValueError("Invalid MIME message")
    sections, attachments, warnings = [], [], []
    for key in ("Subject", "From", "To", "Date"):
        if message.get(key):
            sections.append(("message-header-" + key.lower(), str(message[key])))
    parts = list(message.walk())
    if len(parts) > 100:
        raise ValueError("Too many MIME parts")
    expanded = 0
    for number, part in enumerate(parts, 1):
        if part.is_multipart():
            continue
        data = part.get_payload(decode=True) or b""
        expanded += len(data)
        if expanded > MAX_EXPANDED:
            raise ValueError("Email exceeds limits")
        filename = part.get_filename()
        if filename or part.get_content_disposition() == "attachment":
            if len(attachments) >= 10:
                warnings.append("Attachments after the first ten were not extracted.")
                break
            try:
                result = parse(data, filename or "attachment", part.get_content_type(), nested=True)
            except Exception:
                result = {"error": "Attachment is damaged, unsupported or exceeds extraction limits."}
            attachments.append({"part": number, "filename": (filename or "attachment")[:240],
                "sha256": hashlib.sha256(data).hexdigest(), "status": result.get("status", "unavailable"),
                "scope": result.get("scope") or result.get("error"), "text_truncated": result.get("text_truncated", False)})
            for passage in result.get("excerpts", []):
                sections.append((f"attachment-{number}-" + passage["passage"], passage["text"]))
        elif part.get_content_type() in {"text/plain", "text/html"}:
            text = data.decode(part.get_content_charset() or "utf-8", errors="replace")
            if part.get_content_type() == "text/html":
                from .extraction import extract
                text = extract(text.encode(), "text/html", "message.html").text
            sections.append((f"message-part-{number}", text))
    if any(a["status"] != "complete" or a["text_truncated"] for a in attachments):
        warnings.append("Some attachments could not be fully extracted; inspect the original message.")
    return sections, attachments, warnings
