"""An explicit personal coverage decision never changes shared subscriptions."""

import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_auth import _csrf, _register, _settings

from helvetic_lens import source_review
from helvetic_lens.main import create_app
from helvetic_lens.models import (
    Job,
    Organization,
    OrganizationMembership,
    PersonalSourceReview,
    SourcePackChangeRequest,
    SourcePackDefinition,
    SourcePackSubscription,
)


def selection(client):
    data = client.get("/api/source-packs").json()
    return {
        "catalogue_revision": data["catalogue_revision"],
        "packs": [
            {"id": p["id"], "revision": p["revision"], "enabled": p["subscription"]["enabled"]}
            for p in data["items"]
        ],
    }


def test_review_is_personal_passive_until_explicit_and_does_not_activate(harness):
    client, _, service, model = harness
    body = selection(client)
    assert client.get("/api/onboarding").json()["source_review"] is None
    result = client.post("/api/onboarding/source-review", json=body)
    assert result.status_code == 200, result.text
    saved = result.json()
    assert saved["current"] and not any(p["enabled"] for p in saved["snapshot"]["packs"])
    body["packs"].reverse()
    assert client.post("/api/onboarding/source-review", json=body).json() == saved
    progress = client.get("/api/onboarding").json()
    assert (
        progress["source_review"] == saved
        and progress["state"] == "new"
        and not progress["completion_verified"]
    )
    with service.db.session(include_all_organizations=True) as session:
        for table in (Job, SourcePackSubscription, SourcePackChangeRequest):
            assert session.scalar(select(func.count()).select_from(table)) == 0
        assert source_review.read(session, service.organization_id, "user:colleague") is None
        assert source_review.read(session, "foreign", "anonymous-development") is None
    assert model.calls == []


@pytest.mark.parametrize("change", ["revision", "subscription", "removed", "duplicate", "catalogue"])
def test_stale_or_forged_review_is_rejected_without_overwriting_prior_review(harness, change):
    client, _, service, _ = harness
    body = selection(client)
    saved = client.post("/api/onboarding/source-review", json=body).json()
    if change == "duplicate":
        body["packs"].append(body["packs"][0])
    elif change == "catalogue":
        body["catalogue_revision"] = "old"
    else:
        with service.db.session() as session:
            definition = session.get(SourcePackDefinition, body["packs"][0]["id"])
            if change == "revision":
                definition.revision = "changed"
            elif change == "removed":
                definition.active = False
            else:
                session.add(SourcePackSubscription(pack_id=definition.id, enabled=True))
            session.commit()
        assert not client.get("/api/onboarding").json()["source_review"]["current"]
    response = client.post("/api/onboarding/source-review", json=body)
    assert response.status_code == 409, response.text
    with service.db.session() as session:
        assert session.scalar(select(PersonalSourceReview.snapshot_json)) == saved["snapshot"]
    if change not in {"duplicate", "catalogue"}:
        refreshed = client.post("/api/onboarding/source-review", json=selection(client)).json()
        assert refreshed["current"] and refreshed["first_reviewed_at"] == saved["first_reviewed_at"]
        assert refreshed["reviewed_at"] != saved["reviewed_at"]


def test_viewer_csrf_and_identity_forgery(tmp_path):
    app = create_app(_settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        account = _register(client).json()
        with app.state.service.db.session(include_all_organizations=True) as session:
            session.scalar(
                select(OrganizationMembership).where(OrganizationMembership.user_id == account["user"]["id"])
            ).role = "viewer"
            session.commit()
        body = selection(client)
        assert client.post("/api/onboarding/source-review", json=body).status_code == 403
        assert (
            client.post(
                "/api/onboarding/source-review", json={**body, "user_id": "other"}, headers=_csrf(client)
            ).status_code
            == 422
        )
        assert (
            client.post("/api/onboarding/source-review", json=body, headers=_csrf(client)).status_code == 200
        )


def test_privileged_snapshot_does_not_borrow_foreign_subscription(harness):
    client, _, service, _ = harness
    body = selection(client)
    with service.db.session(include_all_organizations=True) as session:
        session.add(Organization(id="foreign-review", name="Foreign", slug="foreign-review"))
        session.flush()
        session.add(
            SourcePackSubscription(
                organization_id="foreign-review", pack_id=body["packs"][0]["id"], enabled=True
            )
        )
        session.commit()
        own = source_review.snapshot(session, service.organization_id)
        assert not any(p["enabled"] for p in own["packs"])
        assert any(p["enabled"] for p in source_review.snapshot(session, "foreign-review")["packs"])


def test_source_review_migration_preserves_prior_personal_data(harness):
    from pathlib import Path

    from alembic.config import Config

    from alembic import command

    client, _, service, _ = harness
    client.patch("/api/onboarding", json={"action": "topic"})
    assert client.post("/api/onboarding/source-review", json=selection(client)).status_code == 200
    directory = Path(__file__).resolve().parents[1]
    config = Config(str(directory / "alembic.ini"))
    config.set_main_option("script_location", str(directory / "alembic"))
    with service.db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "fd50c94f632b")
        command.upgrade(config, "head")
    result = client.get("/api/onboarding").json()
    assert result["intent"] == "topic" and result["source_review"] is None
