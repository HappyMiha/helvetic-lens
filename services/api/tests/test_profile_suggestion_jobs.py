"""Actual HTTP admission, durable worker and reopened draft; no external inference."""
import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_auth import _csrf, _register
from test_legal_profiles import ROOT, ProposalModel, config, create, post
from test_legal_profiles import signed as signed
from test_product_teams import accept, colleague, invite, managed, switch

from helvetic_lens import ai_dispatch
from helvetic_lens import jobs as durable_jobs
from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.legal_profile_models import LegalMonitoringProfile
from helvetic_lens.models import Job, MonitoringTopic, OutboxMessage, User
from helvetic_lens.profile_suggestion_jobs import TYPE


def request(client, profile, **changes):
    body = {"request_key": str(uuid4()), "expected_revision": profile["revision"],
        "feedback": "Prefer procedure", "locale": "en-CH", **changes}
    route = f"{ROOT}/{profile['id']}/suggestions"
    result = post(client, route, body)
    assert result.status_code == 202, result.text
    return route, body, result.json()["request"]


def execute(service, identifier):
    return asyncio.run(service.execute_job(identifier, "suggestion-test"))


@pytest.mark.parametrize("product", [None, "legal", "pharma"])
def test_durable_suggestion_exact_reopen_idempotency_and_explicit_selection(signed, product):
    client, service, _ = signed
    service.model_client = model = ProposalModel()
    if product:
        result = post(client, f"/api/products/{product}/dossiers", {"creation_key": str(uuid4()), "config": config()})
        assert result.status_code == 201, result.text
        profile = result.json()["profile"]
    else:
        profile, _ = create(client)
    route = f"{ROOT}/{profile['id']}/suggestions"
    assert client.get(route).json() == {"request": None}
    route, body, job = request(client, profile)
    assert job["status"] == "queued" and job["result"] is None and model.inputs == []
    assert post(client, route, body).json()["request"]["id"] == job["id"]
    assert post(client, route, {**body, "request_key": str(uuid4())}).json()["request"]["id"] == job["id"]
    assert post(client, route, {**body, "feedback": "Other request"}).status_code == 409
    with service.db.session() as session:
        saved = session.get(Job, job["id"])
        assert (saved.queue, saved.priority) == ("ai_interactive", 9)
        assert session.scalar(select(func.count()).select_from(Job).where(Job.type == TYPE)) == 1
        assert session.scalar(select(func.count()).select_from(OutboxMessage).where(OutboxMessage.job_id == saved.id)) == 1
    execute(service, job["id"])
    result = client.get(route).json()["request"]
    assert result["status"] == "completed" and len(model.inputs) == 1
    assert result["result"]["suggestions"][0]["name"] == "Citizenship procedure"
    assert result["result"]["profile"]["config"]["topics"] == profile["config"]["topics"]
    assert client.get(route).json()["request"] == result
    assert post(client, route, body).json()["request"] == result
    execute(service, job["id"])
    assert len(model.inputs) == 1
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(MonitoringTopic)) == 0
        cards = result["result"]["suggestions"]
        assert session.get(LegalMonitoringProfile, profile["id"]).proposals_json[cards[0]["id"]]["domain_pack"]["id"] == ("PharmaPack" if product == "pharma" else "LegalPack")
    updated = client.put(f"{ROOT}/{profile['id']}", headers=_csrf(client), json={"expected_revision": 2,
        "step": 2, "config": {**result["result"]["profile"]["config"], "topics": cards}})
    assert updated.status_code == 200, updated.text
    assert client.get(route).json()["request"]["status"] == "superseded"
    assert client.get(route).json()["request"]["result"] is None
    active = post(client, f"{ROOT}/{profile['id']}/activate", {"expected_revision": 3})
    assert active.status_code == 200, active.text
    assert active.json()["topics"][0]["plan"]["ai_assisted"] is True


@pytest.mark.parametrize("busy_code", ["model_rate_limited", "model_provider_busy"])
def test_busy_waits_durably_without_http_failure_or_early_retry(signed, busy_code):
    client, service, _ = signed
    profile, _ = create(client)
    class BusyModel(ProposalModel):
        calls = 0

        async def complete(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise DomainError("private provider diagnostic", 503, busy_code)
            return await super().complete(*args, **kwargs)
    service.model_client = model = BusyModel()
    route, _, job = request(client, profile)
    execute(service, job["id"])
    waiting = client.get(route).json()["request"]
    assert waiting["status"] == "waiting" and waiting["result"] is None
    assert "private provider" not in str(waiting) and "Waiting" in waiting["error"]
    with service.db.session() as session:
        saved = session.get(Job, job["id"])
        assert saved.attempts == 0 and saved.available_at > utcnow().replace(tzinfo=None)
        assert session.get(LegalMonitoringProfile, profile["id"]).revision == 1
    execute(service, job["id"])
    assert model.calls == 1
    with service.db.session() as session:
        session.get(Job, job["id"]).available_at = utcnow() - timedelta(seconds=1)
        session.commit()
    execute(service, job["id"])
    assert model.calls == 2 and client.get(route).json()["request"]["status"] == "completed"


@pytest.mark.parametrize("change,after", [("revision", False), ("revision", True), ("access", False), ("access", True), ("activated", False)])
def test_changed_draft_or_access_never_commits_stale_cards(signed, change, after):
    client, service, identity = signed
    profile, _ = create(client)
    user_id = identity["user"]["id"]
    def alter():
        with service.db.session() as session:
            row = session.get(LegalMonitoringProfile, profile["id"])
            if change == "revision":
                row.revision += 1
                row.config_json = {**row.config_json, "goal": "New current goal"}
            elif change == "activated":
                row.status = "active"
            else:
                session.get(User, user_id).active = False
            session.commit()
    class ChangingModel(ProposalModel):
        async def complete(self, *args, **kwargs):
            output = await super().complete(*args, **kwargs)
            alter()
            return output
    service.model_client = model = ChangingModel()
    route, _, job = request(client, profile)
    if not after:
        alter()
    execute(service, job["id"])
    assert len(model.inputs) == int(after)
    with service.db.session() as session:
        saved = session.get(Job, job["id"])
        assert saved.state == "cancelled" and saved.result_json is None
        assert session.get(LegalMonitoringProfile, profile["id"]).proposals_json == {}
    if change != "access":
        assert client.get(route).json()["request"]["status"] == "superseded"


def test_private_job_does_not_escape_profile_reader_or_generic_controls(signed):
    client, service, _ = signed
    profile, _ = create(client)
    route, _, job = request(client, profile)
    assert job["id"] not in str(client.get("/api/jobs").json())
    for suffix in ("", "/retry", "/cancel"):
        response = post(client, "/api/jobs/" + job["id"] + suffix, {}) if suffix else client.get("/api/jobs/" + job["id"])
        assert response.status_code == 404, response.text
    _register(client, "different@example.com")
    assert client.get(route).status_code == 404
    assert client.get("/api/jobs/" + job["id"]).status_code == 404


def test_new_explicit_request_replaces_pending_only_and_get_never_dispatches(signed):
    client, service, _ = signed
    service.model_client = model = ProposalModel()
    profile, _ = create(client)
    route, _, first = request(client, profile)
    _, _, next_request = request(client, profile, feedback="Different direction")
    assert next_request["id"] != first["id"]
    execute(service, first["id"])
    assert client.get(route).json()["request"]["id"] == next_request["id"] and model.inputs == []
    with service.db.session() as session:
        assert session.get(Job, first["id"]).state == "cancelled"
        background, _ = durable_jobs.enqueue(session, job_type="product_investigation", target_type="product_investigation",
            target_id=str(uuid4()), queue="ai_background", idempotency_key="background", priority=5)
        session.commit()
        offered = ai_dispatch.candidates(session, utcnow(), 10)
        assert offered[0].job_id == next_request["id"] and offered[0].job_id != background.id


def test_provider_failure_has_bounded_retry_and_draft_remains_manually_usable(signed):
    client, service, _ = signed
    profile, _ = create(client)
    class FailedModel:
        async def complete(self, *args, **kwargs):
            raise DomainError("hidden provider body", 502, "model_transport_error")
    service.model_client = FailedModel()
    route, _, job = request(client, profile)
    with service.db.session() as session:
        session.get(Job, job["id"]).max_attempts = 1
        session.commit()
    execute(service, job["id"])
    value = client.get(route).json()["request"]
    assert value["status"] == "failed" and value["result"] is None
    assert "hidden provider" not in str(value)
    assert client.get(f"{ROOT}/{profile['id']}").json()["revision"] == 1
    assert post(client, f"{ROOT}/{profile['id']}/activate", {"expected_revision": 1}).status_code == 200


@pytest.mark.parametrize("role", ["EDITOR", "VIEWER"])
def test_dossier_collaborator_preserves_current_setup_rights_and_actor_private_results(signed, role):
    client, service, identity = signed
    service.model_client = model = ProposalModel()
    user_id, cookies = colleague(client, service, identity)
    owner = dict(client.cookies)
    doc, root = managed(client)
    invitation = invite(client, root, user_id, role)
    switch(client, cookies)
    accept(client, invitation)
    profile = doc["profile"]
    route = f"{ROOT}/{profile['id']}/suggestions"
    assert client.get(route).json() == {"request": None}
    body = {"request_key": str(uuid4()), "expected_revision": profile["revision"]}
    response = post(client, route, body)
    assert response.status_code == (202 if role == "EDITOR" else 403), response.text
    if role == "VIEWER":
        assert model.inputs == []
        return
    identifier = response.json()["request"]["id"]
    execute(service, identifier)
    assert client.get(route).json()["request"]["status"] == "completed"
    assert client.get("/api/jobs/" + identifier).status_code == 404
    switch(client, owner)
    assert client.get(route).json() == {"request": None}
    assert client.get("/api/jobs/" + identifier).status_code == 404


@pytest.mark.parametrize("interruption", ["cancelled", "replaced", "reclaimed", "expired"])
def test_post_model_job_ownership_is_required_before_saving_cards(signed, interruption):
    client, service, _ = signed
    profile, _ = create(client)
    route, _, request_job = request(client, profile)
    class InterruptedModel(ProposalModel):
        async def complete(self, *args, **kwargs):
            result = await super().complete(*args, **kwargs)
            with service.db.session() as session:
                job = session.get(Job, request_job["id"])
                if interruption == "cancelled":
                    durable_jobs.cancel(session, job.id)
                elif interruption == "replaced":
                    job.lease_owner = "different-worker"
                elif interruption == "reclaimed":
                    job.attempts += 1  # A later claim can reuse the same worker name.
                    job.leased_at = utcnow()
                else:
                    job.heartbeat_at = utcnow() - timedelta(seconds=service.settings.job_lease_seconds + 1)
                session.commit()
            return result
    service.model_client = InterruptedModel()
    assert execute(service, request_job["id"])["state"] == "not_owned"
    with service.db.session() as session:
        assert session.get(Job, request_job["id"]).result_json is None
        row = session.get(LegalMonitoringProfile, profile["id"])
        assert row.revision == 1 and row.proposals_json == {}
    assert client.get(route).json()["request"]["result"] is None
