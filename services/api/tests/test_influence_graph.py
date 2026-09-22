"""Evidence integrity, tenant isolation and immutable editorial workflows."""

from copy import deepcopy
from uuid import uuid4

from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from influence.test_contract import document, save_body
from sqlalchemy import select, text
from test_auth import _csrf, _register, _settings

from helvetic_lens.influence_models import InfluenceDossier, InfluenceRevision
from helvetic_lens.main import create_app
from helvetic_lens.models import OrganizationMembership


def test_authenticated_complete_workflow_and_restart(tmp_path):
    settings = _settings(tmp_path)
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as owner:
        assert owner.get("/api/influence/dossiers").status_code == 401
        assert _register(owner).status_code == 201
        body = save_body()
        assert owner.post("/api/influence/dossiers", json=body).status_code == 403
        created = owner.post("/api/influence/dossiers", headers=_csrf(owner), json=body)
        assert created.status_code == 201, created.text
        record = created.json()
        root = "/api/influence/dossiers/" + record["id"]
        assert len(record["documentHash"]) == 64
        assert record["document"]["sources"][0]["snapshotText"] == document()["sources"][0]["snapshotText"]
        assert (
            owner.post("/api/influence/dossiers", headers=_csrf(owner), json=body).json()["id"]
            == record["id"]
        )
        changed_replay = deepcopy(body)
        changed_replay["document"]["title"] = "Conflicting retry"
        assert (
            owner.post("/api/influence/dossiers", headers=_csrf(owner), json=changed_replay).status_code
            == 409
        )
        review = {
            "expectedRevision": 1,
            "decision": "reviewed",
            "note": "Inspected the original extract.",
            "requestId": str(uuid4()),
        }
        assert owner.post(root + "/reviews", headers=_csrf(owner), json=review).status_code == 201
        assert len(owner.post(root + "/reviews", headers=_csrf(owner), json=review).json()["reviews"]) == 1
        edited = document()
        edited["title"] = "Corrected dossier"
        edited["sources"][0]["snapshotText"] += " A correction was published."
        update = save_body(edited, 1)
        result = owner.patch(root, headers=_csrf(owner), json=update)
        assert result.status_code == 200, result.text
        assert result.json()["revision"] == 2 and result.json()["reviews"] == []
        assert result.json()["documentHash"] != record["documentHash"]
        assert owner.patch(root, headers=_csrf(owner), json=update).json()["revision"] == 2
        assert owner.patch(root, headers=_csrf(owner), json=save_body(document(), 1)).status_code == 409
        assert (
            owner.post(
                root + "/reviews", headers=_csrf(owner), json={**review, "requestId": str(uuid4())}
            ).status_code
            == 409
        )
        original = owner.get(root + "?revision=1").json()
        assert original["document"] == record["document"] and len(original["reviews"]) == 1
        assert owner.get(root).headers["cache-control"] == "no-store"
        first = owner.get(root + "/history?limit=1").json()
        assert first["items"][0]["revision"] == 2 and first["nextCursor"] == 2
        assert owner.get(root + "/history?before_revision=2").json()["items"][0]["revision"] == 1
        archive = {
            "expectedRevision": 2,
            "archived": True,
            "note": "Completed research case.",
            "requestId": str(uuid4()),
        }
        assert owner.post(root + "/archive", headers=_csrf(owner), json=archive).json()["revision"] == 3
        assert owner.get("/api/influence/dossiers").json()["items"] == []
        assert owner.get("/api/influence/dossiers?archived=true").json()["items"][0]["id"] == record["id"]
        assert owner.patch(root, headers=_csrf(owner), json=save_body(edited, 3)).status_code == 409
        restored = owner.post(
            root + "/archive",
            headers=_csrf(owner),
            json={**archive, "expectedRevision": 3, "archived": False, "requestId": str(uuid4())},
        )
        assert restored.json()["revision"] == 4 and not restored.json()["archived"]
        cookies = dict(owner.cookies)
    # Reopen the application against the same migrated database.
    restarted = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(restarted) as owner:
        owner.cookies.update(cookies)
        assert owner.get(root).json()["document"]["title"] == "Corrected dossier"
        assert len(owner.get(root + "/history").json()["items"]) == 4
        with restarted.state.service.db.session(include_all_organizations=True) as session:
            assert session.execute(text("PRAGMA foreign_key_check")).all() == []


def test_tenant_visibility_viewer_and_revoked_membership(tmp_path):
    app = create_app(_settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as owner:
        registration = _register(owner).json()
        row = owner.post("/api/influence/dossiers", headers=_csrf(owner), json=save_body()).json()
        root = "/api/influence/dossiers/" + row["id"]
        owner_cookies = dict(owner.cookies)
        owner.cookies.clear()
        assert (
            _register(owner, email="other@example.ch", organization="Different workspace").status_code == 201
        )
        assert owner.get("/api/influence/dossiers").json()["items"] == []
        for suffix in ("", "?revision=1", "/history"):
            response = owner.get(root + suffix)
            assert response.status_code == 404 and "Synthetic" not in response.text
            assert response.headers["cache-control"] == "no-store"
        assert owner.patch(root, headers=_csrf(owner), json=save_body(revision=1)).status_code == 404
        assert (
            owner.post(
                root + "/reviews",
                headers=_csrf(owner),
                json={
                    "expectedRevision": 1,
                    "decision": "reviewed",
                    "note": "No access",
                    "requestId": str(uuid4()),
                },
            ).status_code
            == 404
        )
        owner.cookies.clear()
        owner.cookies.update(owner_cookies)
        db = app.state.service.db
        with db.session(include_all_organizations=True) as session:
            member = session.scalar(
                select(OrganizationMembership).where(
                    OrganizationMembership.user_id == registration["user"]["id"]
                )
            )
            member.role = "viewer"
            session.commit()
        assert owner.get(root).status_code == 200
        assert owner.patch(root, headers=_csrf(owner), json=save_body(revision=1)).status_code == 403
        assert (
            owner.post("/api/influence/dossiers", headers=_csrf(owner), json=save_body()).status_code == 403
        )
        with db.session(include_all_organizations=True) as session:
            member = session.scalar(
                select(OrganizationMembership).where(
                    OrganizationMembership.user_id == registration["user"]["id"]
                )
            )
            session.delete(member)
            session.commit()
        assert owner.get(root).status_code in (401, 403)
        with db.session(include_all_organizations=True) as session:
            assert (
                session.scalar(select(InfluenceDossier).where(InfluenceDossier.id == row["id"])).revision == 1
            )
            assert (
                len(
                    list(
                        session.scalars(
                            select(InfluenceRevision).where(InfluenceRevision.dossier_id == row["id"])
                        )
                    )
                )
                == 1
            )
