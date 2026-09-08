"""Organization policy, live workers, cancellation and no-inference configuration."""
import asyncio

import pytest
from sqlalchemy import func, select
from test_interest_automation import enable, record, second_event, wake
from test_interest_execution import artifacts, execution
from test_topic_history import execute

from helvetic_lens import interest_policy
from helvetic_lens.config import DomainError
from helvetic_lens.models import InterestBriefPolicy, InterestEventAssessment, Job, Organization

__all__ = ["artifacts", "execution"]


def save(service, **changes):
    current = service.interest_brief_policy()
    data = {name: current[name] for name in (*interest_policy.Policy.model_fields, "revision")}
    return service.save_interest_brief_policy(interest_policy.PolicyInput(**{**data, **changes}))


def test_api_bounds_conflict_noop_and_saved_persistence(harness):
    client, _, service, model = harness
    initial = client.get("/api/settings/interest-briefs").json()
    assert initial["revision"] == 0 and initial["enabled"] is False
    data = {"revision": 0, "enabled": True, "locale": "de", "max_pending": 1, "max_daily": 2}
    response = client.patch("/api/settings/interest-briefs", json=data)
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 1 and response.json()["ai_calls"] == 0
    assert client.patch("/api/settings/interest-briefs", json=data).status_code == 409
    data["revision"] = 1
    assert client.patch("/api/settings/interest-briefs", json=data).json()["revision"] == 1
    for change in [{"max_pending": 5}, {"max_daily": 21}, {"locale": "uk"}, {"enabled": "true"}, {"revision": -1}]:
        assert client.patch("/api/settings/interest-briefs", json={**data, **change}).status_code == 422
    assert not model.calls
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 0
        assert session.get(InterestBriefPolicy, service.organization_id).values["locale"] == "de"
    assert service.interest_brief_policy()["max_daily"] == 2


def test_policy_is_explicitly_scoped_even_in_privileged_session(harness):
    service = harness[2]
    save(service, enabled=True)
    with service.db.session(include_all_organizations=True) as session:
        session.add(Organization(id="policy-other", name="Other", slug="policy-other"))
        session.flush()
        session.add(InterestBriefPolicy(organization_id="policy-other", values={"enabled": False, "locale": "fr"}))
        session.commit()
        assert interest_policy.read(session, service.organization_id, service.settings)["enabled"] is True
        assert interest_policy.read(session, "policy-other", service.settings)["locale"] == "fr"


@pytest.mark.parametrize("stage", ["admission", "queued", "generate"])
def test_disable_cancels_automatic_work_without_publishing(execution, stage):
    service = enable(execution)
    save(service, enabled=True)
    admission_id = wake(execution)
    generation_id = None
    if stage != "admission":
        admitted = execute(service, admission_id)
        generation_id = admitted["result"]["data"]["outcomes"][0]["job_id"]
        assert record(service, generation_id).payload["policy_key"]
    if stage == "generate":
        def changed(phase):
            if phase == "generate":
                execution[4]["hook"] = None
                save(service, enabled=False)
        execution[4]["hook"] = changed
    else:
        save(service, enabled=False)
    result = execute(service, generation_id or admission_id)
    assert result["state"] == "cancelled", result
    assert len(execution[4]["generated"]) == int(stage == "generate")
    with service.db.session() as session:
        assert all(row.result is None for row in session.scalars(select(InterestEventAssessment)))


def test_policy_change_retains_completed_result_and_no_automatic_catchup(execution):
    service = enable(execution)
    save(service, enabled=True)
    admitted = execute(service, wake(execution))
    outcome = admitted["result"]["data"]["outcomes"][0]
    assert execute(service, outcome["job_id"])["state"] == "succeeded"
    before = len(execution[4]["requests"])
    saved = save(service, enabled=False, locale="fr")
    assert saved["cancel_requested"] == 0 and len(execution[4]["requests"]) == before
    with service.db.session() as session:
        assert session.get(InterestEventAssessment, outcome["assessment_id"]).status == "succeeded"
        assert session.scalar(select(func.count()).select_from(Job).where(
            Job.type.in_({"interest_brief_admission", "interest_event_brief"}))) == 2


def test_saved_policy_overrides_environment_for_new_matching(execution):
    service = enable(execution)
    save(service, enabled=False)
    with service.db.session() as session:
        from helvetic_lens.interest_automation import enqueue_after_matching
        assert enqueue_after_matching(session, service.settings, [execution[2]], "disabled") is None
    save(service, enabled=True, locale="de")
    service.settings.interest_brief_auto_enabled = False
    with service.db.session() as session:
        result = enqueue_after_matching(session, service.settings, [execution[2]], "enabled")
        session.commit()
        assert session.get(Job, result["job_id"]).payload["locale"] == "de"
    assert not execution[4]["requests"]


@pytest.mark.parametrize("limit", ["max_pending", "max_daily"])
def test_lower_saved_allowance_applies_to_new_admission_and_rolls_back(execution, limit):
    service = enable(execution)
    save(service, **{limit: 1})
    other_id = second_event(execution)
    first = asyncio.run(execution[1].schedule(execution[2]))
    with pytest.raises(DomainError) as error:
        asyncio.run(execution[1].schedule(other_id))
    assert error.value.code == "interest_queue_limit"
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(InterestEventAssessment)) == 1
        assert session.get(Job, first["job_id"]).state == "queued"


def test_policy_api_requires_auth_csrf_and_organization_admin(tmp_path):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_organization_access import csrf, register, settings

    from helvetic_lens.main import create_app
    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as owner, TestClient(app) as viewer, TestClient(app) as other:
        assert owner.get("/api/settings/interest-briefs").status_code == 401
        register(owner, "policy-owner@example.invalid")
        data = {"enabled": True, "locale": "it", "revision": 0}
        assert owner.patch("/api/settings/interest-briefs", json=data).status_code == 403
        assert owner.patch("/api/settings/interest-briefs", json=data, headers=csrf(owner)).status_code == 200
        invitation = owner.post("/api/organization/invitations", headers=csrf(owner),
            json={"email": "policy-viewer@example.invalid", "role": "viewer"}).json()
        register(viewer, "policy-viewer@example.invalid", invitation_token=invitation["token"])
        assert viewer.get("/api/settings/interest-briefs").json()["locale"] == "it"
        assert viewer.patch("/api/settings/interest-briefs", json={**data, "revision": 1},
                            headers=csrf(viewer)).status_code == 403
        register(other, "policy-other@example.invalid")
        assert other.get("/api/settings/interest-briefs").json()["enabled"] is False


def test_policy_migration_preserves_existing_organization(harness):
    from pathlib import Path

    from alembic.config import Config
    from sqlalchemy import inspect

    from alembic import command
    service = harness[2]
    save(service, enabled=True)
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    with service.db.engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.downgrade(cfg, "d8eaf2395cb6")
        assert "interest_brief_policies" not in inspect(connection).get_table_names()
        command.upgrade(cfg, "head")
    assert service.interest_brief_policy()["revision"] == 0
    with service.db.session() as session:
        assert session.get(Organization, service.organization_id) is not None


def test_selected_user_language_is_not_overridden_by_organization_fallback(execution):
    service = enable(execution)
    save(service, locale="en")
    generated = asyncio.run(execution[1].run(execution[2]))
    before = len(execution[4]["generated"])
    response = asyncio.run(service.read_interest_brief(execution[2]))
    assert response["status"] == "available" and response["assessment_id"] == generated["id"]
    save(service, locale="de")
    response = asyncio.run(service.read_interest_brief(execution[2]))
    assert response["locale"] == "en" and response["status"] == "available"
    # Existing explicit API callers can still read an older selected language.
    response = asyncio.run(service.read_interest_brief(execution[2], locale="en"))
    assert response["status"] == "available"
    assert len(execution[4]["generated"]) == before


def test_default_reader_api_uses_browser_language_and_rejects_hidden_event(harness):
    client, _, service, _ = harness
    from test_interest_admission import setup
    _, event_id, *_ = setup(harness)
    save(service, locale="it")
    response = client.get(f"/api/interest-feed/events/{event_id}/brief", headers={"Accept-Language": "fr-CH"})
    assert response.status_code == 200, response.text
    assert response.json()["locale"] == "fr" and response.json()["ai_calls"] == 0
    assert client.get("/api/interest-feed/events/missing/brief").status_code == 404


def test_concurrent_policy_editors_cannot_overwrite_each_other(harness):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    service = harness[2]
    if service.db.engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock concurrency check")
    barrier = Barrier(2)
    def edit(locale):
        barrier.wait(timeout=10)
        try:
            with service.db.session() as session:
                result = interest_policy.save(session, service.organization_id, service.settings,
                    interest_policy.PolicyInput(revision=0, locale=locale))
                session.commit()
                return result["locale"]
        except DomainError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(edit, ["de", "fr"]))
    assert results.count("interest_policy_conflict") == 1
    assert service.interest_brief_policy()["revision"] == 1
    assert service.interest_brief_policy()["locale"] in results


def test_matching_schedules_distinct_active_user_languages_not_admin_fallback(harness):
    from test_interest_admission import setup

    from helvetic_lens.interest_automation import enqueue_after_matching
    from helvetic_lens.models import OrganizationMembership, User
    _, event_id, *_ = setup(harness)
    service = harness[2]
    save(service, enabled=True, locale="it")
    with service.db.session() as session:
        session.add(Organization(id="foreign-language-org", name="Foreign", slug="foreign-language-org"))
        session.flush()
        for index, (locale, active, organization) in enumerate([
                ("de-CH", True, service.organization_id), ("de-CH", True, service.organization_id),
                ("fr-CH", True, service.organization_id), ("rm-CH", False, service.organization_id),
                ("it-CH", True, "foreign-language-org")]):
            user = User(id=f"language-user-{index}", email=f"language-{index}@example.invalid",
                        name="QA", password_hash="unusable", locale=locale, active=active)
            session.add(user)
            session.flush()
            session.add(OrganizationMembership(organization_id=organization, user_id=user.id))
        session.commit()
        first = enqueue_after_matching(session, service.settings, [event_id], "multilingual")
        second = enqueue_after_matching(session, service.settings, [event_id], "multilingual")
        session.commit()
        assert [item["locale"] for item in first["language_jobs"]] == ["de", "fr"]
        assert second["reused"]
        assert [item["job_id"] for item in first["language_jobs"]] == [item["job_id"] for item in second["language_jobs"]]
        assert session.scalar(select(func.count()).select_from(Job).where(Job.type == "interest_brief_admission")) == 2
    assert not harness[3].calls


def test_language_variants_do_not_supersede_each_other(harness):
    from test_interest_assessment import Model, draft_for, run
    from test_interest_assessment_store import claim, prepare, setup
    service, store, english = setup(harness)
    french = english.model_copy(update={"locale": "fr"})
    english_id, english_key, _ = prepare(service, store, english)
    token = claim(service, store, english_id, english_key)
    french_id, french_key, _ = prepare(service, store, french)
    french_token = claim(service, store, french_id, french_key)
    for value, assessment_id, key, owner in [(english, english_id, english_key, token), (french, french_id, french_key, french_token)]:
        result, provenance = run(Model(draft_for(value)), value)
        with service.db.session() as session:
            assert store.finish(session, assessment_id, owner, value, result, provider_calls=provenance["provider_calls"])
            session.commit()
        assert prepare(service, store, value) == (assessment_id, key, False)
    with service.db.session() as session:
        assert store.get(session, english_id).status == store.get(session, french_id).status == "succeeded"


def test_authenticated_reader_uses_personal_language_before_browser_default(tmp_path, monkeypatch):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_organization_access import csrf, register, settings

    from helvetic_lens.main import create_app
    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    async def echo(event_id, *, locale):
        return {"locale": locale, "ai_calls": 0}
    monkeypatch.setattr(app.state.service, "read_interest_brief", echo)
    with TestClient(app) as first, TestClient(app) as second:
        register(first, "language-first@example.invalid")
        invitation = first.post("/api/organization/invitations", headers=csrf(first),
            json={"email": "language-second@example.invalid", "role": "viewer"}).json()
        register(second, "language-second@example.invalid", invitation_token=invitation["token"])
        for client, locale in [(first, "de"), (second, "fr")]:
            changed = client.patch("/api/auth/locale", headers=csrf(client), json={"locale": locale + "-CH"})
            assert changed.status_code == 200
            response = client.get("/api/interest-feed/events/synthetic/brief", headers={"Accept-Language": "it-CH"})
            assert response.json()["locale"] == locale
        assert first.get("/api/interest-feed/events/synthetic/brief").json()["locale"] == "de"
        assert second.get("/api/interest-feed/events/synthetic/brief?locale=rm").json()["locale"] == "rm"
