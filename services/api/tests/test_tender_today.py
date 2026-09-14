"""Public summary admission before private cross-profile paging and counting."""
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, select
from test_auth import _csrf
from test_tender_api import api as _api_fixture
from test_tender_api import create as http_create
from test_tender_api import ingest as http_ingest
from test_tender_api import transition
from test_tender_matching import NOW, PROJECT
from test_tender_repository import create, decide, ingest, publication, read, revised
from test_tender_repository import db as _db_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens.config import DomainError
from helvetic_lens.models import OrganizationMembership
from helvetic_lens.tender_models import TenderDossier, TenderDossierVersion, TenderMonitor
from helvetic_lens.tender_rights import restrict
from helvetic_lens.tender_today import today

api, db, template = _api_fixture, _db_fixture, _template_fixture


def seed(db):
    monitor, raw = create(db, active=True), publication()
    dossier, = ingest(db, monitor, raw)
    return monitor, raw, dossier


def test_pending_reopen_retains_decision_and_exact_evidence_without_writes(db):
    monitor, raw, dossier = seed(db)
    with db.session() as session:
        first, = today(session, "owner", review_state="pending", now=NOW)["items"]
        assert first["id"] == dossier and first["decision"] is None
    decided = decide(db, read(db, dossier))
    with db.session() as session:
        assert today(session, "owner", review_state="pending", now=NOW)["pending_count"] == 0
    updated = revised(raw)
    updated["terms"]["termsCriteria"][0]["description"] = {"en": "5 references required"}
    ingest(db, monitor, updated)
    statements = []
    def capture(conn, cursor, statement, parameters, context, many):
        statements.append(statement)
    event.listen(db.engine, "before_cursor_execute", capture)
    try:
        with db.session() as session:
            page = today(session, "owner", review_state="pending", now=NOW)
            item, = page["items"]
            assert not session.dirty and not session.new
    finally:
        event.remove(db.engine, "before_cursor_execute", capture)
    assert page["pending_count"] == 1 and item["review_state"] == "needs_review"
    assert item["decision"] == "bid" and item["reviewed_sequence"] == decided["sequence"]
    assert item["sequence"] > decided["sequence"]
    assert item["href"].endswith("version=" + item["evidence_version_id"])
    assert len(statements) == 3 and all(s.lstrip().upper().startswith("SELECT") for s in statements)
    assert not any("tender_publication_snapshots" in s or "tender_material_sections" in s or "tender_version_sections" in s for s in statements)
    assert "material" not in item and "match" not in item and "evidence" not in item


@pytest.mark.parametrize("scope", ["project", "publication"])
def test_current_restriction_gates_summary_and_count_without_falling_back(db, scope):
    monitor, raw, dossier = seed(db)
    update = revised(raw)
    ingest(db, monitor, update)
    with db.session() as session:
        restrict(session, scope=scope, target_id=PROJECT if scope == "project" else update["id"],
            policy_reference="PRIVATE POLICY", now=NOW)
        session.commit()
        page = today(session, "owner", now=NOW)
        assert page == {"items": [], "next_cursor": None, "pending_count": 0}
        assert session.get(TenderDossier, dossier).latest_sequence == 2


def test_embargo_irrelevant_discovery_followed_relevance_and_old_profile(db):
    monitor, _, dossier = seed(db)
    with db.session() as session:
        latest = session.scalar(select(TenderDossierVersion))
        latest.publish_after = NOW + timedelta(hours=1)
        session.commit()
        assert today(session, "owner", now=NOW)["items"] == []
        latest.publish_after = NOW - timedelta(hours=1)
        latest.summary = {**latest.summary, "verdict": "excluded"}
        session.commit()
        assert today(session, "owner", now=NOW)["pending_count"] == 0
        session.get(TenderDossier, dossier).following = True
        session.get(TenderMonitor, monitor["id"]).revision = 2
        session.commit()
        item, = today(session, "owner", following=True, now=NOW)["items"]
        assert item["summary"]["verdict"] == "excluded" and item["following"]
        assert item["profile_revision"] != item["current_profile_revision"]


def test_cross_profile_private_tenant_membership_and_archive(db):
    monitor, _, dossier = seed(db)
    with db.session() as session:
        assert today(session, "peer", now=NOW)["items"] == []
        version_id = session.scalar(select(TenderDossierVersion.id))
        with pytest.raises(DomainError):
            today(session, "peer", after_version=version_id, now=NOW)
        session.get(TenderMonitor, monitor["id"]).status = "paused"
        session.commit()
        assert today(session, "owner", now=NOW)["items"][0]["monitor_status"] == "paused"
    with db.organization_context("org-b"), db.session() as session:
        assert today(session, "owner", now=NOW)["items"] == []
    with db.session() as session:
        session.get(TenderMonitor, monitor["id"]).status = "archived"
        session.commit()
        assert today(session, "owner", now=NOW)["pending_count"] == 0
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == "owner"))
        session.commit()
        with pytest.raises(DomainError):
            today(session, "owner", now=NOW)


def test_stable_equal_clock_paging_and_replaced_anchor_across_profiles(db):
    monitor, raw, dossier = seed(db)
    second = create(db, active=True, key="second-profile")
    with db.session() as session:
        original = session.scalar(select(TenderDossierVersion))
        identifiers = [original.id]
        version_values = {column.name: deepcopy(getattr(original, column.name)) for column in TenderDossierVersion.__table__.columns
            if column.name not in {"id", "dossier_id"}}
        for i in range(52):
            row = TenderDossier(organization_id="org-a", monitor_id=monitor["id"] if i % 2 else second["id"],
                project_id=PROJECT, lot_key=str(uuid4()), latest_sequence=1, latest_ordinal=1)
            session.add(row)
            session.flush()
            version = TenderDossierVersion(dossier_id=row.id, **version_values)
            session.add(version)
            session.flush()
            identifiers.append(version.id)
        session.commit()
        first = today(session, "owner", limit=30, now=NOW)
        anchor = session.get(TenderDossierVersion, first["next_cursor"])
        owner = session.get(TenderDossier, anchor.dossier_id)
        # A later material revision preserves the immutable old cursor identity.
        new_values = {**version_values, "sequence": 2, "publication_id": str(uuid4()), "observed_at": NOW + timedelta(seconds=1)}
        session.add(TenderDossierVersion(dossier_id=owner.id, **new_values))
        owner.latest_sequence = 2
        session.commit()
        rest = today(session, "owner", after_version=first["next_cursor"], limit=30, now=NOW)
    assert [i["evidence_version_id"] for i in first["items"] + rest["items"]] == sorted(identifiers, reverse=True)
    assert rest["next_cursor"] is None and len(rest["items"]) == 23


def test_http_today_to_existing_versioned_decision_and_viewer(api):
    client, app, settings, identity = api
    monitor = transition(client, http_create(client), "start")
    raw = publication()
    dossier, = http_ingest(app, identity, monitor, raw)
    path = "/api/tender-watch/today"
    response = client.get(path)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    card, = response.json()["items"]
    exact = f"/api/tender-watch/dossiers/{dossier}/versions/{card['evidence_version_id']}/evidence"
    assert client.get(exact).status_code == 200
    body = {"expected_version": card["version"], "sequence": card["sequence"], "decision": "monitor", "request_key": str(uuid4())}
    decision = f"/api/tender-watch/dossiers/{dossier}/decision"
    assert client.post(decision, json=body).status_code == 403
    assert client.post(decision, json=body, headers=_csrf(client)).status_code == 200
    assert client.get(path, params={"review_state": "pending"}).json()["items"] == []
    update = revised(raw)
    update["terms"]["termsCriteria"][0]["description"] = {"en": "5 references required"}
    http_ingest(app, identity, monitor, update)
    card, = client.get(path, params={"review_state": "pending", "following": True}).json()["items"]
    assert card["decision"] == "monitor" and card["review_state"] == "needs_review"
    assert client.post(decision, json={**body, "request_key": str(uuid4())}, headers=_csrf(client)).status_code == 409
    with app.state.service.db.organization_context(identity["organization"]["id"]), app.state.service.db.session() as session:
        member = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"]))
        member.role = "viewer"
        session.commit()
    assert client.get(path).status_code == 200
    assert client.post(decision, json={**body, "expected_version": card["version"], "sequence": card["sequence"]}, headers=_csrf(client)).status_code == 403
    assert client.get(path, params={"limit": 51}).status_code == 422
    assert client.get(path, params={"review_state": "invalid"}).status_code == 422
    settings.tender_watch_enabled = False
    assert client.get(path).status_code == 404
