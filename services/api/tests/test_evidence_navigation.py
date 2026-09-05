"""Every event surface links the same authorized saved version without body hydration."""
import pytest
from sqlalchemy import delete, select
from sqlalchemy import event as sa_event
from sqlalchemy.orm import Session
from test_corpus_evidence import saved
from test_relation_analysis import relation_delivery

from helvetic_lens import registry
from helvetic_lens.corpus_access import event_evidence_links
from helvetic_lens.models import (
    Law,
    Organization,
    OrganizationRelationCandidate,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryWork,
    RelationCandidate,
    Version,
    new_id,
)


def rows(client, path, params=None):
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()["items"]


@pytest.mark.parametrize("condition", [None, "legacy", "revoked", "private", "wrong_work", "foreign_version", "foreign_law"])
def test_event_surfaces_share_exact_evidence_and_revocation_guards(harness, condition):
    client, _, service, model = harness
    delivery_id, _ = relation_delivery(harness)
    denied = condition not in {None, "legacy"}
    with service.db.session(include_all_organizations=True) as session:
        delivery = session.get(OrganizationRelationCandidate, delivery_id)
        candidate = session.get(RelationCandidate, delivery.candidate_id)
        source_event = session.get(RegulatoryEvent, candidate.event_id)
        event_id, version_id = source_event.id, source_event.document_version_id
        version = session.get(RegulatoryDocumentVersion, version_id)
        # A newer saved version must not silently replace the source of this event.
        session.add(RegulatoryDocumentVersion(expression_id=version.expression_id, version_key="newer-synthetic",
            source_url="https://example.com/newer-synthetic-source", content_hash="b" * 64,
            text="Newer text must not replace the event's saved evidence.", passages=[]))
        version.text = "Unnecessary list payload " * 50_000
        version.passages = [{"id": "p00001", "text": "Exact saved passage"}]
        other = Organization(name="Other evidence owner", slug="navigation-other")
        session.add(other)
        session.flush()
        if condition == "revoked":
            session.delete(delivery)
            session.execute(delete(RegulatoryEventState).where(RegulatoryEventState.event_id == event_id))
        elif condition == "private":
            session.get(RegulatoryWork, source_event.work_id).owner_organization_id = other.id
        elif condition == "wrong_work":
            work = RegulatoryWork(kind="act", authority="fixture", canonical_key="navigation-other-work")
            session.add(work)
            session.flush()
            source_event.work_id = work.id
        elif condition in {"legacy", "foreign_version", "foreign_law"}:
            template = session.scalar(select(Version))
            base_law = session.get(Law, template.law_id)
            linked_law = Law(**{**{column.name: getattr(base_law, column.name) for column in Law.__mapper__.columns},
                               "id": new_id(), "url": "https://example.com/navigation-linked-law",
                               "canonical_identity": "https://example.com/navigation-linked-law",
                               "current_version_id": None,
                               "owner_organization_id": other.id if condition == "foreign_law" else None})
            session.add(linked_law)
            session.flush()
            legacy = Version(**{**{column.name: getattr(template, column.name) for column in Version.__mapper__.columns},
                                "id": new_id(), "law_id": linked_law.id,
                                "owner_organization_id": other.id if condition == "foreign_version" else None})
            session.add(legacy)
            session.flush()
            version.legacy_version_id = legacy.id
        session.commit()
        expected = {} if denied else {event_id: f"/evidence/{legacy.id}" if condition == "legacy" else f"/corpus-evidence/{version_id}"}
        # Explicit guards remain effective even for a platform-wide session.
        assert event_evidence_links(session, service.organization_id, [event_id]) == expected
        assert event_evidence_links(session, other.id, [event_id]) == {}
    loaded = []
    def record(_session, item):
        if isinstance(item, (Version, RegulatoryDocumentVersion)):
            loaded.append(type(item))
    sa_event.listen(Session, "loaded_as_persistent", record)
    try:
        surfaces = [
            (rows(client, "/api/registry", {"view": "events"}), "evidence_url"),
            (rows(client, "/api/impact-inbox/page"), "source_artifact_url"),
            (rows(client, "/api/interest-feed"), "source_artifact_url"),
        ]
    finally:
        sa_event.remove(Session, "loaded_as_persistent", record)
    for items, key in surfaces:
        selected = [item for item in items if item["event_id"] == event_id]
        if denied:
            assert all(item[key] is None for item in selected)
        else:
            assert len(selected) == 1
            assert selected[0][key] == expected[event_id]
    assert loaded == []
    evidence = client.get(f"/api/regulatory-versions/{version_id}")
    assert evidence.status_code == (404 if denied else 200), evidence.text
    if not denied:
        assert evidence.json()["passages"][0]["text"] == "Exact saved passage"
    assert model.calls == []


def test_registry_resolves_only_displayed_page_and_never_hydrates_version_body(harness, monkeypatch):
    client, _, service, model = harness
    saved(harness)
    requested = []
    def links(session, organization_id, event_ids):
        requested.append(list(event_ids))
        return event_evidence_links(session, organization_id, event_ids)
    monkeypatch.setattr(registry, "event_evidence_links", links)
    response = client.get("/api/registry", params={"view": "events", "limit": 1})
    assert response.status_code == 200, response.text
    body = response.json()
    assert requested == [[item["event_id"] for item in body["items"]]]
    assert body["next_cursor"]
    assert model.calls == []


def test_link_query_is_one_bounded_scalar_read_with_no_empty_batch_query(harness):
    _, _, service, _ = harness
    version_id, event_id, _ = saved(harness)
    queries = []
    def query(_connection, _cursor, statement, *_args):
        queries.append(statement)
    with service.db.session() as session:
        sa_event.listen(service.db.engine, "before_cursor_execute", query)
        try:
            assert event_evidence_links(session, service.organization_id, []) == {}
            assert queries == []
            with pytest.raises(ValueError):
                event_evidence_links(session, service.organization_id, [f"event-{i}" for i in range(101)])
            assert queries == []
            links = event_evidence_links(session, service.organization_id, [event_id] * 100)
            assert links == {event_id: f"/corpus-evidence/{version_id}"}
            assert len(queries) == 1
            assert "passages" not in queries[0] and "content_hash" not in queries[0]
        finally:
            sa_event.remove(service.db.engine, "before_cursor_execute", query)
