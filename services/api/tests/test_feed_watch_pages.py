"""Per-event direct watches remain complete without unbounded feed hydration."""
from datetime import timedelta

import pytest
from sqlalchemy import event as sa_event
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_interest_feed import reader
from test_topic_history import saved_events

from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.models import (
    DocumentWatch,
    Law,
    LegacyDocumentMapping,
    Organization,
    RegulatoryEvent,
    RegulatoryWork,
)


def seed_watches(harness, count=121):
    _, _, service, _ = harness
    event_id = saved_events(service, 1)[0]
    with service.db.session() as session:
        work_id = session.get(RegulatoryEvent, event_id).work_id
        for i in range(count):
            law = Law(id=f"watch-law-{i:05}", canonical_identity=f"watch-page:{i}", name=f"Document {i}", url="https://example.invalid/law")
            session.add(law)
            session.flush()
            session.add(LegacyDocumentMapping(law_id=law.id, work_id=work_id, mapping_status="mapped"))
            session.add(DocumentWatch(id=f"watch-{i:05}", organization_id=service.organization_id,
                law_id=law.id, display_name=f"Document {i}"))
        session.commit()
    return event_id


def test_large_watch_fanout_is_complete_bounded_and_does_not_hydrate_laws(harness):
    client, _, service, model = harness
    event_id = seed_watches(harness, 1001)
    loaded = []
    def load(session, instance):
        if isinstance(instance, (Law, DocumentWatch, LegacyDocumentMapping)):
            loaded.append(instance.id)
    sa_event.listen(Session, "loaded_as_persistent", load)
    try:
        card = client.get("/api/interest-feed", params={"event":event_id}).json()["items"][0]
        assert len(card["monitored_documents"]) == 5
        cursor = card["monitored_documents_next_cursor"]
        seen = [row["watch_id"] for row in card["monitored_documents"]]
        while cursor:
            response = client.get(f"/api/interest-feed/events/{event_id}/watches", params={"cursor":cursor, "limit":50})
            assert response.status_code == 200, response.text
            page = response.json()
            assert len(page["items"]) <= 50 and len(response.content) < 15000
            seen += [row["watch_id"] for row in page["items"]]
            cursor = page["next_cursor"]
        assert seen == [f"watch-{i:05}" for i in range(1001)]
        assert not loaded and not model.calls
    finally:
        sa_event.remove(Session, "loaded_as_persistent", load)


def test_watch_cursor_rechecks_visibility_and_excludes_late_watches(harness):
    client, _, service, _ = harness
    event_id = seed_watches(harness, 12)
    url = f"/api/interest-feed/events/{event_id}/watches"
    first = client.get(url, params={"limit":5}).json()
    cursor = first["next_cursor"]
    with service.db.session(include_all_organizations=True) as session:
        other = Organization(name="Other", slug="watch-pages-other")
        session.add(other)
        session.flush()
        session.get(DocumentWatch, "watch-00005").active = False
        session.get(Law, "watch-law-00006").owner_organization_id = other.id
        session.scalar(select(LegacyDocumentMapping).where(LegacyDocumentMapping.law_id == "watch-law-00007")).owner_organization_id = other.id
        session.get(DocumentWatch, "watch-00008").created_at = utcnow() + timedelta(seconds=1)
        session.get(DocumentWatch, "watch-00009").organization_id = other.id
        # A title edit cannot skip/repeat rows: order is the immutable watch ID.
        session.get(DocumentWatch, "watch-00010").display_name = "AAA renamed"
        session.commit()
        page = reader(service).watch_page(session, event_id, cursor=cursor)
        assert [row["watch_id"] for row in page["items"]] == ["watch-00010", "watch-00011"]
        for target in (reader(service, user="someone-else"), reader(service, organization=other.id)):
            with pytest.raises(DomainError) as error:
                target.watch_page(session, event_id, cursor=cursor)
            assert error.value.status == 422
        work = session.get(RegulatoryWork, session.get(RegulatoryEvent, event_id).work_id)
        work.owner_organization_id = other.id
        session.commit()
        with pytest.raises(DomainError) as error:
            reader(service).watch_page(session, event_id, cursor=cursor)
        assert error.value.status == 404
    assert client.get(url, params={"cursor":cursor}).status_code == 404


@pytest.mark.parametrize("params", [{"cursor":"junk"}, {"cursor":"[]"}, {"limit":0}, {"limit":51}])
def test_bad_watch_page_requests(harness, params):
    event_id = seed_watches(harness, 6)
    assert harness[0].get(f"/api/interest-feed/events/{event_id}/watches", params=params).status_code == 422


def test_watch_cursor_cannot_move_to_another_event_and_revoked_watch_stops_access(harness):
    client, _, service, _ = harness
    event_id = seed_watches(harness, 6)
    url = f"/api/interest-feed/events/{event_id}/watches"
    cursor = client.get(url, params={"limit":5}).json()["next_cursor"]
    assert client.get("/api/interest-feed/events/another-event/watches", params={"cursor":cursor}).status_code == 422
    with service.db.session() as session:
        for watch in session.scalars(select(DocumentWatch)):
            watch.active = False
        session.commit()
    assert client.get(url, params={"cursor":cursor}).status_code == 404
    assert client.get(url).status_code == 404
