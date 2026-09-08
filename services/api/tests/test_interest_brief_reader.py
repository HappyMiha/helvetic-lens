"""Reading existing shared briefs must never become an inference trigger."""

import asyncio

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm.attributes import flag_modified
from test_interest_execution import artifacts, execution, run

from helvetic_lens.config import DomainError
from helvetic_lens.models import (
    InterestEventAssessment,
    Job,
    Profile,
    RegulatoryDocumentVersion,
    RegulatoryEventState,
)

__all__ = ["artifacts", "execution"]


def read(value, locale="en"):
    value[0].model_client = value[1].client
    return asyncio.run(value[0].read_interest_brief(value[2], locale=locale))


def test_unscheduled_read_makes_no_runtime_or_generation_calls(execution):
    response = read(execution)
    assert response["status"] == "not_scheduled" and response["result"] is None
    assert not execution[4]["requests"]


def test_exact_shared_result_reuses_without_generation_or_jobs(execution):
    generated = run(execution)
    state = execution[4]
    count, requests = len(state["generated"]), len(state["requests"])
    with execution[0].db.session() as session:
        jobs = session.scalar(select(func.count()).select_from(Job))
    response = read(execution)
    assert response["status"] == "available", response
    assert response["assessment_id"] == generated["id"] and response["result"] == generated["result"]
    assert response["ai_calls"] == 0 and response["saved_at"]
    assert len(state["generated"]) == count
    assert len(state["requests"]) == requests + 1
    assert state["requests"][-1].method == "GET"
    with execution[0].db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == jobs


@pytest.mark.parametrize("change", ["source", "profile", "approval", "runtime", "locale", "cloud"])
def test_changed_current_binding_never_displays_saved_answer_as_current(execution, change):
    generated = run(execution)
    if change in {"source", "profile"}:
        with execution[0].db.session() as session:
            if change == "source":
                session.get(RegulatoryDocumentVersion, execution[3]).text += " corrected"
            else:
                profile = session.scalar(select(Profile))
                profile.description += " changed organization activities"
                profile.revision += 1
            session.commit()
    elif change == "approval":
        execution[6]["profiles"][0]["status"] = "revoked"
        execution[7]()
    elif change == "runtime":
        execution[4]["runtime"]["identity"]["chat_template_sha256"] = "9" * 64
    elif change == "cloud":
        execution[0].settings.apertus_provider = "infomaniak"
    response = read(execution, "fr" if change == "locale" else "en")
    assert response["status"] in {"stale", "not_current", "not_scheduled", "runtime_unverified"}, response
    assert response["result"] is None and len(execution[4]["generated"]) == 1
    with execution[0].db.session() as session:
        row = session.get(InterestEventAssessment, generated["id"])
        assert row.status == "succeeded" and row.result == generated["result"]


@pytest.mark.parametrize("corruption", ["citation", "official_status", "proof", "calls", "extra"])
def test_corrupted_saved_output_or_proof_is_not_displayed(execution, corruption):
    generated = run(execution)
    with execution[0].db.session() as session:
        row = session.get(InterestEventAssessment, generated["id"])
        if corruption == "proof":
            row.provenance = {**row.provenance, "execution": None}
        elif corruption == "calls":
            row.provenance = {**row.provenance, "provider_calls": True}
            flag_modified(row, "provenance")  # Python's True == 1 must not suppress this corruption fixture.
        elif corruption == "citation":
            row.result = {**row.result, "citations": []}
        elif corruption == "extra":
            row.result = {**row.result, "invented": "not permitted"}
        else:
            row.result = {**row.result, "official_status": "invented enactment"}
        session.commit()
    response = read(execution)
    assert response["status"] == "unavailable" and response["result"] is None
    assert len(execution[4]["generated"]) == 1


def test_pending_and_failed_read_do_not_retry(execution):
    queued = asyncio.run(execution[1].schedule(execution[2]))
    assert read(execution)["status"] == "pending"
    with execution[0].db.session() as session:
        row = session.get(InterestEventAssessment, queued["id"])
        row.status, row.error_code = "failed", "model_timeout"
        session.commit()
    assert read(execution)["status"] == "failed"
    assert not execution[4]["generated"]


def test_unknown_event_denied_before_runtime_probe(execution):
    execution[0].model_client = execution[1].client
    with pytest.raises(DomainError) as error:
        asyncio.run(execution[0].read_interest_brief("not-an-event"))
    assert error.value.status == 404 and not execution[4]["requests"]


def test_revoked_admission_denies_saved_answer_before_runtime_probe(execution):
    run(execution)
    count = len(execution[4]["requests"])
    with execution[0].db.session() as session:
        session.execute(delete(RegulatoryEventState).where(RegulatoryEventState.event_id == execution[2]))
        session.commit()
    with pytest.raises(DomainError) as error:
        read(execution)
    assert error.value.status == 404 and len(execution[4]["requests"]) == count


def test_privileged_reader_still_requires_the_requested_organization(execution):
    from helvetic_lens.interest_brief_reader import read as read_saved
    run(execution)
    with execution[0].db.session(include_all_organizations=True) as session:
        with pytest.raises(DomainError) as error:
            read_saved(session, "foreign-organization", execution[2])
    assert error.value.status == 404


def test_available_citations_link_to_exact_saved_native_passage(execution):
    run(execution)
    response = read(execution)
    for citation in response["result"]["citations"]:
        assert response["evidence_links"][citation["id"]] == f"/corpus-evidence/{citation['version_id']}?passage={citation['unit_id']}"
    assert len(response["interest_names"]) == 2


def test_http_reader_validates_locale_and_never_schedules(execution, harness):
    client = harness[0]
    response = client.get(f"/api/interest-feed/events/{execution[2]}/brief?locale=de")
    assert response.status_code == 200 and response.json()["status"] == "not_scheduled"
    assert client.get(f"/api/interest-feed/events/{execution[2]}/brief?locale=xx").status_code == 422
    assert client.get("/api/interest-feed/events/missing/brief").status_code == 404
    assert not execution[4]["requests"]


def test_legacy_material_citations_open_saved_version_not_native_route(execution, harness):
    from test_interest_material import setup_saved
    _, event_id, _, _, _ = setup_saved(harness, count=400)
    asyncio.run(execution[1].run(event_id))
    execution[0].model_client = execution[1].client
    response = asyncio.run(execution[0].read_interest_brief(event_id))
    assert response["status"] == "available", response
    assert response["result"]["source_comparison"] is not None
    for citation in response["result"]["citations"]:
        assert response["evidence_links"][citation["id"]] == f"/evidence/{citation['version_id']}?passage={citation['unit_id']}"
