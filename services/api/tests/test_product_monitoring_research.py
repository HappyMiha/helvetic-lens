"""Native matching, standing authority and real durable research through both products."""
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_private_dossier_monitoring import private
from test_product_contributions import no_discovery
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_investigations import complete, tick
from test_topic_matching import add_event
from test_topic_validity import evaluate

from helvetic_lens.db import utcnow
from helvetic_lens.models import OrganizationMembership, RegulatoryEvent
from helvetic_lens.product_investigation_models import (
    Investigation,
)
from helvetic_lens.product_investigation_models import (
    MonitoringResearchPolicy as Policy,
)
from helvetic_lens.product_investigation_models import MonitoringResearchTrigger as Trigger
from helvetic_lens.product_monitoring_research import enqueue_due


def enable(client, root, **values):
    current = client.get(root + "/monitoring-research")
    assert current.status_code == 200, current.text
    data = {"request_key": str(uuid4()), "expected_revision": current.json()["policy"]["revision"],
        "enabled": True, "daily_limit": 3, "standing_authority_confirmed": True, **values}
    response = post(client, root + "/monitoring-research", data)
    assert response.status_code == 200, response.text
    return response.json(), data


def due(service):
    with service.db.session() as session:
        for row in session.scalars(select(Policy)):
            row.next_check_at = utcnow() - timedelta(seconds=1)
        session.commit()
    return enqueue_due(service.db, service.settings)


def signal(service, topic, *, change=None):
    with service.db.session() as session:
        event = session.scalar(select(RegulatoryEvent.id))
    event = event or add_event(service)
    if change:
        with service.db.session() as session:
            row = session.get(RegulatoryEvent, event)
            row.evidence_json = {**row.evidence_json, "notice": change}
            session.commit()
    evaluate(service, topic, event, "history")
    return event


def model(monkeypatch, target, during=None):
    calls = []
    async def respond(system, user, **kwargs):
        value = json.loads(user)
        calls.append(value)
        if during:
            during(value)
        if "current" in value:
            return json.dumps({"changes": [{"current_claim_id": value["current"][0]["id"],
                "previous_claim_id": value["previous"][0]["id"], "kind": "UPDATES"}]})
        part = value["source"]["excerpts"][0]
        assert value["existing_claims"] == []
        quote = part["text"][:500]
        return json.dumps({"claims": [{"statement": quote, "quote": quote, "locator": part["passage"], "relation": "SUPPORTS"}]})
    monkeypatch.setattr(target, "complete", respond)
    return calls


@pytest.mark.parametrize("product", ["pharma", "loyer"])
def test_native_signal_starts_private_evidence_and_comparison_once(signed, monkeypatch, product):
    client, service, identity, target = signed
    doc, root, topic = private(client, product)
    calls = model(monkeypatch, target)
    external = no_discovery(monkeypatch)
    earlier = post(client, root + "/entries", {"request_key": str(uuid4()), "kind": "note",
        "body": "Earlier naturalisation rules remain recorded in the private dossier.", "analyse": True}).json()
    prior = complete(client, service, root + "/investigations", earlier["analysis"])
    assert prior["claims"]
    saved, command = enable(client, root)
    assert post(client, root + "/monitoring-research", command).json() == saved
    assert post(client, root + "/monitoring-research", {**command, "daily_limit": 2}).status_code == 409
    signal(service, topic)
    assert due(service) == {"checked": 1, "started": 1}
    page = client.get(root + "/monitoring-research").json()
    run = page["items"][0]["investigation"]
    with service.db.session() as session:
        stored = session.get(Investigation, run["id"])
        assert stored.session_id is None and stored.external_discovery is False and stored.publication_id is None
    result = complete(client, service, root + "/investigations", run)
    assert result["status"] == "completed", result
    assert result["sources"][0]["kind"] == "official_event_metadata"
    changes = client.get(root + "/evidence-changes").json()
    assert changes["total"] == 1 and changes["items"][0]["kind"] == "UPDATES"
    assert len(calls) == 3 and external == []
    assert due(service)["started"] == 0
    tick(service, run["id"])
    assert len(calls) == 3
    assert client.get(root + "/monitoring-research").json()["total"] == 1
    assert client.get(root.split("/dossiers/")[0] + "/public-dossiers").json()["items"] == []
    other = root.replace(product, "loyer" if product == "pharma" else "pharma")
    assert client.get(other + "/monitoring-research").status_code == 404
    client.cookies.clear()
    assert client.get(root + "/monitoring-research").status_code == 401


def test_baseline_budget_deferral_and_settings_do_not_replay_old_signals(signed, monkeypatch):
    client, service, _, target = signed
    _, root, topic = private(client)
    calls = model(monkeypatch, target)
    signal(service, topic)
    enable(client, root, daily_limit=1)
    assert due(service)["started"] == 0  # Existing matches are an explicit baseline.
    signal(service, topic, change="New official notice one.")
    assert due(service)["started"] == 1
    first = client.get(root + "/monitoring-research").json()["items"][0]["investigation"]
    complete(client, service, root + "/investigations", first)
    signal(service, topic, change="New official notice two.")
    assert due(service)["started"] == 0
    page = client.get(root + "/monitoring-research").json()
    assert page["items"][0]["state"] == "pending" and page["policy"]["used_today"] == 1
    with service.db.session() as session:
        session.scalar(select(Policy)).budget_day = "2000-01-01"
        session.commit()
    assert due(service)["started"] == 1
    second = client.get(root + "/monitoring-research").json()["items"][0]["investigation"]
    complete(client, service, root + "/investigations", second)
    enable(client, root, enabled=False)
    reset, _ = enable(client, root)
    assert reset["policy"]["checked_at"] is None and reset["policy"]["used_today"] == 1
    assert due(service)["started"] == 0
    assert len(calls) == 3


@pytest.mark.parametrize("race", ["disable", "membership", "source"])
def test_inflight_authority_and_source_changes_discard_model_results(signed, monkeypatch, race):
    client, service, identity, target = signed
    _, root, topic = private(client)
    enable(client, root)
    event = signal(service, topic)
    due(service)
    run = client.get(root + "/monitoring-research").json()["items"][0]["investigation"]
    def change(_):
        if race == "disable":
            enable(client, root, enabled=False)
        else:
            with service.db.session() as session:
                if race == "membership":
                    member = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"]))
                    member.role = "viewer"
                else:
                    row = session.get(RegulatoryEvent, event)
                    row.evidence_json = {**row.evidence_json, "changed": "during analysis"}
                session.commit()
    calls = model(monkeypatch, target, change)
    tick(service, run["id"])
    tick(service, run["id"])
    with service.db.session() as session:
        stored = session.get(Investigation, run["id"])
        assert stored.status in {"cancelled", "paused"}
    result = client.get(root + "/investigations/" + run["id"])
    if result.status_code == 200:
        assert result.json()["claims"] == []
    assert len(calls) == 1
    assert due(service)["started"] == 0


def test_standing_authority_survives_logout_without_a_manufactured_session(signed, monkeypatch):
    client, service, _, target = signed
    _, root, topic = private(client)
    calls = model(monkeypatch, target)
    enable(client, root)
    assert post(client, "/api/auth/logout", {}).status_code == 200
    signal(service, topic)
    assert due(service)["started"] == 1
    with service.db.session() as session:
        identifier = session.scalar(select(Investigation.id))
    for _ in range(4):
        tick(service, identifier)
    with service.db.session() as session:
        run = session.get(Investigation, identifier)
        assert run.status == "completed" and run.session_id is None
    assert len(calls) == 1


@pytest.mark.parametrize("revocation", ["admission", "exclusion", "profile", "membership", "account", "topic"])
def test_pending_work_is_fenced_before_any_paid_request(signed, monkeypatch, revocation):
    from helvetic_lens.legal_profile_models import LegalMonitoringProfile
    from helvetic_lens.models import MonitoringTopic, RegulatoryEventState, User
    from helvetic_lens.product_models import DossierEntry

    client, service, identity, target = signed
    doc, root, topic = private(client)
    calls = model(monkeypatch, target)
    enable(client, root)
    signal(service, topic)
    due(service)
    run = client.get(root + "/monitoring-research").json()["items"][0]["investigation"]
    with service.db.session() as session:
        if revocation == "admission":
            session.delete(session.scalar(select(RegulatoryEventState)))
        elif revocation == "exclusion":
            session.add(DossierEntry(dossier_id=doc["id"], request_key=str(uuid4()), kind="source_review",
                url="https://fedlex.data.admin.ch/eli/cc/topic-match", data_json={"decision": "exclude"}, body="Exclude this source."))
        elif revocation == "profile":
            session.get(LegalMonitoringProfile, doc["profile"]["id"]).revision += 1
        elif revocation == "membership":
            session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"])).role = "viewer"
        elif revocation == "account":
            session.get(User, identity["user"]["id"]).active = False
        else:
            session.get(MonitoringTopic, topic["id"]).status = "paused"
        session.commit()
    tick(service, run["id"])
    with service.db.session() as session:
        assert session.get(Investigation, run["id"]).status == "paused"
    assert not calls
    due(service)
    assert not calls


def test_roles_csrf_revision_and_explicit_consent(signed):
    from test_auth import _csrf
    from test_private_dossier_monitoring import invite
    from test_product_teams import colleague, switch

    client, service, identity, _ = signed
    owner = dict(client.cookies)
    uid, cookies = colleague(client, service, identity, role="organization_admin")
    _, root, _ = private(client)
    body = {"request_key": str(uuid4()), "expected_revision": 0, "enabled": True,
        "daily_limit": 3, "standing_authority_confirmed": True}
    assert client.post(root + "/monitoring-research", json=body).status_code == 403
    for values in ({"standing_authority_confirmed": False}, {"standing_authority_confirmed": 1}, {"daily_limit": 7}, {"daily_limit": True}):
        assert post(client, root + "/monitoring-research", {**body, **values}).status_code == 422
    assert post(client, root + "/monitoring-research", {**body, "expected_revision": 4}).status_code == 409
    invite(client, root, uid, "VIEWER", cookies)
    switch(client, cookies)
    assert client.get(root + "/monitoring-research").json()["can_manage"] is False
    assert post(client, root + "/monitoring-research", body).status_code == 403
    switch(client, owner)
    team = client.get(root + "/team").json()
    assert client.put(root + "/team/members/" + uid, headers=_csrf(client),
        json={"expected_revision": team["revision"], "role": "EDITOR"}).status_code == 200
    switch(client, cookies)
    assert client.get(root + "/monitoring-research").json()["can_manage"] is True
    assert post(client, root + "/monitoring-research", body).status_code == 200


def test_guest_editor_cannot_enable_host_monitoring_research(signed):
    from test_product_guests import accept, guest, invitation
    from test_product_teams import switch

    client, service, _, _ = signed
    _, root, _ = private(client)
    uid, cookies = guest(client, service)
    invitation_id = invitation(client, root, uid, "EDITOR")
    switch(client, cookies)
    accept(client, root, invitation_id)
    result = client.get(root + "/monitoring-research")
    assert result.status_code == 200 and not result.json()["can_manage"], result.text
    assert post(client, root + "/monitoring-research", {"request_key": str(uuid4()), "expected_revision": 0,
        "enabled": True, "daily_limit": 3, "standing_authority_confirmed": True}).status_code == 403


def test_interrupted_step_requires_explicit_budgeted_retry(signed, monkeypatch):
    from copy import deepcopy

    from helvetic_lens.product_investigation_models import InvestigationBranch

    client, service, _, target = signed
    _, root, topic = private(client)
    calls = model(monkeypatch, target)
    enable(client, root, daily_limit=2)
    signal(service, topic)
    due(service)
    run = client.get(root + "/monitoring-research").json()["items"][0]["investigation"]
    tick(service, run["id"])
    with service.db.session() as session:
        branch = session.scalar(select(InvestigationBranch))
        state = deepcopy(branch.checkpoint)
        state.update(inflight="interrupted-receipt", steps=[{"id": "interrupted-receipt", "phase": "extract", "status": "running"}])
        branch.checkpoint = state
        session.commit()
    interrupted = complete(client, service, root + "/investigations", run)
    assert interrupted["status"] == "failed" and not calls
    assert due(service)["started"] == 0
    retried = post(client, root + "/investigations/" + run["id"] + "/control",
        {"expected_revision": interrupted["revision"], "action": "retry"})
    assert retried.status_code == 200, retried.text
    result = complete(client, service, root + "/investigations", retried.json())
    assert result["claims"] and len(calls) == 1
    assert client.get(root + "/monitoring-research").json()["policy"]["used_today"] == 2


def test_receipt_and_job_creation_rollback_together(signed, monkeypatch):
    from helvetic_lens import product_monitoring_research as research

    client, service, _, _ = signed
    _, root, topic = private(client)
    enable(client, root)
    signal(service, topic)
    original = research.enqueue
    def crash(*args):
        raise RuntimeError("Synthetic database boundary failure")
    monkeypatch.setattr(research, "enqueue", crash)
    with pytest.raises(RuntimeError, match="Synthetic"):
        due(service)
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Trigger)) == 0
        assert session.scalar(select(func.count()).select_from(Investigation)) == 0
        assert session.scalar(select(Policy)).budget_used == 0
    monkeypatch.setattr(research, "enqueue", original)
    assert due(service)["started"] == 1
    assert due(service)["started"] == 0


def test_schema_scope_pagination_and_retained_migration(signed):
    from pathlib import Path

    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from sqlalchemy.exc import IntegrityError
    from test_product_dossiers import create

    from alembic import command as migrate
    from helvetic_lens.db import Base

    client, service, _, _ = signed
    doc, root, topic = private(client)
    def config(connection):
        value = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        value.set_main_option("script_location", str(Path(__file__).parents[1] / "alembic"))
        value.attributes["connection"] = connection
        return value
    with service.db.engine.connect() as connection:
        migrate.downgrade(config(connection), "01d495bef125")
        migrate.upgrade(config(connection), "head")
        context = MigrationContext.configure(connection, opts={"include_object": lambda obj, name, kind, reflected, other:
            kind != "table" or name in {Policy.__tablename__, Trigger.__tablename__}})
        assert compare_metadata(context, Base.metadata) == []
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    assert client.get(root).status_code == 200
    enable(client, root)
    signal(service, topic)
    due(service)
    other, _ = create(client)
    with service.db.session() as session:
        trigger = session.scalar(select(Trigger))
        trigger.dossier_id = other["id"]
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
        trigger = session.scalar(select(Trigger))
        for i in range(22):
            session.add(Trigger(organization_id=trigger.organization_id, dossier_id=trigger.dossier_id,
                policy_id=trigger.policy_id, policy_revision=1, match_id=str(uuid4()), evaluation_fingerprint=str(i).zfill(64),
                matched_at=utcnow(), state="skipped", reason="Synthetic pagination fixture", source_json={}))
        session.commit()
    first = client.get(root + "/monitoring-research").json()
    second = client.get(root + "/monitoring-research?offset=20").json()
    assert first["total"] == second["total"] == 23
    assert len(first["items"]) == 20 and len(second["items"]) == 3
    assert not {v["id"] for v in first["items"]} & {v["id"] for v in second["items"]}
    exported = client.get(root + "/export").json()["monitoring_research"]
    assert len(exported["items"]) == 23
    with service.db.engine.connect() as connection, pytest.raises(RuntimeError, match="Retained monitoring research"):
        migrate.downgrade(config(connection), "01d495bef125")


def test_scheduled_request_identity_cannot_be_reused_as_a_public_query(signed):
    client, service, _, _ = signed
    _, root, topic = private(client)
    enable(client, root)
    signal(service, topic)
    due(service)
    with service.db.session() as session:
        run = session.scalar(select(Investigation))
        body = {"request_key": run.request_key, "question": run.question, "public_query_confirmed": True}
    assert post(client, root + "/investigations", body).status_code == 409
