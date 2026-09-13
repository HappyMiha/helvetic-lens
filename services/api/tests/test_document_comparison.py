"""Literal procurement changes, private evidence binding and incomplete readers."""

import hashlib
from uuid import uuid4

import pytest
from pydantic import ValidationError
from test_document_sets import SCOPE, item, manifest

from helvetic_lens.document_comparison import (
    ParsedDocument,
    Passage,
    compare_documents,
    reconcile_documents,
    text_fingerprint,
)
from helvetic_lens.document_sets import reconcile


def document(*texts, revision="1", **extra):
    passages = tuple(Passage(locator=f"page:1/paragraph:{i + 1}", page=1, text=text)
                     for i, text in enumerate(texts))
    data = dict(snapshot_id=uuid4(), access_scope_id=SCOPE, source_id="simap",
                dossier_id="project-1", item_id="requirements",
                content_sha256=hashlib.sha256(revision.encode()).hexdigest(),
                text_sha256=text_fingerprint(passages), extractor_version="tested-parser-v1",
                language="en", parse_status="complete", passages=passages)
    data.update(extra)
    return ParsedDocument.model_validate(data)


def source(doc):
    return item(snapshot_id=doc.snapshot_id, content_sha256=doc.content_sha256,
                text_sha256=doc.text_sha256)


def pair(before, after):
    previous = reconcile(None, manifest(0, source(before))).state
    current = manifest(1, source(after))
    delta = next(row for row in reconcile(previous, current).deltas if row.kind == "replaced")
    snapshots = {doc.snapshot_id: doc for doc in (before, after)}
    return previous, current, delta, snapshots


def test_full_manifest_revision_carries_exact_deadline_and_requirement_evidence():
    before = document("Offer deadline: 20 Sep", "3 references required", "Original conditions")
    after = document("Offer deadline: 27 Sep", "5 references required", "Original conditions", revision="2")
    previous, current, _, snapshots = pair(before, after)
    qa = item("qa-v3", kind="qa", content="c")
    current = current.model_copy(update={"items": (*current.items, qa)})
    result = reconcile_documents(previous, current, snapshots.get)
    assert {(d.item_id, d.kind, d.material) for d in result.reconciliation.deltas} == {
        ("requirements", "replaced", True), ("qa-v3", "added", True),
    }
    comparison = result.comparisons[0]
    assert comparison.status == "changed" and not comparison.truncated
    change, = comparison.changes
    assert [p.text for p in change.before] == ["Offer deadline: 20 Sep", "3 references required"]
    assert [p.text for p in change.after] == ["Offer deadline: 27 Sep", "5 references required"]
    assert change.before[1].snapshot_id == before.snapshot_id
    assert change.after[1].snapshot_id == after.snapshot_id
    assert change.after[1].locator == "page:1/paragraph:2"
    assert change.after[1].page == 1


@pytest.mark.parametrize(("old", "new"), [
    ("5 references", "3 references"), ("must have ISO 27001", "must not have ISO 27001"),
    ("Product ABC", "Product abc"), ("3. Required capacity", "5. Required capacity"),
    ("Wert: CHF 1.000", "Wert: CHF 1,000"), ("Références: 3", "Références: 5"),
    ("Referenze obbligatorie", "Referenze facoltative"),
])
def test_numbers_negations_case_punctuation_and_leading_labels_are_not_layout(old, new):
    before, after = document(old), document(new, revision="2")
    _, current, delta, snapshots = pair(before, after)
    value = compare_documents(delta, current, snapshots.get)
    assert value.status == "changed"
    assert value.changes[0].before[0].text == old
    assert value.changes[0].after[0].text == new


def test_whitespace_only_binary_replacement_stays_material_without_inventing_text_change():
    before = document("3 references\nrequired")
    after = document("3  references required", revision="2")
    previous, current, _, snapshots = pair(before, after)
    value = reconcile_documents(previous, current, snapshots.get)
    assert value.comparisons[0].status == "unchanged"
    assert value.reconciliation.deltas[0].material
    assert value.reconciliation.deltas[0].kind == "replaced"


def test_reordered_paragraphs_remain_visible_and_are_not_described_as_new_requirement():
    before = document("A applies", "B applies", "C applies")
    after = document("B applies", "A applies", "C applies", revision="2")
    _, current, delta, snapshots = pair(before, after)
    value = compare_documents(delta, current, snapshots.get)
    assert value.status == "changed"
    assert {change.kind for change in value.changes} == {"added", "removed"}
    # No claim of semantic significance, classification or qualification count.
    assert all(set(change.model_dump()) == {"kind", "before", "after"} for change in value.changes)


@pytest.mark.parametrize(("field", "replacement", "reason"), [
    ("access_scope_id", uuid4(), "evidence_mismatch"),
    ("dossier_id", "different-dossier", "evidence_mismatch"),
    ("source_id", "other-source", "evidence_mismatch"),
    ("item_id", "other-document", "evidence_mismatch"),
    ("snapshot_id", uuid4(), "evidence_mismatch"),
    ("content_sha256", "f" * 64, "evidence_mismatch"),
    ("parse_status", "partial", "parse_incomplete"),
    ("parse_status", "failed", "parse_incomplete"),
    ("extractor_version", "new-parser", "extractor_changed"),
    ("language", "fr", "language_changed"),
    ("text_sha256", "f" * 64, "evidence_mismatch"),
])
def test_scope_exact_snapshot_parser_and_language_mismatch_never_exposes_text(field, replacement, reason):
    before, after = document("Private original"), document("Private revision", revision="2")
    _, current, delta, snapshots = pair(before, after)
    snapshots[before.snapshot_id] = before.model_copy(update={field: replacement})
    value = compare_documents(delta, current, snapshots.get)
    assert value.status == "unavailable" and value.reason == reason
    assert not value.changes and "Private" not in value.model_dump_json()


def test_reader_rechecks_both_versions_on_each_comparison_and_denial_is_not_removal():
    before, after = document("Private original"), document("Private revision", revision="2")
    previous, current, _, snapshots = pair(before, after)
    assert reconcile_documents(previous, current, snapshots.get).comparisons[0].status == "changed"
    snapshots.pop(before.snapshot_id)  # Rights revoked after the earlier read.
    value = reconcile_documents(previous, current, snapshots.get)
    assert value.comparisons[0].reason == "read_unavailable"
    assert all(delta.kind != "removed" for delta in value.reconciliation.deltas)
    assert "Private" not in value.comparisons[0].model_dump_json()


def test_store_failure_propagates_instead_of_persisting_a_successful_diff():
    before, after = document("A"), document("B", revision="2")
    _, current, delta, _ = pair(before, after)

    def load(_):
        raise OSError("private store temporarily unavailable")

    with pytest.raises(OSError):
        compare_documents(delta, current, load)


def test_self_consistent_but_different_parsed_projection_cannot_replace_the_recorded_original():
    before, after = document("Original"), document("Revision", revision="2")
    _, current, delta, snapshots = pair(before, after)
    altered = (Passage(locator="new-locator", text="Forged source text"),)
    snapshots[before.snapshot_id] = before.model_copy(update={
        "passages": altered, "text_sha256": text_fingerprint(altered),
    })
    value = compare_documents(delta, current, snapshots.get)
    assert value.status == "unavailable" and value.reason == "evidence_mismatch"
    assert "Forged" not in value.model_dump_json()


def test_excerpts_and_hunks_are_bounded_without_reporting_an_incomplete_diff_as_complete():
    texts = [text for i in range(110) for text in (f"unchanged anchor {i}", f"old condition {i}")]
    before = document(*texts)
    after = document(*(text.replace("old condition", "new condition") for text in texts), revision="2")
    _, current, delta, snapshots = pair(before, after)
    value = compare_documents(delta, current, snapshots.get)
    assert value.total_changes == 110 and len(value.changes) == 100 and value.truncated
    before = document("a" * 4000)
    after = document("b" * 4000, revision="2")
    _, current, delta, snapshots = pair(before, after)
    value = compare_documents(delta, current, snapshots.get)
    assert value.truncated and value.changes[0].before[0].truncated
    assert len(value.changes[0].before[0].text) == 2000


def test_parse_integrity_rejects_corruption_empty_complete_and_duplicate_locators():
    valid = document("Original")
    with pytest.raises(ValidationError):
        ParsedDocument.model_validate({**valid.model_dump(), "text_sha256": "a" * 64})
    with pytest.raises(ValidationError):
        document()
    duplicate = (valid.passages[0], valid.passages[0])
    with pytest.raises(ValidationError):
        document(passages=duplicate, text_sha256=text_fingerprint(duplicate))
    with pytest.raises(ValidationError):
        Passage(locator="p1", text=" ")


def test_added_document_and_partial_extraction_do_not_call_reader_or_invent_prior_text():
    original = document("original")
    previous = reconcile(None, manifest(0, source(original))).state
    current = manifest(1, source(original), item("new-qa", content="b", kind="qa"))
    calls = []
    result = reconcile_documents(previous, current, lambda key: calls.append(key))
    assert not result.comparisons and not calls
    incomplete = manifest(2, item(content="c", parse="failed"))
    value = reconcile_documents(result.reconciliation.state, incomplete, lambda key: calls.append(key))
    assert value.comparisons[0].reason == "parse_incomplete" and not calls
