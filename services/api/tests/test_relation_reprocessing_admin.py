from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_administration import csrf, promote, register, settings
from test_relation_profile_freshness import analyse
from test_relation_reprocessing import enqueue, execute

from helvetic_lens import jobs
from helvetic_lens import relation_candidates as rules
from helvetic_lens import relation_reprocessing as reprocess
from helvetic_lens.models import Job, Organization, OrganizationMembership, User


def test_filtered_history_keeps_maintenance_visible_beyond_recent_other_jobs(harness):
    client, _, service, _ = harness
    job = enqueue(service, dry_run=True)
    with service.db.session() as session:
        for index in range(25):
            jobs.enqueue(session, job_type="scan", target_type="source", target_id=str(index), queue="ingest", idempotency_key=f"synthetic-scan-{index}")
        session.commit()
    response = client.get("/api/jobs", params={"job_type": reprocess.JOB_TYPE, "limit": 20})
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [job["id"]]
    metadata = response.json()[0]["maintenance"]
    assert metadata == {"dry_run": True, "rule_revision": rules.RULE_REVISION, "captured_at": job["maintenance"]["captured_at"]}
    assert "checkpoint" not in metadata and "request_id" not in metadata
    assert len(client.get("/api/jobs", params={"limit": 20}).json()) == 20


def test_preview_examples_have_saved_document_labels(harness, monkeypatch):
    _, _, service, _ = harness
    analyse(harness)
    monkeypatch.setattr(rules, "RULE_REVISION", "synthetic-new-rule")
    result = execute(service, enqueue(service, dry_run=True))["result"]["data"]
    assert "Data Protection" in result["examples"][0]["target_title"]
    assert result["examples"][0]["source_title"]
    assert result["examples"][0]["target_work_id"]


@pytest.mark.parametrize("dry_run", [True, False])
def test_lost_response_replay_recovers_original_job_after_rule_change(harness, monkeypatch, dry_run):
    client, _, service, _ = harness
    request = {"request_id": str(uuid4()), "rule_revision": rules.RULE_REVISION, "dry_run": dry_run}
    original = client.post("/api/admin/relation-reprocessing", json=request)
    assert original.status_code == 202
    monkeypatch.setattr(rules, "RULE_REVISION", "synthetic-next-rule")
    recovered = client.post("/api/admin/relation-reprocessing", json=request)
    assert recovered.status_code == 202 and recovered.json()["id"] == original.json()["id"]
    assert recovered.json()["maintenance"]["rule_revision"] == request["rule_revision"]
    rejected = client.post("/api/admin/relation-reprocessing", json={**request, "request_id": str(uuid4())})
    assert rejected.status_code == 409 and rejected.json()["code"] == "relation_reprocess_rule_changed"
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job).where(Job.type == reprocess.JOB_TYPE)) == 1


def test_filtered_maintenance_history_requires_current_platform_role(tmp_path):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient

    from helvetic_lens.main import create_app

    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        params = {"job_type": reprocess.JOB_TYPE}
        assert client.get("/api/jobs", params=params).status_code == 401
        register(client, "maintenance-ui@example.ch")
        assert client.get("/api/jobs", params=params).status_code == 403
        promote(app.state.service, "maintenance-ui@example.ch")
        response = client.post("/api/admin/relation-reprocessing", json={"dry_run": True}, headers=csrf(client))
        assert response.status_code == 202
        assert len(client.get("/api/jobs", params=params).json()) == 1
        with app.state.service.db.session(include_all_organizations=True) as session:
            session.scalar(select(User).where(User.email == "maintenance-ui@example.ch")).platform_admin = False
            session.commit()
        assert client.get("/api/jobs", params=params).status_code == 403
        assert not any(row["type"] == reprocess.JOB_TYPE for row in client.get("/api/jobs").json())


def test_platform_admin_in_read_only_organization_can_manage_only_maintenance(tmp_path):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient

    from helvetic_lens.main import create_app

    config = settings(tmp_path)
    config.job_execution_mode = "celery"
    app = create_app(config, fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        register(client, "platform-viewer@example.ch")
        promote(app.state.service, "platform-viewer@example.ch")
        organization = client.get("/api/auth/session").json()["organization"]["id"]
        with app.state.service.db.session(include_all_organizations=True) as session:
            user = session.scalar(select(User).where(User.email == "platform-viewer@example.ch"))
            session.scalar(select(OrganizationMembership).where(OrganizationMembership.organization_id == organization, OrganizationMembership.user_id == user.id)).role = "viewer"
            other, _ = jobs.enqueue(session, job_type="scan", target_type="source", target_id="synthetic-source", queue="ingest", idempotency_key="unrelated", organization_id=organization)
            foreign = Organization(name="Other maintenance owner", slug="other-maintenance-owner")
            session.add(foreign)
            session.flush()
            private, _ = jobs.enqueue(session, job_type=reprocess.JOB_TYPE, target_type="relation_candidate_rules", target_id=rules.RULE_REVISION,
                queue="maintenance", idempotency_key="foreign-maintenance", organization_id=foreign.id)
            session.commit()
            other_id = other.id
            private_id = private.id
        started = client.post("/api/admin/relation-reprocessing", json={}, headers=csrf(client))
        assert started.status_code == 202
        job_id = started.json()["id"]
        action = f"/api/admin/relation-reprocessing/jobs/{job_id}"
        assert client.post(f"{action}/cancel").status_code == 403  # CSRF still applies.
        cancelled = client.post(f"{action}/cancel", headers=csrf(client))
        assert cancelled.status_code == 200 and cancelled.json()["state"] == "cancelled"
        resumed = client.post(f"{action}/retry", headers=csrf(client))
        assert resumed.status_code == 200 and resumed.json()["state"] == "queued"
        assert client.post(f"/api/admin/relation-reprocessing/jobs/{other_id}/cancel", headers=csrf(client)).status_code == 404
        assert client.post(f"/api/jobs/{other_id}/cancel", headers=csrf(client)).status_code == 403
        assert client.get(f"/api/jobs/{private_id}").status_code == 404
        assert client.post(f"/api/admin/relation-reprocessing/jobs/{private_id}/cancel", headers=csrf(client)).status_code == 404
        assert all(row["id"] != private_id for row in client.get("/api/jobs", params={"job_type": reprocess.JOB_TYPE}).json())
