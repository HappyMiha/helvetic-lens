import hashlib
from io import BytesIO
from zipfile import ZIP_STORED, ZipFile

import pytest
from docx_fixture import CT, PKG, R, W, docx, paragraph
from test_document_comparison import pair
from test_document_parsing import parse

from helvetic_lens.document_comparison import compare_documents
from helvetic_lens.docx_reader import DOCX_MIME


def test_docx_revision_compares_exact_text_with_original_xml_part_locators():
    old_bytes, new_bytes = docx(), docx("5 references required")
    old, reason = parse(old_bytes, DOCX_MIME)
    new, _ = parse(new_bytes, "application/octet-stream")
    assert reason == "text_layer_extracted" and old.parse_status == new.parse_status == "complete"
    assert old.content_sha256 == hashlib.sha256(old_bytes).hexdigest()
    assert old.passages[0].locator == "part:word/document.xml/document/body[1]/p[1]"
    assert old.passages[0].page is None
    _, manifest, delta, snapshots = pair(old, new)
    result = compare_documents(delta, manifest, snapshots.get)
    assert result.status == "changed"
    assert result.changes[0].before[0].text == "3 references required"
    assert result.changes[0].after[0].text == "5 references required"


def test_runs_tables_breaks_whitespace_and_non_ascii_preserve_text_order():
    content = ('<w:p><w:r><w:t xml:space="preserve">  références </w:t></w:r>'
               '<w:r><w:t>requises</w:t><w:tab/><w:t>3</w:t><w:br/><w:t>Änderung &amp; délai</w:t></w:r></w:p>'
               '<w:tbl><w:tr><w:tc>' + paragraph("Deadline") + '</w:tc><w:tc>'
               + paragraph("27 Sep") + '</w:tc></w:tr></w:tbl>')
    parsed, _ = parse(docx(content=content), DOCX_MIME)
    assert parsed.parse_status == "complete"
    assert [p.text for p in parsed.passages] == ["  références requises\t3\nÄnderung & délai", "Deadline", "27 Sep"]
    assert "/tbl[1]/tr[1]/tc[2]/p[1]" in parsed.passages[-1].locator


def test_nonbreaking_and_soft_hyphens_are_not_silently_removed_from_source_words():
    content = '<w:p><w:r><w:t>non</w:t><w:noBreakHyphen/><w:t>compliance</w:t><w:tab/><w:t>sub</w:t><w:softHyphen/><w:t>mission</w:t></w:r></w:p>'
    parsed, _ = parse(docx(content=content), DOCX_MIME)
    assert parsed.parse_status == "complete"
    assert parsed.passages[0].text == "non\u2011compliance\tsub\u00admission"


def test_referenced_headers_footers_and_notes_are_read_but_orphan_stories_are_not():
    content = (paragraph("Main requirements") + '<w:p><w:r><w:footnoteReference w:id="2"/></w:r></w:p>'
               '<w:sectPr><w:headerReference r:id="header"/><w:footerReference r:id="footer"/></w:sectPr>')
    parts = {"word/header1.xml": f'<w:hdr xmlns:w="{W}">{paragraph("Binding header")}</w:hdr>',
             "word/footer1.xml": f'<w:ftr xmlns:w="{W}">{paragraph("Binding footer")}</w:ftr>',
             "word/footnotes.xml": f'<w:footnotes xmlns:w="{W}"><w:footnote w:id="2">{paragraph("Only Swiss references")}</w:footnote>'
             f'<w:footnote w:id="9">{paragraph("Orphan must not appear")}</w:footnote></w:footnotes>',
             "word/header-orphan.xml": f'<w:hdr xmlns:w="{W}">{paragraph("Orphan header")}</w:hdr>'}
    parsed, _ = parse(docx(content=content, parts=parts,
                          relationships=(("header", "header", "header1.xml"), ("footer", "footer", "footer1.xml"),
                                         ("notes", "footnotes", "footnotes.xml")),
                          overrides=(("word/header1.xml", "header"), ("word/footer1.xml", "footer"),
                                     ("word/footnotes.xml", "footnotes"))), DOCX_MIME)
    assert parsed.parse_status == "complete"
    assert [p.text for p in parsed.passages] == ["Main requirements", "Only Swiss references", "Binding header", "Binding footer"]
    assert "footnote[id=2]/p[1]" in parsed.passages[1].locator


@pytest.mark.parametrize("markup", [
    '<w:p><w:pPr><w:numPr/></w:pPr><w:r><w:t>Numbered condition</w:t></w:r></w:p>',
    '<w:p><w:r><w:fldChar w:fldCharType="begin"/><w:instrText>DATE</w:instrText><w:t>27 Sep</w:t></w:r></w:p>',
    '<w:p><w:del><w:r><w:delText>3 references</w:delText></w:r></w:del><w:ins><w:r><w:t>5 references</w:t></w:r></w:ins></w:p>',
    '<w:p><w:r><w:drawing/></w:r></w:p>', '<w:altChunk r:id="external"/>',
])
def test_numbering_fields_tracked_edits_and_nontext_content_prevent_complete_comparison(markup):
    parsed, reason = parse(docx(content=paragraph("Visible condition") + markup), DOCX_MIME)
    assert parsed.parse_status == "partial" and reason == "docx_unsupported_constructs"
    assert parsed.passages[0].text == "Visible condition"
    other, _ = parse(docx("Changed condition"), DOCX_MIME)
    _, manifest, delta, snapshots = pair(parsed, other)
    assert compare_documents(delta, manifest, snapshots.get).status == "unavailable"


@pytest.mark.parametrize("name", ["../escape.xml", "/absolute.xml", "word\\hidden.xml", "word/../ambiguous.xml",
                                 "word/document.XML", "word/vbaProject.bin", "C:/secret.xml"])
def test_unsafe_ambiguous_or_macro_archive_entries_are_rejected_without_extraction(name, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    body = docx(parts={name: "hidden"})
    if "\\" in name:
        # ZipFile normalizes Windows separators when creating fixtures. Put the
        # actual ambiguous byte spelling back in both ZIP filename records.
        body = body.replace(name.replace("\\", "/").encode(), name.encode())
    parsed, reason = parse(body, DOCX_MIME)
    assert parsed.parse_status == "failed" and reason == "docx_extraction_failed" and not parsed.passages
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("xml", [
    '<!DOCTYPE document [<!ENTITY x "expanded">]><w:document xmlns:w="' + W + '"><w:body><w:p><w:r><w:t>&x;</w:t></w:r></w:p></w:body></w:document>',
    '<!DOCTYPE document SYSTEM "https://example.invalid/external.dtd"><w:document xmlns:w="' + W + '"><w:body/></w:document>',
    '<w:document xmlns:w="' + W + '"><w:body>' + '<w:p>' * 70 + '</w:p>' * 70 + '</w:body></w:document>',
    '<w:document xmlns:w="' + W + '"><w:body>',
])
def test_dtd_entities_depth_and_malformed_xml_do_not_return_partial_authoritative_text(xml):
    parsed, reason = parse(docx(parts={"word/document.xml": xml}), DOCX_MIME)
    assert parsed.parse_status == "failed" and reason == "docx_extraction_failed"


def test_missing_reference_encrypted_shape_wrong_main_type_and_compression_bomb_fail():
    bad = [docx(content=paragraph("Main") + '<w:sectPr><w:headerReference r:id="missing"/></w:sectPr>'),
           docx(parts={"word/unused.bin": b"x" * 1000000}),
           docx(parts={"[Content_Types].xml": f'<Types xmlns="{CT}"><Override PartName="/word/document.xml" ContentType="application/vnd.ms-word.document.macroEnabled.main+xml"/></Types>'}),
           docx(parts={"_rels/.rels": f'<Relationships xmlns="{PKG}"><Relationship Id="main" Type="{R}/officeDocument" Target="https://example.invalid/file" TargetMode="External"/></Relationships>'}),
           b"not a zip"]
    for body in bad:
        parsed, reason = parse(body, DOCX_MIME)
        assert parsed.parse_status == "failed" and reason == "docx_extraction_failed"


def test_member_xml_and_common_passage_budgets_remain_bounded():
    for body, expected in [
        (docx(parts={f"part{i}.xml": "tiny" for i in range(260)}), "docx_extraction_failed"),
        (docx(parts={"word/document.xml": " " * (4 * 1024 * 1024 + 1)}, compression=ZIP_STORED), "docx_extraction_failed"),
        (docx(content=paragraph("condition") * 2001, compression=ZIP_STORED), "parsed_limit_exceeded"),
    ]:
        parsed, reason = parse(body, DOCX_MIME)
        assert parsed.parse_status == "failed" and reason == expected and not parsed.passages


def test_duplicate_member_and_corrupt_crc_are_not_accepted():
    stream = BytesIO(docx(compression=ZIP_STORED))
    with ZipFile(stream, "a") as archive, pytest.warns(UserWarning):
        archive.writestr("word/document.xml", "duplicate")
    parsed, _ = parse(stream.getvalue(), DOCX_MIME)
    assert parsed.parse_status == "failed"
    broken = docx(compression=ZIP_STORED).replace(b"3 references required", b"5 references required")
    parsed, _ = parse(broken, DOCX_MIME)
    assert parsed.parse_status == "failed"


def test_encrypted_zip_flag_is_rejected_before_decryption_or_parsing():
    body = bytearray(docx(compression=ZIP_STORED))
    local_header, central_header = body.index(b"PK\x03\x04"), body.index(b"PK\x01\x02")
    body[local_header + 6] |= 1
    body[central_header + 8] |= 1
    parsed, reason = parse(bytes(body), DOCX_MIME)
    assert parsed.parse_status == "failed" and reason == "docx_extraction_failed"
    assert not parsed.passages


@pytest.mark.parametrize("xml", [
    '<?xml version="1.0" encoding="iso-8859-1"?><w:document xmlns:w="' + W + '"><w:body>' + paragraph("références") + '</w:body></w:document>',
    ('<?xml version="1.0" encoding="utf-16"?><!DOCTYPE document [<!ENTITY x "expanded">]><document/>').encode("utf-16"),
])
def test_other_xml_encodings_cannot_bypass_entity_checks_or_change_source_text(xml):
    parsed, reason = parse(docx(parts={"word/document.xml": xml}), DOCX_MIME)
    assert parsed.parse_status == "failed" and reason == "docx_extraction_failed"
