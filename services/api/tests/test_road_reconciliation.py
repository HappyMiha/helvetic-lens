from dataclasses import replace
from datetime import timedelta

import pytest
from test_road_feed import NOW, STAMP, feed, record, situation

from helvetic_lens import road_reconciliation
from helvetic_lens.road_feed import RoadFeedError, decode_road_feed
from helvetic_lens.road_reconciliation import reconcile_road_snapshot


def snapshot(xml=None, *, minute=0):
    stamp = (NOW + timedelta(minutes=minute)).isoformat()
    text = (feed() if xml is None else xml).replace(STAMP, stamp)
    return decode_road_feed(text.encode(), received_at=NOW + timedelta(minutes=minute))


def apply(previous=None, xml=None, *, minute=0, mode="full", continuous=True):
    return reconcile_road_snapshot(previous, snapshot(xml, minute=minute), mode=mode, continuous=continuous)


def test_creation_mutation_and_explicit_revocation_keep_identity_and_history():
    original, changes = apply(xml=feed(record() + record(identifier="lanes", code="laneClosures")))
    assert [change.kind for change in changes] == ["created"]
    updated, changes = apply(original, feed(record(code="narrowLanes")), minute=1, mode="delta")
    assert [change.kind for change in changes] == ["material_changed"]
    cancelled, changes = apply(updated, feed(record(code="narrowLanes", cancelled=True)), minute=2, mode="delta")
    assert [change.kind for change in changes] == ["revoked"]
    assert len(original.situations[0].situation.records) == 2
    assert not updated.situations[0].situation.cancelled
    assert cancelled.situations[0].situation.cancelled
    assert original.situations[0].situation.development_id == changes[0].development_id


def test_same_content_and_new_provider_clock_only_refresh_evidence():
    before, _ = apply()
    after, changes = apply(before, minute=1)
    assert [c.kind for c in changes] == ["source_refreshed"]
    assert before.snapshot_hash != after.snapshot_hash
    assert before.situations[0].seen_at < after.situations[0].seen_at
    assert changes[0].previous_hash == changes[0].current_hash


def test_continuous_delta_does_not_remove_unseen_situations_or_refresh_their_clock():
    before, _ = apply()
    after, changes = apply(before, feed(situations=""), minute=1, mode="delta")
    assert changes == () and after.situations == before.situations
    assert after.published_at > before.published_at
    assert after.situations[0].seen_at == NOW


@pytest.mark.parametrize(("mode", "continuous"), [("full", True), ("full", False), ("delta", False)])
def test_full_disappearance_or_delta_gap_is_unavailable_not_reopened(mode, continuous):
    before, _ = apply()
    after, changes = apply(before, feed(situations=""), minute=1, mode=mode, continuous=continuous)
    assert [c.kind for c in changes] == ["source_unavailable"]
    assert not after.situations[0].present and not after.situations[0].situation.cancelled
    assert after.situations[0].situation.records[0].kind == "road_closure"
    assert after.situations[0].seen_at == before.situations[0].seen_at
    repeated, changes = apply(after, feed(situations=""), minute=2, mode=mode, continuous=continuous)
    assert changes == () and repeated.situations == after.situations


def test_restored_evidence_and_source_clearance_are_distinct_from_physical_reopening():
    before, _ = apply()
    missing, _ = apply(before, feed(situations=""), minute=1)
    restored, changes = apply(missing, minute=2)
    assert [c.kind for c in changes] == ["source_restored"]
    assert restored.situations[0].situation.records[0].kind == "road_closure"
    cleared, changes = apply(restored, feed(record(code="roadCleared")), minute=3)
    assert [c.kind for c in changes] == ["material_changed"]
    assert cleared.situations[0].situation.records[0].kind == "source_clearance"


def test_delta_after_gap_only_restores_explicitly_observed_events():
    before, _ = apply(xml=feed(situations=situation() + situation(identifier="other")))
    after, changes = apply(before, minute=1, mode="delta", continuous=False)
    assert {c.source_id: c.kind for c in changes} == {"event-1": "source_refreshed", "other": "source_unavailable"}
    assert {e.situation.source_id: e.present for e in after.situations} == {"event-1": True, "other": False}


def test_explicit_partial_clause_cancellation_is_only_a_material_change():
    before, _ = apply(xml=feed(record() + record(identifier="other")))
    after, changes = apply(before, feed(record(cancelled=True) + record(identifier="other")), minute=1)
    assert [c.kind for c in changes] == ["material_changed"]
    assert not after.situations[0].situation.cancelled


@pytest.mark.parametrize(("mode", "continuous", "code"), [
    ("delta", True, "road_full_baseline_required"),
    ("other", True, "road_reconciliation_mode"),
    ("full", None, "road_reconciliation_mode"),
])
def test_requires_valid_explicit_retrieval_mode_and_full_baseline(mode, continuous, code):
    with pytest.raises(RoadFeedError, match=code):
        apply(mode=mode, continuous=continuous)


@pytest.mark.parametrize(("xml", "minute", "code"), [
    (feed(), 0, "road_publication_rollback"),
    (feed(record(code="roadCleared")), 1, "road_conflicting_revision"),
    (feed().replace("test-supplier", "another-supplier"), 2, "road_reconciliation_supplier"),
    (feed().replace("2026-09-13T09:00:00Z", "2026-09-13T09:01:00Z"), 2, "road_record_identity_reused"),
])
def test_out_of_order_conflicting_or_reused_identity_does_not_replace_previous(xml, minute, code):
    before, _ = apply(minute=1)
    frozen = repr(before)
    with pytest.raises(RoadFeedError, match=code):
        apply(before, xml, minute=minute)
    assert repr(before) == frozen


def test_rollback_of_one_clause_is_rejected_even_if_other_clause_has_newer_time():
    before, _ = apply(xml=feed(record() + record(identifier="other")), minute=1)
    candidate = snapshot(feed(record() + record(identifier="other")), minute=2)
    event = candidate.situations[0]
    records = (replace(event.records[0], version_at=NOW), event.records[1])
    candidate = replace(candidate, situations=(replace(event, records=records),))
    with pytest.raises(RoadFeedError, match="road_record_rollback"):
        reconcile_road_snapshot(before, candidate, mode="full", continuous=True)


def test_conflict_in_later_situation_cannot_publish_earlier_change():
    before, _ = apply(xml=feed(situations=situation() + situation(identifier="z-other")), minute=1)
    candidate = snapshot(feed(situations=situation(record(code="roadCleared")) + situation(identifier="z-other")), minute=2)
    first, second = candidate.situations
    candidate = replace(candidate, situations=(first, replace(second, version_at=NOW)))
    with pytest.raises(RoadFeedError, match="road_situation_rollback"):
        reconcile_road_snapshot(before, candidate, mode="full", continuous=True)
    assert before.situations[0].situation.records[0].kind == "road_closure"


def test_bounded_retained_history_never_silently_discards_missing_closures(monkeypatch):
    monkeypatch.setattr(road_reconciliation, "MAX_RETAINED_SITUATIONS", 1)
    before, _ = apply()
    with pytest.raises(RoadFeedError, match="road_retained_situation_limit"):
        apply(before, feed(situations=situation(identifier="new")), minute=1)
    assert before.situations[0].present
