"""Native durable investigation, replanning, privacy and interruption contracts."""
import asyncio
import hashlib
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from test_auth import _register
from test_product_dossiers import ROOT, create, post
from test_product_dossiers import signed as signed

from helvetic_lens import decision_search, decision_sources, jobs
from helvetic_lens.db import utcnow
from helvetic_lens.models import Job, OrganizationMembership
from helvetic_lens.product_investigation_models import ClaimEvidence, Investigation, InvestigationBranch
from helvetic_lens.product_models import DecisionSearchBudget

QUOTE = "Alpine Therapeutics owns Helvetic Molecule AG. The registry describes a clinical research company."
OTHER = "The updated registry states that Alpine Therapeutics no longer owns Helvetic Molecule AG."


def start(client, question="Research Alpine Therapeutics ownership"):
    doc, _ = create(client)
    root = f"{ROOT}/{doc['id']}/investigations"
    body = {"request_key": str(uuid4()), "question": question, "public_query_confirmed": True}
    response = post(client, root, body)
    assert response.status_code == 202, response.text
    return root, response.json(), body


def tick(service, identifier):
    with service.db.session() as session:
        job_id = session.get(Investigation, identifier).job_id
    return asyncio.run(service.execute_job(job_id, "test-worker"))


def complete(client, service, root, run):
    for _ in range(40):
        value = client.get(root + "/" + run["id"]).json()
        if value["status"] not in {"queued", "running"}:
            return value
        tick(service, run["id"])
    raise AssertionError("The bounded investigation did not terminate: " + json.dumps(value))


def pipeline(monkeypatch, service, model, *, invalid=False, fail_search=False):
    service.settings.search1api_api_key = SecretStr("fixture")
    queries = []

    async def search(settings, query, mode, depth, product):
        queries.append(query)
        if fail_search:
            raise RuntimeError("private-provider-body")
        url = "https://example.org/registry" if len(queries) == 1 else "https://example.org/update"
        return {"items": [{"id": "a" * 32, "title": "Registry record", "url": url,
                           "retrieval_queries": [query]}], "selected_engine": "jev"}

    async def inspect(settings, query, item, mode, **kwargs):
        text = QUOTE if item["url"].endswith("registry") else OTHER
        return {"status": "complete", "url": item["url"], "sha256": hashlib.sha256(text.encode()).hexdigest(),
                "excerpts": [{"text": text, "passage": "p1"}], "scope": "Fixture public source"}

    async def extract(system, user, **kwargs):
        data = json.loads(user)
        model.calls.append((system, user))
        source = data["source"]
        if source["kind"] != "public_source":
            return json.dumps({"claims": [], "entities": [], "relationships": []})
        first = source["excerpts"][0]["text"] == QUOTE
        claims = data["existing_claims"]
        quote = "This citation was invented entirely." if invalid else QUOTE if first else OTHER
        return json.dumps({"claims": [{"statement": "Alpine Therapeutics owns Helvetic Molecule AG.",
            "existing_claim_id": None if first else claims[0]["id"], "relation": "SUPPORTS" if first else "CONTRADICTS",
            "quote": quote, "locator": "p1"}], "entities": [
                {"name": name, "kind": "company", "quote": quote, "locator": "p1",
                 "investigate": name == "Helvetic Molecule AG"} for name in
                (["Alpine Therapeutics", "Helvetic Molecule AG"] if first else [])],
            "relationships": [{"subject": "Alpine Therapeutics", "object": "Helvetic Molecule AG",
                "predicate": "owns", "quote": quote, "locator": "p1"}] if first else []})

    monkeypatch.setattr(decision_search, "execute", search)
    monkeypatch.setattr(decision_sources, "safe_inspect", inspect)
    monkeypatch.setattr(model, "complete", extract)
    return queries


def test_evidence_discovers_entity_changes_plan_and_preserves_contradiction(signed, monkeypatch):
    client, service, _, model = signed
    queries = pipeline(monkeypatch, service, model)
    root, run, body = start(client)
    assert run["status"] == "queued" and not run["plans"] and run["created_by_user_id"]
    assert post(client, root, body).json()["id"] == run["id"]
    assert post(client, root, {**body, "question": "Different request"}).status_code == 409
    tick(service, run["id"])
    planned = client.get(root + "/" + run["id"]).json()
    assert planned["plans"][0]["version"] == 1 and queries == []
    result = complete(client, service, root, run)
    assert result["status"] == "completed"
    assert len(result["plans"]) == 2 and len(result["branches"]) == 2
    trigger = result["plans"][1]["document"]["trigger"]
    assert trigger["quote"] == QUOTE and trigger["source_id"] == result["sources"][0]["id"]
    assert queries == [body["question"], body["question"] + " Helvetic Molecule AG"]
    claim = result["claims"][0]
    assert claim["status"] == "CONTESTED" and claim["revision"] == 2
    assert [v["to"] for v in claim["history"]] == ["SUPPORTED", "CONTESTED"]
    assert {e["relation"] for e in result["evidence"]} == {"SUPPORTS", "CONTRADICTS"}
    assert len(result["entities"]) == 2 and len(result["relationships"]) == 1
    assert all(e["evidence"]["identity"] == "unresolved_source_mention" for e in result["entities"])
    assert all(step["status"] == "completed" for branch in result["branches"] for step in branch["steps"])
    with service.db.session() as session:
        assert session.get(DecisionSearchBudget, utcnow().date()).used == 4
        job_id = session.get(Investigation, run["id"]).job_id
    assert client.get("/api/jobs/" + job_id).status_code == 404
    assert job_id not in client.get("/api/jobs").text
    exported = client.get(root.removesuffix("/investigations") + "/export").json()
    assert exported["investigations"][0]["claims"] == result["claims"]
    events = client.get(root + f"/{run['id']}/events?after=2&wait=0", headers={"Last-Event-ID": "4"})
    assert events.status_code == 200 and "text/event-stream" in events.headers["content-type"]
    assert "id: 4\n" not in events.text and "plan_updated" in events.text
    assert "no-store" in events.headers["cache-control"]


def test_invalid_quotes_cannot_create_claims_or_replans(signed, monkeypatch):
    client, service, _, model = signed
    queries = pipeline(monkeypatch, service, model, invalid=True)
    root, run, _ = start(client)
    result = complete(client, service, root, run)
    assert result["status"] == "failed" and len(queries) == 1
    assert not result["claims"] and not result["entities"] and len(result["plans"]) == 1
    assert result["sources"][0]["snapshot"]["excerpts"][0]["text"] == QUOTE
    assert result["branches"][0]["steps"][-1]["status"] == "unavailable"


def test_private_context_never_enters_external_queries(signed, monkeypatch):
    client, service, _, model = signed
    queries = pipeline(monkeypatch, service, model)
    root, run, _ = start(client)
    private = "PRIVATE MERGER CODE CERULEAN-842 confidential acquisition"
    note = post(client, root.removesuffix("/investigations") + "/entries",
        {"request_key": str(uuid4()), "kind": "note", "body": private})
    assert note.status_code == 201
    result = complete(client, service, root, run)
    assert result["status"] == "completed" and all("CERULEAN" not in q for q in queries)
    assert any(private in user for _, user in model.calls)
    assert any(s["kind"] == "team_contribution" for s in result["sources"])


def test_pause_resume_uses_new_job_generation_and_cancel_is_terminal(signed, monkeypatch):
    client, service, _, model = signed
    pipeline(monkeypatch, service, model)
    root, run, _ = start(client)
    detail = root + "/" + run["id"]
    tick(service, run["id"])
    run = client.get(detail).json()
    paused = post(client, detail + "/control", {"expected_revision": run["revision"], "action": "pause"})
    assert paused.json()["status"] == "paused"
    stale = post(client, detail + "/control", {"expected_revision": run["revision"], "action": "resume"})
    assert stale.status_code == 409
    with service.db.session() as session:
        old = session.get(Investigation, run["id"]).job_id
    resumed = post(client, detail + "/control", {"expected_revision": paused.json()["revision"], "action": "resume"}).json()
    assert resumed["status"] == "queued"
    with service.db.session() as session:
        assert session.get(Investigation, run["id"]).job_id != old
        assert session.get(Job, old).state == "cancelled"
    cancelled = post(client, detail + "/control", {"expected_revision": resumed["revision"], "action": "cancel"}).json()
    assert cancelled["status"] == "cancelled"
    tick(service, run["id"])
    assert client.get(detail).json()["status"] == "cancelled"
    assert post(client, detail + "/control", {"expected_revision": cancelled["revision"], "action": "resume"}).status_code == 409


def test_recovery_never_repeats_inflight_paid_search(signed, monkeypatch):
    client, service, _, model = signed
    queries = pipeline(monkeypatch, service, model)
    root, run, _ = start(client)
    tick(service, run["id"])
    with service.db.session() as session:
        record = session.get(Investigation, run["id"])
        job = jobs.claim(session, record.job_id, "crashed-worker")
        job.heartbeat_at = utcnow() - timedelta(hours=1)
        branch = session.scalar(select(InvestigationBranch).where(InvestigationBranch.investigation_id == run["id"]))
        branch.checkpoint = {"inflight": "committed-before-network", "steps": [{"phase": "search", "status": "running"}]}
        session.commit()
    with service.db.session() as session:
        jobs.reconcile(session, 30)
        session.commit()
    result = complete(client, service, root, run)
    assert queries == [] and result["status"] == "failed"
    assert result["branches"][0]["steps"][0]["status"] == "interrupted"


def test_revocation_during_search_discards_output_and_pauses(signed, monkeypatch):
    client, service, identity, model = signed
    pipeline(monkeypatch, service, model)
    async def revoke(*args):
        with service.db.session() as session:
            member = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"]))
            member.role = "viewer"
            session.commit()
        return {"items": [{"id": "a" * 32, "title": "MUST NOT SAVE", "url": "https://example.org/private"}]}
    monkeypatch.setattr(decision_search, "execute", revoke)
    root, run, _ = start(client)
    tick(service, run["id"])
    tick(service, run["id"])
    read = client.get(root + "/" + run["id"])
    assert read.json()["status"] == "paused" and "MUST NOT SAVE" not in read.text
    assert post(client, root + f"/{run['id']}/control", {"expected_revision": read.json()["revision"], "action": "resume"}).status_code == 403


def test_paid_allowance_omits_only_paid_channel_and_is_shared_with_search(signed, monkeypatch):
    client, service, _, model = signed
    queries = pipeline(monkeypatch, service, model)
    service.settings.decision_search_daily_limit = 2
    root, run, _ = start(client)
    result = complete(client, service, root, run)
    assert result["status"] == "completed" and len(queries) == 2
    assert len(result["claims"]) == 1
    with service.db.session() as session:
        assert session.get(DecisionSearchBudget, utcnow().date()).used == 2
    assert any(b.get("coverage", {}).get("retrieval", {}).get("skipped_channels") for b in result["branches"])


def test_partial_search_failure_is_sanitized_and_saved_evidence_completes(signed, monkeypatch):
    client, service, _, model = signed
    pipeline(monkeypatch, service, model, fail_search=True)
    root, run, _ = start(client)
    post(client, root.removesuffix("/investigations") + "/entries", {"request_key": str(uuid4()), "kind": "note", "body": "Saved evidence remains available."})
    result = complete(client, service, root, run)
    assert result["status"] == "completed"
    assert {b["status"] for b in result["branches"]} == {"completed", "failed"}
    assert "private-provider-body" not in json.dumps(result)


def test_tenant_product_and_dossier_boundaries(signed):
    client, _, _, _ = signed
    root, run, body = start(client)
    detail = root + "/" + run["id"]
    assert client.post(root, json=body).status_code == 403
    assert client.get(detail.replace("pharma", "loyer")).status_code == 404
    other, _ = create(client)
    assert client.get(f"{ROOT}/{other['id']}/investigations/{run['id']}").status_code == 404
    assert _register(client, "other@example.ch", "Other workspace").status_code == 201
    assert client.get(root).status_code == 404
    assert client.get(detail).status_code == 404
    assert client.get(detail + "/events?wait=0").status_code == 404


def test_foreign_keys_reject_cross_dossier_evidence(signed, monkeypatch):
    client, service, _, model = signed
    pipeline(monkeypatch, service, model)
    root, run, _ = start(client)
    result = complete(client, service, root, run)
    other, _ = create(client)
    with service.db.session() as session:
        session.add(ClaimEvidence(investigation_id=run["id"], dossier_id=other["id"],
            claim_id=result["claims"][0]["id"], source_id=result["sources"][0]["id"],
            relation="SUPPORTS", quote=QUOTE, locator="p1"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_stream_rechecks_access_after_initial_authorized_batch(signed, monkeypatch):
    from sqlalchemy import delete

    from helvetic_lens import product_investigation_api

    client, service, identity, _ = signed
    root, run, _ = start(client)
    original = product_investigation_api.record
    checks = []

    def checked(session, *args, **kwargs):
        value = original(session, *args, **kwargs)
        checks.append(True)
        if len(checks) == 2:
            session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == identity['user']['id']))
            session.commit()
        return value

    monkeypatch.setattr(product_investigation_api, 'record', checked)
    result = client.get(root + f"/{run['id']}/events?wait=3")
    assert result.status_code == 200
    assert 'investigation_queued' in result.text and 'event: access_changed' in result.text
    assert len(checks) == 2


def test_exhausted_native_worker_pauses_instead_of_staying_running(signed, monkeypatch):
    client, service, _, model = signed
    pipeline(monkeypatch, service, model)
    root, run, _ = start(client)
    tick(service, run['id'])
    with service.db.session() as session:
        record = session.get(Investigation, run['id'])
        job = jobs.claim(session, record.job_id, 'crashed-worker')
        job.attempts = job.max_attempts
        job.heartbeat_at = utcnow() - timedelta(hours=1)
        session.commit()
    with service.db.session(include_all_organizations=True) as session:
        jobs.reconcile(session, 30)
        session.commit()
    value = client.get(root + '/' + run['id']).json()
    assert value['status'] == 'paused' and 'recovery limit' in value['stop_reason']
    assert post(client, root + f"/{run['id']}/control", {'expected_revision': value['revision'], 'action': 'resume'}).status_code == 200


def test_cancellation_during_network_discards_late_result(signed, monkeypatch):
    client, service, _, model = signed
    pipeline(monkeypatch, service, model)
    root, run, _ = start(client)
    detail = root + '/' + run['id']
    tick(service, run['id'])
    async def cancel(*args):
        with service.db.session() as session:
            row = session.get(Investigation, run['id'])
            jobs.cancel(session, row.job_id)
            row.status = 'cancelled'
            session.commit()
        return {'items': [{'id': 'b' * 32, 'title': 'LATE NETWORK RESULT', 'url': 'https://example.org/late'}]}
    monkeypatch.setattr(decision_search, 'execute', cancel)
    tick(service, run['id'])
    result = client.get(detail)
    assert result.json()['status'] == 'cancelled' and 'LATE NETWORK RESULT' not in result.text
    assert not result.json()['sources']


def test_migration_roundtrip_matches_models_and_preserves_native_dossier(signed):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from test_account_deletion_migration import config

    from alembic import command
    from helvetic_lens.db import Base
    from helvetic_lens.product_investigation_models import SCOPED

    client, service, _, _ = signed
    doc, _ = create(client)
    tables = {model.__tablename__ for model in SCOPED}
    with service.db.engine.connect() as connection:
        command.downgrade(config(connection), 'f9c495bef124')
        command.upgrade(config(connection), 'head')
        context = MigrationContext.configure(connection, opts={'include_object':
            lambda obj, name, kind, reflected, other: kind != 'table' or name in tables})
        assert compare_metadata(context, Base.metadata) == []
        assert connection.exec_driver_sql('PRAGMA foreign_key_check').all() == []
    assert client.get(ROOT + '/' + doc['id']).json()['id'] == doc['id']


def test_resumption_does_not_reassign_original_question_authorship(signed, monkeypatch):
    from test_auth import _register
    from test_product_dossiers import active
    client, service, identity, model = signed
    pipeline(monkeypatch, service, model)
    root, run, _ = start(client)
    dossier_route = root.removesuffix('/investigations')
    active(client, client.get(dossier_route).json())
    value = post(client, root + f"/{run['id']}/control", {'expected_revision': run['revision'], 'action': 'pause'}).json()
    second = _register(client, 'second-editor@example.ch', 'Second editor').json()
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=second['user']['id'], organization_id=identity['organization']['id'], role='organization_admin'))
        session.commit()
    assert post(client, '/api/auth/session/organization', {'organization_id': identity['organization']['id']}).status_code == 200
    resumed = post(client, root + f"/{run['id']}/control", {'expected_revision': value['revision'], 'action': 'resume'})
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()['created_by_user_id'] == identity['user']['id']
    with service.db.session() as session:
        row = session.get(Investigation, run['id'])
        assert row.actor_user_id == second['user']['id']
        assert row.created_by_user_id == identity['user']['id']
