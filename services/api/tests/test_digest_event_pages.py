"""Event keysets bound digest materialization without splitting law groups."""

from datetime import timedelta

import pytest
from sqlalchemy import select
from test_digest_periods import recipient, seed_events
from test_impact_inbox import _add_second_delivery
from test_relation_analysis import relation_delivery

from helvetic_lens import digests
from helvetic_lens.db import utcnow
from helvetic_lens.impact_inbox import ImpactInboxFilters, ImpactInboxReader
from helvetic_lens.models import (
    DigestPreference,
    OrganizationRelationCandidate,
    RegulatoryEvent,
    RelationCandidate,
    new_id,
)


def test_digest_stops_after_51_eligible_groups_using_small_event_pages(harness, monkeypatch):
    _, _, service, model = harness
    end = utcnow()
    specs = [{"id": new_id(), "detected_at": end - timedelta(seconds=i + 1),
              "impact": "low" if i < 120 else "high"} for i in range(260)]
    seed_events(harness, specs)
    user_id = recipient(service)
    page = ImpactInboxReader.page
    selected = []
    def record_page(self, session, filters):
        assert filters.admitted_before is not None
        selected.append(filters.event_ids)
        return page(self, session, filters)
    monkeypatch.setattr(ImpactInboxReader, "page", record_page)
    saved = service.save_digest_preference(user_id, enabled=False, frequency="daily", severities=["high"], sources=[])
    summary = saved["preview"]
    assert [item["event_id"] for item in summary["events"]] == [s["id"] for s in specs[120:170]]
    assert summary["truncated"] is True
    # Severity can depend on validated AI/reviews, so selection visits preceding
    # low-severity events. It stops at the 51st eligible group, with <=49 prefetched.
    assert len(selected) == 4 and all(len(ids) == 50 for ids in selected)
    assert len({id_ for ids in selected for id_ in ids}) == 200
    assert model.calls == []


def test_equal_time_keysets_ignore_new_admissions_and_advance_empty_filtered_pages(harness, monkeypatch):
    _, _, service, model = harness
    end = utcnow()
    stamp = end - timedelta(minutes=1)
    ids = [f"77000000-0000-0000-0000-{i:012d}" for i in range(121)]
    seed_events(harness, [{"id": id_, "detected_at": stamp, "impact": "high" if i < 50 else "low"}
                          for i, id_ in enumerate(ids)])
    page = ImpactInboxReader.page
    selected = []
    inserted = "77000000-0000-0000-0000-000000000055"
    # Choose a not-yet-existing key between earlier pages; its backdated event
    # detection time must not let a new organization admission enter this traversal.
    inserted = inserted[:-1] + "a"
    def record_page(self, session, filters):
        result = page(self, session, filters)
        selected.extend(filters.event_ids)
        if len(selected) == 17:
            with service.db.session() as writer:
                template = writer.get(RegulatoryEvent, ids[0])
                candidate = writer.scalar(select(RelationCandidate).where(RelationCandidate.event_id == ids[0]))
                delivery = writer.scalar(select(OrganizationRelationCandidate).where(OrganizationRelationCandidate.candidate_id == candidate.id))
                writer.add(RegulatoryEvent(id=inserted, work_id=template.work_id, authority=template.authority,
                                           event_type="created", dedupe_key=inserted, detected_at=stamp,
                                           provenance_method="test-only", impact="high"))
                writer.flush()
                new_candidate = RelationCandidate(event_id=inserted, source_work_id=candidate.source_work_id,
                                                  target_work_id=candidate.target_work_id, score=1,
                                                  rule_revision="test", expires_at=end + timedelta(days=1))
                writer.add(new_candidate)
                writer.flush()
                writer.add(OrganizationRelationCandidate(candidate_id=new_candidate.id, watch_id=delivery.watch_id))
                writer.commit()
        return result
    monkeypatch.setattr(ImpactInboxReader, "page", record_page)
    with service.db.session() as session:
        groups = list(ImpactInboxReader(service.organization_id, None).iter_groups(
            session, ImpactInboxFilters(detected_from=end - timedelta(days=1), detected_before=end, severity="high"), page_size=17,
        ))
    assert [item["event_id"] for item in groups] == list(reversed(ids[:50]))
    assert selected == list(reversed(ids))  # Cursor crosses the empty low-severity pages.
    monkeypatch.setattr(ImpactInboxReader, "page", page)
    with service.db.session() as session:
        groups = list(ImpactInboxReader(service.organization_id, None).iter_groups(
            session, ImpactInboxFilters(detected_from=end - timedelta(days=1), detected_before=end), page_size=50,
        ))
    assert {item["event_id"] for item in groups} == set(ids) | {inserted}
    assert model.calls == []


@pytest.mark.parametrize("size", [0, 51, -1])
def test_event_pages_reject_unbounded_sizes(harness, size):
    _, _, service, _ = harness
    with service.db.session() as session, pytest.raises(ValueError, match="between 1 and 50"):
        list(ImpactInboxReader(service.organization_id, None).iter_groups(session, ImpactInboxFilters(), page_size=size))


def test_group_summary_does_not_consume_after_overflow_evidence():
    end = utcnow()
    item = {"severity": "high", "law_id": "law", "law_title": "Law", "potential_effect": "Evidence",
            "suggested_next_step": "Review", "links": {}}
    def groups():
        for i in range(51):
            yield {"event_id": str(i), "title": "Synthetic event", "detected_at": (end - timedelta(seconds=1)).isoformat(),
                   "items": [item]}
        raise AssertionError("The digest read past its confirmed overflow sentinel")
    summary = digests.summarize_groups(groups(), DigestPreference(severities=[], sources=[]), end - timedelta(days=1), end)
    assert summary["truncated"] and len(summary["events"]) == 50


def test_event_page_never_splits_related_law_deliveries(harness):
    _, _, service, _ = harness
    first, _ = relation_delivery(harness)
    second = _add_second_delivery(harness, first)
    with service.db.session() as session:
        groups = list(ImpactInboxReader(service.organization_id, None).iter_groups(session, ImpactInboxFilters(), page_size=1))
    assert len(groups) == 1
    assert {item["organization_candidate_id"] for item in groups[0]["items"]} == {first, second}
