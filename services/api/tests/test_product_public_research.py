"""Public consent, actual shared-worker execution and revocation boundaries."""
import json
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_auth import _csrf
from test_product_community import action, command
from test_product_dossiers import ROOT, create, post
from test_product_dossiers import signed as signed
from test_product_guests import guest
from test_product_investigations import complete, pipeline, tick
from test_product_publications import PUBLIC, draft, preview_and_publish
from test_product_teams import switch

from helvetic_lens.db import utcnow
from helvetic_lens.models import Job, OrganizationMembership, OutboxMessage, User, UserSession
from helvetic_lens.product_investigation_models import Investigation
from helvetic_lens.product_models import DossierEntry, PublicContribution


def setup(client, service, identity, *, product="pharma"):
    with service.db.session(include_all_organizations=True) as session:
        session.get(User, identity["user"]["id"]).email_verified_at = utcnow()
        session.commit()
    doc, _ = create(client)
    if product != "pharma":
        from helvetic_lens.product_models import ProductDossier

        with service.db.session() as session:
            session.get(ProductDossier, doc["id"]).product = product
            session.commit()
    data = {**draft(), "living_research": True}
    path = ROOT.replace("pharma", product) + "/" + doc["id"] + "/publication"
    preview = post(client, path + "/preview", data)
    assert preview.status_code == 200, preview.text
    value = post(client, path, {**preview.json(), "confirm_public": True, "request_key": str(uuid4())})
    assert value.status_code == 200, value.text
    publication = value.json()["publication"]
    return doc, publication, PUBLIC.replace("pharma", product) + "/" + publication["id"]


def submit(client, root, *, kind="research_request", **changes):
    data = command(kind=kind, analyse_publicly=True, public_query_confirmed=kind == "research_request", **changes)
    data["content"].update(body="Research Alpine Therapeutics ownership", sources=[])
    response = post(client, root + "/discussion", data)
    assert response.status_code == 201, response.text
    return response.json()["contribution"], data


@pytest.mark.parametrize("product", ["pharma", "loyer"])
def test_public_living_journey_uses_same_engine_and_never_private_evidence(signed, monkeypatch, product):
    client, service, identity, model = signed
    doc, publication, root = setup(client, service, identity, product=product)
    with service.db.session() as session:
        session.add(DossierEntry(dossier_id=doc["id"], kind="note", body="HIDDEN-PRIVATE-CONTEXT", request_key=str(uuid4())))
        session.commit()
    account, cookies = guest(client, service)
    switch(client, cookies)
    before = client.get("/api/auth/session").json()["organization"]["id"]
    queries = pipeline(monkeypatch, service, model)
    item, data = submit(client, root)
    run = item["research"]
    assert run and post(client, root + "/discussion", data).json()["contribution"]["research"]["id"] == run["id"]
    with service.db.session(include_all_organizations=True) as session:
        value = session.get(Investigation, run["id"])
        job = session.get(Job, value.job_id)
        assert job.organization_id == identity["organization"]["id"]
        assert session.scalar(select(OutboxMessage).where(OutboxMessage.job_id == job.id)).organization_id == job.organization_id
        assert session.scalar(select(func.count()).select_from(OrganizationMembership).where(
            OrganizationMembership.user_id == account["user"]["id"])) == 1
    result = complete(client, service, root + "/research", run)
    assert result["status"] == "completed", result
    assert result["claims"][0]["status"] == "CONTESTED"
    assert len(result["plans"]) >= 2 and len(queries) >= 2
    assert "HIDDEN-PRIVATE-CONTEXT" not in json.dumps(model.calls)
    assert client.get("/api/auth/session").json()["organization"]["id"] == before
    assert client.get(ROOT.replace("pharma", product) + "/" + doc["id"]).status_code == 404
    client.cookies.clear()
    response = client.get(root + "/research/" + run["id"])
    for private in (doc["id"], identity["organization"]["id"], account["user"]["id"], "HIDDEN-PRIVATE-CONTEXT", "artifact_key"):
        assert private not in response.text
    assert client.get(PUBLIC.replace("pharma", product) + "/" + publication["slug"]).json()["id"] == publication["id"]
    assert client.get(root + "/research/" + run["id"] + "/events?wait=0").status_code == 200
    search = client.get(f"/api/products/{product}/public-knowledge?q=Therapeutics").json()
    assert {item["kind"] for item in search["items"]} >= {"claim", "entity", "investigation"}
    assert "#claim-" in json.dumps(search)
    assert client.get(f"/api/products/{product}/public-knowledge?q=HIDDEN-PRIVATE-CONTEXT").json()["total"] == 0
    assert client.get(root + "/research/" + run["id"] + "/workspace").status_code == 401
    assert client.get(root.replace(product, "loyer" if product == "pharma" else "pharma") + "/research").status_code == 404


def test_signed_publication_opt_in_and_contribution_consent(signed):
    client, service, identity, _ = signed
    doc, _ = create(client)
    snapshot, _ = preview_and_publish(client, doc["id"])
    assert snapshot["living_research"] is False
    item = post(client, PUBLIC + "/" + snapshot["id"] + "/discussion", command()).json()["contribution"]
    assert item["research"] is None
    data = post(client, ROOT + "/" + doc["id"] + "/publication/preview", draft(1)).json()
    assert post(client, ROOT + "/" + doc["id"] + "/publication",
        {**data, "living_research": True, "request_key": str(uuid4()), "confirm_public": True}).status_code == 409
    _, _, root = setup(client, service, identity)
    assert post(client, root + "/discussion", command()).status_code == 409
    assert post(client, root + "/discussion", command(kind="research_request", analyse_publicly=True)).status_code == 422
    _, cookies = guest(client, service, verified=False)
    switch(client, cookies)
    assert post(client, root + "/discussion", command(analyse_publicly=True)).status_code == 403
    assert client.get(root + "/discussion").json()["total"] == 0


@pytest.mark.parametrize("change", ["hide", "remove", "edit", "withdraw", "republish", "source", "erase"])
def test_anonymous_read_search_stream_and_counts_follow_current_visibility(signed, monkeypatch, change):
    client, service, identity, model = signed
    doc, publication, root = setup(client, service, identity)
    pipeline(monkeypatch, service, model)
    item, data = submit(client, root)
    run = item["research"]
    result = complete(client, service, root + "/research", run)
    assert result["claims"]
    if change in {"hide", "remove"}:
        assert action(client, root + "/discussion", item, change).status_code == 200
    elif change == "edit":
        data.update(request_key=str(uuid4()), expected_revision=1)
        data["content"]["body"] = "A changed public contribution with a new meaning."
        assert post(client, root + "/discussion/" + item["id"], data).status_code == 200
    elif change in {"withdraw", "republish"}:
        path = ROOT + "/" + doc["id"] + "/publication"
        if change == "withdraw":
            assert post(client, path + "/withdraw", {"expected_revision": 1, "request_key": str(uuid4())}).status_code == 200
        else:
            current, _ = preview_and_publish(client, doc["id"], {**draft(1), "living_research": True})
            assert current["slug"] == publication["slug"]
    elif change == "source":
        with service.db.session() as session:
            session.add(DossierEntry(dossier_id=doc["id"], kind="source_review", url="https://example.org/registry",
                request_key=str(uuid4()), body="PRIVATE exclusion reason", data_json={"decision": "exclude", "revision": 1}))
            session.commit()
    else:
        with service.db.session() as session:
            session.delete(session.get(PublicContribution, item["id"]))
            session.commit()
    client.cookies.clear()
    for suffix in ("", "/events?wait=0"):
        assert client.get(root + "/research/" + run["id"] + suffix).status_code == 404
    search = client.get("/api/products/pharma/public-knowledge?q=Therapeutics").json()
    assert all(i["investigation_id"] != run["id"] for i in search["items"])
    page = client.get(root + "/research")
    assert page.status_code == 404 if change == "withdraw" else all(r["id"] != run["id"] for r in page.json()["items"])


def test_inflight_withdrawal_and_session_revocation_discard_late_findings(signed, monkeypatch):
    client, service, identity, model = signed
    doc, _, root = setup(client, service, identity)
    pipeline(monkeypatch, service, model)
    item, _ = submit(client, root, kind="comment")
    run = item["research"]
    tick(service, run["id"])
    async def revoke(*args, **kwargs):
        with service.db.session() as session:
            row = session.get(Investigation, run["id"])
            session.get(UserSession, row.session_id).revoked_at = utcnow()
            session.commit()
        return json.dumps({"claims": [], "entities": [], "relationships": []})
    monkeypatch.setattr(model, "complete", revoke)
    tick(service, run["id"])
    result = client.get(root + "/research/" + run["id"]).json()
    assert result["status"] == "paused" and not result["claims"]


def test_public_original_upload_integrity_idempotency_and_moderation(signed, monkeypatch):
    client, service, identity, model = signed
    _, _, root = setup(client, service, identity)
    pipeline(monkeypatch, service, model)
    data = command(kind="file", analyse_publicly=True)
    data["content"]["sources"] = []
    def upload(body=b"This original public report describes an Alpine research programme.", name="report.txt", media="text/plain"):
        return client.post(root + "/files", headers=_csrf(client), data={"metadata": json.dumps(data)},
            files={"file": (name, body, media)})
    response = upload()
    assert response.status_code == 201, response.text
    item = response.json()["contribution"]
    assert upload().json()["contribution"]["id"] == item["id"]
    assert upload(b"Changed bytes").status_code == 409
    assert upload(b"binary", "malware.exe", "application/octet-stream").status_code == 422
    assert upload(b"not PDF", "report.pdf", "application/pdf").status_code == 422
    assert upload(b"x" * (2 * 1024 * 1024 + 1)).status_code == 413
    value = complete(client, service, root + "/research", item["research"])
    assert any(s["kind"] == "public_file" for s in value["sources"])
    cookies = dict(client.cookies)
    client.cookies.clear()
    file = client.get(root + "/files/" + item["id"])
    assert file.status_code == 200 and file.content.startswith(b"This original")
    assert "attachment" in file.headers["content-disposition"] and file.headers["content-security-policy"].startswith("sandbox")
    switch(client, cookies)
    assert action(client, root + "/discussion", item, "hide").status_code == 200
    client.cookies.clear()
    assert client.get(root + "/files/" + item["id"]).status_code == 404


def test_public_schema_roundtrip_retains_native_metadata(signed):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from test_account_deletion_migration import config

    from alembic import command as migrate
    from helvetic_lens.db import Base

    _, service, _, _ = signed
    with service.db.engine.connect() as connection:
        migrate.downgrade(config(connection), "fec495bef124")
        migrate.upgrade(config(connection), "head")
        tables = {"product_publications", "product_public_contributions", "product_investigations"}
        context = MigrationContext.configure(connection, opts={"include_object":
            lambda obj, name, kind, reflected, other: kind != "table" or name in tables})
        assert compare_metadata(context, Base.metadata) == []
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []


@pytest.mark.parametrize("revocation", ["publication", "contribution", "membership", "workspace"])
def test_inflight_public_revocation_cannot_write_late_evidence(signed, monkeypatch, revocation):
    from helvetic_lens.product_investigation_models import DossierClaim
    from helvetic_lens.product_models import ProductPublication

    client, service, identity, model = signed
    _, publication, root = setup(client, service, identity)
    account, cookies = guest(client, service)
    switch(client, cookies)
    pipeline(monkeypatch, service, model)
    item, _ = submit(client, root, kind="comment")
    run = item["research"]
    tick(service, run["id"])
    async def revoke(system, user, **kwargs):
        data = json.loads(user)
        with service.db.session(include_all_organizations=True) as session:
            if revocation == "publication":
                session.get(ProductPublication, publication["id"]).status = "withdrawn"
            elif revocation == "contribution":
                session.get(PublicContribution, item["id"]).status = "hidden"
            elif revocation == "membership":
                session.delete(session.scalar(select(OrganizationMembership).where(
                    OrganizationMembership.user_id == account["user"]["id"])))
            else:
                value = session.get(Investigation, run["id"])
                session.get(UserSession, value.session_id).organization_id = identity["organization"]["id"]
            session.commit()
        excerpt = data["source"]["excerpts"][0]
        return json.dumps({"claims": [{"statement": "A proposed finding that must never be stored.",
            "relation": "SUPPORTS", "quote": excerpt["text"], "locator": excerpt["passage"]}]})
    monkeypatch.setattr(model, "complete", revoke)
    tick(service, run["id"])
    with service.db.session(include_all_organizations=True) as session:
        assert session.get(Investigation, run["id"]).status == "paused"
        assert session.scalar(select(DossierClaim).where(DossierClaim.investigation_id == run["id"])) is None


def test_public_controls_are_current_personal_and_use_host_job_scope(signed):
    client, service, identity, _ = signed
    _, _, root = setup(client, service, identity)
    account, cookies = guest(client, service)
    _, other = guest(client, service, number=2)
    switch(client, cookies)
    with service.db.session(include_all_organizations=True) as session:
        session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == account["user"]["id"])).role = "viewer"
        session.commit()
    item, _ = submit(client, root)
    run = item["research"]
    path = root + "/research/" + run["id"]
    data = {"action": "pause", "expected_revision": run["revision"]}
    assert client.post(path + "/control", json=data).status_code == 403
    switch(client, other)
    assert client.get(path + "/workspace").json()["can_control"] is False
    assert post(client, path + "/control", data).status_code == 403
    switch(client, cookies)
    paused = post(client, path + "/control", data)
    assert paused.status_code == 200, paused.text
    assert post(client, path + "/control", data).status_code == 409
    resumed = post(client, path + "/control", {"action": "resume", "expected_revision": paused.json()["revision"]})
    assert resumed.status_code == 200, resumed.text
    with service.db.session(include_all_organizations=True) as session:
        value = session.get(Investigation, run["id"])
        assert session.get(Job, value.job_id).organization_id == identity["organization"]["id"]
        assert value.session_organization_id == account["organization"]["id"]


def test_real_account_erasure_removes_public_file_and_derived_work_but_retains_host(signed):
    import os
    from datetime import timedelta

    from test_account_deletion_api import confirmation

    from helvetic_lens.maintenance import cleanup_operational_data
    from helvetic_lens.product_models import ProductDossier, ProductPublication

    client, service, identity, _ = signed
    doc, publication, root = setup(client, service, identity)
    account, cookies = guest(client, service)
    switch(client, cookies)
    response = client.post(root + "/files", headers=_csrf(client), data={"metadata": json.dumps(command(kind="file", analyse_publicly=True))},
        files={"file": ("original.txt", b"Original public source evidence.", "text/plain")})
    assert response.status_code == 201, response.text
    item = response.json()["contribution"]
    with service.db.session(include_all_organizations=True) as session:
        artifact = service.environment_settings.storage_path / "artifacts" / session.get(PublicContribution, item["id"]).artifact_key
    assert artifact.is_file()
    old = (utcnow() - timedelta(hours=service.environment_settings.orphan_artifact_retention_hours + 1)).timestamp()
    os.utime(artifact, (old, old))
    assert cleanup_operational_data(service.db, service.environment_settings)["orphan_artifacts"] == 0
    assert artifact.is_file(), "A retained public original must survive scheduled cleanup."
    erased = post(client, "/api/account/deletion", confirmation(client))
    assert erased.status_code == 200, erased.text
    assert not artifact.exists()
    with service.db.session(include_all_organizations=True) as session:
        assert session.get(User, account["user"]["id"]) is None
        assert session.get(PublicContribution, item["id"]) is None
        assert session.get(Investigation, item["research"]["id"]) is None
        assert session.get(ProductDossier, doc["id"]) is not None
        assert session.get(ProductPublication, publication["id"]) is not None
    client.cookies.clear()
    assert client.get(root + "/files/" + item["id"]).status_code == 404
    assert client.get(root + "/research").json()["total"] == 0
