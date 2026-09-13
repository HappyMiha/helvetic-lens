import hashlib
from uuid import uuid4

import pytest
from pdf_fixture import make_pdf
from test_document_comparison import pair
from test_document_sets import SCOPE

from helvetic_lens.document_comparison import compare_documents
from helvetic_lens.document_parsing import MAX_DOCUMENT_BYTES, parse_document


def parse(body, mime="application/pdf"):
    return parse_document(body, content_type=mime, snapshot_id=uuid4(),
                          access_scope_id=SCOPE, source_id="simap", dossier_id="project-1",
                          item_id="requirements", language="en")


def test_real_pdf_text_revision_reaches_comparison_with_byte_hashes_and_page_locators():
    old_bytes = make_pdf(["3 references required", "Offer deadline: 20 Sep"])
    new_bytes = make_pdf(["5 references required", "Offer deadline: 27 Sep"])
    old, old_reason = parse(old_bytes)
    new, new_reason = parse(new_bytes, "application/octet-stream")
    assert old_reason == new_reason == "text_layer_extracted"
    assert old.content_sha256 == hashlib.sha256(old_bytes).hexdigest()
    assert new.content_sha256 == hashlib.sha256(new_bytes).hexdigest()
    _, current, delta, snapshots = pair(old, new)
    compared = compare_documents(delta, current, snapshots.get)
    assert compared.status == "changed"
    change, = compared.changes
    assert [p.text for p in change.before] == ["3 references required", "Offer deadline: 20 Sep"]
    assert [p.text for p in change.after] == ["5 references required", "Offer deadline: 27 Sep"]
    assert change.after[1].page == 2
    assert change.after[1].locator == "page:2/block:1"


def test_missing_page_text_prevents_false_complete_document_comparison():
    parsed, reason = parse(make_pdf(["Readable text", ""]))
    assert parsed.parse_status == "partial" and reason == "page_without_text"
    assert len(parsed.passages) == 1


@pytest.mark.parametrize("body", [b"%PDF broken", make_pdf(["", ""])])
def test_broken_or_scan_without_text_preserves_content_hash_and_does_not_invent_content(body):
    parsed, _ = parse(body)
    assert parsed.parse_status == "failed" and not parsed.passages
    assert parsed.content_sha256 == hashlib.sha256(body).hexdigest()


def test_encrypted_pdf_is_not_decrypted_or_treated_as_an_empty_document():
    parsed, reason = parse(make_pdf(["Private requirements"], password="secret"))
    assert parsed.parse_status == "failed" and reason == "pdf_extraction_failed"
    assert not parsed.passages


def test_utf8_source_lines_remain_exact_and_links_point_to_original_line_numbers():
    body = "  3 références requises  \r\n\r\nNe pas soumettre une offre ici.\n".encode()
    parsed, _ = parse(body, "text/plain; charset=utf-8")
    assert parsed.parse_status == "complete"
    assert [p.locator for p in parsed.passages] == ["line:1", "line:3"]
    assert parsed.passages[0].text == "  3 références requises  "
    assert all(p.page is None for p in parsed.passages)


@pytest.mark.parametrize(("body", "mime", "reason"), [
    (b"PK zip content", "application/zip", "unsupported_format"),
    (b"<form><input type=password></form>", "text/html", "unsupported_format"),
    (b"looks like text", "application/octet-stream", "unsupported_format"),
    (b"invalid \xff", "text/plain", "text_extraction_failed"),
    (b"ASCII text", "text/plain; charset=iso-8859-1", "text_extraction_failed"),
    (b"hidden\x00text", "text/plain", "text_extraction_failed"),
    (b" ", "text/plain", "no_extractable_text"),
])
def test_unsupported_binary_login_html_and_bad_text_do_not_create_comparable_evidence(body, mime, reason):
    parsed, observed = parse(body, mime)
    assert parsed.parse_status == "failed" and not parsed.passages and observed == reason


def test_bounds_reject_bytes_and_preserve_failed_parse_state_for_excessive_passages():
    with pytest.raises(ValueError):
        parse(b"x" * (MAX_DOCUMENT_BYTES + 1), "text/plain")
    with pytest.raises(ValueError):
        parse(b"", "text/plain")
    parsed, reason = parse(b"clause\n" * 2001, "text/plain")
    assert parsed.parse_status == "failed" and reason == "parsed_limit_exceeded"
