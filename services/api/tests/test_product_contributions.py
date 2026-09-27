"""Real native contribution save -> job -> evidence, original and privacy contracts."""
import hashlib
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from pdf_fixture import make_pdf
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from test_auth import _csrf, _register
from test_product_dossiers import ROOT, active, create, post
from test_product_dossiers import signed as signed
from test_product_investigations import complete, tick

from helvetic_lens import decision_search, decision_sources
from helvetic_lens.db import utcnow
from helvetic_lens.models import Job, OrganizationMembership
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch
from helvetic_lens.product_models import DossierEntry

TEXT = "Private Alpine memo: Helvetic Molecule AG supplied the fictional research report."


def submit(client, route, **values):
    body = {"request_key": str(uuid4()), "kind": "note", "body": TEXT, "analyse": True, **values}
    response = post(client, route + "/entries", body)
    assert response.status_code == 201, response.text
    return response.json(), body


def upload(client, route, body=TEXT.encode(), name="memo.txt", media="text/plain", key=None):
    return client.post(route + "/files", headers=_csrf(client),
        data={"request_key": key or str(uuid4()), "analyse": "true"}, files={"file": (name, body, media)})


def model_output(monkeypatch, model, *, invalid=False):
    calls = []

    async def extract(system, user, **kwargs):
        data = json.loads(user)
        calls.append(data)
        source = data["source"]
        part = source["excerpts"][0]
        quote = "Invented evidence never present in the document." if invalid else part["text"][:500]
        entity = [{"name": "Helvetic Molecule AG", "kind": "company", "quote": quote,
                   "locator": part["passage"], "investigate": True}] if "Helvetic Molecule AG" in quote else []
        return json.dumps({"claims": [{"statement": "The contribution describes a research report.",
            "quote": quote, "locator": part["passage"], "relation": "SUPPORTS"}], "entities": entity})

    monkeypatch.setattr(model, "complete", extract)
    return calls


def no_discovery(monkeypatch):
    calls = []

    async def forbidden(*args, **kwargs):
        calls.append(args)
        raise AssertionError("Private contribution reached public search")

    monkeypatch.setattr(decision_search, "execute", forbidden)
    return calls


def test_original_and_job_are_atomic_idempotent_private_and_attributable(signed, monkeypatch):
    client, service, identity, model = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    external = no_discovery(monkeypatch)
    model_output(monkeypatch, model)
    entry, body = submit(client, route)
    assert entry["body"] == TEXT and entry["author"] == "Ada Example"
    assert entry["sha256"] == hashlib.sha256(TEXT.encode()).hexdigest()
    assert entry["analysis"]["external_discovery"] is False
    assert entry["analysis"]["trigger_entry_id"] == entry["id"]
    assert post(client, route + "/entries", body).json()["analysis"]["id"] == entry["analysis"]["id"]
    assert post(client, route + "/entries", {**body, "analyse": False}).status_code == 409
    result = complete(client, service, route + "/investigations", entry["analysis"])
    assert result["status"] == "completed" and len(result["branches"]) == 1 and external == []
    assert result["original"]["body"] == TEXT and result["original"]["author"] == "Ada Example"
    assert result["sources"][0]["kind"] == "human_contribution"
    assert result["sources"][0]["original"] == result["original"]
    assert result["sources"][0]["snapshot"]["allow_discovery"] is False
    assert result["evidence"][0]["quote"] == TEXT
    assert result["created_by_user_id"] == identity["user"]["id"]
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Investigation)) == 1
        assert session.scalar(select(func.count()).select_from(DossierEntry)) == 1
    assert client.get(route + "/export").json()["investigations"][0]["original"]["body"] == TEXT
    assert client.get("/api/products/pharma/public-dossiers").json()["items"] == []


def test_url_reads_only_submitted_url_with_fixed_nonprivate_purpose(signed, monkeypatch):
    from helvetic_lens.product_contributions import PUBLIC_READ_PURPOSE

    client, service, _, model = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    model_output(monkeypatch, model)
    queries, external = [], no_discovery(monkeypatch)

    async def inspect(settings, query, item, mode):
        queries.append((query, item))
        return {"status": "complete", "url": item["url"], "sha256": "a" * 64,
            "excerpts": [{"passage": "p1", "text": TEXT}], "scope": "Fixture public document"}

    monkeypatch.setattr(decision_sources, "safe_inspect", inspect)
    entry, _ = submit(client, route, kind="reference", title="SECRET acquisition", url="https://example.org/report")
    result = complete(client, service, route + "/investigations", entry["analysis"])
    assert result["status"] == "completed" and len(result["branches"]) == 2
    assert queries == [(PUBLIC_READ_PURPOSE, {"url": "https://example.org/report", "title": "Submitted public document"})]
    assert external == [] and len(result["plans"]) == 1
    assert {source["kind"] for source in result["sources"]} == {"human_contribution", "contributed_url"}


@pytest.mark.parametrize("name,media,body,locator", [
    ("memo.txt", "text/plain", TEXT.encode(), "text-block-1-char-1"),
    ("memo.pdf", "application/pdf", make_pdf(["", TEXT]), "page-2-block-1-char-1"),
    ("memo.html", "text/html", f"<main><p>{TEXT}</p></main>".encode(), "p00001-block-1-char-1"),
])
def test_original_file_download_and_real_bounded_parser(signed, monkeypatch, name, media, body, locator):
    client, service, _, model = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    model_output(monkeypatch, model)
    external = no_discovery(monkeypatch)
    key = str(uuid4())
    first = upload(client, route, body, name, media, key)
    assert first.status_code == 201, first.text
    entry = first.json()
    again = upload(client, route, body, name, media, key)
    assert again.json()["id"] == entry["id"] and again.json()["analysis"]["id"] == entry["analysis"]["id"]
    assert upload(client, route, body + b"different", name, media, key).status_code == 409
    result = complete(client, service, route + "/investigations", entry["analysis"])
    assert result["status"] == "completed", result
    assert result["sources"][0]["snapshot"]["excerpts"][0]["passage"] == locator
    assert result["sources"][0]["sha256"] == hashlib.sha256(body).hexdigest()
    assert client.get(route + "/files/" + entry["id"]).content == body and external == []


@pytest.mark.parametrize("name,media,body,reason", [
    ("scan.pdf", "application/pdf", make_pdf([""]), "OCR"),
    ("binary.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"not-docx", "supports"),
    ("spoof.txt", "image/png", TEXT.encode(), "content types"),
    ("large.txt", "text/plain", b"a" * (2 * 1024 * 1024 + 1), "2 MB"),
    ("broken.pdf", "application/pdf", b"not pdf", "PDF"),
])
def test_unavailable_extraction_preserves_original(signed, monkeypatch, name, media, body, reason):
    client, service, _, model = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    calls = model_output(monkeypatch, model)
    entry = upload(client, route, body, name, media).json()
    result = complete(client, service, route + "/investigations", entry["analysis"])
    assert result["status"] == "failed" and not result["claims"] and calls == []
    assert reason in result["branches"][0]["error"], result
    assert client.get(route + "/files/" + entry["id"]).content == body


def test_model_retry_keeps_capture_and_original_and_does_not_repeat_completed_steps(signed, monkeypatch):
    client, service, _, model = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    model_output(monkeypatch, model, invalid=True)
    entry = upload(client, route).json()
    root = route + "/investigations"
    failed = complete(client, service, root, entry["analysis"])
    assert failed["status"] == "failed" and not failed["claims"] and len(failed["sources"]) == 1
    source = failed["sources"][0]
    calls = model_output(monkeypatch, model)
    retried = post(client, root + "/" + failed["id"] + "/control", {"action": "retry", "expected_revision": failed["revision"]})
    assert retried.status_code == 200, retried.text
    result = complete(client, service, root, retried.json())
    assert result["status"] == "completed" and len(calls) == 1
    assert result["sources"] == [source] and result["original"] == failed["original"]
    assert [step["phase"] for step in result["branches"][0]["steps"]] == ["read", "extract", "extract"]
    assert post(client, root + "/" + result["id"] + "/control", {"action": "retry", "expected_revision": result["revision"]}).status_code == 409


def test_queued_contributions_serialize_without_losing_original_or_consuming_attempts(signed, monkeypatch):
    client, service, _, model = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    calls = model_output(monkeypatch, model)
    first, _ = submit(client, route)
    second, _ = submit(client, route, body=TEXT + " Later contribution.")
    assert tick(service, second["analysis"]["id"])["state"] == "queued" and calls == []
    with service.db.session() as session:
        run = session.get(Investigation, second["analysis"]["id"])
        job = session.get(Job, run.job_id)
        assert job.attempts == 0 and job.available_at.replace(tzinfo=utcnow().tzinfo) > utcnow()
    complete(client, service, route + "/investigations", first["analysis"])
    with service.db.session() as session:
        job = session.get(Job, session.get(Investigation, second["analysis"]["id"]).job_id)
        job.available_at = utcnow() - timedelta(seconds=1)
        session.commit()
    assert complete(client, service, route + "/investigations", second["analysis"])["status"] == "completed"
    assert len(calls) == 2


def test_revoke_during_file_read_discards_capture_but_retains_original(signed, monkeypatch):
    from helvetic_lens import product_contributions

    client, service, identity, _ = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    entry = upload(client, route).json()

    async def read(*args):
        with service.db.session() as session:
            member = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"]))
            member.role = "viewer"
            session.commit()
        return {"status": "complete", "sha256": entry["sha256"], "excerpts": [{"text": TEXT, "passage": "p1"}]}

    monkeypatch.setattr(product_contributions, "read_file", read)
    result = complete(client, service, route + "/investigations", entry["analysis"])
    assert result["status"] == "paused" and not result["sources"]
    assert client.get(route + "/files/" + entry["id"]).content == TEXT.encode()
    assert upload(client, route).status_code == 403


def test_contribution_author_key_tenant_product_csrf_and_schema_boundaries(signed):
    client, service, identity, _ = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    entry, body = submit(client, route)
    assert client.post(route + "/entries", json={**body, "request_key": str(uuid4())}).status_code == 403
    assert post(client, route.replace("pharma", "loyer") + "/entries", body).status_code == 404
    other, _ = create(client)
    with pytest.raises(IntegrityError), service.db.session() as session:
        run = session.get(Investigation, entry["analysis"]["id"])
        run.trigger_entry_id = None
        session.flush()
        session.add(Investigation(dossier_id=other["id"], organization_id=identity["organization"]["id"],
            request_key=str(uuid4()), trigger_entry_id=entry["id"], question="Wrong scope"))
        session.flush()
    active(client, doc)
    second = _register(client, "contributor-other@example.ch").json()
    assert client.get(route + "/investigations/" + entry["analysis"]["id"]).status_code == 404
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=second["user"]["id"], organization_id=identity["organization"]["id"], role="organization_admin"))
        session.commit()
    assert post(client, "/api/auth/session/organization", {"organization_id": identity["organization"]["id"]}).status_code == 200
    assert post(client, route + "/entries", body).status_code == 409


def test_interrupted_extraction_requires_explicit_retry_without_duplicate_paid_call(signed, monkeypatch):
    client, service, _, model = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    entry, _ = submit(client, route)
    calls = model_output(monkeypatch, model)
    tick(service, entry["analysis"]["id"])
    with service.db.session() as session:
        branch = session.scalar(select(InvestigationBranch).where(InvestigationBranch.investigation_id == entry["analysis"]["id"]))
        branch.checkpoint = {**branch.checkpoint, "inflight": "lost-worker", "steps": [{"phase": "extract", "status": "running"}]}
        session.commit()
    result = complete(client, service, route + "/investigations", entry["analysis"])
    assert result["status"] == "failed" and calls == []
    assert result["branches"][0]["steps"][0]["status"] == "interrupted"


def test_partial_context_retry_analyses_only_failed_source(signed, monkeypatch):
    client, service, _, model = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    for body in [TEXT + " First saved source.", TEXT + " Second saved source."]:
        assert post(client, route + "/entries", {"request_key": str(uuid4()), "kind": "note", "body": body}).status_code == 201
    calls, failed_source, fail_once = [], [], [True]

    async def extract(system, user, **kwargs):
        data = json.loads(user)
        source = data["source"]
        calls.append(source["id"])
        if source["kind"] == "team_contribution" and fail_once[0]:
            fail_once[0] = False
            failed_source.append(source["id"])
            raise RuntimeError("fixture unavailability")
        return json.dumps({"claims": [], "entities": [], "relationships": []})

    monkeypatch.setattr(model, "complete", extract)
    entry, _ = submit(client, route, kind="research_request", body="Check the Private Alpine research report in the saved evidence.")
    root = route + "/investigations"
    result = complete(client, service, root, entry["analysis"])
    assert result["status"] == "completed" and len(calls) == 3 and len(failed_source) == 1
    retried = post(client, root + "/" + result["id"] + "/control", {"action": "retry", "expected_revision": result["revision"]})
    assert retried.status_code == 200, retried.text
    result = complete(client, service, root, retried.json())
    assert calls[-1:] == failed_source and len(calls) == 4
    assert all(branch["status"] == "completed" for branch in result["branches"])


def test_migration_retains_existing_originals_and_completed_evidence(signed, monkeypatch):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from test_account_deletion_migration import config
    from test_product_investigations import pipeline, start

    from alembic import command
    from helvetic_lens.db import Base

    client, service, _, model = signed
    pipeline(monkeypatch, service, model)
    root, run, _ = start(client)
    value = complete(client, service, root, run)
    route = root.removesuffix("/investigations")
    # A legacy save-only upload survives both SQLite batch replacements.
    saved = client.post(route + "/files", headers=_csrf(client), files={"file": ("memo.txt", TEXT.encode(), "text/plain")}).json()
    tables = {"product_investigations", "product_dossier_entries"}
    with service.db.engine.connect() as connection:
        command.downgrade(config(connection), "fac495bef124")
        command.upgrade(config(connection), "head")
        context = MigrationContext.configure(connection, opts={"include_object":
            lambda obj, name, kind, reflected, other: kind != "table" or name in tables})
        assert compare_metadata(context, Base.metadata) == []
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    current = client.get(root + "/" + run["id"]).json()
    assert current["claims"] == value["claims"] and current["sources"] == value["sources"]
    assert current["external_discovery"] is True and current["original"] is None
    assert client.get(route + "/files/" + saved["id"]).content == TEXT.encode()


def test_file_cancel_during_read_never_commits_late_evidence(signed, monkeypatch):
    from helvetic_lens import product_contributions

    client, service, _, _ = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    entry = upload(client, route).json()
    root = route + "/investigations/" + entry["analysis"]["id"]

    async def read(*args):
        value = client.get(root).json()
        assert post(client, root + "/control", {"action": "cancel", "expected_revision": value["revision"]}).status_code == 200
        return {"status": "complete", "sha256": entry["sha256"], "excerpts": [{"text": TEXT, "passage": "p1"}]}

    monkeypatch.setattr(product_contributions, "read_file", read)
    tick(service, entry["analysis"]["id"])
    assert tick(service, entry["analysis"]["id"])["state"] == "stale_result_discarded"
    value = client.get(root).json()
    assert value["status"] == "cancelled" and value["sources"] == []
    assert client.get(route + "/files/" + entry["id"]).content == TEXT.encode()


@pytest.mark.parametrize("during_read", [False, True])
def test_excluded_source_blocks_attached_text_and_late_url_capture(signed, monkeypatch, during_read):
    from test_product_source_reviews import request

    client, service, _, model = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    entry, _ = submit(client, route, kind="reference", url="https://example.org/excluded")
    review_route = route + "/sources/" + entry["id"] + "/reviews"
    calls, reads = model_output(monkeypatch, model), []

    async def inspect(settings, query, item, mode):
        reads.append(item["url"])
        assert post(client, review_route, request()).status_code == 201
        return {"status": "complete", "url": item["url"], "sha256": "b" * 64,
                "excerpts": [{"passage": "p1", "text": TEXT}], "scope": "Fixture"}

    monkeypatch.setattr(decision_sources, "safe_inspect", inspect)
    if not during_read:
        assert post(client, review_route, request()).status_code == 201
    result = complete(client, service, route + "/investigations", entry["analysis"])
    assert all(source["kind"] != "contributed_url" for source in result["sources"])
    if during_read:
        assert reads == [entry["url"]] and len(calls) == 1
    else:
        assert not reads and not calls and result["claims"] == []
    assert result["original"]["body"] == TEXT
