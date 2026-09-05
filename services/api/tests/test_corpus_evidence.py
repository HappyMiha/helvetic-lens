"""Native artifact access follows corpus visibility and organization admission."""
import asyncio

import pytest
from sqlalchemy import delete, func, inspect, select
from sqlalchemy import event as sa_event
from sqlalchemy.orm import Session
from test_connectors import FixtureConnector

from helvetic_lens import corpus_evidence
from helvetic_lens.config import DomainError
from helvetic_lens.models import (
    Law,
    Organization,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryWork,
    Version,
)


def saved(harness):
    _, _, service, _ = harness
    asyncio.run(service.connector_runner.run_page(FixtureConnector(), stream="catalogue"))
    with service.db.session() as session:
        version = session.scalar(select(RegulatoryDocumentVersion))
        event = session.scalar(select(RegulatoryEvent).where(RegulatoryEvent.document_version_id == version.id))
        session.add(RegulatoryEventState(event_id=event.id))
        session.commit()
        return version.id, event.id, version.artifact_key


def test_native_connector_roundtrip_reads_saved_text_and_safe_original_without_legacy_copy(harness):
    client, _, service, model = harness
    version_id, _, _ = saved(harness)
    url = f"/api/regulatory-versions/{version_id}"
    response = client.get(url)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["passages"] and "stable legal provision" in str(body["passages"])
    assert body["evidence_url"] == f"/corpus-evidence/{version_id}"
    assert body["identity_json"]["language"] == "de"
    assert "artifact_key" not in body and body["law_id"] is None
    artifact = client.get(body["artifact_url"])
    assert artifact.status_code == 200 and b"<html>" in artifact.content
    assert artifact.headers["content-disposition"].startswith("attachment;")
    assert artifact.headers["content-type"].startswith("text/plain")
    assert artifact.headers["content-security-policy"] == "sandbox"
    assert artifact.headers["x-content-type-options"] == "nosniff"
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Law)) == 0
        assert session.scalar(select(func.count()).select_from(Version)) == 0
    assert model.calls == []


@pytest.mark.parametrize("condition", ["revoked", "private", "foreign_org", "wrong_work"])
def test_native_evidence_cannot_bypass_scope_even_in_privileged_session(harness, condition):
    client, _, service, _ = harness
    version_id, event_id, _ = saved(harness)
    with service.db.session(include_all_organizations=True) as session:
        org = Organization(name="Unrelated reader", slug="native-other-reader")
        session.add(org)
        session.flush()
        work_id = session.get(RegulatoryEvent, event_id).work_id
        if condition == "revoked":
            session.execute(delete(RegulatoryEventState).where(RegulatoryEventState.event_id == event_id))
        elif condition == "private":
            session.get(RegulatoryWork, work_id).owner_organization_id = org.id
        elif condition == "wrong_work":
            work = RegulatoryWork(kind="act", authority="fixture", canonical_key="different-work")
            session.add(work)
            session.flush()
            session.get(RegulatoryEvent, event_id).work_id = work.id
        session.commit()
        organization_id = org.id if condition == "foreign_org" else service.organization_id
        with pytest.raises(DomainError) as error:
            corpus_evidence.detail(session, organization_id, version_id, service.settings)
        assert error.value.code == "not_found"
        with pytest.raises(DomainError):
            corpus_evidence.artifact(session, organization_id, version_id, service.settings)
    if condition != "foreign_org":
        assert client.get(f"/api/regulatory-versions/{version_id}").status_code == 404
        assert client.get(f"/api/regulatory-versions/{version_id}/artifact").status_code == 404


@pytest.mark.parametrize("key", [None, "../outside.txt", "..\\outside.txt", "C:/outside.txt", "a" * 64 + ".html"])
def test_missing_or_invalid_artifact_does_not_hide_text_or_read_outside_store(harness, key):
    client, _, service, _ = harness
    version_id, _, _ = saved(harness)
    (service.settings.storage_path / "outside.txt").write_text("Do not expose synthetic outside content")
    with service.db.session() as session:
        session.get(RegulatoryDocumentVersion, version_id).artifact_key = key
        session.commit()
    response = client.get(f"/api/regulatory-versions/{version_id}")
    assert response.status_code == 200 and response.json()["artifact_url"] is None
    assert response.json()["passages"]
    artifact = client.get(f"/api/regulatory-versions/{version_id}/artifact")
    assert artifact.status_code == 404 and "outside content" not in artifact.text


def test_original_download_avoids_document_text_and_passage_hydration(harness):
    client, _, service, _ = harness
    version_id, _, _ = saved(harness)
    seen = []
    def record(_session, item):
        if isinstance(item, RegulatoryDocumentVersion):
            seen.append(inspect(item).unloaded)
    sa_event.listen(Session, "loaded_as_persistent", record)
    try:
        assert client.get(f"/api/regulatory-versions/{version_id}/artifact").status_code == 200
    finally:
        sa_event.remove(Session, "loaded_as_persistent", record)
    assert seen and all({"text", "passages"}.issubset(fields) for fields in seen)


def test_text_only_and_metadata_only_records_do_not_invent_passage_ids(harness):
    client, _, service, _ = harness
    version_id, _, _ = saved(harness)
    with service.db.session() as session:
        version = session.get(RegulatoryDocumentVersion, version_id)
        version.passages = []
        version.text = "Saved text without assigned passage identifiers"
        version.artifact_key = None
        session.commit()
    body = client.get(f"/api/regulatory-versions/{version_id}").json()
    assert body["plain_text"] == "Saved text without assigned passage identifiers"
    assert body["passages"] == [] and body["passage_count"] == 0
    with service.db.session() as session:
        session.get(RegulatoryDocumentVersion, version_id).text = None
        session.commit()
    body = client.get(f"/api/regulatory-versions/{version_id}").json()
    assert body["plain_text"] is None and body["characters"] == 0 and body["artifact_url"] is None


def test_paused_watch_keeps_saved_evidence_but_foreign_legacy_owner_is_not_a_bypass(harness):
    from conftest import add_law

    from helvetic_lens.models import DocumentWatch
    client, _, service, _ = harness
    law = add_law(client)
    with service.db.session() as session:
        version = session.scalar(select(RegulatoryDocumentVersion).where(RegulatoryDocumentVersion.legacy_version_id == session.get(Law, law["id"]).current_version_id))
        version_id, legacy_id = version.id, version.legacy_version_id
        session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law["id"])).active = False
        session.commit()
    assert client.get(f"/api/regulatory-versions/{version_id}").status_code == 200
    with service.db.session(include_all_organizations=True) as session:
        org = Organization(name="Private linked version", slug="native-private-linked")
        session.add(org)
        session.flush()
        session.get(Version, legacy_id).owner_organization_id = org.id
        session.commit()
    assert client.get(f"/api/regulatory-versions/{version_id}").status_code == 404
    assert client.get(f"/api/regulatory-versions/{version_id}/artifact").status_code == 404


def test_relation_delivery_grants_source_evidence_without_direct_watch_or_topic_admission(harness):
    from test_relation_analysis import relation_delivery

    from helvetic_lens.models import OrganizationRelationCandidate, RelationCandidate
    client, _, service, model = harness
    delivery_id, _ = relation_delivery(harness)
    with service.db.session() as session:
        delivery = session.get(OrganizationRelationCandidate, delivery_id)
        candidate = session.get(RelationCandidate, delivery.candidate_id)
        version_id = session.get(RegulatoryEvent, candidate.event_id).document_version_id
        version = session.get(RegulatoryDocumentVersion, version_id)
        version.metadata_json = {"synthetic": True}
        session.commit()
    response = client.get(f"/api/regulatory-versions/{version_id}")
    assert response.status_code == 200, response.text
    assert response.json()["synthetic"] is True
    with service.db.session() as session:
        session.execute(delete(OrganizationRelationCandidate).where(OrganizationRelationCandidate.id == delivery_id))
        session.commit()
    assert client.get(f"/api/regulatory-versions/{version_id}").status_code == 404
    assert model.calls == []
