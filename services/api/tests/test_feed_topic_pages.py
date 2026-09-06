"""Complete topic continuation with current evidence and bounded batch hydration."""
from copy import deepcopy

import pytest
from sqlalchemy import select
from test_interest_feed import reader, seed

from helvetic_lens.config import DomainError
from helvetic_lens.models import (
    MonitoringTopic,
    MonitoringTopicRevision,
    Organization,
    RegulatoryEvent,
    RegulatoryEventState,
    SourcePackDefinition,
    TopicEventMatch,
)
from helvetic_lens.topic_matching import _evaluation_fingerprint, _live_evidence_fingerprint


def seed_topics(harness, count=201):
    _, _, service, _ = harness
    topic, ids = seed(harness)
    with service.db.session() as session:
        original_topic = session.get(MonitoringTopic, topic["id"])
        original_match = session.scalar(select(TopicEventMatch))
        original_revision = session.get(MonitoringTopicRevision, original_match.topic_revision_id)
        event = session.get(RegulatoryEvent, ids[0])
        definitions = {item.id:item for item in session.scalars(select(SourcePackDefinition).where(SourcePackDefinition.active.is_(True)))}
        fingerprint = _live_evidence_fingerprint(session, event)
        def copy(model):
            return {column.key:deepcopy(getattr(model,column.key)) for column in model.__table__.columns}
        for i in range(count - 1):
            new_topic = MonitoringTopic(**{**copy(original_topic), "id":f"page-topic-{i:05}", "idempotency_key":f"page-topic-create-{i:05}"})
            new_revision = MonitoringTopicRevision(**{**copy(original_revision), "id":f"page-revision-{i:05}",
                "topic_id":new_topic.id, "name":f"Matching topic {i}"})
            session.add(new_topic)
            session.flush()
            session.add(new_revision)
            session.flush()
            session.add(TopicEventMatch(**{**copy(original_match), "id":f"page-match-{i:05}",
                "topic_id":new_topic.id, "topic_revision_id":new_revision.id,
                "evaluation_fingerprint":_evaluation_fingerprint(session,event,new_revision,definitions,fingerprint)}))
        session.commit()
        expected = list(session.scalars(select(TopicEventMatch.id).order_by(TopicEventMatch.id)))
    return ids[0], expected


def test_topic_fanout_complete_with_bounded_batches_and_no_ai(harness, monkeypatch):
    client, _, service, model = harness
    event_id, expected = seed_topics(harness)
    from helvetic_lens import interest_feed
    original = interest_feed.describe_matches
    batches = []
    def describe(session, records):
        batches.append(len(records))
        return original(session, records)
    monkeypatch.setattr(interest_feed, "describe_matches", describe)
    card = client.get("/api/interest-feed",params={"event":event_id}).json()["items"][0]
    assert len(card["topic_matches"]) == 5
    assert sum(batches) == 20  # Preview does not fetch/describe all 201 matches.
    seen = [row["id"] for row in card["topic_matches"]]
    cursor = card["topic_matches_next_cursor"]
    while cursor:
        response = client.get(f"/api/interest-feed/events/{event_id}/topics", params={"cursor":cursor,"limit":50})
        assert response.status_code == 200, response.text
        page = response.json()
        assert len(page["items"]) <= 50 and page["ai_calls"] == 0
        seen += [row["id"] for row in page["items"]]
        cursor = page["next_cursor"]
    assert seen == expected and max(batches) <= 100 and not model.calls


def test_sparse_topic_batches_never_hide_later_valid_matches(harness):
    client, _, service, _ = harness
    event_id, expected = seed_topics(harness, 131)
    with service.db.session() as session:
        for match_id in expected[:120]:
            session.get(TopicEventMatch, match_id).evaluation_fingerprint = "stale-evidence"
        session.get(TopicEventMatch, expected[120]).decision_status = "rejected"
        session.commit()
    card = client.get("/api/interest-feed",params={"event":event_id}).json()["items"][0]
    assert [row["id"] for row in card["topic_matches"]] == expected[121:126]
    page = client.get(f"/api/interest-feed/events/{event_id}/topics",params={"cursor":card["topic_matches_next_cursor"]}).json()
    assert [row["id"] for row in page["items"]] == expected[126:] and not page["has_more"]
    with service.db.session() as session:
        for match_id in expected[121:]:
            session.get(TopicEventMatch, match_id).evaluation_fingerprint = "stale-evidence"
        session.commit()
    assert client.get("/api/interest-feed",params={"event":event_id}).json()["items"] == []


def test_topic_page_scope_revocation_and_cursor_kind(harness):
    client, _, service, _ = harness
    event_id, _ = seed_topics(harness, 8)
    url = f"/api/interest-feed/events/{event_id}/topics"
    cursor = client.get(url,params={"limit":5}).json()["next_cursor"]
    for path in (f"/api/interest-feed/events/{event_id}/watches", "/api/interest-feed/events/another-event/topics"):
        assert client.get(path,params={"cursor":cursor}).status_code == 422
    with service.db.session(include_all_organizations=True) as session:
        org = Organization(name="Other",slug="topic-page-other")
        session.add(org)
        session.commit()
        for target in (reader(service,user="other-user"),reader(service,organization=org.id)):
            with pytest.raises(DomainError) as error:
                target.topic_page(session,event_id,cursor=cursor)
            assert error.value.status == 422
        admission = session.scalar(select(RegulatoryEventState).where(RegulatoryEventState.event_id == event_id))
        session.delete(admission)
        session.commit()
    assert client.get(url,params={"cursor":cursor}).status_code == 404


@pytest.mark.parametrize("params", [{"cursor":"junk"}, {"limit":0}, {"limit":51}])
def test_invalid_topic_page(harness, params):
    assert harness[0].get("/api/interest-feed/events/test/topics",params=params).status_code == 422
