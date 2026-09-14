"""Actual SpreadsheetML packages, independent of Office and the production parser."""
from io import BytesIO
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZIP_DEFLATED, ZipFile

from docx_fixture import CT, PKG, R

S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def cell(ref, text, kind="inlineStr", *, attributes="", formula=None):
    value = (f'<is><t xml:space="preserve">{escape(text)}</t></is>' if kind == "inlineStr"
             else f'<v>{escape(text)}</v>')
    if formula is not None:
        value = f'<f>{escape(formula)}</f>' + value
    return f'<c r="{ref}" t="{kind}" {attributes}>{value}</c>'


def worksheet(content, *, before="", after=""):
    return f'<worksheet xmlns="{S}" xmlns:r="{R}">{before}<sheetData>{content}</sheetData>{after}</worksheet>'


def xlsx(text="3 references required", *, rows=None, sheets=None, parts=None, shared=None, styles=None, compression=ZIP_DEFLATED):
    sheets = sheets or [("Conditions", "sheet1.xml", "visible", rows if rows is not None else '<row r="1">' + cell("A1", text) + '</row>')]
    files = {}
    relations, declarations, references = [], [], []
    for i, (name, target, state, content) in enumerate(sheets):
        references.append(f'<sheet name={quoteattr(name)} sheetId="{i+1}" r:id="s{i}" state="{state}"/>')
        relations.append(f'<Relationship Id="s{i}" Type="{R}/worksheet" Target="worksheets/{target}"/>')
        declarations.append(f'<Override PartName="/xl/worksheets/{target}" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        files[f"xl/worksheets/{target}"] = worksheet(content)
    for kind, content in [("sharedStrings", shared), ("styles", styles)]:
        if content is not None:
            files[f"xl/{kind}.xml"] = content
            relations.append(f'<Relationship Id="{kind}" Type="{R}/{kind}" Target="{kind}.xml"/>')
            declarations.append(f'<Override PartName="/xl/{kind}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.{kind}+xml"/>')
    files.update({
        "[Content_Types].xml": f'<Types xmlns="{CT}"><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' + ''.join(declarations) + '</Types>',
        "_rels/.rels": f'<Relationships xmlns="{PKG}"><Relationship Id="main" Type="{R}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": f'<workbook xmlns="{S}" xmlns:r="{R}"><sheets>' + ''.join(references) + '</sheets></workbook>',
        "xl/_rels/workbook.xml.rels": f'<Relationships xmlns="{PKG}">' + ''.join(relations) + '</Relationships>',
    })
    files.update(parts or {})
    stream = BytesIO()
    with ZipFile(stream, 'w', compression=compression) as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    return stream.getvalue()
