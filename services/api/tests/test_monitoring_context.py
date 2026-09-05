"""Contextual monitoring is read-only, exact and scoped; activation stays explicit."""
import pytest
from conftest import add_law
from sqlalchemy import event as sa_event
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_corpus_evidence import saved

from helvetic_lens.config import DomainError
from helvetic_lens.models import (
    Comparison,
    DocumentWatch,
    Job,
    Law,
    MonitoringTopic,
    MonitoringTopicDraft,
    Organization,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryWork,
    Version,
)
from helvetic_lens.monitoring_context import describe


def test_native_event_context_uses_saved_title_and_artifact_without_automatic_monitoring(harness):
    client, _, service, model = harness
    version_id, event_id, _ = saved(harness)
    loaded = []
    def record(_session, item):
        loaded.append(type(item))
    sa_event.listen(Session, "loaded_as_persistent", record)
    try:
        response = client.get("/api/monitoring-context", params={"kind": "event", "id": event_id})
    finally:
        sa_event.remove(Session, "loaded_as_persistent", record)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] and body["evidence_url"] == f"/corpus-evidence/{version_id}"
    assert body["requires_confirmation"] and body["watches"] == [] and body["ai_calls"] == 0
    assert not set(loaded) & {Law, Version, RegulatoryDocumentVersion, RegulatoryWork}
    with service.db.session() as session:
        for entity in (MonitoringTopic, MonitoringTopicDraft, DocumentWatch, Law, Job):
            assert session.scalar(select(func.count()).select_from(entity)) == 0
    assert model.calls == []


def test_law_and_comparison_context_point_to_existing_watch_instead_of_creating_duplicates(harness):
    client, _, service, model = harness
    law = add_law(client)
    with service.db.session() as session:
        version_id = session.get(Law, law["id"]).current_version_id
        comparison = Comparison(law_id=law["id"], old_version_id=version_id, new_version_id=version_id, mode="historical", diff={})
        session.add(comparison)
        session.scalar(select(DocumentWatch)).active = False
        session.commit()
        comparison_id = comparison.id
    for kind, entity_id, reference in (("law", law["id"], f"/laws/{law['id']}"), ("comparison", comparison_id, f"/compare/{comparison_id}")):
        response = client.get("/api/monitoring-context", params={"kind": kind, "id": entity_id})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["title"] == law["name"] and body["reference_url"] == reference
        assert len(body["watches"]) == 1
        assert body["watches"][0]["law_id"] == law["id"] and not body["watches"][0]["active"]
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(DocumentWatch)) == 1
    assert model.calls == []


@pytest.mark.parametrize("kind", ["event", "law", "comparison"])
def test_context_cannot_disclose_foreign_owned_records_in_privileged_session(harness, kind):
    client, _, service, _ = harness
    _, event_id, _ = saved(harness)
    law = add_law(client)
    with service.db.session(include_all_organizations=True) as session:
        other = Organization(name="Private monitor context", slug="private-monitor-context")
        session.add(other)
        session.flush()
        version_id = session.get(Law, law["id"]).current_version_id
        comparison = Comparison(law_id=law["id"], old_version_id=version_id, new_version_id=version_id, mode="historical", diff={})
        session.add(comparison)
        session.flush()
        entity_id = {"event": event_id, "law": law["id"], "comparison": comparison.id}[kind]
        if kind == "event":
            session.get(RegulatoryWork, session.get(RegulatoryEvent, event_id).work_id).owner_organization_id = other.id
        elif kind == "law":
            session.get(Law, law["id"]).owner_organization_id = other.id
        else:
            comparison.owner_organization_id = other.id
        session.commit()
        with pytest.raises(DomainError) as failure:
            describe(session, service.organization_id, kind, entity_id)
        assert failure.value.code == "not_found"
    assert client.get("/api/monitoring-context", params={"kind": kind, "id": entity_id}).status_code == 404


@pytest.mark.parametrize("params,status", [({"kind": "website", "id": "x"}, 422), ({"kind": "event", "id": "x"*37}, 422), ({"kind": "event", "id": "missing"}, 404)])
def test_context_does_not_resolve_arbitrary_urls_or_unknown_entities(harness, params, status):
    client, _, _, model = harness
    assert client.get("/api/monitoring-context", params=params).status_code == status
    assert model.calls == []


def test_context_to_topic_preview_and_explicit_activation_reuses_existing_lifecycle(harness):
    from test_monitoring_topics import add_candidate, plan
    client, _, service, model = harness
    event_id = add_candidate(service)
    context = client.get("/api/monitoring-context", params={"kind": "event", "id": event_id}).json()
    proposed = plan(name=context["title"])
    preview = client.post("/api/monitoring-topics/preview", json=proposed)
    assert preview.status_code == 200, preview.text
    assert any(item["event_id"] == event_id for item in preview.json()["items"])
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(MonitoringTopic)) == 0
    body = {**proposed, "idempotency_key": "contextual-topic-retry-0001"}
    created = client.post("/api/monitoring-topics", json=body)
    assert created.status_code == 201, created.text
    repeated = client.post("/api/monitoring-topics", json=body)
    assert repeated.status_code == 201 and repeated.json()["id"] == created.json()["id"]
    assert repeated.json()["reused"] is True
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(MonitoringTopic)) == 1
    assert model.calls == []


def test_event_context_falls_back_to_recorded_work_source(harness):
    client, _, service, _ = harness
    _, event_id, _ = saved(harness)
    with service.db.session() as session:
        event = session.get(RegulatoryEvent, event_id)
        event.source_url = None
        session.get(RegulatoryWork, event.work_id).stable_official_url = "https://example.com/recorded-official-source"
        session.commit()
    body = client.get("/api/monitoring-context", params={"kind": "event", "id": event_id}).json()
    assert body["source_url"] == "https://example.com/recorded-official-source"
