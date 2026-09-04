from conftest import LAW_URL, FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from sqlalchemy import select

from helvetic_lens.auth import CSRF_COOKIE
from helvetic_lens.config import Settings
from helvetic_lens.main import create_app
from helvetic_lens.models import AdministrativeAudit, OrganizationMembership, User


def settings(tmp_path):
    return Settings(
        _env_file=None,
        database_url="sqlite:///" + (tmp_path / "admin.db").as_posix(),
        data_dir=tmp_path / "admin-data",
        app_environment="test",
        allow_anonymous_dev=False,
        job_execution_mode="inline",
        apertus_provider="custom",
        apertus_base_url="",
        apertus_api_key="",
        firecrawl_api_key="",
    )


def register(client, email):
    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "name": "Admin Example",
            "organization_name": email.split("@")[0],
        },
    )
    assert response.status_code == 201
    return response.json()


def csrf(client):
    return {"X-CSRF-Token": client.cookies.get(CSRF_COOKIE)}


def promote(service, email):
    with service.db.session(include_all_organizations=True) as session:
        user = session.scalar(select(User).where(User.email == email))
        user.platform_admin = True
        session.commit()


def test_platform_reads_are_isolated_and_status_is_bounded(tmp_path):
    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        register(client, "owner@example.ch")
        denied = client.get("/api/admin/status")
        assert denied.status_code == 403
        assert denied.json()["code"] == "platform_admin_required"

        promote(app.state.service, "owner@example.ch")
        status = client.get("/api/admin/status")
        assert status.status_code == 200
        payload = status.json()
        assert payload["scope"] == "platform"
        assert payload["services"]["api"] == "healthy"
        assert payload["resources"]["organizations"] == 2  # legacy bootstrap plus registered org
        assert "dead_letters" in payload["jobs"]
        assert payload["ai_triage"]["records"]["total"] == 0
        assert payload["ai_triage"]["latency"]["deterministic_overview"]["samples"] == 0
        assert payload["ai_triage"]["relation_review"]["entries"] == 0
        assert "retention" in payload["storage"]
        assert payload["storage"]["retention"]["integration_logs_days"] == 30
        assert payload["storage"]["retention"]["terminal_jobs_days"] == 90
        assert payload["storage"]["retention"]["document_evidence"] == "immutable"
        assert payload["storage"]["retention"]["ai_history"] == "user_retained"
        assert payload["backup"]["status"] == "not_configured"

        deployments = client.get("/api/admin/deployments")
        assert deployments.status_code == 200
        assert deployments.json()["service"]["state"] == "not_configured"


def test_platform_admin_with_viewer_membership_can_manage_only_the_platform(tmp_path):
    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        identity = register(client, "platform-viewer@example.ch")
        with app.state.service.db.session(include_all_organizations=True) as session:
            user = session.scalar(select(User).where(User.id == identity["user"]["id"]))
            membership = session.scalar(
                select(OrganizationMembership).where(
                    OrganizationMembership.user_id == identity["user"]["id"],
                    OrganizationMembership.organization_id == identity["organization"]["id"],
                )
            )
            user.platform_admin = True
            membership.role = "viewer"
            session.commit()

        current = client.get("/api/auth/session").json()
        assert current["platform_admin"] is True
        assert current["role"] == "viewer"

        defaults = client.get("/api/admin/prompts")
        assert defaults.status_code == 200
        editable = {
            key: defaults.json()[key]
            for key in (
                "impact_instructions",
                "impact_synthesis_instructions",
                "ask_instructions",
                "answer_synthesis_instructions",
                "repair_instructions",
                "ask_context_mode",
            )
        }
        assert (
            client.patch("/api/admin/prompts", json=editable, headers=csrf(client)).status_code
            == 200
        )

        organization_write = client.patch(
            "/api/profile",
            json={
                "name": "Must remain unchanged",
                "description": "",
                "business_areas": [],
            },
            headers=csrf(client),
        )
        assert organization_write.status_code == 403
        assert organization_write.json()["code"] == "viewer_read_only"


def test_organization_status_and_mutation_audit_never_capture_request_body(tmp_path):
    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        identity = register(client, "workspace@example.ch")
        added = client.post(
            "/api/laws",
            json={"url": LAW_URL, "name": "Private watch title", "synthetic": True},
            headers=csrf(client),
        )
        assert added.status_code == 201
        status = client.get("/api/organization/status").json()
        assert status["scope"] == "organization"
        assert status["workspace"]["members"] == 1
        assert status["workspace"]["active_watches"] == 1
        assert status["ai"]["execution"] == "cloud"

        with app.state.service.db.session(include_all_organizations=True) as session:
            audit = session.scalar(
                select(AdministrativeAudit)
                .where(AdministrativeAudit.organization_id == identity["organization"]["id"])
                .order_by(AdministrativeAudit.created_at.desc())
            )
            assert audit.actor_user_id == identity["user"]["id"]
            assert audit.scope == "organization"
            assert audit.result == "succeeded" and audit.response_status == 201
            assert audit.method == "POST" and audit.path == "/api/laws"
            assert "Private watch title" not in audit.action


def test_platform_prompt_defaults_are_inherited_until_an_organization_overrides_them(tmp_path):
    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as administrator:
        register(administrator, "platform@example.ch")
        promote(app.state.service, "platform@example.ch")
        defaults = administrator.get("/api/admin/prompts").json()
        defaults["ask_instructions"] = (
            "Answer briefly in the user's language and preserve every reference to saved evidence."
        )
        editable = {
            key: defaults[key]
            for key in (
                "impact_instructions",
                "impact_synthesis_instructions",
                "ask_instructions",
                "answer_synthesis_instructions",
                "repair_instructions",
                "ask_context_mode",
            )
        }
        saved = administrator.patch("/api/admin/prompts", json=editable, headers=csrf(administrator))
        assert saved.status_code == 200
        assert saved.json()["scope"] == "platform_default"

        with TestClient(app) as organization:
            register(organization, "organization@example.ch")
            inherited = organization.get("/api/settings/prompts")
            assert inherited.status_code == 200
            assert inherited.json()["source"] == "platform_default"
            assert inherited.json()["ask_instructions"] == editable["ask_instructions"]
            assert organization.get("/api/admin/prompts").status_code == 403
