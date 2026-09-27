from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from test_auth import _register
from test_product_community import setup
from test_product_dossiers import ROOT, active, post
from test_product_dossiers import signed as signed
from test_product_publications import draft, preview_and_publish

from helvetic_lens.models import DigestPreference, MonitoringTopic, OrganizationMembership, UserSession
from helvetic_lens.product_models import ProductDossier, PublicDossierCopy, PublicReuseReceipt


def prepare(client, discussion):
    path = discussion.replace("/discussion", "/reuse")
    result = post(client, path + "/preview", {"expected_revision": 1, "name": "My independent research",
        "goal": "Track evidence relevant to my own question and priorities."})
    assert result.status_code == 200, result.text
    preview = result.json()
    command = {**preview["draft"], "preview_token": preview["preview_token"],
        "preview_expires_at": preview["preview_expires_at"], "request_key": str(uuid4()), "confirm_private_copy": True}
    return path, preview, command


def test_reviewed_cross_organization_copy_has_complete_public_origin_and_no_implicit_activation(signed):
    client, service, owner, _ = signed
    doc, publication, discussion = setup(client)
    post(client, ROOT + "/" + doc["id"] + "/entries", {"request_key": str(uuid4()), "kind": "note", "body": "PRIVATE-PARENT"})
    person = _register(client, "copy-author@example.ch").json()
    cookies = dict(client.cookies)
    path, preview, body = prepare(client, discussion)
    assert preview["snapshot"]["id"] == publication["id"]
    assert "PRIVATE-PARENT" not in str(preview) and doc["id"] not in str(preview)
    result = post(client, path, body)
    assert result.status_code == 201, result.text
    copy = result.json()
    assert post(client, path, body).json() == copy
    read = client.get(ROOT + "/" + copy["dossier_id"]).json()
    assert read["profile"]["status"] == "draft" and read["profile"]["step"] == 0
    config = read["profile"]["config"]
    assert config["name"] == body["name"] and config["goal"] == body["goal"]
    assert config["delivery"] == "off" and not config["delivery_consent"]
    assert not config["topics"] and not config["source_pack_ids"] and not config["source_requests"]
    assert read["public_origin"]["snapshot"] == preview["snapshot"]
    assert read["public_origin"]["snapshot_sha256"] == preview["snapshot_sha256"]
    assert read["entries"][0]["url"] == preview["snapshot"]["sources"][0]["url"]
    assert "PRIVATE-PARENT" not in str(read) and not read["documents"]
    assert client.get(ROOT + "/" + copy["dossier_id"] + "/export").json()["public_origin"] == read["public_origin"]
    with service.db.session(include_all_organizations=True) as session:
        assert session.get(ProductDossier, copy["dossier_id"]).organization_id == person["organization"]["id"]
        assert session.scalar(select(MonitoringTopic)) is None
        assert session.scalar(select(DigestPreference)) is None
        session.add(OrganizationMembership(organization_id=person["organization"]["id"], user_id=owner["user"]["id"], role="organization_admin"))
        session.commit()
    colleague = _register(client, "copy-colleague@example.ch").json()
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(organization_id=person["organization"]["id"], user_id=colleague["user"]["id"], role="organization_admin"))
        session.commit()
    post(client, "/api/auth/session/organization", {"organization_id": person["organization"]["id"]})
    assert client.get(ROOT + "/" + copy["dossier_id"]).status_code == 404
    assert post(client, path, body).status_code == 409
    client.cookies.clear()
    client.cookies.update(cookies)
    assert client.get(ROOT + "/" + copy["dossier_id"]).status_code == 200


@pytest.mark.parametrize("changed", ["name", "goal", "confirm_private_copy", "preview_token", "expiry", "revision", "product"])
def test_exact_preview_and_consent_reject_changed_copy(signed, changed):
    client, service, _, _ = signed
    _, _, discussion = setup(client)
    path, _, body = prepare(client, discussion)
    if changed in ("name", "goal"):
        body[changed] += " Unreviewed content"
    elif changed == "confirm_private_copy":
        body[changed] = False
    elif changed == "preview_token":
        body[changed] = "0" * 64
    elif changed == "expiry":
        body["preview_expires_at"] = "2020-01-01T00:00:00Z"
    elif changed == "revision":
        body["expected_revision"] = 2
    else:
        path = path.replace("pharma", "loyer")
    assert post(client, path, body).status_code in (404, 409)
    with service.db.session() as session:
        assert session.scalar(select(PublicDossierCopy)) is None


def test_preview_session_expiry_and_revocation_are_checked(signed, monkeypatch):
    client, service, _, _ = signed
    _, _, discussion = setup(client)
    path, _, body = prepare(client, discussion)
    from helvetic_lens import product_reuse
    now = product_reuse.utcnow()
    monkeypatch.setattr(product_reuse, "utcnow", lambda: now + timedelta(minutes=31))
    assert post(client, path, body).status_code == 409
    monkeypatch.setattr(product_reuse, "utcnow", lambda: now)
    original = product_reuse.principal

    def invalidate(session, identity, *args, **kwargs):
        session.get(UserSession, identity.session_id).revoked_at = now
        session.flush()
        return original(session, identity, *args, **kwargs)

    monkeypatch.setattr(product_reuse, "principal", invalidate)
    assert post(client, path, body).status_code == 401
    with service.db.session() as session:
        assert session.scalar(select(PublicDossierCopy)) is None


def test_source_revision_withdrawal_and_durable_copy_tombstones(signed):
    client, service, _, _ = signed
    doc, _, discussion = setup(client)
    path, _, body = prepare(client, discussion)
    saved = post(client, path, body).json()
    retry = deepcopy(body)
    retry["goal"] += " Different copy"
    assert post(client, path, retry).status_code == 409
    preview_and_publish(client, doc["id"], draft(1))
    assert post(client, path, {**body, "request_key": str(uuid4())}).status_code == 409
    assert post(client, ROOT + "/" + doc["id"] + "/publication/withdraw", {"expected_revision": 2, "request_key": str(uuid4())}).status_code == 200
    assert post(client, path, body).json()["dossier_id"] == saved["dossier_id"]
    assert post(client, path, {**body, "request_key": str(uuid4())}).status_code == 404
    with service.db.session() as session:
        session.execute(delete(ProductDossier).where(ProductDossier.id == doc["id"]))
        session.commit()
    assert client.get(ROOT + "/" + saved["dossier_id"]).json()["public_origin"]["source_url"].endswith(discussion.split("/")[-2])
    assert post(client, path, body).status_code == 201
    with service.db.session() as session:
        session.execute(delete(ProductDossier).where(ProductDossier.id == saved["dossier_id"]))
        session.commit()
        assert session.scalar(select(PublicReuseReceipt)).dossier_id is None
        assert session.get(PublicDossierCopy, saved["dossier_id"]) is None
    assert post(client, path, body).status_code == 404


def test_viewer_anonymous_and_csrf_denials(signed):
    client, service, person, _ = signed
    _, _, discussion = setup(client)
    path, preview, body = prepare(client, discussion)
    assert client.post(path, json=body).status_code == 403
    with service.db.session() as session:
        membership = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == person["user"]["id"]))
        membership.role = "viewer"
        session.commit()
    assert post(client, path + "/preview", preview["draft"]).status_code == 403
    assert post(client, path, body).status_code == 403
    client.cookies.clear()
    assert client.post(path, json=body).status_code == 401
    assert client.post(path + "/preview", json=preview["draft"]).status_code == 401


def test_migration_preserves_public_discussion_and_origin_is_retained_after_activation(signed):
    from test_account_deletion_migration import config

    from alembic import command as migration

    client, service, _, _ = signed
    _, _, discussion = setup(client)
    with service.db.engine.begin() as connection:
        migration.downgrade(config(connection), "f7c495bef124")
        migration.upgrade(config(connection), "head")
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    assert client.get(discussion).status_code == 200
    path, _, body = prepare(client, discussion)
    result = post(client, path, body)
    assert result.status_code == 201, result.text
    doc = client.get(ROOT + "/" + result.json()["dossier_id"]).json()
    # Activation still requires the existing setup validation, and cannot be
    # implied by merely creating the copy with no selected topics or sources.
    profile = doc["profile"]
    assert post(client, f"/api/monitoring-profiles/{profile['id']}/activate", {"expected_revision": profile["revision"]}).status_code == 422
    with service.db.session() as session:
        from test_legal_profiles import config as ready_config

        from helvetic_lens.legal_profile_models import LegalMonitoringProfile
        from helvetic_lens.legal_profiles import ProfileConfig
        session.get(LegalMonitoringProfile, profile["id"]).config_json = ProfileConfig.model_validate(ready_config()).model_dump(mode="json")
        session.commit()
    active(client, doc)
    assert client.get(ROOT + "/" + doc["id"]).json()["public_origin"] == doc["public_origin"]


def test_full_snapshot_and_personal_retry_receipts_follow_native_erasure(signed):
    from helvetic_lens.account_erasure_store import erase_selected, select_private_rows
    from helvetic_lens.models import User

    client, service, _, _ = signed
    doc, _, discussion = setup(client)
    publication, _ = preview_and_publish(client, doc["id"], draft(1, body="x" * 29990 + "COPY-END!!"))
    assert publication["revision"] == 2
    person = _register(client, "erase-copy@example.ch").json()
    path = discussion.replace("/discussion", "/reuse")
    preview = post(client, path + "/preview", {"expected_revision": 2, "name": "Full length copy", "goal": "Research the complete published material."}).json()
    body = {**preview["draft"], "preview_token": preview["preview_token"], "preview_expires_at": preview["preview_expires_at"],
        "request_key": str(uuid4()), "confirm_private_copy": True}
    response = post(client, path, body)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert len(saved["origin"]["snapshot"]["body"]) == 30000
    assert saved["origin"]["snapshot"]["body"].endswith("COPY-END!!")
    with service.db.session(include_all_organizations=True) as session:
        user = session.get(User, person["user"]["id"])
        selection = select_private_rows(session, user, [person["organization"]["id"]])
        assert selection.counts["product_public_reuse_receipts"] == 1
        assert selection.counts["product_public_copies"] == 1
        erase_selected(session, user, selection)
        session.commit()
        assert session.get(PublicDossierCopy, saved["dossier_id"]) is None
        assert session.scalar(select(PublicReuseReceipt).where(PublicReuseReceipt.actor_user_id == user.id)) is None
        assert session.get(ProductDossier, doc["id"]) is not None
