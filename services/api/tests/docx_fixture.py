"""Small actual OPC/DOCX byte fixtures, with no Office process or remote input."""

from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def paragraph(text):
    return f'<w:p><w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'


def docx(text="3 references required", *, content=None, parts=None, relationships=(), overrides=(), compression=ZIP_DEFLATED):
    files = {
        "[Content_Types].xml": f'<Types xmlns="{CT}"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        + "".join(f'<Override PartName="/{name}" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.{kind}+xml"/>' for name, kind in overrides)
        + '</Types>',
        "_rels/.rels": f'<Relationships xmlns="{PKG}"><Relationship Id="main" Type="{R}/officeDocument" Target="word/document.xml"/></Relationships>',
        "word/document.xml": f'<w:document xmlns:w="{W}" xmlns:r="{R}"><w:body>{content if content is not None else paragraph(text)}</w:body></w:document>',
    }
    if relationships:
        files["word/_rels/document.xml.rels"] = f'<Relationships xmlns="{PKG}">' + "".join(
            f'<Relationship Id="{identifier}" Type="{R}/{kind}" Target="{target}"/>'
            for identifier, kind, target in relationships) + '</Relationships>'
    files.update(parts or {})
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=compression) as archive:
        for name, value in files.items():
            archive.writestr(name, value)
    return buffer.getvalue()
