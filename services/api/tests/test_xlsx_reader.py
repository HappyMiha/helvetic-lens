import hashlib
from io import BytesIO
from zipfile import ZIP_STORED, ZipFile

import pytest
from docx_fixture import CT, PKG, R
from test_document_comparison import pair
from test_document_parsing import parse
from xlsx_fixture import S, cell, worksheet, xlsx

from helvetic_lens.document_comparison import compare_documents
from helvetic_lens.xlsx_reader import EXTRACTOR, XLSX_MIME


def comparison(before, after):
    old, _ = parse(before, XLSX_MIME)
    new, _ = parse(after, XLSX_MIME)
    _, manifest, delta, snapshots = pair(old, new)
    return compare_documents(delta, manifest, snapshots.get)


def test_exact_literals_shared_runs_and_locators_survive_real_package_and_octet_detection():
    shared = f'<sst xmlns="{S}"><si><r><t>  références </t></r><r><t>requises &amp; délai</t></r></si></sst>'
    rows = '<row r="3">' + cell('C3', '1', 'b') + cell('B3', '9007199254740993.00', 'n') + cell('A3', '0', 's') + '</row>'
    body = xlsx(rows=rows, shared=shared)
    for mime in (XLSX_MIME, 'application/octet-stream'):
        parsed, reason = parse(body, mime)
        assert parsed.parse_status == 'complete' and reason == 'text_layer_extracted'
        assert parsed.extractor_version == EXTRACTOR
        assert parsed.content_sha256 == hashlib.sha256(body).hexdigest()
        assert [p.text for p in parsed.passages] == ['  références requises & délai', '9007199254740993.00', '1']
        assert [p.locator for p in parsed.passages] == ['part:xl/worksheets/sheet1.xml/sheet:Conditions/cell:' + x for x in ('A3/text', 'B3/n', 'C3/b')]
        assert all(p.page is None for p in parsed.passages)


def test_cell_changes_moves_and_renamed_sheets_are_material_but_package_names_are_not():
    result = comparison(xlsx(), xlsx('5 references required'))
    assert result.status == 'changed'
    assert result.changes[0].before[0].text == '3 references required'
    assert result.changes[0].after[0].text == '5 references required'
    assert comparison(xlsx(), xlsx(rows='<row r="1">' + cell('B1', '3 references required') + '</row>')).status == 'changed'
    rows = '<row r="1">' + cell('A1', '3 references required') + '</row>'
    assert comparison(xlsx(), xlsx(sheets=[('Conditions', 'renamed.xml', 'visible', rows)])).status == 'unchanged'
    assert comparison(xlsx(), xlsx(sheets=[('New conditions', 'sheet1.xml', 'visible', rows)])).status == 'changed'


def test_representational_order_and_shared_indices_do_not_create_changes():
    rows = '<row r="1">' + cell('A1', '0', 's') + '</row>'
    before = xlsx(rows=rows, shared=f'<sst xmlns="{S}"><si><t>3 references required</t></si></sst>')
    assert comparison(before, xlsx()).status == 'unchanged'
    sheets = [('Zulu', 'z.xml', 'visible', rows), ('Änderung', 'a.xml', 'visible', rows)]
    shared = f'<sst xmlns="{S}"><si><t>literal condition</t></si></sst>'
    assert comparison(xlsx(sheets=sheets, shared=shared), xlsx(sheets=list(reversed(sheets)), shared=shared)).status == 'unchanged'


def test_formula_text_is_distinct_from_untrusted_cached_results_and_blocks_comparison():
    rows = '<row r="1">' + cell('A1', 'Visible requirements') + cell('B1', '999', 'n', formula='SUM(C1:C3)') + '</row>'
    body = xlsx(rows=rows)
    parsed, reason = parse(body, XLSX_MIME)
    assert parsed.parse_status == 'partial' and reason == 'xlsx_literal_values_only'
    assert [p.text for p in parsed.passages] == ['Visible requirements', 'SUM(C1:C3)']
    assert parsed.passages[1].locator.endswith('/cell:B1/formula')
    assert comparison(body, xlsx()).status == 'unavailable'


@pytest.mark.parametrize('construct', ['hidden', 'merge', 'link', 'format', 'rich', 'date', 'error'])
def test_unrendered_or_unsupported_constructs_keep_literal_evidence_but_prevent_false_unchanged(construct):
    rows = '<row r="1">' + cell('A1', '3 references required') + '</row>'
    options = {}
    if construct == 'hidden':
        options['sheets'] = [('Conditions', 'sheet1.xml', 'hidden', rows)]
    elif construct == 'merge':
        options['parts'] = {'xl/worksheets/sheet1.xml': worksheet(rows, after='<mergeCells><mergeCell ref="A1:B1"/></mergeCells>')}
    elif construct == 'link':
        options['parts'] = {'xl/worksheets/_rels/sheet1.xml.rels': f'<Relationships xmlns="{PKG}"><Relationship Id="link" Type="{R}/hyperlink" TargetMode="External" Target="https://example.invalid/never-fetch"/></Relationships>'}
    elif construct == 'format':
        options['styles'] = f'<styleSheet xmlns="{S}"><cellXfs><xf numFmtId="14"/></cellXfs></styleSheet>'
    elif construct == 'rich':
        options['rows'] = '<row r="1"><c r="A1" t="inlineStr"><is><r><rPr><strike/></rPr><t>3 references required</t></r></is></c></row>'
    else:
        options['rows'] = '<row r="1">' + cell('A1', '2026-09-27T10:00:00Z' if construct == 'date' else '#DIV/0!', 'd' if construct == 'date' else 'e') + '</row>'
    body = xlsx(**options)
    parsed, _ = parse(body, XLSX_MIME)
    assert parsed.parse_status == 'partial' and parsed.passages
    stream = BytesIO(body)
    with ZipFile(stream, 'a') as archive:
        archive.comment = b'new source observation'
    assert comparison(body, stream.getvalue()).status == 'unavailable'


@pytest.mark.parametrize('content', [
    '<row r="1">' + cell('A1', '0', 's') + '</row>',
    '<row r="1">' + cell('A1', 'bad', 'n') + '</row>',
    '<row r="1">' + cell('A1', 'NaN', 'n') + '</row>',
    '<row r="1">' + cell('A1', '3', 'b') + '</row>',
    '<row r="1">' + cell('A1', '2026-02-30', 'd') + '</row>',
    '<row r="1">' + cell('A1', 'x', attributes='s="1"') + '</row>',
    '<row r="1">' + cell('A1', 'x') * 2 + '</row>',
    '<row r="1">' + cell('A2', 'x') + '</row>',
    '<row r="1">' + cell('XFE1', 'x') + '</row>',
    '<row r="1048577">' + cell('A1048577', 'x') + '</row>',
    '<row r="1">' + cell('A1', 'x') + '</row><row r="1"/>',
    '<row r="1"><c r="A1"><v>1</v><v>2</v></c></row>',
])
def test_malformed_or_ambiguous_cells_fail_without_authoritative_partial_output(content):
    body = xlsx(rows=content)
    parsed, reason = parse(body, XLSX_MIME)
    assert parsed.parse_status == 'failed' and reason == 'xlsx_extraction_failed'
    assert not parsed.passages and parsed.content_sha256 == hashlib.sha256(body).hexdigest()


@pytest.mark.parametrize('parts', [
    {'../escape.xml': 'unsafe'}, {'xl/vbaProject.bin': 'macro'},
    {'xl/worksheets/SHEET1.xml': 'ambiguous'},
    {'xl/workbook.xml': '<!DOCTYPE x [<!ENTITY x "expanded">]><x>&x;</x>'},
    {'xl/workbook.xml': '<broken'},
    {'xl/worksheets/sheet1.xml': f'<worksheet xmlns="{S}"><sheetData/><sheetData/></worksheet>'},
    {'xl/_rels/workbook.xml.rels': f'<Relationships xmlns="{PKG}"><Relationship Id="s0" Type="{R}/worksheet" TargetMode="External" Target="https://example.invalid/never"/></Relationships>'},
    {'[Content_Types].xml': f'<Types xmlns="{CT}"><Override PartName="/xl/workbook.xml" ContentType="application/vnd.ms-excel.sheet.macroEnabled.main+xml"/></Types>'},
    {'xl/unused.bin': b'x' * 1000000},
])
def test_unsafe_packages_fail_in_memory_and_preserve_original_hash(parts, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    body = xlsx(parts=parts)
    parsed, reason = parse(body, XLSX_MIME)
    assert parsed.parse_status == 'failed' and reason == 'xlsx_extraction_failed'
    assert not parsed.passages and parsed.content_sha256 == hashlib.sha256(body).hexdigest()
    assert list(tmp_path.iterdir()) == []


def test_duplicate_zip_crc_encryption_and_quotas_fail_closed():
    stream = BytesIO(xlsx(compression=ZIP_STORED))
    with ZipFile(stream, 'a') as archive, pytest.warns(UserWarning):
        archive.writestr('xl/workbook.xml', 'duplicate')
    encrypted = bytearray(xlsx(compression=ZIP_STORED))
    encrypted[encrypted.index(b'PK\x03\x04') + 6] |= 1
    encrypted[encrypted.index(b'PK\x01\x02') + 8] |= 1
    for body in [stream.getvalue(), bytes(encrypted),
                 xlsx(compression=ZIP_STORED).replace(b'3 references required', b'5 references required'),
                 xlsx(parts={f'part{i}.xml': 'tiny' for i in range(260)}),
                 xlsx(parts={'xl/workbook.xml': ' ' * (4 * 1024 * 1024 + 1)}, compression=ZIP_STORED)]:
        parsed, reason = parse(body, XLSX_MIME)
        assert parsed.parse_status == 'failed' and reason == 'xlsx_extraction_failed' and not parsed.passages
    rows = ''.join(f'<row r="{i}">' + cell(f'A{i}', 'condition') + '</row>' for i in range(1, 2002))
    parsed, reason = parse(xlsx(rows=rows, compression=ZIP_STORED), XLSX_MIME)
    assert parsed.parse_status == 'failed' and reason == 'parsed_limit_exceeded' and not parsed.passages


def test_spreadsheet_whitespace_is_material_and_excel_character_escapes_are_partial():
    assert comparison(xlsx(" a  b"), xlsx("a b")).status == "changed"
    parsed, _ = parse(xlsx("Terms_x000D_conditions"), XLSX_MIME)
    assert parsed.parse_status == "partial"
    assert parsed.passages[0].text == "Terms_x000D_conditions"
