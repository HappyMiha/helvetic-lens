"""Daily feed joins evidence; it must not manufacture relevance or leak state."""
from datetime import timedelta

import pytest
from sqlalchemy import delete, select
from test_relation_analysis import relation_delivery
from test_topic_history import saved_events
from test_topic_matching import create_topic
from test_topic_validity import evaluate

from helvetic_lens.db import utcnow
from helvetic_lens.interest_feed import InterestFeedReader
from helvetic_lens.models import (
    MonitoringTopic,
    Organization,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryWork,
    RelationCandidate,
    TopicEventMatch,
)


def reader(service, organization=None, user=None):
    return InterestFeedReader(organization or service.organization_id, user,
                              settings=service.settings, prompts=service.prompt_settings)


def seed(harness, count=1):
    client, _, service, _ = harness
    ids = saved_events(service, count)
    topic = create_topic(client)
    evaluate(service, topic, ids[0], "history")
    return topic, ids


def test_one_card_for_multiple_topics_and_law_without_ai(harness):
    client, _, service, model = harness
    relation_delivery(harness)
    with service.db.session() as session:
        event = session.get(RegulatoryEvent, session.scalar(select(RelationCandidate.event_id)))
        session.add(RegulatoryEventState(event_id=event.id))
        event_id = event.id
        event.evidence_json = {**event.evidence_json, "stream": "recent", "language": "en"}
        session.get(RegulatoryWork, event.work_id).metadata_json = {"jurisdiction": "CH"}
        session.commit()
    for index in range(2):
        topic = create_topic(client, key=f"feed-topic-test-{index}", name=f"Retention topic {index}",
                             concepts=["retention"], synonyms=[], exclusions=[], jurisdictions=["CH"],
                             source_pack_ids=["swiss-parliament"], document_kinds=["bill"], event_kinds=["created"], importance_floor="none")
        evaluate(service, topic, event_id, "history")
    page = client.get("/api/interest-feed").json()
    assert page["ai_calls"] == 0
    cards = [item for item in page["items"] if item["event_id"] == event_id]
    assert len(cards) == 1
    card = cards[0]
    assert len(card["topic_matches"]) == 2 and len(card["law_impacts"]) == 1
    assert card["source_url"].startswith("https://www.parlament.ch")
    assert card["law_impacts"][0]["status"] == "awaiting_analysis"
    assert card["ai_coverage"]["analysed"] == 0
    assert model.calls == []


def test_topic_only_event_is_visible_and_read_state_is_shared_with_inbox_storage(harness):
    client, _, service, model = harness
    _, ids = seed(harness)
    card = client.get("/api/interest-feed").json()["items"][0]
    assert card["event_id"] == ids[0] and card["severity"] == "unknown"
    assert card["law_impacts"] == [] and card["topic_matches"][0]["confidence"] == "high"
    result = client.patch(f"/api/interest-feed/events/{ids[0]}/state", json={"state": "read"})
    assert result.status_code == 200, result.text
    assert client.get("/api/interest-feed?state=unread").json()["items"] == []
    assert client.get("/api/interest-feed?state=read").json()["items"][0]["read_state"] == "read"
    with service.db.session() as session:
        assert reader(service, user="different-principal").feed(session)["items"][0]["read_state"] == "unread"
    assert model.calls == []


@pytest.mark.parametrize("change", ["plan", "paused", "archived", "evidence", "work", "expired", "rejected", "muted", "revoked"])
def test_invalid_or_rejected_topic_evidence_does_not_make_current_feed_card(harness, change):
    client, _, service, _ = harness
    topic, ids = seed(harness)
    with service.db.session() as session:
        match = session.scalar(select(TopicEventMatch))
        if change == "plan":
            session.get(MonitoringTopic, topic["id"]).current_revision += 1
        elif change in {"paused", "archived"}:
            session.get(MonitoringTopic, topic["id"]).status = change
        elif change == "evidence":
            session.get(RegulatoryEvent, ids[0]).evidence_json = {"correction": "different evidence"}
        elif change == "work":
            event = session.get(RegulatoryEvent, ids[0])
            session.get(RegulatoryWork, event.work_id).title = "Unrelated correction"
        elif change == "expired":
            match.expires_at = utcnow() - timedelta(seconds=1)
        elif change in {"rejected", "muted"}:
            match.decision_status = change
        elif change == "revoked":
            session.execute(delete(RegulatoryEventState).where(RegulatoryEventState.event_id == ids[0]))
        session.commit()
    assert client.get("/api/interest-feed").json()["items"] == []
    assert client.patch(f"/api/interest-feed/events/{ids[0]}/state", json={"state": "read"}).status_code == 404


def test_equal_time_cursor_covers_all_events_and_binds_filters_and_principal(harness):
    client, _, service, _ = harness
    _, ids = seed(harness, 5)
    first = client.get("/api/interest-feed?limit=2").json()
    assert len(first["items"]) == 2 and first["has_more"]
    cursor = first["next_cursor"]
    second = client.get("/api/interest-feed", params={"limit": 2, "cursor": cursor}).json()
    third = client.get("/api/interest-feed", params={"limit": 2, "cursor": second["next_cursor"]}).json()
    visited = [item["event_id"] for page in (first, second, third) for item in page["items"]]
    assert visited == sorted(ids, reverse=True) and not third["has_more"]
    assert client.get("/api/interest-feed", params={"cursor": cursor, "state": "unread"}).status_code == 422
    with service.db.session() as session:
        from helvetic_lens.config import DomainError
        with pytest.raises(DomainError):
            reader(service, user="different-principal").feed(session, cursor=cursor)


def test_sparse_page_continues_past_stale_candidates(harness):
    client, _, service, _ = harness
    _, ids = seed(harness, 3)
    with service.db.session() as session:
        session.get(RegulatoryEvent, max(ids)).evidence_json = {"correction": "changed"}
        session.commit()
    first = client.get("/api/interest-feed?limit=1").json()
    assert first["items"] == [] and first["has_more"] and first["scanned_event_count"] == 1
    second = client.get("/api/interest-feed", params={"cursor": first["next_cursor"], "limit": 1}).json()
    assert len(second["items"]) == 1


def test_other_organization_has_no_feed_or_state_access_even_in_privileged_session(harness):
    _, _, service, _ = harness
    _, ids = seed(harness)
    with service.db.session(include_all_organizations=True) as session:
        org = Organization(name="Other organization", slug="feed-other")
        session.add(org)
        session.commit()
        other = reader(service, organization=org.id)
        assert other.feed(session)["items"] == []
        from helvetic_lens.config import DomainError
        with pytest.raises(DomainError) as error:
            other.set_feed_state(session, ids[0], "read")
        assert error.value.status == 404


@pytest.mark.parametrize("params", [{"cursor": "junk"}, {"limit": 51}, {"state": "shared-confirmed"}, {"period": "tomorrow"}])
def test_invalid_feed_requests_are_rejected(harness, params):
    assert harness[0].get("/api/interest-feed", params=params).status_code == 422


@pytest.mark.parametrize("day", ["2026-03-29T12:00:00+00:00", "2026-10-25T12:00:00+00:00"])
def test_zurich_calendar_filters_separate_detection_from_official_dates(harness, monkeypatch, day):
    from datetime import UTC, datetime, time
    from zoneinfo import ZoneInfo

    from helvetic_lens import interest_feed
    from helvetic_lens.models import RegulatoryDate
    client, _, service, _ = harness
    _, ids = seed(harness, 3)
    captured = datetime.fromisoformat(day)
    today = datetime.combine(captured.astimezone(ZoneInfo("Europe/Zurich")).date(), time.min, ZoneInfo("Europe/Zurich")).astimezone(UTC)
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return captured.astimezone(tz) if tz else captured.replace(tzinfo=None)
    with service.db.session() as session:
        for index, event_id in enumerate(ids):
            event = session.get(RegulatoryEvent, event_id)
            event.detected_at = today + timedelta(seconds=[-1, 0, 1][index])
            session.scalar(select(RegulatoryEventState).where(RegulatoryEventState.event_id == event_id)).created_at = today - timedelta(days=1)
        # Re-evaluate corrected detection metadata to bind matches to the actual new input.
        from helvetic_lens.models import MonitoringTopicRevision, SourcePackDefinition
        from helvetic_lens.topic_matching import _evaluation_fingerprint
        definitions = {d.id: d for d in session.scalars(select(SourcePackDefinition).where(SourcePackDefinition.active.is_(True)))}
        for match in session.scalars(select(TopicEventMatch)):
            event = session.get(RegulatoryEvent, match.event_id)
            revision = session.get(MonitoringTopicRevision, match.topic_revision_id)
            match.evaluation_fingerprint = _evaluation_fingerprint(session, event, revision, definitions)
            match.matched_at = today - timedelta(hours=1)
            match.expires_at = captured + timedelta(days=30)
        session.add(RegulatoryDate(entity_type="event", entity_id=ids[1], kind="published_at", date_value="1999", precision="year", provenance="official_metadata"))
        session.commit()
    monkeypatch.setattr(interest_feed, "datetime", FixedDatetime)
    from helvetic_lens import topic_matching
    monkeypatch.setattr(topic_matching, "utcnow", lambda: captured)
    today_page = client.get("/api/interest-feed?period=today").json()
    assert {item["event_id"] for item in today_page["items"]} == set(ids[1:])
    assert client.get("/api/interest-feed?period=yesterday").json()["items"][0]["event_id"] == ids[0]
    card = next(item for item in today_page["items"] if item["event_id"] == ids[1])
    assert card["official_dates"] == [{"kind": "published_at", "value": "1999", "precision": "year", "provenance": "official_metadata", "source_url": None}]


def test_private_work_cannot_leak_through_retained_admission_even_in_privileged_reader(harness):
    _, _, service, _ = harness
    _, ids = seed(harness)
    with service.db.session(include_all_organizations=True) as session:
        org = Organization(name="Private owner", slug="feed-private")
        session.add(org)
        session.flush()
        event = session.get(RegulatoryEvent, ids[0])
        session.get(RegulatoryWork, event.work_id).owner_organization_id = org.id
        session.commit()
        assert reader(service).feed(session)["items"] == []


def test_direct_watched_document_event_is_retained_without_topics_or_relation_candidates(harness):
    from conftest import add_law

    from helvetic_lens.models import DocumentWatch, LegacyDocumentMapping
    client, _, service, _ = harness
    law = add_law(client, name="Directly monitored document")
    with service.db.session() as session:
        mapping = session.scalar(select(LegacyDocumentMapping).where(LegacyDocumentMapping.law_id == law["id"]))
        event = RegulatoryEvent(work_id=mapping.work_id, authority="saved_document", event_type="new_version",
                                detected_at=utcnow() - timedelta(seconds=1), dedupe_key="direct-feed-watch",
                                provenance_method="saved_version", connector="saved_document", evidence_json={})
        session.add(event)
        session.commit()
        event_id = event.id
    cards = client.get("/api/interest-feed").json()["items"]
    card = next(item for item in cards if item["event_id"] == event_id)
    assert card["topic_matches"] == [] and card["law_impacts"] == []
    assert card["monitored_documents"][0]["url"] == f"/laws/{law['id']}"
    assert client.patch(f"/api/interest-feed/events/{event_id}/state", json={"state": "read"}).status_code == 200
    with service.db.session() as session:
        session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law["id"])).active = False
        session.commit()
    assert not any(item["event_id"] == event_id for item in client.get("/api/interest-feed").json()["items"])
