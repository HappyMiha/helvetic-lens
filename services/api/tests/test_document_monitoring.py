from datetime import timedelta

import pytest
from conftest import LAW_URL, add_law, policy
from sqlalchemy import select

from helvetic_lens import jobs
from helvetic_lens.db import utcnow
from helvetic_lens.document_monitoring import enqueue_due
from helvetic_lens.models import (
    DocumentWatch,
    Job,
    Organization,
    OrganizationMembership,
    Scan,
    ScanItem,
    User,
)


def operator(service, organization=None):
    organization = organization or service.organization_id
    with service.db.session(include_all_organizations=True) as session:
        user = User(email=organization + "@test.invalid", password_hash="synthetic", name="Test operator")
        session.add(user)
        session.flush()
        session.add(OrganizationMembership(user_id=user.id, organization_id=organization, role="organization_admin"))
        session.commit()
        return user.id


def enable(client, law):
    response = client.patch("/api/laws/" + law["id"], json={"auto_check_enabled": True})
    assert response.status_code == 200, response.text
    assert response.json()["auto_check_enabled"] and response.json()["next_auto_check_at"]


def scheduled(service):
    with service.db.session() as session:
        return session.scalar(select(Job).where(Job.type == "scan").order_by(Job.created_at.desc()))


@pytest.mark.asyncio
async def test_opt_in_scan_saves_real_observation_once_and_defers_next_day(harness):
    client, fetcher, service, _ = harness
    law = add_law(client)
    operator(service)
    assert not law["auto_check_enabled"] and law["next_auto_check_at"] is None
    assert enqueue_due(service.db, service.settings) == {"queued": 0, "documents": 0}
    enable(client, law)
    assert enqueue_due(service.db, service.settings) == {"queued": 1, "documents": 1}
    assert enqueue_due(service.db, service.settings) == {"queued": 0, "documents": 0}
    job = scheduled(service)
    assert job.payload["automatic"] and job.organization_id == service.organization_id
    result = await service.execute_job(job.id)
    assert result["state"] == "succeeded", result
    detail = client.get("/api/laws/" + law["id"]).json()
    assert detail["last_result"] == "unchanged"
    assert len(fetcher.calls) == 2
    with service.db.session() as session:
        watch = session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law["id"]))
        next_run = watch.next_auto_check_at.replace(tzinfo=utcnow().tzinfo)
        assert timedelta(hours=23, minutes=59) < next_run - utcnow() <= timedelta(days=1)
        scan = session.get(Scan, job.target_id)
        assert scan.status == "complete"


@pytest.mark.parametrize("stop", ["disable", "pause", "revoke"])
@pytest.mark.asyncio
async def test_queued_automatic_fetch_rechecks_pause_opt_in_and_membership(harness, stop):
    client, fetcher, service, _ = harness
    law = add_law(client)
    user_id = operator(service)
    enable(client, law)
    assert enqueue_due(service.db, service.settings)["queued"] == 1
    if stop == "revoke":
        with service.db.session() as session:
            session.get(User, user_id).active = False
            session.commit()
    else:
        client.patch("/api/laws/" + law["id"], json={"active" if stop == "pause" else "auto_check_enabled": False})
    result = await service.execute_job(scheduled(service).id)
    assert result["state"] == "succeeded"
    assert len(fetcher.calls) == 1
    with service.db.session() as session:
        item = session.scalar(select(ScanItem))
        assert item.result == "skipped"
    assert enqueue_due(service.db, service.settings)["queued"] == 0


def test_scheduler_bounds_batches_and_keeps_tenant_jobs_separate(harness):
    client, fetcher, service, _ = harness
    operator(service)
    for i in range(7):
        url = LAW_URL + f"?law={i}"
        fetcher.values[url] = policy()
        enable(client, add_law(client, url=url))
    with service.db.session(include_all_organizations=True) as session:
        other = Organization(name="Other tenant", slug="other-tenant")
        session.add(other)
        session.commit()
        other_id = other.id
    operator(service, other_id)
    # No opted-in watches in the second tenant; it must receive no scan/job.
    assert enqueue_due(service.db, service.settings) == {"queued": 1, "documents": 5}
    assert enqueue_due(service.db, service.settings) == {"queued": 1, "documents": 2}
    assert enqueue_due(service.db, service.settings) == {"queued": 0, "documents": 0}
    with service.db.session(include_all_organizations=True) as session:
        scans = list(session.scalars(select(Scan)))
        assert len(scans) == 2 and {s.organization_id for s in scans} == {service.organization_id}
        assert sorted(s.total for s in scans) == [2, 5]


def test_manual_scan_in_progress_and_missing_operator_are_not_duplicated(harness):
    client, _, service, _ = harness
    law = add_law(client)
    enable(client, law)
    assert enqueue_due(service.db, service.settings)["queued"] == 0
    operator(service)
    service.start_scan([law["id"]], None)
    assert enqueue_due(service.db, service.settings)["queued"] == 0


@pytest.mark.asyncio
async def test_automatic_source_failure_keeps_last_good_evidence_and_does_not_retry_continuously(harness):
    from helvetic_lens.config import DomainError

    client, fetcher, service, model = harness
    law = add_law(client)
    original = client.get("/api/laws/" + law["id"]).json()["current_version_id"]
    operator(service)
    enable(client, law)
    fetcher.values[LAW_URL] = DomainError("Official source unavailable", 502, "source_unavailable")
    enqueue_due(service.db, service.settings)
    job = scheduled(service)
    await service.execute_job(job.id)
    detail = client.get("/api/laws/" + law["id"]).json()
    assert detail["current_version_id"] == original
    assert detail["last_result"] == "failed" and "unavailable" in detail["last_error"]
    assert not model.calls
    assert enqueue_due(service.db, service.settings)["queued"] == 0
    with service.db.session() as session:
        assert session.get(Scan, job.target_id).status == "partial"


@pytest.mark.asyncio
async def test_automatic_change_retains_diff_and_queues_ai_separately(harness):
    client, fetcher, service, model = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    operator(service)
    enable(client, law)
    fetcher.values[LAW_URL] = policy(60)
    enqueue_due(service.db, service.settings)
    job = scheduled(service)
    result = await service.execute_job(job.id)
    assert result["state"] == "succeeded", result
    assert not model.calls
    with service.db.session() as session:
        item = session.scalar(select(ScanItem))
        assert item.result == "changed" and item.analysis_status == "queued"
        assert item.comparison_id
        ai = session.scalar(select(Job).where(Job.type == "impact_analysis"))
        assert ai and ai.state in jobs.CLAIMABLE_STATES


def test_daily_schedule_requires_csrf_admin_and_isolated_watch_ownership(tmp_path):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_auth import _csrf, _register, _settings

    from helvetic_lens.main import create_app

    app = create_app(_settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as first, TestClient(app) as second:
        tenants = []
        laws = []
        for index, client in enumerate((first, second)):
            registered = _register(client, f"operator{index}@example.ch", f"Tenant {index}").json()
            tenants.append(registered["organization"]["id"])
            law = client.post("/api/laws", json={"url": LAW_URL, "synthetic": True},
                              headers=_csrf(client)).json()
            laws.append(law["id"])
            endpoint = "/api/laws/" + law["id"]
            assert client.patch(endpoint, json={"auto_check_enabled": True}).status_code == 403
            assert client.patch(endpoint, json={"auto_check_enabled": True}, headers=_csrf(client)).status_code == 200
        assert second.patch("/api/laws/" + laws[0], json={"auto_check_enabled": False},
                            headers=_csrf(second)).status_code == 404
        service = app.state.service
        assert enqueue_due(service.db, service.settings) == {"queued": 2, "documents": 2}
        with service.db.session(include_all_organizations=True) as session:
            scans = list(session.scalars(select(Scan)))
            assert {scan.organization_id for scan in scans} == set(tenants)
            for scan in scans:
                item = session.scalar(select(ScanItem).where(ScanItem.scan_id == scan.id))
                assert item.organization_id == scan.organization_id
                assert item.law_id == laws[tenants.index(scan.organization_id)]
            membership = session.scalar(select(OrganizationMembership).where(
                OrganizationMembership.organization_id == tenants[0]))
            membership.role = "viewer"
            session.commit()
        assert first.get("/api/laws/" + laws[0]).json()["auto_check_enabled"]
        denied = first.patch("/api/laws/" + laws[0], json={"auto_check_enabled": False}, headers=_csrf(first))
        assert denied.status_code == 403 and denied.json()["code"] == "viewer_read_only"


def test_upgrade_preserves_existing_watch_and_keeps_automatic_fetch_off(harness):
    from test_account_deletion_migration import config

    from alembic import command

    client, _, service, _ = harness
    law = add_law(client)
    original = client.get("/api/laws/" + law["id"]).json()["current_version_id"]
    with service.db.engine.begin() as connection:
        command.downgrade(config(connection), "d0b384adf013")
        command.upgrade(config(connection), "head")
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    detail = client.get("/api/laws/" + law["id"]).json()
    assert detail["current_version_id"] == original
    assert detail["auto_check_enabled"] is False and detail["next_auto_check_at"] is None
    assert len(detail["versions"]) == 1
