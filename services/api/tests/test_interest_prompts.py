"""Saved prompt editing, measured execution, stale history and tenant scope."""

import asyncio

import pytest
from sqlalchemy import select
from test_interest_brief_reader import read
from test_interest_execution import artifacts, execution, records, run

from helvetic_lens.config import DomainError
from helvetic_lens.interest_assessment import SYSTEM
from helvetic_lens.interest_jobs import BriefJobs
from helvetic_lens.interest_prompts import current_instructions
from helvetic_lens.models import Job, PromptRevision
from helvetic_lens.prompt_settings import PromptSettingsInput

__all__ = ["artifacts", "execution"]
FOCUS = "Explain practical review priorities for a small organization, without inventing duties."


def save(service, text=FOCUS, platform=False):
    data = PromptSettingsInput(interest_brief_instructions=text)
    return (service.save_platform_prompt_settings if platform else service.save_prompt_settings)(data)


def test_custom_prompt_is_measured_generated_reused_and_reset_without_erasing_history(execution):
    service, _, _, _, state, *_ = execution
    original = run(execution)
    saved = save(service)
    assert saved["interest_brief_instructions"] == FOCUS
    assert read(execution)["status"] == "stale"
    assert len(state["generated"]) == 1  # Saving/reading did not regenerate.
    generated = run(execution)
    assert generated["id"] != original["id"]
    assert state["counts"][-1]["messages"][0]["content"] == state["generated"][-1]["messages"][0]["content"]
    assert state["generated"][-1]["messages"][0]["content"].startswith(SYSTEM)
    assert FOCUS in state["generated"][-1]["messages"][0]["content"]
    assert read(execution)["status"] == "available"
    assert run(execution)["cached"] and len(state["generated"]) == 2
    service.reset_prompt_settings()
    assert read(execution)["assessment_id"] == original["id"]
    assert len(state["generated"]) == 2 and len(records(execution)) == 2
    with service.db.session() as session:
        revision = session.scalar(select(PromptRevision).order_by(PromptRevision.revision.desc()))
        assert revision.values["interest_brief_instructions"] == FOCUS


@pytest.mark.parametrize("phase", ["runtime", "count", "generate"])
def test_persisted_prompt_edit_fences_measurement_and_publication(execution, phase):
    service, _, _, _, state, *_ = execution

    def change(current):
        if current == phase:
            state["hook"] = None
            save(service)

    state["hook"] = change
    if phase == "generate":
        result = run(execution)
        assert result["status"] == "superseded" and result["result"] is None
    else:
        with pytest.raises(DomainError, match="prompt changed"):
            run(execution)
        assert not records(execution) and not state["generated"]


def test_queued_work_does_not_generate_with_changed_saved_prompt(execution):
    service, runner, event_id, _, state, *_ = execution
    queued = asyncio.run(runner.schedule(event_id))
    save(service)
    result = asyncio.run(BriefJobs(runner).execute(queued["job_id"], "prompt-test-worker"))
    assert result["state"] == "failed"
    with service.db.session() as session:
        assert session.get(Job, queued["job_id"]).error_code == "interest_inputs_changed"
    assert not state["generated"]
    assert records(execution)[0].status == "superseded"


def test_workspace_override_platform_fallback_and_older_clients_preserve_new_field(execution):
    service = execution[0]
    save(service, platform=True)
    with service.db.session(include_all_organizations=True) as session:
        assert FOCUS in current_instructions(session, "another-organization")
    save(service, "Focus on evidence limitations and uncertainty for this organization.")
    service.save_prompt_settings(PromptSettingsInput(ask_instructions="An older client edits only Ask guidance."))
    service.save_platform_prompt_settings(PromptSettingsInput(ask_instructions="An older global client edits Ask guidance."))
    with service.db.session(include_all_organizations=True) as session:
        assert FOCUS in current_instructions(session, "another-organization")
        assert "Focus on evidence limitations" in current_instructions(session, service.organization_id)
    service.reset_prompt_settings()
    with service.db.session() as session:
        assert FOCUS in current_instructions(session, service.organization_id)
    save(service, "")
    with service.db.session() as session:
        assert current_instructions(session, service.organization_id) == SYSTEM


def test_prompt_api_accepts_empty_rejects_oversized_and_never_runs_ai(harness):
    client, _, _, model = harness
    for value, status in [("", 200), (FOCUS, 200), ("x" * 4001, 422)]:
        response = client.patch("/api/settings/prompts", json={"interest_brief_instructions": value})
        assert response.status_code == status, response.text
    assert client.get("/api/settings/prompts").json()["interest_brief_instructions"] == FOCUS
    assert not model.calls
