"""Bounded literal SpreadsheetML cells; no calculation or rendered-format claims."""
import re
from datetime import datetime
from io import BytesIO
from urllib.parse import quote
from zipfile import BadZipFile, ZipFile

from .document_comparison import Passage
from .docx_reader import CT, Package, R, local

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
EXTRACTOR = "tender-xlsx-cells-v1"
S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
MAIN = XLSX_MIME + ".main+xml"
WORKSHEET = "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
CELL = re.compile(r"([A-Z]{1,3})([1-9][0-9]{0,6})\Z")
NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[Ee][+-]?[0-9]+)?\Z")


def main_part(package):
    root = package.xml("[Content_Types].xml")
    if root.tag != f"{{{CT}}}Types":
        raise ValueError("Invalid content types")
    overrides = {}
    for node in root:
        if any(word in node.get("ContentType", "").lower() for word in ("macroenabled", "vbaproject")):
            raise ValueError("Macros are unsupported")
        if node.tag == f"{{{CT}}}Override":
            name = node.get("PartName")
            if not name or name in overrides:
                raise ValueError("Ambiguous content type")
            overrides[name] = node.get("ContentType")
    mains = [target for kind, target in package.relationships("").values() if kind == R + "/officeDocument"]
    if len(mains) != 1 or not mains[0] or overrides.get("/" + mains[0]) != MAIN:
        raise ValueError("Not an XLSX workbook")
    return mains[0], overrides


def is_xlsx(body):
    try:
        with ZipFile(BytesIO(body)) as archive:
            main_part(Package(archive))
        return True
    except (ValueError, BadZipFile, RuntimeError, NotImplementedError):
        return False


def rich_text(node):
    text, partial = [], False
    for child in node:
        if child.tag == f"{{{S}}}t":
            text.append(child.text or "")
        elif child.tag == f"{{{S}}}r":
            text.extend(item.text or "" for item in child if item.tag == f"{{{S}}}t")
            partial |= any(local(item.tag) != "t" for item in child)
        else:
            partial = True
    return "".join(text), partial


def coordinate(value):
    match = CELL.fullmatch(value or "")
    if not match:
        raise ValueError("Missing or invalid cell reference")
    letters, row = match.groups()
    col = 0
    for letter in letters:
        col = col * 26 + ord(letter) - 64
    if col > 16384 or int(row) > 1048576:
        raise ValueError("Cell outside XLSX bounds")
    return int(row), col


def read_xlsx(body, append):
    partial = False
    with ZipFile(BytesIO(body)) as archive:
        package = Package(archive)
        main, overrides = main_part(package)
        workbook = package.xml(main)
        if workbook.tag != f"{{{S}}}workbook":
            raise ValueError("Unsupported workbook namespace")
        relationships = package.relationships(main)
        shared, styles = [], None
        seen_kinds = set()
        for kind, target in relationships.values():
            if kind in {R + "/sharedStrings", R + "/styles"}:
                if kind in seen_kinds or not target:
                    raise ValueError("Ambiguous workbook part")
                seen_kinds.add(kind)
                root = package.xml(target)
                if kind.endswith("/sharedStrings"):
                    if root.tag != f"{{{S}}}sst" or any(c.tag != f"{{{S}}}si" for c in root):
                        raise ValueError("Invalid shared string table")
                    shared = [rich_text(child) for child in root]
                else:
                    if root.tag != f"{{{S}}}styleSheet":
                        raise ValueError("Invalid styles")
                    formats = root.findall(f"{{{S}}}cellXfs")
                    if len(formats) != 1 or any(n.tag != f"{{{S}}}xf" for n in formats[0]):
                        raise ValueError("Ambiguous cell styles")
                    styles = list(formats[0])
                    partial |= any(local(n.tag) in {"strike", "vertAlign", "extLst"} for n in root.iter())
            elif kind != R + "/worksheet":
                partial = True
        partial |= any(not n.tag.startswith(f"{{{S}}}") or local(n.tag) not in {"workbook", "fileVersion", "workbookPr", "bookViews", "workbookView", "sheets", "sheet", "calcPr"} for n in workbook.iter())
        sheet_tables = workbook.findall(f"{{{S}}}sheets")
        sheets = sheet_tables[0] if len(sheet_tables) == 1 else None
        if sheets is None or not 1 <= len(sheets) <= 64:
            raise ValueError("Missing or excessive worksheets")
        names, identifiers, targets, selected = set(), set(), set(), []
        for sheet in sheets:
            name, identifier = sheet.get("name", ""), sheet.get("sheetId", "")
            if sheet.tag != f"{{{S}}}sheet" or not name or len(name) > 31 or name.casefold() in names or not identifier.isdecimal() or int(identifier) < 1 or int(identifier) in identifiers:
                raise ValueError("Ambiguous worksheet identity")
            names.add(name.casefold())
            identifiers.add(int(identifier))
            relation = relationships.get(sheet.get(f"{{{R}}}id"))
            if not relation or not relation[1] or relation[1] in targets:
                raise ValueError("Missing or repeated worksheet target")
            kind, target = relation
            targets.add(target)
            if kind != R + "/worksheet":
                partial = True
                continue
            if overrides.get("/" + target) != WORKSHEET:
                raise ValueError("Unsupported worksheet content type")
            visibility = sheet.get("state", "visible")
            if visibility not in {"visible", "hidden", "veryHidden"}:
                raise ValueError("Invalid sheet visibility")
            partial |= visibility != "visible"
            selected.append((name, target))
        # Stable sheet/cell identities, independent of ZIP/member/XML ordering.
        for name, target in sorted(selected):
            root = package.xml(target)
            if root.tag != f"{{{S}}}worksheet":
                raise ValueError("Invalid worksheet")
            partial |= bool(package.relationships(target))
            partial |= any(not n.tag.startswith(f"{{{S}}}") or local(n.tag) not in {"worksheet", "dimension", "sheetViews", "sheetView", "selection", "sheetFormatPr", "sheetData", "row", "c", "v", "is", "t", "r", "f", "pageMargins"} for n in root.iter())
            partial |= any(n.get("hidden") in {"1", "true"} or n.get("s") not in {None, "0"} for n in root.iter() if local(n.tag) == "row")
            rows = root.findall(f"{{{S}}}sheetData")
            if len(rows) != 1:
                raise ValueError("Ambiguous cell table")
            cells, seen_rows = {}, set()
            for row in rows[0]:
                row_id = row.get("r", "")
                if row.tag != f"{{{S}}}row" or not row_id.isdecimal() or not 1 <= int(row_id) <= 1048576 or int(row_id) in seen_rows:
                    raise ValueError("Missing or duplicate row identity")
                seen_rows.add(int(row_id))
                for cell in row:
                    ref = cell.get("r", "")
                    if cell.tag != f"{{{S}}}c" or ref in cells or coordinate(ref)[0] != int(row_id):
                        raise ValueError("Ambiguous cell identity")
                    cells[ref] = cell
            for ref, cell in sorted(cells.items(), key=lambda item: coordinate(item[0])):
                locator = f"part:{target}/sheet:{quote(name, safe='')}/cell:{ref}"
                kind = cell.get("t", "n")
                formula, value, inline = cell.findall(f"{{{S}}}f"), cell.findall(f"{{{S}}}v"), cell.findall(f"{{{S}}}is")
                if len(formula) > 1 or len(value) > 1 or len(inline) > 1:
                    raise ValueError("Duplicate cell value")
                if any(not child.tag.startswith(f"{{{S}}}") for child in cell):
                    raise ValueError("Unsupported cell namespace")
                if formula:
                    partial = True
                    if formula[0].text and formula[0].text.strip():
                        append(Passage(locator=locator + "/formula", text=formula[0].text))
                    continue  # Cached results are not current evaluated values.
                style = cell.get("s", "0")
                if not style.isdecimal() or (styles is not None and int(style) >= len(styles)) or (styles is None and int(style)):
                    raise ValueError("Missing cell style")
                if styles is not None:
                    partial |= styles[int(style)].get("numFmtId", "0") != "0"
                    partial |= styles[int(style)].get("xfId", "0") != "0"
                if kind == "inlineStr":
                    if len(inline) != 1 or value:
                        raise ValueError("Invalid inline cell")
                    text, incomplete = rich_text(inline[0])
                    partial |= incomplete
                else:
                    if inline:
                        raise ValueError("Unexpected inline value")
                    text = value[0].text or "" if value else ""
                    if kind == "s":
                        if not text.isdecimal() or int(text) >= len(shared):
                            raise ValueError("Invalid shared string reference")
                        text, incomplete = shared[int(text)]
                        partial |= incomplete
                    elif kind == "n":
                        if text and not NUMBER.fullmatch(text):
                            raise ValueError("Invalid finite numeric literal")
                    elif kind == "b":
                        if text not in {"0", "1"}:
                            raise ValueError("Invalid boolean literal")
                    elif kind == "d":
                        # Validate an ISO date/time literal, preserving its exact
                        # spelling and timezone instead of formatting a date.
                        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}(?:T[0-9:.]+(?:Z|[+-][0-9]{2}:[0-9]{2})?)?", text):
                            raise ValueError("Invalid ISO date literal")
                        datetime.fromisoformat(text)
                        partial = True
                    elif kind in {"e", "str"}:
                        partial = True
                    else:
                        raise ValueError("Unsupported cell type")
                if text.strip():
                    # Excel character escapes need decoding rules beyond XML.
                    # Keep the source spelling but never certify it as complete.
                    partial |= bool(re.search(r"_x[0-9A-Fa-f]{4}_", text))
                    append(Passage(locator=locator + "/" + ("text" if kind in {"s", "inlineStr"} else kind), text=text))
    return partial
