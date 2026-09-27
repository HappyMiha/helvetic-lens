"""Page status distinguishes attempted, accepted, queued and intentionally paused work."""
from datetime import timedelta
from uuid import uuid4

from conftest import LAW_URL, policy
from sqlalchemy import select
from test_account_deletion_migration import config
from test_auth import _csrf, _register
from test_product_dossiers import ROOT, active, create, post
from test_product_dossiers import signed as signed

from alembic import command
from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.models import DocumentWatch, Law, OrganizationMembership, Version


def connect(client, route, url=LAW_URL):
    reference = post(client, route + "/entries", {"request_key": str(uuid4()), "kind": "reference", "title": "Original source", "url": url})
    assert reference.status_code == 201, reference.text
    result = post(client, route + "/sources/" + reference.json()["id"] + "/monitor", {})
    assert result.status_code == 200, result.text
    return result.json()["data"]["law_id"]


def connected(client):
    doc, _ = create(client)
    active(client, doc)
    route = ROOT + "/" + doc["id"]
    return route, connect(client, route)


def test_real_failure_retains_success_time_and_recovery_advances_it(signed):
    client, service, _, _ = signed
    route, law_id = connected(client)
    initial = client.get(route).json()["documents"][0]
    assert initial["last_success_at"] == initial["last_checked"] and initial["saved_version_at"]
    assert initial["schedule"] == "due" and not initial["stale"] and initial["active_scan"] is None
    service.fetcher.values[LAW_URL] = DomainError("Official source temporarily unavailable", 502, "source_unavailable")
    attempt = post(client, "/api/scans", {"law_ids": [law_id]})
    assert attempt.status_code == 202 and attempt.json()["status"] == "partial"
    failed = client.get(route).json()["documents"][0]
    assert failed["last_result"] == "failed" and "unavailable" in failed["last_error"]
    assert failed["last_success_at"] == initial["last_success_at"] and failed["last_checked"] > initial["last_checked"]
    assert failed["saved_version_at"] == initial["saved_version_at"] and failed["schedule"] == "scheduled"
    service.fetcher.values[LAW_URL] = policy()
    assert post(client, "/api/scans", {"law_ids": [law_id]}).json()["status"] == "complete"
    recovered = client.get(route).json()["documents"][0]
    assert recovered["last_result"] == "unchanged" and recovered["last_error"] == ""
    assert recovered["last_success_at"] == recovered["last_checked"] > failed["last_success_at"]
    assert client.get("/api/laws/" + law_id).json()["last_success_at"] == recovered["last_success_at"]
    # Two topic references to the same native watch must not duplicate its health card.
    assert connect(client, route) == law_id
    assert len(client.get(route).json()["documents"]) == 1


def test_native_queue_pause_manual_schedule_age_and_operator_states(signed):
    client, service, identity, _ = signed
    route, law_id = connected(client)
    def settings(values):
        result = client.patch("/api/laws/" + law_id, headers=_csrf(client), json=values)
        assert result.status_code == 200, result.text
    settings({"auto_check_enabled": False})
    assert client.get(route).json()["documents"][0]["schedule"] == "manual"
    settings({"active": False})
    assert client.get(route).json()["documents"][0]["schedule"] == "paused"
    assert post(client, "/api/scans", {"law_ids": [law_id]}).status_code == 422
    settings({"active": True, "auto_check_enabled": True})
    scan_id = service.start_scan([law_id], None)
    queued = client.get(route).json()["documents"][0]
    assert queued["active_scan"] == {"id": scan_id, "status": "queued", "stage": "queued"}
    assert post(client, "/api/scans", {"law_ids": [law_id]}).status_code == 409
    with service.db.session() as session:
        watch = session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law_id))
        watch.last_success_at = utcnow() - timedelta(hours=49)
        watch.next_auto_check_at = None
        session.commit()
    aged = client.get(route).json()["documents"][0]
    assert aged["stale"] and aged["schedule"] == "unscheduled"
    with service.db.session() as session:
        membership = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"]))
        membership.role = "viewer"
        session.commit()
    no_operator = client.get(route).json()["documents"][0]
    assert no_operator["schedule"] == "needs_operator"
    assert client.patch("/api/laws/" + law_id, headers=_csrf(client), json={"active": False}).status_code == 403


def test_synthetic_checks_do_not_claim_a_successful_live_timestamp(signed):
    client, service, _, _ = signed
    route, law_id = connected(client)
    with service.db.session() as session:
        law = session.get(Law, law_id)
        session.get(Version, law.current_version_id).synthetic = True
        session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law_id)).last_success_at = None
        session.commit()
    assert post(client, "/api/scans", {"law_ids": [law_id]}).status_code == 202
    document = client.get(route).json()["documents"][0]
    assert document["synthetic"] and document["last_success_at"] is None
    assert document["last_checked"] and not document["stale"]


def test_health_read_and_settings_keep_product_tenant_and_csrf_boundaries(signed):
    client, service, _, _ = signed
    route, law_id = connected(client)
    assert client.patch("/api/laws/" + law_id, json={"active": False}).status_code == 403
    assert client.get(route.replace("pharma", "loyer")).status_code == 404
    with service.db.session() as session:
        session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law_id)).last_error = "Private tenant diagnostic"
        session.commit()
    assert _register(client, "other-source-team@example.ch").status_code == 201
    denied = client.get(route)
    assert denied.status_code == 404 and "Private tenant diagnostic" not in denied.text
    assert client.patch("/api/laws/" + law_id, headers=_csrf(client), json={"active": False}).status_code == 404
    assert post(client, "/api/scans", {"law_ids": [law_id]}).status_code == 404


def test_migration_backfills_only_known_nonsynthetic_success_and_preserves_watches(signed):
    client, service, _, _ = signed
    route, first = connected(client)
    identifiers = [first]
    for name in ("failed", "synthetic", "reused"):
        url = LAW_URL + "?case=" + name
        service.fetcher.values[url] = policy()
        identifiers.append(connect(client, route, url))
    with service.db.session() as session:
        rows = [session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == identifier)) for identifier in identifiers]
        expected_time = rows[0].last_checked.replace(tzinfo=utcnow().tzinfo).isoformat()
        rows[1].last_result = "failed"
        law = session.get(Law, identifiers[2])
        session.get(Version, law.current_version_id).synthetic = True
        rows[3].last_result = "baseline_reused"
        session.commit()
    with service.db.engine.connect() as connection:
        command.downgrade(config(connection), "f4c495bef124")
        command.upgrade(config(connection), "head")
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert connection.exec_driver_sql("SELECT count(*) FROM document_watches").scalar() == 4
    documents = {row["id"]: row for row in client.get(route).json()["documents"]}
    assert documents[first]["last_success_at"] == expected_time
    assert all(documents[key]["last_success_at"] is None for key in identifiers[1:])
    assert all(documents[key]["auto_check_enabled"] and documents[key]["saved_version_at"] for key in identifiers)
