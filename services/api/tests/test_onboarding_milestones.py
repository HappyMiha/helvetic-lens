"""Milestones retain actual first actions without implying verified comprehension."""

import pytest
from conftest import LAW_URL, FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from test_auth import _csrf, _register, _settings
from test_corpus_evidence import saved
from test_topic_matching import create_topic, plan
from test_workflow import add_law

from helvetic_lens import onboarding
from helvetic_lens.config import DomainError
from helvetic_lens.main import create_app
from helvetic_lens.models import (
    Job,
    MonitoringTopic,
    OnboardingMilestone,
    Organization,
    OrganizationMembership,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryWork,
    Version,
)


def milestones(client):
    return client.get("/api/onboarding").json()["milestones"]


def test_interest_records_once_and_survives_shared_changes_without_completing_intro(harness):
    client, _, service, _ = harness
    assert milestones(client) == []
    topic = create_topic(client)
    first = milestones(client)
    assert [item["kind"] for item in first] == ["interest_saved"]
    assert first[0]["object_kind"] == "topic" and first[0]["recorded_at"]
    assert client.get("/api/onboarding").json()["state"] == "new"
    assert not client.get("/api/onboarding").json()["completion_verified"]
    create_topic(client)
    add_law(client)
    with service.db.session() as session:
        session.get(MonitoringTopic, topic["id"]).status = "archived"
        session.commit()
    assert milestones(client) == first
    with service.db.session(include_all_organizations=True) as session:
        assert onboarding.read(session, service.organization_id, "user:colleague")["milestones"] == []
        assert onboarding.read(session, "other", "anonymous-development")["milestones"] == []


def test_progress_failure_rolls_back_topic_job_and_milestone_together(harness, monkeypatch):
    client, _, service, _ = harness
    original = onboarding.record

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise DomainError("Synthetic transactional failure", 503, "test_failure")

    monkeypatch.setattr(onboarding, "record", fail)
    response = client.post(
        "/api/monitoring-topics", json={**plan(), "idempotency_key": "rollback-onboarding"}
    )
    assert response.status_code == 503
    with service.db.session() as session:
        for model in (MonitoringTopic, Job, OnboardingMilestone):
            assert session.scalar(select(func.count()).select_from(model)) == 0


def test_document_creation_records_actor_but_not_failed_duplicate(harness):
    client, _, _, _ = harness
    add_law(client)
    first = milestones(client)
    assert first[0]["object_kind"] == "document"
    assert client.post("/api/laws", json={"url": LAW_URL, "synthetic": True}).status_code == 409
    assert milestones(client) == first


@pytest.mark.parametrize("native", [False, True])
def test_view_reads_are_passive_and_explicit_display_is_idempotent(harness, native):
    client, _, service, model = harness
    if native:
        version_id, _, _ = saved(harness)
        with service.db.session() as session:
            session.get(RegulatoryDocumentVersion, version_id).metadata_json = {"synthetic": False}
            session.commit()
        url = f"/api/regulatory-versions/{version_id}"
    else:
        law = add_law(client)
        version_id = law["current_version_id"]
        with service.db.session() as session:
            session.get(Version, version_id).synthetic = False
            session.commit()
        url = f"/api/versions/{version_id}"
    before = milestones(client)
    assert client.get(url).status_code == 200
    assert milestones(client) == before
    body = {"kind": "native_version" if native else "version", "id": version_id}
    response = client.post("/api/onboarding/evidence-displayed", json=body)
    assert response.status_code == 200, response.text
    assert response.json()["recorded"]
    first = milestones(client)
    assert client.post("/api/onboarding/evidence-displayed", json=body).json()["recorded"]
    assert milestones(client) == first
    assert [item["kind"] for item in first].count("evidence_displayed") == 1
    assert model.calls == []


@pytest.mark.parametrize("condition", ["sample", "empty", "whitespace", "revoked", "foreign"])
def test_native_samples_empty_text_and_revoked_scope_never_record_real_evidence(harness, condition):
    client, _, service, _ = harness
    version_id, event_id, _ = saved(harness)
    with service.db.session(include_all_organizations=True) as session:
        version = session.get(RegulatoryDocumentVersion, version_id)
        if condition == "sample":
            version.metadata_json = {"synthetic": True}
        if condition in {"empty", "whitespace"}:
            version.text = "" if condition == "empty" else "    "
        if condition == "revoked":
            session.execute(delete(RegulatoryEventState).where(RegulatoryEventState.event_id == event_id))
        if condition == "foreign":
            session.add(Organization(id="other-evidence", slug="other-evidence", name="Other"))
            session.flush()
            work_id = session.get(RegulatoryEvent, event_id).work_id
            session.get(RegulatoryWork, work_id).owner_organization_id = "other-evidence"
        session.commit()
    response = client.post(
        "/api/onboarding/evidence-displayed", json={"kind": "native_version", "id": version_id}
    )
    assert response.status_code == (200 if condition in {"sample", "empty", "whitespace"} else 404), response.text
    if response.status_code == 200:
        assert not response.json()["recorded"]
    assert milestones(client) == []


def test_authenticated_viewer_can_record_own_opt_out_but_not_forge_other_steps(tmp_path):
    app = create_app(_settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        account = _register(client).json()
        with app.state.service.db.session(include_all_organizations=True) as session:
            membership = session.scalar(
                select(OrganizationMembership).where(OrganizationMembership.user_id == account["user"]["id"])
            )
            membership.role = "viewer"
            session.commit()
        body = {"enabled": False, "frequency": "weekly", "severities": [], "sources": []}
        assert client.get("/api/digests").status_code == 200
        assert milestones(client) == []
        response = client.put("/api/digests/preferences", json=body, headers=_csrf(client))
        assert response.status_code == 200, response.text
        assert [item["kind"] for item in milestones(client)] == ["notifications_saved"]
        first = milestones(client)
        assert client.put("/api/digests/preferences", json=body, headers=_csrf(client)).status_code == 200
        assert milestones(client) == first
        endpoint = "/api/onboarding/evidence-displayed"
        assert client.post(endpoint, json={"kind": "version", "id": "absent"}).status_code == 403
        assert (
            client.post(
                endpoint, json={"kind": "interest_saved", "id": "fake"}, headers=_csrf(client)
            ).status_code
            == 422
        )
        assert (
            client.post(
                endpoint,
                json={"kind": "version", "id": "absent", "user_id": "colleague"},
                headers=_csrf(client),
            ).status_code
            == 422
        )
        assert (
            client.post(endpoint, json={"kind": "version", "id": "absent"}, headers=_csrf(client)).status_code
            == 404
        )
        assert milestones(client) == first


def test_migration_preserves_personal_intent_and_existing_topic(harness):
    from pathlib import Path

    from alembic.config import Config
    from sqlalchemy import inspect

    from alembic import command

    client, _, service, _ = harness
    topic = create_topic(client)
    client.patch("/api/onboarding", json={"action": "topic"})
    directory = Path(__file__).resolve().parents[1]
    config = Config(str(directory / "alembic.ini"))
    config.set_main_option("script_location", str(directory / "alembic"))
    with service.db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "fc49b83e521a")
        assert "onboarding_milestones" not in inspect(connection).get_table_names()
        command.upgrade(config, "head")
    state = client.get("/api/onboarding").json()
    assert state["intent"] == "topic" and state["milestones"] == []
    with service.db.session() as session:
        assert session.get(MonitoringTopic, topic["id"])


def test_postgres_concurrent_first_steps_are_retained_once(harness):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    _, _, service, _ = harness
    if service.db.engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL concurrency test")
    ready = Barrier(2)

    def write(_):
        with service.db.session() as session:
            ready.wait(timeout=10)
            onboarding.record(
                session, service.organization_id, None, "interest_saved", "topic", "synthetic-id"
            )
            session.commit()

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(write, [1, 2]))
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(OnboardingMilestone)) == 1
