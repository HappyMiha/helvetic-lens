"""Guests use real native sessions, scoped evidence and the durable coordinator."""
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_auth import _csrf, _register
from test_private_dossier_monitoring import matches, private, remove
from test_product_contributions import model_output, no_discovery, submit
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_investigations import complete
from test_product_teams import change, colleague, switch

from helvetic_lens.db import utcnow
from helvetic_lens.models import OrganizationMembership, User, UserSession
from helvetic_lens.product_investigation_models import Investigation
from helvetic_lens.product_models import DossierMember


def guest(client, service, *, verified=True, number=1):
    owner = dict(client.cookies)
    client.cookies.clear()
    account = _register(client, f"guest{number}@example.ch", "Guest workspace").json()
    if verified:
        with service.db.session(include_all_organizations=True) as session:
            session.get(User, account["user"]["id"]).email_verified_at = utcnow()
            session.commit()
    cookies = dict(client.cookies)
    switch(client, owner)
    return account, cookies


def invitation(client, root, account, role="EDITOR"):
    data = {"expected_revision": client.get(root + "/team").json()["revision"],
        "request_key": str(uuid4()), "email": account["user"]["email"], "role": role}
    result = post(client, root + "/team/invitations", data)
    assert result.status_code == 201, result.text
    assert post(client, root + "/team/invitations", data).json()["invitation"]["id"] == result.json()["invitation"]["id"]
    return result.json()["invitation"]


def accept(client, root, item):
    route = root.split("/dossiers/")[0] + "/dossier-invitations/" + item["id"] + "/accept"
    result = post(client, route, {})
    assert result.status_code == 200, result.text
    assert post(client, route, {}).status_code == 200


@pytest.mark.parametrize("product", ["pharma", "loyer"])
@pytest.mark.parametrize("role", ["VIEWER", "CONTRIBUTOR", "EDITOR"])
def test_guest_journey_native_isolation_roles_originals_and_matches(signed, product, role):
    client, service, identity, _ = signed
    owner = dict(client.cookies)
    account, cookies = guest(client, service)
    other_account, other_cookies = guest(client, service, number=2)
    hidden_id, _ = colleague(client, service, identity, role="organization_admin")
    doc, root, topic = private(client, product)
    _, sibling, _ = private(client, product)
    _, match = matches(service, topic)
    original = client.post(root + "/files", headers=_csrf(client), files={"file": ("guest.txt", b"Guest evidence", "text/plain")}).json()
    hidden_original = client.post(sibling + "/files", headers=_csrf(client), files={"file": ("sibling.txt", b"Sibling private original", "text/plain")}).json()
    item = invitation(client, root, account, role)
    prefix = f"/api/products/{product}"
    switch(client, other_cookies)
    assert client.get(prefix + "/dossier-invitations").json()["total"] == 0
    assert post(client, prefix + "/dossier-invitations/" + item["id"] + "/accept", {}).status_code == 404
    switch(client, cookies)
    assert client.get(root).status_code == 404
    inbox = client.get(prefix + "/dossier-invitations").json()
    assert inbox["total"] == 1 and inbox["items"][0]["is_guest"] is True
    assert client.get(prefix.replace(product, "loyer" if product == "pharma" else "pharma") + "/dossier-invitations").json()["total"] == 0
    before_session = client.get("/api/auth/session").json()
    accept(client, root, item)
    assert client.get("/api/auth/session").json() == before_session
    with service.db.session(include_all_organizations=True) as session:
        assert session.scalar(select(func.count()).select_from(OrganizationMembership).where(
            OrganizationMembership.user_id == account["user"]["id"])) == 1
        member = session.get(DossierMember, (doc["id"], account["user"]["id"]))
        assert member.is_guest and member.membership_organization_id is None
    shared = client.get(prefix + "/shared-dossiers").json()
    assert shared["total"] == 1 and shared["items"][0]["id"] == doc["id"]
    assert client.get(prefix + "/shared-dossiers?offset=50").json()["items"] == []
    for path in (root, root + "/export", root + "/entries", root + "/team", root + "/matches"):
        response = client.get(path)
        assert response.status_code == 200, (path, response.text)
    assert client.get(root + "/files/" + original["id"]).content == b"Guest evidence"
    assert client.get(root + "/files/" + hidden_original["id"]).status_code == 404
    assert client.get(root + "/matches").json()[0]["id"] == match
    access = client.get(root).json()["access"]
    assert access["is_guest"] is True and access["role"] == role
    assert not any(access[key] for key in ["can_configure", "can_manage", "can_monitor", "can_publish", "can_activate", "can_watch_pages"])
    for path in (sibling, sibling + "/export", "/api/monitoring-profiles/" + doc["profile"]["id"],
            "/api/monitoring-topics/" + topic["id"], "/api/monitoring-topics/" + topic["id"] + "/matches",
            root.replace(product, "loyer" if product == "pharma" else "pharma")):
        assert client.get(path).status_code == 404, path
    for path in (prefix + "/dossiers", prefix + "/workbench", "/api/monitoring-profiles", "/api/monitoring-topics", "/api/jobs", "/api/interest-feed"):
        response = client.get(path)
        assert response.status_code == 200 and doc["id"] not in response.text and topic["id"] not in response.text
    assert client.get(root + "/team").json()["colleagues"] == []
    assert hidden_id not in client.get(root + "/assignees").text
    assert identity["user"]["id"] in client.get(root + "/assignees").text
    result = post(client, root + "/entries", {"request_key": str(uuid4()), "kind": "note", "body": "Guest note"})
    assert result.status_code == (403 if role == "VIEWER" else 201), result.text
    result = post(client, root + "/investigations", {"request_key": str(uuid4()), "question": "Guest public research", "public_query_confirmed": True})
    assert result.status_code == (202 if role == "EDITOR" else 403), result.text
    for suffix in ("source-advice", "improve", "improvements/apply", "publication/withdraw", "team/enable"):
        assert post(client, root + "/" + suffix, {}).status_code == 403, suffix
    switch(client, owner)
    assert change(client, root, account["user"]["id"], "OWNER").status_code == 409
    remove(client, root, account["user"]["id"])
    switch(client, cookies)
    assert client.get(prefix + "/shared-dossiers").json()["total"] == 0
    assert client.get(root).status_code == 404
    assert client.get(root + "/files/" + original["id"]).status_code == 404


def test_guest_verified_exact_email_required(signed):
    client, service, _, _ = signed
    account, _ = guest(client, service, verified=False)
    _, root, _ = private(client)
    for email in (account["user"]["email"], "absent@example.ch"):
        response = post(client, root + "/team/invitations", {"expected_revision": client.get(root + "/team").json()["revision"],
            "request_key": str(uuid4()), "email": email, "role": "EDITOR"})
        assert response.status_code == 404 and "verified email" in response.text


@pytest.mark.parametrize("revocation", [None, "grant", "session", "session_workspace", "membership"])
def test_guest_real_worker_and_late_result_revocation(signed, monkeypatch, revocation):
    client, service, _, model = signed
    owner = dict(client.cookies)
    account, cookies = guest(client, service)
    doc, root, _ = private(client)
    item = invitation(client, root, account, "CONTRIBUTOR")
    switch(client, cookies)
    accept(client, root, item)
    model_output(monkeypatch, model)
    external = no_discovery(monkeypatch)
    original_complete = model.complete

    async def extract(*args, **kwargs):
        result = await original_complete(*args, **kwargs)
        if revocation:
            with service.db.session(include_all_organizations=True) as session:
                if revocation == "grant":
                    session.delete(session.get(DossierMember, (doc["id"], account["user"]["id"])))
                elif revocation == "membership":
                    membership = session.scalar(select(OrganizationMembership).where(
                        OrganizationMembership.user_id == account["user"]["id"]))
                    session.delete(membership)
                else:
                    for login in session.scalars(select(UserSession).where(UserSession.user_id == account["user"]["id"])):
                        if revocation == "session_workspace":
                            login.organization_id = service.organization_id
                        else:
                            login.revoked_at = utcnow()
                session.commit()
        return result

    monkeypatch.setattr(model, "complete", extract)
    entry, _ = submit(client, root)
    with service.db.session() as session:
        run = session.get(Investigation, entry["analysis"]["id"])
        assert run.organization_id == service.organization_id
        assert run.session_organization_id == account["organization"]["id"]
    switch(client, owner)
    result = complete(client, service, root + "/investigations", entry["analysis"])
    assert not external
    assert result["status"] == ("paused" if revocation else "completed"), result
    assert bool(result["claims"]) is (not revocation)
    if not revocation:
        assert result["original"]["author"] == account["user"]["name"]
        assert result["evidence"]


def test_guest_schema_migration_and_erasure_preserve_native_cascade(signed):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from test_account_deletion_migration import config

    from alembic import command
    from helvetic_lens.db import Base
    from helvetic_lens.product_models import DossierInvitation, ProductDossier

    client, service, identity, _ = signed
    with service.db.engine.connect() as connection:
        command.downgrade(config(connection), "fdc495bef124")
        command.upgrade(config(connection), "head")
        tables = {"product_dossier_members", "product_dossier_invitations", "product_investigations"}
        context = MigrationContext.configure(connection, opts={"include_object":
            lambda obj, name, kind, reflected, other: kind != "table" or name in tables})
        assert compare_metadata(context, Base.metadata) == []
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    account, cookies = guest(client, service)
    native_id, native_cookies = colleague(client, service, identity)
    doc, root, _ = private(client)
    item = invitation(client, root, account)
    switch(client, cookies)
    accept(client, root, item)
    with service.db.engine.connect() as connection:
        with pytest.raises(RuntimeError, match="guest grants"):
            command.downgrade(config(connection), "fdc495bef124")
        assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar() == "ffc495bef124"
    with service.db.session(include_all_organizations=True) as session:
        native = DossierMember(dossier_id=doc["id"], organization_id=identity["organization"]["id"], user_id=native_id, role="EDITOR")
        session.add(native)
        session.commit()
        assert native.membership_organization_id == identity["organization"]["id"]
        membership = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == native_id,
            OrganizationMembership.organization_id == identity["organization"]["id"]))
        session.delete(membership)
        session.commit()
        session.expunge_all()
        assert session.get(DossierMember, (doc["id"], native_id)) is None
        assert session.get(DossierMember, (doc["id"], account["user"]["id"])) is not None
    from test_account_deletion_api import confirmation

    response = post(client, "/api/account/deletion", confirmation(client))
    assert response.status_code == 200, response.text
    with service.db.session(include_all_organizations=True) as session:
        assert session.get(User, account["user"]["id"]) is None
        assert session.get(DossierMember, (doc["id"], account["user"]["id"])) is None
        assert session.get(DossierInvitation, item["id"]) is None
        assert session.get(ProductDossier, doc["id"]) is not None
        assert session.get(DossierMember, (doc["id"], identity["user"]["id"])).role == "OWNER"



def test_guest_draft_and_connected_source_reader_do_not_open_host_library(signed):
    from test_product_document_history import setup
    from test_product_teams import managed

    client, service, identity, _ = signed
    owner = dict(client.cookies)
    account, cookies = guest(client, service)
    draft, draft_root = managed(client)
    draft_invite = invitation(client, draft_root, account)
    doc, root, law, version, history = setup(client)
    assert post(client, root + "/team/enable", {"expected_revision": 1}).status_code == 200
    item = invitation(client, root, account)
    _, sibling, _, _, _ = setup(client)
    hidden_id, _ = colleague(client, service, identity, role="organization_admin", number=7)
    switch(client, cookies)
    accept(client, draft_root, draft_invite)
    accept(client, root, item)
    assert client.get(draft_root).json()["access"]["audience"] == "invited_team"
    assert client.get(history).status_code == 200
    assert client.get(history + "/" + version).status_code == 200
    assert client.get(sibling + "/documents/" + law + "/versions").status_code == 404
    assert client.get("/api/laws/" + law).status_code == 404
    action = {"creation_key": str(uuid4()), "title": "Check shared evidence", "assignee_user_id": hidden_id}
    assert post(client, root + "/actions", action).status_code == 422
    action["assignee_user_id"] = identity["user"]["id"]
    response = post(client, root + "/actions", action)
    assert response.status_code == 201, response.text
    switch(client, owner)
    remove(client, root, account["user"]["id"])
    switch(client, cookies)
    assert client.get(history).status_code == 404
    assert client.get(history + "/" + version).status_code == 404
