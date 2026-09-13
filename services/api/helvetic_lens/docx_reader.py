"""Bounded, in-memory DOCX text stories. Never launch Office or extract files.

Text is tied to package-part/XML locations, not invented rendered page numbers.
Unsupported layout/field/revision constructs make extraction explicitly partial.
"""

import re
from collections import Counter
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile
from zlib import error as DecompressionError

from .document_comparison import Passage

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
EXTRACTOR = "tender-docx-stories-v1"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
MAX_MEMBERS = 256
MAX_PART_BYTES = 4 * 1024 * 1024
MAX_PACKAGE_BYTES = 32 * 1024 * 1024
MAX_XML_NODES = 50000
MAX_DEPTH = 64
UNSUPPORTED = {"altChunk", "subDoc", "object", "pict", "drawing", "sym", "fldChar",
               "instrText", "fldSimple", "del", "ins", "moveFrom", "moveTo", "vanish",
               "numPr", "commentReference", "commentRangeStart", "dataBinding", "contentPart"}


class InvalidDocx(ValueError):
    pass


def local(tag):
    return tag.rsplit("}", 1)[-1]


def resolve_target(part, target):
    if not target or any(c in target for c in "\\:%?#") or any(ord(c) < 32 for c in target):
        raise InvalidDocx("Invalid package target")
    pieces = [] if target.startswith("/") else part.split("/")[:-1]
    for piece in target.lstrip("/").split("/"):
        if piece == "..":
            if not pieces:
                raise InvalidDocx("Package target escapes its root")
            pieces.pop()
        elif piece == ".":
            continue
        elif not piece:
            raise InvalidDocx("Ambiguous package target")
        else:
            pieces.append(piece)
    if not pieces:
        raise InvalidDocx("Empty package target")
    return "/".join(pieces)


class Package:
    def __init__(self, archive):
        self.archive = archive
        self.roots = {}
        self.xml_nodes = 0
        members = archive.infolist()
        if len(members) > MAX_MEMBERS or sum(item.file_size for item in members) > MAX_PACKAGE_BYTES:
            raise InvalidDocx("Package exceeds extraction bounds")
        names = set()
        for item in members:
            name = item.filename.rstrip("/")
            if not name or item.filename != item.orig_filename or resolve_target("", name) != name or name.startswith("/"):
                raise InvalidDocx("Unsafe or ambiguous package name")
            if name.casefold() in names:
                raise InvalidDocx("Duplicate package name")
            names.add(name.casefold())
            if (item.flag_bits & 1 or item.compress_type not in {ZIP_STORED, ZIP_DEFLATED}
                    or item.file_size > max(item.compress_size, 1) * 200
                    or name.casefold().endswith("vbaproject.bin")):
                raise InvalidDocx("Unsupported encrypted, macro or excessive compressed content")

    def xml(self, name):
        if name in self.roots:
            return self.roots[name]
        try:
            info = self.archive.getinfo(name)
            if info.file_size > MAX_PART_BYTES:
                raise InvalidDocx("XML part exceeds extraction bound")
            with self.archive.open(info) as stream:
                raw = stream.read(MAX_PART_BYTES + 1)
            if len(raw) > MAX_PART_BYTES:
                raise InvalidDocx("XML part exceeds extraction bound")
            text = raw.decode("utf-8-sig")
            declaration = re.match(r"^<\?xml\s[^>]*encoding\s*=\s*(['\"])(.*?)\1", text)
            if declaration and declaration.group(2).casefold() not in {"utf-8", "utf8"}:
                raise InvalidDocx("Only UTF8 XML is supported")
            if "\x00" in text or "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
                raise InvalidDocx("DTD/entities and non-UTF8 XML are unsupported")
            if text.count("<") > MAX_XML_NODES * 2:
                raise InvalidDocx("XML token bound exceeded")
            root = ET.fromstring(text)
            pending, count = [(root, 0)], 0
            while pending:
                node, depth = pending.pop()
                count += 1
                if count > MAX_XML_NODES or depth > MAX_DEPTH:
                    raise InvalidDocx("XML structure bound exceeded")
                pending.extend((child, depth + 1) for child in node)
            self.xml_nodes += count
            if self.xml_nodes > MAX_XML_NODES * 2:
                raise InvalidDocx("Combined XML structure bound exceeded")
            self.roots[name] = root
            return root
        except (KeyError, UnicodeError, ET.ParseError, BadZipFile, RuntimeError, NotImplementedError,
                DecompressionError, EOFError) as error:
            raise InvalidDocx("Unreadable package XML") from error

    def relationships(self, part):
        parent, _, filename = part.rpartition("/")
        name = f"{parent + '/' if parent else ''}_rels/{filename}.rels" if part else "_rels/.rels"
        if name not in self.archive.namelist():
            return {}
        root = self.xml(name)
        if root.tag != f"{{{PKG}}}Relationships":
            raise InvalidDocx("Invalid relationship part")
        result = {}
        for node in root:
            identifier, kind, target = (node.get(key) for key in ("Id", "Type", "Target"))
            if node.tag != f"{{{PKG}}}Relationship" or not identifier or identifier in result or not kind or not target:
                raise InvalidDocx("Invalid or duplicate relationship")
            mode = node.get("TargetMode", "Internal")
            if mode not in {"Internal", "External"}:
                raise InvalidDocx("Invalid relationship mode")
            result[identifier] = (kind, None if mode == "External" else resolve_target(part, target))
        return result


def read_docx(body, append):
    """Append bounded passages through the parent parser's common quota guard."""
    partial = False
    with ZipFile(BytesIO(body)) as archive:
        package = Package(archive)
        types = package.xml("[Content_Types].xml")
        if types.tag != f"{{{CT}}}Types":
            raise InvalidDocx("Missing content type declarations")
        overrides = {}
        for node in types:
            if any(word in node.get("ContentType", "").lower() for word in ("macroenabled", "vbaproject")):
                raise InvalidDocx("Macro content is not a supported DOCX part")
            if node.tag == f"{{{CT}}}Override":
                name = node.get("PartName", "")
                if name in overrides:
                    raise InvalidDocx("Duplicate content type")
                overrides[name] = node.get("ContentType")
        mains = [target for kind, target in package.relationships("").values() if kind == R + "/officeDocument"]
        if len(mains) != 1 or not mains[0]:
            raise InvalidDocx("Missing internal main document")
        main = mains[0]
        if overrides.get("/" + main) != "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml":
            raise InvalidDocx("Package is not a supported DOCX document")
        pending, seen = [(main, "document", None)], set()
        while pending:
            part, expected_root, note_id = pending.pop(0)
            if (part, note_id) in seen:
                continue
            seen.add((part, note_id))
            if len(seen) > MAX_MEMBERS:
                raise InvalidDocx("Too many referenced stories")
            root = package.xml(part)
            if root.tag != f"{{{W}}}{expected_root}":
                raise InvalidDocx("Unexpected WordprocessingML story root")
            if part != main:
                content_name = {"hdr": "header", "ftr": "footer"}.get(expected_root, expected_root)
                if overrides.get("/" + part) != f"application/vnd.openxmlformats-officedocument.wordprocessingml.{content_name}+xml":
                    raise InvalidDocx("Unexpected story content type")
            relationships = package.relationships(part)
            if note_id is not None:
                notes = [node for node in root if node.get(f"{{{W}}}id") == note_id]
                if len(notes) != 1:
                    raise InvalidDocx("Missing or duplicate referenced note")
                root = notes[0]
                if root.tag != f"{{{W}}}{expected_root.removesuffix('s')}":
                    raise InvalidDocx("Unexpected note element")
            if expected_root == "document" and len(root.findall(f"{{{W}}}body")) != 1:
                raise InvalidDocx("Missing or duplicate main body")
            for node in root.iter():
                name = local(node.tag)
                if name in UNSUPPORTED or not node.tag.startswith(f"{{{W}}}"):
                    partial = True
                if name in {"headerReference", "footerReference"}:
                    wanted = "header" if name == "headerReference" else "footer"
                    kind, target = relationships.get(node.get(f"{{{R}}}id"), (None, None))
                    if kind != R + "/" + wanted or target is None:
                        raise InvalidDocx("Unresolved referenced story")
                    pending.append((target, "hdr" if wanted == "header" else "ftr", None))
                if name in {"footnoteReference", "endnoteReference"}:
                    wanted = "footnotes" if name == "footnoteReference" else "endnotes"
                    targets = [target for kind, target in relationships.values() if kind == R + "/" + wanted]
                    identifier = node.get(f"{{{W}}}id")
                    if len(targets) != 1 or targets[0] is None or identifier is None:
                        raise InvalidDocx("Unresolved referenced note")
                    pending.append((targets[0], wanted, identifier))

            def paragraphs(node, path):
                if node.tag == f"{{{W}}}p":
                    chunks = []

                    def text_of(current):
                        if current is not node and current.tag == f"{{{W}}}p":
                            return
                        if current.tag in {f"{{{W}}}t", f"{{{W}}}delText"}:
                            chunks.append(current.text or "")
                        elif current.tag == f"{{{W}}}tab":
                            chunks.append("\t")
                        elif current.tag in {f"{{{W}}}br", f"{{{W}}}cr"}:
                            chunks.append("\n")
                        elif current.tag == f"{{{W}}}noBreakHyphen":
                            chunks.append("\u2011")
                        elif current.tag == f"{{{W}}}softHyphen":
                            chunks.append("\u00ad")
                        for child in current:
                            text_of(child)

                    text_of(node)
                    text = "".join(chunks)
                    if text.strip():
                        append(Passage(locator=f"part:{part}/{path}", text=text))
                counts = Counter()
                for child in node:
                    name = local(child.tag)
                    counts[name] += 1
                    paragraphs(child, f"{path}/{name}[{counts[name]}]")

            paragraphs(root, local(root.tag) + (f"[id={note_id}]" if note_id is not None else ""))
    return partial
