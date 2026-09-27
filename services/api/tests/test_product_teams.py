"""HTTP team journeys, alternate native paths and current worker access."""
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_auth import _csrf, _register
from test_product_contributions import model_output, no_discovery, submit, upload
from test_product_dossiers import ROOT, active, create, post
from test_product_dossiers import signed as signed
from test_product_investigations import complete, tick

from helvetic_lens.account_deletion_plan import inventory
from helvetic_lens.account_erasure_store import direct_roots
from helvetic_lens.db import utcnow
from helvetic_lens.legal_profile_models import LegalMonitoringProfile
from helvetic_lens.models import OrganizationMembership, User
from helvetic_lens.product_models import DossierInvitation, DossierMember


def colleague(client, service, identity, *, role="viewer", number=1):
    owner = dict(client.cookies)
    client.cookies.clear()
    account = _register(client, f"colleague{number}@example.ch").json()
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=account["user"]["id"], organization_id=identity["organization"]["id"], role=role))
        session.commit()
    result = post(client, "/api/auth/session/organization", {"organization_id": identity["organization"]["id"]})
    assert result.status_code == 200, result.text
    cookies = dict(client.cookies)
    switch(client, owner)
    return account["user"]["id"], cookies


def switch(client, cookies):
    client.cookies.clear()
    client.cookies.update(cookies)


def managed(client):
    doc, _ = create(client)
    root = ROOT + "/" + doc["id"]
    result = post(client, root + "/team/enable", {"expected_revision": 1})
    assert result.status_code == 200, result.text
    return doc, root


def invite(client, root, user_id, role="CONTRIBUTOR"):
    team = client.get(root + "/team").json()
    body = {"expected_revision": team["revision"], "request_key": str(uuid4()), "user_id": user_id, "role": role}
    result = post(client, root + "/team/invitations", body)
    assert result.status_code == 201, result.text
    assert post(client, root + "/team/invitations", body).json()["invitation"]["id"] == result.json()["invitation"]["id"]
    assert post(client, root + "/team/invitations", {**body, "role": "VIEWER" if role != "VIEWER" else "EDITOR"}).status_code == 409
    return result.json()["invitation"]


def accept(client, invitation):
    result = post(client, "/api/products/pharma/dossier-invitations/" + invitation["id"] + "/accept", {})
    assert result.status_code == 200, result.text
    return result.json()


def change(client, root, user_id, role):
    current = client.get(root + "/team").json()
    return client.put(root + "/team/members/" + user_id, headers=_csrf(client),
        json={"expected_revision": current["revision"], "role": role})


@pytest.mark.parametrize("role", ["VIEWER", "CONTRIBUTOR", "EDITOR"])
def test_invitation_account_bound_private_readers_and_role_matrix(signed, role):
    client, service, identity, _ = signed
    user_id, cookies = colleague(client, service, identity)
    doc, root = managed(client)
    other, _ = create(client)
    original = client.post(root + "/files", headers=_csrf(client), files={"file": ("private.txt", b"Private source text.", "text/plain")}).json()
    invitation = invite(client, root, user_id, role)
    wrong = post(client, "/api/products/pharma/dossier-invitations/" + invitation["id"] + "/accept", {})
    assert wrong.status_code == 404
    switch(client, cookies)
    assert client.get(root).status_code == 404
    assert client.get(ROOT).json()["total"] == 0
    inbox = client.get("/api/products/pharma/dossier-invitations").json()
    assert inbox["total"] == 1 and inbox["items"][0]["role"] == role
    assert post(client, "/api/products/loyer/dossier-invitations/" + invitation["id"] + "/accept", {}).status_code == 404
    assert client.post("/api/products/pharma/dossier-invitations/" + invitation["id"] + "/accept").status_code == 403
    assert accept(client, invitation) == {"dossier_id": doc["id"], "role": role}
    assert accept(client, invitation)["dossier_id"] == doc["id"]
    assert client.get(ROOT).json()["total"] == 1
    assert client.get("/api/monitoring-profiles").json()["total"] == 1
    assert client.get(ROOT + "/" + other["id"]).status_code == 404
    for route in (root, root + "/export", root + "/entries", root + "/team", "/api/monitoring-profiles/" + doc["profile"]["id"]):
        assert client.get(route).status_code == 200, route
    assert client.get(root + "/files/" + original["id"]).content == b"Private source text."
    assert client.get(root).json()["access"]["role"] == role
    body = {"request_key": str(uuid4()), "kind": "note", "body": "An attributed contribution."}
    assert post(client, root + "/entries", body).status_code == (403 if role == "VIEWER" else 201)
    assert post(client, root + "/investigations", {"request_key": str(uuid4()), "question": "Public research question", "public_query_confirmed": True}).status_code == (202 if role == "EDITOR" else 403)
    profile = doc["profile"]
    saved = client.put("/api/monitoring-profiles/" + profile["id"], headers=_csrf(client),
        json={"config": profile["config"], "step": 1, "expected_revision": profile["revision"]})
    assert saved.status_code == (200 if role == "EDITOR" else 403), saved.text
    assert post(client, root + "/publication/withdraw", {}).status_code == 403
    assert post(client, root + "/team/enable", {"expected_revision": 1}).status_code == 403
    assert post(client, "/api/monitoring-profiles/" + profile["id"] + "/activate", {"expected_revision": 1}).status_code == 403


def test_contributor_real_analysis_and_revocation_stops_worker_and_every_reader(signed, monkeypatch):
    client, service, identity, model = signed
    owner = dict(client.cookies)
    user_id, cookies = colleague(client, service, identity)
    doc, root = managed(client)
    invitation = invite(client, root, user_id)
    switch(client, cookies)
    accept(client, invitation)
    model_output(monkeypatch, model)
    external = no_discovery(monkeypatch)
    entry, _ = submit(client, root)
    completed = complete(client, service, root + "/investigations", entry["analysis"])
    assert completed["status"] == "completed" and completed["evidence"] and not external
    later, _ = submit(client, root, body="This queued contribution must not be analysed after revocation.")
    original = upload(client, root, b"Private original").json()
    switch(client, owner)
    current = client.get(root + "/team").json()
    assert post(client, root + f"/team/members/{user_id}/remove", {"expected_revision": current["revision"]}).status_code == 200
    tick(service, later["analysis"]["id"])
    paused = client.get(root + "/investigations/" + later["analysis"]["id"]).json()
    assert paused["status"] == "paused" and paused["claims"] == []
    switch(client, cookies)
    for route in (root, root + "/export", root + "/entries", root + "/investigations",
                  root + "/files/" + original["id"], "/api/monitoring-profiles/" + doc["profile"]["id"]):
        assert client.get(route).status_code == 404, route
    assert client.get(ROOT).json()["total"] == 0
    assert client.get("/api/monitoring-profiles").json()["total"] == 0
    assert doc["id"] not in client.get("/api/products/pharma/workbench").text
    assert doc["id"] not in client.get("/api/products/pharma/discover?provider=workspace&q=Private").text
    assert post(client, root + "/entries", {"request_key": str(uuid4()), "kind": "note", "body": "denied"}).status_code == 404
    assert post(client, "/api/products/pharma/dossier-invitations/" + invitation["id"] + "/accept", {}).status_code == 409


@pytest.mark.parametrize("state", ["expired", "revoked", "issuer_demoted"])
def test_pending_invitation_cannot_survive_expiry_revocation_or_owner_change(signed, state):
    client, service, identity, _ = signed
    user_id, cookies = colleague(client, service, identity)
    _, root = managed(client)
    item = invite(client, root, user_id)
    if state == "expired":
        with service.db.session() as session:
            session.get(DossierInvitation, item["id"]).expires_at = utcnow() - timedelta(seconds=1)
            session.commit()
    elif state == "revoked":
        team = client.get(root + "/team").json()
        assert post(client, root + "/team/invitations/" + item["id"] + "/revoke", {"expected_revision": team["revision"]}).status_code == 200
    else:
        with service.db.session() as session:
            session.get(DossierMember, (root.split("/")[-1], identity["user"]["id"])).role = "EDITOR"
            session.commit()
    switch(client, cookies)
    assert post(client, "/api/products/pharma/dossier-invitations/" + item["id"] + "/accept", {}).status_code == 409
    assert client.get(root).status_code == 404


def test_handover_conflict_erasure_retention_and_native_membership_removal(signed):
    client, service, identity, _ = signed
    owner = dict(client.cookies)
    user_id, cookies = colleague(client, service, identity, role="organization_admin")
    doc, root = managed(client)
    item = invite(client, root, user_id, "EDITOR")
    switch(client, cookies)
    accept(client, item)
    switch(client, owner)
    assert change(client, root, identity["user"]["id"], "EDITOR").status_code == 409
    assert client.put(root + "/team/members/" + user_id, headers=_csrf(client), json={"expected_revision": 1, "role": "OWNER"}).status_code == 409
    with service.db.session(include_all_organizations=True) as session:
        plan = inventory(session, identity["user"]["id"], identity["organization"]["id"])
        assert any(item["kind"] == "dossier_owner" for item in plan.public["blockers"])
    assert change(client, root, user_id, "OWNER").status_code == 200
    assert change(client, root, identity["user"]["id"], "EDITOR").status_code == 200
    with service.db.session(include_all_organizations=True) as session:
        plan = inventory(session, identity["user"]["id"], identity["organization"]["id"])
        assert not any(item["kind"] == "dossier_owner" for item in plan.public["blockers"])
        conditions = direct_roots(LegalMonitoringProfile.__table__, session.get(User, identity["user"]["id"]), [])
        from sqlalchemy import or_
        assert session.scalar(select(LegalMonitoringProfile.id).where(LegalMonitoringProfile.id == doc["profile"]["id"], or_(*conditions))) is None
        membership = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == identity["organization"]["id"]))
        membership_id = membership.id
    response = client.delete("/api/organization/members/" + membership_id, headers=_csrf(client))
    assert response.status_code == 409, response.text
    assert "Transfer dossier ownership" in response.text
    # Erase the original creator after real handover: retain the invited team's
    # draft and original file even though the profile still names its creator.
    original = upload(client, root, b"Shared draft original").json()
    third_user, _ = colleague(client, service, identity, role="organization_admin", number=2)
    from test_account_erasure_store import erase

    with service.db.session(include_all_organizations=True) as session:
        session.get(User, user_id).platform_admin = True
        session.commit()
    erase(service.db, identity["user"]["id"], identity["organization"]["id"])
    switch(client, cookies)
    retained = client.get(root)
    assert retained.status_code == 200 and retained.json()["access"]["role"] == "OWNER"
    assert client.get(root + "/files/" + original["id"]).content == b"Shared draft original"
    with service.db.session() as session:
        assert session.get(LegalMonitoringProfile, doc["profile"]["id"]).created_by_user_id is None
        assert session.connection().exec_driver_sql("PRAGMA foreign_key_check").all() == []
    # A transferred draft with a departed creator is now private to its sole
    # remaining owner. Their own erasure removes it without erasing the workspace.
    with service.db.session(include_all_organizations=True) as session:
        session.get(User, third_user).platform_admin = True
        session.commit()
    erase(service.db, user_id, identity["organization"]["id"])
    with service.db.session() as session:
        assert session.get(LegalMonitoringProfile, doc["profile"]["id"]) is None
        assert session.connection().exec_driver_sql("PRAGMA foreign_key_check").all() == []


def test_activation_audience_confirmation_and_admin_role_override_native_topic(signed):
    client, service, identity, _ = signed
    owner = dict(client.cookies)
    user_id, cookies = colleague(client, service, identity, role="organization_admin")
    doc, root = managed(client)
    item = invite(client, root, user_id, "VIEWER")
    switch(client, cookies)
    accept(client, item)
    switch(client, owner)
    profile_route = "/api/monitoring-profiles/" + doc["profile"]["id"]
    assert post(client, profile_route + "/activate", {"expected_revision": 1}).status_code == 409
    response = post(client, profile_route + "/activate", {"expected_revision": 1, "share_with_workspace_confirmed": True})
    assert response.status_code == 200, response.text
    topic = response.json()["topics"][0]
    switch(client, cookies)
    assert client.get(root).json()["access"]["audience"] == "workspace"
    assert post(client, root + "/entries", {"request_key": str(uuid4()), "kind": "note", "body": "denied"}).status_code == 403
    assert post(client, profile_route + "/status", {"expected_revision": 2, "status": "paused"}).status_code == 403
    response = post(client, "/api/monitoring-topics/" + topic["id"] + "/history-scan", {})
    assert response.status_code == 403, response.text


def test_unmanaged_active_dossiers_preserve_workspace_roles_and_cannot_be_taken_over(signed):
    client, service, identity, _ = signed
    _, cookies = colleague(client, service, identity, role="organization_admin")
    doc, _ = create(client)
    active(client, doc)
    switch(client, cookies)
    root = ROOT + "/" + doc["id"]
    assert client.get(root).json()["access"]["role"] == "EDITOR"
    assert post(client, root + "/entries", {"request_key": str(uuid4()), "kind": "note", "body": "Existing team rights."}).status_code == 201
    assert post(client, root + "/team/enable", {"expected_revision": 1}).status_code == 403


def test_team_migration_preserves_existing_originals_and_has_scoped_membership_constraints(signed):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from test_account_deletion_migration import config

    from alembic import command
    from helvetic_lens.db import Base

    client, service, _, _ = signed
    doc, _ = create(client)
    root = ROOT + "/" + doc["id"]
    saved = client.post(root + "/files", headers=_csrf(client), files={"file": ("evidence.txt", b"Retained evidence", "text/plain")}).json()
    tables = {"product_dossiers", "product_dossier_members", "product_dossier_invitations"}
    with service.db.engine.connect() as connection:
        command.downgrade(config(connection), "fbc495bef124")
        command.upgrade(config(connection), "head")
        context = MigrationContext.configure(connection, opts={"include_object":
            lambda obj, name, kind, reflected, other: kind != "table" or name in tables})
        assert compare_metadata(context, Base.metadata) == []
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert any(row[2] == "organization_memberships" for row in connection.exec_driver_sql("PRAGMA foreign_key_list(product_dossier_members)"))
    current = client.get(root).json()
    assert current["access"]["managed"] is False and current["access"]["audience"] == "author"
    assert client.get(root + "/files/" + saved["id"]).content == b"Retained evidence"


def test_role_revocation_during_model_result_discards_late_claims(signed, monkeypatch):
    client, service, identity, model = signed
    user_id, cookies = colleague(client, service, identity)
    doc, root = managed(client)
    item = invite(client, root, user_id)
    switch(client, cookies)
    accept(client, item)
    model_output(monkeypatch, model)
    original_complete = model.complete

    async def revoke_after_inference(*args, **kwargs):
        result = await original_complete(*args, **kwargs)
        with service.db.session() as session:
            session.get(DossierMember, (doc["id"], user_id)).role = "VIEWER"
            session.commit()
        return result

    monkeypatch.setattr(model, "complete", revoke_after_inference)
    entry, _ = submit(client, root)
    result = complete(client, service, root + "/investigations", entry["analysis"])
    assert result["status"] == "paused" and result["claims"] == [] and result["evidence"] == []
