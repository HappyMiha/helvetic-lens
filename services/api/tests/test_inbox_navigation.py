"""Navigation prerequisites: independent scalar law options and scoped deep links."""

from datetime import timedelta

from sqlalchemy import event as sa_event
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_digest_periods import seed_events
from test_relation_analysis import relation_delivery

from helvetic_lens.db import utcnow
from helvetic_lens.impact_inbox import ImpactInboxReader
from helvetic_lens.models import (
    DocumentWatch,
    Law,
    Organization,
    OrganizationRelationCandidate,
    RelationCandidate,
    new_id,
)


def test_options_remain_available_outside_page_and_limit_without_loading_laws(harness):
    client, _, service, _ = harness
    relation_delivery(harness)
    with service.db.session() as session:
        watch = session.scalar(select(DocumentWatch))
        law = session.get(Law, watch.law_id)
        template = {column.name: getattr(law, column.name) for column in Law.__mapper__.columns}
        original = watch.id
        ids = [new_id() for _ in range(61)]
        session.execute(Law.__table__.insert(), [{**template, "id": id_, "url": f"https://example.com/navigation/{i}", "canonical_identity": f"https://example.com/navigation/{i}"} for i, id_ in enumerate(ids)])
        session.add_all([DocumentWatch(law_id=id_, display_name=f"Navigation law {i:03d}", active=i != 60) for i, id_ in enumerate(ids)])
        session.commit()
    loaded = []
    def record(_session, row):
        if isinstance(row, (Law, DocumentWatch)):
            loaded.append(row.id)
    sa_event.listen(Session, "loaded_as_persistent", record)
    try:
        body = client.get("/api/impact-inbox/law-options", params={"q": "Navigation", "selected": ids[-1]}).json()
        assert len(body["items"]) == 50 and body["has_more"]
        assert body["selected"]["id"] == ids[-1] and body["selected"] not in body["items"]
        searched = client.get("/api/impact-inbox/law-options", params={"q": "law 060"}).json()
        assert len(searched["items"]) == 1 and not searched["has_more"]
        assert searched["items"][0]["id"] == ids[-1]
        assert client.get("/api/impact-inbox/law-options", params={"q": "%"}).json()["items"] == []
        assert client.get("/api/impact-inbox/law-options", params={"q": "missing", "selected": original}).json()["selected"]["watch_id"] == original
        assert loaded == []
    finally:
        sa_event.remove(Session, "loaded_as_persistent", record)
    with service.db.session() as session:
        other = Organization(name="Other options", slug="other-options")
        session.add(other)
        session.commit()
        other_id = other.id
    with service.db.organization_context(other_id), service.db.session() as session:
        assert ImpactInboxReader(other_id, None).law_options(session, selected=ids[-1]) == {"items": [], "has_more": False, "selected": None}


def test_candidate_link_reaches_old_event_without_traversing_recent_pages(harness):
    client, _, service, _ = harness
    ids = [new_id() for _ in range(61)]
    stamp = utcnow()
    seed_events(harness, [{"id": id_, "detected_at": stamp-timedelta(minutes=i+1), "connector": "navigation"} for i, id_ in enumerate(ids)])
    with service.db.session() as session:
        delivery_id = session.scalar(select(OrganizationRelationCandidate.id).join(RelationCandidate).where(RelationCandidate.event_id == ids[-1]))
    ordinary = client.get("/api/impact-inbox/page", params={"source": "navigation"}).json()
    assert ids[-1] not in [item["event_id"] for item in ordinary["items"]]
    linked = client.get("/api/impact-inbox/page", params={"candidate": delivery_id}).json()
    assert [item["event_id"] for item in linked["items"]] == [ids[-1]]
    assert linked["scanned_event_count"] == 1 and not linked["has_more"]
    assert client.get("/api/impact-inbox/page", params={"candidate": new_id()}).json()["items"] == []
    assert client.get("/api/impact-inbox/page", params={"candidate": delivery_id, "cursor": ordinary["next_cursor"], "source": "navigation"}).status_code == 422
    with service.db.session() as session:
        other = Organization(name="Foreign link", slug="foreign-link")
        session.add(other)
        session.commit()
        other_id = other.id
    with service.db.organization_context(other_id):
        from helvetic_lens.impact_inbox import ImpactInboxFilters
        assert service.impact_inbox_page(ImpactInboxFilters(candidate=delivery_id), None)["items"] == []
