"""Real persisted provider edits while a separate execution keeps old settings."""
import asyncio

import pytest
from sqlalchemy import select
from test_interest_brief_reader import read
from test_interest_execution import artifacts, execution, records, run

from helvetic_lens.config import DomainError
from helvetic_lens.interest_execution import configuration_key
from helvetic_lens.interest_jobs import BriefJobs
from helvetic_lens.model_settings import PUBLIC_FIELDS
from helvetic_lens.models import ApertusConfiguration, InterestEventAssessment, Organization

__all__ = ["artifacts", "execution"]


@pytest.fixture
def bound(execution, monkeypatch):
    service, runner, *_ = execution
    monkeypatch.setattr("helvetic_lens.model_settings.local_docker_base_url",
                        lambda: runner.client.settings.apertus_base_url)
    values = {name: getattr(runner.client.settings, f"apertus_{name}") for name in PUBLIC_FIELDS}
    with service.db.session() as session:
        session.add(ApertusConfiguration(id=service.tenant_record_id, values=values, key_source="none"))
        session.commit()
    service.model_client = runner.client
    return (service, service.interest_runner(), *execution[2:])


def edit(bound, **changes):
    service = bound[0]
    with service.db.session() as session:
        record = session.get(ApertusConfiguration, service.tenant_record_id)
        record.values = {**record.values, **changes}
        session.commit()


@pytest.mark.parametrize("phase", ["runtime", "count", "generate"])
@pytest.mark.parametrize("field,value", [("model", "different-local-model"),
    ("provider", "infomaniak"), ("explanation_profile", "another-reviewed-profile"),
    ("max_tokens", 900), ("temperature", 0.7)])
def test_persisted_configuration_change_fences_old_execution(bound, phase, field, value):
    state = bound[4]
    old = getattr(bound[1].client.settings, f"apertus_{field}")

    def change(current):
        if current == phase:
            state["hook"] = None
            edit(bound, **{field: value})
    state["hook"] = change
    if phase == "generate":
        result = run(bound)
        assert result["status"] == "superseded" and result["result"] is None
        assert len(state["generated"]) == 1
    else:
        with pytest.raises(DomainError) as error:
            run(bound)
        assert error.value.code == "interest_inputs_changed"
        assert not records(bound) and not state["generated"]
    assert getattr(bound[1].client.settings, f"apertus_{field}") == old


def test_stale_service_client_refused_before_contact_and_queued_generation(bound):
    edit(bound, temperature=0.8)
    with pytest.raises(DomainError) as error:
        run(bound)
    assert error.value.code == "interest_inputs_changed" and not bound[4]["requests"]


def test_queued_configuration_edit_prevents_generation(bound):
    queued = asyncio.run(bound[1].schedule(bound[2]))
    edit(bound, explanation_profile="changed-profile")
    response = asyncio.run(BriefJobs(bound[1]).execute(queued["job_id"], "config-worker"))
    assert response["state"] == "failed" and not bound[4]["generated"]
    assert records(bound)[0].status == "superseded"


@pytest.mark.parametrize("phase", ["before", "during"])
def test_reader_rechecks_database_without_erasing_history_or_generating(bound, phase):
    original = run(bound)
    state = bound[4]
    before = len(state["requests"])
    if phase == "before":
        edit(bound, temperature=0.7)
    else:
        def change(current):
            if current == "runtime":
                state["hook"] = None
                edit(bound, temperature=0.7)
        state["hook"] = change
    response = read(bound)
    assert response["status"] == "not_current" and response["result"] is None
    assert len(state["generated"]) == 1
    assert len(state["requests"]) == before + int(phase == "during")
    with bound[0].db.session() as session:
        saved = session.get(InterestEventAssessment, original["id"])
        assert saved.status == "succeeded" and saved.result == original["result"]


def test_transport_and_credential_edits_preserve_exact_shared_reuse(bound):
    first = run(bound)
    edit(bound, timeout_seconds=50, request_retries=0, batch_concurrency=2)
    with bound[0].db.session() as session:
        record = session.scalar(select(ApertusConfiguration))
        record.key_source, record.api_key = "saved", "synthetic-not-a-real-key"
        session.commit()
    assert run(bound)["id"] == first["id"]
    assert read(bound)["status"] == "available"
    assert len(bound[4]["generated"]) == 1


def test_privileged_configuration_read_is_explicitly_scoped_and_refreshed(bound):
    service = bound[0]
    with service.db.session(include_all_organizations=True) as session:
        session.add(Organization(id="foreign-config", name="Other", slug="foreign-config"))
        session.flush()
        session.add(ApertusConfiguration(id="foreign-config", organization_id="foreign-config",
            values={"provider": "infomaniak", "model": "foreign-model"}, key_source="none"))
        session.commit()
        original = service.brief_configuration(session)
        assert original == configuration_key(bound[1].client.settings)
        edit(bound, temperature=0.7)
        assert service.brief_configuration(session) != original
    assert not bound[4]["requests"]


def test_reset_to_environment_with_old_client_fails_before_model_contact(bound):
    service = bound[0]
    with service.db.session() as session:
        session.delete(session.get(ApertusConfiguration, service.tenant_record_id))
        session.commit()
    # An externally supplied test client otherwise retains the legacy fallback;
    # use the production environment-resolution branch for this reset scenario.
    service._provided_model_client = False
    with pytest.raises(DomainError) as error:
        run(bound)
    assert error.value.code == "interest_inputs_changed" and not bound[4]["requests"]


def test_supersession_cannot_modify_a_newer_attempt(bound):
    service, runner = bound[:2]
    state = bound[4]
    def changed(current):
        if current == "generate":
            state["hook"] = None
            edit(bound, temperature=0.7)
            with service.db.session() as session:
                record = session.scalar(select(InterestEventAssessment))
                record.attempt_key = "new-worker-token"
                session.commit()
    state["hook"] = changed
    result = run(bound)
    assert result["status"] == "running" and result["result"] is None
    assert records(bound)[0].attempt_key == "new-worker-token"
