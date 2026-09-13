"""Independent MV2-044 cases: gaps and retrieval noise cannot rewrite evidence."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from helvetic_lens.document_sets import DocumentItem, Manifest, reconcile

SCOPE = UUID("90000000-0000-0000-0000-000000000001")
AT = datetime(2026, 9, 12, 12, tzinfo=UTC)


def item(key="requirements", *, content="a", access="available", kind="document", lifecycle="present", parse="complete", **extra):
    data = {
        "item_id": key, "kind": kind, "title": key,
        "official_url": "https://www.simap.ch/en/project-detail/official-dossier",
        "access": access, "lifecycle": lifecycle,
    }
    if access == "available":
        data.update(content_sha256=content * 64, snapshot_id=uuid4(), parse_status=parse)
        if parse == "complete":
            data["text_sha256"] = content * 64
    data.update(extra)
    return DocumentItem.model_validate(data)


def manifest(step, *items, coverage="complete", **extra):
    data = {
        "observation_id": uuid4(), "source_id": "simap", "dossier_id": "project-1",
        "access_scope_id": SCOPE, "observed_at": AT + timedelta(minutes=step),
        "coverage": coverage, "items": items,
    }
    data.update(extra)
    return Manifest.model_validate(data)


def changes(result):
    return [(delta.item_id, delta.kind, delta.material) for delta in result.deltas]


def test_initial_capture_is_a_baseline_then_new_qa_and_replaced_file_are_distinct():
    original = item()
    baseline = reconcile(None, manifest(0, original))
    assert baseline.baseline and not baseline.deltas
    replacement = item(content="b")
    added_qa = item("qa-round-3", content="c", kind="qa")
    updated = reconcile(baseline.state, manifest(1, replacement, added_qa))
    assert changes(updated) == [("qa-round-3", "added", True), ("requirements", "replaced", True)]
    delta = updated.deltas[1]
    assert delta.before_snapshot_id == original.snapshot_id
    assert delta.after_snapshot_id == replacement.snapshot_id
    assert delta.before_content_sha256 == "a" * 64
    assert delta.after_content_sha256 == "b" * 64
    assert delta.parsed_comparison_available


def test_reordering_polling_time_and_new_snapshot_same_bytes_are_not_material():
    documents = (item("one"), item("two", content="b"))
    state = reconcile(None, manifest(0, *documents)).state
    updated_one = item("one", title="Renamed display label", source_revision="new-etag")
    updated = reconcile(state, manifest(1, documents[1], updated_one))
    assert not updated.deltas
    assert updated.state.documents[0].current.title == "Renamed display label"


def test_denial_retains_last_content_and_change_during_gap_is_detected_on_return():
    original = item()
    state = reconcile(None, manifest(0, original)).state
    denied = reconcile(state, manifest(1, item(access="denied", lifecycle="unknown")))
    assert changes(denied) == [("requirements", "access_unavailable", False)]
    assert denied.state.documents[0].lifecycle == "present"
    assert denied.state.documents[0].last_available == original
    still_denied = reconcile(denied.state, manifest(2, item(access="denied", lifecycle="unknown")))
    assert not still_denied.deltas
    replacement = item(content="d", parse="failed")
    returned = reconcile(still_denied.state, manifest(3, replacement))
    assert changes(returned) == [
        ("requirements", "access_restored", False), ("requirements", "replaced", True),
    ]
    assert returned.deltas[1].before_snapshot_id == original.snapshot_id
    assert not returned.deltas[1].parsed_comparison_available


@pytest.mark.parametrize("coverage", ["partial", "unavailable"])
def test_partial_page_or_outage_is_not_removal_and_unchanged_return_is_not_addition(coverage):
    original = item()
    state = reconcile(None, manifest(0, original)).state
    gap = reconcile(state, manifest(1, coverage=coverage))
    assert changes(gap) == [("requirements", "access_unavailable", False)]
    assert gap.state.documents[0].lifecycle == "present"
    returned = reconcile(gap.state, manifest(2, original))
    assert changes(returned) == [("requirements", "access_restored", False)]


def test_complete_empty_listing_proves_removal_once_and_return_is_reinstatement():
    original = item()
    state = reconcile(None, manifest(0, original)).state
    removed = reconcile(state, manifest(1))
    assert changes(removed) == [("requirements", "removed", True)]
    assert removed.state.documents[0].last_available == original
    absent_again = reconcile(removed.state, manifest(2))
    assert not absent_again.deltas
    returned = reconcile(absent_again.state, manifest(3, original))
    assert changes(returned) == [
        ("requirements", "reinstated", True), ("requirements", "access_restored", False),
    ]


def test_explicit_withdrawal_is_not_inferred_from_403_and_can_retain_permitted_bytes():
    original = item()
    state = reconcile(None, manifest(0, original)).state
    withdrawn_item = DocumentItem.model_validate({**original.model_dump(), "lifecycle": "withdrawn"})
    withdrawn = reconcile(state, manifest(1, withdrawn_item))
    assert changes(withdrawn) == [("requirements", "withdrawn", True)]
    assert withdrawn.state.documents[0].access == "available"
    gap = reconcile(withdrawn.state, manifest(2, item(access="denied", lifecycle="unknown")))
    assert gap.state.documents[0].lifecycle == "withdrawn"
    assert all(not delta.material for delta in gap.deltas)
    resumed = reconcile(gap.state, manifest(3, withdrawn_item))
    assert changes(resumed) == [("requirements", "access_restored", False)]
    reinstated = reconcile(resumed.state, manifest(4, original))
    assert changes(reinstated) == [("requirements", "reinstated", True)]


def test_first_visibility_after_incomplete_baseline_does_not_claim_new_publication():
    state = reconcile(None, manifest(0, coverage="partial")).state
    discovery = reconcile(state, manifest(1, item()))
    assert changes(discovery) == [("requirements", "discovered", False)]
    new_qa = reconcile(discovery.state, manifest(2, item(), item("qa", kind="qa")))
    assert changes(new_qa) == [("qa", "added", True)]


def test_last_complete_listing_remains_absence_evidence_across_a_partial_page():
    state = reconcile(None, manifest(0)).state
    state = reconcile(state, manifest(1, coverage="partial")).state
    added = reconcile(state, manifest(2, item(), coverage="partial"))
    assert changes(added) == [("requirements", "added", True)]


def test_failed_ocr_cannot_claim_requirements_unchanged_and_retry_is_not_source_change():
    original = item()
    state = reconcile(None, manifest(0, original)).state
    failed = reconcile(state, manifest(1, item(parse="failed")))
    assert changes(failed) == [("requirements", "parse_degraded", False)]
    recovered = reconcile(failed.state, manifest(2, item()))
    assert changes(recovered) == [("requirements", "parse_recovered", False)]
    assert not recovered.deltas[0].parsed_comparison_available


@pytest.mark.parametrize("field,value", [
    ("source_id", "other-source"), ("dossier_id", "project-2"), ("access_scope_id", uuid4()),
])
def test_cross_source_dossier_or_private_scope_cannot_reuse_old_snapshots(field, value):
    state = reconcile(None, manifest(0, item())).state
    with pytest.raises(ValueError, match="private access scopes"):
        reconcile(state, manifest(1, item(), **{field: value}))


def test_exact_replay_is_idempotent_but_conflicting_identity_and_older_observation_fail():
    original = manifest(0, item("one"), item("two"))
    state = reconcile(None, original).state
    reordered = Manifest.model_validate({**original.model_dump(), "items": original.items[::-1]})
    assert not reconcile(state, reordered).deltas
    with pytest.raises(ValueError, match="Conflicting payload"):
        reconcile(state, manifest(0, item(content="b"), observation_id=original.observation_id))
    with pytest.raises(ValueError, match="must advance"):
        reconcile(state, manifest(-1, item(content="b")))


@pytest.mark.parametrize("url", [
    "https://www.simap.ch/file?token=secret", "https://user:secret@www.simap.ch/file",
    "javascript:alert(1)", "http://www.simap.ch/file", "https://www.simap.ch/file#token",
])
def test_ephemeral_or_unsafe_url_is_not_persisted_as_authoritative_evidence(url):
    with pytest.raises(ValidationError, match="stable HTTPS"):
        item(official_url=url)


def test_duplicate_items_ambiguous_time_and_denied_content_claims_are_rejected():
    with pytest.raises(ValidationError, match="Duplicate document"):
        manifest(0, item(), item())
    with pytest.raises(ValidationError, match="timezone aware"):
        manifest(0, observed_at=AT.replace(tzinfo=None))
    with pytest.raises(ValidationError, match="cannot claim retrieved"):
        item(access="denied", content_sha256="a" * 64)
    with pytest.raises(ValidationError, match="requires successful"):
        item(parse="failed", text_sha256="a" * 64)
    state = reconcile(None, manifest(0, item())).state
    with pytest.raises(ValueError, match="kind changed"):
        reconcile(state, manifest(1, item(kind="qa")))
