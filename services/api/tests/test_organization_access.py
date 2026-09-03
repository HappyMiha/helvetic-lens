from conftest import LAW_URL, FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient

from helvetic_lens.admin_cli import run as run_admin
from helvetic_lens.auth import CSRF_COOKIE
from helvetic_lens.config import Settings
from helvetic_lens.main import create_app


def settings(tmp_path):
    return Settings(
        _env_file=None,
        database_url="sqlite:///" + (tmp_path / "organizations.db").as_posix(),
        data_dir=tmp_path / "organization-data",
        app_environment="test",
        allow_anonymous_dev=False,
        session_cookie_secure=False,
        job_execution_mode="inline",
        apertus_provider="custom",
        apertus_base_url="",
        apertus_api_key="",
        firecrawl_api_key="",
    )


def csrf(client):
    return {"X-CSRF-Token": client.cookies.get(CSRF_COOKIE)}


def register(client, email, *, invitation_token=""):
    return client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "name": email.split("@")[0].title(),
            "organization_name": "Test workspace",
            "invitation_token": invitation_token,
        },
    )


def test_invited_viewer_sees_shared_workspace_but_cannot_mutate(tmp_path):
    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as owner, TestClient(app) as viewer:
        organization = register(owner, "owner@example.ch").json()["organization"]
        invitation_response = owner.post(
            "/api/organization/invitations",
            json={"email": "viewer@example.ch", "role": "viewer"},
            headers=csrf(owner),
        )
        assert invitation_response.status_code == 201, invitation_response.text
        invitation = invitation_response.json()
        assert invitation["status"] == "pending" and invitation["token"]

        joined = register(viewer, "viewer@example.ch", invitation_token=invitation["token"])
        assert joined.status_code == 201, joined.text
        assert joined.json()["organization"]["id"] == organization["id"]
        assert joined.json()["role"] == "viewer"

        law = owner.post(
            "/api/laws",
            json={"url": LAW_URL, "synthetic": True},
            headers=csrf(owner),
        )
        assert law.status_code == 201
        assert viewer.get("/api/laws").json()[0]["id"] == law.json()["id"]
        rejected = viewer.post(
            "/api/laws",
            json={"url": "https://example.ch/other", "synthetic": True},
            headers=csrf(viewer),
        )
        assert rejected.status_code == 403
        assert rejected.json()["code"] == "viewer_read_only"
        assert viewer.post("/api/scans", json={}, headers=csrf(viewer)).status_code == 403
        personal_state = viewer.patch(
            "/api/impact-inbox/events/00000000-0000-0000-0000-000000000000/state",
            json={"state": "read"},
            headers=csrf(viewer),
        )
        assert personal_state.status_code == 404
        assert personal_state.json()["code"] == "not_found"
        assert (
            viewer.post(
                "/api/relation-candidates/00000000-0000-0000-0000-000000000000/reanalyse-jobs",
                headers=csrf(viewer),
            ).status_code
            == 403
        )
        assert (
            viewer.post(
                "/api/relation-candidates/00000000-0000-0000-0000-000000000000/reviews",
                json={"decision": "confirmed"},
                headers=csrf(viewer),
            ).status_code
            == 403
        )

        members = owner.get("/api/organization/members").json()
        assert {member["role"] for member in members} == {"organization_admin", "viewer"}
        invitations = owner.get("/api/organization/invitations").json()
        assert invitations[0]["status"] == "accepted"


def test_last_admin_is_protected_and_handover_allows_removal(tmp_path):
    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as owner, TestClient(app) as colleague:
        register(owner, "owner@example.ch")
        invitation = owner.post(
            "/api/organization/invitations",
            json={"email": "colleague@example.ch", "role": "viewer"},
            headers=csrf(owner),
        ).json()
        register(colleague, "colleague@example.ch", invitation_token=invitation["token"])
        members = owner.get("/api/organization/members").json()
        owner_member = next(member for member in members if member["current"])
        colleague_member = next(member for member in members if not member["current"])

        last_admin = owner.patch(
            f"/api/organization/members/{owner_member['id']}",
            json={"role": "viewer"},
            headers=csrf(owner),
        )
        assert last_admin.status_code == 409 and last_admin.json()["code"] == "last_admin"

        handover = owner.post(
            "/api/organization/handover",
            json={"membership_id": colleague_member["id"]},
            headers=csrf(owner),
        )
        assert handover.status_code == 200
        removed = colleague.delete(f"/api/organization/members/{owner_member['id']}", headers=csrf(colleague))
        assert removed.status_code == 200
        assert owner.get("/api/laws").status_code == 401


def test_existing_account_can_accept_and_switch_between_organizations(tmp_path):
    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as first, TestClient(app) as second:
        first_org = register(first, "first@example.ch").json()["organization"]
        second_org = register(second, "second@example.ch").json()["organization"]
        invitation = first.post(
            "/api/organization/invitations",
            json={"email": "second@example.ch", "role": "viewer"},
            headers=csrf(first),
        ).json()
        accepted = second.post(
            "/api/invitations/accept", json={"token": invitation["token"]}, headers=csrf(second)
        )
        assert accepted.status_code == 200 and accepted.json()["organization"]["id"] == first_org["id"]
        assert len(accepted.json()["organizations"]) == 2
        switched = second.post(
            "/api/auth/session/organization",
            json={"organization_id": second_org["id"]},
            headers=csrf(second),
        )
        assert switched.status_code == 200 and switched.json()["role"] == "organization_admin"


def test_invitation_is_single_use_and_bound_to_email(tmp_path):
    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as owner, TestClient(app) as wrong, TestClient(app) as invited:
        register(owner, "owner@example.ch")
        invitation = owner.post(
            "/api/organization/invitations",
            json={"email": "invited@example.ch", "role": "viewer"},
            headers=csrf(owner),
        ).json()
        mismatch = register(wrong, "wrong@example.ch", invitation_token=invitation["token"])
        assert mismatch.status_code == 403 and mismatch.json()["code"] == "invitation_email_mismatch"
        assert (
            register(invited, "invited@example.ch", invitation_token=invitation["token"]).status_code == 201
        )
        replay = register(wrong, "another@example.ch", invitation_token=invitation["token"])
        assert replay.status_code == 410 and replay.json()["code"] == "invitation_invalid"


def test_pending_invitation_can_be_revoked_and_platform_actions_are_separate(tmp_path):
    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as owner, TestClient(app) as invited:
        register(owner, "owner@example.ch")
        invitation = owner.post(
            "/api/organization/invitations",
            json={"email": "invited@example.ch", "role": "viewer"},
            headers=csrf(owner),
        ).json()
        platform_action = owner.post(
            "/api/admin/models/apertus-1.5b-q4/license",
            json={"accepted": True},
            headers=csrf(owner),
        )
        assert platform_action.status_code == 403
        assert platform_action.json()["code"] == "platform_admin_required"
        revoked = owner.delete(f"/api/organization/invitations/{invitation['id']}", headers=csrf(owner))
        assert revoked.status_code == 200 and revoked.json()["status"] == "revoked"
        rejected = register(invited, "invited@example.ch", invitation_token=invitation["token"])
        assert rejected.status_code == 410 and rejected.json()["code"] == "invitation_invalid"


def test_platform_admin_cli_is_idempotent_and_protects_last_admin(tmp_path, capsys):
    app_settings = settings(tmp_path)
    app = create_app(app_settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as first, TestClient(app) as second:
        register(first, "first@example.ch")
        register(second, "second@example.ch")

    assert run_admin(["promote", "first@example.ch"], settings=app_settings) == 0
    assert run_admin(["promote", "first@example.ch"], settings=app_settings) == 0
    assert run_admin(["demote", "first@example.ch"], settings=app_settings) == 1
    assert run_admin(["promote", "second@example.ch"], settings=app_settings) == 0
    assert run_admin(["demote", "first@example.ch"], settings=app_settings) == 0
    assert run_admin(["list"], settings=app_settings) == 0
    output = capsys.readouterr()
    assert "second@example.ch" in output.out
    assert "Promote another platform administrator" in output.err
