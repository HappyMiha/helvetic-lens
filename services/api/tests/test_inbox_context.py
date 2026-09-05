"""Inbox context must avoid per-law reads and never hydrate document/diff bodies."""

from datetime import timedelta
from hashlib import sha256

import pytest
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session
from test_digest_periods import seed_events
from test_relation_analysis import relation_delivery

from helvetic_lens import impact_inbox
from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.inbox_context import load_context
from helvetic_lens.models import (
    Comparison,
    DocumentWatch,
    Law,
    LegacyDocumentMapping,
    Organization,
    OrganizationRelationCandidate,
    RegulatoryDocumentVersion,
    RegulatoryWork,
    RelationCandidate,
    Version,
    new_id,
)


def test_context_queries_do_not_grow_between_one_and_fifty_event_pages(harness):
    client, _, service, model = harness
    seed_events(harness, [{"id": new_id(), "connector": "context-batch"} for _ in range(50)])
    counts = []
    for limit in (1, 50):
        queries, loaded = [], []

        def query(_connection, _cursor, statement, *_args):
            if statement.lstrip().upper().startswith("SELECT"):
                queries.append(statement)

        def record(_session, row):
            loaded.append((type(row), inspect(row).unloaded))

        event.listen(service.db.engine, "before_cursor_execute", query)
        event.listen(Session, "loaded_as_persistent", record)
        try:
            response = client.get(
                "/api/impact-inbox/page", params={"source": "context-batch", "limit": limit}
            )
            assert response.status_code == 200, response.text
            assert response.json()["total_events"] == limit
        finally:
            event.remove(service.db.engine, "before_cursor_execute", query)
            event.remove(Session, "loaded_as_persistent", record)
        counts.append(len(queries))
        assert not any(kind in (Law, Version, Comparison, RegulatoryDocumentVersion) for kind, _ in loaded)
        assert all("evidence_json" in unloaded for kind, unloaded in loaded if kind == RelationCandidate)
        assert all("metadata_json" in unloaded for kind, unloaded in loaded if kind == RegulatoryWork)
    # Includes three configuration reads, event keys/state/deliveries, two empty
    # history selections and eight context queries. Populated histories add reads.
    assert counts[0] == counts[1] and counts[0] <= 16, counts
    assert model.calls == []


def test_comparison_and_artifact_links_use_visible_scalar_ids_only(harness):
    client, _, service, _ = harness
    delivery_id, _ = relation_delivery(harness)
    with service.db.session(include_all_organizations=True) as session:
        delivery = session.get(OrganizationRelationCandidate, delivery_id)
        candidate = session.get(RelationCandidate, delivery.candidate_id)
        watch = session.get(DocumentWatch, delivery.watch_id)
        law = session.get(Law, watch.law_id)
        current = session.get(Version, law.current_version_id)
        old_values = {column.name: getattr(current, column.name) for column in Version.__mapper__.columns}
        older_text = "Synthetic earlier version for link selection."
        old = Version(
            **{
                **old_values,
                "id": new_id(),
                "text": older_text,
                "passages": [],
                "content_hash": sha256(older_text.encode()).hexdigest(),
            }
        )
        foreign = Organization(name="Private comparison owner", slug="private-comparison-owner")
        session.add_all([old, foreign])
        session.flush()
        when = utcnow() - timedelta(minutes=1)
        ids = [f"84000000-0000-0000-0000-{i:012d}" for i in range(3)]
        for i, mode in enumerate(("demo", "live", "foreign-test")):
            session.add(
                Comparison(
                    id=ids[i],
                    owner_organization_id=foreign.id if i == 2 else None,
                    law_id=law.id,
                    old_version_id=old.id,
                    new_version_id=current.id,
                    mode=mode,
                    created_at=when,
                    diff={"synthetic_heavy_diff": "Ignored body " * 50_000},
                )
            )
        source_version = session.get(RegulatoryDocumentVersion, candidate.source_version_id)
        source_version.legacy_version_id = old.id
        source_version.text = "Ignored extracted document " * 50_000
        source_version.passages = [{"text": "Ignored passage " * 50_000}]
        session.commit()
        old_id, foreign_id = old.id, foreign.id
    loaded = []

    def record(_session, row):
        loaded.append(type(row))

    event.listen(Session, "loaded_as_persistent", record)
    try:
        body = client.get("/api/impact-inbox/page").json()
    finally:
        event.remove(Session, "loaded_as_persistent", record)
    assert body["items"][0]["items"][0]["links"]["comparison"] == f"/compare/{ids[1]}"
    assert body["items"][0]["source_artifact_url"] == f"/evidence/{old_id}"
    assert not set(loaded) & {Law, Version, Comparison, RegulatoryDocumentVersion}
    with service.db.session(include_all_organizations=True) as session:
        session.get(Version, old_id).owner_organization_id = foreign_id
        session.commit()
        context = load_context(
            session, service.organization_id, [session.get(OrganizationRelationCandidate, delivery_id)]
        )
        assert context.artifacts == {} and context.comparisons[watch.law_id] == ids[1]


def test_successor_aliases_prefer_current_organization_watch_without_foreign_state(harness):
    client, _, service, _ = harness
    delivery_id, _ = relation_delivery(harness, confirmed=True, relation_type="replaces")
    with service.db.session(include_all_organizations=True) as session:
        delivery = session.get(OrganizationRelationCandidate, delivery_id)
        candidate = session.get(RelationCandidate, delivery.candidate_id)
        base_watch = session.get(DocumentWatch, delivery.watch_id)
        base = session.get(Law, base_watch.law_id)
        template = {column.name: getattr(base, column.name) for column in Law.__mapper__.columns}
        other = Organization(name="Other successor watcher", slug="other-successor-watcher")
        session.add(other)
        session.flush()
        law_ids, watches = [], []
        for i in range(4):
            law_id, watch_id = new_id(), new_id()
            law_ids.append(law_id)
            url = f"https://example.com/context-successor/{i}"
            session.add(
                Law(
                    **{
                        **template,
                        "id": law_id,
                        "current_version_id": None,
                        "url": url,
                        "canonical_identity": url,
                    }
                )
            )
            session.flush()
            session.add(
                LegacyDocumentMapping(
                    law_id=law_id,
                    work_id=candidate.source_work_id,
                    mapping_status="mapped",
                    created_at=utcnow() + timedelta(seconds=i),
                )
            )
            if i:
                session.add(
                    DocumentWatch(
                        id=watch_id,
                        organization_id=other.id if i == 3 else service.organization_id,
                        law_id=law_id,
                        display_name=f"Synthetic successor {i}",
                        active=i != 1,
                    )
                )
                watches.append(watch_id)
        session.commit()

    def successor():
        return client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]["replacement"]["successor"]

    result = successor()
    assert result["law_id"] == law_ids[2] and result["monitored"]
    with service.db.session() as session:
        session.get(DocumentWatch, watches[1]).active = False
        session.commit()
    result = successor()
    assert result["law_id"] == law_ids[1] and not result["monitored"]
    with service.db.session() as session:
        for id_ in watches[:2]:
            session.delete(session.get(DocumentWatch, id_))
        session.commit()
    result = successor()
    assert result["law_id"] == law_ids[0] and not result["monitored"]
    with service.db.session(include_all_organizations=True) as session:
        delivery = session.get(OrganizationRelationCandidate, delivery_id)
        context = load_context(session, service.organization_id, [delivery])
        assert context.successors[candidate.source_work_id] == (law_ids[0], False)
        with pytest.raises(DomainError):
            load_context(session, other.id, [delivery])
        with pytest.raises(ValueError):
            load_context(session, service.organization_id, [delivery] * 101)
        assert load_context(session, service.organization_id, []).law_ids == set()


def test_large_compatibility_page_keeps_context_batches_bounded(harness, monkeypatch):
    client, _, _, model = harness
    seed_events(harness, [{"id": new_id(), "connector": "context-large"} for _ in range(121)])
    sizes = []
    original = impact_inbox.load_context

    def read(session, organization_id, deliveries):
        sizes.append(len(deliveries))
        return original(session, organization_id, deliveries)

    monkeypatch.setattr(impact_inbox, "load_context", read)
    response = client.get("/api/impact-inbox", params={"source": "context-large"})
    assert response.status_code == 200, response.text
    assert response.json()["total_events"] == 121
    assert sizes == [100, 21]
    assert model.calls == []
